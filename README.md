# Henko Form Worker Service

Asynchronous worker service for processing form dispatch events via SQS. This service consumes messages from AWS SQS, retrieves users from Employee Service, and creates assignments via the Form Service API.

## 🏗️ Architecture

This service implements an **Event-Driven Worker Architecture** with the following structure:

- **Lambda Handler**: Entry point for SQS-triggered Lambda function
- **Workers**: Event processing logic
- **Services**: External API clients (Employee Service, Form Service)
- **Models**: Pydantic models for event validation

### 📁 Project Structure

```
form-worker-service/
├── lambda_handler.py          # Lambda handler entry point (root level)
├── app/
│   ├── workers/
│   │   └── dispatch_processor.py  # Main dispatch processing logic
│   ├── services/
│   │   ├── employee_service.py    # Employee Service API client (requests)
│   │   ├── form_service_client.py # Form Service API client (requests)
│   │   └── cognito_auth_service.py # Cognito authentication service
│   ├── models/
│   │   └── events.py              # Pydantic models for SQS events
│   ├── exceptions.py              # Custom exceptions
│   └── config.py                  # Application configuration
└── terraform/                    # Infrastructure as Code
```

### 🔄 Data Flow

1. **SQS Event** → Lambda Handler
2. **Lambda Handler** → Parse SQS messages
3. **Dispatch Processor** → Get users from Employee Service
4. **Dispatch Processor** → Create assignments via Form Service API
5. **Result** → Logged and returned

## 🚀 Technologies

- **Python 3.13** - Programming language
- **requests** - HTTP client for API calls (synchronous, stable in Lambda)
- **boto3** - AWS SDK for SQS
- **Pydantic V2** - Data validation for events
- **AWS Lambda** - Serverless execution environment
- **AWS SQS** - Message queue for events
- **AWS Cognito** - Authentication service for service-to-service auth

## 🎯 Features

- ✅ **Event-Driven**: Processes SQS events asynchronously
- ✅ **Multi-tenant Support**: Tenant-aware processing
- ✅ **Automatic Pagination**: Retrieves all users from Employee Service regardless of count
- ✅ **Optimized Batch Processing**: Creates assignments in large batches (up to 1000 users per call)
- ✅ **Connection Pooling**: Reuses HTTP connections for better performance
- ✅ **Duplicate Handling**: Automatically handles duplicate assignments (idempotent)
- ✅ **Error Handling**: Comprehensive error handling with retries
- ✅ **Efficient Logging**: Optimized logging with argument formatting (only interpolates when needed)
- ✅ **Cognito Authentication**: Secure service-to-service authentication
- ✅ **No Database**: Stateless worker, communicates via APIs only
- ✅ **VPC Support**: Can be deployed in VPC for private network access

## 🏃‍♂️ Quick Start

### Prerequisites

- Python 3.11+ (3.13 recommended)
- AWS Account with SQS and Lambda access
- Access to Employee Service API
- Access to Form Service internal API

### Installation

```bash
# Clone repository
git clone <repository-url>
cd form-worker-service

# Setup development environment (recommended)
make setup

# Or manually:
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[local,test,all]"

# Install pre-commit hooks
pre-commit install
```

### Configuration

Copy `env.example` to `.env` and configure:

```bash
cp env.example .env
```

Key environment variables:

```bash
# SQS Configuration
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/form-dispatch-events-qa

# External Services
FORM_SERVICE_URL=http://localhost:8002
EMPLOYEE_SERVICE_URL=http://localhost:8001

# Internal API Authentication
INTERNAL_API_KEY=your-internal-api-key-here

# AWS Configuration
AWS_REGION=us-east-1
```

### Local Development

For local testing, you can simulate SQS events:

```python
import json

# Example SQS event structure with new event format
event = {
    "Records": [
        {
            "messageId": "test-message-id",
            "body": json.dumps({
                "event_type": "dispatch.created",
                "event_version": "1.0",
                "timestamp": "2025-12-22T16:30:00Z",
                "dispatch_id": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_id": "henko-main",
                "form_id": "660e8400-e29b-41d4-a716-446655440001",
                "role_ids": ["770e8400-e29b-41d4-a716-446655440002"],
                "area_ids": ["880e8400-e29b-41d4-a716-446655440003"],
                "expires_at": "2026-01-01T23:59:59Z",
                "created_by": "990e8400-e29b-41d4-a716-446655440004",
                "created_at": "2025-12-22T16:30:00Z"
            })
        }
    ]
}

# Test handler
from lambda_handler import lambda_handler
result = lambda_handler(event, None)
```


## 📦 Deployment

### Despliegue con Terraform Cloud

El servicio se despliega usando Terraform Cloud. El script de despliegue automatiza todo el proceso.

#### Prerrequisitos

1. **Terraform CLI** instalado
2. **GitHub CLI** (`gh`) instalado y autenticado
3. **Token de Terraform Cloud** configurado como variable de entorno:
   ```bash
   export TF_TOKEN_app_terraform_io="tu_token_de_terraform_cloud"
   ```
4. **Variables configuradas en GitHub**:
   - Variables públicas en GitHub Variables
   - Secrets sensibles en GitHub Secrets (ej: `COGNITO_SYSTEM_PASSWORD`)

#### Comando de Despliegue

```bash
# Para QA
export TF_TOKEN_app_terraform_io="tu_token_de_terraform_cloud"
./scripts/deploy-terraform-cloud.sh qa

# Para otros ambientes
./scripts/deploy-terraform-cloud.sh staging
./scripts/deploy-terraform-cloud.sh prod
```

**Nota sobre Variables:**
- Todas las variables (incluyendo `COGNITO_SYSTEM_PASSWORD`) están configuradas en GitHub Variables
- El script las obtiene automáticamente desde GitHub
- No necesitas exportar variables manualmente antes de ejecutar el script

#### Qué hace el Script

1. ✅ Verifica dependencias (Terraform, GitHub CLI, Python)
2. 📥 Obtiene variables desde GitHub Variables/Secrets
3. 📦 Crea Lambda Layer con dependencias Python
4. 📦 Crea Lambda Code Package con tu código
5. 📋 Ejecuta `terraform plan` para validar cambios
6. ⚠️ Pide confirmación antes de aplicar
7. 🚀 Ejecuta `terraform apply` para crear/actualizar recursos
8. 📊 Muestra información del despliegue (ARNs, URLs, etc.)

#### Recursos Desplegados

- **SQS Queue**: Cola principal para eventos de dispatch
- **SQS DLQ**: Dead Letter Queue para mensajes fallidos
- **Lambda Function**: Función que procesa los eventos
- **CloudWatch Log Group**: Logs de la función Lambda
- **IAM Roles & Policies**: Permisos necesarios
- **Event Source Mapping**: Conexión SQS → Lambda

**Lambda Configuration:**
- Runtime: Python 3.13
- Handler: `lambda_handler.lambda_handler`
- Timeout: 15 minutes (for large batches)
- Memory: 512 MB (adjust based on batch size)
- VPC: Deployed in private subnet with security group for outbound HTTPS/HTTP

**SQS Trigger:**
- Event Source: SQS Queue
- Batch Size: 10 messages
- Maximum Batching Window: 5 seconds

### Terraform

See `terraform/` directory for infrastructure as code.

## 🔄 Processing Flow

### 1. SQS Event Received

Lambda receives SQS event with one or more messages:

```json
{
  "Records": [
    {
      "messageId": "...",
      "body": "{\"event_type\":\"dispatch.created\",\"dispatch_id\":\"...\",...}"
    }
  ]
}
```

### 2. Parse Message

Each message body is parsed into a `DispatchEvent`. The message format from form-service:

```json
{
  "event_type": "dispatch.created",
  "event_version": "1.0",
  "timestamp": "2025-12-22T16:30:00Z",
  "dispatch_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "henko-main",
  "form_id": "660e8400-e29b-41d4-a716-446655440001",
  "role_ids": ["770e8400-e29b-41d4-a716-446655440002"],
  "area_ids": ["880e8400-e29b-41d4-a716-446655440003"],
  "expires_at": "2026-01-01T23:59:59Z",
  "created_by": "990e8400-e29b-41d4-a716-446655440004",
  "created_at": "2025-12-22T16:30:00Z"
}
```

The model supports both the new event format (with `event_type`, `event_version`, `timestamp`, `form_id`) and legacy format for backward compatibility.

### 3. Get Users

Calls Employee Service API to get user IDs with automatic pagination:

```
GET /employees/?tenant_id=...&positions_in=...&departments_in=...&skip=0&limit=100
→ Returns paginated response with all users across all pages
→ Automatically paginates to retrieve all users
```

**Features**:
- Automatic pagination: Retrieves all users regardless of total count
- Supports filtering by `role_ids` (mapped to `positions_in`) and `area_ids` (mapped to `departments_in`)
- If `role_ids` and `area_ids` are `None`, retrieves ALL users for the tenant

### 4. Create Assignments

Creates assignments in optimized batches:

```
POST /assignments
{
  "dispatch_id": "...",
  "user_ids": ["user-id-1", "user-id-2", ...],
  "expires_at": "..."
}
→ Creates assignments in Form Service
→ Automatically handles duplicates (on_conflict_do_nothing)
```

**Features**:
- Optimized batches: Up to 1000 users per API call (configurable)
- Single API call for ≤1000 users (most efficient)
- Automatic duplicate handling: Existing assignments are ignored (no errors)
- Connection pooling: Reuses HTTP connections for better performance

### 5. Return Result

Returns processing statistics:

```json
{
  "processed": 1,
  "successful": 1,
  "failed": 0,
  "results": [
    {
      "message_id": "...",
      "status": "success",
      "result": {
        "dispatch_id": "...",
        "users_found": 150,
        "assignments_created": 150,
        "batches_processed": 2,
        "status": "completed"
      }
    }
  ]
}
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SQS_QUEUE_URL` | SQS queue URL | Required |
| `FORM_SERVICE_URL` | Form Service API URL | `http://localhost:8002` |
| `EMPLOYEE_SERVICE_URL` | Employee Service API URL | `http://localhost:8001` |
| `COGNITO_USER_POOL_ID` | AWS Cognito User Pool ID | Required |
| `COGNITO_CLIENT_ID` | AWS Cognito Client ID | Required |
| `COGNITO_CLIENT_SECRET` | AWS Cognito Client Secret | Optional |
| `COGNITO_SYSTEM_USERNAME` | System user username for authentication | Required |
| `COGNITO_SYSTEM_PASSWORD` | System user password | Required |
| `AWS_REGION` | AWS region | `us-east-1` |
| `ASSIGNMENT_BATCH_SIZE` | Number of assignments per batch | `100` |
| `MAX_RETRIES` | Maximum retry attempts | `3` |
| `RETRY_DELAY_SECONDS` | Delay between retries | `5` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Batch Processing

Assignments are created in optimized batches:

- **Maximum Batch Size**: 1000 users per batch (optimized for efficiency)
- **Configurable**: Via `ASSIGNMENT_BATCH_SIZE` environment variable
- **Single Call Optimization**: If users ≤ batch_size, makes single API call
- **Automatic Splitting**: Users are automatically split into batches only if needed
- **Duplicate Handling**: Endpoint automatically ignores duplicate assignments (same dispatch_id + user_id)

## 🛡️ Error Handling

### Retry Strategy

- **Transient Errors**: Automatically retried by SQS (up to 3 times)
- **Validation Errors**: Not retried (permanent failure)
- **Service Errors**: Retried (Employee Service, Form Service)

### Dead Letter Queue (DLQ)

Failed messages after max retries are sent to DLQ for manual review.

## 📊 Monitoring

### CloudWatch Logs

All processing is logged to CloudWatch with optimized logging:

**INFO Level** (Production):
- Lambda handler invoked
- Processing dispatch (dispatch_id, tenant_id)
- Users found count
- Batch processing (only if multiple batches)
- Assignments created
- Processing complete summary

**DEBUG Level** (Troubleshooting):
- Detailed HTTP request/response information
- Pagination details
- Assignment IDs
- Full error stack traces

**Logging Best Practices**:
- Uses argument formatting (`logger.info("Message: %s", value)`) for efficiency
- Only interpolates strings when log level is enabled
- Minimal verbosity in production (INFO level)
- Detailed debugging available via DEBUG level

### Metrics

Key metrics to monitor:

- Messages processed per minute
- Success rate
- Average processing time
- Error rate by type

## 🔐 Security

- **Cognito Authentication**: Uses JWT tokens from AWS Cognito for service-to-service authentication
- **System User**: Dedicated system user with username/password stored in Secrets Manager
- **Token Management**: Automatic token refresh and caching to minimize authentication calls
- **Tenant Isolation**: All operations include tenant ID
- **No Database Access**: Worker has no direct database access
- **IAM Roles**: Lambda uses IAM role for AWS service access
- **SQS Access Control**: SQS queue access is controlled via IAM roles (no queue policy). Only resources with explicit IAM permissions can publish messages.

## 📝 Development Guidelines

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings
- Run `black`, `isort`, `flake8` before committing

### Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality. The hooks automatically run:
- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **bandit**: Security scanning
- **pre-commit hooks**: Basic file checks (trailing whitespace, YAML validation, etc.)

#### Setup Pre-commit

```bash
# Install pre-commit hooks (automatically done in make setup)
make pre-commit-install

# Or manually
pre-commit install
```

#### Usage

Pre-commit hooks run automatically on `git commit`. To run manually:

```bash
# Run on all files
make pre-commit-run

# Or manually
pre-commit run --all-files

# Update hooks to latest versions
make pre-commit-update
```


## 🤝 Contributing

1. Create feature branch
2. Make changes
3. Run quality checks (`make quality`)
4. Ensure pre-commit hooks pass
5. Submit pull request

## 📄 License

MIT License

## 🔗 Related Services

- **form-service**: Main Form Service API
- **employee-service**: Employee management service

## 🔍 Troubleshooting

### Common Issues

#### Lambda Timeout
**Symptom**: Lambda function times out before completing processing.

**Solutions**:
- Increase Lambda timeout (up to 15 minutes)
- Reduce `ASSIGNMENT_BATCH_SIZE` to process smaller batches
- Check Employee Service and Form Service response times
- Monitor CloudWatch logs for slow operations

#### No Users Found
**Symptom**: `users_found: 0` in processing results.

**Possible Causes**:
- No users match the role/area filters
- Employee Service API returned empty result
- Tenant ID mismatch
- Pagination issue (unlikely, as pagination is automatic)

**Solutions**:
- Verify role_ids and area_ids are correct
- If both are `None`, should return ALL users for tenant
- Check Employee Service logs
- Verify tenant_id matches Employee Service tenant
- Enable DEBUG logging to see pagination details

#### Form Service API Errors
**Symptom**: `form_service_error` in processing results.

**Possible Causes**:
- Cognito authentication failure
- Form Service unavailable
- Invalid dispatch_id
- Rate limiting
- Network connectivity issues (if in VPC)

**Solutions**:
- Verify Cognito credentials are correct
- Check Cognito User Pool configuration
- Check Form Service health
- Verify dispatch exists in Form Service
- Check rate limits
- If in VPC, verify security group allows outbound HTTPS
- Check VPC endpoints and NAT Gateway configuration

#### SQS Messages Not Processing
**Symptom**: Messages remain in SQS queue.

**Possible Causes**:
- Lambda function not triggered
- Lambda execution errors
- SQS trigger misconfigured

**Solutions**:
- Check Lambda function logs in CloudWatch
- Verify SQS trigger configuration
- Check Lambda IAM permissions
- Verify queue URL is correct

### Debugging

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
```

Check CloudWatch logs for:
- Message processing start/end
- User counts from Employee Service
- Batch processing progress
- API call failures
- Error stack traces

## 📋 Example Scenarios

### Scenario 1: Small Dispatch (50 users)

```
1. SQS message received with dispatch_id
2. Employee Service returns 50 user IDs
3. Single batch created (50 < batch_size)
4. Form Service creates 50 assignments
5. Processing completes in ~5 seconds
```

### Scenario 2: Large Dispatch (500 users)

```
1. SQS message received with dispatch_id
2. Employee Service returns 500 user IDs (with pagination if needed)
3. Single batch created (500 < 1000 max batch size)
4. Form Service creates assignments in 1 API call
5. Processing completes in ~5-10 seconds
```

### Scenario 2b: Very Large Dispatch (2000 users)

```
1. SQS message received with dispatch_id
2. Employee Service returns 2000 user IDs (with pagination)
3. Split into 2 batches (2000 / 1000 = 2)
4. Form Service creates assignments in 2 API calls
5. Processing completes in ~15-20 seconds
```

### Scenario 3: No Users Found

```
1. SQS message received with dispatch_id
2. Employee Service returns empty list
3. Processing completes with status "completed_no_users"
4. No assignments created (expected behavior)
```

### Scenario 4: Service Unavailable

```
1. SQS message received
2. Employee Service returns 500 error
3. Worker raises EmployeeServiceError
4. Lambda raises exception
5. SQS retries message (up to 3 times)
6. After max retries, message goes to DLQ
```

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    form-service                            │
│                  (API REST)                               │
│                                                            │
│  POST /dispatches                                          │
│  → Creates dispatch                                         │
│  → Publishes to SQS                                        │
└────────────┬──────────────────────────────────────────────┘
             │
             │ Publishes event
             ↓
┌─────────────────────────────────────────────────────────────┐
│                    AWS SQS                                  │
│         form-dispatch-events-{env}                          │
│                                                            │
│  Message:                                                  │
│  {                                                          │
│    "dispatch_id": "uuid",                                  │
│    "tenant_id": "string",                                  │
│    "role_ids": ["uuid"],                                   │
│    "area_ids": ["uuid"]                                    │
│  }                                                          │
└────────────┬──────────────────────────────────────────────┘
             │
             │ Triggers Lambda
             ↓
┌─────────────────────────────────────────────────────────────┐
│         form-worker-service (Lambda)                       │
│                                                            │
│  1. Parse SQS message                                       │
│  2. Get users from Employee Service                         │
│  3. Split into batches                                      │
│  4. Create assignments via Form Service                      │
│  5. Return results                                          │
└────────────┬──────────────────────────────────────────────┘
             │
             │ HTTP Calls
             ↓
┌─────────────────────────────────────────────────────────────┐
│              External Services                              │
│                                                            │
│  Employee Service: GET /employees/ (with pagination)      │
│  Form Service: POST /assignments (optimized batches)      │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 Event Flow Details

### Complete Processing Flow

```
┌─────────────┐
│ SQS Event   │
└──────┬──────┘
       │
       ↓
┌──────────────────────┐
│ Lambda Handler       │
│ - Parse SQS records  │
│ - Extract messages  │
└──────┬───────────────┘
       │
       ↓
┌──────────────────────┐
│ Dispatch Processor   │
│                      │
│ 1. Parse message     │
│    → DispatchEvent   │
└──────┬───────────────┘
       │
       ↓
┌──────────────────────┐
│ Employee Service     │
│ GET /employees/      │
│ → Paginates all users│
│ → Returns all user_ids│
└──────┬───────────────┘
       │
       ↓
┌──────────────────────┐
│ Batch Processing     │
│ Optimize batches     │
│ → Up to 1000 per call│
│ → Single call if ≤1000│
└──────┬───────────────┘
       │
       ↓
┌──────────────────────┐
│ Form Service         │
│ POST /assignments    │
│ → Creates assignments│
│ → Handles duplicates │
└──────┬───────────────┘
       │
       ↓
┌──────────────────────┐
│ Return Results       │
│ - Statistics         │
│ - Status            │
└──────────────────────┘
```

## 📊 Performance Considerations

### Lambda Configuration

**Recommended Settings**:
- **Memory**: 512 MB - 1024 MB (adjust based on batch size)
- **Timeout**: 15 minutes (maximum)
- **Concurrency**: Unlimited (SQS manages concurrency)

### Performance Optimizations

**HTTP Connection Pooling**:
- Uses `requests.Session` with connection pooling
- Reuses TCP connections between requests
- Reduces connection overhead, especially in pagination
- Configured with `pool_connections=1` and `pool_maxsize=10`

**Batch Size Optimization**:
- **Maximum**: 1000 users per batch (optimal for most cases)
- **Single Call**: If users ≤ 1000, makes single API call (most efficient)
- **Multiple Batches**: Only splits if users > 1000
- **Factors**: Lambda timeout, API rate limits, payload size

**Pagination**:
- Automatically paginates through all Employee Service results
- No manual pagination needed
- Handles both new format (`employees` key) and legacy format (`items` key)

**Duplicate Handling**:
- Form Service endpoint uses `on_conflict_do_nothing`
- Duplicate assignments (same dispatch_id + user_id) are automatically ignored
- No errors thrown for duplicates
- Returns all assignments (new and existing)

### Monitoring Metrics

Key CloudWatch metrics to track:

- **Invocation Count**: Number of Lambda invocations
- **Duration**: Average execution time
- **Error Rate**: Percentage of failed invocations
- **Throttles**: Number of throttled invocations
- **SQS Messages Visible**: Messages waiting in queue
- **SQS Messages In Flight**: Messages being processed

## 🔐 Security Best Practices

### Cognito Configuration

- Store `COGNITO_SYSTEM_PASSWORD` in AWS Secrets Manager
- Use dedicated system user for worker authentication
- Rotate system user password regularly
- Use different credentials per environment
- Never commit credentials to repository

### IAM Permissions

**Lambda Worker Function** needs:
- `sqs:ReceiveMessage` - Read from SQS
- `sqs:DeleteMessage` - Delete processed messages
- `sqs:GetQueueAttributes` - Get queue information
- `logs:CreateLogGroup` - Create CloudWatch log groups
- `logs:CreateLogStream` - Create log streams
- `logs:PutLogEvents` - Write logs
- `secretsmanager:GetSecretValue` - Access Cognito password from Secrets Manager

**Form Service** (publisher) needs:
- `sqs:SendMessage` - Publish messages to SQS queue
- `sqs:GetQueueAttributes` - Optional: Validate queue exists

**Note**: SQS queue has no queue policy. Access is controlled exclusively via IAM roles.

### Network Security

- Use VPC endpoints for AWS services (if in VPC)
- Use HTTPS for all external API calls
- Validate SSL certificates
- Don't expose internal endpoints publicly

## 🚀 Deployment Checklist

Before deploying to production:

- [ ] Environment variables configured
- [ ] API keys stored in Secrets Manager
- [ ] SQS queue created and configured
- [ ] Lambda function deployed
- [ ] SQS trigger configured
- [ ] Dead Letter Queue configured
- [ ] CloudWatch alarms set up
- [ ] IAM roles and permissions verified
- [ ] Documentation updated

## 📚 Additional Resources

- [Architecture Design](./ARCHITECTURE_DESIGN.md)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS SQS Documentation](https://docs.aws.amazon.com/sqs/)
- [requests Documentation](https://requests.readthedocs.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
