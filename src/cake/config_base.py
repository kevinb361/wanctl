"""Base configuration shared across all CAKE components."""

import re
import yaml
from pathlib import Path
from typing import Any, Dict


class ConfigValidationError(ValueError):
    """Raised when config values fail security validation."""
    pass


class BaseConfig:
    """Base configuration for CAKE system components.

    Loads YAML config and provides common fields used across all
    autorate, steering, and monitoring components.

    Subclasses should override _load_specific_fields() to handle
    component-specific configuration sections.

    Attributes:
        data: Raw YAML data dictionary (accessible to subclasses)
        wan_name: WAN interface name (e.g., "ATT", "Spectrum")
        router_host: RouterOS IP address
        router_user: RouterOS SSH username
        ssh_key: Path to SSH private key for RouterOS authentication
    """

    def __init__(self, config_path: str):
        """Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file has invalid YAML syntax
            KeyError: If required config keys are missing
        """
        with open(config_path, 'r') as f:
            self.data = yaml.safe_load(f)

        # Universal fields (present in all configs)
        self.wan_name = self.validate_identifier(self.data['wan_name'], 'wan_name')

        # Router SSH configuration
        router = self.data['router']
        self.router_host = router['host']
        self.router_user = router['user']
        self.ssh_key = router['ssh_key']

        # Load component-specific fields
        self._load_specific_fields()

    def _load_specific_fields(self):
        """Override in subclasses to load component-specific config.

        Subclasses should:
        1. Extract their YAML sections (queues, thresholds, etc.)
        2. Set component-specific attributes
        3. Perform any derived field computation

        This method is called automatically during __init__.

        Example:
            class AutorateConfig(BaseConfig):
                def _load_specific_fields(self):
                    # Extract autorate-specific fields
                    self.queue_down = self.data['queues']['download']
                    self.queue_up = self.data['queues']['upload']
                    # ...
        """
        pass

    # =========================================================================
    # Security validation methods for values used in RouterOS commands
    # =========================================================================

    # Pattern for safe RouterOS identifiers (queue names, interface names, etc.)
    # Allows: alphanumeric, dash, underscore, dot (for interface names like ether1.100)
    _SAFE_IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+$')

    # Pattern for safe mangle rule comments
    # Allows: alphanumeric, dash, underscore, space, colon (for "ADAPTIVE: ..." comments)
    _SAFE_COMMENT_PATTERN = re.compile(r'^[A-Za-z0-9_.\-: ]+$')

    @classmethod
    def validate_identifier(cls, value: str, field_name: str) -> str:
        """Validate a value is safe for use as a RouterOS identifier.

        Used for: queue names, interface names, wan_name, etc.

        Args:
            value: The value to validate
            field_name: Name of the config field (for error messages)

        Returns:
            The validated value (unchanged if valid)

        Raises:
            ConfigValidationError: If value contains unsafe characters
        """
        if not isinstance(value, str):
            raise ConfigValidationError(
                f"{field_name}: expected string, got {type(value).__name__}"
            )
        if not value:
            raise ConfigValidationError(f"{field_name}: cannot be empty")
        if len(value) > 64:
            raise ConfigValidationError(
                f"{field_name}: too long ({len(value)} chars, max 64)"
            )
        if not cls._SAFE_IDENTIFIER_PATTERN.match(value):
            raise ConfigValidationError(
                f"{field_name}: contains invalid characters: '{value}'. "
                f"Only alphanumeric, dash, underscore, and dot allowed."
            )
        return value

    @classmethod
    def validate_comment(cls, value: str, field_name: str) -> str:
        """Validate a value is safe for use in a RouterOS mangle rule comment.

        Args:
            value: The value to validate
            field_name: Name of the config field (for error messages)

        Returns:
            The validated value (unchanged if valid)

        Raises:
            ConfigValidationError: If value contains unsafe characters
        """
        if not isinstance(value, str):
            raise ConfigValidationError(
                f"{field_name}: expected string, got {type(value).__name__}"
            )
        if not value:
            raise ConfigValidationError(f"{field_name}: cannot be empty")
        if len(value) > 128:
            raise ConfigValidationError(
                f"{field_name}: too long ({len(value)} chars, max 128)"
            )
        if not cls._SAFE_COMMENT_PATTERN.match(value):
            raise ConfigValidationError(
                f"{field_name}: contains invalid characters: '{value}'. "
                f"Only alphanumeric, dash, underscore, space, colon, and dot allowed."
            )
        return value
