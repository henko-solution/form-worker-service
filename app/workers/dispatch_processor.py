"""
Dispatch processor worker.

This module contains the main logic for processing form dispatch events
from SQS and creating assignments for users.
"""

import json
import logging
from typing import Any
from uuid import UUID

from ..config import get_settings
from ..exceptions import (
    EmployeeServiceError,
    FormServiceError,
    ValidationError,
    WorkerError,
)
from ..models.events import CreateAssignmentRequest, DispatchEvent
from ..services.cognito_auth_service import CognitoAuthService
from ..services.employee_service import EmployeeService
from ..services.form_service_client import FormServiceClient

logger = logging.getLogger(__name__)


class DispatchProcessor:
    """Processor for form dispatch events."""

    def __init__(
        self,
        employee_service: EmployeeService | None = None,
        form_service_client: FormServiceClient | None = None,
        auth_service: CognitoAuthService | None = None,
    ) -> None:
        """Initialize dispatch processor.

        Args:
            employee_service: Employee Service client instance
            form_service_client: Form Service client instance
            auth_service: Cognito authentication service instance
                (shared between clients)
        """
        self.settings = get_settings()
        # Share auth service between clients to avoid multiple authentications
        self.auth_service = auth_service or CognitoAuthService()
        self.employee_service = employee_service or EmployeeService(
            auth_service=self.auth_service
        )
        self.form_service_client = form_service_client or FormServiceClient(
            auth_service=self.auth_service
        )

    def parse_sqs_message(self, message_body: str) -> DispatchEvent:
        """Parse SQS message body into DispatchEvent.

        Args:
            message_body: JSON string from SQS message body

        Returns:
            Parsed DispatchEvent

        Raises:
            ValidationError: If message cannot be parsed or validated
        """
        try:
            data = json.loads(message_body)
            return DispatchEvent(**data)
        except json.JSONDecodeError as e:
            raise ValidationError(
                f"Invalid JSON in SQS message: {str(e)}",
                "invalid_json",
            )
        except (TypeError, ValueError) as e:
            # Pydantic validation errors
            raise ValidationError(
                f"Failed to validate dispatch event: {str(e)}",
                "validation_error",
            )
        except KeyError as e:
            raise ValidationError(
                f"Missing required field in dispatch event: {str(e)}",
                "missing_field",
            )

    def get_user_ids(
        self,
        tenant_id: str,
        role_ids: list[UUID] | None = None,
        area_ids: list[UUID] | None = None,
    ) -> list[str]:
        """Get user IDs from Employee Service.

        Args:
            tenant_id: Tenant ID
            role_ids: Optional list of role IDs
            area_ids: Optional list of area IDs

        Returns:
            List of user IDs

        Raises:
            EmployeeServiceError: If Employee Service call fails
        """
        role_ids_str = [str(rid) for rid in role_ids] if role_ids else None
        area_ids_str = [str(aid) for aid in area_ids] if area_ids else None

        # Log filter status
        if not role_ids_str and not area_ids_str:
            logger.info(
                f"Fetching all users from Employee Service "
                f"(no filters applied): tenant_id={tenant_id}"
            )
        else:
            logger.info(
                f"Fetching users from Employee Service: "
                f"tenant_id={tenant_id}, "
                f"role_ids={len(role_ids_str) if role_ids_str else 0}, "
                f"area_ids={len(area_ids_str) if area_ids_str else 0}"
            )

        user_ids = self.employee_service.get_users_by_role_and_area(
            tenant_id=tenant_id,
            role_ids=role_ids_str,
            area_ids=area_ids_str,
        )

        logger.info(f"Found {len(user_ids)} users from Employee Service")
        return user_ids

    def split_into_batches(
        self,
        items: list[str],
        batch_size: int | None = None,
    ) -> list[list[str]]:
        """Split list of items into batches.

        Args:
            items: List of items to split
            batch_size: Size of each batch. If None, uses settings value.

        Returns:
            List of batches
        """
        if batch_size is None:
            batch_size = self.settings.assignment_batch_size

        batches = []
        for i in range(0, len(items), batch_size):
            batches.append(items[i : i + batch_size])
        return batches

    def create_assignments_batch(
        self,
        tenant_id: str,
        dispatch_id: UUID,
        user_ids: list[str],
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        """Create assignments for a batch of users.

        Args:
            tenant_id: Tenant ID
            dispatch_id: Dispatch ID
            user_ids: List of user IDs for this batch
            expires_at: Optional expiration date (ISO 8601 string)

        Returns:
            Response from Form Service API

        Raises:
            FormServiceError: If Form Service call fails
        """
        request = CreateAssignmentRequest(
            dispatch_id=str(dispatch_id),
            user_ids=user_ids,
            expires_at=expires_at,
        )

        logger.info(f"Creating {len(user_ids)} assignments for dispatch {dispatch_id}")

        response = self.form_service_client.create_assignments(
            tenant_id=tenant_id,
            request=request,
        )

        logger.info(
            f"Successfully created {response.get('total_created', 0)} "
            f"assignments for dispatch {dispatch_id}"
        )

        return response

    def process_dispatch_event(self, event: DispatchEvent) -> dict[str, Any]:
        """Process a single dispatch event.

        This is the main processing logic:
        1. Get user IDs from Employee Service
        2. Split users into batches
        3. Create assignments via Form Service API

        Args:
            event: Dispatch event to process

        Returns:
            Processing result with statistics

        Raises:
            WorkerError: If processing fails
        """
        logger.info(
            f"Processing dispatch event: dispatch_id={event.dispatch_id}, "
            f"tenant_id={event.tenant_id}"
        )

        try:
            # Step 1: Get user IDs from Employee Service
            # If role_ids and area_ids are None/empty, all users will be returned
            user_ids = self.get_user_ids(
                tenant_id=event.tenant_id,
                role_ids=event.role_ids,
                area_ids=event.area_ids,
            )

            if not user_ids:
                logger.warning(
                    f"No users found for dispatch {event.dispatch_id}. "
                    f"Processing will complete without creating assignments."
                )
                return {
                    "dispatch_id": str(event.dispatch_id),
                    "users_found": 0,
                    "assignments_created": 0,
                    "batches_processed": 0,
                    "status": "completed_no_users",
                }

            # Step 2: Split users into batches
            batches = self.split_into_batches(user_ids)
            logger.info(
                f"Split {len(user_ids)} users into {len(batches)} batches "
                f"(batch_size={self.settings.assignment_batch_size})"
            )

            # Step 3: Create assignments in batches
            total_created = 0
            expires_at_str = event.expires_at.isoformat() if event.expires_at else None

            for batch_idx, batch in enumerate(batches, start=1):
                logger.info(
                    f"Processing batch {batch_idx}/{len(batches)} "
                    f"({len(batch)} users)"
                )

                try:
                    response = self.create_assignments_batch(
                        tenant_id=event.tenant_id,
                        dispatch_id=event.dispatch_id,
                        user_ids=batch,
                        expires_at=expires_at_str,
                    )
                    total_created += response.get("total_created", len(batch))
                except FormServiceError as e:
                    logger.error(
                        f"Failed to create assignments for batch {batch_idx}: {str(e)}"
                    )
                    # Re-raise to trigger retry
                    raise

            logger.info(
                f"Successfully processed dispatch {event.dispatch_id}: "
                f"{total_created} assignments created"
            )

            return {
                "dispatch_id": str(event.dispatch_id),
                "users_found": len(user_ids),
                "assignments_created": total_created,
                "batches_processed": len(batches),
                "status": "completed",
            }

        except EmployeeServiceError as e:
            logger.error(
                f"Employee Service error processing dispatch {event.dispatch_id}: "
                f"{str(e)}"
            )
            raise WorkerError(
                f"Failed to get users from Employee Service: {str(e)}",
                "employee_service_error",
            )
        except FormServiceError as e:
            logger.error(
                f"Form Service error processing dispatch {event.dispatch_id}: "
                f"{str(e)}"
            )
            raise WorkerError(
                f"Failed to create assignments: {str(e)}",
                "form_service_error",
            )
        except (ValueError, TypeError, KeyError) as e:
            # Data validation/processing errors
            logger.error(
                f"Data processing error for dispatch {event.dispatch_id}: {str(e)}",
                exc_info=True,
            )
            raise WorkerError(
                f"Data processing error: {str(e)}",
                "data_processing_error",
            )
        except (AttributeError, IndexError) as e:
            # Programming errors that should be caught
            logger.error(
                f"Programming error processing dispatch {event.dispatch_id}: {str(e)}",
                exc_info=True,
            )
            raise WorkerError(
                f"Processing error: {str(e)}",
                "processing_error",
            )

    def close(self) -> None:
        """Close service clients."""
        try:
            self.employee_service.close()
        except Exception as e:
            logger.warning(f"Error closing employee service: {str(e)}")
        try:
            self.form_service_client.close()
        except Exception as e:
            logger.warning(f"Error closing form service client: {str(e)}")
