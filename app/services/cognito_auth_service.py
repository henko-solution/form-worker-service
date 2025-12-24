"""
Cognito authentication service for system user.

This service handles authentication with AWS Cognito to obtain JWT tokens
for making authenticated requests to external services.
"""

from __future__ import annotations

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
        """Initialize Cognito authentication service.

        Args:
            user_pool_id: Cognito User Pool ID
            client_id: Cognito Client ID
            client_secret: Cognito Client Secret (optional)
            username: System user username
            password: System user password
            region: AWS region
        """
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

        logger.debug(
            f"Initialized CognitoAuthService for user pool: {self.user_pool_id}, "
            f"client_id: {self.client_id}, "
            f"has_client_secret: {bool(self.client_secret)}"
        )

    def _calculate_secret_hash(self, username: str) -> str:
        """Calculate secret hash for Cognito operations.

        Args:
            username: Username for hash calculation

        Returns:
            Secret hash string
        """
        if not self.client_secret:
            return ""

        # Create the message
        message = username + self.client_id

        # Create the secret hash
        digest = hmac.new(
            str(self.client_secret).encode("utf-8"),
            msg=message.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        return base64.b64encode(digest).decode("utf-8")

    def authenticate(self) -> str:
        """Authenticate with Cognito and get access token.

        Returns:
            Access token (JWT)

        Raises:
            WorkerError: If authentication fails
        """
        try:
            logger.debug(
                f"Authenticating with Cognito: username={self.username}, "
                f"has_client_secret={bool(self.client_secret)}"
            )

            # Prepare authentication parameters
            auth_params: dict[str, Any] = {
                "USERNAME": self.username,
                "PASSWORD": self.password,
            }

            # If client_secret is provided, calculate and add SECRET_HASH
            if self.client_secret:
                secret_hash = self._calculate_secret_hash(self.username)
                auth_params["SECRET_HASH"] = secret_hash
            else:
                # Only warn if client_secret is missing (could be intentional if client has no secret)
                logger.debug(
                    "No client_secret provided. Authentication will proceed without SECRET_HASH."
                )

            # Authenticate with Cognito
            response = self.client.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                ClientId=self.client_id,
                AuthParameters=auth_params,
            )

            # Log response structure for debugging (without sensitive data)
            logger.debug(
                f"Cognito response keys: {list(response.keys())}, "
                f"has_AuthenticationResult: {'AuthenticationResult' in response}"
            )

            # Extract tokens from response
            if "AuthenticationResult" not in response:
                # Log full response structure for debugging
                response_keys = list(response.keys())
                logger.error(
                    f"Cognito authentication response structure: {response_keys}"
                )

                # Check if there's a challenge required
                if "ChallengeName" in response:
                    challenge_name = response.get("ChallengeName")
                    logger.error(
                        f"Cognito requires challenge: {challenge_name}. "
                        f"This may indicate the user needs to change password or complete MFA."
                    )
                    raise WorkerError(
                        f"Cognito authentication requires challenge: {challenge_name}. "
                        "System user may need password reset or MFA configuration.",
                        "cognito_challenge_required",
                    )

                # Log any other information in the response
                if "Session" in response:
                    logger.debug("Cognito returned Session (challenge flow)")

                raise WorkerError(
                    "Authentication result not found in Cognito response. "
                    f"Response structure: {response_keys}. "
                    "Check Cognito user pool configuration and system user status.",
                    "cognito_auth_error",
                )

            auth_result = response["AuthenticationResult"]
            access_token = auth_result.get("AccessToken")
            refresh_token = auth_result.get("RefreshToken")
            expires_in = auth_result.get("ExpiresIn", 3600)  # Default to 1 hour

            if not access_token:
                raise WorkerError(
                    "Access token not found in Cognito response",
                    "cognito_token_error",
                )

            # Cache tokens
            self._access_token = access_token
            self._refresh_token = refresh_token
            # Set expiration time (subtract 60 seconds for safety margin)
            self._token_expires_at = datetime.utcnow() + timedelta(
                seconds=expires_in - 60
            )

            logger.info("Successfully authenticated with Cognito")
            return access_token

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(
                f"Cognito authentication failed: {error_code} - {error_message}"
            )
            # Log additional context if available
            if "Error" in e.response:
                logger.error(f"Full error response: {e.response.get('Error')}")
            raise WorkerError(
                f"Cognito authentication failed: {error_message}",
                "cognito_auth_error",
            )
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Error processing Cognito response: {str(e)}")
            raise WorkerError(
                f"Failed to process Cognito authentication response: {str(e)}",
                "cognito_parse_error",
            )

    def refresh_access_token(self) -> str:
        """Refresh access token using refresh token.

        Returns:
            New access token (JWT)

        Raises:
            WorkerError: If token refresh fails
        """
        if not self._refresh_token:
            # No refresh token available, need to re-authenticate
            return self.authenticate()

        try:
            logger.debug("Refreshing Cognito access token")

            # Prepare refresh parameters
            auth_params: dict[str, Any] = {"REFRESH_TOKEN": self._refresh_token}

            if self.client_secret:
                auth_params["SECRET_HASH"] = self._calculate_secret_hash(self.username)

            # Refresh token with Cognito
            response = self.client.initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                ClientId=self.client_id,
                AuthParameters=auth_params,
            )

            # Extract new tokens
            auth_result = response.get("AuthenticationResult", {})
            access_token = auth_result.get("AccessToken")
            expires_in = auth_result.get("ExpiresIn", 3600)

            if not access_token:
                raise WorkerError(
                    "Access token not found in refresh response",
                    "cognito_token_error",
                )

            # Update cached tokens
            self._access_token = access_token
            # Refresh token remains the same
            self._token_expires_at = datetime.utcnow() + timedelta(
                seconds=expires_in - 60
            )

            logger.info("Successfully refreshed Cognito access token")
            return access_token

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.warning(
                f"Cognito token refresh failed: {error_code} - {error_message}. "
                "Will re-authenticate."
            )
            # Clear cached tokens and re-authenticate
            self._access_token = None
            self._refresh_token = None
            self._token_expires_at = None
            return self.authenticate()
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Error processing Cognito refresh response: {str(e)}")
            raise WorkerError(
                f"Failed to process Cognito refresh response: {str(e)}",
                "cognito_parse_error",
            )

    def get_access_token(self) -> str:
        """Get valid access token, refreshing if necessary.

        Returns:
            Valid access token (JWT)

        Raises:
            WorkerError: If token cannot be obtained
        """
        # Check if we have a valid cached token
        if (
            self._access_token
            and self._token_expires_at
            and datetime.utcnow() < self._token_expires_at
        ):
            logger.debug("Using cached access token")
            return self._access_token

        # Token expired or not available, refresh or authenticate
        if self._refresh_token:
            try:
                return self.refresh_access_token()
            except WorkerError:
                # Refresh failed, try full authentication
                logger.debug("Token refresh failed, re-authenticating")
                return self.authenticate()
        else:
            # No refresh token, need to authenticate
            return self.authenticate()

    def clear_tokens(self) -> None:
        """Clear cached tokens (useful for testing or forced re-authentication)."""
        self._access_token = None
        self._refresh_token = None
        self._token_expires_at = None
        logger.debug("Cleared cached tokens")
