# AG-SLG-FrameWork

<div align="center">

![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)
![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg?logo=typescript)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi)
![AG-UI Protocol](https://img.shields.io/badge/AG--UI-Native-orange.svg)

[English](README.md) | **简体中文**

基于 **AG-UI Protocol** 与 **ACP（Agent Client Protocol）** 的 Agent 驱动型交互式叙事 / TRPG 跑团框架。  
通过实时 SSE 流、JSON-Patch 状态增量、多图层舞台渲染与可视化制作台，将大语言模型剧情演绎与结构化游戏状态解耦。

[快速开始](#快速开始) • [核心特性](#核心特性) • [内置剧本](#内置剧本) • [技术架构](#技术架构) • [测试与验证](#测试与验证)

</div>

---

## 项目简介

AG-SLG-FrameWork 打通了本地 Agent CLI（`agy`、`codex`）与 Web 游戏客户端，遵循标准 **AG-UI SSE 协议**（`RUN_STARTED` → `TEXT_MESSAGE_*` / `TOOL_CALL_*` → `STATE_DELTA` → `RUN_FINISHED`）。  
剧本完全采用数据驱动的 YAML 资产包（`world.yaml` + `scenes/*.yaml` + `assets/`），支持声明式条件判定与扩展 `hud_widgets`，无需针对单个剧本硬编码前端界面。

---

## 核心特性

- **双 Agent 后端热切换 + 离线兜底**
  - 基于长驻 **ACP（stdio JSON-RPC 2.0）** 驱动 **Antigravity (`agy acp`)** 与 **OpenAI Codex (`codex-acp` / `npx @agentclientprotocol/codex-acp`)**。
  - 支持在页面顶栏选择框热切换后端（`POST /api/driver`），或通过 `python run_services.py restart codex` 启动，配置持久化在 `.agent_driver`。
  - 内置确定性 **Fallback Director**，在无外部 CLI 或离线状态下依然可完整推演游玩。
- **多维 TRPG 分阶裁决**
  - **四阶判定结果**：大成功（Critical）、成功（Success）、代价成功（Partial）、受挫失败（Failure）。
  - 综合考量属性修正、服装穿戴槽位、随身道具、技能、时间/天气与生理战斗数值。
- **多图层视觉舞台与声明式 HUD**
  - 支持 `background`、`foreground`、可折叠 `hero_image` 焦点特写、`atmosphere` 氛围标签及左右条件 `decorations`（场景道具/建成设施）。
  - 支持剧本自定义 `hud_widgets`（属性条、Boss 阶段追踪面板、同伴状态卡）以及**技能栏 / 服装栏 / 背包**弹窗。
- **游玩进度控制**
  - **手动存档管理**：按剧本分目录保存 / 读取 / 删除命名检查点（`saves/{scenario_id}/`），与 `localStorage` 自动续玩并存。
  - **编辑输入 / 重新生成本轮**：支持完整回滚本轮前端状态与服务端 `GameSession` 后重跑。
- **双模式运行：运行端 (Play) + 工作台 (Studio)**
  - **Play 模式**：快捷行动卡片、D20 掷骰检定、自由文本交互与 Studio 热同步。
  - **Studio 模式**：场景节点编辑、`ScriptLinter` 死锁/孤立节点校验、ZIP 剧本包导入导出，以及可写盘的编剧 Co-pilot。
- **跨平台兼容**：原生支持 **macOS、Linux 与 Windows**（`run_services.py` 与驱动层自动兼容 `.venv/Scripts/python.exe`、`vite.cmd` / `npx.cmd`、`netstat` 端口清理与跨平台 ZIP 路径）。

---

## 内置剧本

| 剧本 ID | 名称 | 核心机制展示 |
|---|---|---|
| `island_survival` | 荒岛余生 | 生理代谢循环（体力/水分/饱食度/体温）、昼夜与天气系统、设施建造与自由文本意图识别 |
| `wow_elwynn_rpg` | 艾泽拉斯传说：法戈第矿洞之影 | 职业选择（圣骑士/猎人/法师/战士）、技能卡组、HP/MP 槽位、回合制战斗与多阶段 Boss `hud_widgets` |
| `black_crow_manor` | 黑鸦庄园 | 悬疑探索、线索道具、属性检定与 NPC 信任度分支 |

---

## 快速开始

### 环境要求
- **Python 3.10+**（`uv` 或 `pip`）
- **Node.js 18+**
- *(可选)* 本地 `agy` 或 `codex` CLI（未安装时自动由内置 Fallback Director 接管）

### 1. 克隆仓库
```bash
git clone https://github.com/mongolia19/AG-SLG-FrameWork.git
# 或 Gitee 镜像：
# git clone https://gitee.com/idroid23/ag-slg-frame-work.git
cd AG-SLG-FrameWork
```

### 2. 安装前后端依赖

**macOS / Linux：**
```bash
uv sync --extra dev
# 或使用 venv + pip：
# python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

cd web && npm install && npm run build && cd ..
```

**Windows (PowerShell)：**
```powershell
uv sync --extra dev
# 或使用 venv + pip：
# python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e ".[dev]"

cd web; npm install; npm run build; cd ..
```

### 3. 启动服务（跨平台）
```bash
# 一键拉起 FastAPI (:8001) 与 Vite (:5173)
python run_services.py start

# 指定启动后端驱动（agy | codex | mock）
python run_services.py restart codex

# 查看状态 / 停止服务
python run_services.py status
python run_services.py stop
```

浏览器访问 `http://localhost:5173`（后端接口文档：`http://127.0.0.1:8001/docs`）。

---

## 自包含剧本包结构

```text
scripts/<scenario_id>/
├── world.yaml              # 世界配置、初始玩家状态、hud_widgets、物品/天气规则
├── scenes/                 # 场景 YAML 节点（描述、视觉层、NPC、行动、条件）
│   └── ...
└── assets/                 # 剧本专属多媒体资源
    ├── scenes/
    ├── illustrations/
    ├── characters/
    ├── props/
    └── items/
```

在 Studio 顶部点击「**导出剧本包**」或「**导入剧本包**」，即可通过标准 `.zip` 在不同平台间分享剧本。

---

## 技术架构

```text
┌──────────────────────────────────────────────────────────┐
│                     Web Browser UI                       │
│        React 18 + TypeScript + TailwindCSS + Vite        │
│      [Play 运行端: HUD / 剧情流 / 行动 / 存档 / 重试]     │
│      [Studio 工作台: 节点拓扑 / YAML / Linter / Co-pilot]  │
└────────────────────────────┬─────────────────────────────┘
                             │ AG-UI Protocol (SSE + REST)
┌────────────────────────────▼─────────────────────────────┐
│               FastAPI Bridge Server (:8001)              │
│  - AGUIBridge: 提示词构建、StateDelta、多维综合裁决        │
│  - ScenarioManager: 剧本加载、资产路由、ZIP 打包与导入     │
│  - ScriptLinter 与游玩存档持久化 (saves/)                 │
└────────────────────────────┬─────────────────────────────┘
                             │ ACP (JSON-RPC 2.0 stdio)
┌────────────────────────────▼─────────────────────────────┐
│                Local Agent Engine CLI                    │
│  - AgyDriver (agy acp)  |  CodexDriver (codex-acp)       │
│  - MockAgentDriver 与内置 Fallback Director               │
└──────────────────────────────────────────────────────────┘
```

---

## 测试与验证

```bash
# 运行全量后端测试套件（pytest）
# macOS / Linux:
.venv/bin/pytest -v
# Windows:
.\.venv\Scripts\pytest.exe -v

# 前端类型检查与生产构建
cd web && npm run build
```

---

## 协议与贡献

本项目以 MIT 协议开源，欢迎提交 Issue 反馈问题或发起 Pull Request 参与共建。
