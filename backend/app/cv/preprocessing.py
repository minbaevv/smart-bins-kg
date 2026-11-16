"""Image preprocessing shared by the baseline and the future CNN.

A camera on a bin is stationary, so we crop a fixed region of interest (ROI)
and resize it to the classifier input size. This part does not change when the
trained MobileNetV3/ResNet18 model replaces the heuristic baseline.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps

ROI_MARGIN = 0.15
INPUT_SIZE = (224, 224)


def load_rgb(data: bytes) -> Image.Image:
    """Decode raw image bytes, honour EXIF rotation and convert to RGB."""
    image = Image.open(BytesIO(data))
    image.load()
    return ImageOps.exif_transpose(image).convert("RGB")


def crop_roi(image: Image.Image, margin: float = ROI_MARGIN) -> Image.Image:
    """Crop the central region where the bin opening is expected."""
    width, height = image.size
    left = int(width * margin)
    top = int(height * margin)
    right = max(left + 1, int(width * (1 - margin)))
    bottom = max(top + 1, int(height * (1 - margin)))
    return image.crop((left, top, right, bottom))


def resize_roi(image: Image.Image, size: tuple[int, int] = INPUT_SIZE) -> Image.Image:
    """Resize to the model input size."""
    return image.resize(size, Image.BILINEAR)
