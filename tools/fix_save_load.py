# -*- coding: utf-8 -*-
"""
Fix save→load blanking attack params / nametag / home fields.

Root cause:
  1) update_cfg_from_main_ui never wrote nametag from character_name_edit.
  2) _write_current_config calls reset_profession_overrides BEFORE get_cfg_diff,
     which restores directional_attack / hybrid_attack from fallback and wipes
     the home-UI attack values that were just collected — so they never enter
     the sparse custom yaml. Loading config_custom.yaml (`{}` or thin) then
     shows empty 名片 + default/zero-looking attack fields.

Fix:
  - Persist nametag enable/name/layers from the home UI into cfg on save collect.
  - After reset_profession_overrides, re-apply home UI attack/hybrid/hp/map/mode
    + nametag onto cfg_to_save so they survive into the diff.
  - On apply_config_to_ui, re-select nametag via apply_character_nametag when name set.
  - Harden load_config with visible errors.
"""
from __future__ import annotations

from pathlib import Path
import py_compile
import shutil
import time

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
UI = ROOT / "src" / "ui" / "ui.py"

MARKER = "SAVE_LOAD_FULL_HOME_FIX_V1"


def _backup(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak_save_load_{stamp}")
    shutil.copy2(path, bak)
    print("backup:", bak)
    return bak


OLD_UPDATE_CFG = '''    def update_cfg_from_main_ui(self):
        \'\'\'
        Collect setting from UI framework
        \'\'\'
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

        attack_type = self.cfg.setdefault("bot", {}).get("attack", "directional")
        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"
        section = self.cfg.setdefault(section_name, {})
        section["range_x"] = self.home_attack_range_x.value()
        section["range_y"] = self.home_attack_range_y.value()
        section["cooldown"] = self.home_attack_cooldown.value() / 10.0
        hybrid_cfg = self.cfg.setdefault("hybrid_attack", {})
        hybrid_cfg["aoe_trigger_count"] = self.home_aoe_trigger_count.value()
        hybrid_cfg["aoe_cooldown"] = self.home_aoe_cooldown.value() / 10.0
        # Map selection
        self.cfg.setdefault("bot", {})["map"] = self.selected_map

        if hasattr(self, "chk_shutdown_timed"):
            self._collect_shutdown_monitor_from_ui()
'''

NEW_UPDATE_CFG = '''    def update_cfg_from_main_ui(self):
        \'\'\'
        Collect setting from UI framework
        \'\'\'
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

        attack_type = self.cfg.setdefault("bot", {}).get("attack", "directional")
        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"
        section = self.cfg.setdefault(section_name, {})
        section["range_x"] = self.home_attack_range_x.value()
        section["range_y"] = self.home_attack_range_y.value()
        section["cooldown"] = self.home_attack_cooldown.value() / 10.0
        hybrid_cfg = self.cfg.setdefault("hybrid_attack", {})
        hybrid_cfg["aoe_trigger_count"] = self.home_aoe_trigger_count.value()
        hybrid_cfg["aoe_cooldown"] = self.home_aoe_cooldown.value() / 10.0
        # Map selection
        self.cfg.setdefault("bot", {})["map"] = self.selected_map

        # Persist nametag / 名片 from home UI so save+load keep the selection.
        nametag_name = ""
        if hasattr(self, "character_name_edit"):
            nametag_name = (self.character_name_edit.text() or "").strip()
        nametag_cfg = self.cfg.setdefault("nametag", {})
        if nametag_name:
            nametag_cfg["name"] = nametag_name
            nametag_cfg["enable"] = True
            # Keep layers if already set; do not force a new default here.
            if "layers" not in nametag_cfg or nametag_cfg.get("layers") in (None, 0, ""):
                try:
                    from src.utils.nametag import load_nametag_layers
                    saved_layers = load_nametag_layers(
                        nametag_name,
                        getattr(self, "nametag_dir", None),
                        default=None,
                    )
                    if saved_layers is not None:
                        nametag_cfg["layers"] = int(saved_layers)
                except Exception:
                    pass
        elif not nametag_cfg.get("enable"):
            # Leave explicit disable alone; only clear name when UI shows empty
            # and enable is already false.
            nametag_cfg["name"] = nametag_cfg.get("name", "") or ""

        if hasattr(self, "chk_shutdown_timed"):
            self._collect_shutdown_monitor_from_ui()
'''

OLD_WRITE = '''    def _write_current_config(self):
        """Write the current UI state as a minimal custom-config override."""
        if "config_default.yaml" in self.path_cfg_custom:
            raise ValueError("默认配置文件不可覆盖，请先加载自定义配置文件。")

        self.update_cfg_from_main_ui()
        cfg_to_save = copy.deepcopy(self.cfg)
        reset_profession_overrides(cfg_to_save, self.cfg_fallback)
        cfg_diff = get_cfg_diff(self.cfg_base, cfg_to_save)
        save_yaml(cfg_diff, self.path_cfg_custom)
        self.profession_store.save()
        return self.path_cfg_custom
'''

NEW_WRITE = '''    def _write_current_config(self):
        """Write current UI state as a custom-config override (diff vs default).

        Profession keybinds stay in ProfessionConfigStore. Home-page attack /
        hybrid / HP / map / mode / nametag are re-applied AFTER
        reset_profession_overrides so they are not wiped from the diff.
        """
        # ''' + MARKER + '''
        if "config_default.yaml" in self.path_cfg_custom:
            raise ValueError("默认配置文件不可覆盖，请先加载自定义配置文件。")

        self.update_cfg_from_main_ui()
        cfg_to_save = copy.deepcopy(self.cfg)
        reset_profession_overrides(cfg_to_save, self.cfg_fallback)

        # Re-apply home UI values that reset_profession_overrides may restore
        # from fallback (directional_attack / hybrid_attack / bot.attack).
        bot = cfg_to_save.setdefault("bot", {})
        bot["mode"] = self.bot_mode.currentData() or bot.get("mode", "normal")
        bot["map"] = getattr(self, "selected_map", None) or bot.get("map", "")

        hm = cfg_to_save.setdefault("health_monitor", {})
        hm["add_hp_percent"] = self.home_hp_percent.value()
        hm["add_mp_percent"] = self.home_mp_percent.value()

        attack_type = bot.get("attack", "directional")
        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"
        section = cfg_to_save.setdefault(section_name, {})
        section["range_x"] = self.home_attack_range_x.value()
        section["range_y"] = self.home_attack_range_y.value()
        section["cooldown"] = self.home_attack_cooldown.value() / 10.0

        hybrid_cfg = cfg_to_save.setdefault("hybrid_attack", {})
        hybrid_cfg["aoe_trigger_count"] = self.home_aoe_trigger_count.value()
        hybrid_cfg["aoe_cooldown"] = self.home_aoe_cooldown.value() / 10.0

        nametag_name = ""
        if hasattr(self, "character_name_edit"):
            nametag_name = (self.character_name_edit.text() or "").strip()
        nametag_cfg = cfg_to_save.setdefault("nametag", {})
        if nametag_name:
            nametag_cfg["name"] = nametag_name
            nametag_cfg["enable"] = True
            live_layers = self.cfg.get("nametag", {}).get("layers")
            if live_layers not in (None, ""):
                nametag_cfg["layers"] = int(live_layers)

        cfg_diff = get_cfg_diff(self.cfg_base, cfg_to_save)
        save_yaml(cfg_diff, self.path_cfg_custom)
        self.profession_store.save()
        return self.path_cfg_custom
'''

OLD_APPLY_NAMETAG = '''        self.window_title_edit.setText(self.cfg["game_window"].get("title", ""))
        selected_nametag = (
            self.cfg["nametag"].get("name", "")
            if self.cfg["nametag"].get("enable") else ""
        )
        self.character_name_edit.setText(selected_nametag)
'''

NEW_APPLY_NAMETAG = '''        self.window_title_edit.setText(self.cfg["game_window"].get("title", ""))
        selected_nametag = (
            self.cfg.get("nametag", {}).get("name", "")
            if self.cfg.get("nametag", {}).get("enable") else ""
        )
        self.character_name_edit.setText(selected_nametag or "")
        # Re-bind nametag assets (layers / enable) when a name is present so
        # load does not leave 名片 looking empty despite yaml keys existing.
        if selected_nametag:
            try:
                self.apply_character_nametag(selected_nametag)
            except Exception as err:
                logger.warning(f"[UI] apply_character_nametag after load failed: {err}")
'''

OLD_LOAD_TRY = '''        # Load customized yaml
        try:
            custom_cfg = load_yaml(path)
            if not isinstance(custom_cfg, dict):
                custom_cfg = {}
            # These retired features may still exist in a config last saved by
            # v30/v31. Ignore them so closing this version cleans the stale data.
            custom_cfg.pop("auto_pickup", None)
            custom_cfg.pop("lie_detector", None)
            self.cfg_fallback = override_cfg(copy.deepcopy(self.cfg_base), custom_cfg)
            self.cfg = copy.deepcopy(self.cfg_fallback)
        except FileNotFoundError:
            logger.warning(f"[UI] Unable to find config file: {path}")
        else:
            self.path_cfg_custom = path

        # Re-apply config to UI
        self.apply_config_to_ui()
'''

NEW_LOAD_TRY = '''        # Load customized yaml (always merge with default base — never replace)
        try:
            custom_cfg = load_yaml(path)
            if not isinstance(custom_cfg, dict):
                custom_cfg = {}
            # These retired features may still exist in a config last saved by
            # v30/v31. Ignore them so closing this version cleans the stale data.
            custom_cfg.pop("auto_pickup", None)
            custom_cfg.pop("lie_detector", None)
            if not custom_cfg:
                logger.warning(
                    f"[UI] Config file is empty/{{}}: {path} — UI will show defaults only"
                )
            self.cfg_fallback = override_cfg(copy.deepcopy(self.cfg_base), custom_cfg)
            self.cfg = copy.deepcopy(self.cfg_fallback)
            self.path_cfg_custom = path
        except FileNotFoundError:
            logger.warning(f"[UI] Unable to find config file: {path}")
            error_label.setText(f"找不到配置文件：{path}")
            error_label.setVisible(True)
            return
        except Exception as error:
            logger.exception(f"[UI] Load config failed: {error}")
            error_label.setText(f"加载失败：{error}")
            error_label.setVisible(True)
            try:
                QMessageBox.warning(self, "加载失败", str(error))
            except Exception:
                pass
            return

        # Re-apply config to UI
        try:
            self.apply_config_to_ui()
        except Exception as error:
            logger.exception(f"[UI] apply_config_to_ui after load failed: {error}")
            error_label.setText(f"配置已读入但刷新界面失败：{error}")
            error_label.setVisible(True)
            try:
                QMessageBox.warning(self, "加载部分失败", str(error))
            except Exception:
                pass
'''


def main() -> None:
    if not UI.exists():
        raise SystemExit(f"missing ui.py: {UI}")

    ui = UI.read_text(encoding="utf-8")
    if MARKER in ui:
        print("already patched:", MARKER)
        py_compile.compile(str(UI), doraise=True)
        print("compile OK (idempotent)")
        return

    _backup(UI)

    changes = 0

    if OLD_UPDATE_CFG not in ui:
        # Tolerate slightly older wording without setdefault
        print("WARN: exact update_cfg_from_main_ui block not found; trying anchor insert")
        anchor = '        self.cfg.setdefault("bot", {})["map"] = self.selected_map\n'
        if anchor not in ui and 'self.cfg["bot"]["map"] = self.selected_map' in ui:
            anchor = '        self.cfg["bot"]["map"] = self.selected_map\n'
        nametag_block = '''
        # Persist nametag / 名片 from home UI so save+load keep the selection.
        nametag_name = ""
        if hasattr(self, "character_name_edit"):
            nametag_name = (self.character_name_edit.text() or "").strip()
        nametag_cfg = self.cfg.setdefault("nametag", {})
        if nametag_name:
            nametag_cfg["name"] = nametag_name
            nametag_cfg["enable"] = True
'''
        if anchor in ui and "Persist nametag / 名片 from home UI" not in ui:
            ui = ui.replace(anchor, anchor + nametag_block, 1)
            changes += 1
            print("patched: nametag persist (anchor)")
        else:
            print("ERROR: could not patch update_cfg_from_main_ui")
    else:
        ui = ui.replace(OLD_UPDATE_CFG, NEW_UPDATE_CFG, 1)
        changes += 1
        print("patched: update_cfg_from_main_ui")

    if OLD_WRITE not in ui:
        print("ERROR: _write_current_config block not found")
    else:
        ui = ui.replace(OLD_WRITE, NEW_WRITE, 1)
        changes += 1
        print("patched: _write_current_config")

    if OLD_APPLY_NAMETAG not in ui:
        print("ERROR: apply_config_to_ui nametag block not found")
    else:
        ui = ui.replace(OLD_APPLY_NAMETAG, NEW_APPLY_NAMETAG, 1)
        changes += 1
        print("patched: apply_config_to_ui nametag")

    if OLD_LOAD_TRY not in ui:
        print("ERROR: load_config try block not found")
    else:
        ui = ui.replace(OLD_LOAD_TRY, NEW_LOAD_TRY, 1)
        changes += 1
        print("patched: load_config harden")

    if changes < 3:
        raise SystemExit(f"too few patches applied ({changes}); abort without write")

    UI.write_text(ui, encoding="utf-8")
    py_compile.compile(str(UI), doraise=True)
    print("wrote", UI)
    print("compile OK")
    print("DONE changes=", changes)


if __name__ == "__main__":
    main()
