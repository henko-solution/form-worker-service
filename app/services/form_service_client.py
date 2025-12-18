"""
Form Service API client for creating assignments.

This service calls the internal form-service API endpoint
to create assignments for users.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import get_settings
from ..exceptions import FormServiceError
from ..models.events import CreateAssignmentRequest

logger = logging.getLogger(__name__)


class FormServiceClient:
    """Client for consuming Form Service internal API."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        """Initialize Form Service client.

        Args:
            base_url: Base URL for Form Service API. If None, uses
                form_service_url from settings.
            timeout: Request timeout in seconds
        """
        settings = get_settings()
        self.base_url = base_url or settings.form_service_url
        self.api_key = settings.internal_api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    async def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            base_url_str: str = str(self.base_url) if self.base_url else ""
            self._client = httpx.AsyncClient(
                base_url=base_url_str,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def create_assignments(
        self,
        tenant_id: str,
        request: CreateAssignmentRequest,
    ) -> dict[str, Any]:
        """Create assignments via Form Service internal API.

        Args:
            tenant_id: Tenant ID for multi-tenant isolation
            request: Assignment creation request

        Returns:
            Response from Form Service API with created assignments

        Raises:
            FormServiceError: If API call fails
        """
        try:
            client = await self.client

            # Prepare headers
            headers = {
                "X-Tenant-ID": tenant_id,
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            }

            # Make API call to internal endpoint
            response = await client.post(
                "/internal/assignments",
                json=request.model_dump(mode="json"),
                headers=headers,
            )

            response.raise_for_status()

            # Parse and return response
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Form Service API error: "
                f"{e.response.status_code} - {e.response.text}"
            )
            raise FormServiceError(
                f"Form Service API returned {e.response.status_code}: {str(e)}",
                "form_service_api_error",
            )
        except httpx.RequestError as e:
            logger.error(f"Form Service request error: {str(e)}")
            raise FormServiceError(
                f"Failed to connect to Form Service: {str(e)}",
                "form_service_connection_error",
            )
        except Exception as e:
            logger.error(f"Unexpected error calling Form Service: {str(e)}")
            raise FormServiceError(
                f"Unexpected error: {str(e)}",
                "form_service_unexpected_error",
            )

    async def __aenter__(self) -> "FormServiceClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
