from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from config_store import ROOT


VENV_PYTHON = ROOT / ".venv" / "Scripts" / "pythonw.exe"
BUNDLED_PYTHONW = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python" / "pythonw.exe"
LOG_DIR = ROOT / "logs"
VISUALIZER_LOG = LOG_DIR / "gesture-visualizer.log"
VISUALIZER_OUT = LOG_DIR / "gesture-visualizer.out"
VISUALIZER_ERR = LOG_DIR / "gesture-visualizer.err"
PID_PATH = ROOT / "config" / "visualizer.pid"


def get_visualizer_pid() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except ValueError:
        PID_PATH.unlink(missing_ok=True)
        return None
    if is_pid_alive(pid):
        return pid
    PID_PATH.unlink(missing_ok=True)
    return None


def is_visualizer_running() -> bool:
    return get_visualizer_pid() is not None


def start_visualizer() -> int:
    existing = get_visualizer_pid()
    if existing is not None:
        return existing

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_handle = VISUALIZER_OUT.open("a", encoding="utf-8")
    err_handle = VISUALIZER_ERR.open("a", encoding="utf-8")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    process = subprocess.Popen(
        [
            str(resolve_pythonw()),
            str(ROOT / "src" / "gesture_visualizer.py"),
            "--log-file",
            str(VISUALIZER_LOG),
        ],
        cwd=ROOT,
        stdout=out_handle,
        stderr=err_handle,
        creationflags=creationflags,
        env=python_env(),
    )
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(process.pid), encoding="utf-8")
    return process.pid


def stop_visualizer() -> bool:
    pid = get_visualizer_pid()
    if pid is None:
        return False

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        PID_PATH.unlink(missing_ok=True)
        return False

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not is_pid_alive(pid):
            PID_PATH.unlink(missing_ok=True)
            return True
        time.sleep(0.1)

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    PID_PATH.unlink(missing_ok=True)
    return True


def toggle_visualizer() -> dict[str, int | bool | None]:
    if is_visualizer_running():
        stopped = stop_visualizer()
        return {"running": False, "pid": None, "changed": stopped}
    pid = start_visualizer()
    return {"running": True, "pid": pid, "changed": True}


def resolve_pythonw() -> Path | str:
    if VENV_PYTHON.exists() and can_run_python(VENV_PYTHON):
        return VENV_PYTHON
    if BUNDLED_PYTHONW.exists():
        return BUNDLED_PYTHONW
    return sys.executable


def can_run_python(path: Path) -> bool:
    try:
        result = subprocess.run([str(path), "-c", "pass"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def python_env() -> dict[str, str]:
    env = os.environ.copy()
    site_packages = ROOT / ".venv" / "Lib" / "site-packages"
    if site_packages.exists():
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(site_packages) if not existing else str(site_packages) + os.pathsep + existing
    return env


def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
