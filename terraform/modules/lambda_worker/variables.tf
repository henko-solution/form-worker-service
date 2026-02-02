variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

# Lambda Function Configuration
variable "lambda_filename" {
  description = "Path to the Lambda function ZIP file"
  type        = string
  default     = "../lambda-code.zip"
}

variable "lambda_handler" {
  description = "Lambda function handler"
  type        = string
  default     = "lambda_handler.lambda_handler"
}

variable "lambda_runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.14"
}

variable "enable_warming" {
  description = "Enable EventBridge scheduled invocations to keep Lambda warm and reduce cold starts"
  type        = bool
  default     = true
}

variable "warming_schedule_rate" {
  description = "EventBridge schedule for Lambda warming. Default: every 5 min during 8am-6pm UTC Mon-Fri"
  type        = string
  default     = "cron(0/5 8-18 ? * MON-FRI *)"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 900 # 15 minutes
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 512
}

variable "environment_variables" {
  description = "Environment variables for Lambda function"
  type        = map(string)
  default     = {}
}

# Lambda Layer Configuration
variable "create_layer" {
  description = "Whether to create a Lambda layer"
  type        = bool
  default     = false
}

variable "layer_filename" {
  description = "Path to the Lambda layer ZIP file"
  type        = string
  default     = "../lambda-layer.zip"
}

# SQS Configuration
variable "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  type        = string
}

variable "sqs_queue_url" {
  description = "URL of the SQS queue"
  type        = string
}

# CloudWatch Configuration
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "cloudwatch_kms_key_id" {
  description = "KMS key ID for CloudWatch log encryption"
  type        = string
  default     = null
}

variable "common_tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default     = {}
}
