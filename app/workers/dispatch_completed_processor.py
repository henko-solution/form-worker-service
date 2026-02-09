"""
Dispatch completed processor worker.

Handles post-processing when a dispatch is completed by an employee.
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
        """
        Process a single dispatch.completed event.

        Executes the full evaluation flow:
        a) Get employee vacancies  → get_employee_vacancies
        For each vacancy:
          b) Calculate dimensions  → get_employee_dimensions
          c) Save dimensions       → create_candidate_dimension_evaluation
          d) Calculate skills      → get_employee_skills
          e) Save skills           → create_candidate_skill_evaluation

        Args:
            event: Validated DispatchCompletedEvent.

        Returns:
            Dict with processing results and statistics.

        Raises:
            WorkerError: If any step fails.
        """
        tenant_id = event.tenant_id
        employee_id = str(event.employee_id)

        logger.info(
            "Processing dispatch.completed: dispatch=%s tenant=%s employee=%s",
            event.dispatch_id,
            tenant_id,
            employee_id,
        )

        try:
            # Step a) Get employee vacancies from Employee Service
            vacancies = self.employee_service.get_employee_vacancies(
                tenant_id=tenant_id,
                employee_id=employee_id,
            )

            if not vacancies:
                logger.warning(
                    "No vacancies found for employee %s",
                    employee_id,
                )
                return {
                    "dispatch_id": str(event.dispatch_id),
                    "event_type": "dispatch.completed",
                    "employee_id": employee_id,
                    "vacancies_processed": 0,
                    "total_dimensions_saved": 0,
                    "total_skills_saved": 0,
                    "status": "completed_no_vacancies",
                }

            logger.info(
                "Found %d vacanc(y/ies) for employee %s",
                len(vacancies),
                employee_id,
            )

            # Process each vacancy
            total_dimensions_saved = 0
            total_skills_saved = 0
            vacancies_processed = 0

            for vacancy in vacancies:
                vacancy_id = vacancy.get("id")
                position_data = vacancy.get("position")

                if not vacancy_id or not position_data:
                    logger.warning(
                        "Skipping vacancy with missing data: id=%s position=%s",
                        vacancy_id,
                        position_data,
                    )
                    continue

                position_id = position_data.get("id")
                if not position_id:
                    logger.warning(
                        "Skipping vacancy %s: missing position.id",
                        vacancy_id,
                    )
                    continue

                vacancy_id_str = str(vacancy_id)
                position_id_str = str(position_id)

                logger.info(
                    "Processing vacancy %s (position %s) for employee %s",
                    vacancy_id_str,
                    position_id_str,
                    employee_id,
                )

                # Step b) Calculate dimensions from Form Service analytics
                dimensions_data = self.form_service_client.get_employee_dimensions(
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    position_id=position_id_str,
                )
                dimensions = dimensions_data.get("dimensions", [])

                logger.debug(
                    "Calculated %d dimension(s) for employee %s, vacancy %s",
                    len(dimensions),
                    employee_id,
                    vacancy_id_str,
                )

                # Step c) Save each dimension evaluation in Employee Service
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
                        vacancy_id=vacancy_id_str,
                        employee_id=employee_id,
                        dimension_id=str(dim_id),
                        dimension_value=float(dim_value),
                    )
                    dimensions_saved += 1

                total_dimensions_saved += dimensions_saved
                logger.debug(
                    "Saved %d dimension(s) for employee %s, vacancy %s",
                    dimensions_saved,
                    employee_id,
                    vacancy_id_str,
                )

                # Step d) Calculate skills from Form Service analytics
                skills_data = self.form_service_client.get_employee_skills(
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    position_id=position_id_str,
                )
                skills = skills_data.get("skills", [])

                logger.debug(
                    "Calculated %d skill(s) for employee %s, vacancy %s",
                    len(skills),
                    employee_id,
                    vacancy_id_str,
                )

                # Step e) Save each skill evaluation in Employee Service
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
                        vacancy_id=vacancy_id_str,
                        employee_id=employee_id,
                        skill_id=str(skill_id),
                        skill_value=float(skill_value),
                    )
                    skills_saved += 1

                total_skills_saved += skills_saved
                logger.debug(
                    "Saved %d skill(s) for employee %s, vacancy %s",
                    skills_saved,
                    employee_id,
                    vacancy_id_str,
                )

                vacancies_processed += 1
                logger.info(
                    "Completed vacancy %s: dimensions=%d skills=%d",
                    vacancy_id_str,
                    dimensions_saved,
                    skills_saved,
                )

            logger.info(
                "Completed dispatch.completed %s: "
                "vacancies=%d dimensions=%d skills=%d",
                event.dispatch_id,
                vacancies_processed,
                total_dimensions_saved,
                total_skills_saved,
            )

            return {
                "dispatch_id": str(event.dispatch_id),
                "event_type": "dispatch.completed",
                "employee_id": employee_id,
                "vacancies_processed": vacancies_processed,
                "total_dimensions_saved": total_dimensions_saved,
                "total_skills_saved": total_skills_saved,
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
