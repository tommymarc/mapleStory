# -*- coding: utf-8 -*-
from pathlib import Path

# 1) config_default.yaml (source)
p = Path("config/config_default.yaml")
text = p.read_text(encoding="utf-8")
text2 = text.replace(
    "jump_attack_delay_min: 0.1   # seconds between jump and attack (random low)",
    "jump_attack_delay_min: 0.04  # seconds between jump and attack (random low)",
).replace(
    "jump_attack_delay_max: 0.8   # seconds between jump and attack (random high)",
    "jump_attack_delay_max: 0.15  # seconds between jump and attack (random high)",
)
assert text2 != text, "config_default no change"
p.write_text(text2, encoding="utf-8")
print("updated", p)

# 2) dist/config/config_default.yaml
p = Path("dist/config/config_default.yaml")
if p.exists():
    text = p.read_text(encoding="utf-8")
    text2 = text.replace(
        "jump_attack_delay_min: 0.1   # seconds between jump and attack (random low)",
        "jump_attack_delay_min: 0.04  # seconds between jump and attack (random low)",
    ).replace(
        "jump_attack_delay_max: 0.8   # seconds between jump and attack (random high)",
        "jump_attack_delay_max: 0.15  # seconds between jump and attack (random high)",
    )
    p.write_text(text2, encoding="utf-8")
    print("updated", p)

# 3) dist/config/.config_tmp.yaml
p = Path("dist/config/.config_tmp.yaml")
text = p.read_text(encoding="utf-8")
text2 = text.replace("jump_attack_delay_max: 0.8", "jump_attack_delay_max: 0.15")
text2 = text2.replace("jump_attack_delay_min: 0.1", "jump_attack_delay_min: 0.04")
assert "jump_attack_delay_min: 0.04" in text2 and "jump_attack_delay_max: 0.15" in text2
p.write_text(text2, encoding="utf-8")
print("updated", p)

# 4) KeyBoardController defaults + floor clamp
p = Path("src/input/KeyBoardController.py")
text = p.read_text(encoding="utf-8")
repls = [
    ('bot.get("jump_attack_delay_min", 0.1) or 0.1', 'bot.get("jump_attack_delay_min", 0.04) or 0.04'),
    ('bot.get("jump_attack_delay_max", 0.8) or 0.8', 'bot.get("jump_attack_delay_max", 0.15) or 0.15'),
    ("lo = max(0.05, lo)", "lo = max(0.01, lo)"),
]
for a, b in repls:
    assert a in text, f"missing: {a}"
    text = text.replace(a, b, 1)
p.write_text(text, encoding="utf-8")
print("updated", p)

# 5) UI tooltips
for fp in [Path("src/ui/profession_config.py"), Path("src/ui/ui.py")]:
    text = fp.read_text(encoding="utf-8")
    text2 = text.replace("0.1–0.8", "0.04–0.15").replace("0.1-0.8", "0.04-0.15")
    text2 = text2.replace("0.1\u20130.8", "0.04\u20130.15")
    if text2 == text:
        for i, l in enumerate(text.splitlines(), 1):
            if "0.1" in l and "0.8" in l:
                print("FOUND", fp, i, repr(l))
        raise SystemExit(f"no tooltip change in {fp}")
    fp.write_text(text2, encoding="utf-8")
    print("updated", fp)

# 6) CHANGELOG one line + refresh delay mentions in same-day section
cl = Path("docs/CHANGELOG.md")
ct = cl.read_text(encoding="utf-8")
ct2 = ct.replace("0.1–0.8 秒", "0.04–0.15 秒").replace("0.1\u20130.8 秒", "0.04\u20130.15 秒")
ct2 = ct2.replace("间隔约 0.1–0.8 秒", "间隔约 0.04–0.15 秒").replace(
    "间隔约 0.1\u20130.8 秒", "间隔约 0.04\u20130.15 秒"
)
one = "## 2026-09-17 · 跳打延迟调低到 0.04–0.15 秒（更接近人手）\n\n"
if "跳打延迟调低到 0.04" not in ct2:
    ct2 = ct2.replace("# Changelog / 更新日志\n\n", "# Changelog / 更新日志\n\n" + one, 1)
cl.write_text(ct2, encoding="utf-8")
print("updated", cl)
print("DONE edits")
