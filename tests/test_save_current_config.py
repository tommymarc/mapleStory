import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from src.ui.profession_config import KeyboardConfigDialog, ProfessionConfigStore
from src.ui.ui import MainWindow
from src.utils.common import load_yaml


class _ControllerStub:
    def enable_bot_viz(self):
        pass

    def disable_bot_viz(self):
        pass


class SaveCurrentConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_menu_saves_current_values_to_active_custom_file(self):
        window = MainWindow(_ControllerStub())
        menu_labels = [action.text() for action in window.button_settings.menu().actions()]
        self.assertIn("保存当前配置", menu_labels)
        self.assertIn("定时关机", menu_labels)
        self.assertEqual(window.tabs.count(), 6)
        self.assertNotIn(
            "定时关机",
            [window.tabs.tabText(index) for index in range(window.tabs.count())],
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = os.path.join(directory, "saved.yaml")
            window.path_cfg_custom = output_path
            window.home_hp_percent.setValue(37)
            with patch.object(window.profession_store, "save"), patch.object(
                window.statusBar(), "showMessage"
            ), patch.object(
                __import__("src.ui.ui", fromlist=["QMessageBox"]).QMessageBox,
                "information",
            ):
                self.assertTrue(window.save_current_config())

            saved = load_yaml(output_path)
            self.assertEqual(saved["health_monitor"]["add_hp_percent"], 37)

        window.deleteLater()

    def test_keyboard_add_buff_creates_numbered_chips(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProfessionConfigStore(os.path.join(directory, "prof.yaml"))
            self.assertTrue(store.add("测试职业", "hybrid", {}))
            dialog = KeyboardConfigDialog(store, "测试职业")
            dialog._add_buff_chip()
            dialog._add_buff_chip()
            self.assertIn("buff1", dialog.function_buttons)
            self.assertIn("buff2", dialog.function_buttons)
            self.assertEqual(dialog.function_buttons["buff1"].text(), "BUFF1")
            self.assertEqual(dialog.function_buttons["buff2"].text(), "BUFF2")
            profile = store.get("测试职业")
            self.assertEqual(profile["intervals"]["buff1"], 60)
            plus_buff = [
                button
                for button in dialog.findChildren(QPushButton)
                if button.text().strip().lower() == "+ buff"
            ]
            self.assertEqual(len(plus_buff), 1)
            buff1_chip = dialog.function_buttons["buff1"].parent()
            self.assertIsNotNone(getattr(buff1_chip, "close_button", None))
            dialog.deleteLater()

    def test_keyboard_remove_buff_chip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProfessionConfigStore(os.path.join(directory, "prof.yaml"))
            self.assertTrue(store.add("测试职业", "hybrid", {}))
            dialog = KeyboardConfigDialog(store, "测试职业")
            dialog._add_buff_chip()
            dialog._add_buff_chip()
            profile = store.get("测试职业")
            profile.setdefault("bindings", {})["buff1"] = "v"
            dialog._remove_extra_buff("buff1")
            self.assertNotIn("buff1", dialog.function_buttons)
            self.assertIn("buff2", dialog.function_buttons)
            self.assertNotIn("buff1", profile.get("bindings", {}))
            self.assertNotIn("buff1", profile.get("intervals", {}))
            self.assertIn("buff2", profile.get("intervals", {}))
            plus_buff = [
                button
                for button in dialog.findChildren(QPushButton)
                if button.text().strip().lower() == "+ buff"
            ]
            self.assertEqual(len(plus_buff), 1)
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
