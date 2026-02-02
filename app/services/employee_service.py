"""
Employee Service client for retrieving users by role and area.
"""

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
        """Initialize Employee Service client with optimized session."""
        settings = get_settings()
        self.base_url = (
            (base_url or settings.employee_service_url or "").strip().rstrip("/")
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
                "accept": "application/json",
            }
        )

    def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            self.session.close()

    def get_users_by_role_and_area(
        self,
        tenant_id: str,
        role_ids: list[str] | None = None,
        area_ids: list[str] | None = None,
    ) -> list[str]:
        """
        Get user IDs from Employee Service filtered by role and/or area.
        Implements pagination to retrieve all users.
        """
        try:
            # Employee Service uses page (1-indexed) and page_size for pagination
            page_size = 100
            base_params: dict[str, Any] = {"page": 1, "page_size": page_size}
            if role_ids:
                base_params["positions_in"] = role_ids
            if area_ids:
                base_params["departments_in"] = area_ids

            # Headers that change per request (override session defaults)
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
            }

            url = f"{self.base_url}/employees/"
            all_user_ids: list[str] = []
            page = 1

            # Paginate through all pages (Employee Service: page 1-indexed, page_size)
            while True:
                params = base_params.copy()
                params["page"] = page
                params["page_size"] = page_size

                response = self.session.get(
                    url, params=params, headers=headers, timeout=self.timeout
                )

                response.raise_for_status()
                data = response.json()

                # Handle response format
                employees: list[Any] = []
                if isinstance(data, list):
                    # Direct list format (legacy)
                    employees = data
                    page_user_ids = [
                        str(user.get("id", "")) for user in employees if user.get("id")
                    ]
                    all_user_ids.extend(page_user_ids)
                    break  # No pagination for list format

                if isinstance(data, dict):
                    # Current format: employees, page, page_size, total_pages
                    if "employees" in data:
                        employees = data["employees"]
                        total_pages = data.get("total_pages", 1)
                        current_page = data.get("page", page)

                        page_user_ids = [
                            str(emp.get("id", "")) for emp in employees if emp.get("id")
                        ]
                        all_user_ids.extend(page_user_ids)

                        if current_page >= total_pages:
                            break

                        page += 1
                        continue

                    # Legacy support: 'items' key (no pagination)
                    if "items" in data:
                        items = data["items"]
                        if items and isinstance(items[0], dict):
                            page_user_ids = [
                                str(user.get("id", ""))
                                for user in items
                                if user.get("id")
                            ]
                            all_user_ids.extend(page_user_ids)
                        elif items:
                            page_user_ids = [str(uid) for uid in items]
                            all_user_ids.extend(page_user_ids)
                        else:
                            logger.warning(
                                "Response has 'items' key but it's empty or None"
                            )
                        break

                    logger.warning(
                        "Unexpected response format: %s", type(data).__name__
                    )
                    break

                logger.warning("Unexpected response format: %s", type(data).__name__)
                break

            return all_user_ids

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error("Employee Service API error: %s", status)
            raise EmployeeServiceError(
                f"Employee Service API returned {status}",
                "employee_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Employee Service request error: %s", e)
            raise EmployeeServiceError(
                f"Failed to connect to Employee Service: {e}",
                "employee_service_connection_error",
            )
        except Exception as e:
            logger.error("Employee Service error: %s", e)
            raise EmployeeServiceError(
                f"Employee Service error: {e}",
                "employee_service_error",
            )
