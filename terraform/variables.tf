variable "environment" {
  description = "Environment name (qa, staging, prod)"
  type        = string
  validation {
    condition     = contains(["qa", "staging", "prod"], var.environment)
    error_message = "Environment must be qa, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Lambda Configuration
variable "lambda_filename" {
  description = "Lambda deployment package filename"
  type        = string
  default     = "lambda-code.zip"
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

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds (max 900 for 15 minutes)"
  type        = number
  default     = 900 # 15 minutes for large batches
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 512
}

# SQS Configuration
variable "sqs_batch_size" {
  description = "Maximum number of records to retrieve from SQS per invocation"
  type        = number
  default     = 10
  validation {
    condition     = var.sqs_batch_size >= 1 && var.sqs_batch_size <= 10
    error_message = "SQS batch size must be between 1 and 10."
  }
}

variable "sqs_maximum_batching_window" {
  description = "Maximum batching window in seconds for SQS event source mapping"
  type        = number
  default     = 5
  validation {
    condition     = var.sqs_maximum_batching_window >= 0 && var.sqs_maximum_batching_window <= 300
    error_message = "SQS maximum batching window must be between 0 and 300 seconds."
  }
}

# External Services Configuration
variable "form_service_url" {
  description = "Form Service API URL"
  type        = string
}

variable "employee_service_url" {
  description = "Employee Service API URL"
  type        = string
}

# Cognito Configuration
variable "cognito_user_pool_id" {
  description = "AWS Cognito User Pool ID"
  type        = string
}

variable "cognito_client_id" {
  description = "AWS Cognito Client ID"
  type        = string
}

variable "cognito_client_secret" {
  description = "AWS Cognito Client Secret (optional, if not using Secrets Manager)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "cognito_client_secret_secret_name" {
  description = "Name of the secret in AWS Secrets Manager containing the Cognito client secret"
  type        = string
  default     = ""
}

variable "cognito_system_username" {
  description = "System user username for Cognito authentication"
  type        = string
  sensitive   = true
}

variable "cognito_system_password" {
  description = "System user password for Cognito authentication (if not using Secrets Manager)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "cognito_system_password_secret_name" {
  description = "Name of the secret in AWS Secrets Manager containing the Cognito system user password"
  type        = string
  default     = ""
}

# Worker Configuration
variable "assignment_batch_size" {
  description = "Number of assignments to create per batch"
  type        = number
  default     = 100
  validation {
    condition     = var.assignment_batch_size > 0 && var.assignment_batch_size <= 1000
    error_message = "Assignment batch size must be between 1 and 1000."
  }
}

variable "max_retries" {
  description = "Maximum number of retry attempts"
  type        = number
  default     = 3
}

variable "retry_delay_seconds" {
  description = "Delay between retries in seconds"
  type        = number
  default     = 5
}

variable "candidate_form_names" {
  description = "Comma-separated list of form names for candidate assessments"
  type        = string
  default     = "Huvantia Measure,Integridad,Valores Huvantia,Habilidades Cognitivas,Motivaciones,Liderazgo,Personalidad"
}

variable "log_level" {
  description = "Logging level (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"
  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR."
  }
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
