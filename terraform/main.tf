terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  cloud {
    organization = "henko-solution"
    workspaces {
      name = "form-worker-service-qa"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Henko Form Worker Service"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Henko Team"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Secrets Manager data source for API key
data "aws_secretsmanager_secret" "internal_api_key" {
  name = var.internal_api_key_secret_name
}

data "aws_secretsmanager_secret_version" "internal_api_key" {
  secret_id = data.aws_secretsmanager_secret.internal_api_key.id
}

# Local values
locals {
  # Extract repository name from git remote
  repo_name = "form-worker-service"

  # Map environment to deployment suffix
  environment_suffix = {
    "dev"  = "qa"
    "qa"   = "qa"
    "prod" = "prod"
  }

  # Use repository name with environment suffix
  project_name = "${local.repo_name}-${local.environment_suffix[var.environment]}"

  common_tags = {
    Project     = local.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = "Henko Team"
  }
}

# SQS Queue for dispatch events
# Note: This queue is created here, but form-service publishes to it
resource "aws_sqs_queue" "dispatch_events" {
  name                      = "${local.project_name}-dispatch-events"
  message_retention_seconds = 345600 # 4 days
  visibility_timeout_seconds = 900    # 15 minutes (Lambda timeout)

  # Dead Letter Queue configuration
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dispatch_events_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Name = "${local.project_name}-dispatch-events"
  })
}

# Dead Letter Queue for failed messages
resource "aws_sqs_queue" "dispatch_events_dlq" {
  name                      = "${local.project_name}-dispatch-events-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = merge(local.common_tags, {
    Name = "${local.project_name}-dispatch-events-dlq"
  })
}

# Lambda Worker Module
module "lambda_worker" {
  source = "./modules/lambda_worker"

  project_name         = local.project_name
  environment          = var.environment
  aws_region           = var.aws_region
  aws_account_id       = data.aws_caller_identity.current.account_id

  lambda_filename    = var.lambda_filename
  lambda_handler     = var.lambda_handler
  lambda_runtime     = var.lambda_runtime
  lambda_timeout     = var.lambda_timeout
  lambda_memory_size = var.lambda_memory_size

  # SQS Queue configuration
  sqs_queue_arn = aws_sqs_queue.dispatch_events.arn
  sqs_queue_url = aws_sqs_queue.dispatch_events.url

  # Batch configuration
  sqs_batch_size              = var.sqs_batch_size
  sqs_maximum_batching_window = var.sqs_maximum_batching_window

  # Environment variables
  environment_variables = {
    ENVIRONMENT            = var.environment
    AWS_REGION             = var.aws_region
    SQS_QUEUE_URL          = aws_sqs_queue.dispatch_events.url
    FORM_SERVICE_URL       = var.form_service_url
    EMPLOYEE_SERVICE_URL   = var.employee_service_url
    INTERNAL_API_KEY       = data.aws_secretsmanager_secret_version.internal_api_key.secret_string
    ASSIGNMENT_BATCH_SIZE  = var.assignment_batch_size
    MAX_RETRIES            = var.max_retries
    RETRY_DELAY_SECONDS    = var.retry_delay_seconds
    LOG_LEVEL              = var.log_level
    DEBUG                  = var.environment == "dev" || var.environment == "qa" ? "true" : "false"
  }

  # CloudWatch configuration
  log_retention_days  = var.log_retention_days
  cloudwatch_kms_key_id = var.cloudwatch_kms_key_id

  common_tags = local.common_tags
}

# SQS Event Source Mapping (Lambda trigger)
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.dispatch_events.arn
  function_name    = module.lambda_worker.lambda_function_arn

  batch_size                         = var.sqs_batch_size
  maximum_batching_window_in_seconds  = var.sqs_maximum_batching_window
  enabled                            = true

  # Filter criteria (optional - can filter messages)
  # filter_criteria {
  #   filter {
  #     pattern = jsonencode({
  #       body = {
  #         tenant_id = ["henko-main"]
  #       }
  #     })
  #   }
  # }

  depends_on = [
    module.lambda_worker
  ]
}
