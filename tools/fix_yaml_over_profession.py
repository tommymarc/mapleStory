# -*- coding: utf-8 -*-
"""After load, YAML home values must win over 剑客 profession overrides."""
from pathlib import Path
import py_compile
import shutil
import time

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
UI = ROOT / "src" / "ui" / "ui.py"
MARKER = "YAML_WINS_OVER_PROFESSION_ON_LOAD_V1"

def main():
    ui = UI.read_text(encoding="utf-8")
    if MARKER in ui:
        print("already patched")
        py_compile.compile(str(UI), doraise=True)
        return

    bak = UI.with_suffix(UI.suffix + f".bak_yaml_prof_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(UI, bak)
    print("backup", bak)

    old_assign = """            self.cfg_fallback = override_cfg(copy.deepcopy(self.cfg_base), custom_cfg)
            self.cfg = copy.deepcopy(self.cfg_fallback)
            self.path_cfg_custom = path
"""
    new_assign = """            self.cfg_fallback = override_cfg(copy.deepcopy(self.cfg_base), custom_cfg)
            self.cfg = copy.deepcopy(self.cfg_fallback)
            self.path_cfg_custom = path
            # Keep raw custom so apply_config_to_ui can re-layer it over profession overrides.
            self._loaded_custom_cfg = copy.deepcopy(custom_cfg)
"""
    if old_assign not in ui:
        raise SystemExit("load assign block not found")
    ui = ui.replace(old_assign, new_assign, 1)
    print("patched: store _loaded_custom_cfg")

    old_apply_call = """        # Re-apply config to UI
        try:
            self.apply_config_to_ui()
        except Exception as error:
            logger.exception(f"[UI] apply_config_to_ui after load failed: {error}")
"""
    new_apply_call = """        # Re-apply config to UI (YAML wins over profession combat overrides)
        try:
            self.apply_config_to_ui(prefer_loaded_custom=True)
        except Exception as error:
            logger.exception(f"[UI] apply_config_to_ui after load failed: {error}")
"""
    if old_apply_call not in ui:
        raise SystemExit("apply call after load not found")
    ui = ui.replace(old_apply_call, new_apply_call, 1)
    print("patched: load prefer_loaded_custom")

    old_apply_def = """    def apply_config_to_ui(self):
        selected_profession = self.profession_combo.currentData() or ""
        self.profession_store.apply_to_cfg(
            self.cfg, selected_profession, self.cfg_fallback
        )

        self.window_title_edit.setText(self.cfg["game_window"].get("title", ""))
"""
    new_apply_def = (
        "    def apply_config_to_ui(self, prefer_loaded_custom=False):\n"
        "        # " + MARKER + "\n"
        "        selected_profession = self.profession_combo.currentData() or \"\"\n"
        "        self.profession_store.apply_to_cfg(\n"
        "            self.cfg, selected_profession, self.cfg_fallback\n"
        "        )\n"
        "        # Loading a YAML must override 剑客 homepage combat fields.\n"
        "        # Profession select still applies overrides via on_profession_selected.\n"
        "        if prefer_loaded_custom:\n"
        "            custom = getattr(self, \"_loaded_custom_cfg\", None)\n"
        "            if isinstance(custom, dict) and custom:\n"
        "                override_cfg(self.cfg, copy.deepcopy(custom))\n"
        "\n"
        "        self.window_title_edit.setText(self.cfg[\"game_window\"].get(\"title\", \"\"))\n"
    )
    if old_apply_def not in ui:
        raise SystemExit("apply_config_to_ui def not found")
    ui = ui.replace(old_apply_def, new_apply_def, 1)
    print("patched: apply_config_to_ui")

    UI.write_text(ui, encoding="utf-8")
    py_compile.compile(str(UI), doraise=True)
    print("wrote", UI)
    print("DONE")

if __name__ == "__main__":
    main()
