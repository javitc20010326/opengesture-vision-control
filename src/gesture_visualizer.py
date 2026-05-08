from __future__ import annotations

import argparse
import ctypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
import pyautogui

from config_store import load_config
from gesture_logic import Gesture, Point, classify_gesture
from runtime_state import load_state, save_state, set_calibration_request, set_control_enabled, update_runtime_status


WINDOW_NAME = "Visualizador IA - Gestos"
FRAME_PATH = Path(__file__).resolve().parents[1] / "config" / "latest_frame.jpg"
POSE_POINTS = {
    "left_wrist": 15,
    "right_wrist": 16,
    "left_ankle": 27,
    "right_ankle": 28,
}
POSE_CONNECTIONS = (
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
    (24, 26), (26, 28), (27, 31), (28, 32)
)


@dataclass
class ControlState:
    enabled: bool
    last_action_at: float = 0.0
    last_pinch_distance: float | None = None
    last_fist_size: float | None = None
    scroll_accumulator: float = 0.0
    cursor_x_accumulator: float = 0.0
    cursor_y_accumulator: float = 0.0
    last_two_hand_distance: float | None = None
    last_frame_write_at: float = 0.0
    hotkey_pressed: bool = False
    last_click_at: float = 0.0
    last_desktop_at: float = 0.0
    last_system_action_at: float = 0.0
    dragging: bool = False
    air_mouse_x: float | None = None
    air_mouse_y: float | None = None
    trajectories: dict[str, list[tuple[float, float, float]]] | None = None
    stable_gesture: str = "NO_HAND"
    stable_count: int = 0
    last_face_center: tuple[float, float] | None = None
    smoothed_body_center: tuple[float, float] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualizador IA de gestos con webcam")
    parser.add_argument("--camera", type=int, default=None, help="Indice de camara. Normalmente 0.")
    parser.add_argument("--control", action="store_true", help="Activa control real de pantalla.")
    parser.add_argument("--scroll-amount", type=int, default=None, help="Velocidad de scroll por segundo.")
    parser.add_argument("--cooldown", type=float, default=0.25, help="Segundos entre acciones.")
    parser.add_argument("--log-file", type=Path, default=None, help="Archivo opcional para registrar gestos.")
    parser.add_argument("--mirror", action="store_true", default=True, help="Muestra la camara en espejo.")
    parser.add_argument("--no-mirror", action="store_false", dest="mirror", help="No espejar camara.")
    return parser.parse_args()


def landmarks_to_points(hand_landmarks) -> dict[int, Point]:
    return {
        idx: Point(landmark.x, landmark.y)
        for idx, landmark in enumerate(hand_landmarks.landmark)
    }


FINGER_RAYS = (
    (2, 4),
    (6, 8),
    (10, 12),
    (14, 16),
    (18, 20),
)


def apply_profile(config: dict[str, Any]) -> dict[str, Any]:
    profile_name = str(config.get("current_profile", "navigation"))
    profile = get_nested(config, ("profiles", profile_name), {})
    if not isinstance(profile, dict):
        return config
    merged = dict(config)
    for key in ("features", "actions", "scroll", "cursor", "zoom", "air_mouse"):
        if isinstance(profile.get(key), dict):
            merged[key] = {**config.get(key, {}), **profile[key]}
    return merged


def draw_pinch_marker(frame, hand_landmarks, pinch_distance: float | None) -> None:
    if pinch_distance is None or pinch_distance >= 0.38:
        return
    height, width = frame.shape[:2]
    thumb = hand_landmarks.landmark[4]
    index = hand_landmarks.landmark[8]
    thumb_point = (int(thumb.x * width), int(thumb.y * height))
    index_point = (int(index.x * width), int(index.y * height))
    cv2.circle(frame, thumb_point, 10, (0, 210, 255), 2)
    cv2.circle(frame, index_point, 10, (0, 210, 255), 2)
    cv2.line(frame, thumb_point, index_point, (0, 210, 255), 2)


def draw_finger_rays(frame, hand_landmarks) -> None:
    height, width = frame.shape[:2]
    for base_id, tip_id in FINGER_RAYS:
        base = hand_landmarks.landmark[base_id]
        tip = hand_landmarks.landmark[tip_id]
        start = (int(base.x * width), int(base.y * height))
        end_x = int((tip.x + (tip.x - base.x) * 0.9) * width)
        end_y = int((tip.y + (tip.y - base.y) * 0.9) * height)
        cv2.arrowedLine(frame, start, (end_x, end_y), (255, 170, 60), 2, tipLength=0.22)


def hand_orientation(hand_landmarks, handedness_label: str | None) -> str:
    thumb_x = hand_landmarks.landmark[4].x
    pinky_x = hand_landmarks.landmark[20].x
    if handedness_label == "Right":
        return "palm" if thumb_x < pinky_x else "back"
    if handedness_label == "Left":
        return "palm" if thumb_x > pinky_x else "back"
    return "unknown"


def get_nested(config: dict[str, Any], path: tuple[str, ...], default: Any) -> Any:
    current: Any = config
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def hotkey_down(hotkey: str) -> bool:
    keys = [key.strip().upper() for key in hotkey.split("+") if key.strip()]
    if not keys:
        return False
    user32 = ctypes.windll.user32
    return all(user32.GetAsyncKeyState(ord(key)) & 0x8000 for key in keys if len(key) == 1)


def maybe_control_screen(
    state: ControlState,
    gesture: Gesture,
    pinch_distance: float | None,
    hand_size: float | None,
    args: argparse.Namespace,
    config: dict[str, Any],
    elapsed: float,
) -> str:
    if not state.enabled:
        state.last_pinch_distance = pinch_distance
        state.last_fist_size = hand_size if gesture == Gesture.FIST else None
        state.scroll_accumulator = 0.0
        state.cursor_x_accumulator = 0.0
        state.cursor_y_accumulator = 0.0
        return "control OFF"

    now = time.monotonic()

    if state.dragging and gesture != Gesture.PINCH:
        pyautogui.mouseUp()
        state.dragging = False

    if gesture == Gesture.FIST:
        if not get_nested(config, ("features", "zoom"), True):
            return "zoom OFF"
        if now - state.last_action_at < float(get_nested(config, ("zoom", "cooldown"), args.cooldown)):
            return "cooldown"
        action = control_fist_motion(state, hand_size, float(get_nested(config, ("zoom", "threshold"), 0.02)), config)
        if action:
            state.last_action_at = now
            return action
        return "fist zoom ready"

    if gesture == Gesture.OPEN_UP:
        state.last_fist_size = None
        return run_action(state, str(get_nested(config, ("actions", "open_up"), "scroll_up")), config, elapsed)

    if gesture == Gesture.OPEN_DOWN:
        state.last_fist_size = None
        return run_action(state, str(get_nested(config, ("actions", "open_down"), "scroll_down")), config, elapsed)

    if gesture == Gesture.OPEN_RIGHT:
        state.last_fist_size = None
        return run_action(state, str(get_nested(config, ("actions", "open_right"), "cursor_right")), config, elapsed)

    if gesture == Gesture.OPEN_LEFT:
        state.last_fist_size = None
        return run_action(state, str(get_nested(config, ("actions", "open_left"), "cursor_left")), config, elapsed)

    if gesture == Gesture.OPEN_UP_RIGHT:
        state.last_fist_size = None
        return run_action(state, str(get_nested(config, ("actions", "open_up_right"), "cursor_up_right")), config, elapsed)

    if gesture == Gesture.OPEN_UP_LEFT:
        state.last_fist_size = None
        return run_action(state, str(get_nested(config, ("actions", "open_up_left"), "cursor_up_left")), config, elapsed)

    if gesture == Gesture.OPEN_DOWN_RIGHT:
        state.last_fist_size = None
        return run_action(state, str(get_nested(config, ("actions", "open_down_right"), "cursor_down_right")), config, elapsed)

    if gesture == Gesture.OPEN_DOWN_LEFT:
        state.last_fist_size = None
        return run_action(state, str(get_nested(config, ("actions", "open_down_left"), "cursor_down_left")), config, elapsed)

    if gesture == Gesture.PINCH and pinch_distance is not None:
        return run_action(state, str(get_nested(config, ("actions", "pinch"), "click")), config, elapsed)

    state.last_pinch_distance = pinch_distance
    state.scroll_accumulator = 0.0
    state.cursor_x_accumulator = 0.0
    state.cursor_y_accumulator = 0.0
    if gesture != Gesture.FIST:
        state.last_fist_size = None
    return "waiting"


def run_action(state: ControlState, action: str, config: dict[str, Any], elapsed: float) -> str:
    if action == "none":
        return "no action"
    if action == "scroll_up":
        if not get_nested(config, ("features", "scroll"), True):
            return "scroll OFF"
        return smooth_scroll(state, 1, config, elapsed)
    if action == "scroll_down":
        if not get_nested(config, ("features", "scroll"), True):
            return "scroll OFF"
        return smooth_scroll(state, -1, config, elapsed)
    if action == "scroll_left":
        if not get_nested(config, ("features", "scroll"), True):
            return "scroll OFF"
        pyautogui.hscroll(-8)
        return "hscroll -8"
    if action == "scroll_right":
        if not get_nested(config, ("features", "scroll"), True):
            return "scroll OFF"
        pyautogui.hscroll(8)
        return "hscroll +8"
    if action == "cursor_left":
        if not get_nested(config, ("features", "cursor"), True):
            return "cursor OFF"
        return smooth_cursor(state, -1, 0, config, elapsed)
    if action == "cursor_right":
        if not get_nested(config, ("features", "cursor"), True):
            return "cursor OFF"
        return smooth_cursor(state, 1, 0, config, elapsed)
    if action == "cursor_up":
        if not get_nested(config, ("features", "cursor"), True):
            return "cursor OFF"
        return smooth_cursor(state, 0, -1, config, elapsed)
    if action == "cursor_down":
        if not get_nested(config, ("features", "cursor"), True):
            return "cursor OFF"
        return smooth_cursor(state, 0, 1, config, elapsed)
    if action == "cursor_up_left":
        if not get_nested(config, ("features", "cursor"), True):
            return "cursor OFF"
        return smooth_cursor(state, -1, -1, config, elapsed)
    if action == "cursor_up_right":
        if not get_nested(config, ("features", "cursor"), True):
            return "cursor OFF"
        return smooth_cursor(state, 1, -1, config, elapsed)
    if action == "cursor_down_left":
        if not get_nested(config, ("features", "cursor"), True):
            return "cursor OFF"
        return smooth_cursor(state, -1, 1, config, elapsed)
    if action == "cursor_down_right":
        if not get_nested(config, ("features", "cursor"), True):
            return "cursor OFF"
        return smooth_cursor(state, 1, 1, config, elapsed)
    if action == "click":
        return click_once(state)
    if action == "drag":
        if not get_nested(config, ("features", "drag"), True):
            return "drag OFF"
        if not state.dragging:
            pyautogui.mouseDown()
            state.dragging = True
            return "drag start"
        return "dragging"
    if action == "right_click":
        return click_once(state, button="right")
    if action == "double_click":
        now = time.monotonic()
        if now - state.last_click_at < 0.7:
            return "click cooldown"
        pyautogui.doubleClick()
        state.last_click_at = now
        return "double click"
    if action == "zoom_in":
        if not get_nested(config, ("features", "zoom"), True):
            return "zoom OFF"
        pyautogui.hotkey("ctrl", "+")
        return "zoom in"
    if action == "zoom_out":
        if not get_nested(config, ("features", "zoom"), True):
            return "zoom OFF"
        pyautogui.hotkey("ctrl", "-")
        return "zoom out"
    if action == "close_window":
        now = time.monotonic()
        if now - state.last_system_action_at < 1.2:
            return "system cooldown"
        pyautogui.hotkey("alt", "f4")
        state.last_system_action_at = now
        return "close window"
    if action == "show_desktop":
        now = time.monotonic()
        if now - state.last_desktop_at < 1.2:
            return "desktop cooldown"
        pyautogui.hotkey("win", "d")
        state.last_desktop_at = now
        return "show desktop"
    if action == "alt_tab":
        now = time.monotonic()
        if now - state.last_system_action_at < 1.2:
            return "system cooldown"
        pyautogui.hotkey("alt", "tab")
        state.last_system_action_at = now
        return "alt tab"
    if action == "escape":
        pyautogui.press("esc")
        return "escape"
    if action == "enter":
        pyautogui.press("enter")
        return "enter"
    if action == "next_slide":
        pyautogui.press("right")
        return "next slide"
    if action == "prev_slide":
        pyautogui.press("left")
        return "prev slide"
    if action == "play_pause":
        pyautogui.press("space")
        return "play pause"
    if action == "volume_up":
        pyautogui.press("volumeup")
        return "volume up"
    if action == "volume_down":
        pyautogui.press("volumedown")
        return "volume down"
    if action == "mute":
        pyautogui.press("volumemute")
        return "mute"
    if action == "media_next":
        pyautogui.press("nexttrack")
        return "media next"
    if action == "media_prev":
        pyautogui.press("prevtrack")
        return "media prev"
    return "unknown action"


def click_once(state: ControlState, button: str = "left") -> str:
    now = time.monotonic()
    if now - state.last_click_at < 0.55:
        return "click cooldown"
    pyautogui.click(button=button)
    state.last_click_at = now
    return f"{button} click"


def smooth_scroll(state: ControlState, direction: int, config: dict[str, Any], elapsed: float) -> str:
    speed = float(get_nested(config, ("scroll", "speed"), 2112))
    max_step = max(1, int(get_nested(config, ("scroll", "max_step"), 12)))
    state.scroll_accumulator += direction * speed * elapsed
    amount = int(state.scroll_accumulator)
    if amount == 0:
        return "scroll smoothing"
    remaining = abs(amount)
    step_direction = 1 if amount > 0 else -1
    sent = 0
    events = 0
    while remaining > 0 and events < 20:
        step = min(max_step, remaining)
        pyautogui.scroll(step * step_direction)
        sent += step
        remaining -= step
        events += 1
    state.scroll_accumulator -= sent * step_direction
    return f"scroll {sent * step_direction:+d}"


def smooth_cursor(state: ControlState, direction_x: int, direction_y: int, config: dict[str, Any], elapsed: float) -> str:
    speed = float(get_nested(config, ("cursor", "speed"), 45))
    max_step = max(1, int(get_nested(config, ("cursor", "max_step"), 28)))
    state.cursor_x_accumulator += direction_x * speed * elapsed
    state.cursor_y_accumulator += direction_y * speed * elapsed
    amount_x = int(state.cursor_x_accumulator)
    amount_y = int(state.cursor_y_accumulator)
    if amount_x == 0 and amount_y == 0:
        return "cursor smoothing"
    amount_x = max(-max_step, min(max_step, amount_x))
    amount_y = max(-max_step, min(max_step, amount_y))
    pyautogui.moveRel(amount_x, amount_y, duration=0)
    state.cursor_x_accumulator -= amount_x
    state.cursor_y_accumulator -= amount_y
    return f"cursor {amount_x:+d},{amount_y:+d}"


def control_two_hands(state: ControlState, detected_hands: list, config: dict[str, Any], elapsed: float) -> str | None:
    if len(detected_hands) < 2:
        state.last_two_hand_distance = None
        return None

    first_points = landmarks_to_points(detected_hands[0][0])
    second_points = landmarks_to_points(detected_hands[1][0])
    first_center = hand_center(first_points)
    second_center = hand_center(second_points)
    distance = ((first_center.x - second_center.x) ** 2 + (first_center.y - second_center.y) ** 2) ** 0.5

    both_pinch = all(hand_result.gesture == Gesture.PINCH for _, hand_result in detected_hands[:2])
    if both_pinch:
        return run_action(state, str(get_nested(config, ("actions", "both_pinch"), "double_click")), config, elapsed)

    gestures = {detected_hands[0][1].gesture, detected_hands[1][1].gesture}
    if Gesture.OPEN_UP in gestures and Gesture.OPEN_DOWN in gestures:
        return run_action(state, str(get_nested(config, ("actions", "split_vertical"), "show_desktop")), config, elapsed)

    previous = state.last_two_hand_distance
    state.last_two_hand_distance = distance
    if previous is None:
        return "two hands ready"
    delta = distance - previous
    threshold = float(get_nested(config, ("two_hands", "distance_threshold"), 0.015))
    if abs(delta) < threshold:
        return "two hands hold"
    if delta > 0:
        return run_action(state, str(get_nested(config, ("actions", "two_hands_apart"), "zoom_in")), config, elapsed)
    return run_action(state, str(get_nested(config, ("actions", "two_hands_together"), "zoom_out")), config, elapsed)


def hand_center(points: dict[int, Point]) -> Point:
    return Point(
        sum(point.x for point in points.values()) / len(points),
        sum(point.y for point in points.values()) / len(points),
    )


def write_latest_frame(state: ControlState, frame, now: float) -> None:
    if now - state.last_frame_write_at < 0.15:
        return
    FRAME_PATH.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(FRAME_PATH), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
    state.last_frame_write_at = now


def update_trajectories(state: ControlState, hand_id: int, hand_landmarks, config: dict[str, Any], now: float) -> None:
    if state.trajectories is None:
        state.trajectories = {}
    seconds = float(get_nested(config, ("trajectory", "seconds"), 4))
    points = landmarks_to_points(hand_landmarks)
    center = hand_center(points)
    samples = {"hand": center}
    if get_nested(config, ("trajectory", "finger_trails"), True):
        for tip_id in (4, 8, 12, 16, 20):
            samples[f"finger_{tip_id}"] = points[tip_id]
    for name, point in samples.items():
        key = f"{hand_id}_{name}"
        trail = state.trajectories.setdefault(key, [])
        trail.append((now, point.x, point.y))
        state.trajectories[key] = [item for item in trail if now - item[0] <= seconds]


def draw_trajectories(frame, state: ControlState) -> None:
    if not state.trajectories:
        return
    height, width = frame.shape[:2]
    for key, trail in state.trajectories.items():
        if key.startswith("body_"):
            continue
        if len(trail) < 2:
            continue
        color = (80, 255, 180) if "hand" in key else (180, 120, 255)
        pts = [(int(x * width), int(y * height)) for _, x, y in trail]
        for start, end in zip(pts, pts[1:]):
            cv2.line(frame, start, end, color, 2)


def update_air_mouse(state: ControlState, hand_landmarks, config: dict[str, Any]) -> str | None:
    if not get_nested(config, ("features", "air_mouse"), False):
        return None
    points = landmarks_to_points(hand_landmarks)
    center = hand_center(points)
    dead_zone = float(get_nested(config, ("air_mouse", "dead_zone"), 0.04))
    smoothing = float(get_nested(config, ("air_mouse", "smoothing"), 0.25))
    screen_w, screen_h = pyautogui.size()
    target_x = center.x * screen_w
    target_y = center.y * screen_h
    if state.air_mouse_x is None or state.air_mouse_y is None:
        state.air_mouse_x = target_x
        state.air_mouse_y = target_y
    dx_norm = abs(target_x - state.air_mouse_x) / screen_w
    dy_norm = abs(target_y - state.air_mouse_y) / screen_h
    if dx_norm < dead_zone and dy_norm < dead_zone:
        return "air mouse hold"
    state.air_mouse_x = state.air_mouse_x + (target_x - state.air_mouse_x) * smoothing
    state.air_mouse_y = state.air_mouse_y + (target_y - state.air_mouse_y) * smoothing
    pyautogui.moveTo(int(state.air_mouse_x), int(state.air_mouse_y), duration=0)
    return "air mouse"


def stabilize_gesture(state: ControlState, gesture: Gesture, config: dict[str, Any]) -> Gesture:
    stable_frames = int(get_nested(config, ("gesture", "stable_frames"), 4))
    if gesture.value == state.stable_gesture:
        state.stable_count += 1
    else:
        state.stable_gesture = gesture.value
        state.stable_count = 1
    if state.stable_count >= stable_frames:
        return gesture
    return Gesture.UNKNOWN


def handle_calibration_request(config: dict[str, Any], gesture_result, runtime_state: dict[str, Any]) -> None:
    label = runtime_state.get("calibration_request")
    if not label or gesture_result.gesture == Gesture.NO_HAND:
        return
    calibration = config.setdefault("calibration", {})
    calibration[str(label)] = {
        "gesture": gesture_result.gesture.value,
        "pinch_distance": gesture_result.pinch_distance,
        "hand_size": gesture_result.hand_size,
        "captured_at": time.time(),
    }
    from config_store import save_config

    save_config(config)
    set_calibration_request(None)


def update_hotkey_toggle(state: ControlState, control_hotkey: str) -> bool:
    pressed = hotkey_down(control_hotkey)
    if pressed and not state.hotkey_pressed:
        state.enabled = not state.enabled
        set_control_enabled(state.enabled)
        state.last_pinch_distance = None
        state.last_fist_size = None
        state.hotkey_pressed = True
        return True
    if not pressed:
        state.hotkey_pressed = False
    return False


def control_zoom_from_pinch(state: ControlState, pinch_distance: float) -> str | None:
    previous = state.last_pinch_distance
    state.last_pinch_distance = pinch_distance

    if previous is None:
        return None

    delta = pinch_distance - previous
    if abs(delta) < 0.05:
        return None

    if delta > 0:
        pyautogui.hotkey("ctrl", "+")
        return "zoom in"

    pyautogui.hotkey("ctrl", "-")
    return "zoom out"


def control_fist_motion(state: ControlState, hand_size: float | None, threshold: float, config: dict[str, Any]) -> str | None:
    if hand_size is None:
        state.last_fist_size = None
        return None

    previous = state.last_fist_size
    state.last_fist_size = hand_size

    if previous is None:
        return None

    delta = hand_size - previous
    if abs(delta) < threshold:
        return None

    if delta > 0:
        return run_action(state, str(get_nested(config, ("actions", "fist_closer"), "zoom_in")), config, 0)

    return run_action(state, str(get_nested(config, ("actions", "fist_away"), "zoom_out")), config, 0)


def process_face(frame, face_landmarks, state: ControlState, config: dict[str, Any]) -> dict[str, Any]:
    height, width = frame.shape[:2]
    landmarks = face_landmarks.landmark
    xs = [point.x for point in landmarks]
    ys = [point.y for point in landmarks]
    center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    nose = landmarks[1]

    previous = state.last_face_center
    state.last_face_center = center
    movement = "still"
    if previous is not None:
        dx = center[0] - previous[0]
        dy = center[1] - previous[1]
        if abs(dx) > 0.012 or abs(dy) > 0.012:
            movement = "right" if abs(dx) > abs(dy) and dx > 0 else "left" if abs(dx) > abs(dy) else "down" if dy > 0 else "up"

    left_open = eye_open_ratio(landmarks, 159, 145)
    right_open = eye_open_ratio(landmarks, 386, 374)
    threshold = float(get_nested(config, ("face", "blink_threshold"), 0.018))
    left_eye = "closed" if left_open < threshold else "open"
    right_eye = "closed" if right_open < threshold else "open"
    smile = smile_ratio(landmarks) > float(get_nested(config, ("face", "smile_threshold"), 3.2))
    gaze = estimate_gaze(landmarks, config)

    if get_nested(config, ("face", "draw_mesh"), True):
        cv2.rectangle(frame, (int(min(xs) * width), int(min(ys) * height)), (int(max(xs) * width), int(max(ys) * height)), (140, 220, 255), 2)
        cv2.circle(frame, (int(nose.x * width), int(nose.y * height)), 5, (0, 255, 255), -1)
        cv2.putText(frame, f"face {movement} gaze {gaze}", (16, height - 52), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (140, 220, 255), 2)
        cv2.putText(frame, f"smile {smile} L {left_eye} R {right_eye}", (16, height - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (140, 220, 255), 2)

    return {
        "detected": True,
        "center": [round(center[0], 3), round(center[1], 3)],
        "movement": movement,
        "smile": smile,
        "left_eye": left_eye,
        "right_eye": right_eye,
        "gaze": gaze,
        "nose": [round(nose.x, 3), round(nose.y, 3)],
    }


def eye_open_ratio(landmarks, upper_id: int, lower_id: int) -> float:
    return abs(landmarks[upper_id].y - landmarks[lower_id].y)


def smile_ratio(landmarks) -> float:
    width = ((landmarks[61].x - landmarks[291].x) ** 2 + (landmarks[61].y - landmarks[291].y) ** 2) ** 0.5
    height = abs(landmarks[13].y - landmarks[14].y) + 0.001
    return width / height


def estimate_gaze(landmarks, config: dict[str, Any]) -> str:
    if len(landmarks) < 478:
        return "front"
    dead_zone = float(get_nested(config, ("face", "gaze_dead_zone"), 0.08))
    left_iris_x = sum(landmarks[idx].x for idx in (468, 469, 470, 471, 472)) / 5
    right_iris_x = sum(landmarks[idx].x for idx in (473, 474, 475, 476, 477)) / 5
    left_iris_y = sum(landmarks[idx].y for idx in (468, 469, 470, 471, 472)) / 5
    right_iris_y = sum(landmarks[idx].y for idx in (473, 474, 475, 476, 477)) / 5
    left_mid_x = (landmarks[33].x + landmarks[133].x) / 2
    right_mid_x = (landmarks[362].x + landmarks[263].x) / 2
    left_mid_y = (landmarks[159].y + landmarks[145].y) / 2
    right_mid_y = (landmarks[386].y + landmarks[374].y) / 2
    dx = ((left_iris_x - left_mid_x) + (right_iris_x - right_mid_x)) / 2
    dy = ((left_iris_y - left_mid_y) + (right_iris_y - right_mid_y)) / 2
    if abs(dx) > abs(dy) and abs(dx) > dead_zone * 0.12:
        return "right" if dx > 0 else "left"
    if abs(dy) > dead_zone * 0.09:
        return "down" if dy > 0 else "up"
    return "front"


def process_body(frame, pose_landmarks, state: ControlState, config: dict[str, Any], now: float, mp_pose) -> tuple[Any, dict[str, Any]]:
    if not pose_landmarks:
        return frame, {"detected": False, "motion": "idle", "center_of_gravity": None, "trajectory_points": 0, "digital_twin": False}

    height, width = frame.shape[:2]
    landmarks = pose_landmarks.landmark
    center = body_center(landmarks)
    smoothing = float(get_nested(config, ("body", "center_smoothing"), 0.2))
    if state.smoothed_body_center is None:
        state.smoothed_body_center = center
    else:
        state.smoothed_body_center = (
            state.smoothed_body_center[0] + (center[0] - state.smoothed_body_center[0]) * smoothing,
            state.smoothed_body_center[1] + (center[1] - state.smoothed_body_center[1]) * smoothing,
        )

    update_body_trajectories(state, landmarks, config, now)
    if get_nested(config, ("body", "draw_pose"), True):
        draw_pose_lines(frame, landmarks, width, height)
        draw_body_trails_on_frame(frame, state, width, height)
        cog = (int(state.smoothed_body_center[0] * width), int(state.smoothed_body_center[1] * height))
        cv2.circle(frame, cog, 10, (0, 255, 180), -1)
        cv2.putText(frame, "COG", (cog[0] + 12, cog[1] + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 180), 2)

    motion = body_motion_label(state)
    digital_twin = bool(get_nested(config, ("body", "draw_digital_twin"), True))
    output = append_body_twin(frame, landmarks, state) if digital_twin else frame
    return output, {
        "detected": True,
        "motion": motion,
        "center_of_gravity": [round(state.smoothed_body_center[0], 3), round(state.smoothed_body_center[1], 3)],
        "trajectory_points": sum(len(v) for k, v in (state.trajectories or {}).items() if k.startswith("body_")),
        "digital_twin": digital_twin,
    }


def body_center(landmarks) -> tuple[float, float]:
    ids = (11, 12, 23, 24)
    x = sum(landmarks[idx].x for idx in ids) / len(ids)
    y = sum(landmarks[idx].y for idx in ids) / len(ids)
    return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))


def update_body_trajectories(state: ControlState, landmarks, config: dict[str, Any], now: float) -> None:
    if state.trajectories is None:
        state.trajectories = {}
    seconds = float(get_nested(config, ("body", "trajectory_seconds"), 6))
    samples = {name: (landmarks[idx].x, landmarks[idx].y) for name, idx in POSE_POINTS.items()}
    samples["center"] = body_center(landmarks)
    for name, (x, y) in samples.items():
        key = f"body_{name}"
        trail = state.trajectories.setdefault(key, [])
        trail.append((now, x, y))
        state.trajectories[key] = [item for item in trail if now - item[0] <= seconds]


def body_motion_label(state: ControlState) -> str:
    if not state.trajectories:
        return "idle"
    left = state.trajectories.get("body_left_ankle", [])
    right = state.trajectories.get("body_right_ankle", [])
    if len(left) < 3 or len(right) < 3:
        return "warming"
    span = max(abs(left[-1][1] - left[0][1]), abs(right[-1][1] - right[0][1]), abs(left[-1][2] - left[0][2]), abs(right[-1][2] - right[0][2]))
    if span > 0.18:
        return "running/dancing"
    if span > 0.06:
        return "walking/lifting"
    return "stable"


def draw_pose_lines(frame, landmarks, width: int, height: int) -> None:
    for start_id, end_id in POSE_CONNECTIONS:
        start = landmarks[start_id]
        end = landmarks[end_id]
        if start.visibility < 0.35 or end.visibility < 0.35:
            continue
        cv2.line(frame, (int(start.x * width), int(start.y * height)), (int(end.x * width), int(end.y * height)), (120, 180, 255), 3)
    for name, idx in POSE_POINTS.items():
        point = landmarks[idx]
        if point.visibility > 0.35:
            cv2.circle(frame, (int(point.x * width), int(point.y * height)), 7, (255, 220, 80), -1)


def draw_body_trails_on_frame(frame, state: ControlState, width: int, height: int) -> None:
    if not state.trajectories:
        return
    for key, trail in state.trajectories.items():
        if not key.startswith("body_") or len(trail) < 2:
            continue
        color = (80, 210, 255) if "ankle" in key else (180, 120, 255)
        pts = [(int(x * width), int(y * height)) for _, x, y in trail]
        for start, end in zip(pts, pts[1:]):
            cv2.line(frame, start, end, color, 2)


def append_body_twin(frame, landmarks, state: ControlState):
    height = frame.shape[0]
    panel_w = 280
    panel = np.full((height, panel_w, 3), (248, 250, 252), dtype=np.uint8)
    cv2.putText(panel, "BODY TWIN", (24, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (31, 41, 55), 2)
    for start_id, end_id in POSE_CONNECTIONS:
        start = twin_point(landmarks[start_id], panel_w, height)
        end = twin_point(landmarks[end_id], panel_w, height)
        cv2.line(panel, start, end, (47, 111, 101), 3)
    draw_body_trails_on_panel(panel, state, panel_w, height)
    return np.hstack((frame, panel))


def twin_point(landmark, width: int, height: int) -> tuple[int, int]:
    x = int(max(0.05, min(0.95, landmark.x)) * width)
    y = int(max(0.08, min(0.96, landmark.y)) * height)
    return x, y


def draw_body_trails_on_panel(panel, state: ControlState, width: int, height: int) -> None:
    if not state.trajectories:
        return
    for key, trail in state.trajectories.items():
        if not key.startswith("body_") or len(trail) < 2:
            continue
        color = (220, 120, 80) if "ankle" in key else (128, 90, 213)
        pts = [(int(x * width), int(y * height)) for _, x, y in trail]
        for start, end in zip(pts, pts[1:]):
            cv2.line(panel, start, end, color, 2)


def draw_overlay(frame, gesture_text: str, control_text: str, fps: float) -> None:
    height, width = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (width, 112), (20, 20, 20), -1)
    cv2.putText(frame, f"Gesto: {gesture_text}", (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (80, 255, 160), 2)
    cv2.putText(frame, f"Accion: {control_text}", (16, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 230, 120), 2)
    cv2.putText(frame, f"FPS: {fps:0.1f}   q: salir   D+F/c: control on/off", (16, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)


def append_log(log_file: Path | None, text: str) -> None:
    if not log_file:
        return
    log_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%H:%M:%S")
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {text}\n")


def main() -> int:
    args = parse_args()
    config = apply_profile(load_config())
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.02

    camera = args.camera if args.camera is not None else int(config.get("camera", 0))
    runtime_state = load_state()
    control_start = bool(args.control or runtime_state.get("control_enabled", config.get("control_enabled_on_start", False)))
    scroll_amount = args.scroll_amount if args.scroll_amount is not None else int(get_nested(config, ("scroll", "speed"), 2112))
    args.scroll_amount = scroll_amount
    args.cooldown = float(get_nested(config, ("zoom", "cooldown"), args.cooldown))
    args.mirror = bool(config.get("mirror", args.mirror))

    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        print(f"No se pudo abrir la camara {camera}. Prueba con otra camara desde la configuracion.")
        return 1

    mp_hands = mp.solutions.hands
    mp_pose = mp.solutions.pose
    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils
    mp_styles = mp.solutions.drawing_styles
    set_control_enabled(control_start)
    control_state = ControlState(enabled=control_start)

    last_frame_at = time.monotonic()
    last_config_at = 0.0
    last_logged_at = 0.0
    last_logged_status = ""
    fps = 0.0
    append_log(args.log_file, f"START camera={camera} control={control_start}")

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=1,
        min_detection_confidence=float(get_nested(config, ("gesture", "min_detection_confidence"), 0.65)),
        min_tracking_confidence=float(get_nested(config, ("gesture", "min_tracking_confidence"), 0.60)),
    ) as hands, mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.55,
        min_tracking_confidence=0.55,
    ) as face_mesh, mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        min_detection_confidence=0.55,
        min_tracking_confidence=0.55,
    ) as pose:
        while True:
            now = time.monotonic()
            if now - last_config_at > 0.5:
                config = apply_profile(load_config())
                runtime_state = load_state()
                control_state.enabled = bool(runtime_state.get("control_enabled", control_state.enabled))
                args.mirror = bool(config.get("mirror", args.mirror))
                last_config_at = now

            ok, frame = cap.read()
            if not ok:
                print("No se pudo leer frame de camara.")
                break

            if args.mirror:
                frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            mode = str(config.get("vision_mode", "GESTURE")).upper()
            face_summary = {
                "detected": False,
                "center": None,
                "movement": "still",
                "smile": False,
                "left_eye": "unknown",
                "right_eye": "unknown",
                "gaze": "unknown",
                "nose": None,
            }
            body_summary = {
                "detected": False,
                "motion": "idle",
                "center_of_gravity": None,
                "trajectory_points": 0,
                "digital_twin": False,
            }
            results = None
            pose_results = None
            face_results = None
            if mode == "BODY":
                pose_results = pose.process(rgb)
            else:
                if mode == "GESTURE":
                    results = hands.process(rgb)
                if get_nested(config, ("features", "face"), True) and get_nested(config, ("face", "enabled"), True):
                    face_results = face_mesh.process(rgb)
            rgb.flags.writeable = True

            gesture_result = classify_gesture(None)
            detected_hands = []
            hand_side = "unknown"
            palm_facing = "unknown"
            if face_results and face_results.multi_face_landmarks:
                face_summary = process_face(frame, face_results.multi_face_landmarks[0], control_state, config)
            if mode == "BODY":
                frame, body_summary = process_body(frame, pose_results.pose_landmarks if pose_results else None, control_state, config, now, mp_pose)
            if results and results.multi_hand_landmarks:
                handedness_list = results.multi_handedness or []
                for hand_index, hand_landmarks in enumerate(results.multi_hand_landmarks[:2]):
                    classified = classify_gesture(landmarks_to_points(hand_landmarks))
                    detected_hands.append((hand_landmarks, classified))
                    label = None
                    if hand_index < len(handedness_list):
                        label = handedness_list[hand_index].classification[0].label
                    if hand_index == 0:
                        hand_side = label or "unknown"
                        palm_facing = hand_orientation(hand_landmarks, label)
                    update_trajectories(control_state, hand_index, hand_landmarks, config, now)
                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_styles.get_default_hand_landmarks_style(),
                        mp_styles.get_default_hand_connections_style(),
                    )
                    draw_pinch_marker(frame, hand_landmarks, classified.pinch_distance)
                    draw_finger_rays(frame, hand_landmarks)
                gesture_result = detected_hands[0][1]
                stable = stabilize_gesture(control_state, gesture_result.gesture, config)
                if stable != gesture_result.gesture:
                    gesture_result = type(gesture_result)(stable, gesture_result.confidence, gesture_result.pinch_distance, gesture_result.hand_size)

            now = time.monotonic()
            elapsed = max(now - last_frame_at, 0.001)
            hotkey_changed = update_hotkey_toggle(control_state, str(config.get("control_hotkey", "D+F")))
            if mode == "BODY":
                control_text = f"BODY {body_summary.get('motion', 'idle')}"
            elif mode == "FACE":
                control_text = f"FACE gaze {face_summary.get('gaze', 'unknown')}"
            else:
                control_text = maybe_control_screen(
                    control_state,
                    gesture_result.gesture,
                    gesture_result.pinch_distance,
                    gesture_result.hand_size,
                    args,
                    config,
                    elapsed,
                )
                if control_state.enabled and detected_hands:
                    air_mouse_text = update_air_mouse(control_state, detected_hands[0][0], config)
                    if air_mouse_text:
                        control_text = air_mouse_text
                if control_state.enabled and len(detected_hands) >= 2:
                    two_hand_action = control_two_hands(control_state, detected_hands, config, elapsed)
                    if two_hand_action:
                        control_text = two_hand_action
            if hotkey_changed:
                control_text = "control ON" if control_state.enabled else "control OFF"
            status = f"hands={len(detected_hands)} gesture={gesture_result.gesture.value} confidence={gesture_result.confidence:0.2f} action={control_text}"
            if status != last_logged_status or now - last_logged_at > 1.0:
                append_log(args.log_file, status)
                last_logged_status = status
                last_logged_at = now

            last_frame_at = now
            fps = fps * 0.85 + (1.0 / elapsed) * 0.15

            handle_calibration_request(config, gesture_result, runtime_state)
            update_runtime_status({
                "gesture": gesture_result.gesture.value,
                "action": control_text,
                "vision_mode": mode,
                "hands": len(detected_hands),
                "face": face_summary,
                "body": body_summary,
                "fps": round(fps, 1),
                "control_enabled": control_state.enabled,
                "profile": str(load_config().get("current_profile", "navigation")),
                "hand_side": hand_side,
                "palm_facing": palm_facing,
                "pinch_distance": gesture_result.pinch_distance,
                "hand_size": gesture_result.hand_size,
                "trajectory_points": sum(len(v) for v in (control_state.trajectories or {}).values()),
            })
            draw_trajectories(frame, control_state)
            draw_overlay(frame, f"{mode} {gesture_result.gesture.value} hands={len(detected_hands)}", control_text, fps)
            write_latest_frame(control_state, frame, now)
            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                control_state.enabled = not control_state.enabled
                set_control_enabled(control_state.enabled)
                control_state.last_pinch_distance = None
                control_state.last_fist_size = None

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
