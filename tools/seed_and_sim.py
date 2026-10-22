# -*- coding: utf-8 -*-
from pathlib import Path
import copy
import sys
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from src.utils.common import load_yaml, get_cfg_diff, override_cfg, save_yaml
from src.utils.profession_bindings import reset_profession_overrides

tommy = ROOT / "config" / "config_tommy.yaml"
custom = ROOT / "config" / "config_custom.yaml"
dist_custom = ROOT / "dist" / "config" / "config_custom.yaml"
base = load_yaml(str(ROOT / "config" / "config_default.yaml"))

# seed empty custom from tommy
raw = custom.read_text(encoding="utf-8").strip() if custom.exists() else ""
if raw in ("", "{}", "null"):
    custom.write_text(tommy.read_text(encoding="utf-8"), encoding="utf-8")
    print("seeded config_custom from tommy")
if (not dist_custom.exists()) or dist_custom.stat().st_size < 400:
    dist_custom.write_text(tommy.read_text(encoding="utf-8"), encoding="utf-8")
    print("seeded dist config_custom from tommy")

# simulate: load tommy, mutate home attack, reset profession, re-apply home, diff
custom_cfg = load_yaml(str(tommy))
cfg = override_cfg(copy.deepcopy(base), custom_cfg)
fallback = copy.deepcopy(cfg)
# pretend UI home values (剑客-like)
home = {"range_x": 170, "range_y": 100, "cooldown": 0.35, "name": "日丁"}
cfg.setdefault("directional_attack", {})["range_x"] = home["range_x"]
cfg["directional_attack"]["range_y"] = home["range_y"]
cfg["directional_attack"]["cooldown"] = home["cooldown"]
cfg.setdefault("nametag", {})["name"] = home["name"]
cfg["nametag"]["enable"] = True

cfg_to_save = copy.deepcopy(cfg)
reset_profession_overrides(cfg_to_save, fallback)
# WITHOUT re-apply (old bug)
diff_old = get_cfg_diff(base, cfg_to_save)
print("OLD diff after reset keys:", list(diff_old.keys()))
print("OLD directional:", diff_old.get("directional_attack"))
print("OLD nametag:", diff_old.get("nametag"))

# WITH re-apply (new fix)
cfg_to_save2 = copy.deepcopy(cfg)
reset_profession_overrides(cfg_to_save2, fallback)
sec = cfg_to_save2.setdefault("directional_attack", {})
sec["range_x"] = home["range_x"]
sec["range_y"] = home["range_y"]
sec["cooldown"] = home["cooldown"]
nt = cfg_to_save2.setdefault("nametag", {})
nt["name"] = home["name"]
nt["enable"] = True
diff_new = get_cfg_diff(base, cfg_to_save2)
print("NEW diff keys:", list(diff_new.keys()))
print("NEW directional:", diff_new.get("directional_attack"))
print("NEW nametag:", {k: diff_new.get("nametag", {}).get(k) for k in ("name", "enable")})
