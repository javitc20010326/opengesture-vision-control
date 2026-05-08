from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config_store import ROOT


STATE_PATH = ROOT / "config" / "runtime_state.json"

DEFAULT_STATE: dict[str, Any] = {
    "control_enabled": False,
    "calibration_request": None,
    "runtime": {
        "gesture": "NO_HAND",
        "action": "waiting",
        "vision_mode": "GESTURE",
        "hands": 0,
        "face": {
            "detected": False,
            "center": None,
            "movement": "still",
            "smile": False,
            "left_eye": "unknown",
            "right_eye": "unknown",
            "gaze": "unknown",
            "nose": None,
        },
        "body": {
            "detected": False,
            "motion": "idle",
            "center_of_gravity": None,
            "trajectory_points": 0,
            "digital_twin": False,
        },
        "fps": 0.0,
        "control_enabled": False,
        "profile": "navigation",
        "hand_side": "unknown",
        "palm_facing": "unknown",
        "pinch_distance": None,
        "hand_size": None,
        "trajectory_points": 0
    }
}


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        save_state(DEFAULT_STATE)
        return dict(DEFAULT_STATE)
    try:
        with STATE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError:
        data = {}
    return {**DEFAULT_STATE, **data}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump({**DEFAULT_STATE, **state}, handle, indent=2)
        handle.write("\n")


def set_control_enabled(enabled: bool) -> dict[str, Any]:
    state = load_state()
    state["control_enabled"] = bool(enabled)
    save_state(state)
    return state


def toggle_control_enabled() -> dict[str, Any]:
    state = load_state()
    state["control_enabled"] = not bool(state.get("control_enabled", False))
    save_state(state)
    return state


def set_calibration_request(label: str | None) -> dict[str, Any]:
    state = load_state()
    state["calibration_request"] = label
    save_state(state)
    return state


def update_runtime_status(runtime: dict[str, Any]) -> dict[str, Any]:
    state = load_state()
    state["runtime"] = {**DEFAULT_STATE["runtime"], **runtime}
    save_state(state)
    return state
