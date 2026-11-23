# AG-SLG-FrameWork

> 基于 **AG-UI 协议** 与 **本地 Agent 引擎（agy / codex）** 构建的 AI Agent 驱动型文字 SLG（文字冒险 / TRPG）运行与编辑框架（Agent-Native SillyTavern）。

---

## 🌟 核心特性

- **Agent 原生驱动，超越传统 LLM 聊天室**：
  不直接拼接 Prompt 调裸 API，而是直接调用本地自主 Agent 进程（默认驱动 Google Antigravity `agy`，兼顾 `codex`），拥有原生规划能力、多步推理与文件级工具调用。
- **AG-UI 标准协议打通前端体验**：
  基于开源 [AG-UI 协议](https://github.com/ag-ui-protocol/ag-ui)，实现沉浸式剧情打字机流式输出（`TextMessageContent`）、数值/背包实时同步（`StateDelta`）、掷骰检定交互（`ToolCall`）。
- **双模体验：运行端 (Play Mode) + 编辑工作台 (Studio Mode)**：
  - **Play Mode**：视觉小说/文字跑团沉浸体验，支持角色立绘、实时 HUD、分支选项与自由行动输入。
  - **Studio Mode**：可视化剧本场景树，配备 **Studio Co-pilot 编剧助手**，通过自然语言吩咐本地 Agent 自动查阅、扩写、修改剧本 YAML，并做死锁与逻辑校验。
- **纯文件系统，零繁琐依赖**：
  剧本与场景统一以清晰规范的 YAML 组织在本地磁盘，可直接 Git 托管、随改随生效。

---

## 📑 核心文档索引

- [需求规格说明书 (Requirements Specification)](docs/REQUIREMENTS.md)
- [开发实施计划 (Development Plan)](docs/DEVELOPMENT_PLAN.md)

---

## 🏗️ 架构概览

```
Web 浏览器 (React + @ag-ui/client)
       ↕ [AG-UI 协议: SSE / JSON-RPC]
FastAPI 桥接中枢 (ag-ui-protocol)
       ↕ [进程管道: stdin/stdout stream-json]
本地 Agent CLI 引擎 (agy / codex)
       ↕ [原生工具调用: 真实读写文件]
本地剧本资产目录 (scripts/*.yaml)
```

---

## 🚀 实施进度

- [x] 阶段一：本地 Agent CLI 适配器与 AG-UI 协议桥接 (Core Bridge)
- [x] 阶段二：SLG 沉浸运行端 (Play Mode)
- [x] 阶段三：剧本编辑与本地 Agent 调试工作台 (Studio Mode)
- [x] 阶段四：剧本导演与视觉编排 Skill (`ag-slg-director`)
- [x] 阶段五：荒岛生存文字 RPG 官方实战剧本 (`island_survival`) 与端到端交付

---

## 🏝️ 实战剧本：荒岛余生 (`island_survival`)

一个完整的荒岛求生文字 RPG 剧本，全面融合多图层视觉与人体生存状态监控：
- **人体生存属性监控**：
  - ⚡ **体力 (Stamina)**：奔跑、搜索、编制与砍伐消耗。
  - 💧 **水分 (Hydration)**：烈日脱水警告，通过寻找溪流或椰子补充。
  - 🍖 **饱食度 (Fullness)**：维持基础代谢，搜寻野生坚果与浆果。
  - 🌡️ **体温 (Temperature)**：防范夜间失温，生起篝火取暖。
- **三大地图场景**：
  - 🌊 **孤岛沙滩 (`beach`)**：失事残骸散落处，搜查防水盒获取 **打火机**，浅滩拾取 **玻璃瓶**，收集海浪冲刷的 **树枝**。
  - 🌴 **海边丛林 (`coastal_jungle`)**：古藤缠绕密林，割取坚韧纤维编织 **绳子**，收集硬木柴。
  - 🏕️ **丛林深处 (`deep_jungle`)**：遮天蔽日的深潭与溪流，用玻璃瓶取水，用打火机与干树枝生起庇护所 **篝火**。
- **随身生存背包**：
  点击顶部 HUD 中的 **生存背包**，可查看物品缩略图、数量、物品说明与详细详情。

---

## 🎨 视觉导演技能 (Agent Skill: ag-slg-director)

框架内置了专属 Agent Skill —— `ag-slg-director`：
- **技能路径**: `~/.t3/userdata/.../config/skills/ag-slg-director/SKILL.md` 及 [skills/ag-slg-director/SKILL.md](skills/ag-slg-director/SKILL.md)
- **四层视觉合成体系**:
  - **Layer 0 (Background)**: 空间全景底图 (`visuals.background`)，受控平稳过渡。
  - **Layer 1 (Foreground)**: 登场 NPC 立绘 (`visuals.foreground`)，对话时动态聚焦。
  - **Layer 2 (Hero Focus)**: 关键证物/焦点插图 (`visuals.hero_image`)，检定成功与线索特写。
  - **Layer 3 (Stream UI)**: 旁白叙事、NPC 对话（`“...”`）与系统检定分离渲染。
- **AG-UI 协议同步**:
  通过 `state_delta.visuals` 实时下发状态补丁，前端无感平滑切换多图层渲染。


