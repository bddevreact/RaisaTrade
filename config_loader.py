import yaml
import threading
import os
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Look for config.yaml in current directory (parent of gui/)
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
_config_cache = None
_config_lock = threading.Lock()

def _replace_env_vars(value):
    """Replace environment variable placeholders in config values"""
    if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
        env_var = value[2:-1]  # Remove ${ and }
        env_value = os.getenv(env_var)
        if env_value:
            return env_value
        else:
            print(f"Warning: Environment variable {env_var} not found, using placeholder")
            return value
    return value

def _process_config_dict(config_dict):
    """Recursively process config dictionary to replace environment variables"""
    if isinstance(config_dict, dict):
        for key, value in config_dict.items():
            config_dict[key] = _process_config_dict(value)
    elif isinstance(config_dict, list):
        for i, item in enumerate(config_dict):
            config_dict[i] = _process_config_dict(item)
    else:
        config_dict = _replace_env_vars(config_dict)
    return config_dict

def get_config():
    global _config_cache
    with _config_lock:
        try:
            with open(_CONFIG_PATH, 'r') as f:
                config_data = yaml.safe_load(f)
                # Process environment variables
                config_data = _process_config_dict(config_data)
                _config_cache = config_data
        except Exception as e:
            raise RuntimeError(f'Failed to load config: {e}')
        return _config_cache

def reload_config():
    global _config_cache
    with _config_lock:
        _config_cache = None
    return get_config() 