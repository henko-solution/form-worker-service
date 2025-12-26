"""
Form Service API client for creating assignments.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import get_settings
from ..exceptions import FormServiceError
from ..models.events import CreateAssignmentRequest
from .cognito_auth_service import CognitoAuthService

logger = logging.getLogger(__name__)


class FormServiceClient:
    """Client for consuming Form Service API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        auth_service: CognitoAuthService | None = None,
    ) -> None:
        """Initialize Form Service client with optimized session."""
        settings = get_settings()
        self.base_url = (
            (base_url or settings.form_service_url or "").strip().rstrip("/")
        )
        self.timeout = timeout
        self.auth_service = auth_service or CognitoAuthService()

        # Create session with connection pooling
        self.session = requests.Session()

        # Configure HTTP adapter with connection pooling
        # pool_connections: number of connection pools to cache
        # pool_maxsize: maximum number of connections to save in the pool
        adapter = HTTPAdapter(
            pool_connections=1,  # Single connection pool for this service
            pool_maxsize=10,  # Allow up to 10 connections in the pool
            max_retries=Retry(
                # Disable automatic retries (we handle retries at higher level)
                total=0,
                backoff_factor=0,
            ),
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers for all requests
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "accept": "application/json",
            }
        )

    def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            self.session.close()

    def create_assignments(
        self,
        tenant_id: str,
        request: CreateAssignmentRequest,
    ) -> dict[str, Any]:
        """Create assignments via Form Service API."""
        try:
            # Headers that change per request (override session defaults)
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
            }

            url = f"{self.base_url}/assignments"
            payload = request.model_dump(mode="json")

            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )

            response.raise_for_status()
            result = response.json()

            # The endpoint returns a list of FormAssignmentResponse
            # Convert to dict format for compatibility
            if isinstance(result, list):
                return {"assignments": result, "total_created": len(result)}
            elif isinstance(result, dict):
                # If it's already a dict, return as is
                return result
            else:
                # Unexpected format, log warning but return what we got
                logger.warning(
                    f"Unexpected response format from Form Service: {type(result)}"
                )
                return {"assignments": [], "total_created": 0}

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error("Form Service API error: %s", status)
            raise FormServiceError(
                f"Form Service API returned {status}",
                "form_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Form Service request error: %s", e)
            raise FormServiceError(
                f"Failed to connect to Form Service: {e}",
                "form_service_connection_error",
            )
        except Exception as e:
            logger.error("Form Service error: %s", e)
            raise FormServiceError(
                f"Form Service error: {e}",
                "form_service_error",
            )
