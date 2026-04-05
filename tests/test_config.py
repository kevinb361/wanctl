"""Tests for Config state_file path loading.

Verifies that _load_state_config() respects the YAML state_file key
when present, and falls back to lock_file-derived path for backward compat.
"""

from pathlib import Path

from wanctl.autorate_config import Config


class TestStateFileConfig:
    """Tests for _load_state_config respecting YAML state_file key."""

    def _make_config_stub(self, data: dict, lock_file: str = "/tmp/wanctl_att.lock"):
        """Create a minimal Config-like object for testing _load_state_config.

        Bypasses Config.__init__ (which requires full YAML file on disk)
        by creating an instance with just the attributes _load_state_config needs.
        """
        config = object.__new__(Config)
        config.data = data
        config.lock_file = Path(lock_file)
        return config

    def test_explicit_state_file_from_yaml(self):
        """Config with state_file in YAML uses that path."""
        config = self._make_config_stub(
            data={"state_file": "/var/lib/wanctl/spectrum_state.json"},
        )
        config._load_state_config()
        assert config.state_file == Path("/var/lib/wanctl/spectrum_state.json")

    def test_missing_state_file_falls_back_to_lock_derived(self):
        """Config without state_file falls back to lock_file-derived path."""
        config = self._make_config_stub(
            data={},
            lock_file="/tmp/wanctl_att.lock",
        )
        config._load_state_config()
        assert config.state_file == Path("/tmp/wanctl_att_state.json")

    def test_empty_string_state_file_falls_back_to_lock_derived(self):
        """Config with empty string state_file falls back to lock_file-derived path."""
        config = self._make_config_stub(
            data={"state_file": ""},
            lock_file="/tmp/wanctl_spectrum.lock",
        )
        config._load_state_config()
        assert config.state_file == Path("/tmp/wanctl_spectrum_state.json")
