# AG-SLG-FrameWork ACP 协议重构计划

## 1. 重构背景与目标

当前 [server/agent_driver.py](/Users/a58/work/AG-SLG-FrameWork/server/agent_driver.py) 采用**每回合冷启动短命子进程**模式：
- `AgyDriver` 每轮执行一次 `agy -p "..." --output-format stream-json --conversation <id>`。
- `CodexDriver` 每轮执行一次 `codex exec --json "..."`，不复用 `conversation_id`，也无法解析工具调用事件。
- `stream_studio`（[server/agui_bridge.py](/Users/a58/work/AG-SLG-FrameWork/server/agui_bridge.py)）与 [AuthoringChat.tsx](/Users/a58/work/AG-SLG-FrameWork/web/src/components/studio/AuthoringChat.tsx) 每次请求生成新的 `thread_id` 且固定传入 `conversation_id=None`，导致 Studio 多轮对话完全无上下文。

本次重构遵照 **Ponytail 极简原则**，在不改变上层 `BaseAgentDriver` / `AgentEvent` / AG-UI SSE 接口的前提下，将 `agy` 与 `codex` 统一切换为 **标准 ACP（Agent Client Protocol, JSON-RPC 2.0 over stdio）长驻双向交互**。

---

## 2. 实机协议探测结论（已验证）

1. **`agy` 侧**：本机 `agy acp --dangerously-skip-permissions` 原生支持 ACP v1（`loadSession: true`、`session/resume`、`session/load`、`agent_message_chunk`、`tool_call`、`tool_call_update`）。
2. **`codex` 侧**：通过 `@agentclientprotocol/codex-acp`（优先查找 `CODEX_ACP_BIN` / `codex-acp`，回退 `npx --yes @agentclientprotocol/codex-acp`）并注入 `CODEX_PATH=<本地 codex 可执行路径>`，可正常完成 ACP v1 握手、`session/new`、`session/resume` 与 `session/prompt`。
3. **关键边界**：
   - ACP 单行 JSON-RPC 响应/通知（如 `available_commands_update`）可能超过 Python `asyncio` 默认的 64KB 行缓冲限制，子进程必须设置 `limit=10 * 1024 * 1024`。
   - 响应返回前可能穿插任意数量服务端通知（如 `_auth/status_update`、`session/update`）和双向请求（`session/request_permission`），需由后台读循环按 `id` 和 `sessionId` 分发路由。

---

## 3. 最小改动范围与架构设计

### 3.1 驱动层：[server/agent_driver.py](/Users/a58/work/AG-SLG-FrameWork/server/agent_driver.py)
- 新增 **`AcpDriver(BaseAgentDriver)`**（零新增第三方依赖，基于标准库 `asyncio` + `json` 实现）：
  - **长驻进程与按需重启**：惰性启动 ACP stdio 子进程并完成 `initialize`；若进程意外退出或 EOF，清理状态并在下一次调用时自动重建。
  - **多路复用路由循环 (`_read_loop`)**：
    - 收到带 `id` 且含 `result`/`error` 的响应 → 唤醒对应 `Future`。
    - 收到 `session/update` 通知 → 投递到对应 `sessionId` 的 `asyncio.Queue`。
    - 收到服务端主动发起的 `session/request_permission` 请求 → 自动选择第一个 `allow*` 选项并回写 JSON-RPC 响应（避免工具调用卡死）。
  - **会话连续性**：
    - 若传入的 `conversation_id` 已存在于活跃进程中，直接复用。
    - 若是服务重启后的历史 `conversation_id`，优先尝试 `session/resume`（失败则尝试 `session/load`），仍不可用则平滑降级为 `session/new` 并回传新 `sessionId`。
  - **事件映射**：
    - `agent_message_chunk` (`text`) → `AgentEvent(event_type="text_delta")`
    - `tool_call` / `tool_call_update` → `AgentEvent(event_type="tool_call_start" | "tool_call_end")`
    - `session/prompt` 完成/报错 → `AgentEvent(event_type="done" | "error")`
  - 提供 `aclose()` 方法，在服务关闭时优雅回收子进程。
- **保留兼容导出**：
  - `AgyDriver(AcpDriver)`：默认命令 `["agy", "acp", "--dangerously-skip-permissions"]`。
  - `CodexDriver(AcpDriver)`：默认解析 `codex-acp`（或 `npx --yes @agentclientprotocol/codex-acp`）并自动设置 `CODEX_PATH`。
  - `MockAgentDriver` 保持不变，确保既有 40+ 单测无侵入通过。

### 3.2 服务生命周期：[server/app.py](/Users/a58/work/AG-SLG-FrameWork/server/app.py)
- 保持 `AG_DRIVER`（`agy` / `codex` / `mock`）和 `/health` 行为不变。
- 注册 FastAPI shutdown 钩子，退出时调用 `await driver.aclose()`，避免残留 ACP 子进程。

### 3.3 会话与上文连续性：[server/agui_bridge.py](/Users/a58/work/AG-SLG-FrameWork/server/agui_bridge.py) & [AuthoringChat.tsx](/Users/a58/work/AG-SLG-FrameWork/web/src/components/studio/AuthoringChat.tsx)
- **`AGUIBridge`**：新增 `studio_sessions: Dict[str, str]`（按 `thread_id` 记录 Studio 的 ACP `sessionId`），在 `stream_studio` 中传入并回写 `conversation_id`，让 Studio 模式同样享有 ACP 多轮上下文记忆。
- **`AuthoringChat.tsx`**：为每个 `scenarioId` 维护稳定的 `thread_id`（而非每次请求 `studio-${Date.now()}`），并随对话缓存持久化；提供“清空对话”重置 `thread_id` 的最小能力（仅在已有需求范围内保持线程连续性）。

### 3.4 自动化测试与真机验证
- 新增 [tests/test_acp_driver.py](/Users/a58/work/AG-SLG-FrameWork/tests/test_acp_driver.py)：使用本地模拟 ACP stdio 子进程覆盖：
  1. `initialize` + `session/new` + `session/prompt` 流式文本与工具调用事件映射；
  2. 同一 `conversation_id` 多轮复用 & 进程重启后 `session/resume` 恢复；
  3. `session/request_permission` 自动审批响应；
  4. 超过 64KB 单行 JSON-RPC 通知不崩溃；
  5. 子进程异常退出时的错误上报与下次自动重启恢复。
- 全量回归测试：`.venv/bin/pytest -v` 与前端 `npm run build`。
- 真机联调验证：使用真实 `agy acp` 跑通 Play / Studio 端到端链路，并验证 `codex-acp` 握手与配置就绪。

---

## 4. 实施步骤

1. 落盘本计划文档（`docs/ACP_REFACTOR_PLAN.md`）。
2. 重构 `server/agent_driver.py`（实现 `AcpDriver`、`AgyDriver`、`CodexDriver`）与 `server/app.py`（进程关闭清理）。
3. 打通 `server/agui_bridge.py` 与 `web/src/components/studio/AuthoringChat.tsx` 的 Studio ACP 会话复用。
4. 编写 `tests/test_acp_driver.py` 并运行全量 pytest + 前端构建。
5. 运行真实 `agy acp` / `codex-acp` 端到端验证并重启本地服务（若服务处于运行态）。
