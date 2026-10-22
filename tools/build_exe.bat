@echo off
setlocal
cd /d "%~dp0\.."

rem ============================================================
rem  RELEASE ONLY — do not run this as a daily workflow.
rem  Dev:  python -m src.main
rem ============================================================

set "APP_NAME=MapleStory"
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

if exist "dist\%APP_NAME%.exe" del /q "dist\%APP_NAME%.exe"
if exist "dist\%APP_NAME%.exe" (
    echo Failed to replace the EXE. Close the running application and try again.
    exit /b 1
)

if exist "release" rmdir /s /q "release"
if exist "%APP_NAME%.zip" del /q "%APP_NAME%.zip"
if exist "build" rmdir /s /q "build"

echo Running profession store smoke test...
"%PYTHON%" tools\smoke_profession_store.py
if errorlevel 1 (
    echo Profession store smoke test failed. Aborting build.
    exit /b 1
)

"%PYTHON%" -m PyInstaller --noconfirm MapleStoryAutoLevelUp.spec
if errorlevel 1 exit /b %errorlevel%

copy /y "README.md" "dist\" >nul
if exist "README.zh.md" copy /y "README.zh.md" "dist\" >nul

if not exist "dist\config" mkdir "dist\config"
for %%F in (config\*) do (
    if not exist "%%F\" (
        if /i not "%%~nxF"=="config_custom.yaml" if /i not "%%~nxF"=="config_professions.yaml" if /i not "%%~nxF"=="config_resource_overrides.yaml" copy /y "%%F" "dist\config\" >nul
    )
)
for %%F in (config_custom.yaml config_professions.yaml config_resource_overrides.yaml) do (
    if not exist "dist\config\%%F" if exist "config\%%F" copy /y "config\%%F" "dist\config\" >nul
)
for /d %%D in (config\*) do (
    xcopy "%%D" "dist\config\%%~nxD\" /d /e /i /y >nul
)

rem Ship assets beside the exe (new layout).
if exist "dist\assets" rmdir /s /q "dist\assets"
xcopy "assets" "dist\assets\" /e /i /y >nul

rem Remove legacy top-level resource dirs left by older builds (optional cleanup).
for %%D in (maps media minimaps misc monster nametag numbers rune) do (
    if exist "dist\%%D" rmdir /s /q "dist\%%D"
)

echo.
echo Build complete: dist\%APP_NAME%.exe
echo Runtime layout: dist\MapleStory.exe + dist\config + dist\assets
