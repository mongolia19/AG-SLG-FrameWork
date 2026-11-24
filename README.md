# AG-SLG-FrameWork

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)
![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg?logo=typescript)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi)
![AG-UI Protocol](https://img.shields.io/badge/AG--UI-Native-orange.svg)

基于 **AG-UI Protocol** 的 Agent 驱动型文字冒险 / TRPG 跑团框架。  
支持 AI 主持人（DM）动态推演、多层视觉舞台编排、多维属性与装备检定，以及剧本可视化编辑器。

[快速开始](#快速开始) • [实战剧本：荒岛余生](#实战剧本荒岛余生) • [核心特性](#核心特性) • [剧本包结构](#自包含剧本包结构) • [技术架构](#技术架构) • [测试验证](#测试与验证)

</div>

---

## 项目简介

AG-SLG-FrameWork 旨在探索大语言模型在交互式叙事（Interactive Fiction）与文字跑团（TRPG）中的结构化实践。框架将文本生成与游戏运行态解耦，通过标准协议（AG-UI SSE）实现“**Agent 剧情演绎 + 局部状态补丁（JSON-Patch）+ 多图层舞台渲染**”。

项目既可作为玩家体验文字跑团的客户端，也是一套面向创作者的剧本开发与调试套件。

---

## 核心特性

- **多维综合裁决与分阶判定**
  - 告别机械的二元通过/失败，引入 TRPG 风格的**四阶判定结果**：卓越成功（Critical）、顺利达成（Success）、代价成功（Partial）、受挫转折（Complication）。
  - 检定综合考量四大要素：角色属性修正、穿戴衣物装备（外衣/鞋履/腕饰/配饰）、随身工具（石刀/打火机/绳索等）以及当前生理状态（体能/水分/饱食度）。
- **多图层视觉编排（Visual Staging）**
  - 场景底图（Background）：空间全景与氛围渲染；
  - 角色立绘（Foreground）：NPC 登场与对话交互；
  - 焦点特写（Hero Focus）：关键线索与拾获道具特写；
  - 场景微距景物（Margin Props）：对话两侧展示环境景物（如礁石、海蟹、椰树、贝壳），提升视觉层次感。
- **双模式运行：游玩端 (Play) + 制作端 (Studio)**
  - **游玩模式**：支持预设快捷行动与自由自然语言输入，实时显示状态 HUD、背包道具与换装插槽。
  - **编剧工作台**：场景拓扑节点可视化编辑、跳转死锁校验，支持与 Studio 编剧助手协作扩写剧情，修改后切换游玩模式即刻热生效。
- **自包含剧本架构（Self-Contained Scenarios）**
  - 场景逻辑 YAML 与图片等多媒体资源就近收纳，支持一键导出与导入 ZIP 剧本包，便于分享与版本管理。
- **双引擎驱动与离线兜底**
  - 支持接入外部自主 Agent（如 Antigravity `agy`、OpenAI `codex`）；
  - 内置零配置本地导演引擎（Fallback Director），无 API Key 或离线状态下依然可完整游玩与推演。

---

## 实战剧本：荒岛余生

项目中内置了求生题材实战剧本——**《荒岛余生》（Island Survival）**，作为框架各系统的完整参考实现：

```
                 ┌──────────────────────┐
                 │    孤岛海滩 (beach)   │
                 │  失事残骸 · 散落行李   │
                 │  礁石海浪 · 潮间青蟹   │
                 └──────────┬───────────┘
                            │
                [深入密林]   │   [返回海岸]
                            ▼
                 ┌──────────────────────┐
                 │  海边丛林 (jungle)   │
                 │  古藤缠绕 · 避风岩壁   │
                 │  收集纤维 · 编织绳索   │
                 └──────────┬───────────┘
                            │
                [探索深处]   │   [折返外围]
                            ▼
                 ┌──────────────────────┐
                 │  丛林深处 (deep)     │
                 │  淡水泉眼 · 搭建营地   │
                 │  升起篝火 · 烤制熟食   │
                 └──────────────────────┘
```

### 包含的玩法系统

1. **生理状态代谢循环**：生命（HP）、理智（SAN）、体力（Stamina）、水分（Hydration）、饱食度（Fullness）、体温（Temperature）。劳作与探索消耗体力水分，饥饿与失温带来状态惩罚。
2. **意图识别与复合行动**：输入自由文本如“从背包拿出打火机引燃甘草，升起火堆烤螃蟹”，系统会准确识别持有道具、生火意图与烹饪动作，同步更新环境状态与角色饱食度。
3. **随身背包与装备槽位**：支持外衣（防风保暖）、鞋子（防滑跑鞋）、腕部（反光腕表）、颈部等槽位穿戴，实时对后续环境检定提供数值修正。
4. **时间流转与昼夜系统**：行动推动时段流转（清晨 → 上午 → 下午 → 黄昏 → 夜晚 → 深夜），天气与能见度随之动态变化。

---

## 快速开始

### 运行环境
- Python 3.10+
- Node.js 18+

### 1. 克隆项目
```bash
git clone https://gitee.com/idroid23/ag-slg-frame-work.git
cd ag-slg-frame-work
```

### 2. 安装后端依赖
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 安装前端依赖并构建
```bash
cd web
npm install
npm run build
cd ..
```

### 4. 启动服务
使用内置的服务管理脚本一键拉起前后端：
```bash
python3 run_services.py start
```

服务就绪后：
- 前端界面：`http://localhost:5173`
- 后端接口：`http://127.0.0.1:8001`
- API 文档：`http://127.0.0.1:8001/docs`

在浏览器打开 `http://localhost:5173`，选择剧本 **【荒岛余生】** 即可体验。

> **服务管理辅助命令**：
> - 查看运行状态：`python3 run_services.py status`
> - 重启服务：`python3 run_services.py restart`
> - 停止服务：`python3 run_services.py stop`

---

## 自包含剧本包结构

每个剧本为一个独立目录，资产与逻辑就近存放，结构清晰规范：

```
scripts/island_survival/
├── world.yaml                  # 世界观、主角初始状态、全局变量
├── scenes/                     # 场景节点 YAML
│   ├── beach.yaml              # 场景描述、可用选项、检定DC、左右景物
│   ├── coastal_jungle.yaml
│   └── deep_jungle.yaml
└── assets/                     # 剧本专属媒体资产
    ├── scenes/                 # 空间背景图 (island_beach.jpg 等)
    ├── illustrations/          # 特写插画 (campfire.jpg, lighter.jpg 等)
    ├── props/                  # 景物素材 (crab.jpg, seashell.jpg 等)
    └── items/                  # 道具图标
```

- **导出剧本**：在 Studio 顶部点击「导出剧本包」，自动打包为标准 `.zip` 文件。
- **导入剧本**：在 Studio 顶部点击「导入剧本包」，上传符合格式的 `.zip` 即可加载并立即游玩。

---

## 技术架构

```
┌────────────────────────────────────────────────────────┐
│                   Web Browser UI                       │
│    (React 18 + TailwindCSS + @ag-ui/client)            │
│    [游玩模式 Play Mode]     |     [制作模式 Studio Mode] │
└───────────────────────────┬────────────────────────────┘
                            │
               AG-UI Protocol (SSE / JSON-RPC)
                            │
┌───────────────────────────▼────────────────────────────┐
│              FastAPI Bridge Server (:8001)             │
│    - AGUIBridge: 协议转换、状态打补丁、DM综合裁决引擎       │
│    - ScenarioManager: 剧本加载、资产路由、ZIP打包导入     │
│    - ScriptLinter: 死锁跳转与孤立节点静态分析           │
└───────────────────────────┬────────────────────────────┘
                            │
                     stdin / stdout 管道
                            │
┌───────────────────────────▼────────────────────────────┐
│              Local Agent Engine CLI                    │
│    - Google Antigravity (agy) / OpenAI Codex           │
│    - 内置 Fallback Director（离线/无 Key 时自动接管）    │
└────────────────────────────────────────────────────────┘
```

---

## 测试与验证

项目包含全面的单元测试、端到端测试以及针对用户反馈建立的 **Bad Cases 回归测试套件**（`tests/test_regression_bad_cases.py`），覆盖意图识别防劫持、背包同步防脱节、生存工具去重、多维综合检定裁决、Studio热更新与剧本合法性校验：

```bash
# 运行后端全量测试套件（35 项全量通过）
.venv/bin/pytest -v

# 仅运行 Bad Cases 回归测试集
.venv/bin/pytest -v tests/test_regression_bad_cases.py

# 前端类型检查与构建验证
cd web && npm run build
```

---

## 协议与贡献

本项目采用 [MIT 许可证](LICENSE)。欢迎提交 Issue 反馈问题或发起 Pull Request 参与共建。
