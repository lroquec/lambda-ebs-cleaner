variable "region" {
  description = "The region in which the resources will be created."
  default     = "us-east-1"
}

variable "lambda_name" {
  description = "The name to be used for the Lambda function."
  type        = string
  default     = "ebs_cleaner"
}

variable "lambda_log_retention" {
  description = "The number of days to retain the logs for the Lambda function."
  type        = number
  default     = 7
}

variable "s3_bucket_prefix" {
  description = "The prefix to be used for the S3 bucket name."
  type        = string
  default     = "lambda-ebs-cleaner"
}