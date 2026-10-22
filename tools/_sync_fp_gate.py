# -*- coding: utf-8 -*-
from pathlib import Path
import shutil

root = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
ui = (root / "src/ui/ui.py").read_text(encoding="utf-8")
nt = (root / "src/utils/nametag.py").read_text(encoding="utf-8")
eng = (root / "src/engine/MapleStoryAutoLevelUp.py").read_text(encoding="utf-8")
print("rope_record_requested", "rope_record_requested" in ui)
print("layers_ui", "一层" in ui and "三层" in ui)
print("nametag_match_mask", "nametag_match_mask" in nt)
print("pick_nametag_candidate", "pick_nametag_candidate" in nt)
print("engine mask", "nametag_match_mask" in eng)

# Fix rope_record if reintroduced
old = (
    "        self.map_management_tab.record_requested.connect(self.open_recording_for_map)\n"
    "        self.map_management_tab.rope_record_requested.connect(\n"
    "            self.open_rope_recording_for_map\n"
    "        )\n"
)
new = "        self.map_management_tab.record_requested.connect(self.open_recording_for_map)\n"
if old in ui:
    (root / "src/ui/ui.py").write_text(ui.replace(old, new, 1), encoding="utf-8")
    print("fixed rope_record_requested")
elif "rope_record_requested" in ui:
    print("WARNING: rope_record still present, pattern mismatch")

src_png = root / "assets/nametag/日丁.png"
src_json = root / "assets/nametag/日丁.layers.json"
for dest in [root / "dist/assets/nametag", root / "dist/nametag", root / "nametag"]:
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_png, dest / "日丁.png")
    if src_json.exists():
        shutil.copy2(src_json, dest / "日丁.layers.json")
    print("synced", dest)

entry = (root / "tools/_nametag_fp_changelog.md").read_text(encoding="utf-8")
cl = root / "docs/CHANGELOG.md"
old_cl = cl.read_text(encoding="utf-8") if cl.exists() else ""
if "假阳性" not in old_cl and "pick_nametag_candidate" not in old_cl:
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(entry.rstrip() + "\n\n" + old_cl, encoding="utf-8")
    print("changelog prepended")
else:
    print("changelog already updated")
print("DONE")
