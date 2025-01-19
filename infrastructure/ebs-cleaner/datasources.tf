data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "../../${path.module}/src.zip"
  source_dir  = "../../${path.module}/src"
}