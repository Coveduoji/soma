"""密码哈希 / JWT / 权限键目录（迁自旧 auth.py）。"""
from __future__ import annotations

import os
import secrets
import time

import bcrypt
import jwt as pyjwt

from app.core.paths import SECRET_PATH

ALGORITHM = "HS256"
TOKEN_TTL = 24 * 3600  # 24h


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _jwt_secret() -> str:
    env = os.environ.get("NEUROIMMUNE_JWT_SECRET", "").strip()
    if env:
        return env
    if SECRET_PATH.exists():
        return SECRET_PATH.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    SECRET_PATH.write_text(key, encoding="utf-8")
    try:
        os.chmod(SECRET_PATH, 0o600)
    except OSError:
        pass
    return key


def create_access_token(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user["role"],
        "exp": int(time.time()) + TOKEN_TTL,
    }
    return pyjwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return pyjwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    except pyjwt.PyJWTError:
        return None


# 权限键目录（键 → 中文说明），前端据此画勾选面板
PERMISSIONS: dict[str, str] = {
    "triage": "分诊：标记误报/真阳性、放回、改案件、外发、免疫规则",
    "config": "配置：旋钮/模型/检测/接入/来源/Webhook/预设/频率/门槛",
    "maintenance": "维护：清库、夜间巩固",
    "users": "用户管理：建号/删号/改角色/改权限",
}
