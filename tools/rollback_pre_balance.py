# -*- coding: utf-8 -*-
"""Rollback to before stand/move balanced-template opt batch.

Keeps: 剑客 profession, _ensure_builtin_profiles crash fix, smoke gate.
Removes: balanced template select, sky filter, tightened sword monster_detect,
         chat-UI nametag reject + tommy ui keys.
"""
from __future__ import annotations
from pathlib import Path
import py_compile
import re
import yaml

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
ENGINE = ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py"
UI = ROOT / "src" / "ui" / "profession_config.py"

text = ENGINE.read_text(encoding="utf-8")

SIMPLE = '''                def _monster_file_sort_key(path):
                    base = os.path.basename(path).lower()
                    if base.startswith("stand"):
                        return (0, base)
                    if base.startswith("move"):
                        return (1, base)
                    return (2, base)
                monster_files = sorted(monster_files, key=_monster_file_sort_key)
                if max_files > 0:
                    monster_files = monster_files[:max_files]
'''

if "_select_balanced_monster_files" in text:
    pattern = re.compile(
        r"                def _monster_file_sort_key\(path\):.*?"
        r"                monster_files = _select_balanced_monster_files\(\n"
        r"                    monster_files, name_prefixes, max_files\n"
        r"                \)\n",
        re.S,
    )
    text2, n = pattern.subn(SIMPLE, text, count=1)
    if n != 1:
        raise SystemExit(f"balanced block replace failed n={n}")
    text = text2
    print("engine: restored stand-first template trim")
else:
    print("engine: balanced select already absent")

SKY = '''        # Drop sky / upper-platform false hits far above the player.
        try:
            max_above = float(
                (self.cfg.get("monster_detect") or {}).get("max_above_player_y", 0) or 0
            )
        except (TypeError, ValueError):
            max_above = 0.0
        if max_above > 0 and getattr(self, "loc_player", None):
            py = int(self.loc_player[1])
            kept = []
            for monster in monsters:
                mx, my = monster["position"]
                _w, height = monster["size"]
                center_y = my + height // 2
                if center_y < py - max_above:
                    continue
                kept.append(monster)
            monsters = kept

'''
if SKY in text:
    text = text.replace(SKY, "", 1)
    print("engine: removed sky filter")
else:
    print("engine: sky filter already absent")

CHAT_HELPERS = '''        # Private chat / buddy avatars sit bottom-right and can look like
        # cyan nametag plates (seen locking at ~fixed (1151,529) score~0.13).
        ui_right_frac = float(nametag_cfg.get("ui_reject_right_frac", 0.72))
        ui_bottom_frac = float(nametag_cfg.get("ui_reject_bottom_frac", 0.60))
        ui_reject_score = float(nametag_cfg.get("ui_zone_reject_score", 0.08))
        exclude_right = max(0, int(nametag_cfg.get("search_exclude_right", 280)))
        exclude_bottom = max(0, int(nametag_cfg.get("search_exclude_bottom", 160)))
        roi_w = int(img_roi.shape[1])
        roi_h = int(img_roi.shape[0])

        def _in_chat_ui_zone(loc, score=None):
            x, y = int(loc[0]), int(loc[1])
            in_corner = (
                x >= int(roi_w * ui_right_frac)
                and y >= int(roi_h * ui_bottom_frac)
            )
            if not in_corner:
                return False
            if score is None:
                return True
            return float(score) > ui_reject_score

'''
if CHAT_HELPERS in text:
    text = text.replace(CHAT_HELPERS, "", 1)
    print("engine: removed chat UI helpers")
else:
    print("engine: chat helpers already absent")

OLD_GBOX = '''            global_box = (
                search_left,
                search_top,
                max(search_left + 1, roi_w - exclude_right),
                max(search_top + 1, roi_h - exclude_bottom),
            )
'''
NEW_GBOX = '''            global_box = (
                search_left,
                search_top,
                img_roi.shape[1],
                img_roi.shape[0],
            )
'''
if OLD_GBOX in text:
    text = text.replace(OLD_GBOX, NEW_GBOX, 1)
    print("engine: restored global_box")
else:
    print("engine: global_box already original or different")

OLD_FLAT = '''            flat = [
                c for c, _src in merged
                if _in_play_field(c[0]) and not _in_chat_ui_zone(c[0], c[1])
            ]
'''
NEW_FLAT = '''            flat = [c for c, _src in merged]
'''
if OLD_FLAT in text:
    text = text.replace(OLD_FLAT, NEW_FLAT, 1)
    print("engine: restored candidate flat list")
else:
    print("engine: flat list already original")

CHAT_REJECT = '''        # Hard reject bottom-right chat / avatar false locks.
        if _in_chat_ui_zone(loc_nametag, score):
            held = self._nametag_return_hold(nametag_cfg, "chat_ui")
            if held is not None:
                return held
            self.nametag_match_valid = False
            return None
'''
if CHAT_REJECT in text:
    text = text.replace(CHAT_REJECT, "", 1)
    print("engine: removed chat hard reject")
else:
    print("engine: chat hard reject already absent")

for bad in ("_select_balanced_monster_files", "_in_chat_ui_zone"):
    if bad in text:
        raise SystemExit(f"leftover {bad}")

ENGINE.write_text(text, encoding="utf-8")
py_compile.compile(str(ENGINE), doraise=True)
print("engine compile OK")

SWORD_OVERRIDES = {
    "combat": {
        "monster_track_enable": True,
        "monster_track_ttl_sec": 0.5,
    },
    "directional_attack": {
        "character_turn_delay": 0.03,
        "cooldown": 0.35,
        "range_x": 170,
        "range_y": 100,
        "skip_turn_if_facing": True,
    },
    "monster_detect": {
        "detect_every_n_frames": 1,
        "template_max_files_per_monster": 6,
        "template_name_prefixes": ["stand", "move"],
    },
}

for path in (
    ROOT / "config" / "config_professions.yaml",
    ROOT / "dist" / "config" / "config_professions.yaml",
):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sword = data.setdefault("professions", {}).setdefault("剑客", {})
    sword["overrides"] = SWORD_OVERRIDES
    if "main_attack_type" not in sword:
        sword["main_attack_type"] = "directional"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("professions reset", path.name)

ui = UI.read_text(encoding="utf-8")
start = ui.find("def _sword_profile")
end = ui.find("\n    def _ensure_builtin_profiles", start)
if end < 0:
    end = ui.find("\n    @staticmethod\n    def empty_profile", start)
if start > 0 and end > start:
    block = ui[start:end]
    block2 = re.sub(
        r'"monster_detect"\s*:\s*\{[^}]*\}',
        '"monster_detect": {\n'
        '                    "detect_every_n_frames": 1,\n'
        '                    "template_max_files_per_monster": 6,\n'
        '                    "template_name_prefixes": ["stand", "move"],\n'
        '                }',
        block,
        count=1,
        flags=re.S,
    )
    ui = ui[:start] + block2 + ui[end:]
    print("profession_config: sword monster_detect reset")
else:
    print("profession_config: could not locate _sword_profile block bounds")

UI.write_text(ui, encoding="utf-8")
py_compile.compile(str(UI), doraise=True)
print("profession_config compile OK")

UI_KEYS = [
    "ui_reject_right_frac",
    "ui_reject_bottom_frac",
    "ui_zone_reject_score",
    "search_exclude_right",
    "search_exclude_bottom",
]
for rel in ("config/config_tommy.yaml", "dist/config/config_tommy.yaml"):
    path = ROOT / rel
    if not path.exists():
        continue
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    nt = data.get("nametag")
    if isinstance(nt, dict):
        for k in UI_KEYS:
            nt.pop(k, None)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print("tommy cleaned", rel)

print("ROLLBACK DONE")
