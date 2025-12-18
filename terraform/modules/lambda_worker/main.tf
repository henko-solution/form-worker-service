# Lambda Worker Module
# This module creates Lambda function for processing SQS events

# Lambda Function
resource "aws_lambda_function" "main" {
  filename      = var.lambda_filename
  function_name = "${var.project_name}-${var.environment}"
  role          = aws_iam_role.lambda_execution.arn
  handler       = var.lambda_handler
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size

  layers = var.create_layer ? [aws_lambda_layer_version.dependencies[0].arn] : []

  # Force update when ZIP content changes
  source_code_hash = filebase64sha256(var.lambda_filename)

  environment {
    variables = var.environment_variables
  }

  # Enable X-Ray tracing
  tracing_config {
    mode = "Active"
  }

  # Note: No VPC configuration needed - worker doesn't access database
  # Note: No Dead Letter Queue configured here - SQS handles DLQ

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-lambda-${var.environment}"
  })
}

# Lambda Layer for dependencies (optional)
resource "aws_lambda_layer_version" "dependencies" {
  count               = var.create_layer ? 1 : 0
  filename            = var.layer_filename
  layer_name          = "${var.project_name}-dependencies-${var.environment}"
  compatible_runtimes = [var.lambda_runtime]
  description         = "Dependencies for ${var.project_name} Lambda"

  # Force update when ZIP content changes
  source_code_hash = filebase64sha256(var.layer_filename)
}

# IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-lambda-execution-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# IAM Policy for Lambda to access SQS
resource "aws_iam_policy" "lambda_sqs" {
  name        = "${var.project_name}-lambda-sqs-policy-${var.environment}"
  description = "Policy for Lambda to access SQS"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = var.sqs_queue_arn
      }
    ]
  })
}

# Attach SQS policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_sqs" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.lambda_sqs.arn
}

# IAM Policy for Lambda to access Secrets Manager (for API key)
resource "aws_iam_policy" "lambda_secrets" {
  name        = "${var.project_name}-lambda-secrets-policy-${var.environment}"
  description = "Policy for Lambda to access Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "*" # Can be restricted to specific secret ARN
      }
    ]
  })
}

# Attach Secrets Manager policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_secrets" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.lambda_secrets.arn
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.main.function_name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.cloudwatch_kms_key_id

  tags = var.common_tags
}

# CloudWatch Log Stream (created automatically by Lambda, but we can define retention)

# Lambda Permission for SQS to invoke Lambda
resource "aws_lambda_permission" "allow_sqs" {
  statement_id  = "AllowExecutionFromSQS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "sqs.amazonaws.com"
  source_arn    = var.sqs_queue_arn
}
