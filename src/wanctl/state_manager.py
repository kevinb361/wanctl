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
from pathlib import Path
from typing import Any, Dict

from .state_utils import atomic_write_json, safe_json_load_file


class StateSchema:
    """Defines state structure, field names, types, and defaults."""

    def __init__(self, fields: Dict[str, Any]):
        """Initialize schema with field definitions.

        Args:
            fields: Dictionary of field_name -> default_value
                   Can also use tuples: (default_value, validator_func)
                   Validator should return cleaned value or raise ValueError
        """
        self.fields = fields

    def get_defaults(self) -> Dict[str, Any]:
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

    def validate_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fill in defaults for entire state.

        Args:
            state: Loaded state dictionary

        Returns:
            Validated state with all defaults applied
        """
        defaults = self.get_defaults()

        # Ensure all required fields exist
        for name, default_value in defaults.items():
            if name not in state:
                state[name] = default_value

        return state


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
            self.state = self.schema.validate_state(loaded)
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

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple state fields at once.

        Args:
            updates: Dictionary of field_name -> value pairs
        """
        self.state.update(updates)

    def reset(self) -> None:
        """Reset state to defaults."""
        self.state = self.schema.get_defaults()

    def to_dict(self) -> Dict[str, Any]:
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

    def __init__(
        self,
        state_file: Path,
        schema: StateSchema,
        logger: logging.Logger,
        context: str = "steering state",
        history_maxlen: int = 50
    ):
        """Initialize steering state manager.

        Args:
            state_file: Path to state file
            schema: StateSchema defining valid fields and defaults
            logger: Logger instance
            context: Context for error messages
            history_maxlen: Maximum length for history deques (default: 50)
        """
        super().__init__(state_file, schema, logger, context)
        self.history_maxlen = history_maxlen

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
            self.state = self.schema.validate_state(loaded)
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

            # Keep only last 50 transitions
            if len(self.state["transitions"]) > 50:
                self.state["transitions"] = self.state["transitions"][-50:]

    def reset(self) -> None:
        """Reset state to default values."""
        self.logger.info(f"Resetting {self.context}")
        self.state = self.schema.get_defaults()
