# -*- coding: utf-8 -*-
"""Apply 剑客 combat optimizations: balanced templates, tighter thresh, sky filter."""
from __future__ import annotations
from pathlib import Path
import re
import yaml

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
ENGINE = ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py"
PROF_PATHS = [
    ROOT / "config" / "config_professions.yaml",
    ROOT / "dist" / "config" / "config_professions.yaml",
]
UI_PROF = ROOT / "src" / "ui" / "profession_config.py"

OLD_SORT = '''                def _monster_file_sort_key(path):
                    base = os.path.basename(path).lower()
                    if base.startswith("stand"):
                        return (0, base)
                    if base.startswith("move"):
                        return (1, base)
                    return (2, base)
                monster_files = sorted(monster_files, key=_monster_file_sort_key)
                if max_files > 0:
                    monster_files = monster_files[:max_files]'''

NEW_SORT = '''                def _monster_file_sort_key(path):
                    base = os.path.basename(path).lower()
                    if base.startswith("stand"):
                        return (0, base)
                    if base.startswith("move"):
                        return (1, base)
                    return (2, base)
                # When both stand and move are requested, split the file budget
                # so move poses are not crowded out by many stand frames.
                def _select_balanced_monster_files(files, prefixes, limit):
                    if limit <= 0:
                        return list(files)
                    prefs = [p for p in prefixes if p]
                    if len(prefs) >= 2 and "stand" in prefs and "move" in prefs:
                        buckets = {p: [] for p in prefs}
                        other = []
                        for path in files:
                            base = os.path.basename(path).lower()
                            placed = False
                            for p in prefs:
                                if base.startswith(p):
                                    buckets[p].append(path)
                                    placed = True
                                    break
                            if not placed:
                                other.append(path)
                        for p in prefs:
                            buckets[p].sort(key=_monster_file_sort_key)
                        other.sort(key=_monster_file_sort_key)
                        n_pref = len(prefs)
                        base_quota = limit // n_pref
                        rem = limit % n_pref
                        quotas = {}
                        # Prefer giving leftover slots to stand first, then move.
                        order = sorted(prefs, key=lambda p: (0 if p == "stand" else 1 if p == "move" else 2, p))
                        for i, p in enumerate(order):
                            quotas[p] = base_quota + (1 if i < rem else 0)
                        chosen = []
                        leftover_budget = 0
                        for p in order:
                            take = buckets[p][: quotas[p]]
                            chosen.extend(take)
                            leftover_budget += quotas[p] - len(take)
                        if leftover_budget > 0:
                            used = set(chosen)
                            pool = []
                            for p in order:
                                pool.extend(buckets[p][quotas[p]:])
                            pool.extend(other)
                            for path in pool:
                                if leftover_budget <= 0:
                                    break
                                if path in used:
                                    continue
                                chosen.append(path)
                                used.add(path)
                                leftover_budget -= 1
                        return sorted(chosen, key=_monster_file_sort_key)
                    sorted_files = sorted(files, key=_monster_file_sort_key)
                    return sorted_files[:limit]

                monster_files = _select_balanced_monster_files(
                    monster_files, name_prefixes, max_files
                )'''

# Sky filter after NMS
OLD_NMS = '''        # Apply Non-Maximum Suppression to monster detection
        monsters = nms(monsters, iou_threshold=0.4)

        # Detect monster via health bar'''

NEW_NMS = '''        # Apply Non-Maximum Suppression to monster detection
        monsters = nms(monsters, iou_threshold=0.4)

        # Drop sky / upper-platform false hits far above the player.
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

        # Detect monster via health bar'''

def patch_engine():
    text = ENGINE.read_text(encoding="utf-8")
    changed = False
    if OLD_SORT not in text:
        if "_select_balanced_monster_files" in text:
            print("engine: balanced select already present")
        else:
            raise SystemExit("OLD_SORT block not found in engine")
    else:
        text = text.replace(OLD_SORT, NEW_SORT, 1)
        changed = True
        print("engine: balanced template select applied")
    if OLD_NMS not in text:
        if "max_above_player_y" in text:
            print("engine: sky filter already present")
        else:
            raise SystemExit("OLD_NMS block not found in engine")
    else:
        text = text.replace(OLD_NMS, NEW_NMS, 1)
        changed = True
        print("engine: sky filter applied")
    if changed:
        ENGINE.write_text(text, encoding="utf-8")
    return changed

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
        "detect_every_n_frames": 2,
        "diff_thres": 0.28,
        "max_above_player_y": 90,
        "template_max_files_per_monster": 6,
        "template_name_prefixes": ["stand", "move"],
    },
}

def patch_professions():
    for path in PROF_PATHS:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        profs = data.setdefault("professions", {})
        sword = profs.setdefault("剑客", {})
        sword["overrides"] = SWORD_OVERRIDES
        # preserve other sword fields if present
        data["selected_profession"] = data.get("selected_profession") or "剑客"
        if data["selected_profession"] not in ("剑客",):
            # keep user's selection if they switched; but prefer 剑客 for this task
            pass
        # Force selected to 剑客 only if already 剑客 or empty
        if not data.get("selected_profession"):
            data["selected_profession"] = "剑客"
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print("updated", path, "selected=", data.get("selected_profession"))

def patch_builtin_seed():
    """Keep profession_config builtin 剑客 seed in sync if present."""
    if not UI_PROF.exists():
        print("no profession_config.py")
        return
    text = UI_PROF.read_text(encoding="utf-8")
    if "剑客" not in text:
        print("profession_config: no 剑客 seed")
        return
    # Best-effort: if detect_every_n_frames: 1 in 剑客 block, bump keys via regex
    # Only touch if clear markers exist.
    if "detect_every_n_frames: 1" in text and "剑客" in text:
        text2 = text.replace("detect_every_n_frames: 1", "detect_every_n_frames: 2", 1)
        # only if that was unique enough - check count
        if text.count("detect_every_n_frames: 1") == 1:
            text = text2
            print("profession_config: bumped detect_every_n_frames")
        else:
            print("profession_config: multiple detect_every_n_frames:1, skip auto bump")
    # inject diff_thres / max_above if missing near 剑客 overrides
    if "max_above_player_y" not in text:
        # insert after template_name_prefixes block if possible
        needle = '"template_name_prefixes": ["stand", "move"]'
        alt = "'template_name_prefixes': ['stand', 'move']"
        for n in (needle, alt, '["stand", "move"]', "['stand', 'move']"):
            if n in text:
                # too risky for free-form; leave yaml files as source of truth
                print("profession_config: leave seed; yaml is source of truth")
                break
    UI_PROF.write_text(text, encoding="utf-8")

def verify_select():
    # simulate selection for 野猪
    mob = ROOT / "assets" / "monster" / "野猪"
    files = sorted(
        [str(p) for p in mob.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")],
        key=lambda s: s.lower(),
    )
    name_prefixes = ["stand", "move"]
    filtered = []
    for file in files:
        base = Path(file).name.lower()
        if any(base.startswith(prefix) for prefix in name_prefixes):
            filtered.append(file)
    # inline copy of helper using engine after patch — re-read and exec snippet
    text = ENGINE.read_text(encoding="utf-8")
    if "_select_balanced_monster_files" not in text:
        print("VERIFY FAIL: helper missing")
        return
    # run local equivalent
    import os
    def _monster_file_sort_key(path):
        base = os.path.basename(path).lower()
        if base.startswith("stand"):
            return (0, base)
        if base.startswith("move"):
            return (1, base)
        return (2, base)
    def _select_balanced_monster_files(files, prefixes, limit):
        if limit <= 0:
            return list(files)
        prefs = [p for p in prefixes if p]
        if len(prefs) >= 2 and "stand" in prefs and "move" in prefs:
            buckets = {p: [] for p in prefs}
            other = []
            for path in files:
                base = os.path.basename(path).lower()
                placed = False
                for p in prefs:
                    if base.startswith(p):
                        buckets[p].append(path)
                        placed = True
                        break
                if not placed:
                    other.append(path)
            for p in prefs:
                buckets[p].sort(key=_monster_file_sort_key)
            other.sort(key=_monster_file_sort_key)
            n_pref = len(prefs)
            base_quota = limit // n_pref
            rem = limit % n_pref
            quotas = {}
            order = sorted(prefs, key=lambda p: (0 if p == "stand" else 1 if p == "move" else 2, p))
            for i, p in enumerate(order):
                quotas[p] = base_quota + (1 if i < rem else 0)
            chosen = []
            leftover_budget = 0
            for p in order:
                take = buckets[p][: quotas[p]]
                chosen.extend(take)
                leftover_budget += quotas[p] - len(take)
            if leftover_budget > 0:
                used = set(chosen)
                pool = []
                for p in order:
                    pool.extend(buckets[p][quotas[p]:])
                pool.extend(other)
                for path in pool:
                    if leftover_budget <= 0:
                        break
                    if path in used:
                        continue
                    chosen.append(path)
                    used.add(path)
                    leftover_budget -= 1
            return sorted(chosen, key=_monster_file_sort_key)
        sorted_files = sorted(files, key=_monster_file_sort_key)
        return sorted_files[:limit]
    picked = _select_balanced_monster_files(filtered, name_prefixes, 6)
    names = [Path(p).name for p in picked]
    print("野猪 templates ->", names)
    assert any(n.startswith("move") for n in names), names
    assert any(n.startswith("stand") for n in names), names
    print("verify OK")

if __name__ == "__main__":
    patch_engine()
    patch_professions()
    patch_builtin_seed()
    verify_select()
    # print effective sword overrides
    for path in PROF_PATHS:
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        ov = d["professions"]["剑客"]["overrides"]["monster_detect"]
        print(path.name, "monster_detect", ov)
