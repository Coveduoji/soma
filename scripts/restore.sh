#!/usr/bin/env bash
# 从 backup.sh 生成的 tar.gz 归档还原Soma运行数据。
#
# 用法：
#   ./scripts/restore.sh <备份.tar.gz>
#   SOMA_DATA_DIR=/data ./scripts/restore.sh <备份.tar.gz>
#
# 还原前会自动对当前状态再做一次备份（防误操作）。
# 若归档含 secret.key，还原后所有已签发 JWT 失效，需重新登录。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${SOMA_DATA_DIR:-$ROOT/backend}"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -lt 1 ]; then
  echo "用法：./scripts/restore.sh <备份.tar.gz>" >&2
  exit 1
fi
ARCHIVE="$1"

if [ ! -f "$ARCHIVE" ]; then
  echo "[restore] 找不到 $ARCHIVE" >&2
  exit 1
fi

# 还原前备份当前状态
"$SELF_DIR/backup.sh" "$ROOT/backups" >/dev/null

mkdir -p "$DATA_DIR/data"
tar -xzf "$ARCHIVE" -C "$DATA_DIR"

echo "[restore] 已从 $ARCHIVE 还原到 $DATA_DIR"
echo "[restore] 提示：若 secret.key 被替换，所有已登录会话失效，需重新登录。"
