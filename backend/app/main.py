"""FastAPI 应用入口——装配路由 / 中间件 / 生命周期 / 静态托管。"""
from __future__ import annotations

import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

import llm  # prototype 领域层（经 app/__init__.py 的 sys.path shim）

from app import crud
from app.core import bootstrap, logging as logging_setup
from app.core.logging import get_logger
from app.services import state, syslog_server, kafka_consumer
from app.api.routers import auth as auth_api, cases, dashboard, ingest as ingest_api

logger = get_logger("app")

# 进程启动时刻（/api/health 上报 uptime 用）
_START_TIME = time.time()


def _consolidate_loop() -> None:
    while True:
        interval = int(state.get_ingest_config().get("consolidate_interval", 21600))
        time.sleep(interval)
        try:
            from app.services import nightly
            r = nightly.consolidate()
            logger.info("夜间巩固 %s，摘要 %s", r.get("status"), r.get("memory") or "—")
        except Exception:
            logger.exception("夜间巩固失败")
        try:
            from app.services import retention
            r = retention.run_retention()
            if any(r.values()):
                logger.info("保留清理 %s", r)
        except Exception:
            logger.exception("保留清理失败")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时统一加载 .env（管理员账号 / JWT 密钥 / 模型 key 等）
    llm.load_dotenv()
    bootstrap.bootstrap_admin()
    try:
        syslog_server.start()
    except OSError as e:
        logger.warning("syslog 启动失败（端口可能被占用）: %s", e)
    try:
        kafka_consumer.start()  # 无 Kafka 环境变量时内部静默跳过
    except Exception:
        logger.exception("Kafka 消费者启动失败")
    threading.Thread(target=_consolidate_loop, daemon=True).start()
    yield


app = FastAPI(title="Soma防御", version="0.1.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in os.environ.get("SOMA_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_allowed_hosts = [h.strip() for h in os.environ.get("SOMA_ALLOWED_HOSTS", "*").split(",") if h.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)

app.include_router(cases.router)
app.include_router(dashboard.router)
app.include_router(auth_api.router)
app.include_router(ingest_api.router)

logging_setup.setup_logging()

_STATIC_DIR = Path(os.environ.get(
    "SOMA_STATIC_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"),
))

if _STATIC_DIR.is_dir():
    _assets = _STATIC_DIR / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/")
    def spa():
        return FileResponse(str(_STATIC_DIR / "index.html"))
else:

    @app.get("/")
    def root():
        return {"service": "soma", "status": "ok", "counts": crud.counts()}


@app.get("/api/health")
def health():
    """真实健康检查：db / syslog / kafka 三组件聚合出 overall 状态（ok / degraded / down）。"""
    db_ok = True
    try:
        counts = crud.counts()
    except Exception:
        counts = None
        db_ok = False
        logger.exception("health: 数据库计数失败")

    sys = syslog_server.status()
    kaf = kafka_consumer.status()
    syslog_ok = bool(sys.get("listening", False))
    # Kafka 未启用视为 n/a（不拖累整体）；启用则要求消费线程存活
    kafka_ok = (not kaf.get("enabled")) or bool(kaf.get("alive", False))

    if not db_ok:
        overall = "down"
    elif syslog_ok and kafka_ok:
        overall = "ok"
    else:
        overall = "degraded"

    return {
        "status": overall,
        "healthy": overall == "ok",
        "version": app.version,
        "uptime": round(time.time() - _START_TIME, 1),
        "time": time.time(),
        "db": {**(counts or {}), "ok": db_ok},
        "syslog": {**sys, "ok": syslog_ok},
        "kafka": {**kaf, "ok": kafka_ok},
        "knob": state.get_knob_name(),
        "mode": state.get_model_mode(),
    }
