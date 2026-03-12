"""
Form Service API client.

Provides methods for:
- Creating assignments (dispatch.created flow)
- Retrieving employee analytics: dimensions, skills, score (dispatch.completed flow)
"""

import logging
from typing import Any, cast

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
            if isinstance(result, dict):
                # If it's already a dict, return as is
                return result

            # Unexpected format, log warning but return what we got
            logger.warning(
                "Unexpected response format from Form Service: %s",
                type(result),
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

    def get_forms_by_names(
        self,
        tenant_id: str,
        form_names: list[str],
    ) -> list[dict[str, Any]]:
        """
        Get forms by exact names using the Form Service API.

        Args:
            tenant_id: Tenant identifier for multi-tenant isolation.
            form_names: List of form names to search for (exact match).

        Returns:
            List of form dictionaries as returned by Form Service.
        """
        if not form_names:
            return []

        try:
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
            }

            # One names_in parameter per form name
            params = [("names_in", name) for name in form_names]
            url = f"{self.base_url}/forms/"

            response = self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            forms = data.get("forms", [])
            if not isinstance(forms, list):
                logger.warning(
                    "Unexpected forms field type from Form Service: %s",
                    type(forms),
                )
                return []

            return cast(list[dict[str, Any]], forms)

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error("Get forms by names API error: %s", status)
            raise FormServiceError(
                f"Get forms by names API returned {status}",
                "form_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Get forms by names request error: %s", e)
            raise FormServiceError(
                f"Failed to get forms by names: {e}",
                "form_service_connection_error",
            )
        except Exception as e:
            logger.error("Get forms by names error: %s", e)
            raise FormServiceError(
                f"Get forms by names error: {e}",
                "form_service_error",
            )

    def create_dispatch(
        self,
        tenant_id: str,
        form_id: str,
        user_ids: list[str],
    ) -> str:
        """
        Create a new dispatch for a form and specific users.

        Args:
            tenant_id: Tenant identifier for multi-tenant isolation.
            form_id: ID of the form to dispatch.
            user_ids: List of user IDs that should receive the dispatch.

        Returns:
            The ID of the created dispatch.
        """
        if not user_ids:
            raise FormServiceError(
                "user_ids must not be empty",
                "form_service_validation_error",
            )

        try:
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
            }

            url = f"{self.base_url}/forms/{form_id}/dispatches"
            payload = {
                "roles": None,
                "areas": None,
                "user_ids": user_ids,
                "expires_at": None,
            }

            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            dispatch_id = data.get("id")
            if not isinstance(dispatch_id, str):
                logger.error(
                    "Invalid dispatch response from Form Service: missing id field",
                )
                raise FormServiceError(
                    "Form Service returned invalid dispatch response (missing id)",
                    "form_service_api_error",
                )

            return dispatch_id

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error("Create dispatch API error: %s", status)
            raise FormServiceError(
                f"Create dispatch API returned {status}",
                "form_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Create dispatch request error: %s", e)
            raise FormServiceError(
                f"Failed to create dispatch: {e}",
                "form_service_connection_error",
            )
        except Exception as e:
            logger.error("Create dispatch error: %s", e)
            raise FormServiceError(
                f"Create dispatch error: {e}",
                "form_service_error",
            )

    def get_employee_dimensions(
        self,
        tenant_id: str,
        employee_id: str,
        position_id: str,
    ) -> dict[str, Any]:
        """
        Get calculated dimension values for an employee in a position.
        """
        try:
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
            }

            url = (
                f"{self.base_url}/analytics/employees/{employee_id}"
                f"/positions/{position_id}/dimensions"
            )

            logger.debug(
                "Getting employee dimensions: employee=%s position=%s",
                employee_id,
                position_id,
            )

            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error(
                "Get employee dimensions API error: status=%s employee=%s "
                "position=%s",
                status,
                employee_id,
                position_id,
            )
            raise FormServiceError(
                f"Get employee dimensions API returned {status}",
                "form_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Get employee dimensions request error: %s", e)
            raise FormServiceError(
                f"Failed to get employee dimensions: {e}",
                "form_service_connection_error",
            )
        except Exception as e:
            logger.error("Get employee dimensions error: %s", e)
            raise FormServiceError(
                f"Get employee dimensions error: {e}",
                "form_service_error",
            )

    def get_employee_skills(
        self,
        tenant_id: str,
        employee_id: str,
        position_id: str,
    ) -> dict[str, Any]:
        """
        Get calculated skill values for an employee in a position.
        """
        try:
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
            }

            url = (
                f"{self.base_url}/analytics/employees/{employee_id}"
                f"/positions/{position_id}/skills"
            )

            logger.debug(
                "Getting employee skills: employee=%s position=%s",
                employee_id,
                position_id,
            )

            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error(
                "Get employee skills API error: status=%s employee=%s " "position=%s",
                status,
                employee_id,
                position_id,
            )
            raise FormServiceError(
                f"Get employee skills API returned {status}",
                "form_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Get employee skills request error: %s", e)
            raise FormServiceError(
                f"Failed to get employee skills: {e}",
                "form_service_connection_error",
            )
        except Exception as e:
            logger.error("Get employee skills error: %s", e)
            raise FormServiceError(
                f"Get employee skills error: {e}",
                "form_service_error",
            )

    def get_employee_score(
        self,
        tenant_id: str,
        employee_id: str,
        position_id: str,
    ) -> dict[str, Any]:
        """
        Get weighted score for an employee in a position.
        """
        try:
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {self.auth_service.get_access_token()}",
            }

            url = (
                f"{self.base_url}/analytics/employees/{employee_id}"
                f"/positions/{position_id}/score"
            )

            logger.debug(
                "Getting employee score: employee=%s position=%s",
                employee_id,
                position_id,
            )

            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error(
                "Get employee score API error: status=%s employee=%s " "position=%s",
                status,
                employee_id,
                position_id,
            )
            raise FormServiceError(
                f"Get employee score API returned {status}",
                "form_service_api_error",
            )
        except requests.RequestException as e:
            logger.error("Get employee score request error: %s", e)
            raise FormServiceError(
                f"Failed to get employee score: {e}",
                "form_service_connection_error",
            )
        except Exception as e:
            logger.error("Get employee score error: %s", e)
            raise FormServiceError(
                f"Get employee score error: {e}",
                "form_service_error",
            )
