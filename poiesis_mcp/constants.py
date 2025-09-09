"""
contains configuration constants for the Poiesis TES MCP server.

All configuration values are loaded from environment variables with sensible
defaults.
"""

import os
from functools import lru_cache


class Constants:
    """
    Configuration constants for the Poiesis TES MCP server.

    All configuration values are loaded from environment variables with sensible
    defaults.
    """

    TES_URL: str | None = os.getenv("TES_URL")
    REQUEST_TOKEN: str | None = os.getenv("TES_TOKEN") or os.getenv("TES_AUTH_TOKEN")
    REQUEST_TIMEOUT: int = int(os.getenv("TES_REQUEST_TIMEOUT", "60"))
    MAX_RETRIES: int = int(os.getenv("TES_MAX_RETRIES", "3"))
    BACKOFF_FACTOR: float = float(os.getenv("TES_BACKOFF_FACTOR", "1.0"))
    MCP_HOST: str = os.getenv("MCP_HOST", "0.0.0.0")
    MCP_PORT: int = int(os.getenv("MCP_PORT", "8080"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    TASK_POLL_INTERVAL: int = int(os.getenv("TASK_POLL_INTERVAL", "5"))  # seconds
    TASK_POLL_MAX_ATTEMPTS: int = int(
        os.getenv("TASK_POLL_MAX_ATTEMPTS", "120")
    )  # 10 minutes with 5s intervals

    @classmethod
    def validate_config(cls) -> list[str]:
        """
        Validate the configuration and return a list of any issues found.

        Returns:
            List of validation error messages. Empty list if all valid.

        """
        errors: list[str] = []

        if not cls.TES_URL:
            errors.append("TES_URL environment variable is required")

        if not cls.REQUEST_TOKEN:
            errors.append(
                "TES_TOKEN environment variable should be set for secure authentication"
            )

        if cls.REQUEST_TIMEOUT <= 0:
            errors.append("TES_REQUEST_TIMEOUT must be a positive integer")

        if cls.MAX_RETRIES < 0:
            errors.append("TES_MAX_RETRIES must be a non-negative integer")

        if cls.BACKOFF_FACTOR <= 0:
            errors.append("TES_BACKOFF_FACTOR must be a positive number")

        if cls.MCP_PORT <= 0 or cls.MCP_PORT > 65535:
            errors.append("MCP_PORT must be a valid port number (1-65535)")

        if cls.TASK_POLL_INTERVAL <= 0:
            errors.append("TASK_POLL_INTERVAL must be a positive integer")

        if cls.TASK_POLL_MAX_ATTEMPTS <= 0:
            errors.append("TASK_POLL_MAX_ATTEMPTS must be a positive integer")

        return errors

    @classmethod
    def get_masked_config(cls) -> dict[str, str]:
        """
        Get configuration values with sensitive data masked for logging.

        Returns:
            Dictionary of configuration values with tokens masked.

        """
        token = cls.REQUEST_TOKEN
        masked_token = "***MASKED***" if token and token != "asdf" else token

        return {
            "TES_URL": cls.TES_URL or "NOT_SET",
            "REQUEST_TOKEN": masked_token or "NOT_SET",
            "REQUEST_TIMEOUT": str(cls.REQUEST_TIMEOUT),
            "MAX_RETRIES": str(cls.MAX_RETRIES),
            "BACKOFF_FACTOR": str(cls.BACKOFF_FACTOR),
            "MCP_HOST": cls.MCP_HOST,
            "MCP_PORT": str(cls.MCP_PORT),
            "LOG_LEVEL": cls.LOG_LEVEL,
            "TASK_POLL_INTERVAL": str(cls.TASK_POLL_INTERVAL),
            "TASK_POLL_MAX_ATTEMPTS": str(cls.TASK_POLL_MAX_ATTEMPTS),
        }


@lru_cache(maxsize=1)
def get_constants() -> Constants:
    """
    Get a cached instance of the Constants class.

    Returns:
        Constants instance with all configuration loaded.

    """
    return Constants()
