# -*- coding: utf-8 -*-
"""Reproduce save_current_config failure without UI."""
from pathlib import Path
import sys, traceback, copy
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from src.utils.common import load_yaml, save_yaml, get_cfg_diff
from src.utils.profession_bindings import reset_profession_overrides, apply_profession_profile
from src.ui.profession_config import ProfessionConfigStore

cfg_base = load_yaml(ROOT / "config" / "config_default.yaml")
# mimic app load: default + custom + maybe tommy?
custom_path = ROOT / "config" / "config_custom.yaml"
print("custom bytes", custom_path.stat().st_size, "repr", repr(custom_path.read_text(encoding="utf-8")[:50]))
try:
    custom = load_yaml(custom_path) if custom_path.stat().st_size else {}
except Exception as e:
    print("load custom FAIL", e)
    custom = {}
print("custom type", type(custom), custom)

tommy = load_yaml(ROOT / "config" / "config_tommy.yaml")
print("tommy keys", list(tommy.keys()) if isinstance(tommy, dict) else tommy)

# merge like app? check main/ui init
# For now: base + override custom + tommy
cfg = copy.deepcopy(cfg_base)
def deep_merge(a, b):
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            deep_merge(a[k], v)
        else:
            a[k] = v
deep_merge(cfg, tommy)
if isinstance(custom, dict):
    deep_merge(cfg, custom)

store = ProfessionConfigStore(str(ROOT / "config" / "config_professions.yaml"))
print("selected", store.selected_name(), "names", store.names())
try:
    store.apply_to_cfg(cfg, store.selected_name() or "剑客", cfg_base)
    print("apply_to_cfg OK")
except Exception:
    traceback.print_exc()

# simulate _write_current_config core
try:
    cfg_to_save = copy.deepcopy(cfg)
    reset_profession_overrides(cfg_to_save, cfg_base)
    cfg_diff = get_cfg_diff(cfg_base, cfg_to_save)
    print("diff keys", list(cfg_diff.keys()) if isinstance(cfg_diff, dict) else cfg_diff)
    out = ROOT / "config" / "_test_save_custom.yaml"
    save_yaml(cfg_diff, str(out))
    print("wrote", out, "size", out.stat().st_size)
    store.save()
    print("profession_store.save OK")
except Exception:
    traceback.print_exc()

# Check KeyError paths in update_cfg_from_main_ui
for key in ("bot", "game_window", "health_monitor", "directional_attack", "hybrid_attack"):
    print("has", key, key in cfg, type(cfg.get(key)))
