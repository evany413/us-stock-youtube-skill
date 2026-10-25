#!/bin/sh
set -eu

if ! command -v uv >/dev/null 2>&1; then
    echo "Installation failed: uv is required but was not found on PATH." >&2
    echo "Install uv from https://docs.astral.sh/uv/ and try again." >&2
    exit 127
fi

script_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
exec uv run --no-project --python 3.10 python "$script_dir/install_skill.py" "$@"
