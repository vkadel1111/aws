# Voice

Reduce avoidable live-agent contacts by identifying — with evidence — *why*
customers end up on the phone for self-service-eligible intents.

> **Status:** pre-validation. The PII redaction service is the first
> shippable component; every other piece is in design or awaiting a
> validation-phase decision gate. See `docs/scope.md`.

## Where to start

| If you are… | Read |
|---|---|
| Establishing context, setting goals, scoping work | [`docs/scope.md`](docs/scope.md) |
| Surveying public reference architectures and gaps | [`docs/prior-art.md`](docs/prior-art.md) |
| Calling the PII redaction service | [`docs/pii-api.md`](docs/pii-api.md) |
| Deploying or tearing down the PII service | [`docs/deploy-and-test.md`](docs/deploy-and-test.md), then [`infra/pii/README.md`](infra/pii/README.md) |
| Modifying the PII service code | [`services/pii/README.md`](services/pii/README.md) |
| Understanding component layout visually | [`docs/architecture-pii.md`](docs/architecture-pii.md) |

## Repository layout

```
.
├── README.md                       this file — index and navigation
├── docs/                           role-agnostic documentation
│   ├── scope.md                    founding artifact: vision, value prop, MVP / long-term scope, non-goals
│   ├── prior-art.md                public reference architectures, what to borrow, where the gaps are
│   ├── pii-api.md                  consumer guide: how to call the PII redaction service
│   ├── architecture-pii.md         Mermaid diagrams of the PII service components and flow
│   └── deploy-and-test.md          operator runbook: local tests → bootstrap → deploy → test → teardown
│
├── infra/
│   └── pii/                        Terraform stack for the stateless PII service
│       ├── README.md               operator reference and per-hour cost breakdown
│       ├── Makefile                pipeline targets: init / plan / up / build / redeploy / down
│       ├── versions.tf             provider + backend declarations
│       ├── main.tf                 provider config, locals, capacity derivation
│       ├── variables.tf            inputs (region, batch size, capacity, image tag, api key, ...)
│       ├── outputs.tf              ALB DNS, ECR URL, ECS cluster/service names, computed capacity
│       ├── vpc.tf                  VPC, private subnets, security groups, VPC endpoints
│       ├── ecr.tf                  ECR repository (force_delete=true) + lifecycle policy
│       ├── alb.tf                  internal ALB, target group, HTTP listener
│       ├── ecs.tf                  Fargate cluster, task definition, service
│       ├── iam.tf                  task execution role + task role with explicit deny on s3/ddb/kms/sm
│       └── scaling.tf              app-autoscaling target + CPU target-tracking policy
│
├── services/
│   └── pii/                        FastAPI + Presidio redaction service
│       ├── README.md               local development and the service's logging discipline
│       ├── pyproject.toml          runtime + dev dependencies
│       ├── Dockerfile              two-stage build, no runtime egress, non-root, read-only rootfs
│       ├── .dockerignore           keeps the image lean and reproducible
│       ├── app/
│       │   ├── main.py             FastAPI entrypoint, /health and /redact, auth, structured logs
│       │   ├── redactor.py         document-scoped, type-typed token replacement
│       │   └── recognizers.py      custom Presidio recognizers (policy / claim / member / agent IDs)
│       └── tests/
│           ├── conftest.py         test environment setup
│           ├── test_redactor.py    redaction correctness, token format, coreference within document
│           └── test_no_pii_in_logs.py   mandatory: synthetic sentinels must not appear in stdout
│
├── ReadMe.txt                      pre-existing repository stub
├── Cap.drawio / Cap.drawio.pdf     pre-existing diagram artifacts (not part of Voice)
├── aws-basic-design-expl.pdf       pre-existing reference doc
└── azure-pipelines.yml             pre-existing CI stub; pipeline integration TBD
```

## Branches

- `main` — clean trunk; nothing Voice-specific yet.
- `voice` — active development branch for this initiative. **All Voice
  work goes here.**

## Conventions

- Documentation lives in `docs/` and is reviewable by non-engineers.
  Markdown only; Mermaid diagrams render inline on GitHub.
- Each service has its own `README.md`; each Terraform stack has its
  own `README.md`. Cross-cutting docs are in `docs/`.
- Commits reference the originating session URL where applicable.
- Tearable infrastructure is a **hard requirement** for any AWS stack
  in this repo — a `terraform destroy` must remove everything created
  by the corresponding `apply`.
