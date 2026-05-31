import os
import yaml
from pathlib import Path
from typing import Any, Optional, Dict

class ConfigManager:
    """
    Manages configuration for ContractHub.
    Resolves configuration in the following order of precedence:
    1. Explicit environment variables (if provided to get())
    2. Local configuration file (.contracthub.yaml in CWD)
    3. Global configuration file (~/.config/contracthub/config.yaml)
    """

    def __init__(self):
        self.config_data: Dict[str, Any] = {}
        self._load_configs()

    def _load_configs(self):
        # Load global first
        global_config_path = Path.home() / ".config" / "contracthub" / "config.yaml"
        if global_config_path.exists():
            try:
                with open(global_config_path, "r", encoding="utf-8") as f:
                    global_data = yaml.safe_load(f) or {}
                    self._update_nested(self.config_data, global_data)
            except Exception:
                pass # Fail silently if global config is malformed or unreadable

        # Load local overriding global
        local_config_path = Path.cwd() / ".contracthub.yaml"
        if local_config_path.exists():
            try:
                with open(local_config_path, "r", encoding="utf-8") as f:
                    local_data = yaml.safe_load(f) or {}
                    self._update_nested(self.config_data, local_data)
            except Exception:
                pass # Fail silently if local config is malformed

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
        
        if not key_path:
            return default

        keys = key_path.split(".")
        current = self.config_data
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default

# A global instance for easy import if needed
config_manager = ConfigManager()
