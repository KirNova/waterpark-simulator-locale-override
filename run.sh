#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python 3.8+ not found. Install Python and try again."
  exit 1
fi

"$PYTHON" "$SCRIPT_DIR/patch_staff_only.py" "$@"
