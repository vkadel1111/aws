"""Custom Presidio recognizers for domain-specific identifiers.

Patterns here are placeholders. Replace with the real formats once provided;
do not commit real customer data even in tests — synthesize examples that
match the structure.
"""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer


def policy_number_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="POLICY_NUM",
        patterns=[
            Pattern(
                name="policy_alpha_dash_digits",
                regex=r"\b[A-Z]{2}-\d{4,8}\b",
                score=0.85,
            ),
        ],
        context=["policy", "policy number", "policy #"],
    )


def claim_number_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="CLAIM_NUM",
        patterns=[
            Pattern(
                name="claim_clm_prefix",
                regex=r"\bCLM-\d{6,10}\b",
                score=0.9,
            ),
        ],
        context=["claim", "claim number", "claim #"],
    )


def member_id_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="MEMBER_ID",
        patterns=[
            Pattern(
                name="member_m_prefix",
                regex=r"\bM\d{8,10}\b",
                score=0.85,
            ),
        ],
        context=["member", "member id", "member number"],
    )


def agent_id_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="AGENT_ID",
        patterns=[
            Pattern(
                name="agent_ag_prefix",
                regex=r"\bAG\d{4,6}\b",
                score=0.85,
            ),
        ],
        context=["agent", "agent id", "rep id"],
    )


CUSTOM_RECOGNIZERS = [
    policy_number_recognizer(),
    claim_number_recognizer(),
    member_id_recognizer(),
    agent_id_recognizer(),
]
