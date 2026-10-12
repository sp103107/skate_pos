#!/usr/bin/env bash
# start_all.sh — daily start for UI01 local bridge (frontend + Core API).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${SKATE_UI01_PYTHON:-}" ]]; then
  PYTHON="$SKATE_UI01_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
elif [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PYTHON="$ROOT/.venv/bin/python3"
else
  echo "ERROR: No project interpreter. See LOCAL_RUN.md (setup) or set SKATE_UI01_PYTHON." >&2
  exit 2
fi
exec "$PYTHON" "$ROOT/scripts/local_lifecycle.py" start "$@"
