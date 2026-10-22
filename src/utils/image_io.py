"""Unicode-safe OpenCV image file helpers."""

import os

import cv2
import numpy as np


def read_image(path, flags=cv2.IMREAD_COLOR):
    """Read an image without passing a potentially non-ASCII path to OpenCV.

    Some Windows OpenCV builds cannot open paths containing Chinese characters
    with ``cv2.imread``. Python and NumPy support those paths, so read the bytes
    first and let OpenCV decode the in-memory buffer instead.
    """
    try:
        encoded = np.fromfile(os.fspath(path), dtype=np.uint8)
    except (OSError, ValueError):
        return None

    if encoded.size == 0:
        return None
    return cv2.imdecode(encoded, flags)


def write_image(path, image, extension=None):
    """Write an OpenCV image to a Unicode path on Windows."""
    if image is None:
        return False
    extension = extension or os.path.splitext(os.fspath(path))[1] or ".png"
    ok, encoded = cv2.imencode(extension, image)
    if not ok:
        return False
    try:
        encoded.tofile(os.fspath(path))
    except OSError:
        return False
    return True
