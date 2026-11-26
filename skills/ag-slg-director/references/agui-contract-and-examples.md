# AG-SLG-FrameWork AG-UI 声明式协议与案例速查

> 本文档面向 **Studio Co-pilot** 与 **剧本作者**，列出框架已原生渲染和解析的完整字段，无需修改 `server/` 或 `web/` 源码即可组装复杂玩法与动态界面。
> 注：Play DM 不直接构造底层 RFC 6902 JSON-Patch，而是通过末尾 ````state_delta```` JSON 块由 `AGUIBridge` 自动转译为标准 AG-UI `STATE_DELTA` 事件。

---

## 1. Play 回合 ````state_delta```` 完整字段契约

```json
{
  "current_scene": "目标场景ID（仅切换场景时填写）",
  "hp_delta": -10,
  "mp_delta": -20,
  "max_hp_delta": 0,
  "max_mp_delta": 0,
  "san_delta": -3,
  "gold": 65,
  "attributes_delta": {"strength": 1},
  "time_cost": 1,
  "add_inventory": [{"id": "item_id", "name": "道具名", "desc": "描述", "icon": "/assets/items/x.png"}],
  "remove_inventory": ["consumed_item_id"],
  "outfit": {"outer": {"id": "coat", "name": "防风大衣", "desc": "防寒", "tag": "保暖"}},
  "unequip_outfit": ["outer"],
  "skills": [],
  "learn_skills": [{"id": "sk_1", "name": "技能名", "desc": "简介", "effect": "作用", "cost": "15 MP", "cooldown": "1回合", "level": 1, "tag": "攻击"}],
  "remove_skills": ["obsolete_skill_id"],
  "variables": {"boss_phase": 2, "boss_armor_broken": true},
  "variables_delta": {"boss_hp": -45, "boss_mp": -20},
  "add_structures": [
    {
      "id": "ally_scout",
      "name": "斥候艾莲娜",
      "image": "/assets/characters/elena.png",
      "side": "left",
      "category": "structure",
      "tag": "HP 110/110",
      "caption": "随行支援",
      "tooltip": "弓箭手同伴",
      "scene_id": "当前场景ID"
    }
  ],
  "hud_widgets": [],
  "replace_hud_widgets": false,
  "remove_hud_widgets": ["obsolete_widget_id"],
  "available_actions": [
    {"id": "dyn_1", "label": "临时派生行动", "type": "check", "skill": "agility", "difficulty": 11}
  ],
  "visuals": {
    "background": "/assets/scenes/room.png",
    "foreground": "",
    "hero_image": "/assets/illustrations/clue.png",
    "atmosphere": "幽暗潮湿"
  },
  "check_result": {
    "skill": "agility",
    "difficulty": 12,
    "roll": 15,
    "modifier": 2,
    "total": 17,
    "isSuccess": true,
    "outcome": "critical_success",
    "outcome_label": "卓越成功",
    "reason": "属性修正+2",
    "message": "身形轻盈地避开伏击"
  }
}
```

- `outfit` 常用槽位：`head`、`outer`、`top`、`bottom`、`shoes`、`accessory`、`wrist`、`neck`。
- `add_structures` 挂载到 `variables.built_structures` 后会自动随 `scene_id` 显示在左右侧边栏（`side: "left"` 适合友军/设施，`side: "right"` 适合敌对目标/环境）。

---

## 2. 声明式 `hud_widgets` 原语（由 `GameHUD.tsx` 直接渲染）

`hud_widgets` 可放在 `world.yaml` 的 `initial_player_state.hud_widgets`、动作的 `on_success.hud_widgets`，或回合 ````state_delta.hud_widgets```` 中（按 `id` 自动新增或增量覆盖）。所有 `{path}` 模板与 `value_ref` / `max_ref` 均从 `PlayerState` 路径取值（如 `hp`、`mp`、`attributes.stamina`、`variables.boss_hp`）。

### 2.1 `metrics`（紧凑数值监控条）
```yaml
- id: "survival_vitals"
  type: "metrics"
  title: "生理指标"
  icon: "🧭"
  when:
    variables:
      day:
        gte: 1
  items:
    - id: "stamina"
      label: "体能"
      icon: "⚡"
      value_ref: "attributes.stamina"
      max: 100
      color: "amber"       # 可选: amber | sky | emerald | teal | rose | violet | indigo
      low_threshold: 25    # 低于等于该值触发红色脉冲警示
    - id: "temp"
      label: "体温"
      icon: "🌡️"
      value_ref: "attributes.temperature"
      unit: "°C"
      color: "teal"
      warn_outside: [35.5, 38.0]  # 超出闭区间触发警示
```

### 2.2 `tracker`（阶段/任务步骤追踪器）
```yaml
- id: "mine_quest_tracker"
  type: "tracker"
  title: "矿洞主线"
  subtitle: "当前进度 · {variables.quest_stage}"
  icon: "⚔️"
  steps:
    - label: "挑选职业"
      done_when:
        variables:
          class_selected: true
      active_when:
        variables:
          class_selected: false
    - label: "击溃蜘蛛领主"
      done_when:
        variables:
          boss_defeated: true
      active_when:
        variables:
          boss_active: true
```

### 2.3 `panel`（Boss / 遭遇战 / 同伴详情面板）
```yaml
- id: "arachnos_boss_panel"
  type: "panel"
  title: "蜘蛛领主 · 阿拉克诺斯"
  icon: "🕷️"
  tone: "danger"   # 可选: danger | default
  when:
    variables:
      boss_active: true
      boss_defeated: false
  badges:
    - text_ref: "阶段 {variables.boss_phase}/3"
      tone: "purple"  # 可选: danger | red | amber | emerald | sky | purple | fuchsia | slate
    - text: "甲壳硬化 (-45%伤)"
      tone: "amber"
      when:
        variables:
          boss_armor_broken: false
  bars:
    - label: "首领生命"
      value_ref: "variables.boss_hp"
      max_ref: "variables.boss_max_hp"
      color: "rose"   # 可选: rose | violet | sky | amber | emerald
    - label: "首领魔力"
      value_ref: "variables.boss_mp"
      max_ref: "variables.boss_max_mp"
      color: "sky"
  cards_title: "查看首领阶段机制"
  cards:
    - title: "阶段二 (<=240 HP)"
      desc: "消耗35 MP召唤2只毒囊幼蛛并蓄力剧毒新星"
  footer: "当前意图：{variables.boss_casting}"
```

---

## 3. `world.yaml` 与 `condition` 声明式字段

### 3.1 `world.yaml` 引擎解耦字段
- `dm_rules`: 注入每次 Play Prompt 的剧本专属规则文本。
- `item_catalog`: `{ item_id: { name, desc, icon } }`，获得物品时自动补全图标与说明。
- `unique_items`: `["lighter", ...]`，自动防重复拾取。
- `scene_scoped_defaults`: 离开/切换场景时自动重置的场景局部变量默认值（防止临时机关带入新场景）。
- `attribute_bounds`: `{ stamina: [0, 100], strength: [1, 30] }`。
- `variable_bounds`: `{ day: { min: 1 }, water_qty: { min: 0, max: 5 } }`。
- `attribute_labels`: `{ strength: "力量", agility: "敏捷" }`（用于 HUD 顶部展示标签）。
- `adjudication_rules`: 数据驱动的检定修正规则列表（按 `condition` 命中并累加 `modifier`）。
- `freeform_rules` / `fallback_recipes` / `default_fallback`: 离线 Fallback Director 匹配规则。

### 3.2 通用 `condition` 支持键（可用于 `action`、`decoration`、`hud_widget`）
- 背包与装备：`has_item`、`has_any_item`、`not_has_item`、`has_outfit`、`not_has_outfit`、`has_outfit_slot`、`not_has_outfit_slot`
- 技能：`has_skill`、`not_has_skill`
- 数值比较：`variables` / `attributes` 支持标量相等或操作符字典 `{ lt, lte, gt, gte, ne, in, not_in }`
- 快捷阈值：`min_day`、`min_hp`、`hp_lte`、`min_mp`、`max_mp`、`min_gold`
- 时间与天气：`time_slot_in`、`time_slot_not_in`、`weather_in`、`weather_not_in`

### 3.3 `action.on_success` / `on_failure` 常用结果键
- `transition_scene`、`message`、`gain_item`（字符串或 `{id, name, desc}`）、`consume_item`、`consume_items`、`consume_any_item`
- `equip_outfit`、`unequip_outfit`、`skills`、`learn_skills`、`remove_skills`
- `hp_delta`、`mp_delta`、`max_hp_delta`、`max_mp_delta`、`san_delta`、`gold_delta`、`attributes_delta`
- `variables`、`variables_delta`、`time_cost`、`hud_widgets`、`replace_hud_widgets`、`remove_hud_widgets`、`visuals`

---

## 4. 剧本专属 Agent Skill 目录约定

任意剧本 `scripts/<scenario_id>/` 均内置支持与通用 Agent Skill 一致的目录布局，并随 ZIP 包一并导入导出：

```text
scripts/<scenario_id>/
├── world.yaml          # 世界设定与声明式规则
├── scenes/*.yaml       # 场景拓扑节点
├── assets/             # 背景、立绘、道具与角色图（前端通过 /assets/<rel> 访问）
├── SKILL.md            # 可选：剧本专属 DM 操作指南（自动注入 Play 与 Studio 上下文）
├── scripts/*.py        # 可选：标准库辅助脚本（数值/战斗/掉落计算等），自动提取首行说明供 Agent 调用
└── references/*        # 可选：设定集与数值参考表
```
