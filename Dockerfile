FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
COPY src ./src
COPY static ./static
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/docker/start-api.sh ./scripts/docker/start-api.sh

RUN pip install --no-cache-dir --upgrade pip -i "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" \
    && pip install --no-cache-dir -r requirements.txt -i "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" \
    && pip install --no-cache-dir -e . -i "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" \
    && chmod +x ./scripts/docker/start-api.sh

EXPOSE 8000

CMD ["./scripts/docker/start-api.sh"]
