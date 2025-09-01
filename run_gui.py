#!/usr/bin/env python3
"""
Pionex Trading Bot GUI - Main Entry Point
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import get_config
from pionex_api import PionexAPI
# Import from local watchdog module with explicit path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from watchdog import start_watchdog, stop_watchdog, get_watchdog_status

def check_environment():
    """Check if all required environment variables are set"""
    load_dotenv()

    required_vars = [
        'PIONEX_API_KEY', 
        'PIONEX_SECRET_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file")
        return False
    
    print("✅ Environment variables check passed")
    return True

def check_api_connection():
    """Test API connection"""
    try:
        config = get_config()
        api = PionexAPI()
        
        # Test connection (only account info)
        connection_test = api.test_connection()
        
        if 'error' in connection_test:
            print(f"❌ API connection failed: {connection_test['error']}")
            return False
        
        print("✅ API connection successful")
        return True
        
    except Exception as e:
        print(f"❌ API connection error: {e}")
        return False

def setup_logging():
    """Setup logging configuration"""
    config = get_config()
    log_config = config.get('logging', {})
    
    # Create logs directory
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    file_handler = logging.FileHandler(log_config.get('file', 'logs/trading_bot.log'), encoding='utf-8')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.basicConfig(
        level=getattr(logging, log_config.get('level', 'INFO')),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[file_handler, stream_handler]
    )
    
    print("✅ Logging configured")

def check_configuration():
    """Validate configuration"""
    try:
        config = get_config()
        
        # Check required config sections
        required_sections = ['trading_pair', 'position_size', 'leverage']
        for section in required_sections:
            if section not in config:
                print(f"❌ Missing required config section: {section}")
                return False
        
        # Check trading hours configuration
        trading_hours = config.get('trading_hours', {})
        if trading_hours.get('enabled', False):
            required_hours = ['start', 'end', 'timezone']
            for hour in required_hours:
                if hour not in trading_hours:
                    print(f"❌ Missing trading hours config: {hour}")
                    return False
        
        # Check watchdog configuration
        watchdog = config.get('watchdog', {})
        if watchdog.get('enabled', False):
            required_watchdog = ['heartbeat_interval', 'max_failures', 'auto_restart']
            for wd in required_watchdog:
                if wd not in watchdog:
                    print(f"❌ Missing watchdog config: {wd}")
                    return False
        
        print("✅ Configuration validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def start_system():
    """Start the complete trading system with GUI"""
    try:
        print("🚀 Starting Pionex Trading Bot GUI System...")
        
        # Setup logging
        setup_logging()
        
        # Start watchdog if enabled
        config = get_config()
        if config.get('watchdog', {}).get('enabled', False):
            print("🔍 Starting watchdog system...")
            watchdog = start_watchdog()
            if watchdog:
                print("✅ Watchdog started successfully")
            else:
                print("❌ Failed to start watchdog")
        else:
            print("⚠️ Watchdog disabled in configuration")
        
        # Import and start GUI
        print("🌐 Starting GUI application...")
        from gui_app import main as run_gui
        run_gui()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully...")
        stop_watchdog()
        print("✅ System shutdown complete")
    except Exception as e:
        print(f"❌ System error: {e}")
        stop_watchdog()
        sys.exit(1)

def main():
    """Main entry point"""
    print("=" * 50)
    print("Pionex Trading Bot GUI System")
    print("=" * 50)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Check API connection
    if not check_api_connection():
        sys.exit(1)
    
    # Check configuration
    if not check_configuration():
        sys.exit(1)
    
    # Start system
    start_system()

if __name__ == "__main__":
    main() 