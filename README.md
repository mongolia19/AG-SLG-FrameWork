# 🏝️ AG-SLG-FrameWork

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)
![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg?logo=typescript)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi)
![AG--UI Protocol](https://img.shields.io/badge/AG--UI-Native-orange.svg)
![Local Agent](https://img.shields.io/badge/Local%20Agent-Antigravity%20%7C%20Codex-purple.svg)

**专为 AI 时代打造的原生 Agent 驱动型文字冒险 / TRPG 跑团引擎（Agent-Native SillyTavern）**  
*动态 DM 现场推演 · 四层视觉舞台编排 · D20 属性判定 · 左右空白景物沉浸渲染 · 完整 Studio 协创工作台*

[🎮 快速开始](#-30-秒极速上手) • [🏝️ 荒岛余生案例](#️-核心实战剧本荒岛余生-island-survival) • [✨ 核心特性](#-核心特性) • [📦 剧本包自包含架构](#-自包含剧本包与资产可维护性) • [🛠️ 架构设计](#️-架构概览)

</div>

---

## 🌟 为什么选择 AG-SLG-FrameWork？

在传统的文字游戏或角色扮演聊天室中，LLM 往往只是单薄地回复一段纯文本，没有真正的数值状态机、缺乏视觉合成体系，且无法像真正的游戏制作人那样理解剧本结构。

**AG-SLG-FrameWork 彻底改变了这一切**：
- 🤖 **Agent 原生主持（Native AI DM）**：不直接裸调单次 API，而是接入具备**长程规划与工具调用能力**的本地自主 Agent 引擎（默认支持 Google Antigravity `agy` 与 OpenAI `codex`，自带零配置本地 Fallback Director），AI 主持人不仅会根据玩家决策推演剧情，还会**动态发放分支选项、投掷 D20 骰子检定、变更玩家生命/饱食/水分/体温数值**。
- 🎨 **多图层视觉舞台（Visual Staging）**：全景背景底图、角色半身立绘、关键线索物特写插图无缝层叠；更支持在对话框两侧的空白区域渲染**场景微距景物**（如爬行青蟹、贝壳礁石、摇曳椰树），打造极致沉浸体验。
- 📦 **自包含剧本包（Self-Contained Scenario Bundles）**：剧本节点、世界观与多媒体图片素材全部就近收纳在同一个剧本目录下，支持 Studio 界面中**一键导出与导入 ZIP 剧本包**，便于创作者分享与社区交流。
- 🛠️ **双模一体：沉浸游玩 (Play Mode) + 智能编剧工作台 (Studio Mode)**：既能尽情游玩，又能一键切换到后台，吩咐 **Studio Co-pilot 编剧助手** 用自然语言为你扩写全新密室、自动纠察死锁跳转！

---

## 🏝️ 核心实战剧本：荒岛余生 (Island Survival)

项目中完整内置了开箱即用的高拟真求生文字 RPG 剧本——**《荒岛余生》**，全面融合了人体代谢监控、动态环境互动与场景道具收集！

```
                     ┌──────────────────────┐
                     │   🌊 孤岛海滩 (beach)  │
                     │  飞机残骸 · 散落行李   │
                     │  海浪浮木 · 潮间青蟹   │
                     └──────────┬───────────┘
                                │
                    [深入岛屿]  │  [返回海岸]
                                ▼
                     ┌──────────────────────┐
                     │ 🌴 海边丛林 (jungle)  │
                     │  古藤缠绕 · 坚韧纤维   │
                     │  避风岩壁 · 编织绳索   │
                     └──────────┬───────────┘
                                │
                    [探索密林]  │  [折返外围]
                                ▼
                     ┌──────────────────────┐
                     │ 🏕️ 丛林深处 (deep)    │
                     │  清澈溪流 · 淡水泉眼   │
                     │  搭建庇护所 · 升起篝火  │
                     └──────────────────────┘
```

### 🎮 游戏核心玩法与亮点

1. **六大生理生存指标实时监控**：
   - ❤️ **生命值 (HP)** & 🧠 **理智值 (SAN)**：受伤与绝望可能带来不可逆的生命危机。
   - ⚡ **体力 (Stamina)**：所有探索、伐木、翻找均会消耗体力，体力过低将无法执行高强度行动。
   - 💧 **水分 (Hydration)**：烈日暴晒与长途跋涉加速脱水，必须尽快寻获容器并在丛林深处过滤淡水。
   - 🍖 **饱食度 (Fullness)**：空腹将导致体能大幅衰退，可拾取海贝应急，或退潮后在礁石间抓捕海蟹生火炙烤！
   - 🌡️ **体温 (Temperature)**：暴雨与夜幕降临可能导致失温症，必须采集干燥树枝并用打火机升起篝火取暖。

2. **左右空白区域景物沉浸渲染（Margin Props）**：
   - 对话流左侧：实时显示当前场景环境景物，如海滩上的**高耸椰树**、沙滩上沙沙爬动的**敏捷红蟹**。
   - 对话流右侧：展示海浪冲刷的**天然海贝**与黝黑的**火山礁石**，点击查看材质细节与交互提示。

3. **自由行动输入 + 严格 D20 属性判定**：
   - 支持预设快捷行动（拾取金属盒、搜索行李、捞取玻璃瓶、探索密林、退潮捕蟹）。
   - **支持任意自然语言自由输入**：输入“仔细清理金属盒的泥沙并撬开卡扣”或“抓一把细沙摩擦生火”，DM 均能精准理解意图，绝不偏题劫持，结合敏捷/感知/体质等属性掷骰检定！

4. **可视化随身生存背包**：
   - 随时点击顶部 HUD 中的 **生存背包**，查看已搜集的军用防风打火机、厚壁储水玻璃瓶、干燥易燃树枝、坚韧古藤绳索与海蟹食材。

---

## ⚡ 30 秒极速上手

无需复杂的数据库配置，只需 Python 与 Node.js 环境即可一键启动：

### 1. 克隆代码库
```bash
git clone https://gitee.com/idroid23/ag-slg-frame-work.git
cd ag-slg-frame-work
```

### 2. 准备后端环境与依赖
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 安装前端依赖
```bash
cd web
npm install
cd ..
```

### 4. 一键启动前后端全套服务
AG-SLG-FrameWork 自带后台服务管家 `run_services.py`：
```bash
python3 run_services.py start
```
- **后端服务 (FastAPI + AG-UI)**: `http://127.0.0.1:8001`
- **前端工作台 (React + Vite)**: `http://localhost:5173`

打开浏览器访问 `http://localhost:5173`，在顶部剧本下拉菜单中选择 **【荒岛余生】**，即可立刻开启求生冒险！

> **常用运维命令**：
> - `python3 run_services.py status` —— 查看前后端运行健康状态
> - `python3 run_services.py restart` —— 一键重启前后端
> - `python3 run_services.py stop` —— 停止前后端守护进程

---

## 📦 自包含剧本包与资产可维护性

传统 SLG 游戏素材往往散落在全局静态资源目录中，一旦需要移植、备份或与朋友分享剧本，极其繁琐且极易丢失图片文件。

AG-SLG-FrameWork 采用了**剧本资产自包含（Co-located Scenario Bundles）**架构：

```
scripts/island_survival/
├── world.yaml                  # 世界观、初始主角属性、全局初始变量
├── scenes/                     # 场景逻辑节点定义
│   ├── beach.yaml              # 孤岛海滩场景：行动、检定DC、左右景物配置
│   ├── coastal_jungle.yaml     # 海边丛林场景
│   └── deep_jungle.yaml        # 丛林深处场景
└── assets/                     # 🎬 剧本专属多媒体资产（自包含在当前目录）
    ├── scenes/                 # 空间背景全景图 (island_beach.png, deep_jungle.png 等)
    ├── illustrations/          # 特写插画 (wreckage.png, campfire.png 等)
    ├── props/                  # 左右景物立绘 (seashell.png, crab.png, palmtree.png 等)
    └── items/                  # 随身道具图标 (lighter.png, rope.png, glass_bottle.png 等)
```

### 导入与导出特权：
- **一键导出（Export ZIP）**：在 Studio 模式顶部点击 **「导出剧本包」**，即可将当前剧本的世界设定、所有场景节点及专属图片资产一键打包下载为 `.zip`。
- **一键导入（Import ZIP）**：点击 **「导入剧本包」**，直接上传任意符合规范的 `.zip` 剧本包，系统自动解包校验并即时生效，随插随玩！

---

## 🎨 视觉导演技能 (Agent Skill: ag-slg-director)

框架内置了符合业内高级视觉叙事标准的 Agent Skill —— `ag-slg-director`：
- **技能规范文件**: [skills/ag-slg-director/SKILL.md](skills/ag-slg-director/SKILL.md)
- **四层视觉合成架构**:
  1. **Layer 0 (Background)**: 空间全景图，受控慢速景深过渡与氛围渐变。
  2. **Layer 1 (Foreground)**: 登场 NPC 立绘与动态表情半身像。
  3. **Layer 2 (Hero Focus)**: 关键线索、证物插画特写。
  4. **Layer 3 (Stream UI)**: 旁白叙事、NPC 对话卡片、检定判定与状态补丁分离渲染。
- **全文本可复制（Copy Anywhere）**：所有玩家决策、人物对话、DM 旁白及打字机流式输出均配备一键复制按钮与原生文本选中支持。

---

## 🏗️ 架构概览

```
┌────────────────────────────────────────────────────────┐
│                   Web Browser UI                       │
│    (React 18 + TailwindCSS + @ag-ui/client SDK)        │
│    [Play Mode 沉浸跑团]   |   [Studio Mode 可视化协创]    │
└───────────────────────────┬────────────────────────────┘
                            │
               AG-UI Protocol (SSE / JSON-RPC)
                            │
┌───────────────────────────▼────────────────────────────┐
│              FastAPI Bridge Server (:8001)             │
│    - AGUIBridge: 协议转换、状态补丁、掷骰引擎             │
│    - ScenarioManager: 剧本加载、自包含资产路由、ZIP导包   │
│    - ScriptLinter: 跳转死锁检测、孤立节点校验          │
└───────────────────────────┬────────────────────────────┘
                            │
             标准输入输出管道 (stdin / stdout stream-json)
                            │
┌───────────────────────────▼────────────────────────────┐
│              Local Agent Engine CLI                    │
│    - Google Antigravity (agy) / OpenAI Codex           │
│    - 具备文件系统读写能力，直接编辑剧本 YAML             │
│    - 零配置内置高拟真 Fallback Director 兜底               │
└────────────────────────────────────────────────────────┘
```

---

## 🧪 自动化测试套件

AG-SLG-FrameWork 具备完备严苛的自动化测试套件，保障每一次提交与剧本扩写均稳定可靠：

```bash
# 运行后端 22 项全量核心测试（包含协议桥接、属性检定、荒岛生存游玩流、自包含打包导入导出等）
.venv/bin/pytest -v

# 运行前端 TypeScript 类型检查与 Vite 生产编译
cd web && npm run build
```

---

## 🤝 参与贡献与社区交流

欢迎提交 Issue、发起 Pull Request，或者分享你制作的精彩剧本包！
- 发现 Bug 或有新的机制创意？欢迎在 [Gitee Issues](https://gitee.com/idroid23/ag-slg-frame-work/issues) 中提出。
- 更多实战剧本持续更新中，敬请期待！

---

<div align="center">
<b>AG-SLG-FrameWork</b> — 让每个人都能轻松拥有属于自己的 Agent 原生文字冒险宇宙！
</div>
