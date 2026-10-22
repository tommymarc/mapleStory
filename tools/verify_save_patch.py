# -*- coding: utf-8 -*-
from pathlib import Path
ui = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\ui.py").read_text(encoding="utf-8")
i = ui.find("def save_current_config")
j = ui.find("\n    def ", i+1)
block = ui[i:j]
print(block)
print("---")
print("OSError count", ui.count("except (OSError, ValueError)"))
print("Exception save", "except Exception as error:" in block)
prof = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\profession_config.py").read_text(encoding="utf-8")
k = prof.find("def _save")
print(prof[k:k+450])
