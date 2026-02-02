"""
Cognito authentication service for system user.
"""

import base64
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ..config import get_settings
from ..exceptions import WorkerError

logger = logging.getLogger(__name__)


class CognitoAuthService:
    """Service for authenticating with Cognito and managing JWT tokens."""

    def __init__(
        self,
        user_pool_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        username: str | None = None,
        password: str | None = None,
        region: str | None = None,
    ) -> None:
        """Initialize Cognito authentication service."""
        settings = get_settings()
        self.user_pool_id = user_pool_id or settings.cognito_user_pool_id
        self.client_id = client_id or settings.cognito_client_id
        self.client_secret = client_secret or settings.cognito_client_secret
        self.username = username or settings.cognito_system_username
        self.password = password or settings.cognito_system_password
        self.region = region or settings.aws_region

        # Token cache
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._refresh_token: str | None = None

        # Initialize Cognito client
        self.client = boto3.client("cognito-idp", region_name=self.region)

    def _calculate_secret_hash(self, username: str) -> str:
        """Calculate secret hash for Cognito operations."""
        if not self.client_secret:
            return ""

        message = username + self.client_id
        digest = hmac.new(
            str(self.client_secret).encode("utf-8"),
            msg=message.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        return base64.b64encode(digest).decode("utf-8")

    def authenticate(self) -> str:
        """Authenticate with Cognito and get access token."""
        try:
            auth_params: dict[str, Any] = {
                "USERNAME": self.username,
                "PASSWORD": self.password,
            }

            if self.client_secret:
                auth_params["SECRET_HASH"] = self._calculate_secret_hash(self.username)

            response = self.client.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                ClientId=self.client_id,
                AuthParameters=auth_params,
            )

            if "AuthenticationResult" not in response:
                if "ChallengeName" in response:
                    raise WorkerError(
                        f"Cognito challenge required: {response.get('ChallengeName')}",
                        "cognito_challenge_required",
                    )
                raise WorkerError(
                    "Authentication result not found in Cognito response",
                    "cognito_auth_error",
                )

            auth_result = response["AuthenticationResult"]
            access_token = auth_result.get("AccessToken")

            if not access_token:
                raise WorkerError(
                    "Access token not found in Cognito response",
                    "cognito_token_error",
                )

            # Cache tokens
            self._access_token = access_token
            self._refresh_token = auth_result.get("RefreshToken")
            expires_in = auth_result.get("ExpiresIn", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(
                seconds=expires_in - 60
            )

            logger.info("Successfully authenticated with Cognito")
            return str(access_token)

        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Cognito authentication failed: {error_message}")
            raise WorkerError(
                f"Cognito authentication failed: {error_message}",
                "cognito_auth_error",
            )
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Error processing Cognito response: {e}")
            raise WorkerError(
                f"Failed to process Cognito authentication response: {e}",
                "cognito_parse_error",
            )

    def refresh_access_token(self) -> str:
        """Refresh access token using refresh token."""
        if not self._refresh_token:
            return self.authenticate()

        try:
            auth_params: dict[str, Any] = {"REFRESH_TOKEN": self._refresh_token}

            if self.client_secret:
                auth_params["SECRET_HASH"] = self._calculate_secret_hash(self.username)

            response = self.client.initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                ClientId=self.client_id,
                AuthParameters=auth_params,
            )

            auth_result = response.get("AuthenticationResult", {})
            access_token = auth_result.get("AccessToken")

            if not access_token:
                raise WorkerError(
                    "Access token not found in refresh response",
                    "cognito_token_error",
                )

            self._access_token = access_token
            expires_in = auth_result.get("ExpiresIn", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(
                seconds=expires_in - 60
            )

            logger.info("Successfully refreshed Cognito access token")
            return str(access_token)

        except ClientError as e:
            logger.warning(f"Token refresh failed, re-authenticating: {e}")
            self._access_token = None
            self._refresh_token = None
            self._token_expires_at = None
            return self.authenticate()

    def get_access_token(self) -> str:
        """Get valid access token, refreshing if necessary."""
        # Check if we have a valid cached token
        if (
            self._access_token
            and self._token_expires_at
            and datetime.utcnow() < self._token_expires_at
        ):
            return self._access_token

        # Token expired or not available, refresh or authenticate
        if self._refresh_token:
            try:
                return self.refresh_access_token()
            except WorkerError:
                return self.authenticate()

        return self.authenticate()

    def clear_tokens(self) -> None:
        """Clear cached tokens."""
        self._access_token = None
        self._refresh_token = None
        self._token_expires_at = None
