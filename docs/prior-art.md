# Prior Art

A survey of public references that overlap with the Voice initiative.
Captured so future contributors don't have to re-derive this and so we
can be explicit about which parts of our design are borrowed from
public patterns and which are net-new.

**Bottom line:** roughly 70 % of the system has good public references;
the differentiated parts (digital-session ↔ contact correlation,
code-aware log RCA tied to contact-volume signals) are not covered
end-to-end by any public project we found.

---

## Closest reference architectures

### AWS — Post Call Analytics (PCA)

[github.com/aws-samples/amazon-transcribe-post-call-analytics](https://github.com/aws-samples/amazon-transcribe-post-call-analytics)

The strongest AWS-native reference for the transcript half of our system.

**Architecture shape:**
S3 ingest → Step Functions DAG → Amazon Transcribe Call Analytics →
Amazon Comprehend (entities + PII) → Bedrock (summarisation, topic
extraction) → S3 curated → QuickSight for BI.

**What's worth borrowing:**
- Step-Functions orchestration topology.
- Redact-before-analyse ordering.
- "Bring-your-own-LLM" flexibility (Bedrock, SageMaker-hosted HF model,
  Anthropic API, custom Lambda).
- Schema for storing tagged conversation data.

**Why we don't fork it:**
- Heavily managed-service: Transcribe, Comprehend, Bedrock, QuickSight.
- Incompatible with our self-hosted-on-Kubernetes constraint.
- We use it as a pattern reference, not a base.

**Production validation:** Principal Financial Group case study —
[aws.amazon.com/blogs/machine-learning/principal-financial-group-...](https://aws.amazon.com/blogs/machine-learning/principal-financial-group-uses-aws-post-call-analytics-solution-to-extract-omnichannel-customer-insights/)

**AWS Solutions Library guidance** (architectural reference, no code):
[aws.amazon.com/solutions/guidance/post-call-analytics-on-aws](https://aws.amazon.com/solutions/guidance/post-call-analytics-on-aws/)

### AWS — Live Call Analytics (LCA), companion to PCA

[github.com/aws-samples/amazon-transcribe-live-call-analytics](https://github.com/aws-samples/amazon-transcribe-live-call-analytics)

Real-time variant of PCA. Less relevant for our batch-first design but
worth knowing about if the long-term roadmap shifts to real-time.

### Azure — Conversation Knowledge Mining (newest, closest to chat-first MVP)

[github.com/microsoft/Customer-Service-Conversational-Insights-with-Azure-OpenAI-Services](https://github.com/microsoft/Customer-Service-Conversational-Insights-with-Azure-OpenAI-Services)
*(repo name `Conversation-Knowledge-Mining-Solution-Accelerator`)*

The closest public match to the **chat-first** thesis in `docs/scope.md`.

**Architecture shape:**
Azure AI Foundry + Azure OpenAI + Azure Content Understanding +
Foundry IQ. Includes a web UI with an interactive chat experience over
conversational data.

**What's worth borrowing:**
- Chat-over-insights as the primary delivery vehicle (same UX thesis we
  adopted).
- Topic modelling and key-phrase extraction patterns that map onto our
  friction / no-attempt taxonomy.
- Web-UI shape for citation-first answers.

**Why we don't fork it:**
- Azure-managed-services throughout; no self-hosted variant.
- Tightly coupled to Foundry IQ which has no open analogue.

### Azure — AI-Powered Call Center Intelligence (older accelerator)

[github.com/MSUSAzureAccelerators/AI-Powered-Call-Center-Intelligence-Accelerator](https://github.com/MSUSAzureAccelerators/AI-Powered-Call-Center-Intelligence-Accelerator)

Earlier Microsoft accelerator. Speech-to-text + Text Analytics + Azure
OpenAI; modular for real-time and batch. Useful for its **architecture
diagrams** and for understanding how Microsoft frames the problem space
before the newer Foundry-based accelerator superseded it.

A community variant by an MS employee that's frequently updated:
[github.com/amulchapla/AI-Powered-Call-Center-Intelligence](https://github.com/amulchapla/AI-Powered-Call-Center-Intelligence).

---

## Adjacent useful tooling

### Langfuse — open-source LLM observability

[github.com/langfuse/langfuse](https://github.com/langfuse/langfuse)

Not contact-center-specific. If our tagging pipeline grows, Langfuse is
the right tool to track prompt versions, run-level evaluations, cost,
and quality regressions. Self-hostable on Kubernetes, which fits our
constraint. **Bookmarked for later phases**, not the MVP.

### LLM user-analytics platform list

[github.com/AndrMoura/llm-user-analytics-platforms](https://github.com/AndrMoura/llm-user-analytics-platforms)

Curated list of OSS and commercial platforms for extracting insights
from user/chatbot conversations. Useful for scanning options when we
expand coverage beyond voice transcripts to chat / email channels.

---

## Academic confirmation (paper, not code)

**LLM-Based Insight Extraction for Contact Center Analytics and
Cost-Efficient Deployment** — [arxiv.org/abs/2503.19090](https://arxiv.org/abs/2503.19090)

Describes the same pattern we're building: LLM for call-driver
generation, topic modelling, classification, trend detection, FAQ
generation. Validates the approach as research-grade; useful citation
when justifying the design.

---

## Where public references run out

We could not find a public end-to-end project covering the following
two pieces of our design:

### 1. Digital-session ↔ contact correlation with cohort decomposition

The "failure demand" / "journey friction" piece of our system —
identifying customers who tried digitally and failed, vs. those who
didn't try at all, vs. those who succeeded — does not exist as an open
reference.

Vendors with closed product offerings in this space:
- Verint Journey Analytics
- NICE Journey Orchestration
- Salesforce Data Cloud
- Genesys AI Experience Orchestrator

Enterprises that have publicly described internal builds: Capital One,
USAA, Progressive, T-Mobile (Team of Experts model), Liberty Mutual.
None has open-sourced their implementation.

### 2. Code-aware log RCA triggered by contact signals

Our "contact-volume spike triggers a scoped log pull and code lookup,
LLM synthesises a hypothesis grounded in `file:line`" pattern is also
absent from public references.

The closest commercial products are:
- Datadog Bits AI (autonomous on-call agent + Dev Agent for code-level fixes)
- New Relic AI (RCA, AIOps)
- Honeycomb Query Assistant + BubbleUp
- Grafana Sift
- Dynatrace Davis AI

Open-source AI-SRE toolkits exist but are early:
- [github.com/Tracer-Cloud/opensre](https://github.com/Tracer-Cloud/opensre)
- Causely (causal reasoning)
- Robusta, Komodor (K8s-focused)

None of these tie back to a contact-centre signal as the trigger.

---

## Implications for our design

- The transcript ingestion → PII redaction → LLM tagging → store →
  chat layers can lean heavily on PCA and the Azure Conversation
  Knowledge Mining accelerator for **architectural patterns**. We
  diverge by self-hosting on Kubernetes per `docs/scope.md`.
- The differentiated value of Voice — the **glue** between
  contact-centre signals, digital-session telemetry, and
  code-anchored system telemetry — is genuinely net-new. There is no
  reference to copy. This justifies the deliberate, hypothesis-led
  validation phase we've scoped before building infra.
- Langfuse is the right place to plug in for LLM-pipeline
  observability when the tagging pipeline matures.

## Survey hygiene

This document is a snapshot. Re-survey before each new phase begins —
the AI-SRE and contact-centre-analytics spaces are both moving quickly,
and a closer match may appear.
