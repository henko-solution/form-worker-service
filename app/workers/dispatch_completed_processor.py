"""
Dispatch completed processor worker.

Handles post-processing when a dispatch is completed by an employee.
The flow calculates candidate evaluations via Form Service analytics
and persists them in Employee Service:
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
from ..models.events import DispatchCompletedEvent
from ..services.cognito_auth_service import CognitoAuthService
from ..services.employee_service import EmployeeService
from ..services.form_service_client import FormServiceClient

logger = logging.getLogger(__name__)


class DispatchCompletedProcessor:
    """Processor for dispatch.completed events."""

    def __init__(
        self,
        employee_service: EmployeeService | None = None,
        form_service_client: FormServiceClient | None = None,
        auth_service: CognitoAuthService | None = None,
    ) -> None:
        """Initialize dispatch completed processor.

        Args:
            employee_service: Optional pre-configured EmployeeService instance.
            form_service_client: Optional pre-configured FormServiceClient instance.
            auth_service: Optional pre-configured CognitoAuthService instance.
        """
        self.settings = get_settings()
        self.auth_service = auth_service or CognitoAuthService()
        self.employee_service = employee_service or EmployeeService(
            auth_service=self.auth_service
        )
        self.form_service_client = form_service_client or FormServiceClient(
            auth_service=self.auth_service
        )

    def parse_sqs_message(self, message_body: str) -> DispatchCompletedEvent:
        """Parse SQS message body into DispatchCompletedEvent.

        Args:
            message_body: Raw JSON string from SQS message body.

        Returns:
            Validated DispatchCompletedEvent instance.

        Raises:
            ValidationError: If JSON is invalid or validation fails.
        """
        try:
            return DispatchCompletedEvent(**json.loads(message_body))
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}", "invalid_json")
        except Exception as e:
            raise ValidationError(f"Validation error: {e}", "validation_error")

    def process_dispatch_completed_event(
        self, event: DispatchCompletedEvent
    ) -> dict[str, Any]:
        """Process a single dispatch.completed event."""
        tenant_id = event.tenant_id
        employee_id = str(event.employee_id)
        vacancy_id = str(event.vacancy_id)
        candidate_id = str(event.candidate_id)
        position_id = str(event.position_id)

        logger.info(
            "Processing dispatch.completed: dispatch=%s tenant=%s "
            "employee=%s vacancy=%s",
            event.dispatch_id,
            tenant_id,
            employee_id,
            vacancy_id,
        )

        try:
            # Step a) Calculate dimensions from Form Service analytics
            dimensions_data = self.form_service_client.get_employee_dimensions(
                tenant_id=tenant_id,
                employee_id=employee_id,
                position_id=position_id,
            )
            dimensions = dimensions_data.get("dimensions", [])

            logger.info(
                "Calculated %d dimension(s) for employee %s",
                len(dimensions),
                employee_id,
            )

            # Step b) Save each dimension evaluation in Employee Service
            dimensions_saved = 0
            for dim in dimensions:
                dim_id = dim.get("dimension_id")
                dim_value = dim.get("dimension_value")

                if dim_id is None or dim_value is None:
                    logger.debug(
                        "Skipping dimension with missing data: id=%s value=%s",
                        dim_id,
                        dim_value,
                    )
                    continue

                self.employee_service.create_candidate_dimension_evaluation(
                    tenant_id=tenant_id,
                    vacancy_id=vacancy_id,
                    employee_id=employee_id,
                    dimension_id=str(dim_id),
                    dimension_value=float(dim_value),
                )
                dimensions_saved += 1

            logger.info(
                "Saved %d dimension evaluation(s) for employee %s",
                dimensions_saved,
                employee_id,
            )

            # Step c) Calculate skills from Form Service analytics
            skills_data = self.form_service_client.get_employee_skills(
                tenant_id=tenant_id,
                employee_id=employee_id,
                position_id=position_id,
            )
            skills = skills_data.get("skills", [])

            logger.info(
                "Calculated %d skill(s) for employee %s",
                len(skills),
                employee_id,
            )

            # Step d) Save each skill evaluation in Employee Service
            skills_saved = 0
            for skill in skills:
                skill_id = skill.get("skill_id")
                skill_value = skill.get("skill_value")

                if skill_id is None or skill_value is None:
                    logger.debug(
                        "Skipping skill with missing data: id=%s value=%s",
                        skill_id,
                        skill_value,
                    )
                    continue

                self.employee_service.create_candidate_skill_evaluation(
                    tenant_id=tenant_id,
                    vacancy_id=vacancy_id,
                    employee_id=employee_id,
                    skill_id=str(skill_id),
                    skill_value=float(skill_value),
                )
                skills_saved += 1

            logger.info(
                "Saved %d skill evaluation(s) for employee %s",
                skills_saved,
                employee_id,
            )

            # Step e) Calculate weighted score from Form Service analytics
            score_data = self.form_service_client.get_employee_score(
                tenant_id=tenant_id,
                employee_id=employee_id,
                position_id=position_id,
            )
            raw_score = score_data.get("score")

            # Step f) Save score in Employee Service (scale 0-1 → 0-100)
            if raw_score is not None:
                score_int = round(float(raw_score) * 100)
                # Clamp to valid range
                score_int = max(0, min(100, score_int))

                self.employee_service.update_vacancy_candidate(
                    tenant_id=tenant_id,
                    vacancy_id=vacancy_id,
                    candidate_id=candidate_id,
                    score=score_int,
                )

                logger.info(
                    "Updated candidate %s score to %d (raw: %s)",
                    candidate_id,
                    score_int,
                    raw_score,
                )
            else:
                score_int = None
                logger.warning(
                    "Score is null for employee %s — skipping candidate update",
                    employee_id,
                )

            logger.info(
                "Completed dispatch.completed %s: "
                "dimensions=%d skills=%d score=%s",
                event.dispatch_id,
                dimensions_saved,
                skills_saved,
                score_int,
            )

            return {
                "dispatch_id": str(event.dispatch_id),
                "event_type": "dispatch.completed",
                "employee_id": employee_id,
                "vacancy_id": vacancy_id,
                "candidate_id": candidate_id,
                "dimensions_saved": dimensions_saved,
                "skills_saved": skills_saved,
                "score": score_int,
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
