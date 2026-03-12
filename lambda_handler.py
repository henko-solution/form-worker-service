"""
Lambda handler for processing SQS events.

Routes incoming messages to the appropriate processor based on event_type:
- dispatch.created          → DispatchProcessor
- dispatch.completed        → DispatchCompletedProcessor
- user.candidate.assigned   → UserCandidateAssignedProcessor
"""

import json
import logging
from typing import Any

from app.config import get_settings
from app.exceptions import ValidationError, WorkerError
from app.workers.dispatch_completed_processor import DispatchCompletedProcessor
from app.workers.dispatch_processor import DispatchProcessor
from app.workers.user_candidate_assigned_processor import (
    UserCandidateAssignedProcessor,
)

logger = logging.getLogger(__name__)

# Supported event types for routing
SUPPORTED_EVENT_TYPES = {
    "dispatch.created",
    "dispatch.completed",
    "user.candidate.assigned",
}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler entry point."""
    settings = get_settings()
    level = getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )

    logger.info("Lambda handler invoked")
    logger.debug("Environment: %s", settings.app_name)

    records = event.get("Records", [])
    if not records:
        logger.warning("No SQS records found")
        return {
            "status": "ok",
            "message": "No records to process",
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "results": [],
        }

    logger.info("Processing %d SQS message(s)", len(records))

    result = process_sqs_records(records)

    logger.info(
        "Processing complete: %d processed, %d ok, %d failed, %d returned to queue",
        result["processed"],
        result["successful"],
        result["failed"],
        len(result.get("batchItemFailures", [])),
    )

    # batchItemFailures = mensajes no borrados (para otros consumidores)
    return result


def process_sqs_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Process SQS records; routes to the appropriate processor based on event_type.

    Supported event types:
    - dispatch.created:         Creates assignments for users.
    - dispatch.completed:       Calculates and persists candidate evaluations.
    - user.candidate.assigned:  Creates dispatches for candidate assessment forms.

    Returns results and batchItemFailures when the queue is shared.
    """
    dispatch_processor = DispatchProcessor()
    completed_processor = DispatchCompletedProcessor()
    user_candidate_processor = UserCandidateAssignedProcessor()

    results: list[dict[str, Any]] = []
    successful = 0
    failed = 0
    batch_item_failures: list[dict[str, str]] = (
        []
    )  # receiptHandle → no borrar; para otros consumidores

    try:
        for record in records:
            message_id = record.get("messageId", "unknown")
            receipt_handle = record.get("receiptHandle", "")
            logger.debug("Processing message: %s", message_id)

            try:
                message_body = record.get("body", "")
                if not message_body:
                    raise ValidationError("Message body is empty", "empty_body")

                logger.debug("Message body for %s: %.200s...", message_id, message_body)

                # Determine event_type from raw JSON before full parsing
                try:
                    raw_data = json.loads(message_body)
                except json.JSONDecodeError as e:
                    raise ValidationError(f"Invalid JSON: {e}", "invalid_json")

                event_type = raw_data.get("event_type")

                if event_type == "user.candidate.assigned":
                    # Log full payload to help debug event structure (non-sensitive)
                    logger.info(
                        "Received user.candidate.assigned message_id=%s payload=%s",
                        message_id,
                        raw_data,
                    )

                # Route to the appropriate processor
                if event_type == "dispatch.completed":
                    result = _handle_dispatch_completed(
                        message_body, message_id, completed_processor
                    )
                elif event_type == "dispatch.created" or event_type is None:
                    # event_type is None → legacy format, assume dispatch.created
                    result = _handle_dispatch_created(
                        message_body, message_id, dispatch_processor
                    )
                elif event_type == "user.candidate.assigned":
                    result = _handle_user_candidate_assigned(
                        message_body,
                        message_id,
                        user_candidate_processor,
                    )
                else:
                    # Unsupported event_type → skip and return to queue
                    logger.info(
                        "Skipping message %s: unsupported event_type=%r",
                        message_id,
                        event_type,
                    )
                    results.append(
                        {
                            "message_id": message_id,
                            "status": "skipped",
                            "reason": f"event_type={event_type!r}",
                        }
                    )
                    if receipt_handle:
                        batch_item_failures.append({"itemIdentifier": receipt_handle})
                    continue

                results.append(
                    {
                        "message_id": message_id,
                        "status": "success",
                        "result": result,
                    }
                )
                successful += 1

                # Log en CloudWatch (buscar "FORM-WORKER result")
                logger.info(
                    "FORM-WORKER result message_id=%s event_type=%s "
                    "dispatch_id=%s status=%s",
                    message_id,
                    event_type or "dispatch.created",
                    result.get("dispatch_id"),
                    result.get("status", "ok"),
                )

            except ValidationError as e:
                logger.warning("Validation error for %s: %s", message_id, e)
                error_code = getattr(e, "error_code", "validation_error")
                results.append(
                    {
                        "message_id": message_id,
                        "status": "failed",
                        "error": str(e),
                        "error_code": error_code,
                        "retryable": False,
                    }
                )
                failed += 1

            except WorkerError as e:
                logger.error("Worker error for %s: %s", message_id, e, exc_info=True)
                error_code = getattr(e, "error_code", "worker_error")
                results.append(
                    {
                        "message_id": message_id,
                        "status": "failed",
                        "error": str(e),
                        "error_code": error_code,
                        "retryable": True,
                    }
                )
                failed += 1
                raise

            except Exception as e:
                logger.error(
                    "Unexpected error for %s: %s", message_id, e, exc_info=True
                )
                results.append(
                    {
                        "message_id": message_id,
                        "status": "failed",
                        "error": str(e),
                        "error_code": "unexpected_error",
                        "retryable": True,
                    }
                )
                failed += 1
                raise

    finally:
        dispatch_processor.close()
        completed_processor.close()
        user_candidate_processor.close()

    out: dict[str, Any] = {
        "processed": len(records),
        "successful": successful,
        "failed": failed,
        "results": results,
    }
    if batch_item_failures:
        out["batchItemFailures"] = batch_item_failures
    return out


# ------------------------------------------------------------------
# Private handler functions — one per event type
# ------------------------------------------------------------------


def _handle_dispatch_created(
    message_body: str,
    message_id: str,
    processor: DispatchProcessor,
) -> dict[str, Any]:
    """Parse and process a dispatch.created event.

    Args:
        message_body: Raw JSON string from SQS.
        message_id: SQS message ID for logging.
        processor: DispatchProcessor instance.

    Returns:
        Processing result dict.
    """
    dispatch_event = processor.parse_sqs_message(message_body)

    role_count = len(dispatch_event.role_ids) if dispatch_event.role_ids else 0
    area_count = len(dispatch_event.area_ids) if dispatch_event.area_ids else 0

    logger.info(
        "Parsed dispatch.created: dispatch_id=%s tenant_id=%s "
        "role_ids=%d area_ids=%d",
        dispatch_event.dispatch_id,
        dispatch_event.tenant_id,
        role_count,
        area_count,
    )

    result = processor.process_dispatch_event(dispatch_event)

    logger.info(
        "dispatch.created result: dispatch_id=%s users_found=%s "
        "assignments_created=%s status=%s",
        result.get("dispatch_id"),
        result.get("users_found", 0),
        result.get("assignments_created", 0),
        result.get("status", "ok"),
    )

    return result


def _handle_dispatch_completed(
    message_body: str,
    message_id: str,
    processor: DispatchCompletedProcessor,
) -> dict[str, Any]:
    """Parse and process a dispatch.completed event.

    Args:
        message_body: Raw JSON string from SQS.
        message_id: SQS message ID for logging.
        processor: DispatchCompletedProcessor instance.

    Returns:
        Processing result dict.
    """
    completed_event = processor.parse_sqs_message(message_body)

    logger.info(
        "Parsed dispatch.completed: dispatch_id=%s tenant_id=%s employee=%s",
        completed_event.dispatch_id,
        completed_event.tenant_id,
        completed_event.employee_id,
    )

    result = processor.process_dispatch_completed_event(completed_event)

    logger.info(
        "dispatch.completed result: dispatch_id=%s "
        "vacancies=%s dimensions=%s skills=%s scores=%s status=%s",
        result.get("dispatch_id"),
        result.get("vacancies_processed", 0),
        result.get("total_dimensions_saved", 0),
        result.get("total_skills_saved", 0),
        result.get("total_scores_updated", 0),
        result.get("status", "ok"),
    )

    return result


def _handle_user_candidate_assigned(
    message_body: str,
    message_id: str,
    processor: UserCandidateAssignedProcessor,
) -> dict[str, Any]:
    """
    Parse and process a user.candidate.assigned event.

    Args:
        message_body: Raw JSON string from SQS.
        message_id: SQS message ID for logging.
        processor: UserCandidateAssignedProcessor instance.

    Returns:
        Processing result dict.
    """
    event = processor.parse_sqs_message(message_body)

    logger.info(
        "Parsed user.candidate.assigned: user_id=%s tenant_id=%s role_id=%s "
        "role_name=%s",
        event.data.user_id,
        event.data.tenant_id,
        event.data.role_id,
        event.data.role_name,
    )

    result = processor.process_user_candidate_assigned_event(event)

    logger.info(
        "user.candidate.assigned result: user_id=%s tenant_id=%s "
        "forms_found=%s dispatches_created=%s status=%s",
        result.get("user_id"),
        result.get("tenant_id"),
        result.get("forms_found", 0),
        result.get("dispatches_created", 0),
        result.get("status", "ok"),
    )

    return result
