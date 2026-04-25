variable "project" {
  description = "Project tag applied to all resources."
  type        = string
  default     = "voice"
}

variable "component" {
  description = "Component tag for this stack."
  type        = string
  default     = "pii"
}

variable "environment" {
  description = "Environment label (dev, test, etc.)."
  type        = string
  default     = "dev"
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the new VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "expected_batch_size" {
  description = <<EOT
Approximate number of conversations the next batch will process. Used to
derive minimum task count so the service is warm before the batch hits.
Adjust this per pipeline run.
EOT
  type        = number
  default     = 50
}

variable "conversations_per_task_per_minute" {
  description = "Conservative throughput estimate per Fargate task. Tune after measurement."
  type        = number
  default     = 30
}

variable "target_minutes_to_complete" {
  description = "Target wall-clock minutes to finish a batch. Drives min capacity."
  type        = number
  default     = 5
}

variable "max_capacity_cap" {
  description = "Hard ceiling on Fargate task count, regardless of batch size."
  type        = number
  default     = 20
}

variable "task_cpu" {
  description = "Fargate task CPU units (256, 512, 1024, 2048, 4096)."
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 2048
}

variable "container_image_tag" {
  description = "Image tag to deploy from the project ECR repo."
  type        = string
  default     = "latest"
}

variable "caller_cidr_blocks" {
  description = "Source CIDRs allowed to invoke the redact ALB. Single internal user expected; restrict tightly."
  type        = list(string)
  default     = []
}

variable "api_key" {
  description = <<EOT
Shared secret for the single internal caller. Injected into the task as an
environment variable; not stored in AWS Secrets Manager (keeps teardown clean
and avoids residual recovery-window state).
EOT
  type        = string
  sensitive   = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention. Short by default to support clean teardown."
  type        = number
  default     = 7
}
