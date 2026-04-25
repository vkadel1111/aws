# PII Service — Architecture Diagram

Visual companion to `infra/pii/README.md` (operator) and
`docs/pii-api.md` (consumer). Diagrams render inline on GitHub.

## Components and connections

```mermaid
flowchart LR
    Caller["Internal caller<br/>(single, allowlisted CIDR)"]

    subgraph VPC["AWS VPC (10.40.0.0/16) — no IGW, no NAT"]
        direction TB

        subgraph Subnets["Private subnets · 2 AZs"]
            ALB["Internal ALB<br/>:80"]
            T1["Fargate Task 1<br/>FastAPI + Presidio"]
            Tn["Fargate Task N<br/>(autoscaled on CPU)"]
        end

        subgraph Endpoints["VPC endpoints"]
            EpEcrApi["Interface · ECR API"]
            EpEcrDkr["Interface · ECR DKR"]
            EpLogs["Interface · CloudWatch Logs"]
            EpS3["Gateway · S3 (ECR layers)"]
        end
    end

    subgraph AWSReg["AWS regional services"]
        ECR[("ECR repository<br/>force_delete = true")]
        CWL[("CloudWatch Logs<br/>metadata only · 7d retention")]
        S3svc[("S3<br/>(ECR layer storage)")]
    end

    subgraph IAM["IAM"]
        TER["Task Execution Role<br/>(ECR pull · log put)"]
        TR["Task Role<br/>Deny s3 / ddb / kms / secretsmanager"]
    end

    Caller -- "HTTP /redact<br/>x-api-key" --> ALB
    ALB -- ":8080" --> T1
    ALB -- ":8080" --> Tn

    T1 -. "image pull" .-> EpEcrApi
    T1 -. "image pull" .-> EpEcrDkr
    T1 -. "layers" .-> EpS3
    T1 -. "log put" .-> EpLogs

    EpEcrApi --> ECR
    EpEcrDkr --> ECR
    EpS3 --> S3svc
    EpLogs --> CWL

    TER -. "assumed by" .-> T1
    TR  -. "assumed by" .-> T1

    classDef vpc  fill:#e8f4fd,stroke:#0277bd,color:#01579b
    classDef aws  fill:#fff7e6,stroke:#e65100,color:#bf360c
    classDef iam  fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c
    classDef ext  fill:#f1f8e9,stroke:#33691e,color:#1b5e20

    class ALB,T1,Tn,EpEcrApi,EpEcrDkr,EpLogs,EpS3 vpc
    class ECR,CWL,S3svc aws
    class TER,TR iam
    class Caller ext
```

## Request flow

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant ALB as Internal ALB
    participant Task as Fargate Task
    participant Logs as CloudWatch Logs

    Caller->>ALB: POST /redact (x-api-key, contact_id, transcript)
    ALB->>Task: forward :8080
    Task->>Task: validate API key
    Task->>Task: Presidio analyze — in-memory only
    Task->>Task: assign document-scoped tokens<br/>(<PERSON_1>, <POLICY_NUM_1>, ...)
    Task->>Task: replace spans · build replacements map
    Task->>Logs: metadata only<br/>(request_id, contact_id, content_sha256, counts, latency)
    Task-->>ALB: 200 · { redacted_transcript, replacements, stats }
    ALB-->>Caller: 200 OK
    Note over Caller: replacements dict now lives only<br/>in caller's process memory
```

## Explicitly absent (by design)

These are *not* part of the stack, and the task IAM role denies the APIs
that would create them:

- **No DynamoDB / RDS / S3 PII vault.** Replacements travel only in the
  HTTP response.
- **No KMS CMK** — there is nothing at rest to encrypt.
- **No Secrets Manager** — the API key is injected at deploy time as a
  task environment variable; teardown leaves no recovery-window state.
- **No NAT gateway, no internet gateway.** Tasks reach AWS APIs solely
  via VPC endpoints; no path to the public internet.
- **No /rehydrate endpoint.** If the caller drops the dict, the value is
  unrecoverable from this stack.

## Capacity (defaults)

```mermaid
flowchart LR
    EBS["expected_batch_size<br/>(default 50)"] --> CALC

    subgraph CALC["Locals"]
        FORM["min = ceil(EBS / (cpm × min_to_complete))<br/>cpm = 30 · min_to_complete = 5"]
    end

    CALC --> MIN["min_capacity = max(1, computed)"]
    MIN --> MAX["max_capacity = min(cap, max(min×2, min+1))"]

    MIN --> SVC["ECS desired_count"]
    MAX --> ASG["Application Auto Scaling target<br/>CPU 60% · cooldown 30/60s"]
```

For the default `expected_batch_size = 50` this resolves to
`min = 1, max = 2`. Increase `expected_batch_size` per pipeline run when a
larger batch is staged; the next `make up` re-applies cleanly.

## Lifecycle

```mermaid
flowchart LR
    A["pipeline trigger"] --> B["make init"]
    B --> C["make up"]
    C --> D["make build"]
    D --> E["make redeploy"]
    E --> F["batch runs<br/>(callers hit /redact)"]
    F --> G["make down"]
    G -. "tfstate persists in S3 backend" .-> A

    classDef step fill:#e3f2fd,stroke:#0d47a1
    class A,B,C,D,E,F,G step
```

`terraform destroy` removes the VPC, ALB, ECS cluster + service, ECR
(with images via `force_delete`), VPC endpoints, IAM roles, log group,
and autoscaling target. The Terraform state bucket and lock table live
outside this stack and are intentionally not in scope for teardown.
