# -*- coding: utf-8 -*-
"""Minimal fix for nametag sky / top-right false lock leaving Attack Range boxes wrong.

Run on Windows from MapleStoryAutoLevelUp project root:
  .\\.venv\\Scripts\\python.exe tools\\_fix_sky_lock_nametag.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_engine() -> None:
    path = ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py"
    text = path.read_text(encoding="utf-8")

    old_in = (
        "        def _in_play_field(loc):\n"
        "            return loc[0] >= search_left and loc[1] >= search_top\n"
    )
    new_in = (
        "        search_right = max(0, int(nametag_cfg.get(\"search_right\", 220)))\n"
        "        max_x = max(search_left + 1, img_roi.shape[1] - search_right)\n"
        "\n"
        "        def _in_play_field(loc):\n"
        "            # Reject top HUD strip, left minimap, and right quest / notice HUD.\n"
        "            return (\n"
        "                loc[0] >= search_left\n"
        "                and loc[0] <= max_x\n"
        "                and loc[1] >= search_top\n"
        "            )\n"
    )
    if "max_x = max(search_left + 1, img_roi.shape[1] - search_right)" in text:
        print("[skip] engine: search_right play-field gate")
    elif old_in not in text:
        raise SystemExit("engine: _in_play_field block not found")
    else:
        text = text.replace(old_in, new_in, 1)
        print("[ok] engine: search_right play-field gate")

    old_occ = (
        "        if score >= threshold:\n"
        "            # Overlapping monster/player names inflate SQDIFF. Keep the hit if\n"
        "            # the matched region is still clearly a cyan nameplate.\n"
        "            occluded_threshold = float(nametag_cfg.get(\"occluded_diff_thres\", 0.36))\n"
        "            occluded_support = float(nametag_cfg.get(\"occluded_plate_support\", 0.28))\n"
        "            if not (\n"
        "                require_plate\n"
        "                and score < occluded_threshold\n"
        "                and plate_support(matched_roi) >= occluded_support\n"
        "            ):\n"
        "                return None\n"
        "            match_source = \"occluded\"\n"
    )
    new_occ = (
        "        if score >= threshold:\n"
        "            # Overlapping monster/player names inflate SQDIFF. Keep the hit only\n"
        "            # when the plate is strong — short CMS cloud tags (e.g. 日丁)\n"
        "            # otherwise false-lock on quest HUD / sky at ~diff_thres.\n"
        "            occluded_threshold = float(nametag_cfg.get(\"occluded_diff_thres\", 0.30))\n"
        "            occluded_support = float(nametag_cfg.get(\"occluded_plate_support\", 0.28))\n"
        "            support = plate_support(matched_roi) if require_plate else 0.0\n"
        "            if not (\n"
        "                require_plate\n"
        "                and score < occluded_threshold\n"
        "                and support >= occluded_support\n"
        "                and support >= 0.22\n"
        "            ):\n"
        "                return None\n"
        "            match_source = \"occluded\"\n"
    )
    if "support >= 0.22" in text:
        print("[skip] engine: occluded already tightened")
    elif old_occ not in text:
        raise SystemExit("engine: occluded block not found — inspect manually")
    else:
        text = text.replace(old_occ, new_occ, 1)
        print("[ok] engine: tighter occluded accept")

    old_skip = (
        "            elif self.loc_player != (0, 0):\n"
        "                # Scan/Return: reuse last attack-center while minimap is driving motion.\n"
        "                return self.loc_player\n"
    )
    new_skip = (
        "            elif self.loc_player != (0, 0):\n"
        "                # Scan/Return: reuse last attack-center while minimap drives motion,\n"
        "                # but drop sky/HUD stale locks (top-right quest false positives).\n"
        "                nametag_cfg = self.cfg.get(\"nametag\") or {}\n"
        "                search_top = max(0, int(nametag_cfg.get(\"search_top\", 100)))\n"
        "                search_left = max(0, int(nametag_cfg.get(\"search_left\", 140)))\n"
        "                search_right = max(0, int(nametag_cfg.get(\"search_right\", 220)))\n"
        "                max_x = max(\n"
        "                    search_left + 1,\n"
        "                    self.img_frame.shape[1] - search_right,\n"
        "                )\n"
        "                px, py = self.loc_player\n"
        "                if px >= search_left and px <= max_x and py >= search_top:\n"
        "                    return self.loc_player\n"
        "                self.nametag_match_valid = False\n"
    )
    if "drop sky/HUD stale locks" in text:
        print("[skip] engine: stale sky-lock reuse guard")
    elif old_skip not in text:
        raise SystemExit("engine: skip-reuse block not found")
    else:
        text = text.replace(old_skip, new_skip, 1)
        print("[ok] engine: stale sky-lock reuse guard")

    path.write_text(text, encoding="utf-8")
    print(f"[write] {path}")


def _set_yaml_keys(path: Path, updates: dict) -> None:
    if not path.exists():
        print(f"[skip] missing {path}")
        return
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    in_nametag = False
    seen = set()
    for line in lines:
        if line.startswith("nametag:"):
            in_nametag = True
            out.append(line)
            continue
        if in_nametag and line and not line[0].isspace() and not line.startswith("#"):
            for k, v in updates.items():
                if k not in seen:
                    out.append(f"  {k}: {v}")
                    seen.add(k)
                    print(f"[insert] {path.name} nametag.{k}={v}")
            in_nametag = False
            out.append(line)
            continue
        if in_nametag:
            stripped = line.lstrip()
            replaced = False
            for k, v in updates.items():
                if stripped.startswith(f"{k}:"):
                    indent = line[: len(line) - len(stripped)]
                    out.append(f"{indent}{k}: {v}")
                    seen.add(k)
                    replaced = True
                    print(f"[set] {path.name} nametag.{k}={v}")
                    break
            if not replaced:
                out.append(line)
            continue
        out.append(line)
    if in_nametag:
        for k, v in updates.items():
            if k not in seen:
                out.append(f"  {k}: {v}")
                print(f"[insert] {path.name} nametag.{k}={v}")
    path.write_text("\n".join(out) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")


def patch_configs() -> None:
    updates = {
        "diff_thres": "0.18",
        "occluded_diff_thres": "0.30",
        "occluded_plate_support": "0.28",
        "search_top": "200",
        "search_left": "150",
        "search_right": "220",
        "cache_keep_thres": "0.12",
        "scan_every_n_frames": "45",
        "skip_when_minimap_ok": "true",
    }
    for rel in [
        "config/config_tommy.yaml",
        "dist/config/.config_tmp.yaml",
        "config/config_default.yaml",
        "dist/config/config_default.yaml",
    ]:
        _set_yaml_keys(ROOT / rel, updates)


def main() -> None:
    patch_engine()
    patch_configs()
    print("DONE — rebuild dist\\MapleStory.exe when ready.")
    print("User check: F2 should show green NameTag on 日丁+勋章 near character,")
    print("and Attack Range boxes around the character — not top-right sky.")
    print("If still wrong: re-crop assets/nametag/日丁.png as hard two-row 名牌+勋章.")


if __name__ == "__main__":
    main()
