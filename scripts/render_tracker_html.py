# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Render a self-contained searchable HTML table from stock-tracker.md."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re
import sys
from urllib.parse import urlparse


LINK_PATTERN = re.compile(r"^\[([^]]+)]\(([^)]+)\)$")
SEPARATOR_PATTERN = re.compile(r"^:?-{3,}:?$")


def _split_markdown_row(line: str) -> list[str]:
    """Split a Markdown table row while preserving escaped pipe characters."""
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        raise ValueError("Markdown table rows must start and end with |")

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in stripped[1:-1]:
        if escaped:
            if character == "|":
                current.append("|")
            else:
                current.extend(("\\", character))
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return cells


def parse_tracker_markdown(markdown: str) -> tuple[list[str], list[list[str]]]:
    """Extract the first Markdown table from the generated tracker."""
    lines = markdown.splitlines()
    for index in range(len(lines) - 1):
        if not lines[index].lstrip().startswith("|"):
            continue
        headers = _split_markdown_row(lines[index])
        separators = _split_markdown_row(lines[index + 1])
        if len(headers) != len(separators) or not all(
            SEPARATOR_PATTERN.fullmatch(cell) for cell in separators
        ):
            continue

        rows: list[list[str]] = []
        for line in lines[index + 2 :]:
            if not line.lstrip().startswith("|"):
                break
            row = _split_markdown_row(line)
            if len(row) != len(headers):
                raise ValueError("Markdown tracker contains a row with the wrong number of cells")
            rows.append(row)
        return headers, rows
    return [], []


def _render_cell(value: str) -> str:
    match = LINK_PATTERN.fullmatch(value)
    if match is None:
        return escape(value)

    label, href = match.groups()
    parsed = urlparse(href)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return escape(label)
    target = ' target="_blank" rel="noopener noreferrer"' if parsed.scheme else ""
    return f'<a href="{escape(href, quote=True)}"{target}>{escape(label)}</a>'


def render_tracker_html(markdown: str, markdown_name: str = "stock-tracker.md") -> str:
    headers, rows = parse_tracker_markdown(markdown)
    try:
        ticker_index = headers.index("個股")
    except ValueError:
        ticker_index = -1

    header_html = "".join(f"<th scope=\"col\">{escape(header)}</th>" for header in headers)
    row_lines = []
    for row in rows:
        ticker = row[ticker_index].upper() if ticker_index >= 0 else ""
        cells = "".join(f"<td>{_render_cell(value)}</td>" for value in row)
        row_lines.append(f'<tr data-ticker="{escape(ticker, quote=True)}">{cells}</tr>')
    body_html = "\n            ".join(row_lines)
    table_hidden = "" if headers else " hidden"
    empty_hidden = " hidden" if rows else ""

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>個股觀點追蹤表</title>
  <style>
    :root {{ color-scheme: light; --ink: #172033; --muted: #667085; --line: #dfe3eb; --surface: #fff; --accent: #2457d6; --page: #f4f6fa; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--page); color: var(--ink); font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
    main {{ width: min(1480px, calc(100% - 32px)); margin: 32px auto; }}
    header {{ margin-bottom: 20px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(1.65rem, 3vw, 2.25rem); }}
    .notice {{ margin: 0; color: var(--muted); }}
    .toolbar {{ display: flex; gap: 12px; align-items: end; flex-wrap: wrap; margin: 22px 0 12px; }}
    .search {{ flex: 1 1 300px; }}
    label {{ display: block; margin-bottom: 6px; color: var(--muted); font-size: .9rem; font-weight: 650; }}
    input {{ width: 100%; min-height: 44px; border: 1px solid #b8c0cf; border-radius: 10px; padding: 0 13px; background: var(--surface); color: var(--ink); font: inherit; }}
    input:focus {{ outline: 3px solid #2457d633; border-color: var(--accent); }}
    button {{ min-height: 44px; border: 1px solid #b8c0cf; border-radius: 10px; padding: 0 16px; background: var(--surface); color: var(--ink); font: inherit; cursor: pointer; }}
    button:hover {{ border-color: var(--accent); color: var(--accent); }}
    .meta {{ display: flex; justify-content: space-between; gap: 16px; margin: 10px 2px; color: var(--muted); font-size: .9rem; }}
    a {{ color: var(--accent); text-underline-offset: 2px; }}
    .table-wrap {{ overflow: auto; max-height: calc(100vh - 245px); border: 1px solid var(--line); border-radius: 12px; background: var(--surface); box-shadow: 0 8px 24px #1720330d; }}
    table {{ width: 100%; min-width: 1180px; border-collapse: separate; border-spacing: 0; font-size: .92rem; }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; line-height: 1.5; }}
    th {{ position: sticky; top: 0; z-index: 1; background: #eef2f9; white-space: nowrap; font-size: .82rem; letter-spacing: .02em; }}
    tbody tr:hover {{ background: #f7f9fd; }}
    tbody tr:last-child td {{ border-bottom: 0; }}
    td:nth-child(1), td:nth-child(3), td:nth-child(4), td:nth-child(5), td:nth-child(8), td:nth-child(9) {{ white-space: nowrap; }}
    td:nth-child(3) {{ color: #173d9e; font-weight: 750; }}
    .empty {{ padding: 40px 18px; border: 1px dashed #b8c0cf; border-radius: 12px; background: var(--surface); color: var(--muted); text-align: center; }}
    [hidden] {{ display: none !important; }}
    @media (max-width: 640px) {{ main {{ width: min(100% - 20px, 1480px); margin-top: 20px; }} .table-wrap {{ max-height: calc(100vh - 260px); }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>個股觀點追蹤表</h1>
      <p class="notice">記錄影片講者的觀點與操作，不構成投資建議。</p>
    </header>
    <section class="toolbar" aria-label="篩選工具">
      <div class="search">
        <label for="ticker-search">搜尋個股</label>
        <input id="ticker-search" type="search" placeholder="輸入代號，例如 NVDA" autocomplete="off">
      </div>
      <button id="clear-search" type="button" hidden>清除搜尋</button>
    </section>
    <div class="meta">
      <span id="result-count">{len(rows)} 筆</span>
      <a href="{escape(markdown_name, quote=True)}">查看 Markdown</a>
    </div>
    <div class="table-wrap"{table_hidden}>
      <table>
        <thead><tr>{header_html}</tr></thead>
        <tbody>
            {body_html}
        </tbody>
      </table>
    </div>
    <p id="empty-state" class="empty"{empty_hidden}>目前沒有符合的個股紀錄。</p>
  </main>
  <script>
    const input = document.querySelector('#ticker-search');
    const clearButton = document.querySelector('#clear-search');
    const count = document.querySelector('#result-count');
    const empty = document.querySelector('#empty-state');
    const rows = [...document.querySelectorAll('tbody tr[data-ticker]')];

    function applyFilter() {{
      const query = input.value.trim().toUpperCase();
      let visible = 0;
      for (const row of rows) {{
        const matches = row.dataset.ticker.includes(query);
        row.hidden = !matches;
        if (matches) visible += 1;
      }}
      count.textContent = query ? `${{visible}} / ${{rows.length}} 筆` : `${{rows.length}} 筆`;
      clearButton.hidden = query.length === 0;
      empty.hidden = visible !== 0;
    }}

    input.addEventListener('input', applyFilter);
    clearButton.addEventListener('click', () => {{ input.value = ''; applyFilter(); input.focus(); }});
  </script>
</body>
</html>
"""


def render_tracker_html_file(markdown_path: Path, output_path: Path | None = None) -> Path:
    markdown_path = markdown_path.expanduser().resolve(strict=True)
    output_path = (output_path or markdown_path.with_suffix(".html")).expanduser().resolve()
    document = render_tracker_html(
        markdown_path.read_text(encoding="utf-8"), markdown_path.name
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path, nargs="?", default=Path("stock-tracker.md"))
    parser.add_argument("--output", type=Path, help="default: Markdown path with .html suffix")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        output = render_tracker_html_file(args.markdown, args.output)
    except (OSError, ValueError) as exc:
        print(f"HTML tracker render failed: {exc}", file=sys.stderr)
        return 1
    print(f"HTML tracker written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
