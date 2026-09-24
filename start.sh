#!/usr/bin/env bash
# 一键启动「Soma」工作台：后端 FastAPI(:8000) + 前端 Vite dev(:5173)
#
# 用法：
#   ./start.sh                       # 启动（已在运行的服务自动复用，不重复起）
#   BACKEND_PORT=8010 ./start.sh     # 自定义后端端口
#   FRONTEND_PORT=5174 ./start.sh    # 自定义前端端口
#
# 首次运行自动装依赖（pip install / npm install）；模型与 syslog 配置在 prototype/.env
#（key 留空 = mock 零成本）。Ctrl+C 停止本脚本启动的服务。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

STARTED_PIDS=()

is_up() { curl -s -m 2 "$1" >/dev/null 2>&1; }

cleanup() {
  if [ ${#STARTED_PIDS[@]} -gt 0 ]; then
    echo; echo "[stop] 停止本脚本启动的服务…"
    kill "${STARTED_PIDS[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# ---- 依赖检查 ----
if ! python3 -c "import fastapi, uvicorn, httpx, pydantic" >/dev/null 2>&1; then
  echo "[setup] 缺后端依赖，安装 backend/requirements.txt …"
  python3 -m pip install -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules ]; then
  echo "[setup] 缺前端依赖，安装 npm 包 …"
  (cd frontend && npm install)
fi

# ---- 后端 ----
if is_up "http://127.0.0.1:${BACKEND_PORT}/api/health"; then
  echo "[backend] :${BACKEND_PORT} 已在运行，复用。"
else
  echo "[backend] 启动 uvicorn :${BACKEND_PORT} …"
  (cd backend && export SOMA_DEV=1 && alembic upgrade head && exec python3 -m uvicorn app.main:app --port "$BACKEND_PORT") > "$LOG_DIR/backend.log" 2>&1 &
  STARTED_PIDS+=("$!")
fi

# ---- 前端 ----
if is_up "http://127.0.0.1:${FRONTEND_PORT}"; then
  echo "[frontend] :${FRONTEND_PORT} 已在运行，复用。"
else
  echo "[frontend] 启动 vite dev :${FRONTEND_PORT} …"
  (cd frontend && exec ./node_modules/.bin/vite --port "$FRONTEND_PORT") > "$LOG_DIR/frontend.log" 2>&1 &
  STARTED_PIDS+=("$!")
fi

# ---- 等待就绪 ----
echo "[wait] 等待服务就绪 …"
for _ in $(seq 1 120); do
  is_up "http://127.0.0.1:${BACKEND_PORT}/api/health" && is_up "http://127.0.0.1:${FRONTEND_PORT}" && break
  sleep 0.5
done

echo
echo "=================================================="
echo "  后端  http://localhost:${BACKEND_PORT}   (API · syslog :5514)"
echo "  前端  http://localhost:${FRONTEND_PORT}"
echo "  日志  $LOG_DIR/"
echo "  Ctrl+C 停止本脚本启动的服务"
echo "=================================================="

# 前台等待：任一被本脚本启动的服务退出即收尾
while [ ${#STARTED_PIDS[@]} -gt 0 ]; do
  alive=1
  for pid in "${STARTED_PIDS[@]}"; do
    kill -0 "$pid" 2>/dev/null || alive=0
  done
  [ "$alive" = 0 ] && { echo "[exit] 有服务退出，见 $LOG_DIR/"; break; }
  sleep 1
done
