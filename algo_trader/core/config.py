"""
Configuration management for Algo Trader
"""
import os
import yaml
from pathlib import Path
from cryptography.fernet import Fernet
from loguru import logger


class Config:
    """Handles application configuration and secure credential storage"""

    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".algo_trader"
        self.config_file = self.config_dir / "config.yaml"
        self.key_file = self.config_dir / ".key"
        self._config = {}
        self._cipher = None

        self._init_config_dir()
        self._init_encryption()
        self._load_config()

    def _init_config_dir(self):
        """Create config directory if it doesn't exist"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _init_encryption(self):
        """Initialize encryption for storing sensitive data"""
        if not self.key_file.exists():
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            # Set restrictive permissions
            os.chmod(self.key_file, 0o600)

        key = self.key_file.read_bytes()
        self._cipher = Fernet(key)

    def _load_config(self):
        """Load configuration from file"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._default_config()
            self._save_config()

    def _save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)

    def _default_config(self) -> dict:
        """Return default configuration"""
        return {
            'app': {
                'name': 'Algo Trader',
                'version': '1.0.0',
                'log_level': 'INFO'
            },
            'brokers': {},
            'trading': {
                'default_quantity': 1,
                'max_positions': 10,
                'risk_percent': 2.0
            },
            'chartink': {
                'enabled': False,
                'scan_interval': 60
            }
        }

    def get(self, key: str, default=None):
        """Get a configuration value using dot notation (e.g., 'app.name')"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value):
        """Set a configuration value using dot notation"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value
        self._save_config()

    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self._cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        try:
            return self._cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ""

    def save_broker_credentials(self, broker: str, api_key: str, api_secret: str, **kwargs):
        """Securely save broker API credentials"""
        creds = {
            'api_key': self.encrypt(api_key),
            'api_secret': self.encrypt(api_secret)
        }
        # Encrypt any additional credentials
        for key, value in kwargs.items():
            if value:
                creds[key] = self.encrypt(str(value))

        self.set(f'brokers.{broker}', creds)
        logger.info(f"Saved credentials for {broker}")

    def get_broker_credentials(self, broker: str) -> dict:
        """Retrieve and decrypt broker credentials"""
        creds = self.get(f'brokers.{broker}', {})
        if not creds:
            return {}

        decrypted = {}
        for key, value in creds.items():
            try:
                decrypted[key] = self.decrypt(value)
            except:
                decrypted[key] = value
        return decrypted

    def list_configured_brokers(self) -> list:
        """List all brokers with saved credentials"""
        brokers = self.get('brokers', {})
        return list(brokers.keys())
