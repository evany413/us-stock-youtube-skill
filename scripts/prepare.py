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
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unicodedata
from urllib.parse import parse_qs, urlparse


VIDEO_SUFFIXES = {".mkv", ".mp4", ".webm", ".mov"}
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def run(args):
    return subprocess.run([str(x) for x in args], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def timestamp(seconds):
    value = int(seconds)
    return f"{value // 3600:02}:{value // 60 % 60:02}:{value % 60:02}"


def normalize_upload_date(value):
    try:
        return datetime.strptime(str(value), "%Y%m%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return "unknown-date"


def safe_component(value, fallback):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip(".-_")
    return cleaned or fallback


def safe_display_component(value, fallback):
    text = unicodedata.normalize("NFKC", str(value))
    text = "".join("-" if ord(character) < 32 or character in '<>:"/\\|?*' else character for character in text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text or text in {".", ".."}:
        text = fallback
    if text.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        text = f"_{text}"
    return text[:64].rstrip(" .") or fallback


def youtube_run_name(metadata):
    video_id = safe_component(metadata.get("id", ""), "")
    if not video_id:
        raise ValueError("YouTube metadata did not include a video ID")
    date = normalize_upload_date(metadata.get("upload_date") or metadata.get("release_date"))
    return f"{date}_{video_id}"


def channel_run_name(metadata):
    display_name = metadata.get("channel") or metadata.get("uploader") or "unknown-channel"
    channel_name = safe_display_component(display_name, "unknown-channel")
    channel_id = metadata.get("channel_id") or metadata.get("uploader_id")
    if channel_id:
        stable_id = safe_component(channel_id, "unknown-channel-id")
    else:
        stable_id = hashlib.sha256(str(display_name).encode("utf-8")).hexdigest()[:10]
    return f"{channel_name}__{stable_id}"


def extract_youtube_id(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    candidate = None
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/", 1)[0]
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        if parsed.path.rstrip("/") == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2 and parts[0] in {"embed", "live", "shorts"}:
                candidate = parts[1]
    if candidate and re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        return candidate
    return None


def folder_video_id(folder):
    metadata = read_json(folder / "metadata.json")
    if isinstance(metadata, dict) and metadata.get("id"):
        return str(metadata["id"])
    manifest = read_json(folder / "manifest.json")
    if isinstance(manifest, dict) and isinstance(manifest.get("metadata"), dict):
        value = manifest["metadata"].get("id")
        if value:
            return str(value)
    return None


def load_frame_index(folder, interval=None):
    frames = read_json(folder / "frames.json")
    if not isinstance(frames, list) or not frames:
        return None
    try:
        valid = all(
            (interval is None or abs(float(item.get("time", -1)) - index * interval) < 1e-6)
            and (folder / item.get("image", "")).is_file()
            for index, item in enumerate(frames)
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return frames if valid else None


def evidence_ready(folder):
    manifest = read_json(folder / "manifest.json")
    return (
        isinstance(manifest, dict)
        and manifest.get("status") == "ready"
        and (folder / "transcript.json").is_file()
        and (folder / "transcript.md").is_file()
        and load_frame_index(folder) is not None
    )


def find_existing_youtube_run(output_root, video_id):
    if not video_id or not output_root.is_dir():
        return None
    matches = []
    suffix = f"_{video_id}"
    for metadata_path in output_root.rglob("metadata.json"):
        folder = metadata_path.parent
        if folder_video_id(folder) == video_id:
            matches.append(folder)
    for manifest_path in output_root.rglob("manifest.json"):
        folder = manifest_path.parent
        if folder_video_id(folder) == video_id:
            matches.append(folder)
    for folder in output_root.rglob(f"*{suffix}"):
        if folder.is_dir():
            matches.append(folder)
    if not matches:
        return None
    return sorted(set(matches), key=lambda folder: (not evidence_ready(folder), str(folder)))[0]


def find_existing_channel_directory(output_root, metadata):
    channel_id = metadata.get("channel_id") or metadata.get("uploader_id")
    if not channel_id or not output_root.is_dir():
        return None
    suffix = f"__{safe_component(channel_id, 'unknown-channel-id')}"
    return next(
        (folder for folder in sorted(output_root.iterdir()) if folder.is_dir() and folder.name.endswith(suffix)),
        None,
    )


def local_run_name(video):
    normalized = str(video)
    if os.name == "nt":
        normalized = normalized.casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
    stem = safe_component(video.stem, "video")[:48]
    return f"local_{stem}_{digest}"


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


def select_caption(info, languages):
    for language in languages.split(","):
        language = language.strip()
        for source, field in (("manual-caption", "subtitles"), ("auto-caption", "automatic_captions")):
            formats = info.get(field, {}).get(language, [])
            if any(item.get("ext") == "json3" for item in formats):
                return language, source
    return None


def youtube_info(url):
    from yt_dlp import YoutubeDL

    options = {"noplaylist": True, "format": "bv*[height<=1080]+ba/b[height<=1080]",
               "socket_timeout": 30}
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("_type") in ("playlist", "multi_video") or info.get("is_live"):
        raise ValueError("Provide a single completed video, not a playlist or live stream")
    if not info.get("id"):
        raise ValueError("YouTube metadata did not include a video ID")
    return info


def downloaded_video(folder):
    videos = [path for path in folder.glob("video.*") if path.suffix.lower() in VIDEO_SUFFIXES]
    if len(videos) > 1:
        raise RuntimeError(f"Expected one merged video; found {videos}")
    return videos[0] if videos else None


def load_transcript(folder):
    transcript = read_json(folder / "transcript.json")
    if isinstance(transcript, dict) and transcript.get("segments"):
        return transcript
    return None


def download(url, folder, args, info):
    from yt_dlp import YoutubeDL

    options = {"noplaylist": True, "outtmpl": str(folder / "video.%(ext)s"),
               "format": "bv*[height<=1080]+ba/b[height<=1080]",
               "merge_output_format": "mkv", "retries": 3, "fragment_retries": 3,
               "socket_timeout": 30}
    video = downloaded_video(folder)
    if video is None:
        with YoutubeDL(options) as ydl:
            ydl.process_info(info)
        video = downloaded_video(folder)
    if video is None:
        raise RuntimeError("Expected one merged video; found none")
    metadata = {key: info.get(key) for key in (
        "id", "title", "channel", "channel_id", "uploader", "uploader_id", "upload_date", "duration", "webpage_url"
    )}
    write_json(folder / "metadata.json", metadata)
    transcript = load_transcript(folder)
    selected = select_caption(info, args.languages) if args.transcript == "auto" and transcript is None else None
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
                    transcript = {"source": source, "language": language, "segments": segments}
        except Exception as exc:
            print(f"Caption download failed; falling back to ASR: {exc}", file=sys.stderr)
    return video, metadata, transcript


def transcribe(video, folder, args):
    from faster_whisper import WhisperModel
    audio = folder / "audio.wav"
    if not audio.is_file() or audio.stat().st_size <= 44:
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
    existing = load_frame_index(folder, interval)
    if existing is not None:
        return len(existing)
    frames = folder / "frames"
    frames.mkdir(exist_ok=True)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", video,
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
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if args.source.startswith(("https://", "http://")):
        hinted_id = extract_youtube_id(args.source)
        folder = find_existing_youtube_run(output_root, hinted_id)
        if folder is not None and evidence_ready(folder):
            print(f"Evidence already ready: {folder}")
            return
        info = youtube_info(args.source)
        video_id = str(info["id"])
        folder = find_existing_youtube_run(output_root, video_id)
        if folder is None:
            channel_folder = find_existing_channel_directory(output_root, info) or output_root / channel_run_name(info)
            folder = channel_folder / youtube_run_name(info)
        folder.mkdir(parents=True, exist_ok=True)
        if evidence_ready(folder):
            print(f"Evidence already ready: {folder}")
            return
        video, metadata, transcript = download(args.source, folder, args, info)
    else:
        video = Path(args.source).resolve(strict=True)
        folder = output_root / "_local" / local_run_name(video)
        folder.mkdir(parents=True, exist_ok=True)
        if evidence_ready(folder):
            print(f"Evidence already ready: {folder}")
            return
        metadata = {"title": video.stem, "local_path": str(video)}
        write_json(folder / "metadata.json", metadata)
        transcript = load_transcript(folder)
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
