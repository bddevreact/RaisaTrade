#!/usr/bin/env python3
"""
Alternative Railway Deployment Script
Enhanced port handling and environment validation
"""

import os
import sys
import logging
import signal
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

def get_valid_port():
    """Get and validate port from environment or use default"""
    port_str = os.environ.get('PORT')
    
    if not port_str:
        logger.info("No PORT environment variable found, using default 5000")
        return 5000
    
    try:
        port = int(port_str)
        if 1 <= port <= 65535:
            logger.info(f"Using PORT from environment: {port}")
            return port
        else:
            logger.warning(f"Invalid PORT value: {port} (out of range 1-65535), using default 5000")
            return 5000
    except ValueError:
        logger.warning(f"Invalid PORT format: '{port_str}', using default 5000")
        return 5000

def setup_environment():
    """Setup environment variables for Railway deployment"""
    try:
        # Set default values
        if not os.getenv('ENVIRONMENT'):
            os.environ['ENVIRONMENT'] = 'production'
        
        if not os.getenv('FLASK_ENV'):
            os.environ['FLASK_ENV'] = 'production'
        
        # Generate SECRET_KEY if not provided
        if not os.getenv('SECRET_KEY'):
            import secrets
            secret_key = secrets.token_hex(32)
            os.environ['SECRET_KEY'] = secret_key
            logger.info("Generated SECRET_KEY for Railway deployment")
        
        # Validate and set PORT
        port = get_valid_port()
        os.environ['PORT'] = str(port)
        
        logger.info("Environment setup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Environment setup failed: {e}")
        return False

def check_dependencies():
    """Check if all required dependencies are available"""
    try:
        import flask
        import flask_socketio
        import requests
        import yaml
        import dotenv
        logger.info("All required dependencies are available")
        return True
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return False

def main():
    """Main entry point for Railway deployment"""
    try:
        logger.info("🚀 Starting RaisaTrade Bot for Railway deployment...")
        
        # Setup signal handlers
        setup_signal_handlers()
        
        # Setup environment
        if not setup_environment():
            logger.error("Environment setup failed, exiting")
            sys.exit(1)
        
        # Check dependencies
        if not check_dependencies():
            logger.error("Dependency check failed, exiting")
            sys.exit(1)
        
        # Import main application
        try:
            from main import app, socketio
            logger.info("✅ Main application imported successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import main application: {e}")
            sys.exit(1)
        
        # Get validated port
        port = int(os.environ.get('PORT', 5000))
        host = '0.0.0.0'
        
        logger.info(f"🌐 Starting server on {host}:{port}")
        logger.info("🎯 Railway deployment ready!")
        logger.info("📱 Access your bot at: https://your-railway-app.railway.app")
        
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
