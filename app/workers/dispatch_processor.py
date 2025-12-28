"""
Dispatch processor worker.
"""

import json
import logging
from typing import Any

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
        """Initialize dispatch processor."""
        self.settings = get_settings()
        self.auth_service = auth_service or CognitoAuthService()
        self.employee_service = employee_service or EmployeeService(
            auth_service=self.auth_service
        )
        self.form_service_client = form_service_client or FormServiceClient(
            auth_service=self.auth_service
        )

    def parse_sqs_message(self, message_body: str) -> DispatchEvent:
        """Parse SQS message body into DispatchEvent."""
        try:
            return DispatchEvent(**json.loads(message_body))
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}", "invalid_json")
        except Exception as e:
            raise ValidationError(f"Validation error: {e}", "validation_error")

    def process_dispatch_event(self, event: DispatchEvent) -> dict[str, Any]:
        """Process a single dispatch event."""
        logger.info(
            "Processing dispatch: %s (tenant: %s)",
            event.dispatch_id,
            event.tenant_id,
        )

        try:
            # Use user_ids directly if provided, otherwise query Employee Service
            if event.user_ids:
                user_ids = event.user_ids
                logger.info(
                    "Using %d user_id(s) from message for dispatch %s",
                    len(user_ids),
                    event.dispatch_id,
                )
            else:
                # Get user IDs from Employee Service
                role_ids_str = (
                    [str(rid) for rid in event.role_ids] if event.role_ids else None
                )
                area_ids_str = (
                    [str(aid) for aid in event.area_ids] if event.area_ids else None
                )

                user_ids = self.employee_service.get_users_by_role_and_area(
                    tenant_id=event.tenant_id,
                    role_ids=role_ids_str,
                    area_ids=area_ids_str,
                )

                logger.info(
                    "Found %d user(s) from Employee Service for dispatch %s",
                    len(user_ids),
                    event.dispatch_id,
                )

            if not user_ids:
                logger.warning(
                    "No users found for dispatch %s (tenant: %s)",
                    event.dispatch_id,
                    event.tenant_id,
                )
                return {
                    "dispatch_id": str(event.dispatch_id),
                    "users_found": 0,
                    "assignments_created": 0,
                    "status": "completed_no_users",
                }

            # Optimize: Use larger batches since endpoint accepts list of user_ids
            # Default batch size is 1000 to minimize HTTP calls while staying
            # within reasonable payload limits
            max_batch_size = 1000
            batch_size = min(
                max_batch_size, self.settings.assignment_batch_size or max_batch_size
            )

            # Split into batches only if needed
            if len(user_ids) <= batch_size:
                batches = [user_ids]
            else:
                batches = [
                    user_ids[i : i + batch_size]
                    for i in range(0, len(user_ids), batch_size)
                ]
                logger.info(
                    "Processing %d batch(es) for %d users",
                    len(batches),
                    len(user_ids),
                )

            # Create assignments
            total_created = 0
            expires_at_str = event.expires_at.isoformat() if event.expires_at else None

            for batch in batches:
                request = CreateAssignmentRequest(
                    dispatch_id=str(event.dispatch_id),
                    user_ids=batch,
                    expires_at=expires_at_str,
                )

                response = self.form_service_client.create_assignments(
                    tenant_id=event.tenant_id,
                    request=request,
                )

                created = response.get("total_created", len(batch))
                total_created += created

            logger.info(
                "Completed dispatch %s: %d assignments created",
                event.dispatch_id,
                total_created,
            )

            return {
                "dispatch_id": str(event.dispatch_id),
                "users_found": len(user_ids),
                "assignments_created": total_created,
                "status": "completed",
            }

        except (EmployeeServiceError, FormServiceError) as e:
            logger.error("Service error: %s", e)
            raise WorkerError(str(e), getattr(e, "error_code", "service_error"))
        except Exception as e:
            logger.error("Processing error: %s", e, exc_info=True)
            raise WorkerError(f"Processing error: {e}", "processing_error")

    def close(self) -> None:
        """Close service clients."""
        try:
            self.employee_service.close()
            self.form_service_client.close()
        except Exception as e:
            logger.warning("Error closing services: %s", e)
