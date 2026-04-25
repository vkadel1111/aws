# syntax=docker/dockerfile:1.7

# ---- Builder: install deps, pre-download spaCy model ----
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml ./
COPY app ./app

# Install runtime deps + project into the user site-packages so the runtime
# stage can copy a single tree.
RUN pip install --user .

# Pre-download the spaCy model so the runtime container needs no internet.
RUN python -m spacy download en_core_web_sm

# ---- Runtime ----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PATH=/home/app/.local/bin:/usr/local/bin:/usr/bin:/bin

RUN groupadd --system app && useradd --system --gid app -m -d /home/app app

WORKDIR /app

COPY --from=builder --chown=app:app /root/.local /home/app/.local
COPY --chown=app:app app /app/app

USER app

EXPOSE 8080

# Disable core dumps for the process; keep it in-memory only.
CMD ["sh", "-c", "ulimit -c 0 && exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --log-level info"]
