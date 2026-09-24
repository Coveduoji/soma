"""24 小时 syslog 接收服务——把实时 syslog 喂进Soma管道。

UDP + TCP 双监听（默认 5514，可配），每条立即判：耐受 → 固有免疫 → 杏仁核 → 黑板；
每 window 秒顶出一次 + 唤醒系统2 深想 + 写 history（夜里 consolidate.py 读它回写规则）。

跑法：
    python3 receiver.py                          # 默认 5514 / 正常档 / 60s 窗口
    python3 receiver.py --port 5514 --knob 正常 --window 30

测试：
    logger -n 127.0.0.1 -P 5514 -T "svc_backup 服务账号凌晨登录 payroll-db-03"          # UDP
    echo '<34>1 2026-08-14T03:14:07Z web-01 auth 123 - - Failed password' | nc 127.0.0.1 5514  # TCP
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import sys
import threading
import time

import amygdala
import blackboard
import config
import innate
import syslog
import system2
import tolerance
from llm import get_client, get_deep_client

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "data", "history.jsonl")


def _write_history(events: list, esc_ids: set) -> None:
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps({
                "time": e.time, "source": e.source, "asset": e.asset, "type": e.etype,
                "confidence": round(e.confidence, 2), "raw": e.raw, "reason": e.reason,
                "label": e.label, "innate": e.innate, "escalated": id(e) in esc_ids,
            }, ensure_ascii=False) + "\n")


def _udp_loop(bind: str, port: int, q: queue.Queue, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((bind, port))
    print(f"[监听] UDP {bind}:{port}")
    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(65535)
            src_ip = addr[0] if addr else ""
            for line in data.decode("utf-8", "replace").splitlines():
                if line.strip():
                    q.put((src_ip, line))
        except OSError as e:
            if not stop.is_set():
                print(f"[UDP] {e}")
            break


def _tcp_loop(bind: str, port: int, q: queue.Queue, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind, port))
    sock.listen(50)
    print(f"[监听] TCP {bind}:{port}")
    while not stop.is_set():
        try:
            conn, addr = sock.accept()
        except OSError:
            break
        threading.Thread(target=_tcp_conn, args=(conn, addr, q, stop), daemon=True).start()


def _tcp_conn(conn: socket.socket, addr, q: queue.Queue, stop: threading.Event) -> None:
    src_ip = addr[0] if addr else ""
    with conn:
        f = conn.makefile("r", encoding="utf-8", errors="replace")
        for line in f:
            if stop.is_set():
                break
            line = line.strip()
            if line:
                q.put((src_ip, line))


def _handle(line: str, src_ip: str, state: dict) -> None:
    sig = syslog.parse_line(line, src_ip)
    if sig is None:
        return
    lock = state["lock"]
    board = state["board"]
    knob = state["knob"]

    with lock:
        state["total"] += 1

    # 免疫耐受：已知好 → 静默
    if tolerance.is_tolerated(sig, state["tol"]):
        with lock:
            state["tol_suppressed"] += 1
        return

    # 固有免疫：已知坏 → 秒拦
    if innate.match(sig, state["innate_rules"]):
        with lock:
            state["innate_hits"] += 1
            board.post(blackboard.Event(
                time=sig["time"], source=sig["source"], asset=sig["asset"],
                etype=sig["type"], confidence=0.95, raw=sig["raw"],
                reason="固有免疫秒拦：已知攻击家族", label="", innate=True,
            ))
        print(f"[秒拦] {sig['asset']} {sig['type']}  {sig['raw'][:50]}")
        return

    # 杏仁核逐条判（慢调用，不放锁里）
    v = amygdala.judge_signal(sig, state["client"])
    if v.confidence < knob.suppress_below:
        with lock:
            state["suppressed"] += 1
        return
    with lock:
        state["surfaced"] += 1
        board.post(blackboard.Event(
            time=sig["time"], source=sig["source"], asset=sig["asset"],
            etype=sig["type"], confidence=v.confidence, raw=sig["raw"], reason=v.reason,
        ))
    print(f"[上板 {v.confidence:.2f}] {sig['asset']} {sig['type']}  {sig['raw'][:50]}")


def _flush(state: dict) -> None:
    lock = state["lock"]
    board = state["board"]
    knob = state["knob"]

    with lock:
        esc = board.escalate(knob.escalate_above)
        new_events = [e for e in board.events if id(e) not in state["written"]]
        for e in new_events:
            state["written"].add(id(e))
        board_events = list(board.events)  # 快照，供拼链算 siblings
        total = state["total"]
        tol_s = state["tol_suppressed"]
        inn = state["innate_hits"]
        sup = state["suppressed"]
        sur = state["surfaced"]

    esc_ids = {id(s.event) for s in esc}
    _write_history(new_events, esc_ids)

    # 系统2：预算内、非固有免疫、且没深想过的才唤醒
    candidates = [s for s in esc if not s.event.innate and id(s.event) not in state["deep_analyzed"]]
    wake = candidates[:knob.budget]
    for s in wake:
        siblings = [e for e in board_events
                    if e is not s.event and (e.asset == s.event.asset or e.etype == s.event.etype)]
        chain = [s.event] + siblings
        print(f"\n[系统2] {s.event.time} {s.event.asset} {s.event.etype}（显著性 {s.significance:.2f}）")
        report = system2.deep_analyze_chain(chain, state["deep_client"])
        print(f"  定性={report.get('verdict')}  置信度={report.get('confidence')}")
        print(f"  {report.get('digest')}")
        for ioc in report.get("iocs", []):
            print(f"  IOC: {ioc.get('value')}（{ioc.get('context')}）")
        with lock:
            state["deep_analyzed"].add(id(s.event))

    with lock:
        board.trim(state["max_events"])
        remaining = len(board.events)

    print(f"[周期] 总{total} 耐受{tol_s} 秒拦{inn} 抑制{sup} 上板{sur} "
          f"顶出{len(esc)} 深想{len(wake)} 板上{remaining}")


def main() -> None:
    # 常驻服务：重定向到文件时也按行刷新，避免日志被块缓冲吞掉
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=None, help="监听端口，默认 5514")
    ap.add_argument("--bind", default=None, help="绑定地址，默认 0.0.0.0")
    ap.add_argument("--knob", default=config.DEFAULT, choices=list(config.PRESETS))
    ap.add_argument("--window", type=float, default=None, help="顶出周期秒数，默认 60")
    ap.add_argument("--max-events", type=int, default=500, help="黑板最多保留事件数")
    args = ap.parse_args()

    port = args.port or int(os.environ.get("SOMA_SYSLOG_PORT", "5514"))
    bind = args.bind or os.environ.get("SOMA_SYSLOG_BIND", "0.0.0.0")
    window = args.window if args.window is not None else float(os.environ.get("SOMA_SYSLOG_WINDOW", "60"))

    knob = config.get_knob(args.knob)
    client = get_client()
    deep_client = get_deep_client()
    tol = tolerance.load_tolerance()
    innate_rules = innate.load_rules()

    state = {
        "lock": threading.Lock(),
        "board": blackboard.Blackboard(),
        "tol": tol, "innate_rules": innate_rules,
        "knob": knob, "client": client, "deep_client": deep_client,
        "total": 0, "tol_suppressed": 0, "innate_hits": 0, "suppressed": 0, "surfaced": 0,
        "written": set(), "deep_analyzed": set(), "max_events": args.max_events,
    }

    print(f"风险旋钮：{knob.name}（抑制线 {knob.suppress_below} / 顶出线 {knob.escalate_above} / 预算 {knob.budget}）")
    print(f"杏仁核后端：{type(client).__name__}   系统2后端：{type(deep_client).__name__}")
    print(f"免疫耐受白名单：{sorted(tol) or '（空）'}")
    print(f"固有免疫规则  : {sorted(innate_rules) or '（空）'}")
    print(f"顶出周期：{window}s，黑板上限 {args.max_events} 条")
    print("-" * 64)

    q: queue.Queue = queue.Queue()
    stop = threading.Event()
    threading.Thread(target=_udp_loop, args=(bind, port, q, stop), daemon=True).start()
    threading.Thread(target=_tcp_loop, args=(bind, port, q, stop), daemon=True).start()

    def worker() -> None:
        while not stop.is_set():
            try:
                src_ip, line = q.get(timeout=1)
            except queue.Empty:
                continue
            try:
                _handle(line, src_ip, state)
            except Exception as e:
                print(f"[worker] {e}")

    threading.Thread(target=worker, daemon=True).start()

    print("开始接收 syslog，Ctrl+C 退出。\n")
    try:
        while True:
            time.sleep(window)
            _flush(state)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        print("\n已停止。")


if __name__ == "__main__":
    main()
