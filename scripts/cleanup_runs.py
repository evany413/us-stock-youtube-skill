# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Remove large media artifacts from completed analysis runs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys


VIDEO_SUFFIXES = {".mkv", ".mp4", ".webm", ".mov"}


@dataclass(frozen=True)
class CleanupPlan:
    run_directory: Path
    targets: tuple[Path, ...]
    size_bytes: int


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _path_size(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size
    total = 0
    with os.scandir(path) as entries:
        for entry in entries:
            item = Path(entry.path)
            if entry.is_symlink() or entry.is_file(follow_symlinks=False):
                total += entry.stat(follow_symlinks=False).st_size
            elif entry.is_dir(follow_symlinks=False):
                total += _path_size(item)
    return total


def _validate_completed_run(run_directory: Path) -> Path:
    run = run_directory.expanduser().resolve(strict=True)
    if not run.is_dir():
        raise ValueError(f"Run path is not a directory: {run}")
    missing = [name for name in ("analysis.json", "summary.md") if not (run / name).is_file()]
    if missing:
        raise ValueError(f"Run is not fully analyzed ({', '.join(missing)} missing): {run}")
    return run


def discover_completed_runs(explicit: list[Path], runs_directory: Path) -> list[Path]:
    if explicit:
        candidates = explicit
    else:
        root = runs_directory.expanduser()
        if not root.exists():
            return []
        candidates = [path.parent for path in root.rglob("analysis.json") if (path.parent / "summary.md").is_file()]

    unique: dict[Path, None] = {}
    for candidate in candidates:
        unique[_validate_completed_run(candidate)] = None
    return sorted(unique)


def build_cleanup_plan(run_directory: Path) -> CleanupPlan:
    run = _validate_completed_run(run_directory)
    candidates = [run / "audio.wav", run / "frames.json", run / "frames"]
    candidates.extend(
        path
        for path in run.glob("video.*")
        if path.suffix.lower() in VIDEO_SUFFIXES
    )

    targets: list[Path] = []
    for candidate in candidates:
        if not candidate.exists() and not candidate.is_symlink():
            continue
        if candidate.parent.resolve(strict=True) != run:
            raise ValueError(f"Cleanup target is outside the run directory: {candidate}")
        if not candidate.is_symlink() and not _is_within(candidate.resolve(strict=True), run):
            raise ValueError(f"Cleanup target resolves outside the run directory: {candidate}")
        targets.append(candidate)
    targets = sorted(set(targets), key=lambda path: path.name.casefold())
    return CleanupPlan(run, tuple(targets), sum(_path_size(path) for path in targets))


def apply_cleanup(plan: CleanupPlan) -> None:
    for target in plan.targets:
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)


def format_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_directories",
        nargs="*",
        type=Path,
        help="specific completed run directories; omit to scan --runs-dir",
    )
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform deletion; without this flag the command only previews",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        runs = discover_completed_runs(args.run_directories, args.runs_dir)
        plans = [build_cleanup_plan(run) for run in runs]
    except (OSError, ValueError) as exc:
        print(f"Run cleanup failed: {exc}", file=sys.stderr)
        return 1

    plans = [plan for plan in plans if plan.targets]
    if not plans:
        print("Nothing to clean.")
        return 0

    total_size = sum(plan.size_bytes for plan in plans)
    mode = "delete" if args.apply else "would delete"
    for plan in plans:
        print(f"{mode}: {plan.run_directory} ({format_size(plan.size_bytes)})")
        for target in plan.targets:
            print(f"  - {target.name}")

    if args.apply:
        try:
            for plan in plans:
                apply_cleanup(plan)
        except OSError as exc:
            print(f"Run cleanup failed: {exc}", file=sys.stderr)
            return 1
        print(f"Cleaned {len(plans)} runs; freed {format_size(total_size)}.")
    else:
        print(
            f"Preview: {len(plans)} runs, {format_size(total_size)} reclaimable. "
            "Re-run with --apply to delete."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
