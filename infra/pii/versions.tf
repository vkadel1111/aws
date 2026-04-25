terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Backend is intentionally partial. Pipeline supplies it via:
  #   terraform init -backend-config=backend.hcl
  # For local development, run `terraform init -backend=false`
  # or omit this block. See README.md.
  backend "s3" {}
}
