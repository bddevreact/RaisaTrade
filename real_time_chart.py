import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import threading
import time
import requests
import json
from typing import Dict, List
import numpy as np

class PionexRealTimeChart:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Pionex Real-Time Price Chart")
        self.root.geometry("1200x800")
        
        # API configuration
        self.base_url = "https://api.pionex.com/api/v1"
        self.symbols = ["BTC_USDT", "ETH_USDT"]
        self.colors = ["#FF6B6B", "#4ECDC4"]  # Red for BTC, Teal for ETH
        
        # Data storage
        self.price_data = {symbol: {"timestamps": [], "prices": []} for symbol in self.symbols}
        self.max_data_points = 100
        
        # Setup UI
        self.setup_ui()
        
        # Start real-time updates
        self.running = True
        self.update_thread = threading.Thread(target=self.update_prices, daemon=True)
        self.update_thread.start()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Pionex Real-Time Price Chart", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Symbol selection
        ttk.Label(control_frame, text="Symbols:").pack(side=tk.LEFT, padx=(0, 5))
        self.symbol_var = tk.StringVar(value="BTC_USDT,ETH_USDT")
        symbol_entry = ttk.Entry(control_frame, textvariable=self.symbol_var, width=30)
        symbol_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Update interval
        ttk.Label(control_frame, text="Update Interval (seconds):").pack(side=tk.LEFT, padx=(0, 5))
        self.interval_var = tk.StringVar(value="5")
        interval_entry = ttk.Entry(control_frame, textvariable=self.interval_var, width=5)
        interval_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Start/Stop button
        self.start_stop_var = tk.StringVar(value="Stop Updates")
        self.start_stop_btn = ttk.Button(control_frame, textvariable=self.start_stop_var, 
                                        command=self.toggle_updates)
        self.start_stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Status label
        self.status_var = tk.StringVar(value="Status: Initializing...")
        status_label = ttk.Label(control_frame, textvariable=self.status_var)
        status_label.pack(side=tk.RIGHT)
        
        # Chart frame
        chart_frame = ttk.Frame(main_frame)
        chart_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(12, 8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Price display frame
        price_frame = ttk.Frame(main_frame)
        price_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Price labels
        self.price_labels = {}
        for i, symbol in enumerate(self.symbols):
            frame = ttk.Frame(price_frame)
            frame.pack(side=tk.LEFT, padx=(0, 20))
            
            ttk.Label(frame, text=f"{symbol}:", font=("Arial", 12, "bold")).pack()
            self.price_labels[symbol] = ttk.Label(frame, text="Loading...", 
                                                 font=("Arial", 14), foreground=self.colors[i])
            self.price_labels[symbol].pack()
        
        # Last update time
        self.last_update_var = tk.StringVar(value="Last Update: Never")
        ttk.Label(price_frame, textvariable=self.last_update_var).pack(side=tk.RIGHT)
        
    def get_ticker_price(self, symbol: str) -> Dict:
        """Get current ticker price from Pionex API"""
        try:
            url = f"{self.base_url}/market/tickers"
            params = {"symbol": symbol}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('result') and 'data' in data:
                return data['data']
            else:
                return {"price": "0"}
                
        except Exception as e:
            print(f"Error getting price for {symbol}: {e}")
            return {"price": "0"}
    
    def get_klines_data(self, symbol: str, interval: str = "1M", limit: int = 50) -> List:
        """Get historical klines data from Pionex API"""
        try:
            url = f"{self.base_url}/market/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('result') and 'data' in data:
                return data['data'].get('klines', [])
            else:
                return []
                
        except Exception as e:
            print(f"Error getting klines for {symbol}: {e}")
            return []
    
    def update_prices(self):
        """Update prices in real-time"""
        while self.running:
            try:
                current_time = datetime.now()
                
                # Get current prices for all symbols
                for symbol in self.symbols:
                    ticker_data = self.get_ticker_price(symbol)
                    price = float(ticker_data.get('price', 0))
                    
                    if price > 0:
                        # Update price data
                        self.price_data[symbol]["timestamps"].append(current_time)
                        self.price_data[symbol]["prices"].append(price)
                        
                        # Keep only last max_data_points
                        if len(self.price_data[symbol]["timestamps"]) > self.max_data_points:
                            self.price_data[symbol]["timestamps"] = self.price_data[symbol]["timestamps"][-self.max_data_points:]
                            self.price_data[symbol]["prices"] = self.price_data[symbol]["prices"][-self.max_data_points:]
                        
                        # Update price label
                        self.root.after(0, lambda s=symbol, p=price: self.update_price_label(s, p))
                
                # Update chart
                self.root.after(0, self.update_chart)
                
                # Update status
                self.root.after(0, lambda: self.status_var.set(f"Status: Updated at {current_time.strftime('%H:%M:%S')}"))
                self.root.after(0, lambda: self.last_update_var.set(f"Last Update: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"))
                
                # Wait for next update
                interval = int(self.interval_var.get())
                time.sleep(interval)
                
            except Exception as e:
                print(f"Error in update loop: {e}")
                time.sleep(5)
    
    def update_price_label(self, symbol: str, price: float):
        """Update price label in UI"""
        if symbol in self.price_labels:
            formatted_price = f"${price:,.2f}"
            self.price_labels[symbol].config(text=formatted_price)
    
    def update_chart(self):
        """Update the chart with current data"""
        try:
            self.ax.clear()
            
            # Plot data for each symbol
            for i, symbol in enumerate(self.symbols):
                if len(self.price_data[symbol]["timestamps"]) > 0:
                    timestamps = self.price_data[symbol]["timestamps"]
                    prices = self.price_data[symbol]["prices"]
                    
                    # Convert timestamps to datetime objects if they're strings
                    if isinstance(timestamps[0], str):
                        timestamps = [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in timestamps]
                    
                    self.ax.plot(timestamps, prices, 
                               color=self.colors[i], 
                               linewidth=2, 
                               label=symbol.replace('_', '/'),
                               alpha=0.8)
            
            # Customize chart
            self.ax.set_title("Pionex Real-Time Price Chart", fontsize=16, fontweight='bold')
            self.ax.set_xlabel("Time", fontsize=12)
            self.ax.set_ylabel("Price (USDT)", fontsize=12)
            self.ax.grid(True, alpha=0.3)
            self.ax.legend()
            
            # Format x-axis
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            self.ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
            plt.setp(self.ax.xaxis.get_majorticklabels(), rotation=45)
            
            # Auto-scale y-axis
            self.ax.autoscale_view()
            
            # Tight layout
            self.fig.tight_layout()
            
            # Update canvas
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error updating chart: {e}")
    
    def toggle_updates(self):
        """Toggle start/stop updates"""
        if self.running:
            self.running = False
            self.start_stop_var.set("Start Updates")
            self.status_var.set("Status: Updates Stopped")
        else:
            self.running = True
            self.start_stop_var.set("Stop Updates")
            self.status_var.set("Status: Updates Running")
            # Restart update thread
            self.update_thread = threading.Thread(target=self.update_prices, daemon=True)
            self.update_thread.start()
    
    def on_closing(self):
        """Handle window closing"""
        self.running = False
        self.root.destroy()
    
    def run(self):
        """Start the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

def main():
    """Main function"""
    app = PionexRealTimeChart()
    app.run()

if __name__ == "__main__":
    main() 