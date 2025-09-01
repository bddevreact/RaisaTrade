#!/usr/bin/env python3
"""
Railway-Specific Fix Script
Handles all possible port scenarios and environment issues
"""

import os
import sys
import logging
import signal
import time
from pathlib import Path

# Configure logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def force_port_fix():
    """Force fix port issues by setting a valid port"""
    try:
        # Clear any problematic PORT variables
        if 'PORT' in os.environ:
            old_port = os.environ['PORT']
            logger.info(f"Clearing problematic PORT: {old_port}")
            del os.environ['PORT']
        
        # Set a valid port
        valid_port = 5000
        os.environ['PORT'] = str(valid_port)
        logger.info(f"Force set PORT to: {valid_port}")
        
        return valid_port
    except Exception as e:
        logger.error(f"Error in force_port_fix: {e}")
        return 5000

def get_railway_port():
    """Get port specifically for Railway deployment"""
    try:
        # Method 1: Check Railway's automatic port assignment
        port_str = os.environ.get('PORT')
        logger.info(f"Railway PORT env var: {port_str}")
        
        if port_str:
            try:
                port = int(port_str)
                if 1 <= port <= 65535:
                    logger.info(f"Using Railway assigned port: {port}")
                    return port
                else:
                    logger.warning(f"Invalid Railway port: {port}, using default")
            except ValueError:
                logger.warning(f"Invalid Railway port format: {port_str}, using default")
        
        # Method 2: Check for any port in environment
        for key, value in os.environ.items():
            if 'PORT' in key.upper() and value:
                try:
                    port = int(value)
                    if 1 <= port <= 65535:
                        logger.info(f"Found valid port in {key}: {port}")
                        return port
                except ValueError:
                    continue
        
        # Method 3: Use default port
        logger.info("No valid port found, using default 5000")
        return 5000
        
    except Exception as e:
        logger.error(f"Error getting Railway port: {e}")
        return 5000

def setup_railway_environment():
    """Setup environment specifically for Railway"""
    try:
        logger.info("Setting up Railway environment...")
        
        # Force fix port issues
        port = force_port_fix()
        
        # Set required environment variables
        os.environ['ENVIRONMENT'] = 'production'
        os.environ['FLASK_ENV'] = 'production'
        os.environ['PORT'] = str(port)
        
        # Generate SECRET_KEY if missing
        if not os.getenv('SECRET_KEY'):
            import secrets
            secret_key = secrets.token_hex(32)
            os.environ['SECRET_KEY'] = secret_key
            logger.info("Generated SECRET_KEY")
        
        # Log environment status
        logger.info(f"Environment setup complete. Port: {port}")
        logger.info(f"ENVIRONMENT: {os.getenv('ENVIRONMENT')}")
        logger.info(f"FLASK_ENV: {os.getenv('FLASK_ENV')}")
        logger.info(f"SECRET_KEY: {'***' if os.getenv('SECRET_KEY') else 'NOT SET'}")
        
        return True
        
    except Exception as e:
        logger.error(f"Railway environment setup failed: {e}")
        return False

def check_railway_requirements():
    """Check Railway-specific requirements"""
    try:
        # Check if we're running on Railway
        is_railway = os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID')
        logger.info(f"Running on Railway: {bool(is_railway)}")
        
        # Check required dependencies
        required_modules = ['flask', 'flask_socketio', 'requests', 'yaml', 'dotenv']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
                logger.info(f"✓ {module} available")
            except ImportError:
                missing_modules.append(module)
                logger.error(f"✗ {module} missing")
        
        if missing_modules:
            logger.error(f"Missing modules: {missing_modules}")
            return False
        
        logger.info("All Railway requirements met")
        return True
        
    except Exception as e:
        logger.error(f"Error checking Railway requirements: {e}")
        return False

def main():
    """Main entry point for Railway fix"""
    try:
        logger.info("🔧 Starting Railway Fix Script...")
        
        # Setup signal handlers
        setup_signal_handlers()
        
        # Setup Railway environment
        if not setup_railway_environment():
            logger.error("Railway environment setup failed")
            sys.exit(1)
        
        # Check Railway requirements
        if not check_railway_requirements():
            logger.error("Railway requirements check failed")
            sys.exit(1)
        
        # Import and start application
        try:
            logger.info("Importing main application...")
            from main import app, socketio
            logger.info("✅ Main application imported successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import main application: {e}")
            sys.exit(1)
        
        # Get validated port
        port = int(os.environ.get('PORT', 5000))
        host = '0.0.0.0'
        
        logger.info(f"🌐 Starting server on {host}:{port}")
        logger.info("🎯 Railway fix applied successfully!")
        logger.info("📱 Your bot should be accessible now")
        
        # Start the application
        socketio.run(
            app,
            host=host,
            port=port,
            debug=False,
            allow_unsafe_werkzeug=True,
            log_output=True
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Application stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        import traceback
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == '__main__':
    main()
