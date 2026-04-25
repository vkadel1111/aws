output "alb_dns_name" {
  description = "Internal ALB DNS for the redact service."
  value       = aws_lb.this.dns_name
}

output "ecr_repository_url" {
  description = "Push the service image here, then deploy."
  value       = aws_ecr_repository.service.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_name" {
  value = aws_ecs_service.service.name
}

output "vpc_id" {
  value = aws_vpc.this.id
}

output "computed_capacity" {
  description = "Min/max derived from expected_batch_size."
  value = {
    min = local.computed_min_capacity
    max = local.computed_max_capacity
  }
}
