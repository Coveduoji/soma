"""启动引导：确保至少有一个 admin（fail-closed）。"""
from __future__ import annotations

import os

from app import crud
from app.core import security
from app.core.logging import get_logger

logger = get_logger("bootstrap")


def bootstrap_admin() -> None:
    """启动时确保至少有一个 admin。

    - 设了 SOMA_ADMIN_USER/PASSWORD → 用它建号（生产）。
    - 设了 SOMA_DEV=1 → 建默认 admin/admin（仅本地开发）。
    - 都没有 → 拒绝启动（fail-closed，避免默认弱口令上生产）。
    """
    if crud.count_admins() > 0:
        return
    env_user = os.environ.get("SOMA_ADMIN_USER", "").strip()
    env_pass = os.environ.get("SOMA_ADMIN_PASSWORD", "").strip()
    if env_user and env_pass:
        username, password = env_user, env_pass
        note = "来自环境变量"
    elif os.environ.get("SOMA_DEV", "").strip() == "1":
        username, password = "admin", "admin"
        note = "开发模式默认账号（生产勿用）"
    else:
        raise RuntimeError(
            "未配置管理员凭据：请设置 SOMA_ADMIN_USER / SOMA_ADMIN_PASSWORD，"
            "或本地开发时设 SOMA_DEV=1。"
        )
    if crud.get_user_by_username(username):
        return
    crud.create_user(username, security.hash_password(password), "admin")
    logger.info("初始管理员已创建：%s（%s）", username, note)
