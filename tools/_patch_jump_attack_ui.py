# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(".").resolve()

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")
    print("updated", rel)

ui = read("src/ui/ui.py")
if "home_jump_attack" not in ui:
    # Ensure QCheckBox already imported (it is)
    # Add checkbox in attack card after creating grid widgets, before adding to layout
    old = (
        '        self.home_attack_grid.addWidget(self.home_aoe_trigger_count_field, 1, 0)\n'
        '        self.home_attack_grid.addWidget(self.home_aoe_cooldown_field, 1, 1)\n'
        '        for column in range(3):\n'
        '            self.home_attack_grid.setColumnStretch(column, 1)\n'
        '        attack_row.addWidget(attack_content, 1)\n'
        '        layout.addWidget(attack_card)\n'
    )
    new = (
        '        self.home_attack_grid.addWidget(self.home_aoe_trigger_count_field, 1, 0)\n'
        '        self.home_attack_grid.addWidget(self.home_aoe_cooldown_field, 1, 1)\n'
        '        self.home_jump_attack = QCheckBox("跳打模式")\n'
        '        self.home_jump_attack.setToolTip(\n'
        '            "勾选后：移动中先断按跳跃，再随机延迟 0.1–0.8 秒断按主攻/群攻；方向键保持按住。\\n'
        '边缘附近自动改为原地攻击（不跳）。"\n'
        '        )\n'
        '        self.home_jump_attack_field = create_field("主攻类型旁", self.home_jump_attack)\n'
        '        self.home_attack_grid.addWidget(self.home_jump_attack_field, 1, 2)\n'
        '        for column in range(3):\n'
        '            self.home_attack_grid.setColumnStretch(column, 1)\n'
        '        attack_row.addWidget(attack_content, 1)\n'
        '        layout.addWidget(attack_card)\n'
    )
    # Fix tooltip string - I broke it with bad escaping. Rewrite carefully.
    new = (
        '        self.home_attack_grid.addWidget(self.home_aoe_trigger_count_field, 1, 0)\n'
        '        self.home_attack_grid.addWidget(self.home_aoe_cooldown_field, 1, 1)\n'
        '        self.home_jump_attack = QCheckBox("跳打模式")\n'
        '        self.home_jump_attack.setToolTip(\n'
        '            "勾选后：移动中先断按跳跃，再随机延迟 0.1–0.8 秒断按主攻/群攻；"\n'
        '            "方向键保持按住。边缘附近自动改为原地攻击（不跳）。"\n'
        '        )\n'
        '        self.home_jump_attack_field = create_field("跳打", self.home_jump_attack)\n'
        '        self.home_attack_grid.addWidget(self.home_jump_attack_field, 1, 2)\n'
        '        for column in range(3):\n'
        '            self.home_attack_grid.setColumnStretch(column, 1)\n'
        '        attack_row.addWidget(attack_content, 1)\n'
        '        layout.addWidget(attack_card)\n'
    )
    if old not in ui:
        raise SystemExit("home attack grid block not found")
    ui = ui.replace(old, new, 1)

    # sync from cfg
    old_sync = (
        '        self.home_aoe_cooldown.setValue(\n'
        '            round(float(hybrid_cfg.get("aoe_cooldown", 0.9)) * 10)\n'
        '        )\n'
    )
    new_sync = (
        '        self.home_aoe_cooldown.setValue(\n'
        '            round(float(hybrid_cfg.get("aoe_cooldown", 0.9)) * 10)\n'
        '        )\n'
        '        if hasattr(self, "home_jump_attack"):\n'
        '            self.home_jump_attack.blockSignals(True)\n'
        '            self.home_jump_attack.setChecked(\n'
        '                bool(self.cfg.get("bot", {}).get("jump_attack", False))\n'
        '            )\n'
        '            self.home_jump_attack.blockSignals(False)\n'
    )
    if old_sync not in ui:
        raise SystemExit("sync attack fields insert not found")
    ui = ui.replace(old_sync, new_sync, 1)

    # save to cfg
    old_save = (
        '        hybrid_cfg = self.cfg.setdefault("hybrid_attack", {})\n'
        '        hybrid_cfg["aoe_trigger_count"] = self.home_aoe_trigger_count.value()\n'
        '        hybrid_cfg["aoe_cooldown"] = self.home_aoe_cooldown.value() / 10.0\n'
        '        # Map selection\n'
        '        self.cfg["bot"]["map"] = self.selected_map\n'
    )
    new_save = (
        '        hybrid_cfg = self.cfg.setdefault("hybrid_attack", {})\n'
        '        hybrid_cfg["aoe_trigger_count"] = self.home_aoe_trigger_count.value()\n'
        '        hybrid_cfg["aoe_cooldown"] = self.home_aoe_cooldown.value() / 10.0\n'
        '        if hasattr(self, "home_jump_attack"):\n'
        '            jump_on = bool(self.home_jump_attack.isChecked())\n'
        '            self.cfg.setdefault("bot", {})["jump_attack"] = jump_on\n'
        '            # Keep selected profession profile in sync with home checkbox.\n'
        '            selected_name = ""\n'
        '            if hasattr(self, "profession_combo"):\n'
        '                selected_name = self.profession_combo.currentData() or ""\n'
        '            profile = self.profession_store.get(selected_name) if selected_name else None\n'
        '            if isinstance(profile, dict):\n'
        '                profile["jump_attack"] = jump_on\n'
        '        # Map selection\n'
        '        self.cfg["bot"]["map"] = self.selected_map\n'
    )
    if old_save not in ui:
        raise SystemExit("update_cfg_from_main_ui insert not found")
    ui = ui.replace(old_save, new_save, 1)

    write("src/ui/ui.py", ui)
else:
    print("ui already patched")

print("OK ui")
