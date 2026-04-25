# PII Redaction Stack

Stateless tokenisation service for the Voice project. Detects PII in
transcripts, replaces each span with a typed, document-scoped token, and
returns the redacted transcript plus a `replacements` dictionary in the same
HTTP response. **Nothing is persisted in AWS.**

## Architecture

```
Caller ──HTTP/VPC──▶ Internal ALB ──▶ ECS Fargate (Presidio + custom recognizers)
                                            │
                                            └─▶  { redacted_transcript, replacements }
```

- New VPC, private subnets only.
- VPC endpoints for ECR (api/dkr), S3 gateway, CloudWatch Logs — no NAT, no
  internet egress.
- Internal ALB; security group restricts inbound to either a configured CIDR
  or, by default, the VPC CIDR.
- Task IAM role explicitly **denies** `s3:*`, `dynamodb:*`, `kms:*`,
  `secretsmanager:*` so the workload cannot persist anything.
- Read-only root filesystem; core dumps disabled.
- CloudWatch log group with short retention (7 days default) — logs metadata
  only (entity counts, content SHA-256, request id, latency); never values.

## Capacity

`expected_batch_size` (default 50) drives `min_capacity` via:

```
min_capacity = ceil(expected_batch_size / (conversations_per_task_per_minute * target_minutes_to_complete))
max_capacity = min(max_capacity_cap, max(min*2, min+1))
```

The pipeline sets `EXPECTED_BATCH_SIZE` before each run. CPU target tracking
auto-scales between min and max while a batch is in flight.

## Required environment for the pipeline

| Variable | Purpose |
|---|---|
| `AWS_REGION` | Region to deploy into |
| `TF_BACKEND_BUCKET` | S3 bucket holding `terraform.tfstate` |
| `TF_BACKEND_KEY` | State object key, e.g. `voice/pii/dev.tfstate` |
| `TF_BACKEND_DDB_TABLE` | (Optional, recommended) DynamoDB table for state lock |
| `API_KEY` | Shared secret for the single internal caller |
| `EXPECTED_BATCH_SIZE` | Conversations expected next run |
| `IMAGE_TAG` | ECR image tag to deploy |

The Terraform state bucket and lock table are **out of scope** for this
stack — they must outlive any teardown. Create them once with whatever
mechanism the org uses.

## Lifecycle (pipeline)

```
make init                # one time per workspace
make plan                # preview
make up                  # apply (creates VPC, ECR, ECS, ALB, autoscaling)
make build               # build + push container image to the new ECR repo
make redeploy            # force the service to pull the new image
make down                # destroy everything
```

`make up` is safe to run repeatedly; capacity changes (e.g. a new
`EXPECTED_BATCH_SIZE` for the next batch) re-apply cleanly.

## Calling the service

```
POST http://<alb-dns>/redact
x-api-key: <API_KEY>

{
  "contact_id": "ct_abc123",
  "transcript": [
    {"speaker": "agent", "text": "Hi Jane, how can I help?"},
    {"speaker": "customer", "text": "My policy is AB-12345."}
  ]
}
```

Response:

```
{
  "contact_id": "ct_abc123",
  "redacted_transcript": [
    {"speaker": "agent", "text": "Hi <PERSON_1>, how can I help?"},
    {"speaker": "customer", "text": "My policy is <POLICY_NUM_1>."}
  ],
  "replacements": {
    "<PERSON_1>": "Jane",
    "<POLICY_NUM_1>": "AB-12345"
  },
  "stats": {
    "entities_by_type": {"PERSON": 1, "POLICY_NUM": 1},
    "latency_ms": 87,
    "request_id": "..."
  }
}
```

The `replacements` dictionary is the caller's responsibility from this point
forward. Hold it in memory; never persist or log it.

## Teardown notes

- `aws_ecr_repository.service` has `force_delete = true`; `terraform destroy`
  removes the repo and any pushed images.
- CloudWatch log group is destroyed with the stack; retention is short.
- VPC endpoints, ALB, ECS service, autoscaling target are all managed
  resources and are torn down automatically.
- No KMS keys created (no at-rest secrets to protect — service is stateless).

## Operational guardrails

A CI test (`tests/test_no_pii_in_logs.py`) submits a fixture containing
synthetic but unique PII patterns and asserts that none appear in captured
log output. **This test must pass before any image is promoted.**

## Cost

Estimates in **USD, us-east-1, on-demand** pricing. Numbers reflect the
default configuration: 1 Fargate task at 1 vCPU / 2 GB, internal ALB, VPC
endpoints in 2 AZs, no NAT.

### At minimum capacity (idle / batch warmup)

| Component | Calculation | $/hr |
|---|---|---|
| Fargate task (1 × 1 vCPU + 2 GB) | (1 × $0.04048) + (2 × $0.004445) | $0.0494 |
| Internal ALB (fixed + minimal LCU at 50 req/hr) | $0.0225 + ~$0.002 | $0.025 |
| VPC interface endpoints (3 endpoints × 2 AZs) | 6 × $0.01 | $0.060 |
| CloudWatch Logs ingest (metadata only) | ~0.5 MB/hr × $0.50/GB | ~$0.0003 |
| ECR storage (~500 MB image, amortised) | $0.10/GB/mo | ~$0.0001 |
| **Total** | | **≈ $0.135 / hr** |

### At a 4-task scaled peak

| Component | $/hr |
|---|---|
| Fargate (4 tasks) | $0.197 |
| ALB | $0.025 |
| VPC endpoints | $0.060 |
| Other | ~$0.001 |
| **Total** | **≈ $0.28 / hr** |

### Per-batch and monthly views

- **Per batch (50 conversations, ~5 min wall-clock at min capacity):**
  ~$0.011 if the stack is brought up only for the run.
- **Always-on (24×7) at min capacity:** ~$0.135 × 730 ≈ **$98/mo**. Fixed
  costs dominate: ALB $16/mo and VPC endpoints $43/mo.

### Cost-shaping notes

- VPC endpoints are the biggest fixed cost in this design. They are kept
  because they let the service run with zero internet egress, which is a
  security property worth paying for.
  - For an **always-on** deployment you may prefer one NAT gateway
    (~$32/mo + traffic) and remove the endpoints; for **batch with
    teardown**, endpoints are cheaper because they vanish on `make down`.
- Fargate Compute Savings Plans can reduce Fargate cost by 17–27%; not
  relevant for tear-up/tear-down workflows.
- Image pulls through the ECR endpoint cost $0.01/GB. A 500 MB image
  pulled by 4 tasks per cold start ≈ $0.02 per teardown/rebuild cycle.
- Other regions vary by ±5–15% from us-east-1.
