"""State persistence management utilities.

Consolidates state loading, validation, and saving logic used in both
autorate_continuous.py and steering/daemon.py. Provides base class for
unified state handling with schema validation and atomic persistence.
"""

import datetime
import fcntl
import logging
import shutil
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from .state_utils import atomic_write_json, safe_json_load_file

# Type variable for validator return types
T = TypeVar("T")

# Type alias for validator functions: takes value, returns cleaned value or raises ValueError
ValidatorFunc = Callable[[Any], T]


# =============================================================================
# COMMON STATE FIELD VALIDATORS
# =============================================================================


def non_negative_int(value: Any) -> int:
    """Validate and coerce value to non-negative integer.

    Args:
        value: Value to validate

    Returns:
        Non-negative integer (min 0)

    Example:
        >>> non_negative_int(5)
        5
        >>> non_negative_int(-3)
        0
        >>> non_negative_int("10")
        10
    """
    return max(0, int(value))


def non_negative_float(value: Any) -> float:
    """Validate and coerce value to non-negative float.

    Args:
        value: Value to validate

    Returns:
        Non-negative float (min 0.0)

    Example:
        >>> non_negative_float(3.14)
        3.14
        >>> non_negative_float(-1.5)
        0.0
    """
    return max(0.0, float(value))


def optional_positive_float(
    value: Any,
    min_val: float | None = None,
    max_val: float | None = None
) -> float | None:
    """Validate optional float with optional bounds.

    Args:
        value: Value to validate (can be None)
        min_val: Minimum allowed value (optional)
        max_val: Maximum allowed value (optional)

    Returns:
        Validated float or None if value is None

    Raises:
        ValueError: If value is out of bounds
    """
    if value is None:
        return None

    result = float(value)

    if min_val is not None and result < min_val:
        raise ValueError(f"Value {result} below minimum {min_val}")
    if max_val is not None and result > max_val:
        raise ValueError(f"Value {result} above maximum {max_val}")

    return result


def bounded_float(
    min_val: float,
    max_val: float,
    clamp: bool = True
) -> ValidatorFunc[float]:
    """Create a validator for floats within bounds.

    Args:
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        clamp: If True, clamp to bounds; if False, raise ValueError

    Returns:
        Validator function

    Example:
        >>> alpha_validator = bounded_float(0.0, 1.0)
        >>> alpha_validator(0.5)
        0.5
        >>> alpha_validator(1.5)  # clamped
        1.0
    """
    def validator(value: Any) -> float:
        result = float(value)
        if clamp:
            return max(min_val, min(max_val, result))
        if result < min_val or result > max_val:
            raise ValueError(f"Value {result} not in range [{min_val}, {max_val}]")
        return result
    return validator


def string_enum(*allowed: str) -> ValidatorFunc[str]:
    """Create a validator for string enum values.

    Args:
        *allowed: Allowed string values

    Returns:
        Validator function that returns the value if valid

    Raises:
        ValueError: If value not in allowed set

    Example:
        >>> state_validator = string_enum("GREEN", "YELLOW", "RED")
        >>> state_validator("GREEN")
        'GREEN'
    """
    allowed_set = set(allowed)

    def validator(value: Any) -> str:
        str_val = str(value)
        if str_val not in allowed_set:
            raise ValueError(f"Value '{str_val}' not in allowed set: {allowed_set}")
        return str_val
    return validator


class StateSchema:
    """Defines state structure, field names, types, and defaults."""

    def __init__(self, fields: dict[str, Any]):
        """Initialize schema with field definitions.

        Args:
            fields: Dictionary of field_name -> default_value
                   Can also use tuples: (default_value, validator_func)
                   Validator should return cleaned value or raise ValueError
        """
        self.fields = fields

    def get_defaults(self) -> dict[str, Any]:
        """Get all field defaults.

        Returns:
            Dictionary of field_name -> default_value
        """
        defaults = {}
        for name, value in self.fields.items():
            if isinstance(value, tuple):
                defaults[name] = value[0]  # First element is default
            else:
                defaults[name] = value
        return defaults

    def validate_field(self, name: str, value: Any) -> Any:
        """Validate and clean a single field value.

        Args:
            name: Field name
            value: Value to validate

        Returns:
            Cleaned/validated value

        Raises:
            ValueError: If validation fails
            KeyError: If field not in schema
        """
        if name not in self.fields:
            raise KeyError(f"Unknown field: {name}")

        field_def = self.fields[name]

        # If tuple with validator, use it
        if isinstance(field_def, tuple):
            validator = field_def[1]
            return validator(value)

        # Otherwise just validate type matches default
        if not isinstance(value, type(field_def)) and value is not None:
            try:
                return type(field_def)(value)
            except (ValueError, TypeError):
                return field_def

        return value

    def validate_state(
        self,
        state: dict[str, Any],
        logger: logging.Logger | None = None
    ) -> dict[str, Any]:
        """Validate and fill in defaults for entire state.

        Validates each field value against its schema definition:
        - Missing fields get default values
        - Existing fields are validated/cleaned via validate_field()
        - Invalid values are logged and replaced with defaults

        Args:
            state: Loaded state dictionary
            logger: Optional logger for validation warnings

        Returns:
            Validated state with all defaults applied and values cleaned
        """
        defaults = self.get_defaults()
        validated = {}

        for name, default_value in defaults.items():
            if name not in state:
                # Field missing - use default
                validated[name] = default_value
            else:
                # Field present - validate it
                try:
                    validated[name] = self.validate_field(name, state[name])
                except (ValueError, TypeError, KeyError) as e:
                    # Validation failed - log warning and use default
                    if logger:
                        logger.warning(
                            f"State field '{name}' validation failed: {e}. "
                            f"Using default: {default_value}"
                        )
                    validated[name] = default_value

        return validated


class StateManager:
    """Base class for managing application state persistence.

    Provides unified state loading, validation, and saving with:
    - Schema-based field validation
    - Atomic file writes
    - JSON serialization
    - Comprehensive error handling
    """

    def __init__(
        self,
        state_file: Path,
        schema: StateSchema,
        logger: logging.Logger,
        context: str = "state"
    ):
        """Initialize state manager.

        Args:
            state_file: Path to state file
            schema: StateSchema defining valid fields and defaults
            logger: Logger instance
            context: Context for error messages (e.g., "steering state", "autorate state")
        """
        self.state_file = state_file
        self.schema = schema
        self.logger = logger
        self.context = context
        # Initialize state with schema defaults
        self.state = self.schema.get_defaults()

    def load(self) -> bool:
        """Load state from file with validation.

        Returns:
            True if state loaded successfully
            False if file doesn't exist or load failed
        """
        if not self.state_file.exists():
            self.logger.debug(f"{self.context}: No state file, using defaults")
            self.state = self.schema.get_defaults()
            return False

        # Load JSON from file
        loaded = safe_json_load_file(
            self.state_file,
            logger=self.logger,
            default=None,
            error_context=self.context
        )

        if loaded is None:
            # JSON parsing failed - use defaults
            self.logger.warning(f"{self.context}: Failed to parse state file, using defaults")
            self.state = self.schema.get_defaults()
            return False

        # Validate and fill defaults
        try:
            self.state = self.schema.validate_state(loaded, logger=self.logger)
            self.logger.debug(f"{self.context}: Loaded state from {self.state_file}")
            return True
        except Exception as e:
            self.logger.error(f"{self.context}: Failed to validate state: {e}")
            self.state = self.schema.get_defaults()
            return False

    def save(self) -> bool:
        """Save state to file atomically.

        Returns:
            True if save succeeded
            False if save failed
        """
        try:
            atomic_write_json(self.state_file, self.state)
            self.logger.debug(f"{self.context}: Saved state to {self.state_file}")
            return True
        except Exception as e:
            self.logger.error(f"{self.context}: Failed to save state: {e}")
            return False

    def get(self, name: str, default: Any = None) -> Any:
        """Get state field value.

        Args:
            name: Field name
            default: Default if not found

        Returns:
            Field value or default
        """
        if default is None:
            default = self.schema.get_defaults().get(name)
        return self.state.get(name, default)

    def set(self, name: str, value: Any) -> None:
        """Set state field value.

        Args:
            name: Field name
            value: New value
        """
        self.state[name] = value

    def update(self, updates: dict[str, Any]) -> None:
        """Update multiple state fields at once.

        Args:
            updates: Dictionary of field_name -> value pairs
        """
        self.state.update(updates)

    def reset(self) -> None:
        """Reset state to defaults."""
        self.state = self.schema.get_defaults()

    def to_dict(self) -> dict[str, Any]:
        """Get current state as dictionary.

        Returns:
            Dictionary representation of state
        """
        return dict(self.state)


class SteeringStateManager(StateManager):
    """Specialized state manager for steering daemon.

    Extends StateManager with steering-specific functionality:
    - Deque-based bounded history (automatic eviction)
    - Legacy state name migration
    - File-level locking for concurrent access
    - State file backups (.backup and .corrupt)
    """

    # Default maximum length for history deques and transitions list.
    # Controls memory usage for long-running daemons by limiting stored history.
    DEFAULT_HISTORY_MAXLEN = 50

    def __init__(
        self,
        state_file: Path,
        schema: StateSchema,
        logger: logging.Logger,
        context: str = "steering state",
        history_maxlen: int | None = None
    ):
        """Initialize steering state manager.

        Args:
            state_file: Path to state file
            schema: StateSchema defining valid fields and defaults
            logger: Logger instance
            context: Context for error messages
            history_maxlen: Maximum length for history deques (default: DEFAULT_HISTORY_MAXLEN)
        """
        super().__init__(state_file, schema, logger, context)
        self.history_maxlen = history_maxlen if history_maxlen is not None else self.DEFAULT_HISTORY_MAXLEN

    def _backup_state_file(self, suffix: str = '.backup') -> bool:
        """Create backup copy of state file.

        Args:
            suffix: Suffix to add to backup filename

        Returns:
            True if backup succeeded, False otherwise
        """
        try:
            if not self.state_file.exists():
                return False

            backup_path = self.state_file.with_suffix(
                self.state_file.suffix + suffix
            )
            shutil.copy2(self.state_file, backup_path)
            self.logger.debug(f"Backed up state to {backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to backup state file: {e}")
            return False

    def load(self) -> bool:
        """Load state from file with validation and legacy migration.

        Handles deque conversion from JSON lists and legacy state name migration.

        Returns:
            True if state loaded successfully
            False if file doesn't exist or load failed
        """
        if not self.state_file.exists():
            self.logger.debug(f"{self.context}: No state file, using defaults")
            self.state = self.schema.get_defaults()
            return False

        # Load JSON from file
        loaded = safe_json_load_file(
            self.state_file,
            logger=self.logger,
            default=None,
            error_context=self.context
        )

        if loaded is None:
            # JSON parsing failed - backup and use defaults
            self.logger.warning(f"{self.context}: Failed to parse state file, using defaults")
            self._backup_state_file(suffix='.corrupt')
            self.state = self.schema.get_defaults()
            return False

        try:
            # Validate and fill defaults
            self.state = self.schema.validate_state(loaded, logger=self.logger)
            # Convert JSON lists back to deques for bounded history
            self._convert_lists_to_deques()
            self.logger.debug(f"{self.context}: Loaded state from {self.state_file}")
            return True
        except Exception as e:
            self.logger.error(f"{self.context}: Failed to validate state: {e}")
            self._backup_state_file(suffix='.corrupt')
            self.state = self.schema.get_defaults()
            return False

    def _convert_lists_to_deques(self) -> None:
        """Convert list-based history fields to bounded deques.

        Deques with maxlen automatically evict oldest elements when full,
        preventing unbounded growth on long-running daemons.
        Uses self.history_maxlen for the deque maximum length.
        """
        history_keys = ['history_rtt', 'history_delta', 'cake_drops_history', 'queue_depth_history']
        for key in history_keys:
            if key in self.state:
                if isinstance(self.state[key], list):
                    self.state[key] = deque(self.state[key], maxlen=self.history_maxlen)
                elif not isinstance(self.state[key], deque):
                    self.state[key] = deque(maxlen=self.history_maxlen)

    def save(self, use_lock: bool = True) -> bool:
        """Save state to file atomically with optional file locking.

        File locking prevents concurrent writes from multiple processes.
        Converts deques to lists for JSON serialization.

        Args:
            use_lock: If True, acquire lock before writing (default: True)

        Returns:
            True if save succeeded, False otherwise
        """
        try:
            # Convert deques to lists for JSON serialization
            state_to_save = dict(self.state)
            for key in ['history_rtt', 'history_delta', 'cake_drops_history', 'queue_depth_history']:
                if isinstance(state_to_save.get(key), type(state_to_save.get(key))) and hasattr(state_to_save[key], '__iter__'):
                    try:
                        state_to_save[key] = list(state_to_save[key])
                    except (TypeError, ValueError):
                        pass  # Keep as-is if conversion fails

            if not use_lock:
                # Direct write without locking
                atomic_write_json(self.state_file, state_to_save)
                self.logger.debug(f"{self.context}: Saved state to {self.state_file}")
                self._backup_state_file(suffix='.backup')
                return True

            # Write with file-level locking for concurrent access protection
            lock_path = self.state_file.with_suffix(self.state_file.suffix + '.lock')

            try:
                with open(lock_path, 'a') as lock_file:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        atomic_write_json(self.state_file, state_to_save)
                        self.logger.debug(f"{self.context}: Saved state to {self.state_file}")
                        self._backup_state_file(suffix='.backup')
                    finally:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except BlockingIOError:
                self.logger.warning(f"{self.context}: State file locked by another process, skipping save")
                return False
            except Exception as e:
                self.logger.error(f"{self.context}: Failed to acquire state file lock: {e}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"{self.context}: Failed to save state: {e}")
            return False

    def add_measurement(self, current_rtt: float, delta: float) -> None:
        """Add RTT measurement and delta to history.

        Uses deques for automatic bounded history eviction.
        No manual trim needed - deques with maxlen automatically evict oldest elements.

        Args:
            current_rtt: Current RTT measurement in milliseconds
            delta: RTT delta (current_rtt - baseline_rtt) in milliseconds
        """
        if "history_rtt" in self.state and isinstance(self.state["history_rtt"], deque):
            self.state["history_rtt"].append(current_rtt)
        if "history_delta" in self.state and isinstance(self.state["history_delta"], deque):
            self.state["history_delta"].append(delta)

    def log_transition(self, old_state: str, new_state: str) -> None:
        """Log a state transition with timestamp and counters.

        Args:
            old_state: Previous state
            new_state: New state
        """
        transition = {
            "timestamp": datetime.datetime.now().isoformat(),
            "from": old_state,
            "to": new_state,
            "bad_count": self.state.get("bad_count", 0),
            "good_count": self.state.get("good_count", 0)
        }

        if "transitions" in self.state:
            self.state["transitions"].append(transition)
            self.state["last_transition_time"] = transition["timestamp"]

            # Keep only last N transitions (matches history_maxlen for consistency)
            if len(self.state["transitions"]) > self.history_maxlen:
                self.state["transitions"] = self.state["transitions"][-self.history_maxlen:]

    def reset(self) -> None:
        """Reset state to default values."""
        self.logger.info(f"Resetting {self.context}")
        self.state = self.schema.get_defaults()
