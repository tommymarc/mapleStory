import os
import tempfile
import unittest

import cv2
import numpy as np

from src.utils.common import screenshot
from src.utils.image_io import read_image


class ImageIoTests(unittest.TestCase):
    def test_read_image_supports_chinese_path(self):
        image = np.zeros((7, 9, 4), dtype=np.uint8)
        image[2:6, 3:8] = (10, 20, 30, 255)
        encoded_ok, encoded = cv2.imencode(".png", image)
        self.assertTrue(encoded_ok)

        with tempfile.TemporaryDirectory() as temp_dir:
            unicode_dir = os.path.join(temp_dir, "斧木妖")
            os.makedirs(unicode_dir)
            path = os.path.join(unicode_dir, "移动_0.png")
            with open(path, "wb") as image_file:
                image_file.write(encoded.tobytes())

            decoded = read_image(path, cv2.IMREAD_UNCHANGED)

        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.shape, image.shape)
        self.assertTrue(np.array_equal(decoded, image))

    def test_screenshot_writes_from_a_chinese_working_directory(self):
        image = np.full((7, 9, 3), 127, dtype=np.uint8)
        original_directory = os.getcwd()

        with tempfile.TemporaryDirectory() as temp_dir:
            unicode_dir = os.path.join(temp_dir, "应用管理")
            os.makedirs(unicode_dir)
            try:
                os.chdir(unicode_dir)
                path = screenshot(image, "unicode_path")
                self.assertIsNotNone(path)
                self.assertTrue(os.path.isfile(path))
                decoded = read_image(path)
            finally:
                os.chdir(original_directory)

        self.assertTrue(np.array_equal(decoded, image))


if __name__ == "__main__":
    unittest.main()
