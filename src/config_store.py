from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config" / "default_config.json"
USER_CONFIG_PATH = ROOT / "config" / "gesture_config.json"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_default_config() -> dict[str, Any]:
    with DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_config() -> dict[str, Any]:
    default = load_default_config()
    if not USER_CONFIG_PATH.exists():
        save_config(default)
        return default

    try:
        with USER_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            user_config = json.load(handle)
    except json.JSONDecodeError:
        return default

    return deep_merge(default, user_config)


def save_config(config: dict[str, Any]) -> None:
    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")

