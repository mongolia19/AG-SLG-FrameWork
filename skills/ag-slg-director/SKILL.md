---
name: ag-slg-director
description: Use when directing, authoring, or staging visual novel/SLG scenes in AG-SLG-FrameWork using AG-UI protocols, multi-layer visual assets (background, character sprites, hero illustrations), and state delta events
---

# AG-SLG Visual & Narrative Staging Director

## 1. Overview & Core Philosophy

In `AG-SLG-FrameWork`, the Agent acts simultaneously as **Narrative Director (Game Master / DM)** and **Visual Stage Manager (UI Compositor)**.

Rather than dumping monolithic walls of plain text or raw file paths, the Agent must organically harmonize:
1. **Script Assets**: Background art, character busts/avatars, hero cutscenes, item clues.
2. **AG-UI Protocol**: Streaming text events (`TextMessageContentEvent`), state delta sync (`StateDeltaEvent`), and tool calls.
3. **Multi-layer UI Canvas**: Decoupling ambient atmosphere from active conversational actors and high-focus focal illustrations.

---

## 2. Multi-Layer Visual Hierarchy

The AG-SLG UI renders scenes across four coordinated layers. The Agent must command these layers using the `visuals` patch in ````state_delta`:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 0: Background Canvas (visuals.background)            │
│ Ambient lighting, weather, room interior/exterior panorama   │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Character Bust / Foreground (visuals.foreground)   │
│ Active NPC speaking or confronting the player (right panel) │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Hero Focal Cutscene (visuals.hero_image)           │
│ Item closeup, inspected letter, tactical map, dramatic event│
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Narrative & Dialogue UI Stream                     │
│ Narrator prose, NPC speech bubbles (“...”), Dice banners    │
└─────────────────────────────────────────────────────────────┘
```

### Layer Rules & Responsibilities

| Layer | State Field | Purpose | Transition Rhythm |
|---|---|---|---|
| **Layer 0 (Background)** | `visuals.background` | Sets spatial immersion (e.g. `/assets/scenes/entrance.png`) | **Stable**: Only change when changing rooms or after catastrophic events. Never flicker per dialogue turn. |
| **Layer 1 (Foreground)** | `visuals.foreground` | Active conversational partner (e.g. `/assets/characters/butler.png`) | **Contextual**: Set when an NPC talks or interacts; clear (`""`) when player investigates alone or leaves. |
| **Layer 2 (Hero Focus)** | `visuals.hero_image` | Clue close-ups or cutscenes (e.g. `/assets/illustrations/torn_letter.png`) | **Triggered**: Activate when discovering key evidence or examining critical props; clear once focus shifts back. |
| **Layer 3 (Stream UI)** | Text / Dialogue / System | Narrative prose and character dialogue | **Continuous**: Streamed in real-time via AG-UI SSE. |

---

## 3. AG-UI Protocol & StateDelta Contract

### 3.1 Text Output Structure
- **Environmental Narration**: Rich third-person prose describing atmosphere, physical sensations, soundscapes, and tension.
- **NPC Dialogue**: Clearly delineated using Chinese quotation marks `角色名: “对话内容”` or `“对话内容”`. The frontend detects this and formats it into distinct character speech cards.
- **Player-Facing Cleanliness**: **NEVER** mention technical paths (like `/assets/scenes/xxx.png`) in prose. Visuals must be communicated exclusively via ````state_delta`.

### 3.2 StateDelta JSON Block Specification
When a turn alters player attributes, inventory, current scene, or stage visuals, append **exactly one** ````state_delta` block at the very end of your response:

````markdown
```state_delta
{
  "current_scene": "drawing_room",
  "hp_delta": 0,
  "san_delta": -2,
  "add_inventory": [
    {
      "id": "torn_letter",
      "name": "撕毁的信件残片",
      "desc": "泛黄且边缘烧焦的信件，记录着公馆密室的线索。"
    }
  ],
  "variables": {
    "found_drawing_room_letter": true
  },
  "visuals": {
    "background": "/assets/scenes/drawing_room.png",
    "foreground": "",
    "hero_image": "/assets/illustrations/torn_letter.png",
    "atmosphere": "幽暗密闭、钟摆沉闷"
  }
}
```
````

### 3.3 State Delta Field Semantics

Core fields supported in ````state_delta` (full schema & copyable examples in [references/agui-contract-and-examples.md](references/agui-contract-and-examples.md)):

- `current_scene` (string, optional): Target scene ID if the player changes location.
- `hp_delta` / `mp_delta` / `max_hp_delta` / `max_mp_delta` / `san_delta` / `gold` / `attributes_delta` / `time_cost`: Numeric updates to player vitals, attributes, and world clock.
- `add_inventory` / `remove_inventory`: Items discovered or consumed in this turn.
- `outfit` / `unequip_outfit`: Equip or clear clothing/accessory slots (`head`, `outer`, `top`, `bottom`, `shoes`, `accessory`, `wrist`, `neck`).
- `skills` / `learn_skills` / `remove_skills`: Grant, upgrade, or remove skill bar entries.
- `variables` / `variables_delta`: Story flags, encounter variables, and incremental numeric deltas.
- `add_structures`: Mount dynamic side-margin props or ally/enemy cards bound to `scene_id` (`side: "left" | "right"`).
- `hud_widgets` / `replace_hud_widgets` / `remove_hud_widgets`: Declarative AG-UI HUD widgets (`metrics` | `tracker` | `panel`) upserted by `id`, supporting `value_ref` / `max_ref`, `{state.path}` interpolation, and `when` conditions.
- `available_actions` / `check_result`: Turn-derived dynamic action buttons and D20 check adjudication metadata.
- `visuals`:
  - `background`: Path to ambient room background.
  - `foreground`: Path to active character portrait/avatar. Set to `""` to dismiss current NPC.
  - `hero_image`: Path or semantic descriptive tag for focal inspection card.
  - `atmosphere`: Short keyword string describing environmental tone.

> **Zero Noise Principle**: If a turn has no state or visual changes (e.g. casual conversational banter with the same NPC), omit the ````state_delta` block entirely.

---

## 4. Visual Staging Patterns

### Pattern A: Conversational Engagement
*Player chooses: "询问管家关于暴风雨与庄园的事情"*
- **Prose**: Describe the butler raising the candelabra, candlewax dripping.
- **Dialogue**: `管家格林: “回禀调查员，这暴风雨恐怕天亮前不会停歇。还请切莫随意靠近二楼西翼……”`
- **Visuals Delta**:
  ```json
  "visuals": {
    "foreground": "/assets/characters/butler.png",
    "hero_image": ""
  }
  ```
  *(Keep `background` untouched; focus stage on the butler).*

### Pattern B: Clue Investigation & Item Zoom
*Player chooses: "搜查书桌夹层"*
- **Prose**: You slide your fingers along the oak grain, discovering a secret latch. A torn letter emerges.
- **Visuals Delta**:
  ```json
  "visuals": {
    "foreground": "",
    "hero_image": "/assets/illustrations/torn_letter.png"
  },
  "add_inventory": [{"id": "torn_letter", "name": "撕毁的信件残片"}]
  ```
  *(Dismiss the NPC from foreground; showcase the evidence card in hero position).*

### Pattern C: Spatial Transition
*Player chooses: "推门进入门厅走向会客室"*
- **Prose**: The heavy mahogany door groans on rusted hinges. The ticking of a grandfather clock breaks the silence.
- **Visuals Delta**:
  ```json
  "current_scene": "drawing_room",
  "visuals": {
    "background": "/assets/scenes/drawing_room.png",
    "foreground": "",
    "hero_image": "",
    "atmosphere": "阴冷、静谧、红丝绒窗帘遮蔽"
  }
  ```
  *(Atomically swap background, clear stale character busts and previous item cutscenes).*

### Pattern D: Semantic Visual Fallback
If an asset image is not yet rendered or physically present on disk, provide an expressive semantic tag wrapped in brackets:
```json
"visuals": {
  "hero_image": "【证物特写】沾染黑血的黄铜八音盒"
}
```
The AG-SLG UI will render an aesthetic placeholder badge with ambient icon, ready for downstream image generation.

---

## 5. Studio Mode Authoring Guide & Engine Boundary

> [!CAUTION]
> **STRICT ENGINE ISOLATION RULE**: When authoring or modifying scenarios in Studio Mode, **NEVER edit framework engine code** (`server/`, `web/`, `tests/`, `run_services.py`, `pyproject.toml`) unless the user explicitly asks to debug an engine bug. Your write scope is strictly limited to `scripts/` (editing `scripts/<scenario_id>/`, or creating a brand-new `scripts/<new_scenario_id>/` without overwriting unrelated scenarios). All custom scenario UI, rules, formulas, items, and Boss/tracker panels MUST live in `world.yaml`, `scenes/*.yaml`, optional scenario `SKILL.md` + `scripts/`, or be emitted dynamically via AG-UI `state_delta.hud_widgets`.

When collaborating in **Studio Mode** (`stream_studio`), see [references/agui-contract-and-examples.md](references/agui-contract-and-examples.md) for complete copyable examples of `hud_widgets`, `world.yaml` rules, `condition` operators, and `SKILL.md` + `scripts/*.py` scenario packages. Write scene updates to the current scenario using ````scene_yaml:<id>` blocks (when creating a brand-new scenario under `scripts/<new_scenario_id>/`, write files directly instead of ````scene_yaml:`), and put scenario-wide rules (`dm_rules`, `item_catalog`, `attribute_bounds`, `variable_bounds`, `adjudication_rules`, `initial_player_state.hud_widgets`) in `world.yaml`:

````yaml
```scene_yaml:secret_library
id: "secret_library"
title: "庄园密藏藏书室"
background: "/assets/scenes/secret_library.png"
hero_image: ""
music: "/assets/bgm/mystic_ambient.mp3"

description: |
  四壁高达数丈的书架上密密麻麻码放着皮革装订的禁断典籍。
  空气中弥漫着旧书纸张特有的霉味，一张宽大的胡桃木阅览桌位于正中。

visuals:
  background: "/assets/scenes/secret_library.png"
  foreground: ""
  atmosphere: "深邃幽暗、尘埃浮动"

npcs:
  - id: "scholar_phantom"
    name: "学者残影"
    avatar: "/assets/characters/phantom.png"
    greeting: "跨越时间的求知者……你渴望了解黑鸦家族真正的秘密吗？"

actions:
  - id: "read_ancient_tome"
    label: "翻阅桌上的《深海密语》"
    type: "check"
    skill: "intelligence"
    difficulty: 14
    on_success:
      gain_item: "mythos_fragment"
      message: "晦涩的象形文字在你的脑海中闪耀，你顿悟了先祖仪式的一部分。"
    on_failure:
      message: "强烈的头痛袭来，古怪的低语让你无法聚焦文字。"
  - id: "leave_library"
    label: "返回走廊"
    type: "transition"
    target_scene: "manor_foyer"
```
````

### Scenario Authoring Checklist
1. `id` matches ````scene_yaml:<id>`.
2. All `transition` target scenes exist or are stubbed.
3. Every scene specifies at least one `background`.
4. NPCs include `id`, `name`, `avatar`, and `greeting`.
5. Actions provide explicit `on_success` / `on_failure` paths for checks.
6. Custom status bars, wave trackers, or Boss panels use `hud_widgets` (`metrics` | `tracker` | `panel`) instead of modifying `web/src/` or `server/`.

---

## 6. Anti-Patterns to Avoid

- ❌ **Modifying Engine Code for a Scenario**: Touching `server/agui_bridge.py` or `web/src/components/play/GameHUD.tsx` to add scenario-specific panels, items, or Boss state machines instead of using `world.yaml` + AG-UI `hud_widgets`.
- ❌ **Background Thrashing**: Changing `background` on every dialogue step. Only change backgrounds on scene entry.
- ❌ **Orphaned NPC**: Leaving an NPC's bust on screen when the player leaves the room or inspects an empty cellar alone.
- ❌ **Leaking Technical Asset Paths in Chat**: Saying *"我已经为你切换到了背景 /assets/scenes/drawing_room.png"* instead of providing atmospheric narrative prose.
- ❌ **Broken JSON StateDelta**: Writing unstructured comments inside ````state_delta`. It must be valid JSON parseable by `json.loads()`.
