# 后端：FastAPI 薄壳 + prototype 算法内核（运行时 import ../prototype）
# 构建上下文是仓库根目录（docker-compose 里 context: .）
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 中文字体（报告图表 matplotlib 用，否则中文标签乱码）
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖，利用 Docker 缓存层
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码：backend 与 prototype 必须同级（backend 运行时会 import ../prototype）
COPY backend/ /app/backend/
COPY prototype/ /app/prototype/

# 非 root 运行
RUN useradd --create-home --uid 10001 appuser

# 数据目录（SQLite / JSON 状态 / secret.key 等），用卷挂载持久化。
# 必须在 USER appuser 之前建好并 chown：否则命名卷挂载后 /data 属 root，
# 非 root 的 appuser 写不进，SQLite 无法创建（unable to open database file）。
ENV SOMA_DATA_DIR=/data
RUN mkdir -p /data && chown appuser:appuser /data

USER appuser

WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers"]
