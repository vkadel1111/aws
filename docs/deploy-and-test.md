# PII Service — Deploy and Test Runbook

Step-by-step from a clean checkout to a tested deployment and back to
zero. Pair with `infra/pii/README.md` (operator reference) and
`docs/pii-api.md` (consumer reference).

## Prerequisites

- AWS CLI v2 configured for the target account (`aws sts get-caller-identity`).
- Terraform ≥ 1.6.
- Docker daemon running locally.
- Python 3.11 (only for local testing in Phase 1).
- `jq` for inspecting responses.

## Phase 1 — Local tests (no AWS needed)

Validate the service logic — including the **no-PII-in-logs** assertion —
before paying for AWS resources.

```bash
cd services/pii
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm

pytest -q                                # all tests must pass

docker build -t voice-pii:dev .          # confirm image builds
docker run --rm -d -p 8080:8080 \
  -e API_KEY=local-test \
  --name voice-pii voice-pii:dev

# wait ~15s for spaCy to load
curl -sS http://localhost:8080/health

curl -sS -X POST http://localhost:8080/redact \
  -H "x-api-key: local-test" \
  -H "content-type: application/json" \
  -d '{"contact_id":"ct_local","transcript":[
        {"speaker":"agent","text":"Hi Jane Doe, your policy is AB-12345."}
      ]}' | jq

docker stop voice-pii
```

If tests pass and the local curl returns redacted text + a `replacements`
map, proceed to Phase 2.

## Phase 2 — One-time state backend bootstrap

The Terraform state bucket and lock table live **outside** the tearable
stack so state survives teardown.

```bash
export AWS_REGION=us-east-1
export TF_BACKEND_BUCKET=voice-tfstate-$(aws sts get-caller-identity --query Account --output text)

aws s3api create-bucket \
  --bucket "$TF_BACKEND_BUCKET" \
  --region "$AWS_REGION" \
  $( [ "$AWS_REGION" = "us-east-1" ] || echo "--create-bucket-configuration LocationConstraint=$AWS_REGION" )

aws s3api put-bucket-versioning --bucket "$TF_BACKEND_BUCKET" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption --bucket "$TF_BACKEND_BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-public-access-block --bucket "$TF_BACKEND_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws dynamodb create-table \
  --table-name voice-tflock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

## Phase 3 — Deploy

**Per-deploy environment:**

```bash
export AWS_REGION=us-east-1
export TF_BACKEND_BUCKET=voice-tfstate-<your-account-id>
export TF_BACKEND_KEY=voice/pii/dev.tfstate
export TF_BACKEND_DDB_TABLE=voice-tflock
export API_KEY=$(openssl rand -hex 32)
export EXPECTED_BATCH_SIZE=50
export IMAGE_TAG=v0.1.0
```

**First deploy** (chicken-and-egg: ECR repo and ECS service are created
first, then the image is pushed, then the service is told to redeploy):

```bash
cd infra/pii
make init        # configures S3 backend, downloads providers
make plan        # review what will be created
make up          # creates VPC / ECR / ALB / ECS; tasks unhealthy until image is pushed
make build       # builds container locally, pushes to the new ECR repo
make redeploy    # forces ECS to pull the new image; tasks become healthy
```

Watch service health until tasks show as healthy targets in the ALB —
typically ~2 minutes after `make redeploy`:

```bash
make output                                                # ALB DNS, ECR URL, etc.
aws ecs describe-services \
  --cluster $(make output | awk -F'= ' '/ecs_cluster_name/{gsub(/"/,"",$2); print $2}') \
  --services $(make output | awk -F'= ' '/ecs_service_name/{gsub(/"/,"",$2); print $2}') \
  --query 'services[0].deployments'
```

**Subsequent deploys** are just:

```bash
make build && make redeploy
```

## Phase 4 — End-to-end test

The ALB is **internal**, so a laptop `curl` will not reach it. Three
options:

### Option A — temporary bastion in the same VPC

Easiest for first-time testing:

```bash
VPC_ID=$(cd infra/pii && terraform output -raw vpc_id)
SUBNET_ID=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC_ID \
            --query 'Subnets[0].SubnetId' --output text)

# Launch a t3.nano with the SSM agent in that subnet, attach a security
# group permitted to reach the ALB SG. Connect with:
aws ssm start-session --target <instance-id>
```

Inside the session:

```bash
ALB_DNS=<from `terraform output alb_dns_name`>
API_KEY=<the value used at deploy time>

curl -sS -X POST "http://$ALB_DNS/redact" \
  -H "x-api-key: $API_KEY" \
  -H "content-type: application/json" \
  -d '{"contact_id":"ct_test","transcript":[
        {"speaker":"agent","text":"Hi Jane Doe, your policy is AB-12345."}
      ]}'
```

### Option B — SSM port-forwarding to your laptop

If you already have an SSM-managed instance in the VPC:

```bash
aws ssm start-session --target <instance-id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters host="$ALB_DNS",portNumber="80",localPortNumber="8080"
# In another shell:
curl http://localhost:8080/health
```

### Option C — existing private connectivity

Peering / Transit Gateway / VPN / Direct Connect that already routes to
the new VPC's `10.40.0.0/16`. Curl directly.

### Expected response

```json
{
  "contact_id": "ct_test",
  "redacted_transcript": [
    {"speaker": "agent", "text": "Hi <PERSON_1>, your policy is <POLICY_NUM_1>."}
  ],
  "replacements": {
    "<PERSON_1>": "Jane Doe",
    "<POLICY_NUM_1>": "AB-12345"
  },
  "stats": {
    "entities_by_type": {"PERSON": 1, "POLICY_NUM": 1},
    "latency_ms": 87,
    "request_id": "..."
  }
}
```

### Verify the security guarantee in production logs

```bash
LOG_GROUP=$(aws logs describe-log-groups \
  --query 'logGroups[?contains(logGroupName, `voice-pii`)].logGroupName' \
  --output text)

aws logs tail "$LOG_GROUP" --since 5m | grep -E "Jane Doe|AB-12345" \
  && echo "FAIL: PII leaked into logs" \
  || echo "PASS: no PII in logs"
```

## Phase 5 — Teardown

```bash
cd infra/pii
make down
```

`terraform destroy` removes the VPC, ECR (with images), ECS, ALB, VPC
endpoints, IAM roles, log group, and autoscaling target. The state
bucket and lock table remain in place for the next deploy.

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `make up` succeeds, ECS targets unhealthy | First deploy — no image at configured tag | Run `make build && make redeploy` |
| `make build` fails on `aws ecr get-login-password` | AWS credentials not in shell | `export AWS_PROFILE=...` or `aws configure` |
| Curl from laptop times out | ALB is internal | Use Option A / B / C |
| 401 on `/redact` | `x-api-key` header missing or wrong | Confirm value matches `$API_KEY` at deploy time |
| 503 on `/redact` for first 10–20s | spaCy still loading | Hit `/health` first as a readiness gate |
| `terraform destroy` says ECR not empty | Race | Re-run `make down`, or `aws ecr delete-repository --force` |
| Tasks restart-loop on cold start | OOM during model load | Bump `task_memory` in `variables.tf` (default 2048 MiB) |
