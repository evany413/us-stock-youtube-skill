# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Validate analysis.json and render a concise fixed-format summary.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


STANCE_LABELS = {
    "bullish": "看多",
    "bearish": "看空",
    "neutral": "中性",
    "mixed": "多空並陳",
    "not-stated": "未明確表態",
}
ACTION_LABELS = {
    "buy": "買進",
    "hold": "持有",
    "sell": "賣出",
    "watch": "觀察",
    "avoid": "避開",
    "not-stated": "未提及",
}
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


class AnalysisError(ValueError):
    """Raised when analysis.json does not match the reporting contract."""


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnalysisError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise AnalysisError(f"{path} must be an array")
    return value


def _require_text(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise AnalysisError(f"{path} must be {qualifier}")
    return value.strip()


def validate_analysis(data: Any) -> dict[str, Any]:
    """Validate the concise v2 fields needed by both report scripts."""
    root = _require_mapping(data, "analysis")
    if root.get("schema_version") != 2:
        raise AnalysisError("schema_version must be 2")

    video = _require_mapping(root.get("video"), "video")
    for field in ("date", "youtuber", "title"):
        _require_text(video.get(field), f"video.{field}")
    if video["date"] != "unknown" and DATE_PATTERN.fullmatch(video["date"]) is None:
        raise AnalysisError("video.date must use YYYY-MM-DD or unknown")
    if "url" in video:
        _require_text(video["url"], "video.url", allow_empty=True)

    events = _require_list(root.get("current_events"), "current_events")
    for index, event_value in enumerate(events):
        event = _require_mapping(event_value, f"current_events[{index}]")
        _require_text(event.get("topic"), f"current_events[{index}].topic")
        _require_text(event.get("summary"), f"current_events[{index}].summary")

    market = _require_mapping(root.get("market"), "market")
    if market.get("stance") not in STANCE_LABELS:
        raise AnalysisError(f"market.stance must be one of: {', '.join(STANCE_LABELS)}")
    _require_text(market.get("summary"), "market.summary")
    _require_text(market.get("outlook"), "market.outlook")

    stocks = _require_list(root.get("stocks"), "stocks")
    seen_tickers: set[str] = set()
    for index, stock_value in enumerate(stocks):
        path = f"stocks[{index}]"
        stock = _require_mapping(stock_value, path)
        ticker = _require_text(stock.get("ticker"), f"{path}.ticker").upper()
        if ticker in seen_tickers:
            raise AnalysisError(f"{path}.ticker duplicates {ticker}; consolidate each ticker")
        seen_tickers.add(ticker)
        if "company" in stock:
            _require_text(stock["company"], f"{path}.company", allow_empty=True)
        if stock.get("stance") not in STANCE_LABELS:
            raise AnalysisError(f"{path}.stance must be one of: {', '.join(STANCE_LABELS)}")
        if stock.get("action") not in ACTION_LABELS:
            raise AnalysisError(f"{path}.action must be one of: {', '.join(ACTION_LABELS)}")
        _require_text(stock.get("key_levels"), f"{path}.key_levels", allow_empty=True)
        _require_text(stock.get("outlook"), f"{path}.outlook")

    if "note" in root:
        _require_text(root["note"], "note", allow_empty=True)
    return root


def load_analysis(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnalysisError(f"Invalid JSON in {path}: {exc}") from exc
    return validate_analysis(data)


def escape_cell(value: Any) -> str:
    text = str(value).strip() if value not in (None, "") else "—"
    return re.sub(r"\s+", " ", text).replace("|", "\\|")


def render_summary_document(data: dict[str, Any]) -> str:
    data = validate_analysis(data)
    video = data["video"]
    title = re.sub(r"\s+", " ", video["title"]).strip()
    video_url = video.get("url", "")
    video_reference = f"[影片連結]({video_url})" if video_url else "—"

    lines = [
        f"# {title}",
        "",
        "> 以下為影片講者觀點摘要，不構成投資建議。",
        "",
        "## 基本資料",
        "",
        "| 影片日期 | YouTuber | 影片 |",
        "|---|---|---|",
        "| "
        + " | ".join(
            escape_cell(value)
            for value in (video["date"], video["youtuber"], video_reference)
        )
        + " |",
        "",
        "## 時事",
        "",
    ]

    if data["current_events"]:
        lines.extend(("| 主題 | 重點 |", "|---|---|"))
        for event in data["current_events"]:
            lines.append(
                "| "
                + " | ".join(
                    (escape_cell(event["topic"]), escape_cell(event["summary"]))
                )
                + " |"
            )
    else:
        lines.append("_影片未提及重要時事。_")

    market = data["market"]
    lines.extend(
        (
            "",
            "## 整體股市",
            "",
            f"- **方向：** {STANCE_LABELS[market['stance']]}",
            f"- **摘要：** {market['summary']}",
            f"- **展望：** {market['outlook']}",
            "",
            "## 個股分析",
            "",
        )
    )

    if data["stocks"]:
        lines.extend(
            (
                "| 個股 | 觀點 | 影片操作 | 關鍵點位 | 未來展望 |",
                "|---|---|---|---|---|",
            )
        )
        for stock in data["stocks"]:
            lines.append(
                "| "
                + " | ".join(
                    escape_cell(value)
                    for value in (
                        stock["ticker"].upper(),
                        STANCE_LABELS[stock["stance"]],
                        ACTION_LABELS[stock["action"]],
                        stock["key_levels"],
                        stock["outlook"],
                    )
                )
                + " |"
            )
    else:
        lines.append("_影片未提及可確認的個股。_")

    if data.get("note"):
        lines.extend(("", f"> 資料限制：{data['note']}"))
    lines.append("")
    return "\n".join(lines)


def render_summary_file(
    run_directory: Path,
    input_name: Path = Path("analysis.json"),
    output_name: Path = Path("summary.md"),
) -> Path:
    run_directory = run_directory.resolve(strict=True)
    input_path = input_name if input_name.is_absolute() else run_directory / input_name
    output_path = output_name if output_name.is_absolute() else run_directory / output_name
    data = load_analysis(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_summary_document(data), encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path, help="run directory containing analysis.json")
    parser.add_argument("--input", type=Path, default=Path("analysis.json"))
    parser.add_argument("--output", type=Path, default=Path("summary.md"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        output = render_summary_file(args.run_directory, args.input, args.output)
    except (AnalysisError, FileNotFoundError, OSError) as exc:
        print(f"Summary generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Summary written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
