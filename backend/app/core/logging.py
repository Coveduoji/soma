"""结构化 JSON 日志：统一输出 stdout，由 Docker / 日志收集器采集。

不写文件、不做轮转——轮转交给 Docker 的 json-file 驱动或外部 logrotate。
所有业务日志走 `soma.*` 命名空间，与 uvicorn 自带的访问日志互不干扰。
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging() -> None:
    logger = logging.getLogger("soma")
    if logger.handlers:
        return
    level = os.environ.get("SOMA_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level, logging.INFO))
    logger.propagate = False  # 不往 root 冒泡，避免与 uvicorn 日志混


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"soma.{name}")
