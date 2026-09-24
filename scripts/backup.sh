#!/usr/bin/env bash
# 备份Soma运行数据：SQLite（热备份）+ JSON 状态 + secret.key + 记忆/反馈 → tar.gz 归档。
#
# 用法：
#   ./scripts/backup.sh                 # 归档到 ./backups/
#   ./scripts/backup.sh /path/to/dir    # 指定输出目录
#   SOMA_DATA_DIR=/data ./scripts/backup.sh   # 指定数据目录（默认 backend/）
#
# Docker 部署：数据在命名卷 soma-data 里，可用一次性容器执行本脚本，
# 或先 `docker compose cp` / 挂卷跑。丢 secret.key 会让所有 JWT 失效（需重新登录）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${SOMA_DATA_DIR:-$ROOT/backend}"
OUT_DIR="${1:-$ROOT/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/soma-backup-$STAMP.tar.gz"
TMP="$(mktemp -d)"
mkdir -p "$OUT_DIR" "$TMP/data"

# 1) SQLite 热备份（Python backup API，服务运行中安全）
if [ -f "$DATA_DIR/soma.db" ]; then
  python3 - "$DATA_DIR/soma.db" "$TMP/soma.db" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close(); src.close()
PY
  echo "[backup] SQLite 已备份"
else
  echo "[backup] 未找到 DB（$DATA_DIR/soma.db），跳过" >&2
fi

# 2) JSON 状态 + 密钥
for f in secret.key knob.json knob_presets.json freq.json mode.json gating.json model.json detection.json ingest.json webhooks.json; do
  [ -f "$DATA_DIR/$f" ] && cp -f "$DATA_DIR/$f" "$TMP/$f"
done

# 3) 记忆 / 反馈（RAG 素材）
for f in feedback.jsonl memory.jsonl; do
  [ -f "$DATA_DIR/data/$f" ] && cp -f "$DATA_DIR/data/$f" "$TMP/data/$f"
done

tar -C "$TMP" -czf "$OUT" .
rm -rf "$TMP"
echo "[backup] 已生成 $OUT"
