# Lambda Worker Module

This module creates a Lambda function for processing SQS events in the Form Worker Service.

## Resources Created

- Lambda function
- IAM role and policies (SQS, Secrets Manager, CloudWatch)
- CloudWatch log group
- Lambda permission for SQS invocation
- Optional Lambda layer for dependencies

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Name of the project | string | - | yes |
| environment | Environment name | string | - | yes |
| aws_region | AWS region | string | - | yes |
| aws_account_id | AWS account ID | string | - | yes |
| lambda_filename | Path to Lambda ZIP file | string | `"../lambda-code.zip"` | no |
| lambda_handler | Lambda handler | string | `"lambda_handler.lambda_handler"` | no |
| lambda_runtime | Lambda runtime | string | `"python3.13"` | no |
| lambda_timeout | Lambda timeout in seconds | number | `900` | no |
| lambda_memory_size | Lambda memory in MB | number | `512` | no |
| sqs_queue_arn | SQS queue ARN | string | - | yes |
| sqs_queue_url | SQS queue URL | string | - | yes |
| environment_variables | Environment variables | map(string) | `{}` | no |
| log_retention_days | CloudWatch log retention | number | `30` | no |

## Outputs

| Name | Description |
|------|-------------|
| lambda_function_name | Name of the Lambda function |
| lambda_function_arn | ARN of the Lambda function |
| lambda_execution_role_arn | ARN of the execution role |
| cloudwatch_log_group_name | Name of the CloudWatch log group |

## Usage

```hcl
module "lambda_worker" {
  source = "./modules/lambda_worker"

  project_name   = "form-worker-service-qa"
  environment    = "qa"
  aws_region     = "us-east-1"
  aws_account_id = "123456789012"

  lambda_filename = "lambda-code.zip"
  lambda_handler   = "lambda_handler.lambda_handler"
  lambda_timeout   = 900
  lambda_memory_size = 512

  sqs_queue_arn = aws_sqs_queue.dispatch_events.arn
  sqs_queue_url = aws_sqs_queue.dispatch_events.url

  environment_variables = {
    ENVIRONMENT = "qa"
    LOG_LEVEL   = "INFO"
  }

  log_retention_days = 30
}
```
