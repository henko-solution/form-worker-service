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
app/
├── lambda_handler.py          # Lambda handler entry point
├── workers/
│   └── dispatch_processor.py  # Main dispatch processing logic
├── services/
│   ├── employee_service.py    # Employee Service API client (httpx)
│   └── form_service_client.py # Form Service API client (httpx)
├── models/
│   └── events.py              # Pydantic models for SQS events
├── exceptions.py              # Custom exceptions
└── config.py                  # Application configuration
```

### 🔄 Data Flow

1. **SQS Event** → Lambda Handler
2. **Lambda Handler** → Parse SQS messages
3. **Dispatch Processor** → Get users from Employee Service
4. **Dispatch Processor** → Create assignments via Form Service API
5. **Result** → Logged and returned

## 🚀 Technologies

- **Python 3.13** - Programming language
- **httpx** - Asynchronous HTTP client for API calls
- **boto3** - AWS SDK for SQS
- **Pydantic** - Data validation for events
- **AWS Lambda** - Serverless execution environment
- **AWS SQS** - Message queue for events

## 🎯 Features

- ✅ **Event-Driven**: Processes SQS events asynchronously
- ✅ **Multi-tenant Support**: Tenant-aware processing
- ✅ **Batch Processing**: Creates assignments in configurable batches
- ✅ **Error Handling**: Comprehensive error handling with retries
- ✅ **Logging**: Structured logging for observability
- ✅ **No Database**: Stateless worker, communicates via APIs only

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
# Example SQS event structure
event = {
    "Records": [
        {
            "messageId": "test-message-id",
            "body": json.dumps({
                "dispatch_id": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_id": "henko-main",
                "role_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "area_ids": [],
                "expires_at": "2025-12-31T23:59:59Z",
                "created_at": "2025-12-15T12:00:00Z",
                "created_by": "user-uuid"
            })
        }
    ]
}

# Test handler
from app.lambda_handler import lambda_handler
result = lambda_handler(event, None)
```

## 🧪 Testing

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit

# Integration tests only
pytest tests/integration

# With coverage
pytest --cov=app --cov-report=html
```

### Test Structure

- **Unit Tests** (`tests/unit/`): Test individual components
- **Integration Tests** (`tests/integration/`): Test full processing flow with mocks

## 📦 Deployment

### AWS Lambda Deployment

The service is deployed as an AWS Lambda function triggered by SQS.

**Lambda Configuration:**
- Runtime: Python 3.13
- Handler: `app.lambda_handler.lambda_handler`
- Timeout: 15 minutes (for large batches)
- Memory: 512 MB (adjust based on batch size)

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
      "body": "{\"dispatch_id\":\"...\",\"tenant_id\":\"...\",...}"
    }
  ]
}
```

### 2. Parse Message

Each message body is parsed into a `DispatchEvent`:

```python
DispatchEvent(
    dispatch_id=UUID("..."),
    tenant_id="henko-main",
    role_ids=[UUID("...")],
    area_ids=[UUID("...")],
    expires_at=datetime(...),
    created_at=datetime(...),
    created_by="user-uuid"
)
```

### 3. Get Users

Calls Employee Service API to get user IDs:

```
GET /api/v1/employees/users?tenant_id=...&role_ids=...&area_ids=...
→ Returns: ["user-id-1", "user-id-2", ...]
```

### 4. Create Assignments

Splits users into batches and creates assignments:

```
POST /internal/assignments
{
  "dispatch_id": "...",
  "user_ids": ["user-id-1", "user-id-2", ...],
  "expires_at": "..."
}
→ Creates assignments in Form Service
```

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
| `INTERNAL_API_KEY` | API key for Form Service internal endpoint | Required |
| `AWS_REGION` | AWS region | `us-east-1` |
| `ASSIGNMENT_BATCH_SIZE` | Number of assignments per batch | `100` |
| `MAX_RETRIES` | Maximum retry attempts | `3` |
| `RETRY_DELAY_SECONDS` | Delay between retries | `5` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Batch Processing

Assignments are created in batches to avoid timeouts and rate limits:

- **Default Batch Size**: 100 users per batch
- **Configurable**: Via `ASSIGNMENT_BATCH_SIZE` environment variable
- **Automatic Splitting**: Users are automatically split into batches

## 🛡️ Error Handling

### Retry Strategy

- **Transient Errors**: Automatically retried by SQS (up to 3 times)
- **Validation Errors**: Not retried (permanent failure)
- **Service Errors**: Retried (Employee Service, Form Service)

### Dead Letter Queue (DLQ)

Failed messages after max retries are sent to DLQ for manual review.

## 📊 Monitoring

### CloudWatch Logs

All processing is logged to CloudWatch:

- Message processing start/end
- User count from Employee Service
- Assignment creation results
- Errors and exceptions

### Metrics

Key metrics to monitor:

- Messages processed per minute
- Success rate
- Average processing time
- Error rate by type

## 🔐 Security

- **API Key Authentication**: Uses `X-API-Key` header for Form Service
- **Tenant Isolation**: All operations include tenant ID
- **No Database Access**: Worker has no direct database access
- **IAM Roles**: Lambda uses IAM role for AWS service access

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

### Testing

- Write unit tests for all components
- Mock external services in tests
- Test error scenarios
- Aim for >90% coverage

## 🤝 Contributing

1. Create feature branch
2. Make changes
3. Run tests and quality checks (`make quality`)
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

**Solutions**:
- Verify role_ids and area_ids are correct
- Check Employee Service logs
- Verify tenant_id matches Employee Service tenant

#### Form Service API Errors
**Symptom**: `form_service_error` in processing results.

**Possible Causes**:
- Invalid API key
- Form Service unavailable
- Invalid dispatch_id
- Rate limiting

**Solutions**:
- Verify `INTERNAL_API_KEY` is correct
- Check Form Service health
- Verify dispatch exists in Form Service
- Check rate limits

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
2. Employee Service returns 500 user IDs
3. Split into 5 batches (500 / 100 = 5)
4. Form Service creates assignments in 5 API calls
5. Processing completes in ~30 seconds
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
│  Employee Service: GET /api/v1/employees/users            │
│  Form Service: POST /internal/assignments                  │
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
│ GET /users           │
│ → Returns user_ids   │
└──────┬───────────────┘
       │
       ↓
┌──────────────────────┐
│ Batch Processing     │
│ Split users          │
│ → Batches of 100     │
└──────┬───────────────┘
       │
       ↓
┌──────────────────────┐
│ Form Service         │
│ POST /assignments    │
│ → Creates assignments│
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

### Batch Size Optimization

**Factors to Consider**:
- Lambda timeout limit (15 minutes)
- Form Service API rate limits
- Average processing time per user (~50ms)
- Network latency

**Calculation**:
```
Max users per batch = (Lambda timeout - overhead) / time_per_user
Example: (900s - 60s) / 0.05s = 16,800 users
But use 100-500 for safety margin
```

### Monitoring Metrics

Key CloudWatch metrics to track:

- **Invocation Count**: Number of Lambda invocations
- **Duration**: Average execution time
- **Error Rate**: Percentage of failed invocations
- **Throttles**: Number of throttled invocations
- **SQS Messages Visible**: Messages waiting in queue
- **SQS Messages In Flight**: Messages being processed

## 🔐 Security Best Practices

### API Key Management

- Store `INTERNAL_API_KEY` in AWS Secrets Manager
- Rotate API keys regularly
- Use different keys per environment
- Never commit API keys to repository

### IAM Permissions

Lambda function needs:
- `sqs:ReceiveMessage` - Read from SQS
- `sqs:DeleteMessage` - Delete processed messages
- `sqs:GetQueueAttributes` - Get queue information
- `logs:CreateLogGroup` - Create CloudWatch log groups
- `logs:CreateLogStream` - Create log streams
- `logs:PutLogEvents` - Write logs

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
- [ ] Tests passing
- [ ] Documentation updated

## 📚 Additional Resources

- [Architecture Design](./ARCHITECTURE_DESIGN.md)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS SQS Documentation](https://docs.aws.amazon.com/sqs/)
- [httpx Documentation](https://www.python-httpx.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
