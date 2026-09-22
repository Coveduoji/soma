"""案件 API：分诊队列 / 详情 / 图 / 处置 / 标记误报。"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core import deps
from app import crud as db
import innate
import tolerance
from app.services import pipeline
from app.services import webhook
from signature import signature
from app.schemas import CasePatch

router = APIRouter(prefix="/api/cases", tags=["cases"], dependencies=[Depends(deps.require_user)])


@router.get("")
def list_cases(status: str | None = None, verdict: str | None = None, severity: str | None = None,
               pending: bool = False, q: str | None = None, risk: str | None = None,
               limit: int = 50, offset: int = 0):
    return {
        "items": db.list_cases(status, verdict, severity, pending, q, risk, limit, offset),
        "total": db.count_cases(status, verdict, severity, pending, q, risk),
    }


@router.post("/bulk-false-positive", dependencies=[Depends(deps.require_perm("triage"))])
def bulk_false_positive(body: dict):
    """批量标记误报：多个案件一次性回写免疫耐受（与单条误报一致：留痕 + 记反馈 + 外发）。"""
    case_ids = (body or {}).get("case_ids", [])
    reason = (body or {}).get("reason", "")
    learned_all = []
    for cid in case_ids:
        case = db.get_case(cid)
        if not case:
            continue
        if case.get("verdict"):
            continue  # 已标记（有结论）的案件跳过，避免重复标记/重复记反馈
        alerts = db.get_case_alerts(cid)
        keys = [signature(a["source"], a["type"], a["raw"], a["asset"]) for a in alerts]
        learned = tolerance.learn_signatures(keys)
        learned_all.extend(learned)
        # 冲突检测：误报签名若已在黑名单，说明同一形状曾被判过真阳，记审计留给人工复核。
        conflicts = [k for k in keys if k in innate.load_rules()]
        if conflicts:
            db.insert_audit("tolerance_conflict", f"case {cid}",
                            json.dumps({"conflicts": conflicts}, ensure_ascii=False))
        db.patch_case(cid, {"verdict": "False Positive", "status": "Closed", "disposition_note": reason})
        db.insert_audit("bulk_false_positive", f"case {cid}",
                        json.dumps({"learned": learned, "reason": reason}, ensure_ascii=False))
        # 处置理由作为学习素材（entities 保留资产给 RAG，keys 是签名给白名单）
        db.append_feedback({
            "type": "false_positive",
            "case_uid": case["correlation_uid"],
            "entities": [[a["asset"], a["type"]] for a in alerts],
            "reason": reason,
            "time": datetime.now().isoformat(),
        })
        webhook.notify("disposition", cid)
    return {"case_ids": case_ids, "learned": learned_all}


@router.get("/{case_id}")
def get_case(case_id: int):
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    alerts = db.get_case_alerts(case_id)
    for a in alerts:
        a["artifacts"] = db.get_alert_artifacts(a["id"])
    return {"case": case, "alerts": alerts, "report": db.get_case_report(case_id)}


@router.get("/{case_id}/hippocampus")
def get_graph(case_id: int):
    if not db.get_case(case_id):
        raise HTTPException(404, "case not found")
    alerts = db.get_case_alerts(case_id)
    entities: dict[tuple, int] = {}
    edges: set[tuple[int, int]] = set()
    for a in alerts:
        idxs = []
        for art in db.get_alert_artifacts(a["id"]):
            k = (art["type"], art["value"])
            if k not in entities:
                entities[k] = len(entities)
            idxs.append(entities[k])
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                edges.add(tuple(sorted((idxs[i], idxs[j]))))
    nodes = [{"id": i, "type": k[0], "value": k[1]}
             for k, i in sorted(entities.items(), key=lambda kv: kv[1])]
    return {"nodes": nodes, "edges": [list(e) for e in edges]}


@router.patch("/{case_id}", dependencies=[Depends(deps.require_perm("triage"))])
def patch_case(case_id: int, body: CasePatch):
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    changes = {}
    for k, v in body.model_dump().items():
        if v is not None:
            changes["disposition_note" if k == "note" else k] = v
    # 状态机：非法转换拒绝
    if "status" in changes and not db.is_valid_transition(case["status"], changes["status"]):
        raise HTTPException(400, f"非法状态转换：{case['status']} → {changes['status']}")
    if changes:
        db.patch_case(case_id, changes)
        db.insert_audit("patch", f"case {case_id}", json.dumps(changes, ensure_ascii=False))
    return db.get_case(case_id)


@router.post("/{case_id}/false-positive", dependencies=[Depends(deps.require_perm("triage"))])
def false_positive(case_id: int, body: dict | None = None):
    if not db.get_case(case_id):
        raise HTTPException(404, "case not found")
    reason = (body or {}).get("reason", "")
    alerts = db.get_case_alerts(case_id)
    keys = [signature(a["source"], a["type"], a["raw"], a["asset"]) for a in alerts]
    learned = tolerance.learn_signatures(keys)
    # 冲突检测：误报签名若已在黑名单，说明同一形状曾被判过真阳，记审计留给人工复核。
    conflicts = [k for k in keys if k in innate.load_rules()]
    if conflicts:
        db.insert_audit("tolerance_conflict", f"case {case_id}",
                        json.dumps({"conflicts": conflicts, "reason": reason}, ensure_ascii=False))
    db.patch_case(case_id, {"verdict": "False Positive", "status": "Closed", "disposition_note": reason})
    db.insert_audit("false_positive", f"case {case_id}",
                    json.dumps({"learned": learned, "reason": reason}, ensure_ascii=False))
    # 处置理由作为学习素材（entities 保留资产给 RAG，keys 是签名给白名单）
    db.append_feedback({
        "type": "false_positive",
        "case_uid": db.get_case(case_id)["correlation_uid"],
        "entities": [[a["asset"], a["type"]] for a in alerts],
        "reason": reason,
        "time": datetime.now().isoformat(),
    })
    webhook.notify("disposition", case_id)
    return {"case_id": case_id, "learned": learned}


@router.post("/{case_id}/true-positive", dependencies=[Depends(deps.require_perm("triage"))])
def true_positive(case_id: int, body: dict | None = None):
    """标记真阳性：把案件 (asset, type) 写进固有免疫规则，下次同家族边缘秒拦。"""
    if not db.get_case(case_id):
        raise HTTPException(404, "case not found")
    reason = (body or {}).get("reason", "")
    alerts = db.get_case_alerts(case_id)
    keys = [signature(a["source"], a["type"], a["raw"], a["asset"]) for a in alerts]
    learned = innate.add_signatures(keys)
    # 冲突检测：真阳签名若已在白名单，说明同一形状曾被判过误报，记审计留给人工复核。
    conflicts = [k for k in keys if k in tolerance.load_tolerance()]
    if conflicts:
        db.insert_audit("innate_conflict", f"case {case_id}",
                        json.dumps({"conflicts": conflicts, "reason": reason}, ensure_ascii=False))
    db.patch_case(case_id, {"verdict": "True Positive", "status": "Closed", "disposition_note": reason})
    db.insert_audit("true_positive", f"case {case_id}",
                    json.dumps({"learned": learned, "reason": reason}, ensure_ascii=False))
    db.append_feedback({
        "type": "true_positive",
        "case_uid": db.get_case(case_id)["correlation_uid"],
        "entities": [[a["asset"], a["type"]] for a in alerts],
        "reason": reason,
        "time": datetime.now().isoformat(),
    })
    webhook.notify("disposition", case_id)
    return {"case_id": case_id, "learned": learned}


@router.post("/{case_id}/push", dependencies=[Depends(deps.require_perm("triage"))])
def push_case(case_id: int):
    """手动外发一个案件到所有 enabled webhook。"""
    if not db.get_case(case_id):
        raise HTTPException(404, "case not found")
    return {"case_id": case_id, "results": webhook.push_case(case_id)}


@router.post("/{case_id}/analyze", dependencies=[Depends(deps.require_perm("triage"))])
def analyze_case(case_id: int):
    """主动研判案件：同步跑系统2 深想，覆盖/刷新调查报告。"""
    if not db.get_case(case_id):
        raise HTTPException(404, "case not found")
    return pipeline.analyze_case(case_id)


def _case_markdown(case: dict, alerts: list[dict], report: dict | None) -> str:
    lines = [f"# 案件报告 {case['correlation_uid']}", ""]
    lines.append(f"- 强度：{case['strength']}")
    lines.append(f"- 状态：{case.get('status') or 'New'}")
    lines.append(f"- 结论：{case.get('verdict') or '—'}")
    if case.get("disposition_note"):
        lines.append(f"- 处置理由：{case['disposition_note']}")
    lines += ["", "## 实体", "", "、".join(e["value"] for e in case.get("entities", []))]
    lines += ["", "## 告警时间线", ""]
    for a in alerts:
        lines.append(f"- [{a['time']}] {a['source']}/{a['type']} (conf {a['confidence']}) — {a['raw']}")
    if report:
        lines += ["", "## AI 调查报告", ""]
        lines.append(f"- 定性：{report.get('verdict', '')} / 置信度 {report.get('confidence', '')}")
        lines.append(f"- 摘要：{report.get('digest', '')}")
        if report.get("iocs"):
            lines.append(f"- IOC：{'、'.join(i['value'] for i in report['iocs'])}")
        if report.get("unknowns"):
            lines.append(f"- 待查：{'；'.join(report['unknowns'])}")
        if report.get("remediations"):
            lines.append(f"- 处置建议：{'；'.join(report['remediations'])}")
    lines.append("")
    return "\n".join(lines)


@router.get("/{case_id}/export")
def export_case(case_id: int):
    """导出单案件结案报告（Markdown）。"""
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    md = _case_markdown(case, db.get_case_alerts(case_id), db.get_case_report(case_id))
    return Response(md, media_type="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename=case_{case_id}.md"})
