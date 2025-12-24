"""
Employee Service client for retrieving users by role and area.

This service consumes the external Employee Service API to get user IDs
based on role and area filters.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import get_settings
from ..exceptions import EmployeeServiceError
from .cognito_auth_service import CognitoAuthService

logger = logging.getLogger(__name__)


class EmployeeService:
    """Client for consuming Employee Service API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        auth_service: CognitoAuthService | None = None,
    ) -> None:
        """Initialize Employee Service client.

        Args:
            base_url: Base URL for Employee Service API. If None, uses
                employee_service_url from settings.
            timeout: Request timeout in seconds
            auth_service: Cognito authentication service instance
        """
        settings = get_settings()
        self.base_url = base_url or settings.employee_service_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self.auth_service = auth_service or CognitoAuthService()

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

    async def get_users_by_role_and_area(
        self,
        tenant_id: str,
        role_ids: list[str] | None = None,
        area_ids: list[str] | None = None,
    ) -> list[str]:
        """Get user IDs from Employee Service filtered by role and/or area.

        Args:
            tenant_id: Tenant ID for filtering
            role_ids: Optional list of role UUIDs to filter by
            area_ids: Optional list of area UUIDs to filter by

        Returns:
            List of user IDs (UUIDs as strings)

        Raises:
            EmployeeServiceError: If API call fails or returns invalid response
        """
        try:
            client = await self.client

            # Build query parameters
            params: dict[str, Any] = {"tenant_id": tenant_id}
            if role_ids:
                params["role_ids"] = role_ids
            if area_ids:
                params["area_ids"] = area_ids

            # Get authentication token
            access_token = await self.auth_service.get_access_token()

            # Prepare headers
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {access_token}",
            }

            # Make API call
            # Expected endpoint:
            # GET /api/v1/employees/users?tenant_id=...&role_ids=...&area_ids=...
            response = await client.get(
                "/api/v1/employees/users",
                params=params,
                headers=headers,
            )

            response.raise_for_status()

            # Parse response
            data = response.json()

            # Expected response format:
            # {
            #   "users": [
            #     {"id": "uuid1", ...},
            #     {"id": "uuid2", ...}
            #   ]
            # }
            # Or:
            # ["uuid1", "uuid2", ...]

            if isinstance(data, list):
                # Direct list of user IDs
                return [str(user_id) for user_id in data]
            elif isinstance(data, dict):
                # Object with users array
                users = data.get("users", [])
                if users and isinstance(users[0], dict):
                    # List of user objects with id field
                    return [str(user.get("id", "")) for user in users if user.get("id")]
                else:
                    # List of user IDs
                    return [str(user_id) for user_id in users]
            else:
                logger.warning(
                    f"Unexpected response format from Employee Service: {type(data)}"
                )
                return []

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Employee Service API error: "
                f"{e.response.status_code} - {e.response.text}"
            )
            raise EmployeeServiceError(
                f"Employee Service API returned {e.response.status_code}: {str(e)}",
                "employee_service_api_error",
            )
        except httpx.RequestError as e:
            logger.error(f"Employee Service request error: {str(e)}")
            raise EmployeeServiceError(
                f"Failed to connect to Employee Service: {str(e)}",
                "employee_service_connection_error",
            )
        except (ValueError, TypeError, KeyError) as e:
            # Response parsing errors
            logger.error(f"Employee Service response parsing error: {str(e)}")
            raise EmployeeServiceError(
                f"Failed to parse Employee Service response: {str(e)}",
                "employee_service_parse_error",
            )
        except httpx.TimeoutException as e:
            logger.error(f"Employee Service timeout: {str(e)}")
            raise EmployeeServiceError(
                f"Employee Service request timed out: {str(e)}",
                "employee_service_timeout",
            )

    async def __aenter__(self) -> "EmployeeService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
