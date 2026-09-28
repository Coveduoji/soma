#!/usr/bin/env bash
# Soma 一键脚本：启动 / 停止 / 状态 / 重启 / 看日志（后端 FastAPI + 前端 Vite dev）
#
# 用法：
#   ./start.sh [start|stop|status|restart|logs]   # 缺省 = start
#   BACKEND_PORT=8010 ./start.sh                   # 自定义后端端口（改端口需同步 vite.config.ts 代理）
#
# start 会自动：加载根 .env、装缺失依赖、跑 alembic 迁移、起后端+前端、打印健康状态。
# 首次运行自动装依赖；Ctrl+C 停止只对前台 logs 子命令有效，其余用 ./start.sh stop。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
LOG_DIR="$ROOT/logs"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
HEALTH_URL="$BACKEND_URL/api/health"

mkdir -p "$LOG_DIR"

is_up() { curl -s -m 2 "$1" >/dev/null 2>&1; }

# 加载根 .env：逐行 export（跳过注释/空行），让 dev 用上真实 SOMA_* 配置（账号/模型 key）。
load_env() {
  [ -f "$ROOT/.env" ] || { echo "[env] 未找到根 .env（可跳过；将退回开发默认账号）"; return 0; }
  local line
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|\#*) continue ;; esac
    export "$line"
  done < "$ROOT/.env"
  echo "[env] 已加载根 .env（SOMA_* 配置）"
}

do_start() {
  load_env

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
  if is_up "$HEALTH_URL"; then
    echo "[backend] :$BACKEND_PORT 已在运行，复用。"
  else
    echo "[backend] 启动 uvicorn :$BACKEND_PORT …"
    # 有 .env 时 SOMA_ADMIN_* 已由 load_env 注入；无 .env 时 SOMA_DEV=1 兜底建 admin/admin。
    (cd backend && export SOMA_DEV=1 && alembic upgrade head && exec python3 -m uvicorn app.main:app --port "$BACKEND_PORT") > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
  fi

  # ---- 前端 ----
  if is_up "$FRONTEND_URL"; then
    echo "[frontend] :$FRONTEND_PORT 已在运行，复用。"
  else
    echo "[frontend] 启动 vite dev :$FRONTEND_PORT …"
    (cd frontend && exec ./node_modules/.bin/vite --port "$FRONTEND_PORT") > "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
  fi

  # ---- 等待就绪 ----
  echo "[wait] 等待服务就绪 …"
  for _ in $(seq 1 120); do
    is_up "$HEALTH_URL" && is_up "$FRONTEND_URL" && break
    sleep 0.5
  done

  echo
  do_status || true
  echo
  echo "  前端  http://localhost:${FRONTEND_PORT}"
  echo "  后端  $BACKEND_URL   (syslog :5514)"
  echo "  日志  $LOG_DIR/"
  echo "  停止  ./start.sh stop"
}

do_stop() {
  local pid
  if [ -f "$FRONTEND_PID_FILE" ]; then
    pid="$(cat "$FRONTEND_PID_FILE")"
    echo "[stop] 前端 pid $pid"
    kill "$pid" 2>/dev/null || true
    rm -f "$FRONTEND_PID_FILE"
  fi
  if [ -f "$BACKEND_PID_FILE" ]; then
    pid="$(cat "$BACKEND_PID_FILE")"
    echo "[stop] 后端 pid $pid"
    kill "$pid" 2>/dev/null || true
    rm -f "$BACKEND_PID_FILE"
  fi
  sleep 1
  if is_up "$HEALTH_URL" || is_up "$FRONTEND_URL"; then
    echo "[stop] 端口仍有监听（可能是外部启动的服务，未强杀）。"
  else
    echo "[stop] 已停止本脚本启动的服务。"
  fi
}

do_status() {
  if ! is_up "$HEALTH_URL"; then
    echo "Soma 状态：后端未运行（$BACKEND_URL 连不上）"
    echo "  启动：./start.sh start"
    return 1
  fi
  curl -s -m 3 "$HEALTH_URL" | python3 "$ROOT/scripts/health_status.py"
}

do_logs() {
  tail -f "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log"
}

# ---- 分发 ----
case "${1:-start}" in
  start)   do_start ;;
  stop)    do_stop ;;
  status)  do_status ;;
  restart) do_stop; do_start ;;
  logs)    do_logs ;;
  *)       echo "用法: ./start.sh [start|stop|status|restart|logs]"; exit 2 ;;
esac
