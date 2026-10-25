# Workflow Notes

## Tool choices

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) downloads a single video with audio, up to 1080p, and json3 captions. Caption failures fall back to ASR; video download failures stop preparation. Check upstream documentation for current JavaScript runtime requirements. Investigate 403/429 errors rather than retrying indefinitely.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) supports local CTranslate2 inference and CPU int8. Start with small; consider medium or large-v3 if needed. Accuracy depends on language, audio quality, and terminology. Preserve the spoken language and flag uncertain financial figures.
- [FFmpeg](https://ffmpeg.org/ffmpeg-filters.html) samples nominal targets at 0, 15, 30 seconds, and so on using the fps filter with round=up. Indexed times are sampling targets, not exact original frame presentation timestamps.

## Examples

Local video:

```powershell
uv run --script scripts/prepare.py "C:\videos\market.mp4" --language en --model medium
```

Force English speech recognition:

```powershell
uv run --script scripts/prepare.py "https://www.youtube.com/watch?v=VIDEO_ID" --transcript whisper --language en
```

CUDA inference requires compatible local CUDA/cuDNN dependencies:

```powershell
uv run --script scripts/prepare.py "https://www.youtube.com/watch?v=VIDEO_ID" --device cuda --compute-type float16
```

Resolve `scripts/prepare.py` relative to the installed skill directory when running outside this repository. Keep the user's workspace as the working directory so the default `runs/` output is created with the user's project rather than inside the skill installation.

The CLI defaults to Chinese-first caption selection; use `--languages en,zh-TW,zh` for English-first sources. Summary language is an independent agent choice.

## Agent handoff

`prepare.py` does not make investment judgments. Give the run directory to an agent capable of reading text and images and follow `SKILL.md`. After review, the agent writes `analysis.json` according to [the data contract](analysis-schema.md).

Generate the fixed single-video report:

```powershell
uv run --script scripts/render_summary.py runs/<run-id>
```

Rebuild the cumulative stock tracker from all completed runs:

```powershell
uv run --script scripts/update_stock_tracker.py --runs-dir runs --output stock-tracker.md
```

Both reporting scripts use only the Python standard library. The tracker is rebuilt from source analysis files on every run, so rerunning it does not duplicate records.

Synthetic tests validate extraction mechanics, not real YouTube access or transcription quality. Report this limitation when no real source has been tested.
