#!/usr/bin/env python3
"""
Railway Deployment Startup Script
Optimized for Railway cloud platform deployment
"""

import os
import sys
import logging
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

def validate_port(port_str):
    """Validate port number and return valid port or default"""
    if not port_str:
        logger.info("No PORT environment variable found, using default 5000")
        return 5000
    
    try:
        port = int(port_str)
        if 1 <= port <= 65535:
            logger.info(f"Valid PORT environment variable: {port}")
            return port
        else:
            logger.warning(f"Invalid PORT value: {port} (out of range 1-65535), using default 5000")
            return 5000
    except ValueError:
        logger.warning(f"Invalid PORT format: '{port_str}', using default 5000")
        return 5000

def validate_environment():
    """Validate and set up environment for Railway deployment"""
    try:
        # Check and validate PORT environment variable
        port_str = os.environ.get('PORT')
        validated_port = validate_port(port_str)
        
        # Set validated port back to environment
        os.environ['PORT'] = str(validated_port)
        
        # Check other required environment variables
        required_vars = ['PIONEX_API_KEY', 'PIONEX_SECRET_KEY', 'SECRET_KEY']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
            logger.info("These can be set in Railway dashboard")
            
            # Generate fallback SECRET_KEY if missing
            if 'SECRET_KEY' in missing_vars:
                import secrets
                fallback_key = secrets.token_hex(32)
                os.environ['SECRET_KEY'] = fallback_key
                logger.info("Generated fallback SECRET_KEY for Railway deployment")
        
        # Set default values for Railway
        if not os.getenv('ENVIRONMENT'):
            os.environ['ENVIRONMENT'] = 'production'
        
        if not os.getenv('FLASK_ENV'):
            os.environ['FLASK_ENV'] = 'production'
        
        logger.info(f"Environment validation completed. Port: {validated_port}")
        return True
        
    except Exception as e:
        logger.error(f"Environment validation failed: {e}")
        return False

def main():
    """Main entry point for Railway deployment"""
    try:
        logger.info("Starting RaisaTrade Bot for Railway deployment...")
        
        # Validate environment
        if not validate_environment():
            logger.error("Environment validation failed, exiting")
            sys.exit(1)
        
        # Import and start the main application
        try:
            from main import app, socketio
            logger.info("Main application imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import main application: {e}")
            sys.exit(1)
        
        # Get validated port from environment
        port = int(os.environ.get('PORT', 5000))
        host = '0.0.0.0'
        
        logger.info(f"Starting server on {host}:{port}")
        logger.info("Railway deployment ready!")
        
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
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == '__main__':
    main()
