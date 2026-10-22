# -*- coding: utf-8 -*-
"""Harden save buttons so failures surface; fix empty custom yaml; setdefault UI cfg keys."""
from pathlib import Path
import py_compile

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
UI = ROOT / "src" / "ui" / "ui.py"
PROF = ROOT / "src" / "ui" / "profession_config.py"

# 1) Fix empty custom yaml files
for rel in ("config/config_custom.yaml", "dist/config/config_custom.yaml"):
    p = ROOT / rel
    if p.exists() and p.stat().st_size == 0:
        p.write_text("{}\n", encoding="utf-8")
        print("fixed empty", rel)
    elif not p.exists():
        p.write_text("{}\n", encoding="utf-8")
        print("created", rel)
    else:
        print("ok", rel, p.stat().st_size)

ui = UI.read_text(encoding="utf-8")

OLD_UPDATE = '''    def update_cfg_from_main_ui(self):
        '''
        Collect setting from UI framework
        '''
        self.cfg["bot"]["mode"] = self.bot_mode.currentData() or "normal"
        if self.cfg["bot"]["mode"] == "aux":
            # Start/save in assist mode always uses classic heal (not multi-press).
            self._force_disable_potion_profile_for_assist(persist=False)

        selected_profession = self.profession_combo.currentData() or ""
        self.profession_store.apply_to_cfg(
            self.cfg, selected_profession, self.cfg_fallback
        )

        window_title = self.window_title_edit.text().strip()
        if window_title:
            self.cfg["game_window"]["title"] = window_title

        self.cfg["health_monitor"]["add_hp_percent"] = self.home_hp_percent.value()
        self.cfg["health_monitor"]["add_mp_percent"] = self.home_mp_percent.value()

        attack_type = self.cfg["bot"].get("attack", "directional")
        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"
        self.cfg[section_name]["range_x"] = self.home_attack_range_x.value()
        self.cfg[section_name]["range_y"] = self.home_attack_range_y.value()
        self.cfg[section_name]["cooldown"] = self.home_attack_cooldown.value() / 10.0
        hybrid_cfg = self.cfg.setdefault("hybrid_attack", {})
        hybrid_cfg["aoe_trigger_count"] = self.home_aoe_trigger_count.value()
        hybrid_cfg["aoe_cooldown"] = self.home_aoe_cooldown.value() / 10.0
        # Map selection
        self.cfg["bot"]["map"] = self.selected_map

        if hasattr(self, "chk_shutdown_timed"):
            self._collect_shutdown_monitor_from_ui()
'''

NEW_UPDATE = '''    def update_cfg_from_main_ui(self):
        '''
        Collect setting from UI framework
        '''
        bot = self.cfg.setdefault("bot", {})
        bot["mode"] = self.bot_mode.currentData() or "normal"
        if bot.get("mode") == "aux":
            # Start/save in assist mode always uses classic heal (not multi-press).
            self._force_disable_potion_profile_for_assist(persist=False)

        selected_profession = self.profession_combo.currentData() or ""
        self.profession_store.apply_to_cfg(
            self.cfg, selected_profession, self.cfg_fallback
        )

        window_title = self.window_title_edit.text().strip()
        if window_title:
            self.cfg.setdefault("game_window", {})["title"] = window_title

        hm = self.cfg.setdefault("health_monitor", {})
        hm["add_hp_percent"] = self.home_hp_percent.value()
        hm["add_mp_percent"] = self.home_mp_percent.value()

        attack_type = bot.get("attack", "directional")
        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"
        section = self.cfg.setdefault(section_name, {})
        section["range_x"] = self.home_attack_range_x.value()
        section["range_y"] = self.home_attack_range_y.value()
        section["cooldown"] = self.home_attack_cooldown.value() / 10.0
        hybrid_cfg = self.cfg.setdefault("hybrid_attack", {})
        hybrid_cfg["aoe_trigger_count"] = self.home_aoe_trigger_count.value()
        hybrid_cfg["aoe_cooldown"] = self.home_aoe_cooldown.value() / 10.0
        # Map selection
        bot["map"] = self.selected_map

        if hasattr(self, "chk_shutdown_timed"):
            self._collect_shutdown_monitor_from_ui()
'''

if OLD_UPDATE not in ui:
    raise SystemExit("update_cfg_from_main_ui block not found")
ui = ui.replace(OLD_UPDATE, NEW_UPDATE, 1)
print("patched update_cfg_from_main_ui")

OLD_SAVE = '''    def save_current_config(self):
        """Save the visible settings immediately from the Settings menu."""
        try:
            path = self._write_current_config()
        except (OSError, ValueError) as error:
            logger.error(f"[UI] Save current config failed: {error}")
            QMessageBox.warning(self, "保存失败", str(error))
            self.statusBar().showMessage("状态：配置保存失败")
            return False
'''

# Use ASCII-safe match - Chinese may be garbled in file as UTF-8 fine
# Read actual bytes of save_current_config from file
start = ui.find("    def save_current_config(self):")
if start < 0:
    raise SystemExit("save_current_config not found")
end = ui.find("\n    def ", start + 1)
block = ui[start:end]
print("OLD SAVE BLOCK:\n", block[:500])

NEW_SAVE = '''    def save_current_config(self):
        """Save the visible settings immediately from the Settings menu."""
        try:
            path = self._write_current_config()
        except Exception as error:
            logger.exception(f"[UI] Save current config failed: {error}")
            QMessageBox.warning(self, "保存失败", str(error))
            self.statusBar().showMessage("状态：配置保存失败")
            return False

        logger.info(f"[UI] Current config saved: {path}")
        self.statusBar().showMessage(f"状态：当前配置已保存到 {path}")
        QMessageBox.information(
            self,
            "保存成功",
            f"当前配置已保存到：\\n{path}",
        )
        return True
'''

# Replace entire function carefully - find return True end
# Prefer surgically change except clause only
OLD_EXCEPT = '''        except (OSError, ValueError) as error:
            logger.error(f"[UI] Save current config failed: {error}")
'''
NEW_EXCEPT = '''        except Exception as error:
            logger.exception(f"[UI] Save current config failed: {error}")
'''
if OLD_EXCEPT not in ui:
    # try already patched
    if "except Exception as error:" in block and "Save current config failed" in block:
        print("save_current_config except already broad")
    else:
        raise SystemExit("save except block not found")
else:
    ui = ui.replace(OLD_EXCEPT, NEW_EXCEPT, 1)
    print("patched save_current_config except")

UI.write_text(ui, encoding="utf-8")
py_compile.compile(str(UI), doraise=True)
print("ui.py OK")

# Harden KeyboardConfigDialog._save
prof = PROF.read_text(encoding="utf-8")
OLD_PSAVE = '''    def _save(self):
        if self.profession_combo.currentText():
            self.store.select(self.profession_combo.currentText())
        self.store.save()
        self.profiles_changed.emit()
        QMessageBox.information(self, "保存配置", "职业键位配置已保存。")
'''
NEW_PSAVE = '''    def _save(self):
        try:
            if self.profession_combo.currentText():
                self.store.select(self.profession_combo.currentText())
            self.store.save()
            self.profiles_changed.emit()
        except Exception as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return
        QMessageBox.information(self, "保存配置", "职业键位配置已保存。")
'''
if OLD_PSAVE not in prof:
    if "保存失败" in prof and "def _save" in prof:
        print("profession _save already hardened?")
    else:
        # fuzzy: replace body
        import re
        m = re.search(r"    def _save\(self\):\n(?:.*\n)*?        QMessageBox\.information\(self, \"保存配置\".*\n", prof)
        if not m:
            raise SystemExit("profession _save not found")
        prof = prof[:m.start()] + NEW_PSAVE + prof[m.end():]
        print("profession _save replaced via regex")
else:
    prof = prof.replace(OLD_PSAVE, NEW_PSAVE, 1)
    print("profession _save patched")

PROF.write_text(prof, encoding="utf-8")
py_compile.compile(str(PROF), doraise=True)
print("profession_config OK")
print("DONE")
