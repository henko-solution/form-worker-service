"""
Lambda handler for processing SQS events.

This is the entry point for the Lambda function triggered by SQS.
"""

import logging
from typing import Any

from app.config import get_settings
from app.exceptions import ValidationError, WorkerError
from app.workers.dispatch_processor import DispatchProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler entry point.

    Processes SQS events containing dispatch events and creates assignments
    for users via Employee Service and Form Service APIs.

    Args:
        event: SQS event from Lambda with Records array
        context: Lambda context

    Returns:
        Processing result with statistics
    """
    # Load settings to validate environment variables
    settings = get_settings()

    logger.info("Lambda handler invoked")
    logger.info(f"Environment: {settings.app_name}")
    logger.info(f"AWS Region: {settings.aws_region}")
    logger.info(f"Form Service URL: {settings.form_service_url}")
    logger.info(f"Employee Service URL: {settings.employee_service_url}")

    # Parse SQS event
    records = event.get("Records", [])
    if not records:
        logger.warning("No SQS records found in event")
        return {
            "status": "ok",
            "message": "No records to process",
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "results": [],
        }

    logger.info(f"Processing {len(records)} SQS message(s)")

    # Process records synchronously
    result = process_sqs_records(records)

    logger.info(
        f"Processing complete: {result['processed']} processed, "
        f"{result['successful']} successful, {result['failed']} failed"
    )

    return result


def process_sqs_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Process SQS records.

    Args:
        records: List of SQS records

    Returns:
        Processing result with statistics
    """
    processor = DispatchProcessor()
    results = []
    successful = 0
    failed = 0

    try:
        for record in records:
            message_id = record.get("messageId", "unknown")

            logger.info(f"Processing message: {message_id}")

            try:
                # Extract message body
                message_body = record.get("body", "")
                if not message_body:
                    raise ValidationError(
                        "Message body is empty",
                        "empty_body",
                    )

                # Parse and process dispatch event
                dispatch_event = processor.parse_sqs_message(message_body)
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
                    f"Successfully processed message {message_id}: "
                    f"{result.get('assignments_created', 0)} assignments created"
                )

            except ValidationError as e:
                logger.warning(f"Validation error for message {message_id}: {str(e)}")
                # Validation errors are permanent - don't retry
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
                logger.error(
                    f"Worker error for message {message_id}: {str(e)}",
                    exc_info=True,
                )
                # Worker errors may be retryable (transient service errors)
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
                # Re-raise to trigger SQS retry mechanism
                raise

            except Exception as e:
                logger.error(
                    f"Unexpected error processing message " f"{message_id}: {str(e)}",
                    exc_info=True,
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
                # Re-raise to trigger SQS retry mechanism
                raise

    finally:
        # Always close clients
        processor.close()

    return {
        "processed": len(records),
        "successful": successful,
        "failed": failed,
        "results": results,
    }
