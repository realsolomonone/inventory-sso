#!/usr/bin/env bash
# One command: venv + deps + IAM role verify + executive HTML.
# Usage: ./scripts/verify.sh [--open] [--profiles NAME ...] [--no-probe]

set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.9+ is required. On iebcloud: module load python/3.11" >&2
  exit 2
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "Creating .venv"
  "$PY" -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
. "$ROOT/.venv/bin/activate"

if ! python -c "import boto3, yaml" >/dev/null 2>&1; then
  echo "Installing requirements"
  python -m pip install --upgrade pip
  python -m pip install -r "$ROOT/requirements.txt"
fi

python "$ROOT/edl_resource_inventory.py" verify --open "$@"
echo
echo "Executive HTML: $ROOT/reports/executive.html"
echo "Detail HTML:    $ROOT/reports/role-verify.html"
