"""
Lambda handler for processing SQS events.

This is the entry point for the Lambda function triggered by SQS.
"""

import json
import logging
from typing import Any

from .exceptions import ValidationError, WorkerError
from .models.events import SQSEvent
from .workers.dispatch_processor import DispatchProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def process_sqs_event(event: dict[str, Any]) -> dict[str, Any]:
    """Process SQS event asynchronously.

    Args:
        event: SQS event from Lambda

    Returns:
        Processing result
    """
    processor = DispatchProcessor()
    results = []

    try:
        # Parse SQS event
        sqs_event = SQSEvent(**event)

        logger.info(f"Received {len(sqs_event.Records)} SQS records")

        # Process each record
        for record in sqs_event.Records:
            message_id = record.get("messageId", "unknown")
            receipt_handle = record.get("receiptHandle", "")
            body = record.get("body", "")

            logger.info(f"Processing message {message_id}")

            try:
                # Parse dispatch event from message body
                dispatch_event = processor.parse_sqs_message(body)

                # Process the dispatch event
                result = await processor.process_dispatch_event(dispatch_event)

                results.append(
                    {
                        "message_id": message_id,
                        "status": "success",
                        "result": result,
                    }
                )

                logger.info(
                    f"Successfully processed message {message_id}: "
                    f"{result.get('assignments_created', 0)} assignments created"
                )

            except ValidationError as e:
                logger.error(
                    f"Validation error processing message {message_id}: {str(e)}"
                )
                # Don't retry validation errors
                results.append(
                    {
                        "message_id": message_id,
                        "status": "failed",
                        "error": str(e),
                        "error_code": e.error_code,
                        "retryable": False,
                    }
                )
            except WorkerError as e:
                logger.error(
                    f"Worker error processing message {message_id}: {str(e)}"
                )
                # Retry worker errors (SQS will handle retries)
                results.append(
                    {
                        "message_id": message_id,
                        "status": "failed",
                        "error": str(e),
                        "error_code": e.error_code,
                        "retryable": True,
                    }
                )
                # Re-raise to trigger Lambda retry
                raise
            except Exception as e:
                logger.error(
                    f"Unexpected error processing message {message_id}: {str(e)}",
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
                # Re-raise to trigger Lambda retry
                raise

    finally:
        # Close service clients
        await processor.close()

    return {
        "processed": len(results),
        "successful": sum(1 for r in results if r.get("status") == "success"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "results": results,
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler entry point.

    Args:
        event: SQS event from Lambda
        context: Lambda context

    Returns:
        Processing result
    """
    import asyncio

    logger.info("Lambda handler invoked")

    try:
        # Run async processing
        result = asyncio.run(process_sqs_event(event))
        logger.info(
            f"Processing complete: {result['successful']} successful, "
            f"{result['failed']} failed"
        )
        return result
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}", exc_info=True)
        # Return error result
        return {
            "processed": 0,
            "successful": 0,
            "failed": 1,
            "error": str(e),
            "results": [],
        }
