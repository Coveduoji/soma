#!/usr/bin/env python3
"""生成 sec-terminal-linux 设备日志（WAF / 天眼 ips / 天眼 webids / HIDS）。

日志行格式：`TIMESTAMP [LEVEL] [device] [k=v&k=v&...]`（bracket_kv，与真实设备一致），
文件名按真实约定 `<类型>-YYYY-MM-DD-HH.log`。

用法（追加 N 行到指定文件，带唯一 event_id，供去重断言）：
    python3 gen_device_logs.py append --file <path> --type waf|tianyan_ips|tianyan_webids|hids \
        --count N --seq-start K [--ts-base "2026-09-20T22:22:21.000"]

event_id = evt-<type>-<seq>，seq 从 --seq-start 起递增。测试驱动通过递增 seq-start 保证全局唯一。
"""
from __future__ import annotations

import argparse
import datetime

# 每类源的可选告警内容（event + severity + attack_result + rule_id），模拟真实多变。
# severity: 2/4/6/8（low/medium/high/critical）；attacker_succ/action 决定攻击结果。
EVENTS = {
    "waf": [
        ("检测非浏览器客户端", "中风险", "blocked", "10506000"),
        ("SQL注入拦截", "高风险", "blocked", "10507001"),
        ("目录遍历探测", "低风险", "blocked", "10502011"),
        ("CC攻击防护", "中风险", "allow", "10508002"),
        ("恶意UA请求", "危急", "blocked", "10509003"),
    ],
    "tianyan_ips": [
        ("发现客户端挖矿行为(登录矿池)", 6, True, "410"),
        ("发现主机失陷外联", 8, True, "320"),
        ("扫描探测行为", 2, False, "101"),
        ("异常DNS解析", 4, True, "505"),
    ],
    "tianyan_webids": [
        ("检测到Web入侵", 6, True, "7200"),
        ("检测到Webshell上传", 8, True, "7301"),
        ("SQL注入攻击", 6, True, "7105"),
        ("扫描器指纹", 2, False, "7001"),
    ],
    "hids": [
        ("检测到异常进程执行", 6, True, "5001"),
        ("可疑进程提权", 8, True, "5002"),
        ("反弹shell连接", 8, True, "5003"),
        ("异常登录失败", 2, False, "5004"),
    ],
}

# 每类源一个样本 IP 池（src / dst 分离，便于看归案与实体抽取）
IP_POOL = {
    "waf": [("111.68.5.126", "101.227.60.120"), ("45.83.12.7", "101.227.60.120"),
            ("203.0.113.9", "10.10.0.200"), ("91.237.124.248", "10.10.0.201")],
    "tianyan_ips": [("91.237.124.248", "21.66.202.12"), ("185.199.108.153", "10.20.1.10"),
                    ("45.9.148.7", "10.20.2.20"), ("103.75.190.11", "10.20.3.30")],
    "tianyan_webids": [("91.237.124.248", "21.66.202.12"), ("185.199.108.153", "10.20.1.10"),
                       ("45.9.148.7", "10.20.2.20"), ("103.75.190.11", "10.20.3.30")],
    "hids": [("10.20.3.30", "10.20.4.40"), ("10.20.1.10", "10.20.2.20"),
             ("172.16.0.7", "172.16.0.20"), ("10.10.5.14", "10.10.5.20")],
}

# 天眼/HIDS 的 severity 数字 → 文本（仅用于展示/断言，不参与解析）
SEV_TEXT = {2: "low", 4: "medium", 6: "high", 8: "critical"}


def _ts(base: str, offset_sec: int) -> str:
    dt = datetime.datetime.strptime(base, "%Y-%m-%dT%H:%M:%S.%f")
    dt += datetime.timedelta(seconds=offset_sec)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def make_line(kind: str, seq: int, ts: str) -> str:
    """构造一行 bracket_kv 日志。kind ∈ {waf, tianyan_ips, tianyan_webids, hids}。"""
    eid = f"evt-{kind}-{seq:05d}"
    pool = IP_POOL[kind]
    src_ip, dst_ip = pool[seq % len(pool)]
    ev, sev, succ, rule = EVENTS[kind][seq % len(EVENTS[kind])]

    if kind == "waf":
        return (f"{ts} [WARN] [device] [app=sec-terminal-linux&site= 站点侦测 -{dst_ip}-1"
                f"&tag=通用防护&device_type=waf&threat_level={sev}&event={ev}"
                f"&src_port=63913&src_ip={src_ip}&action={succ}&dst_ip={dst_ip}"
                f"&rule_id={rule}&attack_sig=python-requests&event_id={eid}]")
    if kind.startswith("tianyan"):
        alert_type = "ips_alert" if kind == "tianyan_ips" else "webids_alert"
        succ_v = "true" if succ else "false"
        return (f"{ts} [WARN] [device] [asset_role=client&device_type=tianyan"
                f"&app=sec-terminal-linux&alert_type={alert_type}&event={ev}"
                f"&confidence=80&src_port=34072&severity={sev}&proto=6&src_ip={src_ip}"
                f"&dst_ip={dst_ip}&attacker_succ={succ_v}&alert_name={ev}"
                f"&rule_id={rule}&event_id={eid}]")
    # hids
    succ_v = "true" if succ else "false"
    return (f"{ts} [WARN] [device] [app=sec-terminal-linux&device_type=hids"
            f"&alert_type=hids_alert&event={ev}&confidence=75&src_port=44300"
            f"&severity={sev}&proto=6&src_ip={src_ip}&dst_ip={dst_ip}&dst_port=22"
            f"&attacker_succ={succ_v}&alert_name={ev}&rule_id={rule}&event_id={eid}]")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("append", help="追加 N 行到指定文件")
    p.add_argument("--file", required=True)
    p.add_argument("--type", required=True,
                   choices=["waf", "tianyan_ips", "tianyan_webids", "hids"])
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--seq-start", type=int, default=1)
    p.add_argument("--ts-base", default="2026-09-20T22:22:21.000")
    args = ap.parse_args()

    with open(args.file, "a", encoding="utf-8") as f:
        for i in range(args.count):
            seq = args.seq_start + i
            line = make_line(args.type, seq, _ts(args.ts_base, seq))
            f.write(line + "\n")
    print(f"appended {args.count} lines ({args.type}) -> {args.file} (seq {args.seq_start}..{args.seq_start + args.count - 1})")


if __name__ == "__main__":
    main()
