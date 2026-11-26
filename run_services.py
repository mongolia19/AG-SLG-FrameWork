#!/usr/bin/env python3
"""Service manager for AG-SLG-FrameWork daemon processes."""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
PID_FILE = ROOT_DIR / ".services.pid"


def resolve_python() -> str:
    candidates = (
        [ROOT_DIR / ".venv" / "Scripts" / "python.exe", ROOT_DIR / ".venv" / "Scripts" / "python"]
        if os.name == "nt"
        else [ROOT_DIR / ".venv" / "bin" / "python3", ROOT_DIR / ".venv" / "bin" / "python"]
    )
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return sys.executable


def resolve_vite_cmd() -> List[str]:
    vite_bin = WEB_DIR / "node_modules" / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
    if vite_bin.exists():
        return [str(vite_bin)]
    npx = shutil.which("npx") or "npx"
    return [npx, "vite"]


def _detached_popen_kwargs() -> Dict[str, Any]:
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0
        )
        return {"creationflags": flags} if flags else {}
    return {"start_new_session": True}


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, SystemError):
        return False


def _terminate_pid(pid: int) -> bool:
    if os.name == "nt":
        try:
            res = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass
    if not is_running(pid):
        return False
    os.kill(pid, signal.SIGTERM)
    return True


def _parse_windows_netstat_pids(output: str, port: int) -> List[int]:
    pids: List[int] = []
    port_suffix = f":{port}"
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_addr, state, pid_str = parts[1], parts[3].upper(), parts[-1]
        if state == "LISTENING" and local_addr.endswith(port_suffix) and pid_str.isdigit():
            pid = int(pid_str)
            if pid > 0 and pid not in pids:
                pids.append(pid)
    return pids


def _kill_port(port: int) -> None:
    try:
        if os.name == "nt":
            out = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True, errors="replace")
            for pid in _parse_windows_netstat_pids(out, port):
                try:
                    _terminate_pid(pid)
                except Exception:
                    pass
        else:
            out = subprocess.check_output(["lsof", "-t", f"-i:{port}"], text=True).strip()
            for pid_str in out.splitlines():
                if pid_str.isdigit():
                    os.kill(int(pid_str), signal.SIGTERM)
    except Exception:
        pass


def start():
    # Clean any residual processes on ports 8001 and 5173
    for port in (8001, 5173):
        _kill_port(port)

    time.sleep(0.5)
    popen_extra = _detached_popen_kwargs()

    # 1. Start Backend (port 8001)
    backend_log = open(ROOT_DIR / "server.log", "a", encoding="utf-8")
    backend_proc = subprocess.Popen(
        [resolve_python(), "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", "8001"],
        cwd=str(ROOT_DIR),
        stdin=subprocess.DEVNULL,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        **popen_extra,
    )
    backend_pid = backend_proc.pid

    # 2. Start Frontend Vite (port 5173; bind 127.0.0.1 by default to avoid exposing dev server on LAN)
    vite_host = os.getenv("VITE_HOST", "127.0.0.1")
    frontend_log = open(ROOT_DIR / "web.log", "a", encoding="utf-8")
    frontend_proc = subprocess.Popen(
        [*resolve_vite_cmd(), "--host", vite_host, "--port", "5173"],
        cwd=str(WEB_DIR),
        stdin=subprocess.PIPE,   # Keep stdin pipe open so Vite interactive prompt doesn't exit on EOF
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        **popen_extra,
    )
    frontend_pid = frontend_proc.pid

    PID_FILE.write_text(f"{backend_pid}\n{frontend_pid}\n", encoding="utf-8")

    print(f"Started Backend (PID: {backend_pid}) on http://127.0.0.1:8001")
    print(f"Started Frontend (PID: {frontend_pid}) on http://localhost:5173")


def stop():
    if not PID_FILE.exists():
        print("No PID file found.")
        return
    lines = PID_FILE.read_text(encoding="utf-8").strip().splitlines()
    for line in lines:
        if line.strip().isdigit():
            pid = int(line.strip())
            try:
                if _terminate_pid(pid):
                    print(f"Stopped PID {pid}")
            except Exception as e:
                print(f"Failed to kill {pid}: {e}")
    PID_FILE.unlink(missing_ok=True)


def status():
    # Check port 8001 and 5173
    import urllib.request
    backend_ok = False
    frontend_ok = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=2) as r:
            backend_ok = (r.status == 200)
    except Exception:
        pass

    try:
        with urllib.request.urlopen("http://127.0.0.1:5173", timeout=2) as r:
            frontend_ok = (r.status == 200)
    except Exception:
        pass

    print(f"Backend  (http://127.0.0.1:8001): {'UP' if backend_ok else 'DOWN'}")
    print(f"Frontend (http://localhost:5173):  {'UP' if frontend_ok else 'DOWN'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    # Optional 2nd arg selects the agent backend: agy | codex | mock. It is persisted to
    # .agent_driver (same file the UI's backend selector writes), so it survives later restarts.
    if len(sys.argv) > 2:
        chosen = sys.argv[2].lower()
        if chosen not in ("agy", "codex", "mock"):
            sys.exit(f"Unknown driver '{chosen}', expected agy | codex | mock")
        (ROOT_DIR / ".agent_driver").write_text(chosen + "\n", encoding="utf-8")
        os.environ.pop("AG_DRIVER", None)  # an exported AG_DRIVER would otherwise override it
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        stop()
        time.sleep(1)
        start()
    else:
        status()
