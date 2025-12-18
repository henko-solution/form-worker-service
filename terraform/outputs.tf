# Main outputs
output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "project_name" {
  description = "Project name"
  value       = local.project_name
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

# Lambda Outputs
output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.lambda_worker.lambda_function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.lambda_worker.lambda_function_arn
}

# SQS Outputs
output "sqs_queue_url" {
  description = "URL of the SQS queue for dispatch events"
  value       = aws_sqs_queue.dispatch_events.url
}

output "sqs_queue_arn" {
  description = "ARN of the SQS queue for dispatch events"
  value       = aws_sqs_queue.dispatch_events.arn
}

output "sqs_queue_name" {
  description = "Name of the SQS queue for dispatch events"
  value       = aws_sqs_queue.dispatch_events.name
}

output "sqs_dlq_url" {
  description = "URL of the Dead Letter Queue"
  value       = aws_sqs_queue.dispatch_events_dlq.url
}

output "sqs_dlq_arn" {
  description = "ARN of the Dead Letter Queue"
  value       = aws_sqs_queue.dispatch_events_dlq.arn
}

# Lambda Event Source Mapping
output "lambda_event_source_mapping_id" {
  description = "ID of the Lambda event source mapping"
  value       = aws_lambda_event_source_mapping.sqs_trigger.id
}

# CloudWatch Logs
output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = module.lambda_worker.cloudwatch_log_group_name
}

# Monitoring URLs
output "cloudwatch_logs_url" {
  description = "CloudWatch Logs URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#logsV2:log-groups/log-group/${module.lambda_worker.cloudwatch_log_group_name}"
}

output "lambda_console_url" {
  description = "Lambda Console URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/lambda/home?region=${var.aws_region}#/functions/${module.lambda_worker.lambda_function_name}"
}

output "sqs_console_url" {
  description = "SQS Console URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/sqs/v2/home?region=${var.aws_region}#/queues/${aws_sqs_queue.dispatch_events.url}"
}

# Summary
output "deployment_summary" {
  description = "Deployment summary"
  value = {
    environment              = var.environment
    project_name             = local.project_name
    aws_region               = var.aws_region
    lambda_function_name     = module.lambda_worker.lambda_function_name
    lambda_function_arn      = module.lambda_worker.lambda_function_arn
    sqs_queue_url           = aws_sqs_queue.dispatch_events.url
    sqs_queue_arn           = aws_sqs_queue.dispatch_events.arn
    sqs_dlq_url             = aws_sqs_queue.dispatch_events_dlq.url
    cloudwatch_log_group     = module.lambda_worker.cloudwatch_log_group_name
  }
}
