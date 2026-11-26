# AG-SLG-FrameWork

<div align="center">

![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)
![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg?logo=typescript)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi)
![AG-UI Protocol](https://img.shields.io/badge/AG--UI-Native-orange.svg)

**English** | [简体中文](README.zh-CN.md)

An Agent-driven Interactive Fiction / TRPG engine built natively on the **AG-UI Protocol** and **ACP (Agent Client Protocol)**.  
Decouples AI narrative generation from structured game state through real-time SSE streaming, JSON-Patch state deltas, multi-layer visual staging, and a built-in Studio editor.

[Quick Start](#quick-start) • [Core Features](#core-features) • [Built-in Scenarios](#built-in-scenarios) • [Architecture](#architecture) • [Testing](#testing)

</div>

---

## Overview

AG-SLG-FrameWork bridges local autonomous coding/reasoning Agent CLIs (`agy`, `codex`) and a visual web game client over standard **AG-UI SSE** (`RUN_STARTED` → `TEXT_MESSAGE_*` / `TOOL_CALL_*` → `STATE_DELTA` → `RUN_FINISHED`).  
Scenarios are 100% data-driven YAML bundles (`world.yaml` + `scenes/*.yaml` + `assets/`) with declarative rules, dynamic HUD widgets, and zero scenario-specific hardcoding required in the UI.

---

## Core Features

- **Hot-Swappable Dual Agent Backends + Offline Fallback**
  - Persistent **ACP (JSON-RPC 2.0 over stdio)** drivers for **Antigravity (`agy acp`)** and **OpenAI Codex (`codex-acp` / `npx @agentclientprotocol/codex-acp`)**.
  - Switch backends live from the header selector (`POST /api/driver`) or CLI (`python run_services.py restart codex`), persisted in `.agent_driver`.
  - Built-in deterministic **Fallback Director** keeps Play and Studio usable offline or without external API keys.
- **Multi-Dimensional TRPG Adjudication**
  - Four-tier outcome resolution: **Critical Success**, **Success**, **Partial Success**, and **Failure / Complication**.
  - Evaluates character attributes, equipped outfit slots, inventory tools, skills, weather/time conditions, and physiological/combat vitals.
- **Data-Driven Visual Staging & Dynamic HUD**
  - Multi-layer scene rendering: `background`, `foreground`, collapsible `hero_image` focus cards, `atmosphere` badges, and left/right conditional `decorations` (ambient props & built structures).
  - Declarative `hud_widgets` (metrics bars, boss encounter trackers, companion status cards), plus **Skills**, **Outfit**, and **Inventory** modals.
- **Play Progress Controls**
  - **Save / Load / Delete** named checkpoints per scenario (`saves/{scenario_id}/`), alongside automatic `localStorage` continuity.
  - **Edit Input & Regenerate Turn** with full client + server session rollback to pre-turn state.
- **Dual Mode: Play + Studio**
  - **Play Mode**: Preset actions, D20 dice checks, custom free-form input, and live Studio hot-sync.
  - **Studio Mode**: Scene topology & node editor, static `ScriptLinter` checks, ZIP bundle export/import, and a persistent Co-pilot chat that writes validated `scene_yaml` directly to disk.
- **Cross-Platform Support**: Runs on **macOS, Linux, and Windows** (`run_services.py` handles platform-specific venv paths, `.cmd` wrappers for `vite`/`npx`/`codex-acp`, port cleanup, and portable ZIP paths).

---

## Built-in Scenarios

| Scenario ID | Title | Highlights |
|---|---|---|
| `island_survival` | 荒岛余生 (*Island Survival*) | Survival vitals (stamina, hydration, fullness, temperature), weather & time-slot cycle, craftable structures, free-form tool/fire/cooking intent matching |
| `wow_elwynn_rpg` | 艾泽拉斯传说：法戈第矿洞之影 (*Legends of Azeroth*) | Class selection (Paladin / Hunter / Mage / Warrior), skill cards, HP/MP bars, turn-based combat & multi-phase boss `hud_widgets` |
| `black_crow_manor` | 黑鸦庄园 (*Black Crow Manor*) | Gothic mystery investigation, clue collection, skill checks, NPC trust progression |

---

## Quick Start

### Prerequisites
- **Python 3.10+** (with `uv` or `pip`)
- **Node.js 18+**
- *(Optional)* Local `agy` or `codex` CLI for live Agent inference (works without them via Fallback Director)

### 1. Clone the Repository
```bash
git clone https://github.com/mongolia19/AG-SLG-FrameWork.git
# Or Gitee mirror:
# git clone https://gitee.com/idroid23/ag-slg-frame-work.git
cd AG-SLG-FrameWork
```

### 2. Install Backend & Frontend Dependencies

**macOS / Linux:**
```bash
uv sync --extra dev
# Or with venv + pip:
# python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

cd web && npm install && npm run build && cd ..
```

**Windows (PowerShell):**
```powershell
uv sync --extra dev
# Or with venv + pip:
# python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e ".[dev]"

cd web; npm install; npm run build; cd ..
```

### 3. Start Services (Cross-Platform)
```bash
# Start both FastAPI (:8001) and Vite (:5173)
python run_services.py start

# Optional: start directly with a specific backend (agy | codex | mock)
python run_services.py restart codex

# Service management
python run_services.py status
python run_services.py stop
```

Open `http://localhost:5173` in your browser (API docs at `http://127.0.0.1:8001/docs`).

---

## Scenario Bundle Layout

Each scenario lives in its own self-contained folder under `scripts/`:

```text
scripts/<scenario_id>/
├── world.yaml              # World config, initial player state, hud_widgets, item/weather rules
├── scenes/                 # Scene YAML nodes (description, visuals, npcs, actions, conditions)
│   └── ...
└── assets/                 # Co-located scenario images & audio
    ├── scenes/
    ├── illustrations/
    ├── characters/
    ├── props/
    └── items/
```

Use **Export Bundle** / **Import Bundle** in Studio to share portable `.zip` packages across platforms.

---

## Architecture

```text
┌──────────────────────────────────────────────────────────┐
│                     Web Browser UI                       │
│        React 18 + TypeScript + TailwindCSS + Vite        │
│    [Play Mode: HUD / Story / Actions / Saves / Retry]    │
│    [Studio Mode: Topology / YAML / Linter / Co-pilot]    │
└────────────────────────────┬─────────────────────────────┘
                             │ AG-UI Protocol (SSE + REST)
┌────────────────────────────▼─────────────────────────────┐
│               FastAPI Bridge Server (:8001)              │
│  - AGUIBridge: prompt builder, StateDelta, adjudication  │
│  - ScenarioManager: YAML loader, asset routing, ZIP I/O  │
│  - ScriptLinter & Save/Load slot persistence (saves/)    │
└────────────────────────────┬─────────────────────────────┘
                             │ ACP (JSON-RPC 2.0 stdio)
┌────────────────────────────▼─────────────────────────────┐
│                Local Agent Engine CLI                    │
│  - AgyDriver (agy acp)  |  CodexDriver (codex-acp)       │
│  - MockAgentDriver & built-in Fallback Director          │
└──────────────────────────────────────────────────────────┘
```

---

## Testing

```bash
# Backend full test suite (pytest)
# macOS / Linux:
.venv/bin/pytest -v
# Windows:
.\.venv\Scripts\pytest.exe -v

# Frontend TypeScript check & production bundle
cd web && npm run build
```

---

## License

This project is open-source under the MIT License. Issues and Pull Requests are welcome.
