"""
Base API Interface for Trading Bot

This provides a common interface for different exchanges:
- Pionex (Spot Trading) - Current
- Binance (Futures Trading) - Future
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
import logging

class BaseTradingAPI(ABC):
    """
    Abstract base class for trading APIs
    
    This ensures all exchange implementations have the same interface,
    making it easy to switch between exchanges or add new ones.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exchange_name = "Unknown"
        self.trading_type = "Unknown"  # "SPOT" or "FUTURES"
    
    @abstractmethod
    def get_balances(self) -> Dict:
        """Get account balances"""
        pass
    
    @abstractmethod
    def get_positions(self) -> Dict:
        """Get current positions/holdings"""
        pass
    
    @abstractmethod
    def place_order(self, symbol: str, side: str, order_type: str, 
                   quantity: float, price: Optional[str] = None, **kwargs) -> Dict:
        """Place an order"""
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> Dict:
        """Get open orders"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def get_real_time_price(self, symbol: str) -> float:
        """Get real-time price for a symbol"""
        pass
    
    @abstractmethod
    def get_market_data(self, symbol: str) -> Dict:
        """Get comprehensive market data"""
        pass
    
    @abstractmethod
    def test_connection(self) -> Dict:
        """Test API connection"""
        pass
    
    def get_exchange_info(self) -> Dict:
        """Get exchange information"""
        return {
            'exchange': self.exchange_name,
            'trading_type': self.trading_type,
            'status': 'connected'
        }

class SpotTradingAPI(BaseTradingAPI):
    """
    Base class for spot trading APIs (like Pionex)
    """
    
    def __init__(self):
        super().__init__()
        self.trading_type = "SPOT"
    
    def get_spot_holdings(self) -> Dict:
        """Get spot holdings (same as positions for spot trading)"""
        return self.get_positions()
    
    def place_spot_order(self, symbol: str, side: str, order_type: str,
                        quantity: float, price: Optional[str] = None, **kwargs) -> Dict:
        """Place a spot order"""
        return self.place_order(symbol, side, order_type, quantity, price, **kwargs)

class FuturesTradingAPI(BaseTradingAPI):
    """
    Base class for futures trading APIs (like Binance Futures)
    """
    
    def __init__(self):
        super().__init__()
        self.trading_type = "FUTURES"
    
    @abstractmethod
    def get_futures_balance(self) -> Dict:
        """Get futures account balance"""
        pass
    
    @abstractmethod
    def get_futures_positions(self) -> Dict:
        """Get futures positions (leveraged)"""
        pass
    
    @abstractmethod
    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for a symbol"""
        pass
    
    @abstractmethod
    def place_futures_order(self, symbol: str, side: str, order_type: str,
                           quantity: float, price: Optional[str] = None, **kwargs) -> Dict:
        """Place a futures order"""
        pass
    
    def get_position_risk(self, symbol: str) -> Dict:
        """Get position risk metrics"""
        # Default implementation
        return {
            'symbol': symbol,
            'risk_level': 'unknown',
            'margin_ratio': 0.0,
            'unrealized_pnl': 0.0
        }

class TradingBot:
    """
    Main trading bot that can work with different exchanges
    """
    
    def __init__(self, spot_api: Optional[SpotTradingAPI] = None, 
                 futures_api: Optional[FuturesTradingAPI] = None):
        self.spot_api = spot_api
        self.futures_api = futures_api
        self.logger = logging.getLogger(__name__)
        
        # Log available trading types
        if spot_api:
            self.logger.info(f"Spot trading enabled: {spot_api.exchange_name}")
        if futures_api:
            self.logger.info(f"Futures trading enabled: {futures_api.exchange_name}")
    
    def get_spot_balances(self) -> Dict:
        """Get spot balances"""
        if not self.spot_api:
            return {'error': 'Spot trading not configured'}
        return self.spot_api.get_balances()
    
    def get_futures_balances(self) -> Dict:
        """Get futures balances"""
        if not self.futures_api:
            return {'error': 'Futures trading not configured'}
        return self.futures_api.get_futures_balance()
    
    def place_spot_order(self, symbol: str, side: str, order_type: str,
                        quantity: float, price: Optional[str] = None, **kwargs) -> Dict:
        """Place a spot order"""
        if not self.spot_api:
            return {'error': 'Spot trading not configured'}
        return self.spot_api.place_order(symbol, side, order_type, quantity, price, **kwargs)
    
    def place_futures_order(self, symbol: str, side: str, order_type: str,
                           quantity: float, price: Optional[str] = None, **kwargs) -> Dict:
        """Place a futures order"""
        if not self.futures_api:
            return {'error': 'Futures trading not configured'}
        return self.futures_api.place_futures_order(symbol, side, order_type, quantity, price, **kwargs)
    
    def get_market_price(self, symbol: str, trading_type: str = "SPOT") -> float:
        """Get market price for a symbol"""
        if trading_type == "SPOT" and self.spot_api:
            return self.spot_api.get_real_time_price(symbol)
        elif trading_type == "FUTURES" and self.futures_api:
            return self.futures_api.get_real_time_price(symbol)
        else:
            return 0.0
    
    def get_exchange_status(self) -> Dict:
        """Get status of all configured exchanges"""
        status = {
            'spot_trading': bool(self.spot_api),
            'futures_trading': bool(self.futures_api),
            'exchanges': []
        }
        
        if self.spot_api:
            status['exchanges'].append({
                'name': self.spot_api.exchange_name,
                'type': 'SPOT',
                'status': 'configured'
            })
        
        if self.futures_api:
            status['exchanges'].append({
                'name': self.futures_api.exchange_name,
                'type': 'FUTURES',
                'status': 'configured'
            })
        
        return status

# Factory function to create trading bot
def create_trading_bot(spot_api_class=None, futures_api_class=None, **kwargs):
    """
    Factory function to create a trading bot with specified APIs
    
    Args:
        spot_api_class: Class for spot trading API (e.g., PionexAPI)
        futures_api_class: Class for futures trading API (e.g., BinanceAPI)
        **kwargs: Arguments to pass to API constructors
    
    Returns:
        TradingBot instance
    """
    spot_api = None
    futures_api = None
    
    if spot_api_class:
        spot_api = spot_api_class(**kwargs)
    
    if futures_api_class:
        futures_api = futures_api_class(**kwargs)
    
    return TradingBot(spot_api=spot_api, futures_api=futures_api) 