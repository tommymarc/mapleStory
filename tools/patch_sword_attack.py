# -*- coding: utf-8 -*-
from pathlib import Path
import re
import py_compile

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")

# 1) YAML configs
for rel in [
    "config/config_professions.yaml",
    "dist/config/config_professions.yaml",
]:
    p = ROOT / rel
    if not p.exists():
        print("missing", p)
        continue
    t = p.read_text(encoding="utf-8")
    # Only touch 剑客 directional_attack block — replace the three keys nearby
    # Safer: replace whole overrides directional_attack section under 剑客
    old = """    overrides:
      combat:
        monster_track_enable: true
        monster_track_ttl_sec: 0.5
      directional_attack:
        character_turn_delay: 0.03
        cooldown: 0.35
        range_x: 170
        range_y: 100
        skip_turn_if_facing: true
"""
    new = """    overrides:
      combat:
        monster_track_enable: true
        monster_track_ttl_sec: 0.5
      directional_attack:
        character_turn_delay: 0.03
        cooldown: 0.35
        range_x: 130
        range_y: 80
        skip_turn_if_facing: true
"""
    if old in t:
        t = t.replace(old, new, 1)
        p.write_text(t, encoding="utf-8")
        print("yaml patched", rel)
    elif "range_x: 130" in t and "剑客" in t:
        print("yaml already 130", rel)
    else:
        # fallback regex within file for 剑客 range
        t2, n = re.subn(
            r"(剑客:[\s\S]*?directional_attack:[\s\S]*?)range_x:\s*170",
            r"\1range_x: 130",
            t,
            count=1,
        )
        t2, n2 = re.subn(
            r"(剑客:[\s\S]*?directional_attack:[\s\S]*?)range_y:\s*100",
            r"\1range_y: 80",
            t2,
            count=1,
        )
        if n or n2:
            p.write_text(t2, encoding="utf-8")
            print("yaml regex patched", rel, n, n2)
        else:
            print("WARN yaml no change", rel)

# 2) Builtin sword profile in profession_config.py
pc = ROOT / "src" / "ui" / "profession_config.py"
text = pc.read_text(encoding="utf-8")
# Common patterns in _sword_profile
repls = [
    ('"range_x": 170', '"range_x": 130'),
    ("'range_x': 170", "'range_x': 130"),
    ('"range_y": 100', '"range_y": 80'),
    ("'range_y': 100", "'range_y': 80"),
]
# Only within sword profile — find _sword_profile method
m = re.search(r"def _sword_profile\([\s\S]*?(?=\n    def |\nclass |\Z)", text)
if not m:
    # maybe staticmethod
    m = re.search(r"_sword_profile\([\s\S]*?(?=\n    def |\nclass |\Z)", text)
if not m:
    raise SystemExit("_sword_profile not found")
block = m.group(0)
new_block = block
for a, b in repls:
    new_block = new_block.replace(a, b)
# Also ensure cooldown stays 0.35 (already)
if new_block == block and "130" not in block:
    # try without quotes spacing
    new_block = re.sub(r"range_x\s*:\s*170", "range_x: 130", block)
    new_block = re.sub(r"range_y\s*:\s*100", "range_y: 80", new_block)
if new_block == block:
    print("profession_config: no numeric change needed or already updated")
    print(block[:500])
else:
    text = text[: m.start()] + new_block + text[m.end() :]
    pc.write_text(text, encoding="utf-8")
    print("profession_config patched")

py_compile.compile(str(pc), doraise=True)
print("compile OK")

# Verify
import yaml
for rel in ["config/config_professions.yaml", "dist/config/config_professions.yaml"]:
    d = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    sw = d["professions"]["剑客"]["overrides"]["directional_attack"]
    print(rel, sw.get("range_x"), sw.get("range_y"), sw.get("cooldown"))
print("DONE")
