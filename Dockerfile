FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单并安装
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# 复制 Agent 代码
COPY agent/ ./agent/
COPY mcp/ ./mcp/
COPY main.py .
COPY devices.yml .
COPY .env.example .env

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "from agent.state_store import StateStore; s=StateStore(); s.initialize(); print('OK')" || exit 1

CMD ["python", "main.py"]