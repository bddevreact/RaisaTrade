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

def _validate_port(port_str):
    """Validate port number and return valid port or default"""
    if not port_str:
        return '5000'
    
    try:
        port = int(port_str)
        if 1 <= port <= 65535:
            return str(port)
        else:
            print(f"Warning: Invalid port number {port} (out of range 1-65535), using default 5000")
            return '5000'
    except ValueError:
        print(f"Warning: Invalid port format '{port_str}', using default 5000")
        return '5000'

def _replace_env_vars(value):
    """Replace environment variable placeholders in config values"""
    if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
        env_var = value[2:-1]  # Remove ${ and }
        
        # Special handling for PORT variable
        if env_var == 'PORT':
            port = os.getenv('PORT', '5000')
            return _validate_port(port)
        
        # Special handling for SECRET_KEY variable
        if env_var == 'SECRET_KEY':
            secret_key = os.getenv('SECRET_KEY')
            if secret_key:
                return secret_key
            else:
                # Generate a fallback secret key if not provided
                import secrets
                fallback_key = secrets.token_hex(32)
                print(f"Warning: SECRET_KEY not found, using generated fallback key")
                return fallback_key
        
        # Handle other environment variables
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