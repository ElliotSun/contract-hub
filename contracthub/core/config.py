import os
import yaml
from pathlib import Path
from typing import Any, Optional, Dict, List
import logging

LOGGER = logging.getLogger(__name__)

class ConfigManager:
    """
    Manages configuration for ContractHub.
    Resolves configuration in the following order of precedence:
    1. Explicit environment variables (if provided to get())
    2. Local configuration file (.contracthub.yaml in CWD)
    3. Global configuration file (~/.config/contracthub/config.yaml)
    """

    def __init__(self) -> None:
        self.config_data: Dict[str, Any] = {}
        self._last_cwd: Optional[Path] = None
        self._overlays: List[Dict[str, Any]] = []
        self._overlay_names: List[str] = []
        # Lazy resolution: Do not load CWD-dependent configs at import time


    def _load_configs(self) -> None:
        self._last_cwd = Path.cwd()
        # Load global first
        global_config_path = Path.home() / ".config" / "contracthub" / "config.yaml"
        if global_config_path.exists():
            try:
                with open(global_config_path, "r", encoding="utf-8") as f:
                    global_data = yaml.safe_load(f) or {}
                    self._update_nested(self.config_data, global_data)
            except Exception as e:
                LOGGER.warning(f"Failed to load global config from {global_config_path}: {e}")

        # Load local overriding global
        local_config_path = Path.cwd() / ".contracthub.yaml"
        if local_config_path.exists():
            try:
                with open(local_config_path, "r", encoding="utf-8") as f:
                    local_data = yaml.safe_load(f) or {}
                    self._update_nested(self.config_data, local_data)
            except Exception as e:
                LOGGER.warning(f"Failed to load local config from {local_config_path}: {e}")

    def load_from_path(self, path: str | Path) -> None:
        """Load configuration from a specific YAML file path, overriding current settings."""
        config_path = Path(path)
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self._update_nested(self.config_data, data)
            except Exception as e:
                LOGGER.warning(f"Failed to load custom config from {config_path}: {e}")
        else:
            LOGGER.warning(f"Custom config file not found: {config_path}")

    def update_config(self, config_dict: Dict[str, Any]) -> None:
        """Inject a dictionary of configurations directly into the manager."""
        self._update_nested(self.config_data, config_dict)

    def push_overlay(self, name: str, overlay: Dict[str, Any]) -> None:
        """Push a temporary configuration overlay. Higher precedence than base configs."""
        if name in self._overlay_names:
            self.pop_overlay(name)
        self._overlay_names.append(name)
        self._overlays.append(overlay)

    def pop_overlay(self, name: str) -> None:
        """Remove a specific configuration overlay by name."""
        try:
            idx = self._overlay_names.index(name)
            self._overlay_names.pop(idx)
            self._overlays.pop(idx)
        except ValueError:
            LOGGER.warning(f"Overlay '{name}' not found.")

    def _update_nested(self, d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = self._update_nested(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    def get(self, key_path: str, env_var: Optional[str] = None, default: Any = None) -> Any:
        """
        Get a configuration value.
        Precedence:
        1. Environment Variable (if env_var is provided and exists)
        2. Config File Value (from key_path like 'azure.auth_method')
        3. Default Value
        """
        if env_var and env_var in os.environ:
            return os.environ[env_var]
            
        if self._last_cwd is None or self._last_cwd != Path.cwd():
            self.config_data = {}

            self._load_configs()
        
        if not key_path:
            return default

        keys = key_path.split(".")
        
        # 1. Try resolving from active overlays (last pushed has highest precedence)
        for overlay in reversed(self._overlays):
            try:
                current = overlay
                for key in keys:
                    current = current[key]
                return current
            except (KeyError, TypeError):
                continue
                
        # 2. Try resolving from base config_data
        current = self.config_data
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default

# A global instance for easy import if needed
config_manager = ConfigManager()
