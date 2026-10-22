from pathlib import Path

changelog = Path("docs/CHANGELOG.md")
text = changelog.read_text(encoding="utf-8")
entry = """# Changelog / 更新日志

## 2026-09-17 · 战士跳打模式（jump-attack）

### 做什么
- **UI**：主攻类型旁新增「跳打模式」勾选（键盘配置页 + 首页攻击参数）。
- **配置**：`bot.jump_attack`（默认 `false`）；延迟 `bot.jump_attack_delay_min/max`（默认 **0.1–0.8 秒** 随机）。
- **战斗**：勾选后，发出主攻/群攻时：**断按跳跃 → 随机延迟 → 断按攻击**；寻路方向键在组合期间保持按住。
- **边界**：smart_patrol 近/过边界时抑制跳跃，改为原地攻击（不外跳）。
- 未勾选时行为不变。Scan 纯走路、BUFF 不受影响。
- 重建 `dist\\MapleStory.exe`。

### Tommy 怎么用
1. 职业键盘配置（或首页攻击参数）勾选「跳打模式」并保存。
2. 跑图/智能巡逻中移动攻击时观察：先跳后打，间隔约 0.1–0.8 秒。
3. 靠边时应变为原地攻击、不向外跳。

"""
if "跳打模式（jump-attack）" not in text:
    # replace first heading line block
    if text.startswith("\ufeff"):
        body = text[1:]
        bom = "\ufeff"
    else:
        body = text
        bom = ""
    if body.startswith("# Changelog"):
        # drop first line, prepend new entry which includes heading
        rest = body.split("\n", 1)[1]
        # rest still starts with blank or ## 
        text = bom + entry + rest.lstrip("\n")
        # Avoid duplicated title: entry already has # Changelog
        # But rest may start with more content under old title - we removed first line only.
        # If rest starts with blank then ## that's fine.
    else:
        text = bom + entry + body
    changelog.write_text(text, encoding="utf-8")
    print("CHANGELOG updated")
else:
    print("CHANGELOG already has entry")

# show head
print(Path("docs/CHANGELOG.md").read_text(encoding="utf-8")[:500])
