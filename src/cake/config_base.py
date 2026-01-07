"""Base configuration shared across all CAKE components."""

import re
import yaml
from typing import Any, Dict, List, Optional, Union


class ConfigValidationError(ValueError):
    """Raised when config values fail security or schema validation."""
    pass


# =============================================================================
# SCHEMA VALIDATION HELPERS
# =============================================================================

def _get_nested(data: Dict, path: str, default: Any = None) -> Any:
    """Get a nested value from a dictionary using dot notation.

    Args:
        data: Dictionary to traverse
        path: Dot-separated path (e.g., "router.host")
        default: Value to return if path not found

    Returns:
        Value at path, or default if not found
    """
    keys = path.split('.')
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _type_name(value: Any) -> str:
    """Get human-readable type name for error messages."""
    if value is None:
        return "null"
    return type(value).__name__


def validate_field(
    data: Dict,
    path: str,
    expected_type: Union[type, tuple],
    required: bool = True,
    min_val: Optional[Union[int, float]] = None,
    max_val: Optional[Union[int, float]] = None,
    choices: Optional[List] = None,
    default: Any = None
) -> Any:
    """Validate a single config field.

    Args:
        data: Full config dictionary
        path: Dot-notation path to field (e.g., "router.host")
        expected_type: Expected Python type(s)
        required: Whether field must exist
        min_val: Minimum value (for numeric types)
        max_val: Maximum value (for numeric types)
        choices: List of allowed values
        default: Default value if field is missing and not required

    Returns:
        The validated value

    Raises:
        ConfigValidationError: If validation fails
    """
    value = _get_nested(data, path)

    # Check required
    if value is None:
        if required:
            raise ConfigValidationError(f"Missing required field: {path}")
        return default

    # Check type
    # Allow int where float is expected (YAML often parses "10" as int)
    if expected_type == float and isinstance(value, int):
        value = float(value)
    elif not isinstance(value, expected_type):
        raise ConfigValidationError(
            f"Invalid type for {path}: expected {expected_type.__name__ if isinstance(expected_type, type) else expected_type}, "
            f"got {_type_name(value)}"
        )

    # Check numeric range
    if min_val is not None and value < min_val:
        raise ConfigValidationError(
            f"Value out of range for {path}: {value} < {min_val} (minimum)"
        )
    if max_val is not None and value > max_val:
        raise ConfigValidationError(
            f"Value out of range for {path}: {value} > {max_val} (maximum)"
        )

    # Check choices
    if choices is not None and value not in choices:
        raise ConfigValidationError(
            f"Invalid value for {path}: '{value}'. Must be one of: {choices}"
        )

    return value


def validate_schema(data: Dict, schema: List[Dict]) -> Dict[str, Any]:
    """Validate config data against a schema definition.

    Args:
        data: Full config dictionary to validate
        schema: List of field specifications, each containing:
            - path: Dot-notation path to field
            - type: Expected Python type
            - required: Whether field must exist (default: True)
            - min: Minimum value for numeric types
            - max: Maximum value for numeric types
            - choices: List of allowed values
            - default: Default value if missing

    Returns:
        Dictionary of validated values keyed by path

    Raises:
        ConfigValidationError: If any validation fails

    Example:
        schema = [
            {"path": "wan_name", "type": str, "required": True},
            {"path": "router.host", "type": str, "required": True},
            {"path": "bandwidth.down_max", "type": (int, float), "min": 1, "max": 10000},
            {"path": "tuning.alpha", "type": float, "min": 0.0, "max": 1.0, "default": 0.3},
        ]
        validated = validate_schema(config_data, schema)
    """
    errors = []
    validated = {}

    for field_spec in schema:
        path = field_spec["path"]
        expected_type = field_spec.get("type", str)
        required = field_spec.get("required", True)
        min_val = field_spec.get("min")
        max_val = field_spec.get("max")
        choices = field_spec.get("choices")
        default = field_spec.get("default")

        try:
            validated[path] = validate_field(
                data, path, expected_type, required, min_val, max_val, choices, default
            )
        except ConfigValidationError as e:
            errors.append(str(e))

    if errors:
        raise ConfigValidationError(
            f"Config validation failed with {len(errors)} error(s):\n  - " +
            "\n  - ".join(errors)
        )

    return validated


class BaseConfig:
    """Base configuration for CAKE system components.

    Loads YAML config and provides common fields used across all
    autorate, steering, and monitoring components.

    Subclasses should override _load_specific_fields() to handle
    component-specific configuration sections and can define
    SCHEMA class attribute for automatic validation.

    Attributes:
        data: Raw YAML data dictionary (accessible to subclasses)
        wan_name: WAN interface name (e.g., "ATT", "Spectrum")
        router_host: RouterOS IP address
        router_user: RouterOS SSH username
        ssh_key: Path to SSH private key for RouterOS authentication
    """

    # Base schema for fields present in all configs
    # Subclasses can define their own SCHEMA class attribute for additional fields
    BASE_SCHEMA = [
        {"path": "wan_name", "type": str, "required": True},
        {"path": "router.host", "type": str, "required": True},
        {"path": "router.user", "type": str, "required": True},
        {"path": "router.ssh_key", "type": str, "required": True},
    ]

    # Subclasses override this to add component-specific schema
    SCHEMA: List[Dict] = []

    def __init__(self, config_path: str):
        """Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file has invalid YAML syntax
            ConfigValidationError: If required config keys are missing or invalid
        """
        with open(config_path, 'r') as f:
            self.data = yaml.safe_load(f)

        # Validate base schema first
        self._validate_base_schema()

        # Validate component-specific schema if defined
        if self.SCHEMA:
            validate_schema(self.data, self.SCHEMA)

        # Universal fields (present in all configs) - already validated
        self.wan_name = self.validate_identifier(self.data['wan_name'], 'wan_name')

        # Router SSH configuration
        router = self.data['router']
        self.router_host = router['host']
        self.router_user = router['user']
        self.ssh_key = router['ssh_key']

        # Load component-specific fields
        self._load_specific_fields()

    def _validate_base_schema(self):
        """Validate base schema fields present in all configs."""
        validate_schema(self.data, self.BASE_SCHEMA)

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
