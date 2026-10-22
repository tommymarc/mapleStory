# -*- coding: utf-8 -*-
"""Reject nametag false-locks on bottom-right chat / party UI."""
from pathlib import Path
import py_compile
import yaml

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
ENGINE = ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py"

OLD = '''        def _in_play_field(loc):
            return loc[0] >= search_left and loc[1] >= search_top

        require_plate = mode == "color"
'''

NEW = '''        def _in_play_field(loc):
            return loc[0] >= search_left and loc[1] >= search_top

        # Private chat / buddy avatars sit bottom-right and can look like
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

        require_plate = mode == "color"
'''

OLD2 = '''            global_box = (
                search_left,
                search_top,
                img_roi.shape[1],
                img_roi.shape[0],
            )
'''

NEW2 = '''            global_box = (
                search_left,
                search_top,
                max(search_left + 1, roi_w - exclude_right),
                max(search_top + 1, roi_h - exclude_bottom),
            )
'''

OLD3 = '''            flat = [c for c, _src in merged]
            gated = pick_nametag_candidate(
                flat,
                prefer_box=biased_box,
'''

NEW3 = '''            flat = [
                c for c, _src in merged
                if _in_play_field(c[0]) and not _in_chat_ui_zone(c[0], c[1])
            ]
            gated = pick_nametag_candidate(
                flat,
                prefer_box=biased_box,
'''

OLD4 = '''        # Hard reject HUD / minimap false positives even if matcher returned them.
        if not _in_play_field(loc_nametag):
            held = self._nametag_return_hold(nametag_cfg, "hud")
            if held is not None:
                return held
            self.nametag_match_valid = False
            return None
'''

NEW4 = '''        # Hard reject HUD / minimap false positives even if matcher returned them.
        if not _in_play_field(loc_nametag):
            held = self._nametag_return_hold(nametag_cfg, "hud")
            if held is not None:
                return held
            self.nametag_match_valid = False
            return None
        # Hard reject bottom-right chat / avatar false locks.
        if _in_chat_ui_zone(loc_nametag, score):
            held = self._nametag_return_hold(nametag_cfg, "chat_ui")
            if held is not None:
                return held
            self.nametag_match_valid = False
            return None
'''

text = ENGINE.read_text(encoding="utf-8")
for label, old, new in (
    ("helpers", OLD, NEW),
    ("global_box", OLD2, NEW2),
    ("filter_cands", OLD3, NEW3),
    ("hard_reject", OLD4, NEW4),
):
    if old not in text:
        if label == "hard_reject" and "chat_ui" in text:
            print(label, "already applied")
            continue
        raise SystemExit(f"block not found: {label}")
    text = text.replace(old, new, 1)
    print("patched", label)

ENGINE.write_text(text, encoding="utf-8")
py_compile.compile(str(ENGINE), doraise=True)
print("engine syntax OK")

# Seed nametag keys into tommy configs (both)
keys = {
    "ui_reject_right_frac": 0.72,
    "ui_reject_bottom_frac": 0.60,
    "ui_zone_reject_score": 0.08,
    "search_exclude_right": 280,
    "search_exclude_bottom": 160,
}
for rel in ("config/config_tommy.yaml", "dist/config/config_tommy.yaml"):
    path = ROOT / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    nt = data.setdefault("nametag", {})
    if not isinstance(nt, dict):
        data["nametag"] = {}
        nt = data["nametag"]
    for k, v in keys.items():
        nt[k] = v
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("updated", rel, "nametag ui reject keys")
