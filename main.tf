resource "aws_s3_bucket" "lambda_bucket" {
  bucket_prefix = var.s3_bucket_prefix
  force_destroy = true
}

resource "aws_lambda_function" "app" {
  function_name = var.lambda_name
  description   = "ebs cleaner serverless function"

  s3_bucket = aws_s3_bucket.lambda_bucket.id
  s3_key    = aws_s3_object.lambda_app.key

  handler = "app.lambda_handler"
  runtime = "python3.11"

  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  memory_size = 128
  timeout     = 60

  role       = aws_iam_role.lambda_exec.arn
  depends_on = [aws_cloudwatch_log_group.lambda_log]
}

resource "aws_cloudwatch_log_group" "lambda_log" {
  name              = "/aws/lambda/${var.lambda_name}"
  retention_in_days = var.lambda_log_retention
}

resource "aws_iam_role" "lambda_exec" {
  name                 = "lambda_exec_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_exec" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_exec.name
}

resource "aws_iam_role_policy_attachment" "ebs_access" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  role       = aws_iam_role.lambda_exec.name
}

resource "aws_s3_object" "lambda_app" {
  bucket = aws_s3_bucket.lambda_bucket.id
  key    = "source.zip"
  source = data.archive_file.lambda_zip.output_path

  etag = filemd5(data.archive_file.lambda_zip.output_path)
}