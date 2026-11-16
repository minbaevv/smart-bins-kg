"""Fill-level classifier.

Two modes are supported (``CV_MODE`` env var):

* ``heuristic`` — placeholder baseline: dark pixels inside the ROI are treated
  as bin content, so a mostly dark frame means the bin is full. This keeps the
  whole pipeline working until a trained CNN exists and is honest about being
  a baseline, not a model.
* ``stub`` — always returns ``needs_review`` with zero confidence. Useful for a
  UI/demo that must not show fabricated statuses.

Replacing this with the real MobileNetV3/ResNet18 is a one-function change:
``predict()`` already receives raw image bytes and returns the same Prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from PIL import Image

from ..config import settings
from .preprocessing import crop_roi, load_rgb, resize_roi

GREEN_MAX = 0.28
YELLOW_MAX = 0.55
DARK_PIXEL_THRESHOLD = 60
REVIEW_CONFIDENCE = 0.5


@dataclass(frozen=True)
class Prediction:
    status: str
    confidence: float
    fill_ratio: float


def status_for_ratio(fill_ratio: float) -> str:
    """Map fill ratio (0..1) to the traffic-light status."""
    if fill_ratio < GREEN_MAX:
        return "green"
    if fill_ratio < YELLOW_MAX:
        return "yellow"
    return "red"


def confidence_for_ratio(fill_ratio: float) -> float:
    """Distance to the nearest decision boundary, squashed into 0.55..0.95."""
    distance = min(abs(fill_ratio - GREEN_MAX), abs(fill_ratio - YELLOW_MAX))
    return round(min(0.95, 0.55 + 1.4 * distance), 2)


def classify_image(image: Image.Image) -> Prediction:
    roi = resize_roi(crop_roi(image))
    gray = np.asarray(roi.convert("L"), dtype=np.uint8)
    fill_ratio = float((gray < DARK_PIXEL_THRESHOLD).mean())
    prediction = Prediction(
        status=status_for_ratio(fill_ratio),
        confidence=confidence_for_ratio(fill_ratio),
        fill_ratio=round(fill_ratio, 3),
    )
    if prediction.confidence < REVIEW_CONFIDENCE:
        return replace(prediction, status="needs_review")
    return prediction


def predict(data: bytes) -> Prediction:
    """Classify raw image bytes coming from a bin camera or the simulator."""
    if settings.cv_mode == "stub":
        return Prediction(status="needs_review", confidence=0.0, fill_ratio=0.0)
    return classify_image(load_rgb(data))
