"""Unit tests for the redactor.

All PII strings here are synthesized; do not commit real customer data.
"""

from app.redactor import Turn, redact


def test_redact_replaces_person_name():
    turns = [
        Turn(speaker="agent", text="Hi Jane Doe, how can I help you today?"),
    ]
    result = redact(turns)
    assert "Jane Doe" not in result.redacted_turns[0].text
    assert any(tok.startswith("<PERSON_") for tok in result.replacements)


def test_same_value_reuses_token_within_document():
    turns = [
        Turn(speaker="agent", text="Hi Jane, this is for Jane's policy."),
    ]
    result = redact(turns)
    person_tokens = [t for t in result.replacements if t.startswith("<PERSON_")]
    # Same name twice should map to same token.
    assert len(person_tokens) == 1


def test_custom_policy_number_recognized():
    turns = [
        Turn(speaker="customer", text="My policy number is AB-12345."),
    ]
    result = redact(turns)
    assert "AB-12345" not in result.redacted_turns[0].text
    assert any(t.startswith("<POLICY_NUM_") for t in result.replacements)
    assert "POLICY_NUM" in result.entities_by_type


def test_replacements_dict_lets_caller_reconstruct():
    turns = [
        Turn(speaker="agent", text="Hi Jane Doe, claim CLM-1234567 is open."),
    ]
    result = redact(turns)
    rebuilt = result.redacted_turns[0].text
    for token, original in result.replacements.items():
        rebuilt = rebuilt.replace(token, original)
    assert rebuilt == turns[0].text


def test_empty_text_passes_through():
    turns = [Turn(speaker="agent", text="")]
    result = redact(turns)
    assert result.redacted_turns[0].text == ""
    assert result.replacements == {}


def test_preserves_speaker_and_ts():
    turns = [
        Turn(speaker="customer", text="It's me, John.", ts=1.5),
        Turn(speaker="agent", text="Got it.", ts=2.0),
    ]
    result = redact(turns)
    assert result.redacted_turns[0].speaker == "customer"
    assert result.redacted_turns[0].ts == 1.5
    assert result.redacted_turns[1].speaker == "agent"
    assert result.redacted_turns[1].ts == 2.0


def test_document_scoped_counters_reset_across_calls():
    a = redact([Turn(speaker="agent", text="Jane Doe is here.")])
    b = redact([Turn(speaker="agent", text="Bob Smith is here.")])
    # Both documents start their counters at 1 — re-identification across
    # documents by token frequency is therefore not possible.
    assert any(t == "<PERSON_1>" for t in a.replacements)
    assert any(t == "<PERSON_1>" for t in b.replacements)
