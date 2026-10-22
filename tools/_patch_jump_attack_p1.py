# -*- coding: utf-8 -*-
from pathlib import Path
import re

ROOT = Path(".").resolve()

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")
    print("updated", rel)

# ---------- config_default.yaml ----------
cfg = read("config/config_default.yaml")
if "jump_attack:" not in cfg:
    needle = '  map: "" # Please refer to config/config_data.yaml\n'
    insert = (
        '  map: "" # Please refer to config/config_data.yaml\n'
        '  jump_attack: false           # Jump-attack: tap jump then tap attack while move held\n'
        '  jump_attack_delay_min: 0.1   # seconds between jump and attack (random low)\n'
        '  jump_attack_delay_max: 0.8   # seconds between jump and attack (random high)\n'
    )
    if needle not in cfg:
        raise SystemExit("map line not found in config_default")
    cfg = cfg.replace(needle, insert, 1)
    write("config/config_default.yaml", cfg)
else:
    print("config_default already has jump_attack")

# ---------- profession_bindings.py ----------
pb = read("src/utils/profession_bindings.py")
if 'cfg["bot"]["jump_attack"]' not in pb:
    pb = pb.replace(
        '    if "attack" in fallback_bot:\n'
        '        cfg["bot"]["attack"] = fallback_bot["attack"]\n',
        '    if "attack" in fallback_bot:\n'
        '        cfg["bot"]["attack"] = fallback_bot["attack"]\n'
        '    if "jump_attack" in fallback_bot:\n'
        '        cfg["bot"]["jump_attack"] = fallback_bot["jump_attack"]\n'
        '    if "jump_attack_delay_min" in fallback_bot:\n'
        '        cfg["bot"]["jump_attack_delay_min"] = fallback_bot["jump_attack_delay_min"]\n'
        '    if "jump_attack_delay_max" in fallback_bot:\n'
        '        cfg["bot"]["jump_attack_delay_max"] = fallback_bot["jump_attack_delay_max"]\n',
        1,
    )
    pb = pb.replace(
        '    cfg[RUNTIME_CONFIG_KEY] = {\n'
        '        "name": name,\n'
        '        "main_attack_type": attack_type,\n'
        '        "bindings": copy.deepcopy(bindings),\n'
        '        "intervals": copy.deepcopy(intervals),\n'
        '    }\n'
        '\n'
        '    # Legacy engine compatibility for the actions it already understands.\n'
        '    if has_profile:\n'
        '        cfg["bot"]["attack"] = attack_type\n',
        '    jump_attack = bool(profile.get("jump_attack", False))\n'
        '\n'
        '    cfg[RUNTIME_CONFIG_KEY] = {\n'
        '        "name": name,\n'
        '        "main_attack_type": attack_type,\n'
        '        "jump_attack": jump_attack,\n'
        '        "bindings": copy.deepcopy(bindings),\n'
        '        "intervals": copy.deepcopy(intervals),\n'
        '    }\n'
        '\n'
        '    # Legacy engine compatibility for the actions it already understands.\n'
        '    if has_profile:\n'
        '        cfg["bot"]["attack"] = attack_type\n'
        '        cfg["bot"]["jump_attack"] = jump_attack\n',
        1,
    )
    write("src/utils/profession_bindings.py", pb)
else:
    print("profession_bindings already patched")

# ---------- profession_config.py ----------
pc = read("src/ui/profession_config.py")
if "jump_attack_checkbox" not in pc:
    # import QCheckBox
    if "QCheckBox" not in pc:
        pc = pc.replace(
            "from PySide6.QtWidgets import (",
            "from PySide6.QtWidgets import (\n    QCheckBox,",
            1,
        )

    pc = pc.replace(
        '            "main_attack_type": attack_type,\n'
        '            "bindings": dict(bindings or {}),\n',
        '            "main_attack_type": attack_type,\n'
        '            "jump_attack": False,\n'
        '            "bindings": dict(bindings or {}),\n',
        1,
    )

    old_opts = (
        '        self.attack_type_combo.currentIndexChanged.connect(self._on_attack_type_changed)\n'
        '        layout.addWidget(self.attack_type_combo)\n'
        '\n'
        '        self.interval_container = QWidget()\n'
    )
    new_opts = (
        '        self.attack_type_combo.currentIndexChanged.connect(self._on_attack_type_changed)\n'
        '        layout.addWidget(self.attack_type_combo)\n'
        '\n'
        '        self.jump_attack_checkbox = QCheckBox("跳打模式")\n'
        '        self.jump_attack_checkbox.setToolTip(\n'
        '            "勾选后：移动中先断按跳跃，再随机延迟 0.1–0.8 秒断按主攻/群攻；方向键保持按住"\n'
        '        )\n'
        '        self.jump_attack_checkbox.stateChanged.connect(self._on_jump_attack_changed)\n'
        '        layout.addWidget(self.jump_attack_checkbox)\n'
        '\n'
        '        self.interval_container = QWidget()\n'
    )
    if old_opts not in pc:
        raise SystemExit("profile options insert point not found")
    pc = pc.replace(old_opts, new_opts, 1)

    pc = pc.replace(
        '        self.attack_type_combo.setEnabled(enabled)\n'
        '        for button in self.function_buttons.values():\n',
        '        self.attack_type_combo.setEnabled(enabled)\n'
        '        if hasattr(self, "jump_attack_checkbox"):\n'
        '            self.jump_attack_checkbox.setEnabled(enabled)\n'
        '        for button in self.function_buttons.values():\n',
        1,
    )

    old_load = (
        '            self.attack_type_combo.blockSignals(True)\n'
        '            self.attack_type_combo.setCurrentIndex(max(index, 0))\n'
        '            self.attack_type_combo.blockSignals(False)\n'
        '        self.current_function_label.setText("当前按键功能：无")\n'
    )
    new_load = (
        '            self.attack_type_combo.blockSignals(True)\n'
        '            self.attack_type_combo.setCurrentIndex(max(index, 0))\n'
        '            self.attack_type_combo.blockSignals(False)\n'
        '            if hasattr(self, "jump_attack_checkbox"):\n'
        '                self.jump_attack_checkbox.blockSignals(True)\n'
        '                self.jump_attack_checkbox.setChecked(bool(profile.get("jump_attack", False)))\n'
        '                self.jump_attack_checkbox.blockSignals(False)\n'
        '        elif hasattr(self, "jump_attack_checkbox"):\n'
        '            self.jump_attack_checkbox.blockSignals(True)\n'
        '            self.jump_attack_checkbox.setChecked(False)\n'
        '            self.jump_attack_checkbox.blockSignals(False)\n'
        '        self.current_function_label.setText("当前按键功能：无")\n'
    )
    if old_load not in pc:
        raise SystemExit("profession load insert point not found")
    pc = pc.replace(old_load, new_load, 1)

    old_handler = (
        '    def _on_attack_type_changed(self):\n'
        '        profile = self._current_profile()\n'
        '        if profile:\n'
        '            profile["main_attack_type"] = self.attack_type_combo.currentData()\n'
        '\n'
        '    def _on_key_clicked(self, key):\n'
    )
    new_handler = (
        '    def _on_attack_type_changed(self):\n'
        '        profile = self._current_profile()\n'
        '        if profile:\n'
        '            profile["main_attack_type"] = self.attack_type_combo.currentData()\n'
        '\n'
        '    def _on_jump_attack_changed(self, _state=None):\n'
        '        profile = self._current_profile()\n'
        '        if profile and hasattr(self, "jump_attack_checkbox"):\n'
        '            profile["jump_attack"] = bool(self.jump_attack_checkbox.isChecked())\n'
        '\n'
        '    def _on_key_clicked(self, key):\n'
    )
    if old_handler not in pc:
        raise SystemExit("attack type handler insert point not found")
    pc = pc.replace(old_handler, new_handler, 1)
    write("src/ui/profession_config.py", pc)
else:
    print("profession_config already patched")

print("OK phase1")
