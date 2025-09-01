#!/usr/bin/env python3
"""
Pionex Trading Bot GUI - Main Entry Point for Render.com
Run this file to start the GUI application on Render.com
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Main entry point for the GUI on Render.com"""
    print("🚀 Starting Pionex Trading Bot GUI on Render.com...")
    
    # Render.com specific setup
    if os.environ.get('RENDER'):
        print("📦 Running on Render.com environment")
        
        # Create necessary directories for Render
        data_dir = Path("data")
        logs_dir = Path("logs")
        
        data_dir.mkdir(exist_ok=True)
        logs_dir.mkdir(exist_ok=True)
        
        print(f"📁 Data directory: {data_dir.absolute()}")
        print(f"📁 Logs directory: {logs_dir.absolute()}")
    
    # Check if we're in the right directory
    if not Path(__file__).parent.exists():
        print("❌ GUI directory not found. Please run this from the project root.")
        return 1
    
    # Import and run the GUI
    try:
        from gui_app import main as gui_main
        gui_main()
        return 0
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please ensure all dependencies are installed.")
        return 1
    except Exception as e:
        print(f"❌ Error starting GUI: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 