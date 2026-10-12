"""Install Core successor from ../core-successor (editable). Explicit setup only."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
CORE_SRC = REPO / "core-successor"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--core-source",
        default=str(CORE_SRC),
        help="Path to core-successor package root (default: ../core-successor)",
    )
    a = p.parse_args()
    if sys.prefix == sys.base_prefix:
        p.error("Activate a separately provisioned virtual environment first")
    src = Path(a.core_source).resolve()
    if not (src / "pyproject.toml").is_file():
        p.error(f"core source missing pyproject.toml: {src}")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(src)],
        check=True,
    )
    # jsonschema / referencing deps come from requirements.lock.txt or pyproject.
    sys.path.insert(0, str(ROOT / "adapter"))
    from bridge import verify_installed_core

    print(json.dumps(verify_installed_core()))


if __name__ == "__main__":
    main()
