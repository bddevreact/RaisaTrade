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

def validate_environment():
    """Validate and set up environment for Railway deployment"""
    try:
        # Check PORT environment variable
        port_str = os.environ.get('PORT')
        if port_str:
            try:
                port = int(port_str)
                if 1 <= port <= 65535:
                    logger.info(f"Railway PORT environment variable: {port}")
                else:
                    logger.warning(f"Invalid PORT value: {port}, using default 5000")
                    os.environ['PORT'] = '5000'
            except ValueError:
                logger.warning(f"Invalid PORT format: '{port_str}', using default 5000")
                os.environ['PORT'] = '5000'
        else:
            logger.info("No PORT environment variable found, using default 5000")
            os.environ['PORT'] = '5000'
        
        # Check other required environment variables
        required_vars = ['PIONEX_API_KEY', 'PIONEX_SECRET_KEY', 'SECRET_KEY']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
            logger.info("These can be set in Railway dashboard")
        
        # Set default values for Railway
        if not os.getenv('ENVIRONMENT'):
            os.environ['ENVIRONMENT'] = 'production'
        
        if not os.getenv('FLASK_ENV'):
            os.environ['FLASK_ENV'] = 'production'
        
        logger.info("Environment validation completed")
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
        
        # Get validated port
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
