# tools/

保留的维护脚本：

| 脚本 | 用途 |
|------|------|
| `ropeRecorder.py` | smart_patrol：一次攀爬录绳子边 → `assets/minimaps/<map>/ropes.yaml`（实现见 `src/utils/rope_recorder.py`，UI 管理页共用） |
| `routeRecorder.py` | 录制小地图路线到 `assets/minimaps/<map>/` |
| `mob_maker.py` | 怪物资源辅助 |
| `pyi_rth_dll_paths.py` | PyInstaller runtime hook |
| `build_exe.bat` | **仅发版**时打包到 `dist/` |

不要把调试脚本、一次性实验丢进本目录。
