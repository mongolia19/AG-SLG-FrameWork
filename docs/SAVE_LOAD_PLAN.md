# AG-SLG-FrameWork 游玩进度保存与读取设计计划

## 1. 目标与原则（Ponytail）

在 Play 运行端为当前剧本提供**显式的手动存档（保存）与读档（读取 / 删除）**能力，支持多存档槽位管理与跨刷新/跨浏览器持久化：
- **最小完整改动**：直接复用 [PlayView.tsx](/Users/a58/work/AG-SLG-FrameWork/web/src/components/play/PlayView.tsx) 既有的全量进度快照结构（`playerState`、`messages`、`activeVisuals`、`dynamicActions`、`lastTurn`），不发明新的状态序列化格式，不引入外部数据库或多余依赖。
- **数据安全与边界校验**：对 `scenario_id` 与 `save_id` 做严格白名单字符校验防路径穿越；存档目录 `saves/` 加入 [.gitignore](/Users/a58/work/AG-SLG-FrameWork/.gitignore) 避免污染仓库。

---

## 2. 整体方案

### 2.1 存储与后端接口（[server/app.py](/Users/a58/work/AG-SLG-FrameWork/server/app.py)）
按剧本分目录落盘于 `saves/{scenario_id}/{save_id}.json`（JSON 文件存储，天然支持跨标签/跨端口持久化与直接单测验证）：
- `GET /api/scenarios/{scenario_id}/saves`：列出该剧本下所有存档摘要（`id`、`name`、`scene_id`、`scene_title`、`player_name`、`hp`、`max_hp`、`saved_at`），按 `saved_at` 倒序返回。
- `POST /api/scenarios/{scenario_id}/saves`：接收前端传入的存档名称与完整游玩快照，校验剧本存在后生成唯一 `save_id`（`save_<ms>_<hex>`）写盘并返回存档摘要。
- `GET /api/scenarios/{scenario_id}/saves/{save_id}`：读取指定存档完整快照 JSON。
- `DELETE /api/scenarios/{scenario_id}/saves/{save_id}`：删除指定存档文件。

### 2.2 前端状态同步与交互（[PlayView.tsx](/Users/a58/work/AG-SLG-FrameWork/web/src/components/play/PlayView.tsx) & [GameHUD.tsx](/Users/a58/work/AG-SLG-FrameWork/web/src/components/play/GameHUD.tsx)）
- **保存（Save）**：
  - 流式推演中禁用保存，避免保存半截状态；非流式状态下可将当前 `playerState`、`messages`、`activeVisuals`、`dynamicActions`、`lastTurn` 提交至 `POST /api/scenarios/{scenario_id}/saves`。
  - 支持输入自定义存档备注；留空时默认生成 `<场景标题> · <时间>`。
- **读取（Load）**：
  - 从 `GET /api/scenarios/{scenario_id}/saves/{save_id}` 获取快照后，若当前有进行中的请求则先中止并递增 `sessionEpochRef`。
  - 使用既有的 `hydrateMissingStateDefaults(...)` 补齐剧本升级后的新增字段（如 `hud_widgets`、`max_hp`、`mp`），并校验目标 `current_scene` 仍存在于当前剧本中。
  - **服务端会话隔离**：读档时生成全新 `threadId` 并更新本地 `ag_slg_save_{scenarioId}`（更新 `resetAt`/`savedAt` 防跨标签页旧状态反覆盖），确保下一回合自动通过 `forwarded_props.player_state` + `recent_history` 重建干净的后端 `GameSession` 与新的 Agent 会话，不与旧回合混淆。
- **入口 UI**：
  - 在 [GameHUD.tsx](/Users/a58/work/AG-SLG-FrameWork/web/src/components/play/GameHUD.tsx) 顶部操作栏新增「**存档**」按钮（与「同步剧本」「重置」并列），点击打开统一的「存档管理（保存 / 读取 / 删除）」弹窗。

### 2.3 自动存档兼容
- 保留现有的 `localStorage`（`ag_slg_save_{scenarioId}`）自动续玩机制不受影响；手动存档作为命名检查点共存。

---

## 3. 涉及文件与验证计划

| 模块 | 文件 | 改动说明 |
|---|---|---|
| 忽略配置 | [.gitignore](/Users/a58/work/AG-SLG-FrameWork/.gitignore) | 新增 `saves/` 忽略规则 |
| 后端接口 | [server/app.py](/Users/a58/work/AG-SLG-FrameWork/server/app.py) | 实现 4 个 `/api/scenarios/{scenario_id}/saves*` 端点与路径/剧本校验 |
| 游玩容器 | [PlayView.tsx](/Users/a58/work/AG-SLG-FrameWork/web/src/components/play/PlayView.tsx) | 暴露当前状态读写边界（`handleSaveSlot` / `handleLoadSlot` / 存档列表请求） |
| HUD 弹窗 | [GameHUD.tsx](/Users/a58/work/AG-SLG-FrameWork/web/src/components/play/GameHUD.tsx) | 新增「存档」按钮及保存/读取/删除弹窗，附 [types.ts](/Users/a58/work/AG-SLG-FrameWork/web/src/types.ts) 类型定义 |
| 回归测试 | [tests/test_save_load.py](/Users/a58/work/AG-SLG-FrameWork/tests/test_save_load.py) | 覆盖保存、列表排序、读取恢复、跨存档隔离、删除与非法 ID 防护，以及读档后继续游玩端到端验证 |

验证命令：`.venv/bin/pytest -q && npm --prefix web run build`
