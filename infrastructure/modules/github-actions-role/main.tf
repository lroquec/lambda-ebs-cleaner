variable "role_name" {
  type        = string
  description = "Name of the IAM role"
}

variable "repo_name" {
  type        = string
  description = "GitHub repository name (without organization)"
}

variable "provider_arn" {
  type        = string
  description = "ARN of the GitHub OIDC provider"
}

variable "policy" {
  type        = string
  description = "IAM policy JSON for the role"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}

resource "aws_iam_role" "github_actions" {
  name = var.role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = var.provider_arn
        }
        Condition = {
          StringLike = {
            "token.actions.githubusercontent.com:sub": "repo:*/${var.repo_name}:*"
          }
          StringEquals = {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "github_actions" {
  name   = "${var.role_name}-policy"
  role   = aws_iam_role.github_actions.id
  policy = var.policy
}

output "role_arn" {
  value       = aws_iam_role.github_actions.arn
  description = "ARN of the GitHub Actions role"
}