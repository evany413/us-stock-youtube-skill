# US Stock YouTube Summarizer

An agent skill for summarizing US stock market YouTube videos using timestamped transcripts and screenshots.

## Install the skill

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/) and `ffmpeg` / `ffprobe` on `PATH`.

Install the latest version directly from GitHub with one command on Windows, macOS, or Linux:

```console
uv run https://raw.githubusercontent.com/evany413/us-stock-youtube-skill/main/scripts/install_from_github.py
```

To update an existing installation while keeping a timestamped backup:

```console
uv run https://raw.githubusercontent.com/evany413/us-stock-youtube-skill/main/scripts/install_from_github.py -- --force
```

Use `-- --agent claude` or `-- --agent agents` for their conventional user skill directories. Put bootstrap options before the separator—for example, `--ref <tag-or-commit> -- --force` installs a pinned release and replaces an existing installation.

For a cloned repository, the local installer works as follows.

The installer works on Windows, macOS, and Linux. It defaults to the Codex user skills directory (`$CODEX_HOME/skills` or `~/.codex/skills`).

```powershell
# Windows PowerShell
.\scripts\install.ps1
```

```bash
# macOS or Linux (POSIX sh)
sh scripts/install.sh
```

Other supported destinations:

```powershell
.\scripts\install.ps1 --agent claude
.\scripts\install.ps1 --agent agents
.\scripts\install.ps1 --skills-dir "D:\my-agent\skills"
```

```sh
sh scripts/install.sh --agent claude
sh scripts/install.sh --agent agents
sh scripts/install.sh --skills-dir "$HOME/my-agent/skills"
```

The `claude` destination is `~/.claude/skills`; `agents` is `~/.agents/skills` on every operating system. `--skills-dir` accepts any parent skills directory. Re-run the matching command with `--force` to update an existing installation. The previous version is moved to a timestamped backup instead of being deleted.

Both wrappers use the same cross-platform Python installer. They handle repository paths and destination paths containing spaces, and uv supplies Python 3.10 when it is not already installed.

## Project structure

```text
us-stock-youtube/
|-- SKILL.md                 # Agent instructions
|-- README.md                # Project overview and setup
|-- pyproject.toml           # Project metadata and Python dependencies
|-- uv.lock                  # Reproducible dependency lock
|-- .gitignore               # Excludes environments and generated media
|-- agents/
|   `-- openai.yaml           # Skill metadata and example prompt
|-- references/
|   |-- workflow.md           # Tool choices and usage examples
|   `-- analysis-schema.md    # Structured analysis data contract
|-- scripts/
|   |-- cleanup_runs.py       # Remove large media from completed runs
|   |-- cleanup_runs.py.lock
|   |-- install_skill.py      # Cross-platform skill installer
|   |-- install_from_github.py # One-command remote bootstrap
|   |-- install.ps1           # Windows one-command wrapper
|   |-- install.sh            # macOS / Linux one-command wrapper
|   |-- prepare.py            # Download, transcription, and screenshots
|   |-- prepare.py.lock       # Lockfile for evidence preparation
|   |-- render_summary.py     # Generate a fixed single-video summary
|   |-- render_summary.py.lock
|   |-- render_tracker_html.py # Convert tracker Markdown to searchable HTML
|   |-- render_tracker_html.py.lock
|   |-- update_stock_tracker.py # Rebuild Markdown and HTML trackers
|   `-- update_stock_tracker.py.lock
`-- tests/                    # Standard-library unit tests
```

## Workflow

1. Download a video with yt-dlp, or use a local video.
2. Group videos into stable `CHANNEL-NAME__CHANNEL-ID/YYYY-MM-DD_VIDEO-ID` run directories.
3. Retrieve captions; fall back to local faster-whisper transcription.
4. Extract a screenshot every 15 seconds with FFmpeg.
5. Have an agent review the transcript and screenshots using SKILL.md.
6. Save the supported findings in the fixed `analysis.json` contract.
7. Render a concise `summary.md` with short news, market, and stock sections.
8. Rebuild `stock-tracker.md` across all analyzed videos.

## Setup

For repository development, sync the locked Python 3.10+ environment:

```console
uv sync
```

Then prepare a video:

```powershell
uv run python scripts/prepare.py "https://www.youtube.com/watch?v=VIDEO_ID" --languages en,zh-TW,zh
```

The installed skill can run the preparation script directly from any working directory. Its inline dependency metadata lets uv create a cached, isolated environment without modifying the skill directory:

```bash
uv run --script /path/to/us-stock-youtube/scripts/prepare.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

See [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp) for current YouTube runtime requirements. The first ASR run downloads model weights. The preparation script requires no separate LLM API key; summarization uses the agent's model.

Run the lightweight test suite with:

```console
uv run --no-project python -m unittest discover -s tests -v
```

When preparation dependencies change, refresh the project and preparation lockfiles:

```console
uv lock
uv lock --script scripts/prepare.py
```

The two reporting scripts use only the standard library, but their script lockfiles should also be refreshed if their inline metadata changes:

```console
uv lock --script scripts/render_summary.py
uv lock --script scripts/update_stock_tracker.py
```

## Reporting commands

After the Agent reviews one run and writes `analysis.json`, generate its fixed-format report:

```console
uv run --script scripts/render_summary.py runs/<channel-name>__<channel-id>/<run-id>
```

Then rebuild the table covering every completed analysis:

```console
uv run --script scripts/update_stock_tracker.py --runs-dir runs --output stock-tracker.md
```

The tracker is rebuilt rather than appended, so the same command can be run repeatedly without duplicate rows. It keeps one video date and one compact row per stock: view, stated action, one-line key levels, outlook, source, and summary link. Rows are sorted by ticker, then YouTuber, then newest video date. The command also converts `stock-tracker.md` into a self-contained `stock-tracker.html` with ticker search; Markdown remains the single maintained tracker source. Missing values are not inferred.

## Generated output

```text
runs/<channel-name>__<channel-id>/
`-- <YYYY-MM-DD>_<youtube-video-id>/
    |-- manifest.json            # Successful preparation metadata
    |-- transcript.json          # Timestamped segments and transcript source
    |-- transcript.md            # Human-readable transcript
    |-- frames.json              # Screenshot paths and nominal timestamps
    |-- frames/
    |   |-- 000000.jpg
    |   `-- ...
    |-- analysis.json            # Structured findings written by the agent
    `-- summary.md               # Deterministically rendered report
```

The workspace also contains one cumulative file:

```text
stock-tracker.md              # One table covering stocks from every completed run
stock-tracker.html            # Searchable generated view of stock-tracker.md
```

Downloaded videos, captions, metadata, and extracted ASR audio are retained when applicable. Generated runs and virtual environments are excluded from Git.

The channel display name keeps the directory readable, while `channel-id` and `video-id` provide stable identity and avoid collisions. Unsafe path characters are replaced for Windows, macOS, and Linux. Recursive video-ID lookup reuses the same run even if the channel later changes its display name. Local inputs use `runs/_local/local_<stem>_<path-hash>/`.

## Clean completed runs

Preview the downloaded video, extracted audio, and frames that can be removed from completed analyses:

```console
uv run --script scripts/cleanup_runs.py --runs-dir runs
```

After reviewing the paths and reclaimable space, perform the deletion:

```console
uv run --script scripts/cleanup_runs.py --runs-dir runs --apply
```

Only runs with both `analysis.json` and `summary.md` are eligible. Cleanup removes `video.*`, `audio.wav`, `frames/`, and `frames.json`; manifests, transcripts, captions, analyses, summaries, and tracker data remain available. To clean one run, pass its directory as the positional argument instead of scanning `--runs-dir`.

## Agent usage

Ask an agent to read SKILL.md and summarize a video or existing run directory. The Agent reviews the evidence and writes concise schema-v2 `analysis.json`; the reporting scripts validate that data, generate `summary.md`, and rebuild `stock-tracker.md`. The fixed headings are Traditional Chinese, and analysis text follows your request.

## Development status

Initial implementation. Skill format, caption parsing, and screenshot extraction on synthetic video have been validated. Real YouTube downloads and speech recognition have not yet been tested end to end.
