from pathlib import Path
p = Path("src/input/KeyBoardController.py")
kb = p.read_text(encoding="utf-8")
old = (
    "            ##########################\n"
    "            ### Left-Right Command ###\n"
    "            ##########################\n"
    "            if self.cmd_left_right == \"left\":\n"
)
new = (
    "            ##########################\n"
    "            ### Left-Right Command ###\n"
    "            ##########################\n"
    "            # During jump-attack delay, keep pathfinding direction held.\n"
    "            if self._jump_attack_pending and self._jump_attack_hold_dir in (\"left\", \"right\"):\n"
    "                if self.cmd_left_right in (\"none\", \"stop\", \"\"):\n"
    "                    self.cmd_left_right = self._jump_attack_hold_dir\n"
    "            if self.cmd_left_right == \"left\":\n"
)
if old not in kb:
    raise SystemExit("marker not found")
if "During jump-attack delay" not in kb:
    kb = kb.replace(old, new, 1)
    p.write_text(kb, encoding="utf-8")
    print("injected")
else:
    print("already injected")
import ast
ast.parse(p.read_text(encoding="utf-8"))
print("syntax OK")
