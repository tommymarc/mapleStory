## 2026-09-24 — BUFF 芯片可删除，修 +buff 残影

- 新增的 BUFF1/BUFF2… 右上角有 **×**，可移除该芯片及其键位/间隔。
- 重建功能色块时立刻摘掉旧控件，避免默认样式的 `+ buff` 透到按键卡片后面。

## 2026-09-24 — 怪物生命条辅助定位

- 被打过的怪头顶会出现**绿条 + 黑底**（未挨打没有）。模板对 hit/die 动作经常漏检，生命条作为攻击范围内的辅助定位。
- 旧逻辑用 `hp_bar_color: [71, 204, 64]` 精确匹配，Artale 实际填充是 `[0, 243, 0]`，等于没生效。
- 新检测认霓虹绿填充 + 黑色顶边/端帽，把条映射到下方怪身；已有模板命中则只打标不重复计数，没模板时仍当作可打目标。

## 2026-09-23 — 设置：定时关机 + 多 BUFF

- 「定时关机」从顶栏 Tab 移到左下角 **设置** 菜单。
- 键盘设置增加 **+ buff**：依次生成 BUFF1、BUFF2、BUFF3…，各自绑键和间隔，运行时按 `buff_skill.keys` 顺序释放。

## 2026-09-23 — 智能巡逻不再因远处怪而站桩

### 原因
- 搜索框里一有怪就进 Engage，群攻会把 `cmd_move_x` 清成 none。
- Engage 最长 6 秒；野猪领土上几乎总有 2 只怪在大 AoE 框里，所以一直站着打、不左右走。

### 修复
- 只有怪进入定向攻击框或达到群攻触发数才进入 Engage。
- Engage/Scan 在非转向帧恢复左右巡逻；群攻可边走边按 `c`。
- 离开 Engage 看的是攻击范围内有没有怪，不再被搜索框残影拖住。

## 2026-09-22 — 怪物模板 stand/move 各 3 张

- 恢复最初设定：每种怪最多 6 张，`stand` 3 + `move` 3（不再先堆满 6 张站立再丢掉走路图）。
- `select_monster_template_files` 按前缀分别截取；野猪用 stand_0–2 与 move_0–2。

## 2026-09-22 — 恢复打怪灵敏度

### 原因
- Hybrid 群攻冷却被代码 `max(0.7, …)` 锁死，首页设的 0.3s 不生效，实际约 0.5–0.95s 才按一次 `c`。
- 定向攻击框被剑客调参写成 `range_x: 130`，比之前的 180 更窄。
- 怪物必须和攻击框重叠约 1500 像素才出手，贴边的怪经常“框到了但不打”。

### 修复
- 群攻冷却按配置走，只把 0 以下夹到 0.25s；随机抖动从 0.75–1.35 收到 0.9–1.1。
- 重叠判定改为攻击框/怪物框较小者的 15%（至少 80px）。
- `config_custom` / `config_tommy` 的 `range_x` 回到 180；打开短时 monster track，减少漏检闪断。

## 2026-09-22 — 名片定位防误锁（日丁 ROI / 二峰 / 宠物黄字）

### 做了什么
- **Anti false-positive location gate**：重锁定时合并小地图偏置 ROI 与全屏候选；若 ROI 内有可接受命中，则拒绝 ROI 外的“好分数”（避免锁到约 y=271 的假峰）。
- **Ambiguity / second-peak**：最佳峰与远处第二峰都低于阈值时，优先选落在期望 ROI 内的峰。
- **`nametag_match_mask`**：运行时掩膜忽略砂石地形与黄色宠物名牌（如「花蘑菇仔」）；不把模板存成绿幕 PNG。
- **日丁模板**：收紧为三层牌（名+比比拉布+新手冒险家勋章），排除宠物黄字；写入 `日丁.layers.json` layers=3，同步 assets + dist。
- 保留导入 **一层 / 两层 / 三层** 行为。

### 验证（提供的全屏截图）
- Before（旧模板 + 全掩膜 raw）：真峰约 `(654,461) score≈0.149`；假峰区约 `(617,279) score≈0.167`。
- After（紧裁 + mask）：真峰约 `(669,464) score≈0.000`；假峰区约 `(688,287) score≈0.279`（不再赢）。

## 2026-09-22
- 名片导入增加 **一层 / 两层 / 三层** 选择对话框：一层仅名字；两层=名+公会或勋章；三层=名+公会+勋章。可从三层截图裁成一层/两层；层数写入 `nametag/<名>.layers.json` 与 cfg。
- 硬副带匹配跟随导入层数：一层不要求副带；两层要求该条副带；三层要求公会+勋章都匹配（取消无条件强制三层）。
- 名片丢失重锁定：小地图边缘 margin 默认 **10%**（`nametag.minimap_edge_frac`）。距四边都 >10% → 优先搜窗口中部；靠近任一边 → 向屏幕对应侧偏置 ROI，再回退全屏搜索。

## 2026-09-22
- nametag「日丁」: install 3-row template (云名「日丁」+ 公会「比比拉布」+「新手冒险家勋章」); hard match requires all secondary bands when guild+medal present; offset still from name-row top.

# Changelog / 迭代日记


## 2026-09-18 — 边界拖拽精度：与 runtime 统一 ratio↔像素

### 根因
- Preview 用了 `round(ratio * (w-1))` / `x/(w-1)`，而 `smart_patrol._minimap_x_ratio` 与 F6/F7 是 `player_x / w`。
- 右侧误差随 ratio 增大（显示上可偏约 1 个原生像素 × 放大倍数），表现为右边界比左边界更不准。

### 修复
- `map_overlay.py`：`ratio_to_x` → `round(ratio * w)`（夹到 `[0,w-1]`）；新增 `x_to_ratio`；`clamp_range` 保留。
- `BoundsPreviewCanvas` 拖拽/绘制走同一对 helper（含 pan/zoom 的 `_map_rect`）。
- `boundary_recorder.player_x_ratio` 改用共享 `x_to_ratio`（仍仅采样，F7 不自动保存）。

### Tommy 验证
1. 重启新 `dist\MapleStory.exe` → 地图→管理→边界。
2. 站在目标左/右边缘，F6 / F7 采样，或拖拽竖线对齐角色标记 → 「保存边界」。
3. 确认竖线压在角色点上；再开挂机，到边界应刚好折返。


## 2026-09-17 — 边界预览可拖拽 L/R + 放大 + 仅手动保存

### 做了什么
- 地图→管理→边界：更大的小地图预览；左右边界为可拖拽竖线（粗抓取条）；拖拽只改内存 ratio（`round(ratio*(w-1))` 与 overlay/smart_patrol 一致）；滚轮缩放、空白平移。
- F6/F7 仅采样，不再自动写 `patrol.yaml`；只有「保存边界」落盘。
- 重建 `dist\MapleStory.exe`。


## 2026-09-17 · smart_patrol 可靠性：缺绳子告警 + 更安全默认 range + preferred_y 软锁定

### 做了什么
- **缺绳子告警**：`rope_enable` 且 `ropes.yaml` `edges: []` 时，`load_config` / `smart_patrol` 启动打 **error/warning**；UI 启动成功后弹窗 + 状态栏提示「必须先录绳子才能掉层爬回」。真正修复仍是 UI 录绳子（不发明坐标）。
- **更安全默认 range**：`smart_patrol.range` 默认改为 **[0.25, 0.75]**（config_default / config_tommy / .config_tmp；patrol.py 空文档默认同步）。
- **preferred_y 软锁定**：`preferred_y` 为 null 时，在有怪的 Scan/Engage 下若小地图 y 稳定约 **3s**，运行时 soft-lock 到当前 y，使掉层/离带检测在用户未手设前也能工作（写入 `rope_doc`，不改用户配置文件）。
- **Scan 无怪 + 无绳子**：不再静默左右空转；约每 **10s** 再打一次缺绳子日志；仍只在 range 内慢走，不发明绳子。
- 重建 `dist\MapleStory.exe`。

### Tommy 怎么用
1. 启动若弹「必须先录绳子…」→ 地图 → 管理 → 绳子 / 录制 Tab 录绳子（F6/F7）。
2. 未设 preferred_y 时，先在本层打怪几秒即可自动软锁定；掉落后才可能触发 Return（需已有绳子边）。


## 2026-09-17 — 运行监控预览清晰度

### 做了什么
- 将 system.debug_ui_scale 从 0.4 提至 **0.85**，
ps_limit_debug_ui 提至 **8**（default / tommy / .config_tmp）；运行监控 QLabel 上采样改用 **SmoothTransformation** + KeepAspectRatio，避免低分 pixmap 被快速拉伸成糊块。

## 2026-09-17 — 录制 Tab 绳子 UI 精简

### 做了什么
- 录制 Tab：去掉绳子边列表（QListWidget）与「列出当前地图绳子」；仅保留 **录制绳子** 按钮 + 简易文本日志（事件流，非边列表）。
- 绳子边列表/删除仍只在：地图 → 管理 → 绳子。

## 2026-09-17 — 地图 UI 清理 + 边界 F6/F7 采集

### 做了什么
- **旧地图列表按钮移除**：不再显示「录制路线 / 选择怪物 / 编辑路线」（录制/怪物/路线改走管理 Hub）。
- **管理 → 怪物**：去掉「本图关联」中间页；直接进入本图怪物列表勾选编辑（原关联编辑能力）。
- **管理 → 路线**：进入路线列表；右上角 **录制路线**（跳转录制 Tab）；保留 **打开地图文件夹**；新增 **删除选中路线**（确认后只删 route*.png，拒绝 map.png）。
- **管理 → 边界**：新增现场采集会话（停挂机后）— 左缘 **F6** / 右缘 **F7** 用小地图玩家 x 比值写入 patrol.yaml range（左>右自动对调）；亦可手动点按钮；保留表单保存。
- 新增 src/utils/boundary_recorder.py + BoundaryRecorderWorker。
- 重建 dist\MapleStory.exe。

### 新点击路径
1. 地图列表 → **管理** → **怪物** → 勾选 → **保存怪物列表**
2. 地图列表 → **管理** → **路线** → **录制路线** / **删除选中路线** / **打开地图文件夹**
3. 地图列表 → **管理** → **边界** → **开始采集会话 F6/F7** → 左 F6 → 右 F7
4. 绳子仍：管理 → 绳子 → 去录制（录制 Tab）；列表/删除不变

### 未做
- 录制 Tab 的「boundary mode」可选扩展（本次以管理页为主）

## 2026-09-17 — 绳子 UX：管理页只列表，录制走录制 Tab

### 做了什么
- 地图管理 → 绳子：去掉「开始录制会话 / F6 / F7」嵌入式录制；仅列表 / 删除。
- 新增「去录制 / 新增」跳转 **录制** Tab，并预选当前地图（沿用现有「录绳子 F6/F7」）。
- 录制 Tab 绳子日志：`QLabel` 改为带行高的 `QListWidget`，修复显示裁切。
- 地图列表行高裁切修复（见同日条目）一并打进本次 exe。

## 2026-09-17 — 地图列表行高/裁切样式修复

### 做了什么
- 修复「地图列表」行文字垂直裁切（中英文被拦腰切断）、行高过矮、未垂直居中。
- 根因：全局 `QListWidget::item { padding: 6px 10px }` 与自定义 `setItemWidget` 行冲突——stylesheet padding 挤占 item 内容区，而 `sizeHint` 未计入该 padding；叠加「管理」按钮全局 `min-height: 28px`，行被压扁。
- `src/ui/resource_tabs.py`：`mapList` 本地样式 `padding: 0` + `min-height: 44px`；行 `minHeight` 44、垂直居中；管理按钮固定 72×30。
- 重建 `dist\MapleStory.exe`。

### 未做
- 无功能改动

## 2026-09-17 — 地图管理 UI（绳子 / 边界 / 怪物 / 路线）

### 做了什么
- 地图列表每行增加「管理」按钮；进入该地图管理 Hub（堆叠页）。
- Hub 入口：绳子（P0 完整）、边界、怪物、路线。
- 绳子：列表 / 删除 / 录制会话（F6/F7 + 屏上「开始边/保存边」）；录制前若挂机运行会确认停止。
- 边界：写入 `assets/minimaps/<map>/patrol.yaml`（range / preferred_y / preferred_y_tol / rope_enable）；引擎 `load_config` 合并进 `smart_patrol`；并同步 ropes.yaml 的 preferred_*。
- 怪物：查看本图关联 + 跳转现有关联编辑；路线：列出 route*.png、打开文件夹、刷新；深度编辑 stub「后续」。
- 抽取共享录制 API：`src/utils/rope_recorder.py`（CLI `tools/ropeRecorder.py` 仍可用）。
- 测试：`tests/test_patrol_and_delete.py`；重建 `dist\MapleStory.exe`。

### Tommy 怎么用
1. UI → **地图** Tab → 某行点 **管理**。
2. **绳子** → **开始录制会话** → 走到绳旁 **F6 / 开始边** → 爬到另一层 **F7 / 保存边** → 可删边 → **停止录制会话**。
3. Hub → **边界** → 改 range / preferred_y 等 → **保存边界**。
4. Hub 可进 **怪物** / **路线**（路线对 smart_patrol 可选）。

### Pending
- [ ] 深度路线编辑器


## 2026-09-17 · FPS: skip Scan nametag/minimap-OK, stand-only templates, detect every 2 Scan frames, no full-frame copy unless monitor refresh

## 2026-09-17 — Fix MSLogger multi-arg TypeError on startup
- Fixed startup TypeError: converted multi-arg logger.info/warning printf calls to single-string % formatting (load_config smart_patrol + ropeRecorder); rebuilt dist/MapleStory.exe.

## 2026-09-17 — 发版打包（exe rebuild）

### 做了什么
- 运行 `tools\build_exe.bat`（`.venv` + PyInstaller `MapleStoryAutoLevelUp.spec`）重建 `dist\MapleStory.exe`。
- 同步复制 `config/` 与 `assets/`（含 minimaps / monster / nametag 等）到 `dist/`。
- 校验：`dist\MapleStory.exe`、`dist\assets\`、`dist\config` 均存在。

### 如何运行
- `dist\MapleStory.exe`

### Pending
- [x] 下次发版：重建 exe，使 `dist/` 含 `MapleStory.exe` + `config/` + `assets/`

## 2026-09-16 — smart_patrol P2（绳子录边 + Return 跨层）

### 做了什么
- 绳子边存储：`assets/minimaps/{map}/ropes.yaml`（`src/utils/ropes.py` load/save/nearest）。
- 一次攀爬录制：`tools/ropeRecorder.py`（F6 开始 / F7 保存 / F8 列表 / F9 退出）；UI「录制」页增加「录绳子」。
- `smart_patrol` 新相位 **Return**：无怪超时或掉出 preferred band → 走近绳 start → 按住 up/down 到 end → 回 Scan。
- 配置：`smart_patrol.rope_*` / `preferred_y` / `preferred_y_tol`（见 `config_default.yaml`）。
- 引擎 `load_config`：smart_patrol 加载 ropes.yaml；**normal 模式不动**。
- 测试：`tests/test_smart_patrol.py`（edge I/O + Return 状态切换）。
- 文档：更新 `ARCHITECTURE.md`。

### Tommy 怎么录绳子并启用
1. **不要**同时开智能巡逻挂机（避免抢键）。
2. 录制（任选其一）：
   - CLI：`.venv\Scripts\python.exe tools\ropeRecorder.py --map duoluozhuyi-xia --cfg tommy`
   - UI：地图 Tab 选好地图 → 录制 Tab →「录绳子 F6/F7」
3. 走到绳子旁按 **F6**，爬到另一层按 **F7**（可多录几条；F8 看列表）。
4. 确认生成：`assets/minimaps/duoluozhuyi-xia/ropes.yaml`（或 `-shang`）。
5. 启用巡逻：
   ```yaml
   bot:
     mode: smart_patrol
     map: duoluozhuyi-xia
   smart_patrol:
     rope_enable: true
     # preferred_y: 20   # 可选；不填则用 ropes.yaml 里的 preferred_y
   ```
6. 运行：`python -m src.main`（或 UI 选「智能巡逻」）。无需 rebuild exe。

### 未做
- 测谎仪自动过（保持退役）
- 发版 exe 重建

### Pending
- [x] 下次发版：重建 exe
- [x] smart_patrol P2：绳子记录 + 跨层

## 2026-09-16 — smart_patrol P0（单层智能巡逻）

### 做了什么
- 新增 FSM state `smart_patrol`（`src/states/smart_patrol.py`）：Scan（小地图左右） <-> Engage（复用 Hybrid/定向 `update_cmd_by_mob_detection`）。
- 配置：`bot.mode: smart_patrol` + `smart_patrol:` 块（`range` / `turn_point_thres` / `scan_turn_sec` / `engage_timeout_sec` / `no_mob_turn_sec`）。
- `load_config`：smart_patrol **加载怪物模板但不要求 route PNG**（仍需 `bot.map` 对应 `map_mobs_mapping`）。
- UI：运行方式下拉增加「智能巡逻」 / `smart_patrol`。
- 测试：`tests/test_smart_patrol.py`（相位切换、边界转向、超时回 Scan）。
- 文档：更新 `ARCHITECTURE.md`。

### 如何启用（Tommy）
1. **UI**：主页「执行方式」选 **智能巡逻**，选好地图后启动。
2. **YAML**（开发推荐）：在 `config/config_tommy.yaml` 增加：
   ```yaml
   bot:
     mode: smart_patrol
     map: duoluozhuyi-xia   # or your map key
   ```
   然后：`python -m src.main`（或 `python -m src.engine.MapleStoryAutoLevelUp --cfg tommy`）。
3. 攻击模式仍用现有 `bot.attack`（建议 `hybrid`）。名牌继续用于攻击中心；Scan 走路只看小地图黄点。
4. **不需要**画 route；**不需要** rebuild exe。

### 未做（有意延后）
- ~~绳子记录 / 跨层（P2）~~ → 见上方 P2
- 测谎仪自动过（保持退役）
- 发版 exe 重建

### Pending
- [x] smart_patrol P2：绳子记录 + 跨层
- [x] 下次发版：重建 exe，使 `dist/` 仅保留 `MapleStory.exe` + `config/` + `assets/` + `log/`

## 2026-09-16 — 项目瘦身与目录规范化（cleanup）

### 做了什么
- 建立统一静态资源目录 `assets/`（minimaps / monster / nametag / numbers / media / misc / rune / maps），合并原根目录与 `dist/` 下重复资源树。
- 新增 `src/utils/paths.py`，开发态与打包态统一从 `assets/` 加载资源。
- 新增 `docs/`：`CHANGELOG.md` / `ARCHITECTURE.md` / `CONVENTIONS.md`。
- 清理根目录调试垃圾（`_*.png/_*.jpg/_*.py`、临时 crop、route 重建脚本等）。
- 删除多余 PyInstaller spec（`*_v25`…`*_v34`），仅保留 `MapleStoryAutoLevelUp.spec`。
- `build.bat` 移至 `tools/build_exe.bat`，标注「仅发版时使用」，不再作为日常流程。
- 删除已退出运行时的死代码：`RuneSolver` 与 rune 相关 states（FSM 早已只保留 hunting/aux/patrol；测试 `test_rune_removed` 已锁定）。
- 精简 `tools/`：仅保留 `routeRecorder.py`、`mob_maker.py`、`pyi_rth_dll_paths.py`。
- 清理 `__pycache__`、`.codegraph`、各类 `.bak*`、`maps/route_audit` 临时审计产物。

### 未做（有意延后）
- **已实现 P0** `smart_patrol`（单层 Scan/Engage）；绳子/跨层仍延后。
- **未实现** 测谎仪绕过；相关功能保持退役状态。
- **未强制重打 exe**：当前 `dist/MapleStory.exe` 仍按旧相对路径（`minimaps/` 等）读资源；Python 源码已切到 `assets/`。发版时用 `tools/build_exe.bat` 一次打包即可同步。

### Pending（部分已由上方 P0 完成）
- [x] smart_patrol P0 落地
- [x] 下次发版：重建 exe，使 `dist/` 仅保留 `MapleStory.exe` + `config/` + `assets/` + `log/`
