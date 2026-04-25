# voice-pii

Stateless PII redaction service. See `../../infra/pii/README.md` for the AWS
deployment.

## Local dev

```
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm

# tests
pytest -q

# run locally
API_KEY=local-test-key uvicorn app.main:app --port 8080
```

## What it does

Detects PII spans in each turn of a transcript, replaces with typed,
document-scoped tokens (`<PERSON_1>`, `<POLICY_NUM_1>`...), and returns the
redacted transcript plus a `replacements` map in one HTTP response. Nothing
is stored.

## Custom recognizers

Domain identifiers (policy / claim / member / agent IDs) are recognised via
`app/recognizers.py`. Patterns are placeholders — replace with the real
formats once provided. Do not commit real customer data; synthesize examples.

## Logging discipline

- Logs include: request id, contact id, content SHA-256, entity counts by
  type, latency.
- Logs **never** include: request body, response body, or any token's
  original value.
- `tests/test_no_pii_in_logs.py` enforces this with synthetic sentinels.
  The test is mandatory in CI.
