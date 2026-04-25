# Voice — Value Proposition & Scope

**Status:** v0.1 — Draft (founding artifact, pre-validation)
**Last updated:** 2026-04-25
**Owner:** _TBD_

> This is the founding document for the Voice initiative. Every downstream
> artifact (hypothesis register, data inventory, architecture, MVP plan) must
> be traceable to a statement in here. If something we are about to build is
> not justified by this document, either the work is out of scope or this
> document is wrong — both should be corrected explicitly.

---

## 1. Vision (one line)

Help business and engineering teams systematically reduce avoidable
live-agent contacts by identifying — with evidence — *why* customers end up
on the phone for self-service-eligible intents.

## 2. Problem

Customers contacting live agents for intents that should be self-serviceable
represent a recurring, expensive failure of the customer journey. Today we
cannot reliably answer:

- Why did this customer end up calling?
- Did they try a self-service path? If so, what failed?
- If they didn't try, what stopped them?
- Which team owns the fix — engineering, UX, IVR, marketing, trust, or
  accessibility?
- Is a given intervention actually reducing contact volume?

Without these answers, contact-deflection effort is reactive and uncoordinated.

## 3. Value proposition

The differentiated capability is a **chat surface that ties transcripts →
digital telemetry → code → owners**, with citations at every step. Existing
tools cover one or two of those layers individually; the value sits in the
join.

| Persona | What they get |
|---|---|
| CX / ops analyst | Chat surface to investigate contact-driver questions end-to-end with cited evidence |
| Product / UX | Per-intent friction profiles tied to specific journey steps and quotes |
| Engineering / SRE | Failure modes anchored to `file:line` in the relevant service repo |
| IVR / journey owner | Cohort views of "didn't try" and "tried & failed" routed to the right intervention class |
| Leadership | Defensible reporting on which interventions are reducing avoidable volume |

## 4. Scope — short term (MVP)

Target window: **~60 days following the validation phase decision gate**
(see §7).

**Domain and intents:** top 3 intents per domain (service, claims) — 6 total.
Specific intents _TBD_ at validation phase kickoff.

**Capabilities in MVP:**
- Transcript ingestion + PII redaction (Presidio + custom recognizers for
  domain identifiers).
- LLM tagging of each transcript with: intent, friction codes, no-attempt
  reasons, intervention class, evidence quotes, resolution.
- Tagged data in ClickHouse with vector + keyword search.
- Chat agent with four read-only tools:
  - `transcripts_sql` — structured queries over tagged data.
  - `transcripts_search` — semantic and keyword retrieval.
  - `logs_query` — on-demand pull via the existing log CLI.
  - `code_lookup` — repo grep / read by path.
- Internal web UI for analysts; citation-first answers with one-click drill
  to underlying contacts and source.
- Audit logging on every tool call.

**Deployment posture:** self-hosted on Kubernetes; no managed services in
the data path.

## 5. Scope — long term (6–12 months)

- Coverage expansion to all material self-service-eligible intents in both
  domains.
- Multi-trigger enrichment pipeline:
  - Manual analyst question (already in MVP).
  - Contact-volume anomaly on a self-service-eligible intent.
  - System telemetry anomaly upstream.
- Digital-session ↔ contact joins where data permits, lifting cohort
  classification from inferred to observed.
- Intervention tracking — when a fix ships, did the targeted contact
  category drop?
- Saved investigations and shared workspaces for analyst/engineering/product
  collaboration.
- Recommendation surface that routes findings to the owning team
  automatically.

## 6. Non-goals (explicit)

The following are **out of scope**, short and long term, unless this document
is amended:

- Customer-facing surfaces. This is an internal tool.
- Real-time / streaming. Daily batch is the design target.
- Auto-remediation, PR generation, or any write-back to production systems.
- **Pre / post IVR migration as an analytical factor.** _Decision:
  2026-04-25._
- Replacing existing observability (Grafana / Loki / etc.) or
  contact-center analytics tools.
- Universal AIOps root-cause analysis across all services.
- Managed-cloud dependencies in the data path.

## 7. Decision gates and prerequisites

Before MVP build commences:

1. **Hypothesis validation phase** completes with a scorecard of which causal
   claims are supported by 6 months of historical data. MVP scope is
   narrowed to validated hypotheses only.
2. **Join feasibility** assessed for digital-session ↔ contact, auth-events
   ↔ contact, IVR-session ↔ contact. Hypotheses depending on joins below
   acceptable coverage are flagged "instrumentation needed" and deferred.
3. **LLM tagging prompt locked** against a hand-coded validation set
   (≥ 300 transcripts, two annotators on a shared subset). Per-code
   precision/recall reported and accepted.

## 8. Success metrics

| Horizon | Metric | Target |
|---|---|---|
| Validation phase exit | Hypotheses validated / total tested | _TBD_ |
| MVP launch | Tagging F1 on codes used in cohorting | ≥ 0.7 |
| MVP launch | Tagged coverage of contacts in chosen intents | ≥ 80% with ≥ 1 code |
| MVP + 30d | Weekly active analyst users | _TBD_ |
| MVP + 60d | Investigations cited in shipped fixes | _TBD_ |
| MVP + 90d | Contact volume reduction attributable to surfaced interventions | _TBD_ |

Targets marked _TBD_ are set at stakeholder review of this document.

## 9. Open questions

- Persona ownership of "the analyst" — single role or multiple?
- Source of truth for self-service eligibility per intent — does this exist,
  or is it derived during validation?
- Customer / account ID strategy — is there a unified ID across digital and
  contact systems, or do we accept fragmentation in v1?
- GPU budget and model-serving capacity for self-hosted LLM.
- Stakeholder ownership and approval path for this document.

## 10. Follow-up artifacts (planned, not yet authored)

- `docs/hypotheses.md` — hypothesis register for the validation phase.
- `docs/data-inventory.md` — sources, joins, coverage matrix.
- `docs/tagging-taxonomy.md` — friction codes, no-attempt reasons,
  intervention classes, with definitions and examples.
- `docs/architecture.md` — MVP architecture and self-hosted component
  choices.
- `docs/mvp-plan.md` — week-by-week build plan, scoped to validated
  hypotheses.

---

### Assumptions made in this draft (to confirm or correct)

The following were inferred from prior discussion and need explicit
confirmation:

- This is an **internal** tool for analysts, product, eng, IVR, leadership —
  not a customer-facing surface.
- **Self-hosted on Kubernetes** is a hard constraint across the data path.
- **Top 3 intents per domain** (6 total) is the right MVP breadth.
- The existing **log CLI** is the access path for system logs; no new
  ingestion for logs is in MVP scope.
- Code repo access exists for the services that handle the chosen intents.
- The chat surface (not a static dashboard) is the primary delivery vehicle
  for value to business users.
