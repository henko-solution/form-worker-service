"""
Configuration module for the Form Worker Service.

This module handles all configuration settings including SQS,
external service URLs, and application-specific settings.
"""

import os
from typing import Any

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings configuration.

    This class handles all configuration settings for the form worker service,
    including SQS, external services, and application settings.
    """

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Configuration
    app_name: str = "Henko Form Worker Service"
    debug: bool = False
    log_level: str = "INFO"

    # AWS Configuration
    # In Lambda, AWS_REGION is automatically provided by the runtime
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None  # For local development
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # SQS Configuration
    sqs_queue_url: str = ""
    sqs_max_number_of_messages: int = 10
    sqs_wait_time_seconds: int = 20

    # External Services URLs
    form_service_url: str = "http://localhost:8002"
    employee_service_url: str = "http://localhost:8001"

    # Cognito Configuration
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_client_secret: str | None = None
    cognito_system_username: str = ""
    cognito_system_password: str = ""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize settings with environment variable support."""
        super().__init__(**kwargs)
        # Override region if AWS_REGION is set (Lambda environment)
        if os.environ.get("AWS_REGION"):
            self.aws_region = os.environ["AWS_REGION"]
        # Normalize empty string to None for client_secret
        if self.cognito_client_secret == "":
            self.cognito_client_secret = None

    # Internal API Authentication (deprecated - use Cognito instead)
    internal_api_key: str = ""

    # Retry Configuration
    max_retries: int = 3
    retry_delay_seconds: int = 5

    # Batch Configuration
    assignment_batch_size: int = 100

    def __repr__(self) -> str:
        """Return string representation of settings (without sensitive data)."""
        sqs_url_repr = (
            self.sqs_queue_url[:50] + "..."
            if len(self.sqs_queue_url) > 50
            else self.sqs_queue_url
        )
        cognito_id_repr = (
            self.cognito_user_pool_id[:20] + "..."
            if len(self.cognito_user_pool_id) > 20
            else self.cognito_user_pool_id
        )
        return (
            f"Settings("
            f"app_name={self.app_name!r}, "
            f"aws_region={self.aws_region!r}, "
            f"sqs_queue_url={sqs_url_repr!r}, "
            f"form_service_url={self.form_service_url!r}, "
            f"employee_service_url={self.employee_service_url!r}, "
            f"cognito_user_pool_id={cognito_id_repr!r}, "
            f"max_retries={self.max_retries}, "
            f"assignment_batch_size={self.assignment_batch_size}"
            f")"
        )


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get global settings instance (singleton pattern).

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
