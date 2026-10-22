import threading
import unittest

import cv2
import numpy as np

from src.engine.HealthMonitor import HealthMonitor


class HealthMonitorTests(unittest.TestCase):
    def test_detects_current_1280x720_status_bar_geometry(self):
        ui_frame = np.zeros((90, 1296, 3), dtype=np.uint8)
        boxes = [(476, 73, 102, 15), (579, 73, 102, 15), (686, 73, 111, 15)]
        colors = [(0, 0, 255), (255, 0, 0), (0, 255, 255)]
        for (x, y, w, h), color in zip(boxes, colors):
            cv2.rectangle(ui_frame, (x, y), (x + w - 1, y + h - 1), (255, 255, 255), 1)
            cv2.rectangle(ui_frame, (x + 2, y + 2), (x + w // 2, y + h - 3), color, -1)

        monitor = HealthMonitor.__new__(HealthMonitor)
        monitor.img_frame = ui_frame
        monitor.frame_lock = threading.Lock()
        monitor.loc_size_bars = [(0, 0, 0, 0)] * 3

        hp, mp, exp = monitor.get_hp_mp_exp_percent()

        self.assertEqual(monitor.loc_size_bars, boxes)
        self.assertTrue(all(value is not None for value in (hp, mp, exp)))


if __name__ == "__main__":
    unittest.main()
