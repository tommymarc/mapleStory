# Architecture / 当前架构

## 运行模式（FSM）

当前引擎状态机注册：

- `hunting` — 正常挂机（路线 + 打怪 + Hybrid/定向攻击）← `bot.mode: normal`
- `aux` — 辅助模式（较宽松分辨率等）
- `patrol` — 简易巡逻（屏幕比例左右走；不跑怪物模板检测）
- `smart_patrol` — 智能巡逻（小地图 Scan <-> Engage <-> Return；无需 route PNG）

配置入口：`config/config_default.yaml` → `bot.mode`: `normal` | `aux` | `patrol` | `smart_patrol`。  
`smart_patrol` 参数块：`smart_patrol:`（`scan_turn_sec` / `engage_timeout_sec` / `no_mob_turn_sec` / `range` / rope_*）。

核心链路：

```
UI (src/ui) → AutoBotController → MapleStoryAutoBot (engine)
       ↓
  KeyBoardController / GameWindowCapturor / HealthMonitor
       ↓
  FSM states: hunting | aux | patrol | smart_patrol
```

定位：小地图颜色点 +（可选）名牌模板匹配（`assets/nametag/`）。  
- `smart_patrol` Scan / Return：**小地图为主**（`loc_player_minimap`）  
- 攻击中心：仍走现有 `get_player_location()`（名牌优先，不破坏双行名牌）  
打怪：轮廓 / 模板（`assets/monster/`）+ Hybrid AoE / 定向攻击（`smart_patrol` 复用 `update_cmd_by_mob_detection`）。  
资源路径：统一经 `src/utils/paths.py` → `assets/...`。


## Phase roadmap (Tommy)

- **Phase1 (current priority)**: stable **bounds** + **smart_patrol Scan/Engage** + **attack monsters** inside `patrol.yaml` range. `smart_patrol.rope_enable` defaults **false** — no Return / rope climb macros.
- **Boundary always wins over chase**: at/past range edges, never walk further outward toward out-of-range mobs; stand/face inward and attack in place (Hybrid AoE OK). Clamp after every mob-detection update.
- **Phase2 (deferred)**: rope jump+up macros / inventing rope coords — do not invest until Phase1 is solid.

## smart_patrol（P0 + P2）

实现：`src/states/smart_patrol.py`，内部相位 `scan` <-> `engage` <-> `return`。

- **Scan**：按小地图 x 比例在 `smart_patrol.range` 内左右走；`scan_turn_sec` 强制转向。
- **Engage**：附近有怪 / engage-hold / soft track 时停扫，用 Hybrid/定向攻击。
- **回 Scan**：无怪持续 `no_mob_turn_sec`，或 Engage 超过 `engage_timeout_sec`。
- **Return（P2，默认关闭）**：仅当 `rope_enable: true` 且有绳子边时；掉出 `preferred_y ± preferred_y_tol` 或 Scan 无怪超时 → 走向绳子。**Phase1 默认 `rope_enable: false`，不启动 Return。**
- **绳子数据**：`assets/minimaps/{map}/ropes.yaml`（`src/utils/ropes.py` 读写）。录制：`tools/ropeRecorder.py` 或 UI「录制」页「录绳子」。
- **不需要** `route*.png`；仍需要 `bot.map` 以加载该图绑定的怪物模板。
- **未做**：测谎仪自动过（保持退役）。

启用方式见 `docs/CHANGELOG.md`（UI 选「智能巡逻」或 YAML `bot.mode: smart_patrol`）。

## 已退役（保留测试锁定）

- Rune 求解器与 `finding_rune` / `near_rune` / `solving_rune` states（源码已删；`tests/test_rune_removed.py`）
- auto_pickup / lie_detector（`tests/test_retired_features.py`）
- 不要在未评审前把上述能力加回主路径


## 地图管理 UI

路径：`地图` Tab → 行内 **管理** → Hub（绳子 / 边界 / 怪物 / 路线）。

- 绳子：`assets/minimaps/{map}/ropes.yaml`（`src/utils/ropes.py` + `src/utils/rope_recorder.py`）
- 边界：`assets/minimaps/{map}/patrol.yaml`（`src/utils/patrol.py`）；`load_config` 合并覆盖全局 `smart_patrol.range` / `preferred_y*` / `rope_enable`
- 怪物：读 `map_mobs_mapping`（含 overrides）；编辑复用原「选择怪物」页
- 路线：列出 `route*.png`；smart_patrol 不强制；深度编辑后续

实现：`src/ui/map_manage.py` + `MapManagementTab` 堆叠页。

## `src/legacy/`

旧实现快照，**不参与**现行 UI/FSM。仅供对照；新功能不要往里加。
