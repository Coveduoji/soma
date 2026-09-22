"""机器入库 API：JSON 信号流，共享 token 保护（与用户登录并存）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import deps
from app.services import pipeline
from app.schemas import IngestRequest

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest", dependencies=[Depends(deps.require_token)])
def ingest(body: IngestRequest):
    """增量入库：不重置，逐条归入/合并案件（24h 流式）。走全局旋钮。"""
    results = [pipeline.process_signal(sig) for sig in body.signals]
    return {"ingested": len(results), "results": results}
