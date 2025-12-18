"""
Custom exceptions for the Form Worker Service.
"""


class WorkerError(Exception):
    """Base exception for worker errors."""

    def __init__(self, message: str, error_code: str = "worker_error") -> None:
        """Initialize worker error.

        Args:
            message: Error message
            error_code: Error code for identification
        """
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class EmployeeServiceError(WorkerError):
    """Error raised when Employee Service API call fails."""

    def __init__(self, message: str, error_code: str = "employee_service_error") -> None:
        """Initialize employee service error.

        Args:
            message: Error message
            error_code: Error code for identification
        """
        super().__init__(message, error_code)


class FormServiceError(WorkerError):
    """Error raised when Form Service API call fails."""

    def __init__(self, message: str, error_code: str = "form_service_error") -> None:
        """Initialize form service error.

        Args:
            message: Error message
            error_code: Error code for identification
        """
        super().__init__(message, error_code)


class ValidationError(WorkerError):
    """Error raised when event validation fails."""

    def __init__(self, message: str, error_code: str = "validation_error") -> None:
        """Initialize validation error.

        Args:
            message: Error message
            error_code: Error code for identification
        """
        super().__init__(message, error_code)
