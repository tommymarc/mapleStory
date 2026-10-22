# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
ui = (ROOT/"src/ui/ui.py").read_text(encoding="utf-8")
lines = ui.splitlines()
for i, line in enumerate(lines):
    if "profiles_changed" in line or "open_keyboard" in line or "KeyboardConfig" in line:
        print(f"{i+1}: {line}")

# Test ProfessionConfigStore save on both paths
import sys, traceback
sys.path[:0] = [str(ROOT), str(ROOT/"src")]
from src.ui.profession_config import ProfessionConfigStore
for path in [
    str(ROOT/"config/config_professions.yaml"),
    str(ROOT/"dist/config/config_professions.yaml"),
    "config/config_professions.yaml",
]:
    try:
        s = ProfessionConfigStore(path)
        s.save()
        print("SAVE OK", path, "selected", s.selected_name())
    except Exception:
        print("SAVE FAIL", path)
        traceback.print_exc()

# compile check profession_config full
import py_compile
py_compile.compile(str(ROOT/"src/ui/profession_config.py"), doraise=True)
print("compile OK")

# show _ensure and _sword exist
t = (ROOT/"src/ui/profession_config.py").read_text(encoding="utf-8")
print("ensure", "def _ensure_builtin_profiles" in t)
print("sword", "def _sword_profile" in t)
print("getattr load", "getattr(self, \"_ensure_builtin_profiles\"" in t or "getattr(self, '_ensure_builtin_profiles'" in t)
