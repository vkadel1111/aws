# Task execution role: lets ECS pull from ECR and write to CloudWatch Logs.
data "aws_iam_policy_document" "task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${local.name}-task-exec"
  assume_role_policy = data.aws_iam_policy_document.task_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution_default" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task role: the workload's runtime identity. Intentionally has NO permissions
# to S3, DynamoDB, KMS, or anything else that would allow PII persistence.
# This is enforced by giving it an empty inline policy and zero attachments.
resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.task_assume.json
}

resource "aws_iam_role_policy" "task_no_persistence" {
  name = "${local.name}-task-no-persistence"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "NoOp"
        Effect   = "Deny"
        Action   = ["s3:*", "dynamodb:*", "kms:*", "secretsmanager:*"]
        Resource = "*"
      }
    ]
  })
}
