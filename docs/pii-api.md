# PII Redaction Service — Consumer Guide

This is the **consumer-facing** reference for callers of the Voice PII
redaction service. If you are deploying or tearing down the stack, see
`infra/pii/README.md` instead.

The service detects PII in conversation transcripts, replaces each detected
span with a typed token, and returns the redacted transcript plus a map of
tokens → original values **in the same HTTP response**. **Nothing is
persisted in AWS.** The map lives only in your process from that moment
forward; you are responsible for what happens to it next.

---

## TL;DR

```
POST http://<alb-dns>/redact
x-api-key: <shared-secret>
Content-Type: application/json

{
  "contact_id": "ct_abc123",
  "transcript": [
    {"speaker": "agent",    "text": "Hi Jane Doe, how can I help?"},
    {"speaker": "customer", "text": "My policy is AB-12345."}
  ]
}
```

Response (200):

```
{
  "contact_id": "ct_abc123",
  "redacted_transcript": [
    {"speaker": "agent",    "text": "Hi <PERSON_1>, how can I help?"},
    {"speaker": "customer", "text": "My policy is <POLICY_NUM_1>."}
  ],
  "replacements": {
    "<PERSON_1>":     "Jane Doe",
    "<POLICY_NUM_1>": "AB-12345"
  },
  "stats": {
    "entities_by_type": {"PERSON": 1, "POLICY_NUM": 1},
    "latency_ms": 87,
    "request_id": "9d2e..."
  }
}
```

## Authentication

- A single shared API key, supplied as the `x-api-key` request header.
- Inbound is locked to the configured caller CIDR by the ALB security
  group; if you receive a connection error, you are calling from outside
  the allowlist.
- The key is rotated by redeploy: the operator updates `API_KEY` and runs
  `make up && make redeploy`.

## Endpoints

### `GET /health`

No auth. Returns `{"status": "ok"}` once the analyzer has loaded. Use this
for caller-side readiness checks before issuing the first redact call —
cold start can take 10–20 seconds while the spaCy model loads.

### `POST /redact`

Auth required. Body schema:

| Field | Type | Required | Notes |
|---|---|---|---|
| `contact_id` | string (1–128) | yes | Opaque to the service; used for log traceability and echoed in the response. |
| `transcript` | array of turns | yes | Order is preserved. |
| `transcript[].speaker` | string | yes | Free-form; commonly `agent` / `customer`. |
| `transcript[].text` | string | yes | The turn's text. May contain PII. |
| `transcript[].ts` | number | no | Optional timestamp; echoed back verbatim. |

Response schema:

| Field | Notes |
|---|---|
| `contact_id` | Echo of the request. |
| `redacted_transcript` | Same shape and order as the input; `text` has tokens in place of PII. |
| `replacements` | `{ "<TOKEN>": "original_value" }`. **Treat as PII.** |
| `stats.entities_by_type` | Counts of replaced spans by type. |
| `stats.latency_ms` | Server-side processing latency. |
| `stats.request_id` | Server-generated; useful when reporting issues. |

## Token format

Tokens follow `<TYPE_N>` where `TYPE` is the entity class and `N` is the
1-based occurrence index **within this document**.

- **Type-typed.** `<PERSON_1>` is a person; `<POLICY_NUM_1>` is a policy
  number. Downstream consumers (e.g., LLM analysis) can reason about the
  type without seeing the value.
- **Document-scoped.** Counters reset on every `/redact` call. The same
  token in two different responses refers to two unrelated entities. This
  prevents cross-document re-identification by token frequency.
- **Same value, same token, within one document.** If "Jane Doe" appears
  three times in one transcript, all three sites map to `<PERSON_1>` and
  the dictionary has one entry. Coreference is preserved.

### Entity types

The service ships with these types:

- Built-in (Presidio): `PERSON`, `PHONE_NUMBER`, `EMAIL_ADDRESS`,
  `US_SSN`, `CREDIT_CARD`, `IBAN_CODE`, `IP_ADDRESS`, `DATE_TIME`,
  `LOCATION`, `URL`, `US_DRIVER_LICENSE`, `US_PASSPORT`, `MEDICAL_LICENSE`,
  and others — see Presidio docs for the full list.
- Custom (this service): `POLICY_NUM`, `CLAIM_NUM`, `MEMBER_ID`,
  `AGENT_ID`. *Patterns are placeholders in v0.1; final formats will land
  before the validation phase.*

If you require a new custom type, file a request to update
`services/pii/app/recognizers.py` and redeploy.

## Caller responsibilities

The replacement dictionary is PII once it leaves the service. Treat it as
such:

- **In-memory only** for the duration of one analysis. Do not write it to
  disk, logs, queues, or any persistent store unless you have an explicit
  decision and the appropriate controls.
- **Do not pass it into untrusted third parties** — including external
  LLM APIs. The redacted transcript is what goes to analysis; the
  dictionary is for re-joining results back to a customer record only when
  strictly necessary.
- **Discard at the end of the analysis.** Long-running callers should
  scope the dict's lifetime to a single unit of work and explicitly free
  it.
- **Do not log it.** This includes debug logging during development.

## Errors

| Status | Meaning |
|---|---|
| 200 | Success. |
| 401 | Missing or invalid `x-api-key`. |
| 422 | Request body failed schema validation. |
| 503 | Service is not yet ready (analyzer still loading) or auth is misconfigured server-side. |

Errors do not include any portion of the request body in their messages.

## Behaviour and limits

- **Statelessness.** No request data is retained beyond the response. There
  is no rehydrate endpoint and no way to recover a value the caller has
  already discarded. If you need the original later, re-call `/redact` on
  the original transcript.
- **Idempotency.** `/redact` is deterministic for a given input *within a
  single service version*. Token assignments depend on the order of
  detection; the same input on the same image will produce the same
  output, but a different image version may not.
- **Throughput.** Default sizing assumes ~30 conversations per task per
  minute. Capacity scales with `expected_batch_size` (set per pipeline
  run) and again on CPU when traffic arrives.
- **Cold start.** First request after a fresh deployment can take
  10–20 seconds while spaCy loads. Use `/health` as a readiness gate.
- **Maximum payload.** No hard limit is enforced; very large transcripts
  (tens of thousands of turns in one call) will increase latency
  proportionally. Prefer one call per conversation.

## Examples

### `curl`

```sh
curl -sS -X POST "http://$ALB_DNS/redact" \
  -H "x-api-key: $API_KEY" \
  -H "content-type: application/json" \
  -d '{
        "contact_id": "ct_demo",
        "transcript": [
          {"speaker": "agent",    "text": "Hi Jane, how can I help?"},
          {"speaker": "customer", "text": "Policy AB-12345 please."}
        ]
      }'
```

### Python

```python
import os, requests

ALB     = os.environ["PII_ENDPOINT"]      # e.g. http://internal-alb.us-east-1.elb.amazonaws.com
API_KEY = os.environ["PII_API_KEY"]

def redact(contact_id: str, transcript: list[dict]) -> dict:
    r = requests.post(
        f"{ALB}/redact",
        headers={"x-api-key": API_KEY, "content-type": "application/json"},
        json={"contact_id": contact_id, "transcript": transcript},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

# Typical workflow: redact, analyse on redacted, discard the dict.
result = redact("ct_demo", transcript)
redacted = result["redacted_transcript"]
replacements = result["replacements"]   # PII — keep in memory only
try:
    analysis = run_llm_analysis(redacted)            # only redacted text leaves this process
    final = rejoin_if_needed(analysis, replacements) # if at all
finally:
    replacements = None                              # explicit drop
```

## Versioning

The service surfaces no version field today. The image tag deployed via
`make build` is the de facto version. Breaking changes to the request /
response schema will land behind a new path (`/v2/redact`) rather than a
silent change.

## Reporting issues

When opening an issue, include:

- The `request_id` from the `stats` block (do **not** include any portion
  of the request body or replacements).
- Approximate timestamp.
- The image tag in use, if known.
