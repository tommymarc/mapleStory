# -*- coding: utf-8 -*-
from pathlib import Path
bat = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\tools\build_exe.bat")
text = bat.read_text(encoding="utf-8", errors="ignore")
needle = '"%PYTHON%" -m PyInstaller --noconfirm MapleStoryAutoLevelUp.spec'
insert = '''echo Running profession store smoke test...
"%PYTHON%" tools\\smoke_profession_store.py
if errorlevel 1 (
    echo Profession store smoke test failed. Aborting build.
    exit /b 1
)

"%PYTHON%" -m PyInstaller --noconfirm MapleStoryAutoLevelUp.spec'''
if "smoke_profession_store.py" in text:
    print("build_exe.bat already has smoke test")
else:
    if needle not in text:
        raise SystemExit("pyinstaller line not found")
    text = text.replace(needle, insert, 1)
    bat.write_text(text, encoding="utf-8")
    print("build_exe.bat patched with smoke gate")
