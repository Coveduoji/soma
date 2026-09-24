#!/usr/bin/env bash
# 无 Docker 离线部署打包：在【能上网的机器】上执行，产出纯内网可直接部署的目录。
#
# 用法：./scripts/offline_bundle_no_docker.sh [输出目录，默认 ./dist-offline-nodocker]
#       PY_TARGET=3.12 PLATFORM=manylinux2014_aarch64 ./scripts/offline_bundle_no_docker.sh   # 覆盖目标 Python/架构
#
# 产出（目录结构 = 内网机 /opt/soma 应放的结构）：
#   wheels/                后端全部依赖的 wheel 包（与内网机同 Python/OS/架构）
#   backend/  prototype/   源码（已剔除本机 DB/密钥/缓存）
#   frontend/dist/         前端静态产物（后端直接托管，无需 nginx）
#   deploy/soma.service         systemd 常驻单元
#   deploy/soma.env.example     环境变量模板
#
# 内网机部署见 README「纯内网离线部署（无 Docker）」。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$ROOT/dist-offline-nodocker}"
PY="${PYTHON:-python3}"

cd "$ROOT"
mkdir -p "$OUT_DIR"

echo "=== 1/4 下载后端依赖 wheel（目标：Python ${PY_TARGET:-3.11} / ${PLATFORM:-manylinux2014_x86_64}）==="
PY_TARGET="${PY_TARGET:-3.11}"
ABI="cp${PY_TARGET//./}"                       # 3.11 -> cp311
PLATFORM="${PLATFORM:-manylinux2014_x86_64}"   # 最兼容(glibc≥2.17)；ARM 服务器改 manylinux2014_aarch64
"$PY" -m pip download -r backend/requirements.txt -d "$OUT_DIR/wheels" \
  --only-binary=:all: \
  --python-version "$PY_TARGET" \
  --platform "$PLATFORM" \
  --implementation cp \
  --abi "$ABI"

echo "=== 2/4 构建前端静态产物 ==="
(cd frontend && npm ci && npm run build)

echo "=== 3/4 拷贝源码 + 前端产物 ==="
cp -r backend "$OUT_DIR/backend"
cp -r prototype "$OUT_DIR/prototype"
mkdir -p "$OUT_DIR/frontend"
cp -r frontend/dist "$OUT_DIR/frontend/dist"
# 剔除本机运行时数据与缓存，避免把开发机的 DB/密钥/规则拷进内网
find "$OUT_DIR/backend" "$OUT_DIR/prototype" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
rm -f "$OUT_DIR"/backend/*.db "$OUT_DIR"/backend/*.sqlite "$OUT_DIR"/backend/secret.key \
      "$OUT_DIR"/backend/*.json "$OUT_DIR"/backend/data/*.jsonl 2>/dev/null || true
rm -f "$OUT_DIR"/prototype/data/tolerance.json "$OUT_DIR"/prototype/data/innate_rules.json \
      "$OUT_DIR"/prototype/data/memory.jsonl "$OUT_DIR"/prototype/data/history.jsonl \
      "$OUT_DIR"/prototype/data/last_run.json 2>/dev/null || true
# 剔除开发机的 .env（含真实 key），内网模型配置改在 /etc/soma.env 里给
rm -f "$OUT_DIR"/prototype/.env "$OUT_DIR"/backend/.env 2>/dev/null || true

echo "=== 4/4 拷贝部署文件 ==="
mkdir -p "$OUT_DIR/deploy"
cp deploy/soma.service "$OUT_DIR/deploy/" 2>/dev/null || true
cp deploy/soma.env.example "$OUT_DIR/deploy/" 2>/dev/null || true

echo
echo "打包完成：$OUT_DIR/"
echo "内网机三步："
echo "  1) 拷目录到 /opt/soma"
echo "  2) python3.11 -m venv /opt/soma/venv && /opt/soma/venv/bin/pip install --no-index --find-links wheels -r backend/requirements.txt"
echo "  3) 按 deploy/soma.env.example 填 /etc/soma.env，再 systemctl enable --now soma"
