"""Base configuration shared across all CAKE components."""

import yaml
from pathlib import Path
from typing import Any, Dict


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
        self.wan_name = self.data['wan_name']

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
