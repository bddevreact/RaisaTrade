#!/usr/bin/env python3
"""
Pionex Trading Bot - Main Entry Point for Production
Copyright © 2025 Telegram-Airdrop-Bot
https://github.com/Telegram-Airdrop-Bot/autotradebot

Production entry point for the Pionex Trading Bot with proper
deployment settings for cloud platforms like Railway.
"""

import os
import sys
import logging
import traceback
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Environment variables loaded from .env file")
except ImportError:
    print("python-dotenv not installed, using system environment variables")
except Exception as e:
    print(f"Error loading .env file: {e}")

# Configure logging for production with ASCII-safe messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/app.log') if os.path.exists('logs') else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application for production"""
    try:
        # Ensure required directories exist
        os.makedirs('logs', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        
        logger.info("Directories created successfully")
        
        # Import Flask app with detailed error handling
        try:
            from gui_app import app, socketio
            logger.info("Flask app imported successfully")
        except ImportError as e:
            logger.error(f"Import error for Flask app: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        except Exception as e:
            logger.error(f"Error importing Flask app: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Configure for production
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        
        logger.info("Flask application created successfully")
        return app, socketio
        
    except Exception as e:
        logger.error(f"Error creating Flask application: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

# Create app instance for Railway deployment
app, socketio = create_app()

def main():
    """Main entry point for production deployment"""
    try:
        logger.info("Starting Pionex Trading Bot for Production...")
        
        # Check environment variables
        api_key = os.getenv('PIONEX_API_KEY')
        api_secret = os.getenv('PIONEX_SECRET_KEY')
        
        if not api_key or not api_secret:
            logger.error("Missing required environment variables: PIONEX_API_KEY, PIONEX_SECRET_KEY")
            logger.info("Please set these variables in your deployment environment")
            return
        
        logger.info("Environment variables check passed")
        
        # Get port from environment (for Railway and other cloud platforms)
        port_str = os.environ.get('PORT', '5000')
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                logger.warning(f"Invalid port number {port}, using default 5000")
                port = 5000
        except ValueError:
            logger.warning(f"Invalid port format '{port_str}', using default 5000")
            port = 5000
        
        host = '0.0.0.0'  # Bind to all interfaces for production
        
        logger.info(f"Starting server on {host}:{port}")
        
        # Start the application with production settings
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
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == '__main__':
    main() 