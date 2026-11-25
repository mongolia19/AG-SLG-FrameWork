# AG-SLG-FrameWork 剧本与引擎解耦重构计划

## 1. 背景与问题诊断

当前代码库（含已提交的 `island_survival` 兼容代码和未提交的 `wow_elwynn_rpg` Boss/血蓝改动）存在明显的**剧本逻辑污染框架引擎**问题：

1. **前端 HUD 硬编码剧本界面**（`web/src/components/play/GameHUD.tsx`、`PlayView.tsx`、`App.tsx`）：
   - `GameHUD.tsx` 写死了 `isSurvivalMode`（荒岛体力/水分/饱食度/体温、头部 `SUR:` 标识）、`showVanguardTracker`（`fargodeep_entrance` 狗头人与护卫蛛两波进度）、`bossActive`（`蜘蛛领主·阿拉克诺斯` 血蓝条、阶段徽章、5 张 Boss 技能卡和 WoW 伤害公式说明）。
   - `PlayView.tsx` 硬编码 `scenarioId === 'island_survival'` / `'wow_elwynn_rpg'` 的开场白分支。
   - `App.tsx` 硬编码 3 个固定剧本的标题与 emoji 前缀。
2. **后端桥接层硬编码剧本规则与状态机**（`server/agui_bridge.py`）：
   - `ITEM_META` 硬编码了荒岛与艾尔文两个剧本的 20+ 条道具描述与图标。
   - `SCENE_SCOPED_STRUCT_DEFAULTS` 与 `SURVIVAL_CLAMP_100` 硬编码荒岛变量名。
   - `GameSession.apply_delta` 中 `variables_delta` 硬编码 `boss_hp` / `boss_mp` / `boss_minions` 封顶逻辑。
   - `build_play_prompt` 硬编码 WoW Boss 战况/伤害公式，以及荒岛金属盒/打火机/生火烤蟹红线。
   - `evaluate_agent_adjudication` 硬编码荒岛道具/生理状态与 WoW Boss 抗毒/协同/蛛网/幼蛛修正值。
   - `_match_freeform_action` 与 `generate_fallback_turn` 硬编码 `island_survival` / `wow_elwynn_rpg` / `black_crow_manor` 关键词路由与合成配方。
   - `stream_play` 末尾硬编码 180 行蜘蛛领主三阶段切换、减伤 0.55 倍率、`"幽暗蛛王丝"` 掉落与 `level = 4` 晋升逻辑。

**设计原则（遵循 `$ponytail` 最小完备改动）**：
- **引擎层**只保留通用能力：AG-UI 协议桥接、声明式 `hud_widgets` 渲染、通用条件/增量/规则解释器、Prompt 注入口。
- **剧本层 + Agent（via AG-UI `STATE_DELTA`）**承载全部专属内容：开场白、物品目录、数值上下限、检定规则、DM 玩法规则（`dm_rules`）、以及所有专属状态栏/Boss 面板/阶段追踪器（`hud_widgets`）。

---

## 2. 目标架构与协议设计

### 2.1 AG-UI 声明式面板协议：`hud_widgets`

不新增自定义 AG-UI 事件类型，直接复用现有 `STATE_DELTA`（JSON Patch `path: "/hud_widgets"`）与 `PlayerState.hud_widgets: List[HUDWidget]`：

- **支持 3 种通用原语**（覆盖 Boss 战、波次追踪、生存指标、理智/好感/声望等所有剧本 UI）：
  1. `metrics`（紧凑数值/进度条带）：
     - `items`: `[{ id, label, value?, max?, unit?, icon?, color?, value_ref?, max_ref? }]`
     - 支持通过 `value_ref`（如 `"attributes.stamina"`、`"variables.boss_hp"`）实时绑定状态，无需每回合重发整个 widget。
  2. `tracker`（多步骤/波次进度条）：
     - `title`、`icon?`、`steps: [{ label, status?: "done"|"active"|"locked", done_when?: Condition, active_when?: Condition }]`
  3. `panel`（通用遭遇/Boss/事件面板）：
     - `title`、`subtitle?`、`tone?`（`danger`|`amber`|`sky`|`purple`）、`when?: Condition`
     - `badges?: [{ text, tone?, when? }]`
     - `bars?: [{ label, value?, max?, value_ref?, max_ref?, color? }]`
     - `cards_title?`、`cards?: [{ title, desc, tone? }]`（可折叠详情卡片）
     - `footer?`
- **双通道更新**：
  - **剧本 YAML**：可在 `initial_player_state.hud_widgets` 或动作 `on_success`/`on_failure` 中声明初始或阶段性面板。
  - **Agent 运行时**：可通过 ```state_delta``` 的 `hud_widgets`（按 `id` upsert 新增或更新）与 `remove_hud_widgets`（按 `id` 移除）自主生成或撤除剧本专属界面。

### 2.2 通用剧本配置模型（`server/scenario_manager.py` `WorldSpec` & `ActionOption`）

在 `WorldSpec` 新增纯声明式可选字段（引擎零感知具体剧本名称）：
- `icon: str = ""`、`sort_order: int = 100`、`opening_narration: Optional[str] = None`
- `dm_rules: Optional[str] = None`（透传给 DM Prompt，承载剧本专属玩法/伤害公式/阶段规则）
- `item_catalog: Dict[str, Dict[str, Any]]`（替代引擎写死的 `ITEM_META`）
- `unique_items: List[str]`（替代写死的唯一道具列表）
- `scene_scoped_defaults: Dict[str, Any]`（替代 `SCENE_SCOPED_STRUCT_DEFAULTS`）
- `attribute_bounds: Dict[str, List[int]]`（替代 `SURVIVAL_CLAMP_100` 与体温硬编码）
- `variable_bounds: Dict[str, Dict[str, Any]]`（支持 `min` / `max` / `max_var`，替代 `boss_hp` 特判）
- `adjudication_rules: List[Dict[str, Any]]`（数据驱动检定修正：`when` 条件 / `outfit_slot` / `skill_in` / `action_keywords` / `not_action_keywords` / `mod` / `label`）
- `fallback_recipes: List[Dict[str, Any]]` 与 `default_fallback: Optional[Dict[str, Any]]`（数据驱动离线兜底逻辑）
- `ActionOption` 新增 `keywords: List[str]` 与 `intent_guard: Optional[Dict[str, Any]]`（替代 `_match_freeform_action` 写死的 `kw_map`）

---

## 3. 分步实施清单

1. **后端模型与条件引擎（`server/scenario_manager.py`）**：
   - 在 `PlayerState` 增加 `hud_widgets: List[Dict[str, Any]]` 及私有运行态 `_scenario_id`（不序列化，供无参调用检索 `WorldSpec`）。
   - 扩展 `WorldSpec` 与 `ActionOption` 上述通用字段；`list_scenario_summaries` 按 `world.sort_order` 排序并返回 `icon`、`opening_narration`。
2. **后端 AG-UI 桥接重构（`server/agui_bridge.py`）**：
   - 删除 `ITEM_META`、`SCENE_SCOPED_STRUCT_DEFAULTS`、`SURVIVAL_CLAMP_100`、WoW Boss 状态机（`2122–2300` 行）、WoW/荒岛硬编码 Prompt 与兜底分支、`_match_freeform_action` 硬编码词表。
   - `GameSession.apply_delta` 支持通用 `hud_widgets`（按 `id` upsert）与 `remove_hud_widgets`，并按剧本 `attribute_bounds` / `variable_bounds` / `scene_scoped_defaults` / `unique_items` / `item_catalog` 执行。
   - `build_play_prompt` 改为通用 AG-UI 协议说明（含 `hud_widgets` 用法）+ 注入 `scenario.world.dm_rules`。
   - `evaluate_agent_adjudication` 改为纯通用属性 + 剧本 `adjudication_rules` 求值。
   - `_match_freeform_action` 与 `generate_fallback_turn` 改为读取 `ActionOption.keywords` 与 `WorldSpec.fallback_recipes` / `default_fallback`。
3. **前端通用渲染重构（`web/src/types.ts`、`PlayView.tsx`、`GameHUD.tsx`、`App.tsx`）**：
   - `types.ts` 定义 `HUDWidget` 与 `WorldConfig` 新增字段。
   - `PlayView.tsx` 在 `applyStateDeltas` 与 `hydrateMissingStateDefaults` 中同步 `/hud_widgets`；开场白优先取 `world.opening_narration || initialScene.description`。
   - `GameHUD.tsx` 删除 `isSurvivalMode`、`showVanguardTracker`、`bossActive` 及全部荒岛/WoW 写死 JSX；新增通用 `<DynamicHudWidgets />` 渲染 `metrics` / `tracker` / `panel`；头部属性栏按当前 `attributes` 动态展示。
   - `App.tsx` 使用后端返回的 `icon` 与 `title`，移除硬编码剧本列表。
4. **剧本内容迁移（`scripts/island_survival/`、`scripts/wow_elwynn_rpg/`、`scripts/black_crow_manor/`）**：
   - `island_survival`：将 `hud_widgets`（体力/水分/饱食度/体温 `metrics`）、`item_catalog`、`unique_items`、`scene_scoped_defaults`、`attribute_bounds`、`adjudication_rules`、`fallback_recipes`、`dm_rules`、`opening_narration` 迁入 `world.yaml`；将 `keywords` 迁入各场景动作 YAML。
   - `wow_elwynn_rpg`：将战斗公式、Boss 三阶段规则、MP 规则迁入 `world.yaml` `dm_rules` 与 `variable_bounds`/`adjudication_rules`；将前哨波次 `tracker` 与 Boss `panel` 迁入对应场景动作 `on_success`（同时支持 Agent 运行时动态通过 AG-UI `hud_widgets` 驱动）。
   - `black_crow_manor`：补充 `icon`、`opening_narration`、`dm_rules`、`default_fallback`。
5. **测试更新与全量验证**：
   - 修复/重构 `tests/test_wow_boss_and_vitals.py` 与 `tests/test_wow_combat_and_vitals.py`（移除对引擎硬编码蜘蛛领主公式的断言，改为验证 `hud_widgets`、`dm_rules` 注入、通用 `variables_delta` 与剧本 YAML 驱动流转，并新增合成剧本测试证明引擎零耦合）。
   - 运行全部后端 `pytest` 与前端 `npm --prefix web run build` 验证通过。
