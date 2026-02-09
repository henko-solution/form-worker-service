# Henko Form Worker Service

Asynchronous worker service for processing form dispatch events via SQS. This service consumes messages from AWS SQS, retrieves users from Employee Service, and creates assignments via the Form Service API.

## 🏗️ Architecture

This service implements an **Event-Driven Worker Architecture** with the following structure:

- **Lambda Handler**: Entry point for SQS-triggered Lambda function (event routing)
- **Workers**: Event processing logic (one processor per event type)
- **Services**: External API clients (Employee Service, Form Service)
- **Models**: Pydantic models for event validation

### 📁 Project Structure

```
form-worker-service/
├── lambda_handler.py              # Lambda handler entry point (event routing)
├── app/
│   ├── workers/
│   │   ├── dispatch_processor.py           # dispatch.created processing logic
│   │   └── dispatch_completed_processor.py # dispatch.completed processing logic
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

**dispatch.created** (assignment creation):

1. **SQS Event** → Lambda Handler
2. **Lambda Handler** → Route by `event_type`
3. **Dispatch Processor** → Get users from Employee Service
4. **Dispatch Processor** → Create assignments via Form Service API
5. **Result** → Logged and returned

**dispatch.completed** (candidate evaluation):

1. **SQS Event** → Lambda Handler
2. **Lambda Handler** → Route by `event_type`
3. **Dispatch Completed Processor** → Get employee vacancies (Employee Service)
4. **For each vacancy:**
   - Calculate dimensions (Form Service Analytics)
   - Save dimension evaluations (Employee Service)
   - Calculate skills (Form Service Analytics)
   - Save skill evaluations (Employee Service)
5. **Result** → Logged and returned

## 🚀 Technologies

- **Python 3.14** - Programming language
- **Pydantic V2** - Data validation and models (events, config)
- **pydantic-settings** - Config from environment variables
- **requests** - HTTP client for Employee Service and Form Service
- **AWS Lambda** - Serverless execution (runtime incluye boto3 para Cognito/SQS)
- **AWS SQS** - Message queue for events
- **AWS Cognito** - Authentication service for service-to-service auth

## 🎯 Features

- ✅ **Event-Driven**: Processes SQS events asynchronously
- ✅ **Multi-Event Routing**: Routes `dispatch.created` and `dispatch.completed` to dedicated processors
- ✅ **Candidate Evaluation Pipeline**: Calculates and persists dimensions, skills, and score on dispatch completion
- ✅ **Multi-tenant Support**: Tenant-aware processing
- ✅ **Automatic Pagination**: Retrieves all users from Employee Service regardless of count
- ✅ **Optimized Batch Processing**: Creates assignments in large batches (up to 1000 users per call)
- ✅ **Connection Pooling**: Reuses HTTP connections for better performance
- ✅ **Duplicate Handling**: Automatically handles duplicate assignments (idempotent)
- ✅ **Error Handling**: Comprehensive error handling with retries
- ✅ **Efficient Logging**: Optimized logging with argument formatting (only interpolates when needed)
- ✅ **Cognito Authentication**: Secure service-to-service authentication
- ✅ **No Database**: Stateless worker, communicates via APIs only
- ✅ **No VPC**: Lambda runs with default internet access for HTTP calls to Form/Employee services

## 🏃‍♂️ Quick Start

### Prerequisites

- Python 3.11+ (3.14 recommended)
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
- Runtime: Python 3.14
- Handler: `lambda_handler.lambda_handler`
- Timeout: 15 minutes (for large batches)
- Memory: 512 MB (adjust based on batch size)
- No VPC: Lambda uses default internet access for HTTP APIs

**SQS Trigger:**
- Event Source: SQS Queue
- Batch Size: 10 messages
- Maximum Batching Window: 5 seconds
- Filter Pattern: `event_type` in `["dispatch.created", "dispatch.completed"]`

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
GET /employees/?positions_in=...&departments_in=...&page=1&page_size=100
Headers: X-Tenant-ID: <tenant_id>, Authorization: Bearer <token>
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

## 🔄 dispatch.completed Processing Flow

### 1. SQS Event Received

Lambda receives an SQS event with `event_type: "dispatch.completed"`:

```json
{
  "Records": [
    {
      "messageId": "...",
      "body": "{\"event_type\":\"dispatch.completed\",\"dispatch_id\":\"...\",\"employee_id\":\"...\",\"vacancy_id\":\"...\",\"candidate_id\":\"...\",\"position_id\":\"...\",...}"
    }
  ]
}
```

### 2. Parse Message

The message body is parsed into a `DispatchCompletedEvent`:

```json
{
  "event_type": "dispatch.completed",
  "event_version": "1.0",
  "timestamp": "2026-02-08T12:00:00Z",
  "dispatch_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "henko-main",
  "form_id": "660e8400-e29b-41d4-a716-446655440001",
  "employee_id": "987fcdeb-51a2-43d7-9876-543210987654",
  "created_at": "2026-02-08T12:00:00Z",
  "created_by": "987fcdeb-51a2-43d7-9876-543210987654"
}
```

### 3. Evaluation Pipeline

The processor first retrieves all vacancies for the employee, then runs the following steps for each vacancy:

| Step | Action | Service | Endpoint |
|------|--------|---------|----------|
| a | Get employee vacancies | Employee Service | `GET /employees/{employee_id}/vacancies` |
| **For each vacancy:** | | | |
| b | Calculate dimensions | Form Service | `GET /analytics/employees/{id}/positions/{id}/dimensions` |
| c | Save dimension evaluations | Employee Service | `POST /vacancies/{id}/candidates/{id}/dimensions/{id}` |
| d | Calculate skills | Form Service | `GET /analytics/employees/{id}/skills` |
| e | Save skill evaluations | Employee Service | `POST /vacancies/{id}/candidates/{id}/skills/{id}` |
| f | Get weighted score | Form Service | `GET /analytics/employees/{id}/positions/{id}/score` |
| g | Update candidate score | Employee Service | `PATCH /vacancies/{id}/candidates/{id}` |

**Notes:**
- The vacancy list contains `id` (vacancy_id) and `position_id` for each entry.
- Vacancies without `position_id` are skipped.
- Dimensions and skills with `null` values are skipped (insufficient data).
- Score from Form Service is 0-1 (float); it is converted to 0-100 (int) for Employee Service. If score is `null`, the update is skipped.
- All evaluations are processed for all vacancies the employee belongs to.

### 4. Return Result

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
        "event_type": "dispatch.completed",
        "employee_id": "...",
        "vacancies_processed": 2,
        "total_dimensions_saved": 10,
        "total_skills_saved": 16,
        "total_scores_updated": 2,
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
- Network connectivity issues

**Solutions**:
- Verify Cognito credentials are correct
- Check Cognito User Pool configuration
- Check Form Service health
- Verify dispatch exists in Form Service
- Check rate limits
- Verify Lambda has internet access (no VPC; public endpoints via HTTPS)

#### SQS Messages Not Processing
**Symptom**: Messages remain in SQS queue or Lambda never runs.

**Possible Causes**:
- Form-service sends to a different queue URL (wrong env or old name)
- Lambda event source mapping disabled or pointing to wrong queue
- Message body validation fails (e.g. schema change in form-service)

**Solutions**:
- **Queue URL**: In form-service, `SQS_DISPATCH_EVENTS_QUEUE_URL` must be the URL of this worker's queue. Queue name pattern: `form-worker-service-{env}-dispatch-events` (e.g. `form-worker-service-qa-dispatch-events` for QA). Get the URL from Terraform output `sqs_queue_url` or AWS Console.
- **Event source mapping**: In AWS Lambda → this function → Configuration → Triggers, confirm SQS trigger is enabled and linked to the same queue.
- **Message format**: This worker expects the same JSON as form-service `DispatchCreatedEvent` (dispatch_id, tenant_id, form_id, role_ids, area_ids, user_ids, expires_at, created_at, created_by optional). If form-service changed the payload, validation may fail; check CloudWatch logs for validation errors.
- Check Lambda function logs in CloudWatch for invocation and parsing errors
- Verify Lambda IAM permissions (SQS ReceiveMessage, DeleteMessage, etc.)

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

### Scenario 4: Dispatch Completed (Candidate Evaluation)

```
1. SQS message received with event_type=dispatch.completed
2. Employee Service returns 2 vacancies for the employee
3. For vacancy 1:
   - Form Service Analytics calculates 5 dimensions
   - Employee Service saves 5 dimension evaluations
   - Form Service Analytics calculates 4 skills
   - Employee Service saves 4 skill evaluations
   - Form Service Analytics returns score; Employee Service updates candidate score
4. For vacancy 2:
   - Form Service Analytics calculates 5 dimensions
   - Employee Service saves 5 dimension evaluations
   - Form Service Analytics calculates 4 skills
   - Employee Service saves 4 skill evaluations
   - Form Service Analytics returns score; Employee Service updates candidate score
5. Processing completes in ~5-8 seconds
   Result: 2 vacancies, 10 dimensions, 8 skills, 2 scores updated
```

### Scenario 5: Service Unavailable

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
│ - Route by event_type│
└──────┬───────┬───────┘
       │       │
       │       └──── dispatch.completed ──┐
       │                                  ↓
       │ dispatch.created   ┌────────────────────────────┐
       ↓                    │ DispatchCompletedProcessor  │
┌──────────────────────┐    │                            │
│ Dispatch Processor   │    │ a) GET vacancies (Emp.)    │
│                      │    │ For each vacancy:          │
│ 1. Parse message     │    │   b) GET dimensions (Form) │
│    → DispatchEvent   │    │   c) POST dimensions (Emp.)│
└──────┬───────────────┘    │   d) GET skills (Form)     │
       │                    │   e) POST skills (Emp.)     │
       ↓                    └─────────────┬──────────────┘
┌──────────────────────┐                  │
│ Employee Service     │                  ↓
│ GET /employees/      │    ┌────────────────────────────┐
│ → Paginates all users│    │ Return Results             │
│ → Returns all user_ids│    │ - dimensions_saved         │
└──────┬───────────────┘    │ - skills_saved             │
       │                    │ - score                    │
       ↓                    └────────────────────────────┘
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
