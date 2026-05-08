from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot
from typing import Mapping


class Gesture(str, Enum):
    NO_HAND = "NO_HAND"
    FIST = "FIST"
    OPEN_UP = "OPEN_UP"
    OPEN_DOWN = "OPEN_DOWN"
    OPEN_SIDE = "OPEN_SIDE"
    OPEN_LEFT = "OPEN_LEFT"
    OPEN_RIGHT = "OPEN_RIGHT"
    OPEN_UP_LEFT = "OPEN_UP_LEFT"
    OPEN_UP_RIGHT = "OPEN_UP_RIGHT"
    OPEN_DOWN_LEFT = "OPEN_DOWN_LEFT"
    OPEN_DOWN_RIGHT = "OPEN_DOWN_RIGHT"
    PINCH = "PINCH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class GestureResult:
    gesture: Gesture
    confidence: float
    pinch_distance: float | None = None
    hand_size: float | None = None


WRIST = 0
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_TIP = 20

FINGER_JOINTS = (
    (INDEX_MCP, INDEX_PIP, INDEX_TIP),
    (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP),
    (RING_MCP, RING_PIP, RING_TIP),
    (PINKY_MCP, PINKY_PIP, PINKY_TIP),
)


def distance(a: Point, b: Point) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def classify_gesture(landmarks: Mapping[int, Point] | None) -> GestureResult:
    if not landmarks:
        return GestureResult(Gesture.NO_HAND, 1.0)

    wrist = landmarks[WRIST]
    middle_mcp = landmarks[MIDDLE_MCP]
    middle_tip = landmarks[MIDDLE_TIP]
    index_tip = landmarks[INDEX_TIP]
    thumb_tip = landmarks[THUMB_TIP]

    min_x = min(point.x for point in landmarks.values())
    max_x = max(point.x for point in landmarks.values())
    min_y = min(point.y for point in landmarks.values())
    max_y = max(point.y for point in landmarks.values())
    hand_size = max(hypot(max_x - min_x, max_y - min_y), 0.001)
    palm_size = max(distance(wrist, middle_mcp), 0.001)
    pinch_distance = distance(index_tip, thumb_tip) / palm_size

    extended_count = 0
    extension_scores: list[float] = []
    for mcp_id, pip_id, tip_id in FINGER_JOINTS:
        mcp = landmarks[mcp_id]
        pip = landmarks[pip_id]
        tip = landmarks[tip_id]
        pip_ratio = distance(wrist, pip) / palm_size
        tip_ratio = distance(wrist, tip) / palm_size
        score = tip_ratio - pip_ratio
        extension_scores.append(score)
        if score > 0.18 and distance(tip, mcp) > palm_size * 0.45:
            extended_count += 1

    # Pinch only counts when the hand is otherwise open enough to avoid treating a fist as a zoom.
    if extended_count >= 2 and pinch_distance < 0.38:
        return GestureResult(Gesture.PINCH, 0.80, pinch_distance, hand_size)

    if extended_count <= 1 and sum(extension_scores) < 0.30:
        return GestureResult(Gesture.FIST, 0.85, pinch_distance, hand_size)

    if extended_count >= 3:
        vertical_delta = middle_tip.y - wrist.y
        horizontal_delta = middle_tip.x - wrist.x
        if abs(horizontal_delta) > 0.18 and abs(vertical_delta) > 0.18:
            if vertical_delta < 0 and horizontal_delta < 0:
                return GestureResult(Gesture.OPEN_UP_LEFT, 0.82, pinch_distance, hand_size)
            if vertical_delta < 0 and horizontal_delta > 0:
                return GestureResult(Gesture.OPEN_UP_RIGHT, 0.82, pinch_distance, hand_size)
            if vertical_delta > 0 and horizontal_delta < 0:
                return GestureResult(Gesture.OPEN_DOWN_LEFT, 0.82, pinch_distance, hand_size)
            return GestureResult(Gesture.OPEN_DOWN_RIGHT, 0.82, pinch_distance, hand_size)
        if abs(horizontal_delta) > 0.22 and abs(horizontal_delta) > abs(vertical_delta) * 1.25:
            if horizontal_delta > 0:
                return GestureResult(Gesture.OPEN_RIGHT, min(0.95, abs(horizontal_delta) + 0.55), pinch_distance, hand_size)
            return GestureResult(Gesture.OPEN_LEFT, min(0.95, abs(horizontal_delta) + 0.55), pinch_distance, hand_size)
        if vertical_delta < -0.18:
            return GestureResult(Gesture.OPEN_UP, min(0.95, abs(vertical_delta) + 0.55), pinch_distance, hand_size)
        if vertical_delta > 0.18:
            return GestureResult(Gesture.OPEN_DOWN, min(0.95, abs(vertical_delta) + 0.55), pinch_distance, hand_size)
        return GestureResult(Gesture.OPEN_SIDE, 0.65, pinch_distance, hand_size)

    return GestureResult(Gesture.UNKNOWN, 0.35, pinch_distance, hand_size)
