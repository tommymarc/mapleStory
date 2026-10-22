# Conventions / 协作约定

中文为主，英文补充。

## 目录职责

| 路径 | 用途 |
|------|------|
| `assets/` | **唯一**静态游戏资源（小地图、怪物模板、名牌、图标等）。编辑资源只改这里。 |
| `config/` | YAML 配置 only |
| `src/` | Python 源码 only |
| `tests/` | 单元 / 回归测试 |
| `tools/` | 少量维护脚本（录路线、打包 runtime hook、怪物导入辅助） |
| `docs/` | 架构说明、约定、**迭代日记（CHANGELOG）** |
| `dist/` | **运行时发版输出**：exe + 运行所需 config/assets 拷贝。不是日常工作区。 |
| `log/` / `screenshot/` | 运行时产物（可 gitignore） |

## 怎么改代码 / 资源

1. **改资源**：放到 `assets/<类别>/...`，不要在项目根再散落 `monster/`、`nametag/` 等。
2. **改配置**：只动 `config/*.yaml`；临时覆盖走 UI 或 `config_custom.yaml` / overrides。
3. **改逻辑**：只动 `src/`；不要在根目录丢 `_debug_*.py`。
4. **迭代说明**：每次有意义的改动写一行到 `docs/CHANGELOG.md`（日期 + 要点）。不要再新建一堆 `*_vNN.spec` 或 ad-hoc 说明 txt。
5. **打包**：默认用 Python 开发运行。**无需每天 rebuild**。仅发版时执行 `tools/build_exe.bat`。
6. **禁止**：为一次小改新增 `MapleStoryAutoLevelUp_vXX_*.spec`；禁止把调试截图/crop 提交到根目录。

## 运行方式

```bash
# 开发（推荐）
python -m src.main

# 无 UI 引擎入口
python -m src.engine.MapleStoryAutoLevelUp --cfg tommy

# 发版 exe（偶尔）
tools\build_exe.bat
# 然后运行 dist\MapleStory.exe
```

路径约定：`src/main.py` 会把 cwd 设为项目根（开发）或 exe 所在目录（frozen）。相对路径均相对该根目录；静态资源前缀为 `assets/`。
