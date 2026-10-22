from pathlib import Path
import yaml
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
d = yaml.safe_load((ROOT/"config/config_professions.yaml").read_text(encoding="utf-8"))
print(yaml.safe_dump(d["professions"]["剑客"]["overrides"], allow_unicode=True))
