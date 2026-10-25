"""Install this repository's skill payload into an agent skills directory."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
import tempfile


SKILL_NAME = "us-stock-youtube"
PAYLOAD = (
    Path("SKILL.md"),
    Path("agents"),
    Path("references"),
    Path("scripts") / "prepare.py",
    Path("scripts") / "prepare.py.lock",
    Path("scripts") / "render_summary.py",
    Path("scripts") / "render_summary.py.lock",
    Path("scripts") / "update_stock_tracker.py",
    Path("scripts") / "update_stock_tracker.py.lock",
)


def default_skills_dir(agent: str) -> Path:
    """Return the conventional user-level skills directory for an agent."""
    if agent == "codex":
        codex_home = os.environ.get("CODEX_HOME")
        if codex_home:
            return Path(codex_home).expanduser() / "skills"
        return Path.home() / ".codex" / "skills"
    home = Path.home()
    if agent == "claude":
        return home / ".claude" / "skills"
    return home / ".agents" / "skills"


def copy_payload(source_root: Path, destination: Path) -> None:
    """Copy the runtime skill files into an empty staging directory."""
    for relative_path in PAYLOAD:
        source = source_root / relative_path
        target = destination / relative_path
        if not source.exists():
            raise FileNotFoundError(f"Required skill file is missing: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
        else:
            shutil.copy2(source, target)


def install(source_root: Path, skills_dir: Path, force: bool, dry_run: bool) -> tuple[Path, Path | None]:
    """Install atomically and return the target and optional backup paths."""
    source_root = source_root.resolve(strict=True)
    skills_dir = skills_dir.expanduser().resolve()
    target = skills_dir / SKILL_NAME

    for relative_path in PAYLOAD:
        if not (source_root / relative_path).exists():
            raise FileNotFoundError(f"Required skill file is missing: {source_root / relative_path}")

    if target.exists() and not force:
        raise FileExistsError(
            f"Skill already exists at {target}. Re-run with --force to replace it and keep a backup."
        )

    if dry_run:
        return target, None

    skills_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{SKILL_NAME}-install-", dir=skills_dir))
    backup = None
    try:
        copy_payload(source_root, staging)
        if target.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = skills_dir / f".{SKILL_NAME}.backup-{stamp}"
            suffix = 1
            while backup.exists():
                backup = skills_dir / f".{SKILL_NAME}.backup-{stamp}-{suffix}"
                suffix += 1
            target.rename(backup)
        staging.rename(target)
    except Exception:
        if backup is not None and backup.exists() and not target.exists():
            backup.rename(target)
        if staging.exists():
            shutil.rmtree(staging)
        raise

    return target, backup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        choices=("codex", "claude", "agents"),
        default="codex",
        help="select the default skills directory (default: codex)",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        help="override the parent skills directory; the skill name is appended automatically",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing installation after moving it to a timestamped backup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show the resolved destination without changing files",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_root = Path(__file__).resolve().parents[1]
    skills_dir = args.skills_dir or default_skills_dir(args.agent)

    try:
        target, backup = install(source_root, skills_dir, args.force, args.dry_run)
    except (FileExistsError, FileNotFoundError, OSError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Would install {SKILL_NAME} to: {target}")
    else:
        print(f"Installed {SKILL_NAME} to: {target}")
        if backup is not None:
            print(f"Previous installation backed up to: {backup}")
        print("Restart your agent session if the skill is not discovered immediately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
