"""
local_lifecycle.py — shared start/stop/status helper for UI01 local launchers (rc.6).

Controls the single loopback bridge (frontend + Core API). Daily start does not
install packages, download browsers, or alter system configuration.
Runtime state lives under <package>/.local-runtime/ (excluded from candidate ZIP).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".local-runtime"
DEMO = RUNTIME / "demo"
REAL = RUNTIME / "real"
LOGS = RUNTIME / "logs"
STATE_DIR = RUNTIME / "state"
STATE_FILE = STATE_DIR / "bridge.json"
DEFAULT_PORT = 8765
READY_TIMEOUT_S = 20.0
STOP_GRACE_S = 8.0
STOP_FORCE_S = 4.0


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _die(code: int, msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _info(msg: str) -> None:
    print(msg, flush=True)


def ensure_runtime_dirs() -> None:
    for d in (RUNTIME, DEMO, REAL, LOGS, STATE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def workspace_for_mode(mode: str) -> Path:
    if mode == "real":
        return REAL.resolve()
    return DEMO.resolve()


def _venv_python_path(p: Path) -> Path:
    """Return an absolute path to the venv shim without following it to system Python.

    On Unix, `.venv/bin/python` is often a symlink to `/usr/bin/python3`. Following that
    symlink would drop the venv's site-packages and break Core imports.
    """
    return Path(os.path.abspath(str(p)))


def resolve_python() -> Path:
    env = os.environ.get("SKATE_UI01_PYTHON", "").strip()
    if env:
        p = Path(env)
        if p.is_file() or p.is_symlink():
            return _venv_python_path(p)
        _die(2, f"SKATE_UI01_PYTHON is not a file: {env}")
    for cand in (
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
        ROOT / ".venv" / "bin" / "python3",
    ):
        if cand.is_file() or cand.is_symlink():
            return _venv_python_path(cand)
    _die(
        2,
        "No project interpreter found. Create <package>/.venv, install "
        "requirements.lock.txt + Core via scripts/install_core.py, or set SKATE_UI01_PYTHON. "
        "See LOCAL_RUN.md. Daily start will not install packages.",
    )


def load_state() -> dict | None:
    if not STATE_FILE.is_file():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_state(data: dict) -> None:
    ensure_runtime_dirs()
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def clear_state() -> None:
    if STATE_FILE.is_file():
        STATE_FILE.unlink()


def fingerprint(python: Path, bridge: Path, workspace: Path, port: int) -> str:
    raw = f"{python}|{bridge}|{workspace}|{port}|{ROOT}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # OpenProcess would be ideal; tasklist is available without extra deps.
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return str(pid) in (r.stdout or "")
        except (OSError, subprocess.TimeoutExpired):
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def owned_running(state: dict | None, python: Path, bridge: Path, workspace: Path, port: int) -> bool:
    if not state:
        return False
    pid = int(state.get("pid") or 0)
    if not pid_alive(pid):
        return False
    if state.get("fingerprint") != fingerprint(python, bridge, workspace, port):
        return False
    if int(state.get("port") or 0) != port:
        return False
    # Require the recorded port still answering our status endpoint when possible.
    if port_in_use(port) and fetch_status(port) is not None:
        return True
    # Process alive with matching fingerprint but not yet/no longer serving — treat as owned if cmdline matches loosely.
    return True


def fetch_status(port: int) -> dict | None:
    url = f"http://127.0.0.1:{port}/api/status"
    try:
        req = urllib.request.Request(url, headers={"Host": f"127.0.0.1:{port}"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None


def wait_ready(port: int, timeout: float = READY_TIMEOUT_S) -> dict | None:
    deadline = time.time() + timeout
    ok_modes = {"ACTUAL_CORE_SYNTHETIC_ONLY", "ACTUAL_CORE_REAL_WORKSPACE"}
    while time.time() < deadline:
        st = fetch_status(port)
        if st and st.get("mode") in ok_modes:
            return st
        time.sleep(0.2)
    return None


def terminate_owned(pid: int) -> None:
    if not pid_alive(pid):
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True, check=False)
        time.sleep(STOP_GRACE_S)
        if pid_alive(pid):
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
            time.sleep(STOP_FORCE_S)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + STOP_GRACE_S
    while time.time() < deadline and pid_alive(pid):
        time.sleep(0.2)
    if pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        time.sleep(STOP_FORCE_S)


def cmd_setup() -> int:
    _info("Setup is intentional and separate from daily start.")
    _info(f"Package root: {ROOT}")
    _info("1) python3 -m venv .venv")
    _info("2) .venv/bin/python -m pip install -r requirements.lock.txt")
    _info("3) .venv/bin/python scripts/install_core.py")
    _info("   (editable install of ../core-successor 0.4.0-a01.1)")
    _info("Or set SKATE_UI01_PYTHON to an interpreter with Core successor installed.")
    _info("Daily start will not run pip/npm or download browsers.")
    return 0


def cmd_status() -> int:
    ensure_runtime_dirs()
    python = None
    try:
        python = resolve_python()
    except SystemExit:
        python = None
    bridge = ROOT / "adapter" / "bridge.py"
    workspace = DEMO
    port = DEFAULT_PORT
    state = load_state()
    _info(f"root={ROOT}")
    _info(f"runtime={RUNTIME}")
    _info(f"state_file={STATE_FILE} exists={STATE_FILE.is_file()}")
    if state:
        _info(f"recorded_pid={state.get('pid')} port={state.get('port')} started_at={state.get('started_at')}")
    if python:
        running = owned_running(state, python, bridge, workspace, int((state or {}).get("port") or port))
        _info(f"owned_running={running}")
        if running:
            st = fetch_status(int(state["port"]))
            _info(f"status={json.dumps(st) if st else 'unreachable'}")
    else:
        _info("interpreter=NOT_CONFIGURED")
    return 0


def cmd_start(open_browser: bool) -> int:
    ensure_runtime_dirs()
    python = resolve_python()
    bridge = (ROOT / "adapter" / "bridge.py").resolve()
    if not bridge.is_file():
        _die(2, f"bridge missing: {bridge}")
    mode = os.environ.get("SKATE_UI01_MODE", "demo").strip().lower() or "demo"
    if mode not in ("demo", "real"):
        _die(2, f"invalid SKATE_UI01_MODE: {mode} (use demo|real)")
    workspace = workspace_for_mode(mode)
    port = int(os.environ.get("SKATE_UI01_PORT", str(DEFAULT_PORT)))
    if not (1 <= port <= 65535):
        _die(2, f"invalid SKATE_UI01_PORT: {port}")

    state = load_state()
    if owned_running(state, python, bridge, workspace, port):
        origin = f"http://127.0.0.1:{port}"
        _info(f"already running: {origin}")
        _info(f"pid={state['pid']} workspace={workspace}")
        return 0

    # Stale record cleanup (never kill unrelated).
    if state and not owned_running(state, python, bridge, workspace, port):
        _info("clearing stale process record (pid dead or ownership mismatch)")
        clear_state()

    if port_in_use(port):
        # Someone else holds the port.
        st = fetch_status(port)
        if st:
            _die(3, f"port {port} is already serving a UI01-like status endpoint but is not owned by this package state; refusing to kill it")
        _die(3, f"port {port} is occupied by an unrelated process; set SKATE_UI01_PORT to a free port or stop the other listener")

    log_path = LOGS / f"bridge-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    fp = fingerprint(python, bridge, workspace, port)
    cmd = [
        str(python),
        str(bridge),
        "--workspace",
        str(workspace),
        "--mode",
        mode,
        "--port",
        str(port),
    ]
    if mode == "demo":
        cmd.append("--seed-synthetic")
    _info(f"starting: {' '.join(cmd)}")
    try:
        logf = open(log_path, "a", encoding="utf-8")
        logf.write(f"=== START {_now()} ===\n")
        logf.flush()
        if os.name == "nt":
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=logf,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]
            )
        else:
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=logf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError as e:
        _die(3, f"failed to spawn bridge: {e}")

    # Record provisional ownership immediately so failure cleanup can find the child.
    save_state(
        {
            "pid": proc.pid,
            "port": port,
            "python": str(python),
            "bridge": str(bridge),
            "workspace": str(workspace),
            "fingerprint": fp,
            "started_at": _now(),
            "log": str(log_path),
            "root": str(ROOT),
        }
    )

    ready = wait_ready(port)
    if ready is None:
        _info("startup failed; terminating owned child")
        terminate_owned(proc.pid)
        # Reap
        try:
            proc.wait(timeout=2)
        except Exception:
            pass
        clear_state()
        _die(3, f"bridge did not become ready on 127.0.0.1:{port} within {READY_TIMEOUT_S}s; see {log_path}")

    origin = f"http://127.0.0.1:{port}"
    _info(f"ready: {origin}")
    _info(f"workspace: {workspace}")
    _info(f"log: {log_path}")
    _info(f"mode: {ready.get('mode')}")

    if open_browser or os.environ.get("SKATE_UI01_OPEN_BROWSER", "").strip() in ("1", "true", "yes"):
        try:
            if os.name == "nt":
                os.startfile(origin)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", origin])
            else:
                subprocess.Popen(["xdg-open", origin])
        except OSError as e:
            _info(f"browser open skipped: {e}")

    return 0


def cmd_stop() -> int:
    ensure_runtime_dirs()
    state = load_state()
    if not state:
        _info("already stopped")
        return 0

    python_s = state.get("python")
    bridge_s = state.get("bridge")
    workspace_s = state.get("workspace")
    port = int(state.get("port") or DEFAULT_PORT)
    pid = int(state.get("pid") or 0)
    fp = state.get("fingerprint")

    # Ownership: refuse to kill if fingerprint cannot be verified against recorded fields.
    if not (python_s and bridge_s and workspace_s and fp):
        _info("state incomplete; clearing record without killing any process")
        clear_state()
        return 0

    python = Path(python_s)
    bridge = Path(bridge_s)
    workspace = Path(workspace_s)
    expected = fingerprint(python, bridge, workspace, port)
    if fp != expected:
        _info("ownership mismatch versus current package paths; clearing stale record; not killing any process")
        clear_state()
        return 0

    if not pid_alive(pid):
        _info("already stopped (stale pid)")
        clear_state()
        return 0

    _info(f"stopping owned pid={pid} port={port}")
    terminate_owned(pid)
    if pid_alive(pid):
        _die(3, f"owned process pid={pid} did not exit; not killing unrelated processes")
    clear_state()
    # Port may take a moment to release.
    deadline = time.time() + 5
    while time.time() < deadline and port_in_use(port):
        time.sleep(0.2)
    if port_in_use(port):
        _info(f"warning: port {port} still in use after owned process exit (may be unrelated)")
    else:
        _info(f"stopped; port {port} released")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "start", "stop", "status"))
    parser.add_argument("--open", action="store_true", help="open default browser after successful start")
    args = parser.parse_args(argv)
    if args.command == "setup":
        return cmd_setup()
    if args.command == "status":
        return cmd_status()
    if args.command == "start":
        return cmd_start(open_browser=args.open)
    if args.command == "stop":
        return cmd_stop()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
