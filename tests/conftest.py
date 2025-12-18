"""
Pytest configuration and shared fixtures for tests.
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.events import DispatchEvent


@pytest.fixture
def sample_dispatch_event() -> DispatchEvent:
    """Create a sample dispatch event for testing."""
    return DispatchEvent(
        dispatch_id=uuid4(),
        tenant_id="henko-main",
        role_ids=[uuid4()],
        area_ids=[uuid4()],
        expires_at=datetime(2025, 12, 31, 23, 59, 59),
        created_at=datetime(2025, 12, 15, 12, 0, 0),
        created_by=str(uuid4()),
    )


@pytest.fixture
def sample_sqs_event() -> dict[str, Any]:
    """Create a sample SQS event for testing."""
    dispatch_id = uuid4()
    return {
        "Records": [
            {
                "messageId": "test-message-id-1",
                "receiptHandle": "test-receipt-handle-1",
                "body": json.dumps({
                    "dispatch_id": str(dispatch_id),
                    "tenant_id": "henko-main",
                    "role_ids": [str(uuid4())],
                    "area_ids": [str(uuid4())],
                    "expires_at": "2025-12-31T23:59:59Z",
                    "created_at": "2025-12-15T12:00:00Z",
                    "created_by": str(uuid4()),
                }),
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1523232000000",
                },
                "messageAttributes": {},
                "md5OfBody": "test-md5",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:form-dispatch-events-qa",
                "awsRegion": "us-east-1",
            }
        ]
    }


@pytest.fixture
def mock_employee_service():
    """Create a mock Employee Service client."""
    service = AsyncMock()
    service.get_users_by_role_and_area = AsyncMock(
        return_value=["user-id-1", "user-id-2", "user-id-3"]
    )
    service.close = AsyncMock()
    return service


@pytest.fixture
def mock_form_service_client():
    """Create a mock Form Service client."""
    client = AsyncMock()
    client.create_assignments = AsyncMock(
        return_value={
            "assignments": [
                {"id": "assignment-1", "user_id": "user-id-1"},
                {"id": "assignment-2", "user_id": "user-id-2"},
            ],
            "total_created": 2,
        }
    )
    client.close = AsyncMock()
    return client
