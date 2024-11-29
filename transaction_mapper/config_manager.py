import json
from typing import Dict, Any

class ConfigManager:
    """Manages global configuration settings for the accounting system."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config_data: Dict[str, Any] = {}
        self.load_config()

    def load_config(self):
        """Load configuration from a JSON file."""
        with open(self.config_path, 'r') as file:
            self.config_data = json.load(file)

    def get_accounting_rule(self, rule_key: str) -> Any:
        """Retrieve a specific accounting rule."""
        return self.config_data.get('accounting_rules', {}).get(rule_key)

    def get_country_config(self, country: str) -> Dict[str, Any]:
        """Retrieve configuration settings for a specific country."""
        return self.config_data.get('countries', {}).get(country, {})

    def update_config(self, new_config: Dict[str, Any]):
        """Update the configuration with new settings."""
        self.config_data.update(new_config)
        self.save_config()

    def save_config(self):
        """Save the current configuration to the JSON file."""
        with open(self.config_path, 'w') as file:
            json.dump(self.config_data, file, indent=4)
