import hashlib
import hmac
import time
import requests
import json
from typing import Dict, List, Optional
import logging

# Import the official Bybit SDK
try:
    from pybit.unified_trading import HTTP
    PYBIT_AVAILABLE = True
except ImportError:
    PYBIT_AVAILABLE = False
    print("⚠️  pybit library not installed. Installing...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pybit"])
    try:
        from pybit.unified_trading import HTTP
        PYBIT_AVAILABLE = True
        print("✅ pybit library installed successfully!")
    except ImportError:
        PYBIT_AVAILABLE = False
        print("❌ Failed to install pybit library")

logger = logging.getLogger(__name__)

class BybitAPI:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        if PYBIT_AVAILABLE:
            # Use the official pybit library
            self.session = HTTP(
                testnet=testnet,
                api_key=api_key,
                api_secret=api_secret,
            )
            logger.info("✅ Using official pybit library for API calls")
        else:
            # Fallback to manual implementation
            logger.warning("⚠️  pybit not available, using manual implementation")
        self.base_url = 'https://api-testnet.bybit.com' if testnet else 'https://api.bybit.com'
        self.session = requests.Session()
        
    def _make_request_with_pybit(self, method_name: str, **kwargs) -> Dict:
        """Make request using official pybit library"""
        try:
            method = getattr(self.session, method_name)
            response = method(**kwargs)
            
            # Log the response for debugging
            logger.info(f"Pybit API Response: {response.get('retCode', 'N/A')} - {response.get('retMsg', 'N/A')}")
            
            if response.get('retCode') == 0:
                return {'success': True, 'data': response.get('result', response)}
            else:
                return {
                    'success': False,
                    'error': response.get('retMsg', 'Unknown error'),
                    'code': response.get('retCode')
                }
        except Exception as e:
            logger.error(f"Pybit API error: {e}")
            return {'success': False, 'error': str(e)}
    
    # ===== UNIFIED TRADING API METHODS =====
    
    def place_unified_order(self, category: str, symbol: str, side: str, orderType: str, 
                           qty: str, price: str = None, timeInForce: str = "GTC", 
                           orderLinkId: str = None, isLeverage: int = 0, 
                           orderFilter: str = "Order") -> Dict:
        """Place order using unified trading API"""
        try:
            if not PYBIT_AVAILABLE:
                return {'success': False, 'error': 'pybit library not available'}
            
            # Prepare order parameters
            order_params = {
                "category": category,
                "symbol": symbol,
                "side": side,
                "orderType": orderType,
                "qty": qty,
                "timeInForce": timeInForce,
                "isLeverage": isLeverage,
                "orderFilter": orderFilter
            }
            
            # Add optional parameters
            if price:
                order_params["price"] = price
            if orderLinkId:
                order_params["orderLinkId"] = orderLinkId
            
            logger.info(f"Placing unified order: {order_params}")
            
            # Place the order
            response = self.session.place_order(**order_params)
            
            logger.info(f"Unified order response: {response}")
            
            if response.get('retCode') == 0:
                return {
                    'success': True,
                    'data': response.get('result', response),
                    'orderId': response.get('result', {}).get('orderId'),
                    'orderLinkId': response.get('result', {}).get('orderLinkId')
                }
            else:
                return {
                    'success': False,
                    'error': response.get('retMsg', 'Unknown error'),
                    'code': response.get('retCode')
                }
                
        except Exception as e:
            logger.error(f"Error placing unified order: {e}")
            return {'success': False, 'error': str(e)}
    
    def place_spot_order(self, symbol: str, side: str, orderType: str, qty: str, 
                        price: str = None, timeInForce: str = "GTC", 
                        orderLinkId: str = None) -> Dict:
        """Place spot order using unified trading API"""
        try:
            # Generate order link ID if not provided
            if not orderLinkId:
                import uuid
                orderLinkId = f"spot-{uuid.uuid4().hex[:8]}"
            
            return self.place_unified_order(
                category="spot",
                symbol=symbol,
                side=side,
                orderType=orderType,
                qty=qty,
                price=price,
                timeInForce=timeInForce,
                orderLinkId=orderLinkId,
                isLeverage=0,
                orderFilter="Order"
            )
            
        except Exception as e:
            logger.error(f"Error placing spot order: {e}")
            return {'success': False, 'error': str(e)}
    
    def place_futures_order(self, symbol: str, side: str, orderType: str, qty: str,
                           price: str = None, timeInForce: str = "GTC",
                           orderLinkId: str = None, leverage: int = 10) -> Dict:
        """Place futures order using unified trading API"""
        try:
            # Generate order link ID if not provided
            if not orderLinkId:
                import uuid
                orderLinkId = f"futures-{uuid.uuid4().hex[:8]}"
            
            # Set leverage first
            leverage_result = self.set_leverage(symbol, leverage)
            if not leverage_result.get('success'):
                logger.warning(f"Failed to set leverage: {leverage_result.get('error')}")
            
            return self.place_unified_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType=orderType,
                qty=qty,
                price=price,
                timeInForce=timeInForce,
                orderLinkId=orderLinkId,
                isLeverage=1,
                orderFilter="Order"
            )
            
        except Exception as e:
            logger.error(f"Error placing futures order: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_unified_positions(self, category: str = "linear", symbol: str = None) -> Dict:
        """Get positions using unified trading API"""
        try:
            if not PYBIT_AVAILABLE:
                return {'success': False, 'error': 'pybit library not available'}
            
            params = {"category": category}
            if symbol:
                params["symbol"] = symbol
            
            logger.info(f"Getting unified positions: {params}")
            
            response = self.session.get_positions(**params)
            
            logger.info(f"Unified positions response: {response}")
            
            if response.get('retCode') == 0:
                return {
                    'success': True,
                    'data': response.get('result', response)
                }
            else:
                return {
                    'success': False,
                    'error': response.get('retMsg', 'Unknown error'),
                    'code': response.get('retCode')
                }
                
        except Exception as e:
            logger.error(f"Error getting unified positions: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_unified_balance(self, accountType: str = "UNIFIED") -> Dict:
        """Get balance using unified trading API"""
        try:
            if not PYBIT_AVAILABLE:
                return {'success': False, 'error': 'pybit library not available'}
            
            params = {"accountType": accountType}
            
            logger.info(f"Getting unified balance: {params}")
            
            response = self.session.get_wallet_balance(**params)
            
            logger.info(f"Unified balance response: {response}")
            
            if response.get('retCode') == 0:
                return {
                    'success': True,
                    'data': response.get('result', response)
                }
            else:
                return {
                    'success': False,
                    'error': response.get('retMsg', 'Unknown error'),
                    'code': response.get('retCode')
                }
                
        except Exception as e:
            logger.error(f"Error getting unified balance: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_unified_ticker(self, category: str = "linear", symbol: str = None) -> Dict:
        """Get ticker using unified trading API"""
        try:
            if not PYBIT_AVAILABLE:
                return {'success': False, 'error': 'pybit library not available'}
            
            params = {"category": category}
            if symbol:
                params["symbol"] = symbol
            
            logger.info(f"Getting unified ticker: {params}")
            
            response = self.session.get_tickers(**params)
            
            logger.info(f"Unified ticker response: {response}")
            
            if response.get('retCode') == 0:
                return {
                    'success': True,
                    'data': response.get('result', response)
                }
            else:
                return {
                    'success': False,
                    'error': response.get('retMsg', 'Unknown error'),
                    'code': response.get('retCode')
                }
                
        except Exception as e:
            logger.error(f"Error getting unified ticker: {e}")
            return {'success': False, 'error': str(e)}
    
    def cancel_unified_order(self, category: str, symbol: str, orderId: str = None, 
                           orderLinkId: str = None) -> Dict:
        """Cancel order using unified trading API"""
        try:
            if not PYBIT_AVAILABLE:
                return {'success': False, 'error': 'pybit library not available'}
            
            if not orderId and not orderLinkId:
                return {'success': False, 'error': 'Either orderId or orderLinkId is required'}
            
            params = {
                "category": category,
                "symbol": symbol
            }
            
            if orderId:
                params["orderId"] = orderId
            if orderLinkId:
                params["orderLinkId"] = orderLinkId
            
            logger.info(f"Cancelling unified order: {params}")
            
            response = self.session.cancel_order(**params)
            
            logger.info(f"Cancel order response: {response}")
            
            if response.get('retCode') == 0:
                return {
                    'success': True,
                    'data': response.get('result', response)
                }
            else:
                return {
                    'success': False,
                    'error': response.get('retMsg', 'Unknown error'),
                    'code': response.get('retCode')
                }
                
        except Exception as e:
            logger.error(f"Error cancelling unified order: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_unified_order_history(self, category: str, symbol: str, limit: int = 50) -> Dict:
        """Get order history using unified trading API"""
        try:
            if not PYBIT_AVAILABLE:
                return {'success': False, 'error': 'pybit library not available'}
            
            params = {
                "category": category,
                "symbol": symbol,
                "limit": limit
            }
            
            logger.info(f"Getting unified order history: {params}")
            
            response = self.session.get_order_history(**params)
            
            logger.info(f"Order history response: {response}")
            
            if response.get('retCode') == 0:
                return {
                    'success': True,
                    'data': response.get('result', response)
                }
            else:
                return {
                    'success': False,
                    'error': response.get('retMsg', 'Unknown error'),
                    'code': response.get('retCode')
                }
                
        except Exception as e:
            logger.error(f"Error getting unified order history: {e}")
            return {'success': False, 'error': str(e)}
    
    def set_unified_leverage(self, category: str, symbol: str, buyLeverage: str, 
                            sellLeverage: str = None) -> Dict:
        """Set leverage using unified trading API"""
        try:
            if not PYBIT_AVAILABLE:
                return {'success': False, 'error': 'pybit library not available'}
            
            if not sellLeverage:
                sellLeverage = buyLeverage
            
            params = {
                "category": category,
                "symbol": symbol,
                "buyLeverage": buyLeverage,
                "sellLeverage": sellLeverage
            }
            
            logger.info(f"Setting unified leverage: {params}")
            
            response = self.session.set_leverage(**params)
            
            logger.info(f"Set leverage response: {response}")
            
            if response.get('retCode') == 0:
                return {
                    'success': True,
                    'data': response.get('result', response)
                }
            else:
                return {
                    'success': False,
                    'error': response.get('retMsg', 'Unknown error'),
                    'code': response.get('retCode')
                }
                
        except Exception as e:
            logger.error(f"Error setting unified leverage: {e}")
            return {'success': False, 'error': str(e)}
    
    # ===== LEGACY METHODS (KEPT FOR COMPATIBILITY) =====
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        """Make manual HTTP request to Bybit API"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {'Content-Type': 'application/json'}
            
            if signed:
                # Add authentication headers
                timestamp = str(int(time.time() * 1000))
                params = params or {}
                params['timestamp'] = timestamp
                params['api_key'] = self.api_key
                
                # Create signature
                query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                params['sign'] = signature
                headers['X-BAPI-SIGN'] = signature
                headers['X-BAPI-API-KEY'] = self.api_key
                headers['X-BAPI-TIMESTAMP'] = timestamp
            
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, headers=headers)
            else:
                response = self.session.post(url, json=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0:
                    return {'success': True, 'data': data.get('result', data)}
                else:
                    return {
                        'success': False,
                        'error': data.get('retMsg', 'Unknown error'),
                        'code': data.get('retCode')
                    }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Manual API request error: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_account_balance(self) -> Dict:
        """Get account balance"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_wallet_balance', accountType='UNIFIED')
        else:
            # Fallback to manual implementation
            return self.get_futures_balance()
    
    def get_positions(self) -> Dict:
        """Get open positions"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_positions', category='linear', settleCoin='USDT')
        else:
            # Fallback to manual implementation
            return self.get_futures_positions()
    
    def place_order(self, symbol: str, side: str, orderType: str, qty: float, 
                   price: float = None, leverage: int = 10, **kwargs) -> Dict:
        """Place order using pybit"""
        if PYBIT_AVAILABLE:
            order_params = {
                'category': 'linear',
                'symbol': symbol,
                'side': side.title(),  # "Buy" or "Sell"
                'orderType': orderType.title(),  # "Market" or "Limit"
                'qty': str(qty),
                'timeInForce': kwargs.get('timeInForce', 'GTC'),
            }
            
            # Add price for limit orders
            if price and orderType.upper() == 'LIMIT':
                order_params['price'] = str(price)
            
            # Add optional parameters
            if kwargs.get('reduceOnly'):
                order_params['reduceOnly'] = True
            if kwargs.get('closeOnTrigger'):
                order_params['closeOnTrigger'] = True
            if kwargs.get('stopLoss'):
                order_params['stopLoss'] = str(kwargs['stopLoss'])
            if kwargs.get('takeProfit'):
                order_params['takeProfit'] = str(kwargs['takeProfit'])
            
            return self._make_request_with_pybit('place_order', **order_params)
        else:
            # Fallback to manual implementation
            return self.place_futures_order(symbol, side, orderType, qty, price, leverage, **kwargs)
    
    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        """Close a specific position"""
        if PYBIT_AVAILABLE:
            # To close a position, place an opposite order with reduceOnly=True
            opposite_side = 'Sell' if side == 'Buy' else 'Buy'
            return self.place_order(
                symbol=symbol,
                side=opposite_side,
                orderType='Market',
                qty=qty,
                reduceOnly=True
            )
        else:
            # Fallback to manual implementation
            opposite_side = 'Sell' if side == 'Buy' else 'Buy'
            return self.place_futures_order(
                symbol=symbol,
                side=opposite_side,
                order_type='Market',
                qty=qty,
                reduce_only=True
            )
    
    def get_futures_ticker(self, symbol: str) -> Dict:
        """Get futures ticker data for a specific symbol"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_tickers', category='linear', symbol=symbol)
        else:
            # Fallback to manual implementation
            params = {'category': 'linear', 'symbol': symbol}
            return self._make_request('GET', '/v5/market/tickers', params)
    
    def get_futures_funding_rate(self, symbol: str) -> Dict:
        """Get futures funding rate for a specific symbol"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_funding_rate_history', category='linear', symbol=symbol, limit=1)
        else:
            # Fallback to manual implementation
            params = {'category': 'linear', 'symbol': symbol, 'limit': 1}
            return self._make_request('GET', '/v5/market/funding/history', params)
    
    def get_futures_market_status(self) -> Dict:
        """Get futures market status"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_market_status', category='linear')
        else:
            # Fallback to manual implementation
            params = {'category': 'linear'}
            return self._make_request('GET', '/v5/market/status', params)
    
    def get_futures_open_interest(self, symbol: str) -> Dict:
        """Get futures open interest for a specific symbol"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_open_interest', category='linear', symbol=symbol)
        else:
            # Fallback to manual implementation
            params = {'category': 'linear', 'symbol': symbol}
            return self._make_request('GET', '/v5/market/open-interest', params)
    
    def get_futures_market_summary(self) -> Dict:
        """Get futures market summary"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_tickers', category='linear')
        else:
            # Fallback to manual implementation
            params = {'category': 'linear'}
            return self._make_request('GET', '/v5/market/tickers', params)
    
    def get_futures_klines(self, symbol: str, interval: str = '5', limit: int = 100) -> Dict:
        """Get futures klines/candlestick data"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_kline', category='linear', symbol=symbol, interval=interval, limit=limit)
        else:
            # Fallback to manual implementation
            params = {'category': 'linear', 'symbol': symbol, 'interval': interval, 'limit': limit}
            return self._make_request('GET', '/v5/market/kline', params)
    
    def get_futures_orderbook(self, symbol: str, limit: int = 25) -> Dict:
        """Get futures order book"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_orderbook', category='linear', symbol=symbol, limit=limit)
        else:
            # Fallback to manual implementation
            params = {'category': 'linear', 'symbol': symbol, 'limit': limit}
            return self._make_request('GET', '/v5/market/orderbook', params)
    
    def get_futures_recent_trades(self, symbol: str, limit: int = 100) -> Dict:
        """Get futures recent trades"""
        if PYBIT_AVAILABLE:
            return self._make_request_with_pybit('get_public_trade_history', category='linear', symbol=symbol, limit=limit)
        else:
            # Fallback to manual implementation
            params = {'category': 'linear', 'symbol': symbol, 'limit': limit}
            return self._make_request('GET', '/v5/market/recent-trade', params)
    
    def close_futures_position(self, symbol: str, side: str, qty: float) -> Dict:
        """Close futures position"""
        if PYBIT_AVAILABLE:
            # For closing, we need to place an opposite order
            opposite_side = 'Sell' if side == 'Buy' else 'Buy'
            return self._make_request_with_pybit(
                'place_order',
                category='linear',
                symbol=symbol,
                side=opposite_side,
                orderType='Market',
                qty=str(qty),
                timeInForce='IOC'  # Immediate or Cancel
            )
        else:
            # Fallback to manual implementation
            return self.place_order(symbol, side, 'Market', qty)
    
    def close_all_positions(self) -> Dict:
        """Close all futures positions"""
        try:
            # Get all open positions
            positions_response = self.get_positions()
            if not positions_response.get('success'):
                return {'success': False, 'error': 'Failed to get positions'}
            
            positions = positions_response.get('data', {}).get('list', [])
            if not positions:
                return {'success': True, 'message': 'No positions to close'}
            
            results = []
            for position in positions:
                if float(position.get('size', 0)) > 0:
                    symbol = position.get('symbol', '')
                    side = position.get('side', '')
                    size = float(position.get('size', 0))
                    
                    if symbol and side and size > 0:
                        close_result = self.close_futures_position(symbol, side, size)
                        results.append({
            'symbol': symbol,
                            'side': side,
                            'size': size,
                            'result': close_result
                        })
            
            return {
                'success': True,
                'message': f'Closed {len(results)} positions',
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_futures_real_time_data(self, symbols: List[str] = None) -> Dict:
        """Get real-time data for multiple futures symbols"""
        if not symbols:
            symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'DOTUSDT', 'BNBUSDT']
        
        all_data = {}
        for symbol in symbols:
            try:
                # Get ticker data using pybit
                if PYBIT_AVAILABLE:
                    ticker_response = self._make_request_with_pybit('get_tickers', category='linear', symbol=symbol)
                    if ticker_response.get('success'):
                        ticker_data = ticker_response['data']
                        ticker_list = ticker_data.get('list', [])
                        if ticker_list:
                            ticker = ticker_list[0]
                            
                            # Get funding rate
                            funding_response = self._make_request_with_pybit('get_funding_rate_history', category='linear', symbol=symbol, limit=1)
                            funding_rate = 0.0
                            if funding_response.get('success'):
                                funding_data = funding_response['data']
                                funding_list = funding_data.get('list', [])
                                if funding_list:
                                    funding_rate = float(funding_list[0].get('fundingRate', 0))
                            
                            # Combine data
                            all_data[symbol] = {
            'symbol': symbol,
                                'price': float(ticker.get('lastPrice', 0)),
                                'change_24h': float(ticker.get('price24hPcnt', 0)) * 100,
                                'volume_24h': float(ticker.get('volume24h', 0)),
                                'turnover_24h': float(ticker.get('turnover24h', 0)),
                                'high_24h': float(ticker.get('highPrice24h', 0)),
                                'low_24h': float(ticker.get('lowPrice24h', 0)),
                                'funding_rate': funding_rate,
                                'open_interest': float(ticker.get('openInterest', 0)),
                                'mark_price': float(ticker.get('markPrice', 0)),
                                'index_price': float(ticker.get('indexPrice', 0)),
                                'prev_price': float(ticker.get('prevPrice24h', 0)),
                                'timestamp': ticker.get('timestamp', '')
                            }
                else:
                    # Fallback to manual implementation
                    ticker_data = self.get_futures_ticker(symbol)
                    if ticker_data.get('success'):
                        ticker = ticker_data['data']['list'][0] if ticker_data['data'].get('list') else {}
                        
                        funding_data = self.get_futures_funding_rate(symbol)
                        funding_rate = 0.0
                        if funding_data.get('success') and funding_data['data'].get('list'):
                            funding_rate = float(funding_data['data']['list'][0].get('fundingRate', 0))
                        
                        all_data[symbol] = {
            'symbol': symbol,
                            'price': float(ticker.get('lastPrice', 0)),
                            'change_24h': float(ticker.get('price24hPcnt', 0)) * 100,
                            'volume_24h': float(ticker.get('volume24h', 0)),
                            'turnover_24h': float(ticker.get('turnover24h', 0)),
                            'high_24h': float(ticker.get('highPrice24h', 0)),
                            'low_24h': float(ticker.get('lowPrice24h', 0)),
                            'funding_rate': funding_rate,
                            'open_interest': float(ticker.get('openInterest', 0)),
                            'mark_price': float(ticker.get('markPrice', 0)),
                            'index_price': float(ticker.get('indexPrice', 0)),
                            'prev_price': float(ticker.get('prevPrice24h', 0)),
                            'timestamp': ticker.get('timestamp', '')
                        }
                        
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                continue
        
        return {'success': True, 'data': all_data} 