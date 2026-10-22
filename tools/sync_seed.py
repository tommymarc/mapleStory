# -*- coding: utf-8 -*-
from pathlib import Path
import re

UI = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\profession_config.py")
text = UI.read_text(encoding="utf-8")
print("has max_above", "max_above_player_y" in text)
print("has diff 0.28", "0.28" in text and "剑客" in text)
# show 剑客-related slices
idx = text.find("剑客")
while idx != -1:
    print("---", idx, "---")
    print(text[max(0, idx-80): idx+400])
    idx = text.find("剑客", idx+1)
    if text.find("剑客", idx) > idx + 5000:
        break
    # limit prints
    if text.count("剑客") > 8:
        # print only first 3 occurrences context
        break
