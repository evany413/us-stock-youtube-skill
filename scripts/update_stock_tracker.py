# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Rebuild Markdown and searchable HTML stock trackers from completed analyses."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import quote

try:
    from .render_summary import (
        ACTION_LABELS,
        STANCE_LABELS,
        AnalysisError,
        escape_cell,
        load_analysis,
    )
    from .render_tracker_html import render_tracker_html_file
except ImportError:  # Direct execution places this script's directory on sys.path.
    from render_summary import (  # type: ignore[no-redef]
        ACTION_LABELS,
        STANCE_LABELS,
        AnalysisError,
        escape_cell,
        load_analysis,
    )
    from render_tracker_html import render_tracker_html_file  # type: ignore[no-redef]


def discover_run_directories(explicit: list[Path], runs_directory: Path) -> list[Path]:
    candidates = explicit or [path.parent for path in runs_directory.rglob("analysis.json")]
    unique: dict[Path, None] = {}
    for candidate in candidates:
        unique[candidate.expanduser().resolve(strict=True)] = None
    return sorted(unique)


def _summary_link(run_directory: Path, output_path: Path) -> str:
    target = run_directory / "summary.md"
    if not target.exists():
        target = run_directory / "analysis.json"
    try:
        relative = os.path.relpath(target, output_path.parent)
    except ValueError:
        relative = str(target)
    href = quote(relative.replace("\\", "/"), safe="/:#?=&")
    return f"[摘要]({href})"


def collect_rows(run_directories: list[Path], output_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_directory in run_directories:
        data = load_analysis(run_directory / "analysis.json")
        video = data["video"]
        video_url = video.get("url", "")
        video_link = f"[影片]({video_url})" if video_url else "—"
        for stock in data["stocks"]:
            rows.append(
                {
                    "date": video["date"],
                    "youtuber": video["youtuber"],
                    "ticker": stock["ticker"].upper(),
                    "stance": STANCE_LABELS[stock["stance"]],
                    "action": ACTION_LABELS[stock["action"]],
                    "key_levels": stock["key_levels"],
                    "outlook": stock["outlook"],
                    "video": video_link,
                    "summary": _summary_link(run_directory, output_path),
                }
            )
    # Stable sorts make the final priority ticker -> YouTuber -> newest date.
    rows.sort(
        key=lambda row: (row["date"] != "unknown", row["date"]),
        reverse=True,
    )
    rows.sort(key=lambda row: (row["ticker"], row["youtuber"].casefold()))
    return rows


def render_tracker(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 個股觀點追蹤表",
        "",
        "> 記錄影片講者的觀點與操作，不構成投資建議。",
        "",
    ]
    if not rows:
        lines.extend(("_目前沒有個股紀錄。_", ""))
        return "\n".join(lines)

    lines.extend(
        (
            "| 日期 | YouTuber | 個股 | 觀點 | 影片操作 | 關鍵點位 | 未來展望 | 來源 | 單次摘要 |",
            "|---|---|---|---|---|---|---|---|---|",
        )
    )
    fields = (
        "date",
        "youtuber",
        "ticker",
        "stance",
        "action",
        "key_levels",
        "outlook",
        "video",
        "summary",
    )
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(row[field]) for field in fields) + " |")
    lines.append("")
    return "\n".join(lines)


def update_tracker(run_directories: list[Path], output_path: Path) -> tuple[Path, Path]:
    output_path = output_path.expanduser().resolve()
    rows = collect_rows(run_directories, output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_tracker(rows), encoding="utf-8")
    html_output = render_tracker_html_file(output_path)
    return output_path, html_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_directories",
        nargs="*",
        type=Path,
        help="specific run directories; omit to scan --runs-dir",
    )
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument("--output", type=Path, default=Path("stock-tracker.md"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        run_directories = discover_run_directories(args.run_directories, args.runs_dir)
        output, html_output = update_tracker(run_directories, args.output)
    except (AnalysisError, FileNotFoundError, OSError) as exc:
        print(f"Stock tracker update failed: {exc}", file=sys.stderr)
        return 1
    print(f"Stock tracker written: {output} ({len(run_directories)} runs)")
    print(f"Searchable HTML written: {html_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
