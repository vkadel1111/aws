provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  name_prefix = "${var.project}-${var.component}-${var.environment}"
  name        = "${local.name_prefix}-${random_id.suffix.hex}"

  common_tags = {
    Project     = var.project
    Component   = var.component
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  # Derive desired task count from configured batch size.
  # Floor at 1 so the service is always reachable.
  computed_min_capacity = max(
    1,
    ceil(
      var.expected_batch_size /
      (var.conversations_per_task_per_minute * var.target_minutes_to_complete)
    )
  )

  computed_max_capacity = min(
    var.max_capacity_cap,
    max(local.computed_min_capacity * 2, local.computed_min_capacity + 1)
  )
}
