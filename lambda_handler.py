"""
Lambda handler for processing SQS events.
"""

import logging
from typing import Any

from app.config import get_settings
from app.exceptions import ValidationError, WorkerError
from app.workers.dispatch_processor import DispatchProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler entry point."""
    settings = get_settings()

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
        "Processing complete: %d processed, %d successful, %d failed",
        result["processed"],
        result["successful"],
        result["failed"],
    )

    return result


def process_sqs_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Process SQS records."""
    processor = DispatchProcessor()
    results = []
    successful = 0
    failed = 0

    try:
        for record in records:
            message_id = record.get("messageId", "unknown")
            logger.debug("Processing message: %s", message_id)

            try:
                message_body = record.get("body", "")
                if not message_body:
                    raise ValidationError("Message body is empty", "empty_body")

                logger.debug(
                    "Message body for %s: %.200s...", message_id, message_body
                )
                dispatch_event = processor.parse_sqs_message(message_body)
                role_count = (
                    len(dispatch_event.role_ids) if dispatch_event.role_ids else 0
                )
                area_count = (
                    len(dispatch_event.area_ids) if dispatch_event.area_ids else 0
                )
                logger.debug(
                    "Parsed dispatch event: dispatch_id=%s, tenant_id=%s, "
                    "role_ids=%d, area_ids=%d",
                    dispatch_event.dispatch_id,
                    dispatch_event.tenant_id,
                    role_count,
                    area_count,
                )
                result = processor.process_dispatch_event(dispatch_event)

                results.append(
                    {
                        "message_id": message_id,
                        "status": "success",
                        "result": result,
                    }
                )
                successful += 1

                logger.info(
                    "Successfully processed %s: %d assignments created",
                    message_id,
                    result.get("assignments_created", 0),
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
        processor.close()

    return {
        "processed": len(records),
        "successful": successful,
        "failed": failed,
        "results": results,
    }
