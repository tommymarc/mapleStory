"""Make bundled PySide/Shiboken DLL directories visible to Windows loader."""

import os
import sys
import ctypes


_DLL_DIRECTORY_HANDLES = []
_PRELOADED_DLLS = []

if sys.platform.startswith("win") and getattr(sys, "frozen", False):
    bundle_root = getattr(sys, "_MEIPASS", "")
    for package_name in ("shiboken6", "PySide6"):
        dll_dir = os.path.join(bundle_root, package_name)
        if os.path.isdir(dll_dir):
            # Keep the handle alive for the whole process. Closing or garbage
            # collecting it removes the directory from the DLL search path.
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(dll_dir))
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

    # PySide 6.11 links pyside6.abi3.dll to the Shiboken DLL in a sibling
    # package directory. Preloading the small dependency chain makes the
    # layout work reliably in PyInstaller's isolated one-file environment.
    for relative_path in (
        os.path.join("shiboken6", "shiboken6.abi3.dll"),
        os.path.join("PySide6", "Qt6Core.dll"),
        os.path.join("PySide6", "pyside6.abi3.dll"),
        os.path.join("PySide6", "Qt6Gui.dll"),
        os.path.join("PySide6", "Qt6Widgets.dll"),
    ):
        dll_path = os.path.join(bundle_root, relative_path)
        if os.path.isfile(dll_path):
            _PRELOADED_DLLS.append(ctypes.WinDLL(dll_path))
