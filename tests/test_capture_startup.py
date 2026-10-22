import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
from src.input.GameWindowCapturor import GameWindowCapturor


class CaptureStartupTests(unittest.TestCase):
    def test_windows_capture_callback_keeps_owned_frame_copy(self):
        capturor = GameWindowCapturor.__new__(GameWindowCapturor)
        capturor.frame = None
        capturor.lock = threading.Lock()
        capturor.frame_ready = threading.Event()
        capturor.t_last_run = 0.0
        capturor.fps = 0

        source = np.full((3, 4, 4), 17, dtype=np.uint8)
        frame = SimpleNamespace(frame_buffer=source)
        capturor.on_frame_arrived(frame, None)
        source[:] = 99

        self.assertTrue(capturor.frame_ready.is_set())
        self.assertTrue(np.all(capturor.frame == 17))

    def test_outer_window_frame_is_cropped_to_real_client_area(self):
        frame = np.zeros((759, 1296, 4), dtype=np.uint8)
        frame[31:751, 8:1288] = 73

        cropped = GameWindowCapturor.crop_frame_to_client_geometry(
            frame,
            window_rect=(545, 232, 1841, 991),
            client_origin=(553, 263),
            client_size=(1280, 720),
        )

        self.assertEqual(cropped.shape, (720, 1280, 4))
        self.assertTrue(np.all(cropped == 73))

    def test_wgc_visible_bounds_are_preferred_over_invisible_outer_border(self):
        frame = np.zeros((752, 1282, 4), dtype=np.uint8)
        frame[31:751, 1:1281] = 91
        window_rect = (545, 232, 1841, 991)
        visible_rect = (552, 232, 1834, 984)

        capture_bounds = GameWindowCapturor.select_capture_bounds(
            frame.shape[:2], window_rect, visible_rect
        )
        cropped = GameWindowCapturor.crop_frame_to_client_geometry(
            frame,
            capture_bounds,
            client_origin=(553, 263),
            client_size=(1280, 720),
        )

        self.assertEqual(capture_bounds, visible_rect)
        self.assertEqual(cropped.shape, (720, 1280, 4))
        self.assertTrue(np.all(cropped == 91))

    def test_keyboard_is_not_started_when_both_capture_backends_fail(self):
        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.args = SimpleNamespace(test_image="")
        bot.cfg = {}
        bot.capture = None
        bot._wait_for_valid_game_frame = MagicMock(return_value=None)

        first_capture = MagicMock()
        fallback_capture = MagicMock()
        with (
            patch(
                "src.engine.MapleStoryAutoLevelUp.GameWindowCapturor",
                side_effect=[first_capture, fallback_capture],
            ) as capture_type,
            patch("src.engine.MapleStoryAutoLevelUp.KeyBoardController") as keyboard_type,
            patch("src.engine.MapleStoryAutoLevelUp.is_mac", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "控制线程未启动"):
                bot.start()

        self.assertEqual(capture_type.call_count, 2)
        capture_type.assert_any_call({}, backend="mss")
        first_capture.stop.assert_called_once()
        fallback_capture.stop.assert_called_once()
        keyboard_type.assert_not_called()


if __name__ == "__main__":
    unittest.main()
