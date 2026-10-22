# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT))
from src.utils.common import load_yaml
from src.utils.profession_bindings import apply_profession_profile
import copy

for rel in ("config/config_professions.yaml", "dist/config/config_professions.yaml"):
    d = load_yaml(str(ROOT / rel))
    names = list((d.get("professions") or {}).keys())
    print(rel, "names=", names, "selected=", d.get("selected_profession"))
    sword = (d.get("professions") or {}).get("剑客")
    print("  sword overrides", None if not sword else list((sword.get("overrides") or {}).keys()))

# simulate apply
cfg = load_yaml(str(ROOT / "config" / "config_default.yaml"))
fallback = copy.deepcopy(cfg)
d = load_yaml(str(ROOT / "dist" / "config" / "config_professions.yaml"))
prof = d["professions"]["剑客"]
apply_profession_profile(cfg, "剑客", prof, fallback)
print("after apply:")
print("  attack", cfg["bot"]["attack"])
print("  cooldown", cfg["directional_attack"].get("cooldown"))
print("  turn_delay", cfg["directional_attack"].get("character_turn_delay"))
print("  range", cfg["directional_attack"].get("range_x"), cfg["directional_attack"].get("range_y"))
print("  skip_turn", cfg["directional_attack"].get("skip_turn_if_facing"))
print("  detect_n", cfg["monster_detect"].get("detect_every_n_frames"))
print("  prefixes", cfg["monster_detect"].get("template_name_prefixes"))
print("  track", cfg.get("combat", {}).get("monster_track_enable"))

# switch to 法师 should restore
apply_profession_profile(cfg, "法师", d["professions"]["法师"], fallback)
print("after 法师:")
print("  cooldown", cfg["directional_attack"].get("cooldown"))
print("  detect_n", cfg["monster_detect"].get("detect_every_n_frames"))
print("  skip_turn", cfg["directional_attack"].get("skip_turn_if_facing"))
