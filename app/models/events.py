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
    """

    dispatch_id: UUID = Field(..., description="ID of the form dispatch")
    tenant_id: str = Field(..., description="Tenant ID for multi-tenant isolation")
    role_ids: list[UUID] = Field(
        default_factory=list,
        description="List of role IDs to filter users",
    )
    area_ids: list[UUID] = Field(
        default_factory=list,
        description="List of area IDs to filter users",
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

    @field_validator("role_ids", "area_ids")
    @classmethod
    def validate_not_both_empty(
        cls,
        v: list[UUID],
        info: Any,
    ) -> list[UUID]:
        """
        Validate that at least one filter (roles or areas) is provided.

        Args:
            v: Value to validate
            info: Validation info

        Returns:
            Validated value

        Raises:
            ValueError: If both role_ids and area_ids are empty
        """
        # This validator runs for each field separately
        # We need to check both fields in model_validator
        return v

    @field_validator("tenant_id")
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
        Validate that at least one filter is provided.

        Args:
            __context: Context for post-init validation

        Raises:
            ValueError: If both role_ids and area_ids are empty
        """
        if not self.role_ids and not self.area_ids:
            raise ValueError(
                "At least one of role_ids or area_ids must be provided"
            )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "dispatch_id": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_id": "henko-main",
                "role_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "area_ids": ["550e8400-e29b-41d4-a716-446655440002"],
                "expires_at": "2025-12-31T23:59:59Z",
                "created_at": "2025-12-15T12:00:00Z",
                "created_by": "user-uuid",
            }
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
                        "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:form-dispatch-events-qa",
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
