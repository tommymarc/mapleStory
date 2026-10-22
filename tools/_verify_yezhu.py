# -*- coding: utf-8 -*-
from pathlib import Path
import yaml

root = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
print("map.png", (root / "assets/minimaps/yezhulingtu/map.png").exists())
print("野猪 stand", (root / "assets/monster/野猪/stand_0.png").exists())
print("dist map", (root / "dist/assets/minimaps/yezhulingtu/map.png").exists())
print("dist 野猪", (root / "dist/assets/monster/野猪/stand_0.png").exists())
print("monsters", [p.name for p in (root / "assets/monster").iterdir() if p.is_dir()])
tommy = yaml.safe_load((root / "config/config_tommy.yaml").read_text(encoding="utf-8"))
print("tommy map", tommy["bot"]["map"])
for rel in ["config/config_resource_overrides.yaml", "dist/config/config_resource_overrides.yaml"]:
    ov = yaml.safe_load((root / rel).read_text(encoding="utf-8"))
    print(rel, "yezhulingtu mobs", (ov.get("map_mobs_mapping") or {}).get("yezhulingtu"))
    print(rel, "eng", (ov.get("eng_to_cn") or {}).get("yezhulingtu"))
# fix source overrides map_mobs if broken
src = root / "config/config_resource_overrides.yaml"
ov = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
mobs = ov.setdefault("map_mobs_mapping", {})
# use same as dist if available
dist = yaml.safe_load((root / "dist/config/config_resource_overrides.yaml").read_text(encoding="utf-8"))
want = (dist.get("map_mobs_mapping") or {}).get("yezhulingtu") or ["野猪"]
# only keep monsters that exist
existing = {p.name for p in (root / "assets/monster").iterdir() if p.is_dir()}
want = [m for m in want if m in existing] or ["野猪"]
mobs["yezhulingtu"] = want
if "yezhudelingdi" in (dist.get("map_mobs_mapping") or {}):
    wd = [m for m in dist["map_mobs_mapping"]["yezhudelingdi"] if m in existing]
    if wd:
        mobs["yezhudelingdi"] = wd
eng = ov.setdefault("eng_to_cn", {})
eng["yezhulingtu"] = "yezhulingtu"
eng["野猪"] = "野猪"
src.write_text(yaml.safe_dump(ov, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("fixed src overrides", ov)
print("patrol", (root / "assets/minimaps/yezhulingtu/patrol.yaml").read_text(encoding="utf-8"))
