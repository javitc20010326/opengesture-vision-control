from __future__ import annotations

import ctypes
import time
from pathlib import Path

from config_store import load_config
from process_control import is_visualizer_running, start_visualizer, stop_visualizer


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LAUNCHER_LOG = LOG_DIR / "gesture-launcher.log"


class Hotkey:
    def __init__(self, first_key: str, second_key: str) -> None:
        self.first_key = first_key.upper()
        self.second_key = second_key.upper()
        self.was_pressed = False

    def pressed_once(self) -> bool:
        pressed = is_key_down(self.first_key) and is_key_down(self.second_key)
        if pressed and not self.was_pressed:
            self.was_pressed = True
            return True
        if not pressed:
            self.was_pressed = False
        return False


def is_key_down(key: str) -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(ord(key)) & 0x8000)


def split_two_key_hotkey(hotkey: str) -> tuple[str, str]:
    keys = [key.strip().upper() for key in hotkey.split("+") if len(key.strip()) == 1]
    if len(keys) != 2:
        return ("E", "R")
    return (keys[0], keys[1])


def append_log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%H:%M:%S")
    with LAUNCHER_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def main() -> int:
    config = load_config()
    camera_hotkey = str(config.get("camera_hotkey", "E+R"))
    append_log(f"launcher START hotkey={camera_hotkey}")
    launch_hotkey = Hotkey(*split_two_key_hotkey(camera_hotkey))
    last_config_at = 0.0

    try:
        while True:
            now = time.monotonic()
            if now - last_config_at > 1.0:
                config = load_config()
                updated_hotkey = str(config.get("camera_hotkey", "E+R"))
                if updated_hotkey != camera_hotkey:
                    camera_hotkey = updated_hotkey
                    launch_hotkey = Hotkey(*split_two_key_hotkey(camera_hotkey))
                    append_log(f"hotkey UPDATE {camera_hotkey}")
                last_config_at = now

            if launch_hotkey.pressed_once():
                if is_visualizer_running():
                    stopped = stop_visualizer()
                    append_log(f"visualizer STOP changed={stopped}")
                else:
                    pid = start_visualizer()
                    append_log(f"visualizer START pid={pid}")

            time.sleep(0.05)
    except KeyboardInterrupt:
        append_log("launcher STOP keyboard interrupt")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
