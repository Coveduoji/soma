#!/usr/bin/env bash
# 离线部署打包：在【能上网的机器】上执行，产出可拷入纯内网的完整部署包。
#
# 用法：./scripts/offline_bundle.sh [输出目录，默认 ./dist-offline]
#
# 产出内容：
#   neuroimmune-images-<时间戳>.tar.gz   四个镜像（backend + nginx + kafka + filebeat）
#   docker-compose.yml                   部署编排
#   .env.example                         环境变量模板（内网填密码/token 后改名 .env）
#   backup.sh / restore.sh               备份恢复脚本
#
# 内网机三步：gunzip | docker load → 填 .env → docker compose up -d --no-build
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$ROOT/dist-offline}"
STAMP="$(date +%Y%m%d-%H%M%S)"
cd "$ROOT"

echo "=== 1/5 构建镜像（拉基础镜像 + 装 pip/npm 依赖）==="
docker compose build

echo "=== 2/5 拉取 image 类镜像（kafka + filebeat，非 build 的）==="
docker pull apache/kafka:3.9.0
docker pull elastic/filebeat:8.15.0

echo "=== 3/5 导出镜像为 tar.gz ==="
mkdir -p "$OUT_DIR"
docker save neuroimmune-backend:latest neuroimmune-nginx:latest apache/kafka:3.9.0 elastic/filebeat:8.15.0 \
  | gzip > "$OUT_DIR/neuroimmune-images-$STAMP.tar.gz"

echo "=== 4/5 拷贝部署文件 ==="
cp docker-compose.yml "$OUT_DIR/"
cp .env.example "$OUT_DIR/"
mkdir -p "$OUT_DIR/deploy"
cp deploy/filebeat.yml "$OUT_DIR/deploy/"
cp scripts/backup.sh scripts/restore.sh "$OUT_DIR/"

echo "=== 5/5 完成 ==="
echo
echo "打包目录：$OUT_DIR/"
ls -lh "$OUT_DIR/" | grep -vE '^total|^d'
echo
echo "拷贝整个目录进内网机，然后在内网机执行："
echo "  gunzip -c neuroimmune-images-*.tar.gz | docker load"
echo "  cp .env.example .env     # 填 NEUROIMMUNE_ADMIN_PASSWORD / NEUROIMMUNE_API_TOKEN"
echo "  docker compose up -d --no-build"
