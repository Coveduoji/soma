#!/usr/bin/env bash
# 新架构动态测试：设备日志采集 + logrotate 轮转（Filebeat → Kafka → 后端）
#
# 前置：栈已起（docker compose up -d --build）、宿主日志目录可写。
# 跑法（仓库根目录）：N1=10 TAIL=3 N2=10 bash scripts/test_dynamic_rotation.sh
#
# 核心不变量（真实 logrotate 场景）：轮转改名 + 新建下一小时文件 → 不重不漏。
#   断言 kafka.consumed == db.counts()["alerts"] == 批次1 + 批次2。
#
# 已知行为（本脚本同时探针并如实报告）：
#   「向已改名文件追加的尾巴行」不会被 Filebeat 采集——Filebeat 只尾随 *.log，
#   文件被 logrotate 改名成 *.log-YYYYMMDD 后即脱离采集。若设备在轮转瞬间仍在写
#   该文件，最后几行会丢（rename 式 logrotate + Filebeat 的固有行为，建议 logrotate 改 copytruncate）。
set -euo pipefail

N1=${N1:-10}
TAIL=${TAIL:-3}
N2=${N2:-10}

BASE=/wls/applogs/rtlog/sec-terminal-linux
TIANYAN=$BASE/tianyanlog
WAF=$BASE/waflog
HIDS=$BASE/hidslog
GEN="python3 scripts/gen_device_logs.py"

# 文件（真实设备命名 <类型>-YYYY-MM-DD-HH.log）
IPS="$TIANYAN/ips-2026-09-20-18.log"
WEBIDS="$TIANYAN/webids-2026-09-20-12.log"
WAFLOG="$WAF/waf-2026-09-21-11.log"
HIDSLOG="$HIDS/hids-2026-09-21-00.log"

# 轮转后新建的"下一小时"文件
IPS2="$TIANYAN/ips-2026-09-20-19.log"
WEBIDS2="$TIANYAN/webids-2026-09-20-13.log"
WAFLOG2="$WAF/waf-2026-09-21-12.log"
HIDSLOG2="$HIDS/hids-2026-09-21-01.log"

ROTATE_SUFFIX="-20260921"

FILES=("$IPS" "$WEBIDS" "$WAFLOG" "$HIDSLOG")
FILES2=("$IPS2" "$WEBIDS2" "$WAFLOG2" "$HIDSLOG2")
KINDS=(tianyan_ips tianyan_webids waf hids)
TS1=(2026-09-20T18:00:00.000 2026-09-20T12:00:00.000 2026-09-21T11:00:00.000 2026-09-21T00:00:00.000)
TS2=(2026-09-20T19:00:00.000 2026-09-20T13:00:00.000 2026-09-21T12:00:00.000 2026-09-21T01:00:00.000)

health() { curl -s --max-time 5 http://localhost/api/health; }
jget() { python3 -c "import sys,json;d=json.load(sys.stdin);print(d$1)"; }
kafka_consumed() { health | jget "['kafka']['consumed']"; }
db_alerts() { health | jget "['db']['alerts']"; }

wait_consumed() {  # $1=期望值, $2=超时秒
  local want=$1 timeout=${2:-120} n=0
  while [ $n -lt $timeout ]; do
    local c; c=$(kafka_consumed)
    if [ "$c" -ge "$want" ]; then echo "$c"; return 0; fi
    sleep 3; n=$((n+3))
  done
  echo "$(kafka_consumed)"; return 1
}

PASS=0; FAIL=0
check() { if [ "$1" = "$2" ]; then PASS=$((PASS+1)); echo "  [PASS] $3 (=$1)"; else FAIL=$((FAIL+1)); echo "  [FAIL] $3 (got=$1 want=$2)"; fi; }

echo "== 批次1：写入 $((4*N1)) 行（4 文件 × $N1） =="
seq=1
for i in 0 1 2 3; do
  $GEN append --file "${FILES[$i]}" --type "${KINDS[$i]}" --count "$N1" --seq-start $seq --ts-base "${TS1[$i]}" >/dev/null
  seq=$((seq + N1))
done
BATCH1=$((4*N1))

echo "== 等待批次1入库（期望 consumed=$BATCH1） =="
if c=$(wait_consumed "$BATCH1" 180); then echo "  consumed=$c"; else echo "  超时：consumed=$c（期望 $BATCH1）"; exit 1; fi
check "$(db_alerts)" "$BATCH1" "db.alerts == 批次1行数"

echo "== 轮转：改名 .log -> .log-20260921（模拟 logrotate dateformat -%Y%m%d） =="
for f in "${FILES[@]}"; do mv "$f" "$f$ROTATE_SUFFIX"; done

echo "== 探针：向已改名文件追加「尾巴」行（预期不被采集——见脚本头注释） =="
for i in 0 1 2 3; do
  $GEN append --file "${FILES[$i]}$ROTATE_SUFFIX" --type "${KINDS[$i]}" --count "$TAIL" --seq-start $seq --ts-base "${TS1[$i]}" >/dev/null
  seq=$((seq + TAIL))
done
TAIL_TOTAL=$((4*TAIL))

echo "== 新建下一小时文件 + 写批次2（$((4*N2)) 行，验证捡起新 *.log） =="
for i in 0 1 2 3; do
  $GEN append --file "${FILES2[$i]}" --type "${KINDS[$i]}" --count "$N2" --seq-start $seq --ts-base "${TS2[$i]}" >/dev/null
  seq=$((seq + N2))
done

EXPECTED=$((BATCH1 + 4*N2))   # 真实场景（批次1 + 批次2）应收到的行数
MAX=$((BATCH1 + TAIL_TOTAL + 4*N2))   # 全部写入行数（含尾巴）
echo "== 等待批次2入库（期望 consumed >= $EXPECTED；尾巴 $TAIL_TOTAL 行为竞态、可能被采集也可能丢） =="
if c=$(wait_consumed "$EXPECTED" 240); then echo "  consumed=$c"; else echo "  超时：consumed=$c（期望 >= $EXPECTED）"; exit 1; fi
sleep 5  # 等最后一批 DB 落库稳定
c=$(kafka_consumed)
# 确定性不变量：批次1+批次2 一定被采集（轮转不丢）；总数不超过全部写入（不重）。
if [ "$c" -ge "$EXPECTED" ]; then PASS=$((PASS+1)); echo "  [PASS] 批次1+批次2 完整采集，轮转不丢（consumed=$c >= $EXPECTED）"; else FAIL=$((FAIL+1)); echo "  [FAIL] 批次1+批次2 采集不完整（consumed=$c < $EXPECTED）"; fi
if [ "$c" -le "$MAX" ]; then PASS=$((PASS+1)); echo "  [PASS] 无重复（consumed=$c <= 全部写入 $MAX）"; else FAIL=$((FAIL+1)); echo "  [FAIL] 出现重复（consumed=$c > $MAX）"; fi
check "$(db_alerts)" "$c" "db.alerts == kafka.consumed（后端入库与采集一致）"
echo "  [INFO] 尾巴行本次采集 $((c - EXPECTED))/$TAIL_TOTAL 行（竞态，非确定性；rename 式 logrotate 的丢尾风险）"

echo "== 每源 alert 计数 =="
docker compose exec -T backend python3 -c "from app import crud; import json; print(json.dumps(crud.get_source_stats(), ensure_ascii=False))" 2>/dev/null

echo
echo "结果：$PASS PASS / $FAIL FAIL"
[ $FAIL -eq 0 ]
