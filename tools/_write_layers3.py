from pathlib import Path
import json
root = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
for base in [root/"assets/nametag", root/"dist/assets/nametag", root/"dist/nametag", root/"nametag"]:
    base.mkdir(parents=True, exist_ok=True)
    p = base / "日丁.layers.json"
    p.write_text(json.dumps({"layers": 3}, ensure_ascii=False, indent=2), encoding="utf-8")
    png = base / "日丁.png"
    print(base.name, "png", png.exists(), png.stat().st_size if png.exists() else 0, "json", p.exists())
