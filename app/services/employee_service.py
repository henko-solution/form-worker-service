"""
Employee Service client.

Provides methods for:
- Retrieving users by role and area (dispatch.created flow)
- Managing vacancy candidate evaluations (dispatch.completed flow)
"""

import logging
from typing import Any, cast

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
            body_preview = ""
            if e.response is not None:
                try:
                    body_preview = (e.response.text or "")[:500]
                except Exception:
                    body_preview = "(unable to read body)"
                logger.error(
                    "Employee Service API error: status=%s url=%s body_preview=%s",
                    status,
                    e.response.url if e.response else "",
                    body_preview,
                )
            else:
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

    def create_candidate_skill_evaluation(
        self,
        tenant_id: str,
        vacancy_id: str,
        employee_id: str,
        skill_id: str,
        skill_value: float,
    ) -> dict[str, Any]:
        """
        Create a skill evaluation for a candidate in a vacancy.
        """
        try:
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
                "Content-Type": "application/json",
            }

            url = (
                f"{self.base_url}/vacancies/{vacancy_id}"
                f"/candidates/{employee_id}/skills/{skill_id}"
            )
            payload = {"skill_value": skill_value}

            logger.debug(
                "Creating skill evaluation: vacancy=%s employee=%s skill=%s value=%s",
                vacancy_id,
                employee_id,
                skill_id,
                skill_value,
            )

            response = self.session.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error(
                "Skill evaluation API error: status=%s vacancy=%s employee=%s skill=%s",
                status,
                vacancy_id,
                employee_id,
                skill_id,
            )
            raise EmployeeServiceError(
                f"Skill evaluation API returned {status}",
                "employee_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Skill evaluation request error: %s", e)
            raise EmployeeServiceError(
                f"Failed to create skill evaluation: {e}",
                "employee_service_connection_error",
            )
        except Exception as e:
            logger.error("Skill evaluation error: %s", e)
            raise EmployeeServiceError(
                f"Skill evaluation error: {e}",
                "employee_service_error",
            )

    def create_candidate_dimension_evaluation(
        self,
        tenant_id: str,
        vacancy_id: str,
        employee_id: str,
        dimension_id: str,
        dimension_value: float,
    ) -> dict[str, Any]:
        """
        Create a dimension evaluation for a candidate in a vacancy.
        """
        try:
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
                "Content-Type": "application/json",
            }

            url = (
                f"{self.base_url}/vacancies/{vacancy_id}"
                f"/candidates/{employee_id}/dimensions/{dimension_id}"
            )
            payload = {"dimension_value": dimension_value}

            logger.debug(
                "Creating dimension evaluation: vacancy=%s employee=%s "
                "dimension=%s value=%s",
                vacancy_id,
                employee_id,
                dimension_id,
                dimension_value,
            )

            response = self.session.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error(
                "Dimension evaluation API error: status=%s vacancy=%s "
                "employee=%s dimension=%s",
                status,
                vacancy_id,
                employee_id,
                dimension_id,
            )
            raise EmployeeServiceError(
                f"Dimension evaluation API returned {status}",
                "employee_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Dimension evaluation request error: %s", e)
            raise EmployeeServiceError(
                f"Failed to create dimension evaluation: {e}",
                "employee_service_connection_error",
            )
        except Exception as e:
            logger.error("Dimension evaluation error: %s", e)
            raise EmployeeServiceError(
                f"Dimension evaluation error: {e}",
                "employee_service_error",
            )

    def update_candidate_score(
        self,
        tenant_id: str,
        vacancy_id: str,
        employee_id: str,
        score: int,
    ) -> dict[str, Any]:
        """
        Update the evaluation score for a candidate in a vacancy.

        PATCH /vacancies/{vacancy_id}/candidates/{employee_id}
        """
        try:
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
                "Content-Type": "application/json",
            }

            url = f"{self.base_url}/vacancies/{vacancy_id}" f"/candidates/{employee_id}"
            payload = {"score": score}

            logger.debug(
                "Updating candidate score: vacancy=%s employee=%s score=%s",
                vacancy_id,
                employee_id,
                score,
            )

            response = self.session.patch(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error(
                "Update candidate score API error: status=%s vacancy=%s employee=%s",
                status,
                vacancy_id,
                employee_id,
            )
            raise EmployeeServiceError(
                f"Update candidate score API returned {status}",
                "employee_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Update candidate score request error: %s", e)
            raise EmployeeServiceError(
                f"Failed to update candidate score: {e}",
                "employee_service_connection_error",
            )
        except Exception as e:
            logger.error("Update candidate score error: %s", e)
            raise EmployeeServiceError(
                f"Update candidate score error: {e}",
                "employee_service_error",
            )

    def get_employee_vacancies(
        self,
        tenant_id: str,
        employee_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get the list of vacancies for an employee.

        GET /employees/{employee_id}/vacancies

        Returns a list where each vacancy has:
        - id: vacancy_id
        - position_id: UUID of the associated position

        Args:
            tenant_id: Tenant ID for multi-tenant isolation.
            employee_id: ID of the employee.

        Returns:
            List of vacancy dicts, each with id and position_id.

        Raises:
            EmployeeServiceError: If the API call fails.
        """
        try:
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
            }

            url = f"{self.base_url}/employees/{employee_id}/vacancies"

            logger.debug(
                "Getting vacancies for employee: employee=%s",
                employee_id,
            )

            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            # Response is a list of vacancies
            if isinstance(data, list):
                return data
            else:
                logger.warning(
                    "Unexpected response format for employee vacancies: %s",
                    type(data).__name__,
                )
                return []

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error(
                "Get employee vacancies API error: status=%s employee=%s",
                status,
                employee_id,
            )
            raise EmployeeServiceError(
                f"Get employee vacancies API returned {status}",
                "employee_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Get employee vacancies request error: %s", e)
            raise EmployeeServiceError(
                f"Failed to get employee vacancies: {e}",
                "employee_service_connection_error",
            )
        except Exception as e:
            logger.error("Get employee vacancies error: %s", e)
            raise EmployeeServiceError(
                f"Get employee vacancies error: {e}",
                "employee_service_error",
            )
