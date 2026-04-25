"""Stateless PII redaction.

Token design:
- Document-scoped (counters reset per /redact call) so cross-document
  re-identification by frequency analysis is not possible.
- Type-typed (e.g. <PERSON_1>) so downstream LLM analysis can reason about
  entity kind.
- Same value within one document maps to the same token so coreference is
  preserved for the LLM (e.g. "John" mentioned twice gets <PERSON_1> both
  times).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

from .recognizers import CUSTOM_RECOGNIZERS


@dataclass
class Turn:
    speaker: str
    text: str
    ts: float | None = None


@dataclass
class RedactionResult:
    redacted_turns: list[Turn]
    replacements: dict[str, str]
    entities_by_type: dict[str, int] = field(default_factory=dict)


@lru_cache(maxsize=1)
def _analyzer() -> AnalyzerEngine:
    """Lazy-initialised, process-wide analyzer. Loaded once per task."""
    nlp_engine = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
    ).create_engine()

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(nlp_engine=nlp_engine, languages=["en"])
    for r in CUSTOM_RECOGNIZERS:
        registry.add_recognizer(r)

    return AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)


def _resolve_overlaps(results):
    """Drop lower-confidence detections that overlap a stronger one."""
    sorted_results = sorted(results, key=lambda r: (-r.score, r.start))
    kept = []
    for r in sorted_results:
        if any(not (r.end <= k.start or r.start >= k.end) for k in kept):
            continue
        kept.append(r)
    return kept


def redact(turns: list[Turn]) -> RedactionResult:
    analyzer = _analyzer()
    type_counters: dict[str, int] = {}
    value_to_token: dict[str, str] = {}
    replacements: dict[str, str] = {}
    entities_by_type: dict[str, int] = {}
    redacted_turns: list[Turn] = []

    for turn in turns:
        text = turn.text
        if not text:
            redacted_turns.append(Turn(speaker=turn.speaker, text=text, ts=turn.ts))
            continue

        results = analyzer.analyze(text=text, language="en")
        results = _resolve_overlaps(results)
        # Replace from end -> start to keep offsets valid as we mutate.
        results.sort(key=lambda r: r.start, reverse=True)

        new_text = text
        for r in results:
            original = text[r.start : r.end]
            token = value_to_token.get(original)
            if token is None:
                type_counters[r.entity_type] = type_counters.get(r.entity_type, 0) + 1
                token = f"<{r.entity_type}_{type_counters[r.entity_type]}>"
                value_to_token[original] = token
                replacements[token] = original
            entities_by_type[r.entity_type] = entities_by_type.get(r.entity_type, 0) + 1
            new_text = new_text[: r.start] + token + new_text[r.end :]

        redacted_turns.append(Turn(speaker=turn.speaker, text=new_text, ts=turn.ts))

    return RedactionResult(
        redacted_turns=redacted_turns,
        replacements=replacements,
        entities_by_type=entities_by_type,
    )


def warmup() -> None:
    """Force model load at startup so the first request isn't cold."""
    _analyzer().analyze(text="warmup", language="en")
