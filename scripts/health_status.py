#!/usr/bin/env python3
"""把 /api/health 的 JSON 渲染成终端友好汇总（从 stdin 读）。"""
import json
import sys
import time

_STATUS_LABEL = {"ok": "正常", "degraded": "降级", "down": "异常"}


def ago(ts) -> str:
    if not ts:
        return "—"
    try:
        s = max(0, time.time() - float(ts))
    except (TypeError, ValueError):
        return "?"
    if s < 60:
        return f"{int(s)}s 前"
    if s < 3600:
        return f"{int(s // 60)}m 前"
    if s < 86400:
        return f"{int(s // 3600)}h{int(s % 3600 // 60)}m 前"
    return f"{int(s // 86400)}d 前"


def main() -> None:
    try:
        h = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001
        print(f"解析 health 返回失败：{e}")
        sys.exit(1)

    st = h.get("status", "?")
    label = _STATUS_LABEL.get(st, st)
    db = h.get("db") or {}
    sy = h.get("syslog") or {}
    ka = h.get("kafka") or {}
    up = h.get("uptime")
    if isinstance(up, (int, float)):
        up_s = f"{int(up // 3600)}h{int(up % 3600 // 60)}m{int(up % 60)}s"
    else:
        up_s = "?"

    kafka_state = "未启用" if not ka.get("enabled") else ("消费中" if ka.get("ok") else "失活")

    print("Soma 系统状态")
    print("=" * 44)
    print(f"整体   ：{label}（{st}） · 版本 {h.get('version', '?')} · 已运行 {up_s}")
    print(f"后端   ：{h.get('knob', '?')} 旋钮 · 模型 {h.get('mode', '?')}")
    print(f"数据库 ：{'正常' if db.get('ok') else '不可用'} · {db.get('alerts', 0)} 告警 / {db.get('cases', 0)} 案件 / {db.get('reports', 0)} 报告")
    print(f"syslog ：{'监听中' if sy.get('ok') else '未监听'} · workers {sy.get('workers', '?')} · 上次入库 {ago(sy.get('last_ingest'))}")
    print(f"Kafka  ：{kafka_state} · 消费 {ka.get('consumed', 0)} 条 · 失败 {ka.get('failed', 0)} · 上次消费 {ago(ka.get('last_consume'))}")


if __name__ == "__main__":
    main()
