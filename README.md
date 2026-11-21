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

按照开发计划，项目按 4 个阶段有序推进：
- [x] 阶段一：本地 Agent CLI 适配器与 AG-UI 协议桥接 (Core Bridge)
- [x] 阶段二：SLG 沉浸运行端 (Play Mode)
- [ ] 阶段三：剧本编辑与本地 Agent 调试工作台 (Studio Mode)
- [ ] 阶段四：完整实战剧本与端到端交付 (Delivery & Verification)
