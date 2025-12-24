"""
Form Service API client for creating assignments.

This service calls the internal form-service API endpoint
to create assignments for users.
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
    """Client for consuming Form Service internal API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        auth_service: CognitoAuthService | None = None,
    ) -> None:
        """Initialize Form Service client.

        Args:
            base_url: Base URL for Form Service API. If None, uses
                form_service_url from settings.
            timeout: Request timeout in seconds
            auth_service: Cognito authentication service instance
        """
        settings = get_settings()
        self.base_url = base_url or settings.form_service_url
        self.timeout = timeout
        self.auth_service = auth_service or CognitoAuthService()
        # Keep API key for backward compatibility (deprecated)
        self.api_key = settings.internal_api_key
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

    def create_assignments(
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
            # Get authentication token
            access_token = self.auth_service.get_access_token()

            # Prepare headers
            headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Fallback to API key if Cognito is not configured (backward compatibility)
            if not access_token and self.api_key:
                logger.warning(
                    "Using deprecated API key authentication. "
                    "Please configure Cognito authentication."
                )
                headers["X-API-Key"] = self.api_key
                headers.pop("Authorization", None)

            # Build full URL
            url = f"{self.base_url}/internal/assignments"

            # Make API call to internal endpoint
            response = self.session.post(
                url,
                json=request.model_dump(mode="json"),
                headers=headers,
                timeout=self.timeout,
            )

            response.raise_for_status()

            # Parse and return response
            return response.json()

        except requests.HTTPError as e:
            logger.error(
                f"Form Service API error: "
                f"{e.response.status_code if e.response else 'Unknown'} - "
                f"{e.response.text if e.response else str(e)}"
            )
            raise FormServiceError(
                f"Form Service API returned "
                f"{e.response.status_code if e.response else 'unknown status'}: {str(e)}",
                "form_service_api_error",
            )
        except requests.RequestException as e:
            logger.error(f"Form Service request error: {str(e)}")
            raise FormServiceError(
                f"Failed to connect to Form Service: {str(e)}",
                "form_service_connection_error",
            )
        except (ValueError, TypeError, KeyError) as e:
            # Response parsing errors
            logger.error(f"Form Service response parsing error: {str(e)}")
            raise FormServiceError(
                f"Failed to parse Form Service response: {str(e)}",
                "form_service_parse_error",
            )
        except requests.Timeout as e:
            logger.error(f"Form Service timeout: {str(e)}")
            raise FormServiceError(
                f"Form Service request timed out: {str(e)}",
                "form_service_timeout",
            )
