#!/usr/bin/env python3
"""Service manager for AG-SLG-FrameWork daemon processes."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
VENV_PYTHON = ROOT_DIR / ".venv" / "bin" / "python3"
PID_FILE = ROOT_DIR / ".services.pid"


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start():
    backend_pid = None
    frontend_pid = None

    # Check if already running
    # Clean any residual processes on ports 8001 and 5173
    for port in (8001, 5173):
        try:
            out = subprocess.check_output(["lsof", "-t", f"-i:{port}"], text=True).strip()
            for pid_str in out.splitlines():
                if pid_str.isdigit():
                    os.kill(int(pid_str), signal.SIGTERM)
        except Exception:
            pass

    time.sleep(0.5)

    # 1. Start Backend (port 8001)
    backend_log = open(ROOT_DIR / "server.log", "a")
    backend_proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", "8001"],
        cwd=str(ROOT_DIR),
        stdin=subprocess.DEVNULL,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # Fully detached session
    )
    backend_pid = backend_proc.pid

    # 2. Start Frontend Vite (port 5173)
    vite_bin = WEB_DIR / "node_modules" / ".bin" / "vite"
    frontend_log = open(ROOT_DIR / "web.log", "a")
    frontend_proc = subprocess.Popen(
        [str(vite_bin), "--host", "0.0.0.0", "--port", "5173"],
        cwd=str(WEB_DIR),
        stdin=subprocess.PIPE,   # Keep stdin pipe open so Vite interactive prompt doesn't exit on EOF
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # Fully detached session
    )
    frontend_pid = frontend_proc.pid

    PID_FILE.write_text(f"{backend_pid}\n{frontend_pid}\n")

    print(f"Started Backend (PID: {backend_pid}) on http://127.0.0.1:8001")
    print(f"Started Frontend (PID: {frontend_pid}) on http://localhost:5173")


def stop():
    if not PID_FILE.exists():
        print("No PID file found.")
        return
    lines = PID_FILE.read_text().strip().splitlines()
    for line in lines:
        if line.strip().isdigit():
            pid = int(line.strip())
            if is_running(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
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
