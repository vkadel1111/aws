"""FastAPI entrypoint for the PII redaction service.

Logging discipline:
- Never log request body, response body, or any token's original value.
- Log only metadata: request id, contact id, entity counts by type, latency.
- A CI test enforces this by submitting fixtures with known synthetic PII
  patterns and asserting no occurrence in captured stdout.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from .redactor import Turn, redact, warmup

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("pii")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("warming up analyzer")
    warmup()
    log.info("ready")
    yield


app = FastAPI(title="voice-pii", lifespan=lifespan)


class TurnIn(BaseModel):
    speaker: str
    text: str
    ts: float | None = None


class RedactRequest(BaseModel):
    contact_id: str = Field(min_length=1, max_length=128)
    transcript: list[TurnIn]


class TurnOut(BaseModel):
    speaker: str
    text: str
    ts: float | None = None


class RedactResponse(BaseModel):
    contact_id: str
    redacted_transcript: list[TurnOut]
    replacements: dict[str, str]
    stats: dict


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        # Fail closed if misconfigured; never auth-skip when key is missing.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "auth not configured")
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid api key")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/redact", response_model=RedactResponse, dependencies=[Depends(require_api_key)])
def post_redact(req: RedactRequest) -> RedactResponse:
    request_id = str(uuid.uuid4())
    started = time.perf_counter()

    # Content hash gives auditable traceability without exposing PII.
    raw = "\n".join(f"{t.speaker}:{t.text}" for t in req.transcript)
    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    turns = [Turn(speaker=t.speaker, text=t.text, ts=t.ts) for t in req.transcript]
    result = redact(turns)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    log.info(
        "redact done request_id=%s contact_id=%s content_sha256=%s "
        "turns=%d entities=%s latency_ms=%s",
        request_id,
        req.contact_id,
        content_hash,
        len(turns),
        result.entities_by_type,
        latency_ms,
    )

    return RedactResponse(
        contact_id=req.contact_id,
        redacted_transcript=[
            TurnOut(speaker=t.speaker, text=t.text, ts=t.ts) for t in result.redacted_turns
        ],
        replacements=result.replacements,
        stats={
            "entities_by_type": result.entities_by_type,
            "latency_ms": latency_ms,
            "request_id": request_id,
        },
    )
