# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "faster-whisper>=1.1,<2",
#   "av>=11,<19",
#   "yt-dlp[default]",
# ]
# ///
"""Prepare timestamped evidence; summarization is performed by the skill agent."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def run(args):
    return subprocess.run([str(x) for x in args], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def timestamp(seconds):
    value = int(seconds)
    return f"{value // 3600:02}:{value // 60 % 60:02}:{value % 60:02}"


def parse_captions(data):
    segments = []
    for event in data.get("events", []):
        text = "".join(s.get("utf8", "") for s in event.get("segs", [])).strip()
        if not text:
            continue
        start = event.get("tStartMs", 0) / 1000
        end = start + event.get("dDurationMs", 0) / 1000
        # Drop identical overlapping rolling captions, preserving repeated later speech.
        if segments and text == segments[-1]["text"] and start <= segments[-1]["end"]:
            segments[-1]["end"] = max(end, segments[-1]["end"])
        else:
            segments.append({"start": start, "end": end, "text": text})
    return segments


def download(url, folder, args):
    from yt_dlp import YoutubeDL
    options = {"noplaylist": True, "outtmpl": str(folder / "video.%(ext)s"),
               "format": "bv*[height<=1080]+ba/b[height<=1080]",
               "merge_output_format": "mkv", "retries": 3, "fragment_retries": 3,
               "socket_timeout": 30}
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
        if info.get("_type") in ("playlist", "multi_video") or info.get("is_live"):
            raise ValueError("Provide a single completed video, not a playlist or live stream")
        selected = None
        if args.transcript == "auto":
            for language in args.languages.split(","):
                for source, field in (("manual-caption", "subtitles"), ("auto-caption", "automatic_captions")):
                    formats = info.get(field, {}).get(language.strip(), [])
                    if any(f.get("ext") == "json3" for f in formats):
                        selected = (language.strip(), source)
                        break
                if selected:
                    break
        ydl.process_info(info)
    videos = [p for p in folder.glob("video.*") if p.suffix in (".mkv", ".mp4", ".webm", ".mov")]
    if len(videos) != 1:
        raise RuntimeError(f"Expected one merged video; found {videos}")
    metadata = {k: info.get(k) for k in ("id", "title", "channel", "upload_date", "duration", "webpage_url")}
    write_json(folder / "metadata.json", metadata)
    captions = None
    if selected:
        language, source = selected
        sub_options = {**options, "skip_download": True, "writesubtitles": source == "manual-caption",
                       "writeautomaticsub": source == "auto-caption", "subtitleslangs": [language],
                       "subtitlesformat": "json3"}
        try:
            with YoutubeDL(sub_options) as ydl:
                ydl.extract_info(url, download=True)
            files = list(folder.glob("video.*.json3"))
            if files:
                segments = parse_captions(json.loads(files[0].read_text(encoding="utf-8")))
                if segments:
                    captions = {"source": source, "language": language, "segments": segments}
        except Exception as exc:
            print(f"Caption download failed; falling back to ASR: {exc}", file=sys.stderr)
    return videos[0], metadata, captions


def transcribe(video, folder, args):
    from faster_whisper import WhisperModel
    audio = folder / "audio.wav"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", video,
         "-vn", "-ac", "1", "-ar", "16000", audio])
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    segments, info = model.transcribe(str(audio), language=args.language, vad_filter=True, beam_size=5)
    result = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    if not result:
        raise RuntimeError("No speech found; no successful transcript produced")
    return {"source": "faster-whisper", "model": args.model, "language": info.language,
            "language_probability": info.language_probability, "segments": result}


def screenshots(video, folder, interval):
    frames = folder / "frames"
    frames.mkdir()
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", video,
         "-vf", f"setpts=PTS-STARTPTS,fps=1/{interval}:start_time=0:round=up,scale=1280:-2",
         "-q:v", "2", "-start_number", "0", frames / "%06d.jpg"])
    result = [{"time": i * interval, "timestamp": timestamp(i * interval),
               "image": p.relative_to(folder).as_posix()} for i, p in enumerate(sorted(frames.glob("*.jpg")))]
    if not result:
        raise RuntimeError("No screenshots extracted")
    write_json(folder / "frames.json", result)
    return len(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Single YouTube URL or local video path")
    parser.add_argument("--output", type=Path, default=Path("runs"))
    parser.add_argument("--interval", type=float, default=15)
    parser.add_argument("--languages", default="zh-TW,zh-Hant,zh,en")
    parser.add_argument("--transcript", choices=("auto", "whisper"), default="auto")
    parser.add_argument("--language", default=None, help="ASR language code; omitted = detect")
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default="int8")
    args = parser.parse_args()
    import math
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be finite and positive")
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            parser.error(f"{tool} is required on PATH")
    folder = args.output.resolve() / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    if args.source.startswith(("https://", "http://")):
        video, metadata, transcript = download(args.source, folder, args)
    else:
        video = Path(args.source).resolve(strict=True)
        metadata = {"title": video.stem, "local_path": str(video)}
        transcript = None
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", video]))
    if not any(s.get("codec_type") == "video" for s in probe["streams"]):
        raise ValueError("Source has no video stream")
    # ASR and screenshot extraction run concurrently after the download finishes.
    with ThreadPoolExecutor(max_workers=2) as pool:
        frames_task = pool.submit(screenshots, video, folder, args.interval)
        if transcript is None:
            transcript = transcribe(video, folder, args)
        count = frames_task.result()
    write_json(folder / "transcript.json", transcript)
    (folder / "transcript.md").write_text("\n".join(
        f"[{timestamp(s['start'])}–{timestamp(s['end'])}] {s['text']}" for s in transcript["segments"]), encoding="utf-8")
    write_json(folder / "manifest.json", {"status": "ready", "metadata": metadata,
        "video": str(video), "duration": probe["format"].get("duration"),
        "transcript_source": transcript["source"], "language": transcript["language"],
        "frame_interval": args.interval, "frame_count": count,
        "frame_time_semantics": "nominal sampling targets; source-frame timing may differ",
        "summary_status": "pending-agent"})
    print(f"Evidence ready: {folder}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, ImportError, subprocess.CalledProcessError) as exc:
        print(f"Preparation failed: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr, file=sys.stderr)
        sys.exit(1)
