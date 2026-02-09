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
          c) Save dimensions       → create_candidate_dimension_evaluations_batch
          d) Calculate skills      → get_employee_skills
          e) Save skills           → create_candidate_skill_evaluations_batch
          f) Get score             → get_employee_score (Form Service)
          g) Update candidate score → update_candidate_score (Employee Service)

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
                    "total_scores_updated": 0,
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
            total_scores_updated = 0
            vacancies_processed = 0

            for vacancy in vacancies:
                vacancy_id = vacancy.get("id")
                position_id = vacancy.get("position_id")

                if not vacancy_id or not position_id:
                    logger.warning(
                        "Skipping vacancy with missing data: id=%s position_id=%s",
                        vacancy_id,
                        position_id,
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

                # Step c) Save dimension evaluations in Employee Service (batch)
                dimension_evals = [
                    {
                        "dimension_id": d["dimension_id"],
                        "dimension_value": d["dimension_value"],
                    }
                    for d in dimensions
                    if d.get("dimension_id") is not None
                    and d.get("dimension_value") is not None
                ]
                dimensions_saved = 0
                batch_size = self.employee_service.BATCH_MAX_ITEMS
                emp_svc = self.employee_service
                for i in range(0, len(dimension_evals), batch_size):
                    chunk = dimension_evals[i : i + batch_size]
                    resp = emp_svc.create_candidate_dimension_evaluations_batch(
                        tenant_id=tenant_id,
                        vacancy_id=vacancy_id_str,
                        employee_id=employee_id,
                        evaluations=chunk,
                    )
                    dimensions_saved += len(resp)
                if len(dimension_evals) > batch_size:
                    logger.info(
                        "Vacancy %s: sent %d dimensions in %d batch request(s)",
                        vacancy_id_str,
                        len(dimension_evals),
                        (len(dimension_evals) + batch_size - 1) // batch_size,
                    )
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

                # Step e) Save skill evaluations in Employee Service (batch)
                skill_evals = [
                    {"skill_id": s["skill_id"], "skill_value": s["skill_value"]}
                    for s in skills
                    if s.get("skill_id") is not None
                    and s.get("skill_value") is not None
                ]
                skills_saved = 0
                for i in range(0, len(skill_evals), batch_size):
                    chunk = skill_evals[i : i + batch_size]
                    resp = emp_svc.create_candidate_skill_evaluations_batch(
                        tenant_id=tenant_id,
                        vacancy_id=vacancy_id_str,
                        employee_id=employee_id,
                        evaluations=chunk,
                    )
                    skills_saved += len(resp)
                if len(skill_evals) > batch_size:
                    logger.info(
                        "Vacancy %s: sent %d skills in %d batch request(s)",
                        vacancy_id_str,
                        len(skill_evals),
                        (len(skill_evals) + batch_size - 1) // batch_size,
                    )
                total_skills_saved += skills_saved
                logger.debug(
                    "Saved %d skill(s) for employee %s, vacancy %s",
                    skills_saved,
                    employee_id,
                    vacancy_id_str,
                )

                # Step f) Get score from Form Service analytics (0-1)
                score_data = self.form_service_client.get_employee_score(
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    position_id=position_id_str,
                )
                score_value = score_data.get("score")

                # Step g) Update candidate score in Employee Service (0-100)
                if score_value is not None:
                    score_int = int(round(float(score_value) * 100))
                    score_int = max(0, min(100, score_int))
                    self.employee_service.update_candidate_score(
                        tenant_id=tenant_id,
                        vacancy_id=vacancy_id_str,
                        employee_id=employee_id,
                        score=score_int,
                    )
                    total_scores_updated += 1
                    logger.info(
                        "Updated score for vacancy %s employee %s: %s",
                        vacancy_id_str,
                        employee_id,
                        score_int,
                    )
                else:
                    logger.debug(
                        "Skipping score update for vacancy %s: no score from Form",
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
                "vacancies=%d dimensions=%d skills=%d scores=%d",
                event.dispatch_id,
                vacancies_processed,
                total_dimensions_saved,
                total_skills_saved,
                total_scores_updated,
            )

            return {
                "dispatch_id": str(event.dispatch_id),
                "event_type": "dispatch.completed",
                "employee_id": employee_id,
                "vacancies_processed": vacancies_processed,
                "total_dimensions_saved": total_dimensions_saved,
                "total_skills_saved": total_skills_saved,
                "total_scores_updated": total_scores_updated,
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
