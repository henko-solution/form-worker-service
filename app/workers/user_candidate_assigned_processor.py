"""
User candidate assigned processor worker.

Handles the user.candidate.assigned event emitted by auth-service when a
user is assigned the candidate role. For each configured candidate form,
this worker creates a new dispatch targeted only to that user. The
existing dispatch.created flow is responsible for creating assignments.
"""

import json
import logging
from typing import Any

from ..config import get_settings
from ..exceptions import FormServiceError, ValidationError, WorkerError
from ..models.events import UserCandidateAssignedEvent
from ..services.cognito_auth_service import CognitoAuthService
from ..services.form_service_client import FormServiceClient

logger = logging.getLogger(__name__)


class UserCandidateAssignedProcessor:
    """Processor for user.candidate.assigned events."""

    def __init__(
        self,
        form_service_client: FormServiceClient | None = None,
        auth_service: CognitoAuthService | None = None,
    ) -> None:
        """Initialize user candidate assigned processor."""
        self.settings = get_settings()
        self.auth_service = auth_service or CognitoAuthService()
        self.form_service_client = form_service_client or FormServiceClient(
            auth_service=self.auth_service
        )

    def parse_sqs_message(self, message_body: str) -> UserCandidateAssignedEvent:
        """
        Parse SQS message body into UserCandidateAssignedEvent.

        Args:
            message_body: Raw JSON string from SQS message body.

        Returns:
            Validated UserCandidateAssignedEvent instance.

        Raises:
            ValidationError: If JSON is invalid or validation fails.
        """
        try:
            payload = json.loads(message_body)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}", "invalid_json")

        try:
            return UserCandidateAssignedEvent(**payload)
        except Exception as e:
            raise ValidationError(f"Validation error: {e}", "validation_error")

    def _get_candidate_form_names(self) -> list[str]:
        """Parse candidate form names from settings into a list."""
        raw_names = self.settings.candidate_form_names or ""
        return [name.strip() for name in raw_names.split(",") if name.strip()]

    def process_user_candidate_assigned_event(
        self,
        event: UserCandidateAssignedEvent,
    ) -> dict[str, Any]:
        """
        Process a single user.candidate.assigned event.

        Flow:
        1) Get form names from configuration (candidate_form_names).
        2) Resolve forms by name via Form Service.
        3) For each form, create a new dispatch targeted to the candidate user.
        4) Return processing statistics.
        """
        tenant_id = event.data.tenant_id
        user_id = str(event.data.user_id)

        logger.info(
            "Processing user.candidate.assigned: user_id=%s tenant_id=%s role_id=%s "
            "role_name=%s",
            user_id,
            tenant_id,
            event.data.role_id,
            event.data.role_name,
        )

        try:
            form_names = self._get_candidate_form_names()
            if not form_names:
                logger.warning(
                    "No candidate form names configured; skipping dispatch creation "
                    "for user_id=%s tenant_id=%s",
                    user_id,
                    tenant_id,
                )
                return {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "forms_found": 0,
                    "dispatches_created": 0,
                    "status": "completed_no_forms_configured",
                }

            forms = self.form_service_client.get_forms_by_names(
                tenant_id=tenant_id,
                form_names=form_names,
            )

            if not forms:
                logger.warning(
                    "No forms found in Form Service for configured "
                    "candidate_form_names; user_id=%s tenant_id=%s",
                    user_id,
                    tenant_id,
                )
                return {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "forms_found": 0,
                    "dispatches_created": 0,
                    "status": "completed_no_forms",
                }

            dispatches_created = 0

            for form in forms:
                form_id = form.get("id")
                form_name = form.get("name")

                if not form_id:
                    logger.warning(
                        "Skipping form without id in candidate dispatch creation: %s",
                        form,
                    )
                    continue

                dispatch_id = self.form_service_client.create_dispatch(
                    tenant_id=tenant_id,
                    form_id=str(form_id),
                    user_ids=[user_id],
                )
                dispatches_created += 1

                logger.info(
                    "Created candidate dispatch: dispatch_id=%s form_id=%s "
                    "form_name=%s user_id=%s tenant_id=%s",
                    dispatch_id,
                    form_id,
                    form_name,
                    user_id,
                    tenant_id,
                )

            logger.info(
                "Completed user.candidate.assigned: user_id=%s tenant_id=%s "
                "forms_found=%d dispatches_created=%d",
                user_id,
                tenant_id,
                len(forms),
                dispatches_created,
            )

            return {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "forms_found": len(forms),
                "dispatches_created": dispatches_created,
                "status": "completed",
            }

        except FormServiceError as e:
            logger.error("Form Service error while processing candidate event: %s", e)
            raise WorkerError(str(e), getattr(e, "error_code", "service_error"))
        except Exception as e:
            logger.error(
                "Processing error for user.candidate.assigned: %s",
                e,
                exc_info=True,
            )
            raise WorkerError(f"Processing error: {e}", "processing_error")

    def close(self) -> None:
        """Close service clients."""
        try:
            self.form_service_client.close()
        except Exception as e:
            logger.warning("Error closing FormServiceClient: %s", e)
