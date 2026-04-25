# Pipeline-friendly targets for bring-up and tear-down of the PII stack.
#
# Required env (typically supplied by the pipeline or a .env file):
#   AWS_REGION              region to deploy into
#   TF_BACKEND_BUCKET       existing S3 bucket holding tfstate
#   TF_BACKEND_KEY          state object key (e.g. voice/pii/dev.tfstate)
#   TF_BACKEND_DDB_TABLE    DynamoDB table for state lock (optional but recommended)
#   API_KEY                 shared secret injected into the task
#   EXPECTED_BATCH_SIZE     conversations the next batch will process (default 50)
#   IMAGE_TAG               ECR image tag to deploy (default 'latest')
#
# Pipeline lifecycle:
#   make init        once per workspace
#   make plan        review changes
#   make up          apply
#   make build       build + push container image
#   make redeploy    force a new deployment with the latest image
#   make down        tear everything down

SHELL              := /bin/bash
TF                 ?= terraform
SERVICE_DIR        := ../../services/pii
EXPECTED_BATCH_SIZE ?= 50
IMAGE_TAG          ?= latest
AWS_REGION         ?= us-east-1

.PHONY: init plan up down output build login redeploy fmt validate

init:
	$(TF) init \
	  -backend-config="bucket=$(TF_BACKEND_BUCKET)" \
	  -backend-config="key=$(TF_BACKEND_KEY)" \
	  -backend-config="region=$(AWS_REGION)" \
	  $(if $(TF_BACKEND_DDB_TABLE),-backend-config="dynamodb_table=$(TF_BACKEND_DDB_TABLE)",)

fmt:
	$(TF) fmt -recursive

validate:
	$(TF) validate

plan:
	$(TF) plan \
	  -var "region=$(AWS_REGION)" \
	  -var "expected_batch_size=$(EXPECTED_BATCH_SIZE)" \
	  -var "container_image_tag=$(IMAGE_TAG)" \
	  -var "api_key=$(API_KEY)"

up:
	$(TF) apply -auto-approve \
	  -var "region=$(AWS_REGION)" \
	  -var "expected_batch_size=$(EXPECTED_BATCH_SIZE)" \
	  -var "container_image_tag=$(IMAGE_TAG)" \
	  -var "api_key=$(API_KEY)"

down:
	$(TF) destroy -auto-approve \
	  -var "region=$(AWS_REGION)" \
	  -var "expected_batch_size=$(EXPECTED_BATCH_SIZE)" \
	  -var "container_image_tag=$(IMAGE_TAG)" \
	  -var "api_key=$(API_KEY)"

output:
	$(TF) output

# Build + push the container image to the ECR repo created by `make up`.
# Requires Docker daemon and AWS credentials.
build:
	@ECR_URL=$$($(TF) output -raw ecr_repository_url); \
	REGISTRY=$${ECR_URL%/*}; \
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $$REGISTRY; \
	docker build -t $$ECR_URL:$(IMAGE_TAG) $(SERVICE_DIR); \
	docker push $$ECR_URL:$(IMAGE_TAG)

# Force a fresh deployment so the service picks up the new image.
redeploy:
	@CLUSTER=$$($(TF) output -raw ecs_cluster_name); \
	SERVICE=$$($(TF) output -raw ecs_service_name); \
	aws ecs update-service --cluster $$CLUSTER --service $$SERVICE --force-new-deployment --region $(AWS_REGION) > /dev/null; \
	echo "Forced new deployment of $$SERVICE in $$CLUSTER"
