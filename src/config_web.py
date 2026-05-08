from __future__ import annotations

import json
import socket
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config_store import ROOT, load_config, save_config
from process_control import get_visualizer_pid, is_visualizer_running, start_visualizer, stop_visualizer, toggle_visualizer
from runtime_state import load_state, set_calibration_request, set_control_enabled, toggle_control_enabled
import pyautogui


WEB_ROOT = ROOT / "web"
HOST = "0.0.0.0"
PORT = 8765
FRAME_PATH = ROOT / "config" / "latest_frame.jpg"


class ConfigHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/config":
            self.write_json(load_config())
            return
        if path == "/api/status":
            state = load_state()
            self.write_json({
                "ok": True,
                "configPath": str(ROOT / "config" / "gesture_config.json"),
                "visualizerRunning": is_visualizer_running(),
                "visualizerPid": get_visualizer_pid(),
                "controlEnabled": bool(state.get("control_enabled", False)),
                "runtime": state.get("runtime", {}),
                "lanUrls": lan_urls(),
            })
            return
        if path == "/api/frame.jpg":
            self.write_frame()
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/config":
            self.handle_config_post()
            return
        if path == "/api/visualizer/toggle":
            self.write_json({"ok": True, **toggle_visualizer()})
            return
        if path == "/api/visualizer/start":
            self.write_json({"ok": True, "running": True, "pid": start_visualizer()})
            return
        if path == "/api/visualizer/stop":
            self.write_json({"ok": True, "running": False, "changed": stop_visualizer()})
            return
        if path == "/api/control/toggle":
            state = toggle_control_enabled()
            self.write_json({"ok": True, "controlEnabled": bool(state["control_enabled"])})
            return
        if path == "/api/control/on":
            state = set_control_enabled(True)
            self.write_json({"ok": True, "controlEnabled": bool(state["control_enabled"])})
            return
        if path == "/api/control/off":
            state = set_control_enabled(False)
            self.write_json({"ok": True, "controlEnabled": bool(state["control_enabled"])})
            return
        if path == "/api/mouse/move":
            payload = self.read_json_body()
            dx = clamp_int(payload.get("dx", 0), -250, 250)
            dy = clamp_int(payload.get("dy", 0), -250, 250)
            pyautogui.moveRel(dx, dy, duration=0)
            self.write_json({"ok": True, "dx": dx, "dy": dy})
            return
        if path == "/api/mouse/click":
            pyautogui.click()
            self.write_json({"ok": True})
            return
        if path == "/api/mouse/right-click":
            pyautogui.click(button="right")
            self.write_json({"ok": True})
            return
        if path == "/api/profile":
            payload = self.read_json_body()
            profile = str(payload.get("profile", "navigation"))
            config = load_config()
            if profile not in config.get("profiles", {}):
                self.write_json({"ok": False, "error": "Perfil no existe"}, status=HTTPStatus.BAD_REQUEST)
                return
            config["current_profile"] = profile
            save_config(config)
            self.write_json({"ok": True, "profile": profile})
            return
        if path == "/api/calibration/request":
            payload = self.read_json_body()
            label = str(payload.get("label", "open"))
            set_calibration_request(label)
            self.write_json({"ok": True, "label": label})
            return
        if path == "/api/voice/command":
            payload = self.read_json_body()
            self.write_json(handle_voice_command(str(payload.get("text", ""))))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def handle_config_post(self) -> None:
        if urlparse(self.path).path != "/api/config":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            data = json.loads(body.decode("utf-8"))
            save_config(clean_config(data))
        except (json.JSONDecodeError, ValueError) as exc:
            self.write_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        self.write_json({"ok": True, "config": load_config()})

    def write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def write_frame(self) -> None:
        if not FRAME_PATH.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = FRAME_PATH.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Frame-Time", str(int(time.time())))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        return


def clean_config(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("La configuracion debe ser un objeto JSON.")
    data["app_name"] = "OPENGESTURE"
    mode = str(data.get("vision_mode", "GESTURE")).upper()
    data["vision_mode"] = mode if mode in {"GESTURE", "FACE", "BODY"} else "GESTURE"
    for key in ("camera_hotkey", "control_hotkey"):
        value = str(data.get(key, "")).upper().replace(" ", "")
        parts = [part for part in value.split("+") if part]
        if len(parts) != 2 or any(len(part) != 1 or not part.isalpha() for part in parts):
            raise ValueError(f"{key} debe tener formato A+B.")
        data[key] = f"{parts[0]}+{parts[1]}"
    data["camera"] = max(0, int(data.get("camera", 0)))
    data["mirror"] = bool(data.get("mirror", True))
    data["control_enabled_on_start"] = bool(data.get("control_enabled_on_start", False))

    features = data.setdefault("features", {})
    for key, default in {
        "scroll": True,
        "zoom": True,
        "cursor": True,
        "air_mouse": False,
        "drag": True,
        "voice": True,
        "face": True,
        "body": True,
    }.items():
        features[key] = bool(features.get(key, default))

    scroll = data.setdefault("scroll", {})
    scroll["speed"] = clamp_int(scroll.get("speed", 2112), 0, 6000)
    scroll["max_step"] = clamp_int(scroll.get("max_step", 12), 1, 240)

    cursor = data.setdefault("cursor", {})
    cursor["speed"] = clamp_int(cursor.get("speed", 45), 0, 1000)
    cursor["max_step"] = clamp_int(cursor.get("max_step", 28), 1, 160)

    zoom = data.setdefault("zoom", {})
    zoom["threshold"] = clamp_float(zoom.get("threshold", 0.02), 0.005, 0.15)
    zoom["cooldown"] = clamp_float(zoom.get("cooldown", 0.25), 0.05, 2.0)
    two_hands = data.setdefault("two_hands", {})
    two_hands["distance_threshold"] = clamp_float(two_hands.get("distance_threshold", 0.015), 0.003, 0.08)
    trajectory = data.setdefault("trajectory", {})
    trajectory["seconds"] = clamp_float(trajectory.get("seconds", 4), 0.5, 15)
    trajectory["finger_trails"] = bool(trajectory.get("finger_trails", True))
    trajectory["hand_trails"] = bool(trajectory.get("hand_trails", True))
    trajectory["body_trails"] = bool(trajectory.get("body_trails", True))
    face = data.setdefault("face", {})
    face["enabled"] = bool(face.get("enabled", True))
    face["draw_mesh"] = bool(face.get("draw_mesh", True))
    face["blink_threshold"] = clamp_float(face.get("blink_threshold", 0.018), 0.006, 0.06)
    face["smile_threshold"] = clamp_float(face.get("smile_threshold", 3.2), 1.4, 8.0)
    face["gaze_dead_zone"] = clamp_float(face.get("gaze_dead_zone", 0.08), 0.01, 0.25)
    face["movement_smoothing"] = clamp_float(face.get("movement_smoothing", 0.22), 0.01, 0.9)
    body = data.setdefault("body", {})
    body["enabled"] = bool(body.get("enabled", True))
    body["draw_pose"] = bool(body.get("draw_pose", True))
    body["draw_digital_twin"] = bool(body.get("draw_digital_twin", True))
    body["trajectory_seconds"] = clamp_float(body.get("trajectory_seconds", 6), 1.0, 20.0)
    body["center_smoothing"] = clamp_float(body.get("center_smoothing", 0.2), 0.01, 0.9)
    voice = data.setdefault("voice", {})
    voice["language"] = str(voice.get("language", "es-ES"))
    voice["device_hint"] = str(voice.get("device_hint", "auto"))
    air_mouse = data.setdefault("air_mouse", {})
    air_mouse["smoothing"] = clamp_float(air_mouse.get("smoothing", 0.25), 0.05, 1.0)
    air_mouse["dead_zone"] = clamp_float(air_mouse.get("dead_zone", 0.04), 0.0, 0.2)

    gesture = data.setdefault("gesture", {})
    gesture["min_detection_confidence"] = clamp_float(gesture.get("min_detection_confidence", 0.65), 0.1, 0.95)
    gesture["min_tracking_confidence"] = clamp_float(gesture.get("min_tracking_confidence", 0.6), 0.1, 0.95)
    actions = data.setdefault("actions", {})
    allowed = {
        "none", "scroll_up", "scroll_down", "scroll_left", "scroll_right",
        "cursor_left", "cursor_right", "cursor_up", "cursor_down",
        "cursor_up_left", "cursor_up_right", "cursor_down_left", "cursor_down_right", "click",
        "right_click", "double_click", "drag", "zoom_in", "zoom_out", "close_window", "show_desktop",
        "alt_tab", "escape", "enter", "next_slide", "prev_slide", "play_pause", "volume_up",
        "volume_down", "mute", "media_next", "media_prev"
    }
    for key, default in {
        "open_up": "scroll_up",
        "open_down": "scroll_down",
        "open_left": "cursor_left",
        "open_right": "cursor_right",
        "open_up_left": "cursor_up_left",
        "open_up_right": "cursor_up_right",
        "open_down_left": "cursor_down_left",
        "open_down_right": "cursor_down_right",
        "pinch": "click",
        "both_pinch": "double_click",
        "fist_closer": "zoom_in",
        "fist_away": "zoom_out",
        "two_hands_apart": "zoom_in",
        "two_hands_together": "zoom_out",
        "split_vertical": "show_desktop",
    }.items():
        value = str(actions.get(key, default))
        actions[key] = value if value in allowed else default
    return data


def handle_voice_command(text: str) -> dict[str, Any]:
    command = text.lower().strip()
    if not command:
        return {"ok": False, "error": "Comando vacio"}
    if "activar control" in command or "control on" in command:
        state = set_control_enabled(True)
        return {"ok": True, "command": command, "controlEnabled": state["control_enabled"]}
    if "apagar control" in command or "desactivar control" in command or "control off" in command:
        state = set_control_enabled(False)
        return {"ok": True, "command": command, "controlEnabled": state["control_enabled"]}
    if "abrir camara" in command or "encender camara" in command:
        return {"ok": True, "command": command, "pid": start_visualizer()}
    if "cerrar camara" in command or "apagar camara" in command:
        return {"ok": True, "command": command, "changed": stop_visualizer()}
    mode_aliases = {
        "modo gestos": "GESTURE",
        "modo gesto": "GESTURE",
        "modo cara": "FACE",
        "modo face": "FACE",
        "modo cuerpo": "BODY",
        "modo body": "BODY",
    }
    for phrase, mode in mode_aliases.items():
        if phrase in command:
            config = load_config()
            config["vision_mode"] = mode
            save_config(config)
            return {"ok": True, "command": command, "visionMode": mode}
    profile_aliases = {
        "navigation": "navigation",
        "navegacion": "navigation",
        "presentacion": "presentation",
        "presentation": "presentation",
        "media": "media",
        "multimedia": "media",
        "air mouse": "air_mouse",
        "mouse aereo": "air_mouse",
        "air_mouse": "air_mouse",
    }
    for phrase, profile in profile_aliases.items():
        if phrase in command:
            config = load_config()
            config["current_profile"] = profile
            save_config(config)
            return {"ok": True, "command": command, "profile": profile}
    return {"ok": False, "command": command, "error": "No reconozco ese comando"}


def clamp_int(value: Any, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def clamp_float(value: Any, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def lan_urls() -> list[str]:
    urls = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                url = f"http://{ip}:{PORT}"
                if url not in urls:
                    urls.append(url)
    except socket.gaierror:
        pass
    return urls


def main() -> int:
    WEB_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), ConfigHandler)
    print(f"Config web abierta en http://127.0.0.1:{PORT}")
    for url in lan_urls():
        print(f"LAN: {url}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
