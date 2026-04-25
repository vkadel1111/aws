"""Critical security test: ensure no original PII value appears in service
logs at any level. If this test fails the service must not be deployed.
"""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.main import app

# Synthetic PII fixtures. Each value must be unique enough that any leak is
# unambiguous in captured stdout.
SENTINELS = {
    "PERSON": "Janelle Quirkenstein",
    "PHONE_NUMBER": "+1-555-867-5309",
    "EMAIL_ADDRESS": "janelle.quirkenstein@example-fictional.test",
    "POLICY_NUM": "ZZ-99887766",
    "CLAIM_NUM": "CLM-9988776655",
    "MEMBER_ID": "M9988776655",
    "AGENT_ID": "AG999888",
}


def test_no_pii_in_logs(caplog):
    """Submit a transcript containing each PII type; assert none appear in logs."""
    client = TestClient(app)

    transcript = [
        {
            "speaker": "agent",
            "text": (
                f"Hi {SENTINELS['PERSON']}, I see your email is "
                f"{SENTINELS['EMAIL_ADDRESS']} and phone {SENTINELS['PHONE_NUMBER']}."
            ),
        },
        {
            "speaker": "customer",
            "text": (
                f"My policy is {SENTINELS['POLICY_NUM']}, claim {SENTINELS['CLAIM_NUM']}, "
                f"member {SENTINELS['MEMBER_ID']}. Agent id {SENTINELS['AGENT_ID']}."
            ),
        },
    ]

    with caplog.at_level(logging.DEBUG):
        resp = client.post(
            "/redact",
            json={"contact_id": "ct_test_001", "transcript": transcript},
            headers={"x-api-key": "test-key-not-a-real-secret"},
        )
    assert resp.status_code == 200, resp.text

    # Every captured log record at every level: original values must not appear.
    captured = "\n".join(rec.getMessage() for rec in caplog.records)
    for label, value in SENTINELS.items():
        assert value not in captured, f"{label} value leaked into logs: {value!r}"


def test_auth_required():
    client = TestClient(app)
    resp = client.post(
        "/redact",
        json={"contact_id": "ct_test_001", "transcript": []},
    )
    assert resp.status_code == 401


def test_health_open():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
