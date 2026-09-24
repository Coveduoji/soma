"""数据目录统一解析——所有持久化文件（DB / JSON 状态 / 密钥 / 记忆 / 反馈）挂到同一数据目录。

用环境变量 `SOMA_DATA_DIR` 可整体迁走（容器内挂卷到 /data，本地默认回落 backend/）。
该变量须在进程启动前就绪（Docker 环境变量 / shell export），不读 .env。
"""
from __future__ import annotations

import os
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def data_dir() -> Path:
    env = os.environ.get("SOMA_DATA_DIR", "").strip()
    d = Path(env).expanduser() if env else _BACKEND_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


DB_PATH = data_dir() / "soma.db"
SECRET_PATH = data_dir() / "secret.key"

KNOB_PATH = data_dir() / "knob.json"
PRESETS_PATH = data_dir() / "knob_presets.json"
FREQ_PATH = data_dir() / "freq.json"
MODE_PATH = data_dir() / "mode.json"
GATING_PATH = data_dir() / "gating.json"
MODEL_PATH = data_dir() / "model.json"
DETECTION_PATH = data_dir() / "detection.json"
INGEST_PATH = data_dir() / "ingest.json"
WEBHOOKS_PATH = data_dir() / "webhooks.json"

FEEDBACK_PATH = data_dir() / "data" / "feedback.jsonl"
MEMORY_PATH = data_dir() / "data" / "memory.jsonl"
ARCHIVE_PATH = data_dir() / "archive"
