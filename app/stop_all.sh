#!/usr/bin/env bash
# stop_all.sh — stop only this package's owned UI01 bridge process.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${SKATE_UI01_PYTHON:-}" ]]; then
  PYTHON="$SKATE_UI01_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
elif [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PYTHON="$ROOT/.venv/bin/python3"
else
  # Stop can clear stale state with system python if helper is present.
  PYTHON="$(command -v python3 || true)"
  if [[ -z "$PYTHON" ]]; then
    echo "ERROR: No Python available to run stop helper." >&2
    exit 2
  fi
fi
exec "$PYTHON" "$ROOT/scripts/local_lifecycle.py" stop "$@"
