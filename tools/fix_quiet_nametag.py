# -*- coding: utf-8 -*-
"""Don't popup missing nametag image on startup auto-bind."""
from pathlib import Path
import py_compile
import shutil
import time

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
UI = ROOT / "src" / "ui" / "ui.py"
MARKER = "QUIET_NAMETAG_AUTO_BIND_V1"

def main():
    ui = UI.read_text(encoding="utf-8")
    if MARKER in ui:
        print("already patched")
        py_compile.compile(str(UI), doraise=True)
        return

    bak = UI.with_suffix(UI.suffix + f".bak_quiet_nt_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(UI, bak)
    print("backup", bak)

    old_fn = '''    def apply_character_nametag(self, name):
        try:
            safe_name = safe_nametag_name(name)
        except ValueError as error:
            QMessageBox.warning(self, "选择失败", str(error))
            return False

        image_path = nametag_image_path(safe_name, self.nametag_dir)
        if not os.path.isfile(image_path):
            QMessageBox.warning(self, "选择失败", f"找不到角色名图片“{safe_name}”。")
            return False

        self.cfg.setdefault("nametag", {})["name"] = safe_name
        saved_layers = load_nametag_layers(safe_name, self.nametag_dir, default=None)
        if saved_layers is not None:
            self.cfg.setdefault("nametag", {})["layers"] = int(saved_layers)

        self.cfg["nametag"]["enable"] = True
        self.cfg.setdefault("player_detect", {})["mode"] = "auto"
        self.character_name_edit.setText(safe_name)
        logger.info(f"[UI] Selected character nametag image: {image_path}")
        self.statusBar().showMessage(f"状态：已选择角色名图片“{safe_name}”")
        return True
'''

    new_fn = '''    def apply_character_nametag(self, name, quiet=False):
        # ''' + MARKER + '''
        try:
            safe_name = safe_nametag_name(name)
        except ValueError as error:
            if not quiet:
                QMessageBox.warning(self, "选择失败", str(error))
            else:
                logger.warning(f"[UI] Invalid nametag name on auto-bind: {error}")
            return False

        image_path = nametag_image_path(safe_name, self.nametag_dir)
        if not os.path.isfile(image_path):
            # Keep the configured name in the field; only popup on manual pick.
            self.cfg.setdefault("nametag", {})["name"] = safe_name
            if hasattr(self, "character_name_edit"):
                self.character_name_edit.setText(safe_name)
            msg = f"找不到角色名图片“{safe_name}”（路径：{image_path}）"
            if quiet:
                logger.warning(f"[UI] {msg}")
                if hasattr(self, "statusBar"):
                    self.statusBar().showMessage(f"状态：{msg}", 5000)
            else:
                QMessageBox.warning(self, "选择失败", f"找不到角色名图片“{safe_name}”。")
            return False

        self.cfg.setdefault("nametag", {})["name"] = safe_name
        saved_layers = load_nametag_layers(safe_name, self.nametag_dir, default=None)
        if saved_layers is not None:
            self.cfg.setdefault("nametag", {})["layers"] = int(saved_layers)

        self.cfg["nametag"]["enable"] = True
        self.cfg.setdefault("player_detect", {})["mode"] = "auto"
        self.character_name_edit.setText(safe_name)
        logger.info(f"[UI] Selected character nametag image: {image_path}")
        self.statusBar().showMessage(f"状态：已选择角色名图片“{safe_name}”")
        return True
'''

    if old_fn not in ui:
        raise SystemExit("apply_character_nametag block not found")
    ui = ui.replace(old_fn, new_fn, 1)
    print("patched apply_character_nametag quiet=")

    # Auto-bind from apply_config_to_ui should be quiet
    old_call = '''        if selected_nametag:
            try:
                self.apply_character_nametag(selected_nametag)
            except Exception as err:
                logger.warning(f"[UI] apply_character_nametag after load failed: {err}")
'''
    new_call = '''        if selected_nametag:
            try:
                self.apply_character_nametag(selected_nametag, quiet=True)
            except Exception as err:
                logger.warning(f"[UI] apply_character_nametag after load failed: {err}")
'''
    if old_call not in ui:
        raise SystemExit("auto-bind call not found")
    ui = ui.replace(old_call, new_call, 1)
    print("patched apply_config_to_ui quiet call")

    UI.write_text(ui, encoding="utf-8")
    py_compile.compile(str(UI), doraise=True)
    print("DONE")

if __name__ == "__main__":
    main()
