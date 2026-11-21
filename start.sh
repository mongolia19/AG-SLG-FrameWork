#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=== AG-SLG-FrameWork 启动 ==="

# 1. 检查 Python 虚拟环境
if [ ! -d ".venv" ]; then
    echo "创建 Python 虚拟环境..."
    uv venv .venv
    source .venv/bin/activate
    uv pip install fastapi uvicorn pydantic pyyaml ag-ui-protocol httpx pytest pytest-asyncio
else
    source .venv/bin/activate
fi

# 2. 启动 FastAPI 后端 (8001)
echo "启动 AG-UI 桥接后端 (http://127.0.0.1:8001)..."
python -m uvicorn server.app:app --host 127.0.0.1 --port 8001 &
SERVER_PID=$!


# 3. 启动前端 Vite (5173)
if [ -d "web" ]; then
    echo "启动 Web 前端 (http://localhost:5173)..."
    cd web
    npm run dev &
    WEB_PID=$!
    cd ..
fi

cleanup() {
    echo "停止服务..."
    kill $SERVER_PID 2>/dev/null || true
    kill $WEB_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
