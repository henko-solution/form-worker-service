"""
Unit tests for dispatch processor.
"""

import pytest
from uuid import uuid4

from app.exceptions import EmployeeServiceError, FormServiceError, ValidationError
from app.models.events import DispatchEvent
from app.workers.dispatch_processor import DispatchProcessor


@pytest.mark.asyncio
async def test_parse_sqs_message_valid(mock_employee_service, mock_form_service_client):
    """Test parsing valid SQS message."""
    processor = DispatchProcessor(
        employee_service=mock_employee_service,
        form_service_client=mock_form_service_client,
    )

    message_body = '{"dispatch_id":"550e8400-e29b-41d4-a716-446655440000","tenant_id":"henko-main","role_ids":["550e8400-e29b-41d4-a716-446655440001"],"area_ids":[],"expires_at":"2025-12-31T23:59:59Z","created_at":"2025-12-15T12:00:00Z","created_by":"user-uuid"}'

    event = processor.parse_sqs_message(message_body)

    assert isinstance(event, DispatchEvent)
    assert event.tenant_id == "henko-main"
    assert len(event.role_ids) == 1


@pytest.mark.asyncio
async def test_parse_sqs_message_invalid_json(mock_employee_service, mock_form_service_client):
    """Test parsing invalid JSON."""
    processor = DispatchProcessor(
        employee_service=mock_employee_service,
        form_service_client=mock_form_service_client,
    )

    with pytest.raises(ValidationError):
        processor.parse_sqs_message("invalid json")


@pytest.mark.asyncio
async def test_get_user_ids_success(mock_employee_service, mock_form_service_client):
    """Test getting user IDs from Employee Service."""
    processor = DispatchProcessor(
        employee_service=mock_employee_service,
        form_service_client=mock_form_service_client,
    )

    user_ids = await processor.get_user_ids(
        tenant_id="henko-main",
        role_ids=[uuid4()],
        area_ids=[uuid4()],
    )

    assert len(user_ids) == 3
    assert user_ids == ["user-id-1", "user-id-2", "user-id-3"]
    mock_employee_service.get_users_by_role_and_area.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_ids_employee_service_error(mock_employee_service, mock_form_service_client):
    """Test handling Employee Service error."""
    mock_employee_service.get_users_by_role_and_area.side_effect = EmployeeServiceError(
        "Service unavailable", "service_error"
    )

    processor = DispatchProcessor(
        employee_service=mock_employee_service,
        form_service_client=mock_form_service_client,
    )

    with pytest.raises(EmployeeServiceError):
        await processor.get_user_ids(
            tenant_id="henko-main",
            role_ids=[uuid4()],
        )


@pytest.mark.asyncio
async def test_split_into_batches(mock_employee_service, mock_form_service_client):
    """Test splitting users into batches."""
    processor = DispatchProcessor(
        employee_service=mock_employee_service,
        form_service_client=mock_form_service_client,
    )

    user_ids = [f"user-{i}" for i in range(250)]
    batches = processor.split_into_batches(user_ids, batch_size=100)

    assert len(batches) == 3
    assert len(batches[0]) == 100
    assert len(batches[1]) == 100
    assert len(batches[2]) == 50


@pytest.mark.asyncio
async def test_process_dispatch_event_success(
    sample_dispatch_event, mock_employee_service, mock_form_service_client
):
    """Test successful dispatch event processing."""
    processor = DispatchProcessor(
        employee_service=mock_employee_service,
        form_service_client=mock_form_service_client,
    )

    result = await processor.process_dispatch_event(sample_dispatch_event)

    assert result["status"] == "completed"
    assert result["users_found"] == 3
    assert result["assignments_created"] == 2
    assert result["batches_processed"] == 1


@pytest.mark.asyncio
async def test_process_dispatch_event_no_users(
    sample_dispatch_event, mock_employee_service, mock_form_service_client
):
    """Test processing when no users are found."""
    mock_employee_service.get_users_by_role_and_area.return_value = []

    processor = DispatchProcessor(
        employee_service=mock_employee_service,
        form_service_client=mock_form_service_client,
    )

    result = await processor.process_dispatch_event(sample_dispatch_event)

    assert result["status"] == "completed_no_users"
    assert result["users_found"] == 0
    assert result["assignments_created"] == 0


@pytest.mark.asyncio
async def test_process_dispatch_event_form_service_error(
    sample_dispatch_event, mock_employee_service, mock_form_service_client
):
    """Test handling Form Service error."""
    mock_form_service_client.create_assignments.side_effect = FormServiceError(
        "Service unavailable", "service_error"
    )

    processor = DispatchProcessor(
        employee_service=mock_employee_service,
        form_service_client=mock_form_service_client,
    )

    with pytest.raises(FormServiceError):
        await processor.process_dispatch_event(sample_dispatch_event)
