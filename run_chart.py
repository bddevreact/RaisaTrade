#!/usr/bin/env python3
"""
Pionex Real-Time Price Chart Runner
This script installs dependencies and runs the real-time chart application.
"""

import subprocess
import sys
import os

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_chart.txt"])
        print("Dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return False
    return True

def run_chart():
    """Run the real-time chart application"""
    print("Starting Pionex Real-Time Price Chart...")
    try:
        from real_time_chart import main
        main()
    except ImportError as e:
        print(f"Error importing chart module: {e}")
        print("Please make sure all dependencies are installed.")
        return False
    except Exception as e:
        print(f"Error running chart: {e}")
        return False
    return True

def main():
    """Main function"""
    print("=== Pionex Real-Time Price Chart ===")
    print("This application shows live BTC/USDT and ETH/USDT prices from Pionex API")
    print()
    
    # Check if dependencies are installed
    try:
        import matplotlib
        import requests
        import numpy
        print("Dependencies already installed.")
    except ImportError:
        print("Installing dependencies...")
        if not install_dependencies():
            print("Failed to install dependencies. Please install manually:")
            print("pip install matplotlib requests numpy")
            return
    
    # Run the chart
    if not run_chart():
        print("Failed to run chart application.")
        return
    
    print("Chart application closed.")

if __name__ == "__main__":
    main() 