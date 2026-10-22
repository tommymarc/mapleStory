import unittest
from unittest.mock import call, patch

from src.input import KeyBoardController as keyboard_controller


class KeyboardJitterTests(unittest.TestCase):
    def setUp(self):
        keyboard_controller._pressed_keys.clear()

    def tearDown(self):
        keyboard_controller._pressed_keys.clear()

    def test_press_key_jitters_key_down_and_held_duration(self):
        with patch.object(
            keyboard_controller.random, "uniform", side_effect=[0.04, 0.07]
        ) as uniform, patch.object(
            keyboard_controller.time, "sleep"
        ) as sleep, patch.object(
            keyboard_controller.keyboard_output, "keyDown"
        ) as backend_down, patch.object(
            keyboard_controller.keyboard_output, "keyUp"
        ) as backend_up:
            keyboard_controller.press_key("a", duration=0.05)

        self.assertEqual(
            uniform.call_args_list,
            [call(0.01, 0.08), call(0.01, 0.08)],
        )
        self.assertEqual(sleep.call_args_list, [call(0.04), call(0.05), call(0.07)])
        backend_down.assert_called_once_with("a")
        backend_up.assert_called_once_with("a")

    def test_hotkey_jitters_each_down_and_up_event(self):
        with patch.object(
            keyboard_controller.random,
            "uniform",
            side_effect=[0.01, 0.02, 0.03, 0.04],
        ), patch.object(
            keyboard_controller.time, "sleep"
        ) as sleep, patch.object(
            keyboard_controller.keyboard_output, "keyDown"
        ) as backend_down, patch.object(
            keyboard_controller.keyboard_output, "keyUp"
        ) as backend_up:
            keyboard_controller.press_hotkey("ctrl", "s", duration=0.08)

        self.assertEqual(
            sleep.call_args_list,
            [call(0.01), call(0.02), call(0.08), call(0.03), call(0.04)],
        )
        self.assertEqual(backend_down.call_args_list, [call("ctrl"), call("s")])
        self.assertEqual(backend_up.call_args_list, [call("s"), call("ctrl")])

    def test_held_direction_does_not_repeat_key_down_each_frame(self):
        with patch.object(
            keyboard_controller.random, "uniform", return_value=0.02
        ) as uniform, patch.object(
            keyboard_controller.time, "sleep"
        ), patch.object(
            keyboard_controller.keyboard_output, "keyDown"
        ) as backend_down:
            self.assertTrue(keyboard_controller.key_down("left"))
            self.assertFalse(keyboard_controller.key_down("left"))

        uniform.assert_called_once_with(0.01, 0.08)
        backend_down.assert_called_once_with("left")

    def test_direction_release_jitters_held_duration(self):
        keyboard_controller._pressed_keys.add("left")
        with patch.object(
            keyboard_controller.random, "uniform", return_value=0.06
        ), patch.object(
            keyboard_controller.time, "sleep"
        ) as sleep, patch.object(
            keyboard_controller.keyboard_output, "keyUp"
        ) as backend_up:
            self.assertTrue(keyboard_controller.key_up("left"))

        sleep.assert_called_once_with(0.06)
        backend_up.assert_called_once_with("left")
        self.assertNotIn("left", keyboard_controller._pressed_keys)

    def test_empty_key_does_not_wait(self):
        with patch.object(
            keyboard_controller.random, "uniform"
        ) as uniform, patch.object(keyboard_controller.time, "sleep") as sleep:
            keyboard_controller.press_key("")

        uniform.assert_not_called()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
