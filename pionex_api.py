import requests
import hmac
import hashlib
import time
import json
import logging
from typing import Dict, List, Optional
from urllib.parse import urlencode
import random
import os
from dotenv import load_dotenv

from config_loader import get_config

load_dotenv()  # Load .env variables

class PionexAPI:
    def __init__(self):
        self.api_key = os.getenv('PIONEX_API_KEY')
        self.secret_key = os.getenv('PIONEX_SECRET_KEY')
        self.config = get_config()
        self.base_url = "https://api.pionex.com"
        self.retry_attempts = self.config.get('api', {}).get('retry_attempts', 3)
        self.retry_backoff = self.config.get('api', {}).get('retry_backoff', 1.5)
        self.timeout = self.config.get('api', {}).get('timeout', 30)
        self.request_count = 0
        self.last_request_time = 0
        self.rate_limit_delay = 0.1
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PionexTradingBot/1.0'
        })

    def _rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()
        self.request_count += 1

    def _generate_signature(self, params: Dict) -> str:
        try:
            sorted_params = dict(sorted(params.items()))
            query_string = urlencode(sorted_params)
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return signature
        except Exception as e:
            self.logger.error(f"Error generating signature: {e}")
            raise

    def _make_request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        import json as pyjson
        url = f"{self.base_url}{endpoint}"
        self._rate_limit()
        if params is None:
            params = {}
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'PionexTradingBot/1.0'
        }
        body = ''
        if signed:
            # Get exact server timestamp
            server_timestamp = self._get_exact_server_timestamp()
            params['timestamp'] = str(server_timestamp)
            sorted_items = sorted(params.items())
            query_string = '&'.join(f'{k}={v}' for k, v in sorted_items)
            path_url = f"{endpoint}?{query_string}" if query_string else endpoint
            sign_str = f"{method.upper()}{path_url}"
            if method.upper() in ['POST', 'DELETE']:
                # For POST requests, include timestamp in body for signature
                body = pyjson.dumps(params, separators=(',', ':')) if params else ''
                sign_str += body
            signature = hmac.new(self.secret_key.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
            headers['PIONEX-KEY'] = self.api_key
            headers['PIONEX-SIGNATURE'] = signature
        # Debug logging (only in debug mode)
        if os.getenv('DEBUG', 'False').lower() == 'true':
            self.logger.debug(f"Request: {method.upper()} {url}")
            self.logger.debug(f"Headers: {headers}")
            if method.upper() == 'GET':
                self.logger.debug(f"Params: {params}")
            else:
                self.logger.debug(f"Body: {pyjson.dumps(params, separators=(',', ':')) if params else ''}")
        last_exception = None
        for attempt in range(self.retry_attempts):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                elif method.upper() == 'POST':
                    # For POST requests, include timestamp in URL for Pionex API
                    if signed and 'timestamp' in params:
                        url_with_params = f"{url}?timestamp={params['timestamp']}"
                        # Keep timestamp in body for POST
                        body = pyjson.dumps(params, separators=(',', ':')) if params else ''
                    else:
                        url_with_params = url
                        body = pyjson.dumps(params, separators=(',', ':')) if params else ''
                    response = self.session.post(url_with_params, data=body, headers=headers, timeout=self.timeout)
                elif method.upper() == 'DELETE':
                    response = self.session.delete(url, data=pyjson.dumps(params), headers=headers, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                if response.status_code == 200:
                    data = response.json()
                    if 'code' in data and data['code'] != 0:
                        error_msg = data.get('msg', 'Unknown API error')
                        self.logger.error(f"API error: {error_msg} (code: {data['code']})")
                        return {'error': error_msg, 'code': data['code']}
                    return data
                elif response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                elif response.status_code >= 500:
                    self.logger.warning(f"Server error {response.status_code}, attempt {attempt + 1}/{self.retry_attempts}")
                    if attempt < self.retry_attempts - 1:
                        time.sleep(self.retry_backoff ** attempt)
                    continue
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    self.logger.error(error_msg)
                    return {'error': error_msg}
            except requests.exceptions.Timeout:
                last_exception = f"Request timeout (attempt {attempt + 1}/{self.retry_attempts})"
                self.logger.warning(last_exception)
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_backoff ** attempt)
                continue
            except requests.exceptions.ConnectionError as e:
                last_exception = f"Connection error: {e} (attempt {attempt + 1}/{self.retry_attempts})"
                self.logger.warning(last_exception)
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_backoff ** attempt)
                continue
            except Exception as e:
                last_exception = f"Request error: {e} (attempt {attempt + 1}/{self.retry_attempts})"
                self.logger.error(last_exception)
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_backoff ** attempt)
                continue
        return {'error': f"All retry attempts failed. Last error: {last_exception}"}

    def _get_exact_server_timestamp(self) -> int:
        """Get exact server timestamp in milliseconds"""
        try:
            # Get server time from the ticker endpoint (public)
            response = self.session.get(f"{self.base_url}/api/v1/market/tickers", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'timestamp' in data['data']:
                    return data['data']['timestamp']  # Return as milliseconds
                elif 'timestamp' in data:
                    return data['timestamp']  # Return as milliseconds
        except Exception as e:
            self.logger.warning(f"Failed to get server time from ticker: {e}")
        
        # Fallback to local time in milliseconds
        return int(time.time() * 1000)

    # --- Account Endpoints ---
    def get_balances(self) -> Dict:
        """GET /api/v1/account/balances"""
        return self._make_request('GET', '/api/v1/account/balances', signed=True)

    def get_assets(self) -> Dict:
        """GET /api/v1/account/assets"""
        return self._make_request('GET', '/api/v1/account/assets', signed=True)

    def get_positions(self) -> Dict:
        """GET /api/v1/account/balances (as a proxy for positions)"""
        return self._make_request('GET', '/api/v1/account/balances', signed=True)

    # --- Order Endpoints ---
    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: str = None, client_order_id: str = None, **kwargs) -> Dict:
        """POST /api/v1/trade/order"""
        params = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
            'size': str(quantity)  # Use 'size' instead of 'quantity'
        }
        if price:
            params['price'] = price
        if client_order_id:
            params['clientOrderId'] = client_order_id
        params.update(kwargs)
        return self._make_request('POST', '/api/v1/trade/order', params, signed=True)

    def get_order(self, order_id: int, symbol: str) -> Dict:
        """GET /api/v1/trade/order"""
        params = {'orderId': order_id, 'symbol': symbol}
        return self._make_request('GET', '/api/v1/trade/order', params, signed=True)

    def get_order_by_client_order_id(self, client_order_id: str, symbol: str) -> Dict:
        """GET /api/v1/trade/orderByClientOrderId"""
        params = {'clientOrderId': client_order_id, 'symbol': symbol}
        return self._make_request('GET', '/api/v1/trade/orderByClientOrderId', params, signed=True)

    def cancel_order(self, order_id: int, symbol: str) -> Dict:
        """DELETE /api/v1/trade/order"""
        params = {'orderId': order_id, 'symbol': symbol}
        return self._make_request('DELETE', '/api/v1/trade/order', params, signed=True)

    def get_open_orders(self, symbol: str = None) -> Dict:
        """GET /api/v1/trade/openOrders"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._make_request('GET', '/api/v1/trade/openOrders', params, signed=True)

    def get_all_orders(self, symbol: str = None, limit: int = 100) -> Dict:
        """GET /api/v1/trade/allOrders"""
        params = {'limit': limit}
        if symbol:
            params['symbol'] = symbol
        return self._make_request('GET', '/api/v1/trade/allOrders', params, signed=True)

    # --- Fills (Trade History) Endpoints ---
    def get_fills(self, symbol: str = None, order_id: int = None) -> Dict:
        """GET /api/v1/trade/fills"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        if order_id:
            params['orderId'] = order_id
        return self._make_request('GET', '/api/v1/trade/fills', params, signed=True)

    # --- Grid Trading Endpoints ---
    def create_grid_bot(self, symbol: str, params: Dict) -> Dict:
        """POST /api/v1/grid/order"""
        params['symbol'] = symbol
        return self._make_request('POST', '/api/v1/grid/order', params, signed=True)

    def get_grid_bot(self, grid_id: str) -> Dict:
        """GET /api/v1/grid/order"""
        params = {'gridId': grid_id}
        return self._make_request('GET', '/api/v1/grid/order', params, signed=True)

    def stop_grid_bot(self, grid_id: str) -> Dict:
        """POST /api/v1/grid/order/stop"""
        params = {'gridId': grid_id}
        return self._make_request('POST', '/api/v1/grid/order/stop', params, signed=True)

    def list_grid_bots(self) -> Dict:
        """GET /api/v1/grid/order/list"""
        return self._make_request('GET', '/api/v1/grid/order/list', signed=True)

    # --- Market Data Endpoints (Public) ---
    def get_symbols(self) -> Dict:
        """GET /api/v1/common/symbols"""
        return self._make_request('GET', '/api/v1/common/symbols')

    def get_klines(self, symbol: str, interval: str = '1H', limit: int = 100) -> Dict:
        """GET /api/v1/market/klines"""
        # Convert interval format to match Pionex API requirements
        interval_map = {
            '1m': '1M',
            '5m': '5M',
            '15m': '15M',
            '30m': '30M',
            '1h': '1H',
            '4h': '4H',
            '8h': '8H',
            '12h': '12H',
            '1d': '1D'
        }

        # Convert interval to proper format
        api_interval = interval_map.get(interval.lower(), interval.upper())

        params = {
            'symbol': symbol,
            'interval': api_interval,
            'limit': min(limit, 500)  # Ensure limit doesn't exceed 500
        }

        response = self._make_request('GET', '/api/v1/market/klines', params)

        # Handle the response structure according to documentation
        if 'data' in response and isinstance(response['data'], dict) and 'klines' in response['data']:
            return response
        elif 'data' in response and isinstance(response['data'], list):
            # If data is directly a list, wrap it in the expected format
            return {
                'result': True,
                'data': {'klines': response['data']},
                'timestamp': response.get('timestamp', int(time.time() * 1000))
            }

        return response

    def get_ticker(self, symbol: str = None) -> Dict:
        """GET /api/v1/market/tickers"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._make_request('GET', '/api/v1/market/tickers', params)

    def get_depth(self, symbol: str, limit: int = 100) -> Dict:
        """GET /api/v1/market/depth"""
        params = {'symbol': symbol, 'limit': limit}
        return self._make_request('GET', '/api/v1/market/depth', params)

    def get_trades(self, symbol: str, limit: int = 100) -> Dict:
        """GET /api/v1/market/trades"""
        params = {'symbol': symbol, 'limit': limit}
        
        # Add debug logging (only in debug mode)
        if os.getenv('DEBUG', 'False').lower() == 'true':
            self.logger.debug(f"Fetching trades for {symbol} with limit {limit}")
        else:
            self.logger.info(f"Fetching trades for {symbol} with limit {limit}")
        
        response = self._make_request('GET', '/api/v1/market/trades', params)
        
        # Log the response for debugging (only in debug mode)
        if os.getenv('DEBUG', 'False').lower() == 'true':
            self.logger.debug(f"Trades response for {symbol}: {response}")
        
        return response

    def get_ticker_price(self, symbol: str) -> Dict:
        """Get current ticker price for a symbol"""
        params = {'symbol': symbol}
        response = self._make_request('GET', '/api/v1/market/tickers', params)

        if 'error' in response:
            return response

        if 'data' in response and isinstance(response['data'], dict) and 'tickers' in response['data']:
            for ticker in response['data']['tickers']:
                if isinstance(ticker, dict) and ticker.get('symbol') == symbol:
                    return {'data': {'price': ticker.get('close', '0')}}

        # If not found in list, return error
        return {'error': f"Symbol {symbol} not found in ticker data"}

    def get_real_time_price(self, symbol: str) -> Dict:
        """Get real-time price for a symbol (alias for get_ticker_price)"""
        return self.get_ticker_price(symbol)

    def get_trading_pairs(self) -> Dict:
        """Get trading pairs"""
        return self._make_request('GET', '/api/v1/market/symbols')

    def get_account_info(self) -> Dict:
        """Get account information - uses balances as a proxy for account status"""
        try:
            # Use get_balances as a proxy for account info since Pionex doesn't have a dedicated account info endpoint
            balances_response = self.get_balances()
            
            if 'error' in balances_response:
                return {'error': balances_response['error']}
            
            # Extract account info from balances response
            account_info = {
                'status': 'success',
                'data': {
                    'account_status': 'active',
                    'balances_count': len(balances_response.get('data', {}).get('balances', [])),
                    'last_updated': int(time.time() * 1000)
                }
            }
            
            return account_info
            
        except Exception as e:
            return {'error': f'Failed to get account info: {str(e)}'}

    def get_account_balance(self) -> Dict:
        """Get account balance in a format expected by the GUI"""
        try:
            balances_response = self.get_balances()
            
            if 'error' in balances_response:
                return balances_response
            
            # Process balances to extract USDT balance
            balances = balances_response.get('data', {}).get('balances', [])
            total_balance = 0
            available_balance = 0
            frozen_balance = 0
            
            for balance in balances:
                # Pionex uses 'coin' instead of 'currency'
                coin = balance.get('coin', balance.get('currency', ''))
                if coin == 'USDT':
                    # Pionex uses 'free' and 'frozen' instead of 'available' and 'frozen'
                    available_balance = float(balance.get('free', balance.get('available', 0)))
                    frozen_balance = float(balance.get('frozen', 0))
                    total_balance = available_balance + frozen_balance
                    break
            
            return {
                'total': total_balance,
                'available': available_balance,
                'frozen': frozen_balance,
                'currency': 'USDT'
            }
            
        except Exception as e:
            return {'error': f'Failed to get account balance: {str(e)}'}

    def test_connection(self) -> Dict:
        try:
            balance = self.get_balances()
            if 'error' in balance:
                return {'error': f"Authentication error: {balance['error']}"}
            return {'status': 'connected'}
        except Exception as e:
            return {'error': f"Connection test failed: {str(e)}"}

    def place_market_order(self, symbol: str, side: str, quantity: float, **kwargs) -> Dict:
        """Place market order with enhanced parameters"""
        return self.place_order(symbol, side, 'MARKET', quantity, **kwargs)
    
    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float, **kwargs) -> Dict:
        """Place limit order with enhanced parameters"""
        return self.place_order(symbol, side, 'LIMIT', quantity, str(price), **kwargs)
    
    def place_stop_loss_order(self, symbol: str, side: str, quantity: float, stop_price: float, **kwargs) -> Dict:
        """Place stop loss order"""
        params = {
            'activationPrice': str(stop_price),
            'workingType': 'MARK_PRICE'
        }
        params.update(kwargs)
        return self.place_order(symbol, side, 'STOP_MARKET', quantity, **params)
    
    def place_take_profit_order(self, symbol: str, side: str, quantity: float, take_profit_price: float, **kwargs) -> Dict:
        """Place take profit order"""
        params = {
            'activationPrice': str(take_profit_price),
            'workingType': 'MARK_PRICE'
        }
        params.update(kwargs)
        return self.place_order(symbol, side, 'TAKE_PROFIT_MARKET', quantity, **params)
    
    def place_trailing_stop_order(self, symbol: str, side: str, quantity: float, callback_rate: float, **kwargs) -> Dict:
        """Place trailing stop order"""
        params = {
            'callbackRate': str(callback_rate),
            'workingType': 'MARK_PRICE'
        }
        params.update(kwargs)
        return self.place_order(symbol, side, 'TRAILING_STOP_MARKET', quantity, **params)
    
    def place_ioc_order(self, symbol: str, side: str, quantity: float, price: float = None, **kwargs) -> Dict:
        """Place Immediate or Cancel (IOC) order"""
        params = {'IOC': True}
        params.update(kwargs)
        
        if price:
            return self.place_order(symbol, side, 'LIMIT', quantity, str(price), **params)
        else:
            return self.place_order(symbol, side, 'MARKET', quantity, **params)
    
    def place_fok_order(self, symbol: str, side: str, quantity: float, price: float, **kwargs) -> Dict:
        """Place Fill or Kill (FOK) order"""
        params = {'FOK': True}
        params.update(kwargs)
        return self.place_order(symbol, side, 'LIMIT', quantity, str(price), **params)

    def _convert_symbol_format(self, symbol: str) -> str:
        """Convert symbol format for Pionex API compatibility"""
        # Remove any existing underscore
        clean_symbol = symbol.replace('_', '')
        
        # Add underscore before USDT, USDC, BUSD, etc.
        if clean_symbol.endswith('USDT'):
            return clean_symbol[:-4] + '_USDT'
        elif clean_symbol.endswith('USDC'):
            return clean_symbol[:-4] + '_USDC'
        elif clean_symbol.endswith('BUSD'):
            return clean_symbol[:-4] + '_BUSD'
        elif clean_symbol.endswith('BTC'):
            return clean_symbol[:-3] + '_BTC'
        elif clean_symbol.endswith('ETH'):
            return clean_symbol[:-3] + '_ETH'
        else:
            # If no known suffix, return as is
            return symbol

    def get_live_trades(self, symbol: str, limit: int = 50) -> Dict:
        """Get live trades for a symbol"""
        try:
            # Convert symbol format if needed
            formatted_symbol = self._convert_symbol_format(symbol)
            
            trades_response = self.get_trades(formatted_symbol, limit)
            
            if 'error' in trades_response:
                self.logger.error(f"Error getting trades for {symbol}: {trades_response['error']}")
                return {'error': trades_response['error']}
            
            # Handle different response formats
            trades = []
            if 'data' in trades_response:
                if isinstance(trades_response['data'], list):
                    trades = trades_response['data']
                elif isinstance(trades_response['data'], dict):
                    # If data is a dict, look for trades array
                    if 'trades' in trades_response['data']:
                        trades = trades_response['data']['trades']
                    else:
                        trades = [trades_response['data']]  # Single trade
            
            # Format trades for GUI
            formatted_trades = []
            for trade in trades:
                if isinstance(trade, dict):
                    formatted_trade = {
                        'id': trade.get('id', trade.get('tradeId', '')),
                        'price': float(trade.get('price', 0)),
                        'quantity': float(trade.get('qty', trade.get('quantity', 0))),
                        'side': trade.get('side', 'UNKNOWN'),
                        'time': trade.get('time', int(time.time() * 1000)),
                        'symbol': symbol
                    }
                    formatted_trades.append(formatted_trade)
            
            return {
                'success': True,
                'data': {
                    'trades': formatted_trades,
                    'symbol': symbol,
                    'count': len(formatted_trades),
                    'timestamp': int(time.time() * 1000)
                }
            }
                
        except Exception as e:
            self.logger.error(f"Error getting live trades for {symbol}: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {
                    'trades': [],
                    'symbol': symbol,
                    'count': 0,
                    'timestamp': int(time.time() * 1000)
                }
            }

    def get_market_depth(self, symbol: str, limit: int = 20) -> Dict:
        """Get market depth (order book) for a symbol"""
        try:
            depth_response = self.get_depth(symbol, limit)
            
            if 'error' in depth_response:
                return {'error': depth_response['error']}
            
            if 'data' in depth_response:
                depth_data = depth_response['data']
                return {
                    'symbol': symbol,
                    'bids': depth_data.get('bids', []),
                    'asks': depth_data.get('asks', []),
                    'timestamp': depth_data.get('timestamp', int(time.time() * 1000))
                }
            else:
                return {'error': 'No depth data available'}
                
        except Exception as e:
            self.logger.error(f"Error getting market depth for {symbol}: {e}")
            return {'error': str(e)}

    def get_24hr_ticker(self, symbol: str = None) -> Dict:
        """Get 24-hour ticker statistics"""
        try:
            if symbol:
                ticker_response = self.get_ticker(symbol)
            else:
                ticker_response = self.get_ticker()
            
            if 'error' in ticker_response:
                return {'error': ticker_response['error']}
            
            if 'data' in ticker_response:
                return {
                    'data': ticker_response['data'],
                    'timestamp': int(time.time() * 1000)
                }
            else:
                return {'error': 'No ticker data available'}
                
        except Exception as e:
            self.logger.error(f"Error getting 24hr ticker: {e}")
            return {'error': str(e)}

    def get_klines_realtime(self, symbol: str, interval: str = '1m', limit: int = 100) -> Dict:
        """Get real-time klines/candlestick data"""
        try:
            klines_response = self.get_klines(symbol, interval, limit)
            
            if 'error' in klines_response:
                return {'error': klines_response['error']}
            
            if 'data' in klines_response:
                klines_data = klines_response['data']
                return {
                    'symbol': symbol,
                    'interval': interval,
                    'klines': klines_data,
                    'count': len(klines_data),
                    'timestamp': int(time.time() * 1000)
                }
            else:
                return {'error': 'No klines data available'}
                
        except Exception as e:
            self.logger.error(f"Error getting real-time klines for {symbol}: {e}")
            return {'error': str(e)}

    def get_real_time_market_data(self, symbol: str) -> Dict:
        """Get comprehensive real-time market data including price, volume, 24h change"""
        try:
            # Get ticker data
            ticker_response = self.get_ticker(symbol)
            
            if 'error' in ticker_response:
                return {'error': ticker_response['error']}
            
            # Handle different response formats
            ticker_data = None
            
            if 'data' in ticker_response:
                if isinstance(ticker_response['data'], dict):
                    # If data is a dict, it might contain tickers array
                    if 'tickers' in ticker_response['data']:
                        # Find the specific symbol in tickers array
                        for ticker in ticker_response['data']['tickers']:
                            if isinstance(ticker, dict) and ticker.get('symbol') == symbol:
                                ticker_data = ticker
                                break
                    else:
                        # Data might be the ticker itself
                        ticker_data = ticker_response['data']
                elif isinstance(ticker_response['data'], list):
                    # If data is a list, find the specific symbol
                    for ticker in ticker_response['data']:
                        if isinstance(ticker, dict) and ticker.get('symbol') == symbol:
                            ticker_data = ticker
                            break
            
            if not ticker_data:
                # Try to get basic price data as fallback
                price_response = self.get_ticker_price(symbol)
                if 'data' in price_response and 'price' in price_response['data']:
                    current_price = float(price_response['data']['price'])
                    return {
                        'symbol': symbol,
                        'price': current_price,
                        'volume': 0,
                        'quoteVolume': 0,
                        'priceChange': 0,
                        'priceChangePercent': 0,
                        'high': current_price,
                        'low': current_price,
                        'open': current_price,
                        'close': current_price,
                        'timestamp': int(time.time() * 1000)
                    }
                else:
                    return {'error': 'No data available'}
            
            return {
                'symbol': symbol,
                'price': float(ticker_data.get('price', ticker_data.get('close', 0))),
                'volume': float(ticker_data.get('volume', 0)),
                'quoteVolume': float(ticker_data.get('quoteVolume', 0)),
                'priceChange': float(ticker_data.get('priceChange', 0)),
                'priceChangePercent': float(ticker_data.get('priceChangePercent', 0)),
                'high': float(ticker_data.get('high', 0)),
                'low': float(ticker_data.get('low', 0)),
                'open': float(ticker_data.get('open', 0)),
                'close': float(ticker_data.get('close', 0)),
                'timestamp': int(ticker_data.get('closeTime', time.time() * 1000))
            }
                
        except Exception as e:
            self.logger.error(f"Error getting real-time market data for {symbol}: {e}")
            return {'error': str(e)} 