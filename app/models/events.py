"""
Pydantic models for SQS events and messages.

This module defines the data structures for SQS messages
that trigger the worker to process form dispatches.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DispatchEvent(BaseModel):
    """
    Model for dispatch event received from SQS.

    This represents a form dispatch that needs to be processed
    to create assignments for users.

    Supports both legacy format and new event format with event_type,
    event_version, timestamp, and form_id.
    """

    # Event metadata (optional for backward compatibility)
    event_type: str | None = Field(
        None,
        description="Type of event (e.g., 'dispatch.created')",
    )
    event_version: str | None = Field(
        None,
        description="Version of the event schema",
    )
    timestamp: datetime | None = Field(
        None,
        description="Timestamp when the event was created",
    )

    # Dispatch data
    dispatch_id: UUID = Field(..., description="ID of the form dispatch")
    tenant_id: str = Field(..., description="Tenant ID for multi-tenant isolation")
    form_id: UUID | None = Field(
        None,
        description="ID of the form associated with the dispatch",
    )
    role_ids: list[UUID] | None = Field(
        default=None,
        description=(
            "List of role IDs to filter users. "
            "If None or empty, all users are included."
        ),
    )
    area_ids: list[UUID] | None = Field(
        default=None,
        description=(
            "List of area IDs to filter users. "
            "If None or empty, all users are included."
        ),
    )
    expires_at: datetime | None = Field(
        None,
        description="Optional expiration date for assignments",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the dispatch was created",
    )
    created_by: str = Field(..., description="User ID who created the dispatch")

    @field_validator("role_ids", "area_ids", mode="before")  # type: ignore[untyped-decorator]  # noqa: E501
    @classmethod
    def normalize_lists(cls, v: Any) -> Any:
        """
        Normalize None or empty lists to None.
        Empty lists or None values mean "all users" (no filtering).

        Args:
            v: Value to normalize (can be None, empty list, or list of UUIDs/strings)

        Returns:
            None if value is None or empty list,
            otherwise the list (will be converted to UUIDs)
        """
        if v is None:
            return None
        if isinstance(v, list):
            # Convert empty list to None (means "all users")
            if len(v) == 0:
                return None
            # Non-empty list will be validated and converted to UUIDs by Pydantic
            return v
        # If it's not None and not a list, let Pydantic handle the error
        return v

    @field_validator("tenant_id")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        """
        Validate tenant ID is not empty.

        Args:
            v: Tenant ID value

        Returns:
            Validated tenant ID

        Raises:
            ValueError: If tenant_id is empty
        """
        if not v or not v.strip():
            raise ValueError("tenant_id cannot be empty")
        return v.strip()

    def model_post_init(self, __context: Any) -> None:
        """
        Post-initialization processing.

        When both role_ids and area_ids are None or empty,
        it means all users should receive the dispatch.

        Args:
            __context: Context for post-init validation
        """
        # No validation needed - empty filters mean "all users"
        pass

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
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
                "created_at": "2025-12-22T16:30:00Z",
            },
            "examples": [
                {
                    "description": "With filters (specific roles/areas)",
                    "value": {
                        "dispatch_id": "550e8400-e29b-41d4-a716-446655440000",
                        "tenant_id": "henko-main",
                        "role_ids": ["770e8400-e29b-41d4-a716-446655440002"],
                        "area_ids": ["880e8400-e29b-41d4-a716-446655440003"],
                        "created_at": "2025-12-22T16:30:00Z",
                        "created_by": "990e8400-e29b-41d4-a716-446655440004",
                    },
                },
                {
                    "description": "All users (no filters)",
                    "value": {
                        "dispatch_id": "550e8400-e29b-41d4-a716-446655440000",
                        "tenant_id": "henko-main",
                        "role_ids": None,
                        "area_ids": None,
                        "created_at": "2025-12-22T16:30:00Z",
                        "created_by": "990e8400-e29b-41d4-a716-446655440004",
                    },
                },
            ],
        }


class SQSEvent(BaseModel):
    """
    Model for AWS SQS event structure.

    This represents the event structure that Lambda receives
    when triggered by SQS.
    """

    Records: list[dict[str, Any]] = Field(
        ...,
        description="List of SQS records",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "Records": [
                    {
                        "messageId": "19dd0b57-b21e-4ac1-bd88-01b068e44e77",
                        "receiptHandle": "MessageReceiptHandle",
                        "body": '{"dispatch_id":"...","tenant_id":"..."}',
                        "attributes": {
                            "ApproximateReceiveCount": "1",
                            "SentTimestamp": "1523232000000",
                            "SenderId": "AIDAIT2UOQQY3AUEKVGXU",
                            "ApproximateFirstReceiveTimestamp": "1523232000001",
                        },
                        "messageAttributes": {},
                        "md5OfBody": "7b270e59b47ff90a553787216d55d91d",
                        "eventSource": "aws:sqs",
                        "eventSourceARN": (
                            "arn:aws:sqs:us-east-1:123456789012:"
                            "form-dispatch-events-qa"
                        ),
                        "awsRegion": "us-east-1",
                    }
                ]
            }
        }


class CreateAssignmentRequest(BaseModel):
    """
    Model for creating assignments via form-service API.

    This represents the request body sent to form-service
    internal endpoint to create assignments.
    """

    dispatch_id: str = Field(..., description="ID of the form dispatch")
    user_ids: list[str] = Field(
        ...,
        description="List of user IDs to create assignments for",
        min_length=1,
    )
    expires_at: datetime | None = Field(
        None,
        description="Optional expiration date for assignments",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "dispatch_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_ids": [
                    "550e8400-e29b-41d4-a716-446655440001",
                    "550e8400-e29b-41d4-a716-446655440002",
                ],
                "expires_at": "2025-12-31T23:59:59Z",
            }
        }
