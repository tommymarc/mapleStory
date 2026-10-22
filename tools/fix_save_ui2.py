# -*- coding: utf-8 -*-
from pathlib import Path
import py_compile
import re

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
UI = ROOT / "src" / "ui" / "ui.py"
PROF = ROOT / "src" / "ui" / "profession_config.py"

for rel in ("config/config_custom.yaml", "dist/config/config_custom.yaml"):
    p = ROOT / rel
    if (not p.exists()) or p.stat().st_size == 0:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}\n", encoding="utf-8")
        print("wrote empty-safe", rel)
    else:
        print("keep", rel, p.stat().st_size)

ui = UI.read_text(encoding="utf-8")

# Broaden save_current_config except
old_ex = "        except (OSError, ValueError) as error:\n            logger.error(f\"[UI] Save current config failed: {error}\")\n"
new_ex = "        except Exception as error:\n            logger.exception(f\"[UI] Save current config failed: {error}\")\n"
# only the save_current_config one - replace first occurrence in that function
idx = ui.find("def save_current_config")
if idx < 0:
    raise SystemExit("save_current_config missing")
idx2 = ui.find("except (OSError, ValueError) as error:", idx)
idx3 = ui.find("def ", idx + 10)
if idx2 < 0 or idx2 > idx3:
    if "except Exception as error:" in ui[idx:idx3]:
        print("save except already broad")
    else:
        raise SystemExit("save except not found in function")
else:
    # replace this specific except line + next logger.error line
    end_line2 = ui.find("\n", ui.find("\n", idx2) + 1) + 1
    chunk = ui[idx2:end_line2]
    if "Save current config failed" not in chunk and "logger.error" not in ui[idx2:idx2+200]:
        # replace two lines
        pass
    ui = ui[:idx2] + new_ex + ui[end_line2:]
    # Wait end_line2 might be wrong. Do simpler:
    
ui = UI.read_text(encoding="utf-8")
count = ui.count("except (OSError, ValueError) as error:")
print("OSError ValueError except count", count)
# Replace ALL of these related to save - there may be assist mode persist too - broadening those is fine
ui = ui.replace(
    "        except (OSError, ValueError) as error:\n            logger.error(f\"[UI] Save current config failed: {error}\")\n",
    "        except Exception as error:\n            logger.exception(f\"[UI] Save current config failed: {error}\")\n",
)
ui = ui.replace(
    "            except (OSError, ValueError) as error:\n                logger.warning(\n                    f\"[UI] Assist mode: unable to persist potion_profile disable: {error}\"\n                )\n",
    "            except Exception as error:\n                logger.warning(\n                    f\"[UI] Assist mode: unable to persist potion_profile disable: {error}\"\n                )\n",
)

# Harden update_cfg_from_main_ui key access with setdefault via targeted replaces
repls = [
    (
        '        self.cfg["bot"]["mode"] = self.bot_mode.currentData() or "normal"\n        if self.cfg["bot"]["mode"] == "aux":',
        '        bot = self.cfg.setdefault("bot", {})\n        bot["mode"] = self.bot_mode.currentData() or "normal"\n        if bot.get("mode") == "aux":',
    ),
    (
        '            self.cfg["game_window"]["title"] = window_title\n',
        '            self.cfg.setdefault("game_window", {})["title"] = window_title\n',
    ),
    (
        '        self.cfg["health_monitor"]["add_hp_percent"] = self.home_hp_percent.value()\n        self.cfg["health_monitor"]["add_mp_percent"] = self.home_mp_percent.value()\n',
        '        hm = self.cfg.setdefault("health_monitor", {})\n        hm["add_hp_percent"] = self.home_hp_percent.value()\n        hm["add_mp_percent"] = self.home_mp_percent.value()\n',
    ),
    (
        '        attack_type = self.cfg["bot"].get("attack", "directional")\n        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"\n        self.cfg[section_name]["range_x"] = self.home_attack_range_x.value()\n        self.cfg[section_name]["range_y"] = self.home_attack_range_y.value()\n        self.cfg[section_name]["cooldown"] = self.home_attack_cooldown.value() / 10.0\n',
        '        attack_type = self.cfg.setdefault("bot", {}).get("attack", "directional")\n        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"\n        section = self.cfg.setdefault(section_name, {})\n        section["range_x"] = self.home_attack_range_x.value()\n        section["range_y"] = self.home_attack_range_y.value()\n        section["cooldown"] = self.home_attack_cooldown.value() / 10.0\n',
    ),
    (
        '        self.cfg["bot"]["map"] = self.selected_map\n',
        '        self.cfg.setdefault("bot", {})["map"] = self.selected_map\n',
    ),
]
for a, b in repls:
    if a not in ui:
        print("WARN missing chunk", a[:60])
    else:
        ui = ui.replace(a, b, 1)
        print("patched chunk", a.splitlines()[0][:50])

UI.write_text(ui, encoding="utf-8")
py_compile.compile(str(UI), doraise=True)
print("ui compile OK")

prof = PROF.read_text(encoding="utf-8")
old_psave = """    def _save(self):
        if self.profession_combo.currentText():
            self.store.select(self.profession_combo.currentText())
        self.store.save()
        self.profiles_changed.emit()
        QMessageBox.information(self, \"保存配置\", \"职业键位配置已保存。\")
"""
new_psave = """    def _save(self):
        try:
            if self.profession_combo.currentText():
                self.store.select(self.profession_combo.currentText())
            self.store.save()
            self.profiles_changed.emit()
        except Exception as error:
            QMessageBox.warning(self, \"保存失败\", str(error))
            return
        QMessageBox.information(self, \"保存配置\", \"职业键位配置已保存。\")
"""
if old_psave in prof:
    prof = prof.replace(old_psave, new_psave, 1)
    print("profession _save patched")
else:
    # already?
    if "保存失败" in prof[prof.find("def _save"):prof.find("def _save")+400]:
        print("profession _save already has 保存失败")
    else:
        raise SystemExit("profession _save pattern mismatch")

PROF.write_text(prof, encoding="utf-8")
py_compile.compile(str(PROF), doraise=True)
print("profession compile OK")
print("DONE")
