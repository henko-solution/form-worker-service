"""
Employee Service client for retrieving users by role and area.

This service consumes the external Employee Service API to get user IDs
based on role and area filters.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
        base_url_raw = base_url or settings.employee_service_url
        # Add https:// if not already present
        if not base_url_raw.startswith("https://"):
            base_url_clean = base_url_raw.removeprefix("http://")
            self.base_url = f"https://{base_url_clean}"
        else:
            self.base_url = base_url_raw
        self.timeout = timeout
        self.auth_service = auth_service or CognitoAuthService()
        # Create a session with retry strategy
        self._session: requests.Session | None = None

    @property
    def session(self) -> requests.Session:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = requests.Session()
            # Configure retry strategy
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session

    def close(self) -> None:
        """Close HTTP session."""
        if self._session is not None:
            try:
                self._session.close()
            except Exception as e:
                logger.warning(f"Error closing HTTP session: {str(e)}")
            finally:
                self._session = None

    def get_users_by_role_and_area(
        self,
        tenant_id: str,
        role_ids: list[str] | None = None,
        area_ids: list[str] | None = None,
    ) -> list[str]:
        """Get user IDs from Employee Service filtered by role and/or area.

        Args:
            tenant_id: Tenant ID for filtering (sent as X-Tenant-ID header)
            role_ids: Optional list of role UUIDs to filter by (mapped to positions_in)
            area_ids: Optional list of area UUIDs to filter by (mapped to departments_in)

        Returns:
            List of user IDs (UUIDs as strings)

        Raises:
            EmployeeServiceError: If API call fails or returns invalid response
        """
        try:
            # Build query parameters
            # Note: role_ids maps to positions_in, area_ids maps to departments_in
            params: dict[str, Any] = {"skip": 0, "limit": 100}
            if role_ids:
                params["positions_in"] = role_ids
            if area_ids:
                params["departments_in"] = area_ids

            # Get authentication token
            access_token = self.auth_service.get_access_token()

            # Prepare headers
            # X-Tenant-ID is sent as header, not query parameter
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {access_token}",
                "accept": "application/json",
            }

            # Build full URL
            # Endpoint: GET /employees/
            url = f"{self.base_url}/employees/"

            # Make API call
            # Expected endpoint:
            # GET /employees/?skip=0&limit=100&positions_in=...&departments_in=...
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )

            response.raise_for_status()

            # Parse response
            data = response.json()

            # Expected response format from /employees/ endpoint:
            # {
            #   "items": [
            #     {"id": "uuid1", ...},
            #     {"id": "uuid2", ...}
            #   ],
            #   "total": 100,
            #   "skip": 0,
            #   "limit": 100
            # }
            # Or direct list:
            # [{"id": "uuid1", ...}, {"id": "uuid2", ...}]

            if isinstance(data, list):
                # Direct list of user objects
                return [str(user.get("id", "")) for user in data if user.get("id")]
            elif isinstance(data, dict):
                # Object with items array (pagination format)
                items = data.get("items", [])
                if items and isinstance(items[0], dict):
                    # List of user objects with id field
                    return [str(user.get("id", "")) for user in items if user.get("id")]
                else:
                    # List of user IDs
                    return [str(user_id) for user_id in items]
            else:
                logger.warning(
                    f"Unexpected response format from Employee Service: {type(data)}"
                )
                return []

        except requests.HTTPError as e:
            logger.error(
                f"Employee Service API error: "
                f"{e.response.status_code if e.response else 'Unknown'} - "
                f"{e.response.text if e.response else str(e)}"
            )
            raise EmployeeServiceError(
                f"Employee Service API returned "
                f"{e.response.status_code if e.response else 'unknown status'}: {str(e)}",
                "employee_service_api_error",
            )
        except requests.RequestException as e:
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
        except requests.Timeout as e:
            logger.error(f"Employee Service timeout: {str(e)}")
            raise EmployeeServiceError(
                f"Employee Service request timed out: {str(e)}",
                "employee_service_timeout",
            )
