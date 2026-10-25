# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Download this repository and run its cross-platform skill installer."""

from __future__ import annotations

import argparse
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import zipfile


REPOSITORY = "evany413/us-stock-youtube-skill"
DEFAULT_REF = "main"


def archive_url(ref: str) -> str:
    return f"https://codeload.github.com/{REPOSITORY}/zip/{quote(ref, safe='')}"


def download_archive(ref: str) -> bytes:
    request = Request(archive_url(ref), headers={"User-Agent": "us-stock-youtube-skill-installer"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def extract_archive(data: bytes, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError(f"Archive contains an unsafe path: {member.filename}")
        archive.extractall(destination)


def find_source_root(destination: Path) -> Path:
    candidates = [
        path.parent.parent
        for path in destination.rglob("scripts/install_skill.py")
        if (path.parent.parent / "SKILL.md").is_file()
    ]
    if len(candidates) != 1:
        raise FileNotFoundError(f"Expected one skill repository in the archive; found {candidates}")
    return candidates[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default=DEFAULT_REF, help="Git branch, tag, or commit to install")
    return parser


def forwarded_installer_args(arguments: list[str]) -> list[str]:
    return arguments[1:] if arguments[:1] == ["--"] else arguments


def main() -> int:
    args, installer_args = build_parser().parse_known_args()
    installer_args = forwarded_installer_args(installer_args)
    try:
        archive_data = download_archive(args.ref)
        with tempfile.TemporaryDirectory(prefix="us-stock-youtube-install-") as temporary:
            destination = Path(temporary)
            extract_archive(archive_data, destination)
            source_root = find_source_root(destination)
            installer = source_root / "scripts" / "install_skill.py"
            completed = subprocess.run([sys.executable, str(installer), *installer_args], check=False)
            return completed.returncode
    except (FileNotFoundError, HTTPError, URLError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Remote installation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
