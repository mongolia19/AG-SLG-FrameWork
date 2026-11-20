# AG-SLG-FrameWork 需求规格说明书 (Requirements Specification)

## 1. 项目定位与背景

**AG-SLG-FrameWork** 是一个基于 **AG-UI 协议** 与 **本地 Agent 引擎（agy / codex）** 构建的轻量级、高扩展性 AI 文字战略/冒险游戏（SLG / Text Adventure / TRPG）的**运行时 + 可视化编辑器框架**。

### 1.1 核心痛点与与传统方案（如 SillyTavern）对比
传统 AI 跑团与角色扮演前端（以 SillyTavern 为代表）的本质是：
- **Prompt 模板拼接器 + 裸 LLM 聊天室**：逻辑控制依赖脆弱的 System Prompt 提示词，无法进行确定性的状态结算与复杂的规则检定。
- **缺乏真实 Agent 规划与工具链**：状态变更、剧本文件编辑、多步规划完全脱节，难以自动创建和重构剧本。

**AG-SLG-FrameWork 的核心范式转变**：
1. **Agent 引擎化**：不直接调用裸 LLM API，而是直接接入本地具有系统级工具调用、文件读写、自主规划能力的成熟 Agent（首选 `agy`，兼顾 `codex`）。
2. **协议标准化**：基于 **AG-UI 协议**（Agent-User Interaction Protocol），通过 SSE 流式统一承载剧情输出（`TextMessage*`）、角色与世界状态同步（`StateDelta`）、检定工具触发（`ToolCall*`）。
3. **编剧即研发**：创作端不仅仅是可视化表单，更是由本地编剧 Agent 拥有对剧本文件的真实读写、自检、推演能力。

---

## 2. 核心架构与运行模型

系统采用“**前端双模式 UI + 后端 AG-UI 桥接层 + 本地 Agent 进程驱动 + 文件系统持久化**”的四层架构：

```
+------------------------------------------------------------------------+
|                               Web 前端                                  |
|   +-------------------------------+  +-------------------------------+ |
|   |    🎮 Play Mode (运行端)       |  |     ✍️ Studio Mode (编辑端)    | |
|   | 剧情流、立绘、数值HUD、动态选项  |  | 剧本文件树、Agent实时编剧/调试 | |
|   +-------------------------------+  +-------------------------------+ |
+-----------------------------------▲------------------------------------+
                                    │ AG-UI Protocol (SSE / JSON-RPC)
+-----------------------------------▼------------------------------------+
|                         FastAPI 桥接中枢                                |
|  - AG-UI Event Encoder / Streamer (状态广播、流式转译)                    |
|  - Session / Thread Manager (映射 Web 会话至 Agent Conversation)       |
+-----------------------------------▲------------------------------------+
                                    │ 子进程 stdin/stdout (JSONL / stream-json)
+-----------------------------------▼------------------------------------+
|                       本地 Agent 适配层 (CLI Driver)                    |
|  - agy (Google Antigravity CLI, 默认)                                  |
|  - codex (Codex CLI, 备选支持)                                          |
+-----------------------------------▲------------------------------------+
                                    │ 原生工具调用 (read_file / write_file / exec)
+-----------------------------------▼------------------------------------+
|                     本地剧本资产库 (Workspaces)                          |
|  scripts/{scenario_id}/                                                |
|    ├── world.yaml        # 世界观规则、全局变量、属性初始值              |
|    ├── characters.yaml   # 角色卡（人设、立绘资源、初始好感/关系）        |
|    └── scenes/           # 分幕与场景定义（节点逻辑、可用动作、跳转条件） |
+------------------------------------------------------------------------+
```

---

## 3. 功能需求规格

### 3.1 游戏运行端 (Play Mode)
- **FR-P01 剧情流式叙事 (Story Stream)**：
  - 接入 AG-UI 的 `TextMessageContentEvent`，实现视觉小说级打字机逐字输出。
  - 支持区分旁白（Narration）、角色台词（Dialogues）与心声提示。
  - 动态关联当前登场角色立绘（Avatar）与场景背景（Background）。
- **FR-P02 状态栏与实时 HUD (State Sync)**：
  - 通过 AG-UI 的 `StateDeltaEvent` 与 `StateSnapshotEvent` 实时无缝更新前端状态。
  - 展示玩家属性（如：生命 HP、精力/理智 SAN、金币 Gold）、装备背包（Inventory）、当前所在场景、NPC 好感度及时间/天气。
- **FR-P03 动态交互面板 (Action & Decision)**：
  - **结构化选项**：展示当前场景配置的推荐行动（如：“[调查] 仔细搜查书架上的古籍”、“[离开] 前往中庭”）。
  - **自由文本行动**：允许玩家输入任意自由动作（如：“我拔出匕首悄悄摸向卫兵身后”），由 DM Agent 自主决策并判定。
- **FR-P04 确定性检定与工具可视化 (Game Tools)**：
  - 当触发属性判定（如力量检定 D20、运气检定）或获得道具时，捕获 AG-UI `ToolCallStartEvent` / `ToolCallEndEvent`，在界面展示骰子掷出动画或物品获得弹窗。

---

### 3.2 剧本编辑与调试端 (Studio Mode)
- **FR-S01 可视化剧本结构管理**：
  - 场景节点树（Scenes Tree）：查看全剧本节点跳转逻辑流。
  - 角色卡编辑（Characters）：角色基本属性、性格特质、对话口吻、动态记忆。
  - 世界状态设定（World State）：全局变量定义、检定难度等级（DC）预设。
- **FR-S02 编剧 Agent 协创 (Authoring Co-pilot)**：
  - 创作者可通过自然语言与 Studio Agent 对话进行内容生产（例如：“在庄园地窖与主厅之间增加一个密道场景，需要敏捷 12 以上或使用铁撬棍才能发现”）。
  - Agent 利用其内置的文件读写能力，直接定位对应 YAML 文件，生成或增量修改规范场景节点。
- **FR-S03 剧本一致性校验与死锁检测 (Script Linter)**：
  - 静态检查：未定义的场景跳转目标、不存在的物品变量引用、缺少退出路径的死循环。
  - Agent 驱动的逻辑语义审计：检查剧情线前后设定的矛盾（如死者在后续场景中复活）。
- **FR-S04 自动试玩推演 (Automated Playtest)**：
  - 支持设定预设玩家性格（如“高智商解谜狂”、“鲁莽好斗战士”），由 Agent 自主以玩家身份推演 5~10 轮交互，输出推演轨迹报告，供创作者排查剧情体验卡点。

---

### 3.3 本地 Agent 驱动层 (Engine & Adapters)
- **FR-A01 默认驱动：`agy` CLI 适配器**：
  - 运行命令：`agy -p "<prompt>" --output-format stream-json --continue --conversation <thread_id>`。
  - 实时捕获 NDJSON 事件（`init`, `step_update`, `tool_call`, `result`），转译为 AG-UI 标准事件。
- **FR-A02 备选驱动：`codex` CLI 适配器**：
  - 运行命令：`codex exec --json --cd <workspace> ...`。
  - 支持会话恢复与工作区隔离。
- **FR-A03 会话状态与进程生命周期**：
  - 映射 Web 前端 Session 与本地 Agent 的持久会话 ID，保证剧情长线记忆不丢失。

---

## 4. 数据与剧本规范 (Script Specification)

剧本以标准 YAML 格式保存在磁盘目录 `scripts/<scenario_name>/` 下：

### 4.1 世界与规则配置 (`world.yaml`)
```yaml
id: "black_crow_manor"
title: "黑鸦公馆的雨夜"
version: "1.0.0"
author: "AI Lab & Agent"
initial_scene: "manor_entrance"

initial_player_state:
  name: "调查员亚伦"
  hp: 100
  san: 80
  gold: 50
  attributes:
    strength: 12
    agility: 14
    intelligence: 16
  inventory:
    - id: "magnifying_glass"
      name: "复古放大镜"
      desc: "用于观察细微线索"
  variables:
    discovered_secret_passage: false
    butler_trust: 10
```

### 4.2 场景规范 (`scenes/<scene_id>.yaml`)
```yaml
id: "manor_entrance"
title: "公馆大门玄关"
background: "/assets/scenes/entrance.png"
music: "/assets/bgm/rain_night.mp3"

description: |
  大门在你们身后沉重地合上，隔绝了暴风雨的咆哮。
  挑高的大厅中央悬挂着一盏摇摇晃晃的黄铜吊灯，管家格林手持烛台，面色苍白地立在阴影中。

npcs:
  - id: "butler_grim"
    name: "管家格林"
    avatar: "/assets/characters/butler.png"
    greeting: "尊敬的调查员，这么晚冒雨造访，主人早已歇息了……"

actions:
  - id: "talk_to_butler"
    label: "询问今晚发生的异响"
    type: "interact"
    target_npc: "butler_grim"

  - id: "inspect_coat_rack"
    label: "调查衣帽架旁滴水的雨衣"
    type: "check"
    skill: "intelligence"
    difficulty: 12
    on_success:
      gain_item: "silver_key"
      transition_scene: "manor_foyer"
    on_failure:
      message: "只是一件普通的湿透雨衣，并没有发现特别之处。"

  - id: "explore_hall"
    label: "穿过门厅前往会客室"
    type: "transition"
    target_scene: "drawing_room"
```

---

## 5. 非功能性需求 (NFR)
1. **轻量即开即用 (Zero Over-engineering)**：纯本地运行，不依赖 MySQL/PostgreSQL/Redis，文件系统即数据库。
2. **低延迟响应**：本地 Agent CLI 首字返回延迟控制在 1.5 秒内，流式输出体感流畅。
3. **安全与沙箱**：Agent 读写范围严格限定在 `scripts/` 与剧本运行目录内，防止意外误操作宿主其他目录。
4. **确定性容错**：当本地 Agent 产生非预期格式输出时，桥接层具备自愈兜底机制，保证前端 UI 不崩溃。
