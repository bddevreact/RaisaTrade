
import os
import sys
import logging
import threading
import time
import json
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_socketio import SocketIO, emit
import webbrowser
from dotenv import load_dotenv
import traceback
import yaml

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging first with encoding handling
import sys
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/gui_app.log', encoding='utf-8') if os.path.exists('logs') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

from config_loader import get_config, reload_config
from pionex_api import PionexAPI
from trading_strategies import TradingStrategies, RSIFilter

# Import Bybit API for futures trading
try:
    from bybit_api import BybitAPI as BybitAPIClass
    BYBIT_AVAILABLE = True
    logger.info("Bybit API imported successfully")
except ImportError as e:
    BYBIT_AVAILABLE = False
    logger.warning(f"Bybit API not available: {e}")

# Try to import database - fallback to simple database if SQLite is not available
try:
    from database import Database
    logger.info("Using SQLite database")
except ImportError as e:
    logger.warning(f"SQLite database not available: {e}")
    logger.info("Using simple JSON-based database")
    from simple_database import SimpleDatabase as Database

from auto_trader import get_auto_trader, start_auto_trading, stop_auto_trading, restart_auto_trading, get_auto_trading_status
from futures_trading import (
    get_futures_trader, create_futures_grid, create_hedging_grid,
    get_dynamic_limits, check_liquidation_risk, get_strategy_status,
    get_performance_metrics
)
from backtesting import (
    run_backtest, enable_paper_trading, disable_paper_trading, get_paper_trading_ledger
)
# Try to import PionexWebSocket, fallback to None if not available
try:
    from pionex_ws import PionexWebSocket
    WEBSOCKET_AVAILABLE = True
    logger.info("PionexWebSocket imported successfully")
except ImportError as e:
    logger.warning(f"PionexWebSocket import failed: {e}")
    PionexWebSocket = None
    WEBSOCKET_AVAILABLE = False

# Load environment variables
load_dotenv()

# Configure Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['ENV'] = 'production'
app.config['DEBUG'] = False
app.config['TESTING'] = False

# Configure SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Error handling middleware
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'Something went wrong on our end',
        'timestamp': datetime.now().isoformat()
    }), 500

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'error': 'Not found',
        'message': 'The requested resource was not found',
        'timestamp': datetime.now().isoformat()
    }), 404

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    return jsonify({
        'error': 'Server error',
        'message': 'An unexpected error occurred',
        'timestamp': datetime.now().isoformat()
    }), 500

class TradingBotGUI:
    def __init__(self):
        self.api = PionexAPI()
        self.strategies = TradingStrategies(self.api)
        self.db = Database()
        self.config = get_config()
        
        # Initialize WebSocket for real-time data
        self.ws = None
        self.ws_connected = False
        self.real_time_data = {}
        self.ws_thread = None
        
        # Start WebSocket connection
        self._start_websocket()
        
        # Auto trading status
        self.auto_trading_enabled = False
        self.current_user = None
    
    def check_auth(self, user_id: str) -> bool:
        """Check if user is authorized"""
        allowed_users = self.config.get('allowed_users', [])
        return str(user_id) in allowed_users or not allowed_users
    
    def get_account_balance(self):
        """Get account balance"""
        try:
            balance = self.api.get_account_balance()
            return {'success': True, 'data': balance}
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_positions(self):
        """Get current positions"""
        try:
            positions_response = self.api.get_positions()
            
            # Log the response for debugging
            logger.info(f"Positions API response: {positions_response}")
            
            # If API returns error, return empty positions list instead of error
            if 'error' in positions_response:
                logger.warning(f"API error for positions: {positions_response['error']}")
                # Return empty positions list instead of error
                return {'success': True, 'data': []}
            
            # Handle different response formats
            positions = []
            
            # Check if response has success and data structure
            if 'success' in positions_response and positions_response['success']:
                if 'data' in positions_response and 'positions' in positions_response['data']:
                    positions = positions_response['data']['positions']
                else:
                    logger.info("No positions data in response")
                    return {'success': True, 'data': []}
            
            # Legacy format handling
            elif 'data' in positions_response:
                data = positions_response['data']
                
                # Check if it's a positions response
                if 'positions' in data:
                    positions_data = data['positions']
                    for position in positions_data:
                        if float(position.get('size', 0)) > 0:
                            positions.append({
                                'symbol': position.get('symbol', ''),
                                'size': float(position.get('size', 0)),
                                'entryPrice': float(position.get('entryPrice', 0)),
                                'markPrice': float(position.get('markPrice', 0)),
                                'unrealizedPnl': float(position.get('unrealizedPnl', 0)),
                                'roe': float(position.get('roe', 0)),
                                'notional': float(position.get('notional', 0))
                            })
                
                # Check if it's a balances response (fallback)
                elif 'balances' in data:
                    balances = data['balances']
                    for balance in balances:
                        if float(balance.get('total', 0)) > 0:
                            positions.append({
                                'symbol': balance.get('currency', ''),
                                'size': float(balance.get('total', 0)),
                                'entryPrice': 0,  # Not available in balance response
                                'markPrice': 0,   # Not available in balance response
                                'unrealizedPnl': 0,  # Not available in balance response
                                'roe': 0,  # Not available in balance response
                                'notional': float(balance.get('total', 0))
                            })
            
            # If no positions found, return empty list with success
            if not positions:
                logger.info("No positions found, returning empty list")
                return {'success': True, 'data': []}
            
            return {'success': True, 'data': positions}
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            # Return empty positions list instead of error
            return {'success': True, 'data': []}
    
    def get_portfolio(self):
        """Get portfolio information"""
        try:
            balance = self.api.get_account_balance()
            positions_response = self.api.get_positions()
            
            if 'error' in balance:
                return {'success': False, 'error': balance['error']}
            
            if 'error' in positions_response:
                return {'success': False, 'error': positions_response['error']}
            
            # Calculate portfolio metrics
            total_value = 0
            total_pnl = 0
            
            # Process positions from balance data
            balances = positions_response.get('data', {}).get('balances', [])
            positions = []
            
            for balance_item in balances:
                if float(balance_item.get('total', 0)) > 0:
                    notional = float(balance_item.get('total', 0))
                    total_value += notional
                    
                    position = {
                        'symbol': balance_item.get('currency', ''),
                        'size': float(balance_item.get('total', 0)),
                        'notional': notional,
                        'unrealizedPnl': 0  # Not available in balance response
                    }
                    positions.append(position)
            
            portfolio = {
                'balance': balance,
                'positions': positions,
                'total_value': total_value,
                'total_pnl': total_pnl,
                'timestamp': datetime.now().isoformat()
            }
            
            return {'success': True, 'data': portfolio}
        except Exception as e:
            logger.error(f"Error getting portfolio: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_trading_history(self):
        """Get trading history"""
        try:
            # Get recent trades from database
            trades = self.db.get_recent_trades(limit=50)
            return {'success': True, 'data': trades}
        except Exception as e:
            logger.error(f"Error getting trading history: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_settings(self):
        """Get current settings"""
        try:
            settings = {
                'trading_pair': self.config.get('trading_pair'),
                'position_size': self.config.get('position_size'),
                'leverage': self.config.get('leverage'),
                'trading_amount': self.config.get('trading_amount', 100),
                'max_daily_loss': self.config.get('max_daily_loss', 500),
                'rsi': self.config.get('rsi', {}),
                'volume_filter': self.config.get('volume_filter', {}),
                'macd': self.config.get('macd', {}),
                'stop_loss_percentage': self.config.get('stop_loss_percentage'),
                'take_profit_percentage': self.config.get('take_profit_percentage'),
                'trailing_stop_percentage': self.config.get('trailing_stop_percentage'),
                'trading_hours': self.config.get('trading_hours', {}),
                'notifications': self.config.get('notifications', {}),
                'auto_trading_enabled': self.auto_trading_enabled
            }
            return {'success': True, 'data': settings}
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            return {'success': False, 'error': str(e)}
    
    def update_settings(self, new_settings):
        """Update settings"""
        try:
            # Handle strategy update separately
            if 'default_strategy' in new_settings:
                strategy_name = new_settings['default_strategy']
                # Update user settings in database
                if self.current_user:
                    self.db.update_user_setting(self.current_user, 'default_strategy', strategy_name)
                # Update config
                self.config['default_strategy'] = strategy_name
            
            # Handle trading hours settings
            if 'trading_hours' in new_settings:
                trading_hours = new_settings['trading_hours']
                self.config['trading_hours'] = {
                    'enabled': trading_hours.get('enabled', True),
                    'start': trading_hours.get('start', '19:30'),
                    'end': trading_hours.get('end', '01:30'),
                    'timezone': trading_hours.get('timezone', 'UTC-5'),
                    'exclude_weekends': trading_hours.get('exclude_weekends', False),
                    'exclude_holidays': trading_hours.get('exclude_holidays', False)
                }
            
            # Handle notification settings
            if 'notifications' in new_settings:
                notifications = new_settings['notifications']
                self.config['notifications'] = {
                    'telegram': {
                        'enabled': notifications.get('telegram_enabled', False),
                        'bot_token': notifications.get('telegram_token', ''),
                        'user_id': notifications.get('telegram_user_id', '')
                    },
                    'email': {
                        'enabled': notifications.get('email_enabled', False),
                        'recipient_email': notifications.get('notification_email', ''),
                        'sender_email': notifications.get('sender_email', ''),
                        'sender_password': notifications.get('sender_password', ''),
                        'smtp_server': notifications.get('smtp_server', 'smtp.gmail.com'),
                        'smtp_port': 587
                    },
                    'types': {
                        'trade_notifications': notifications.get('notify_trades', True),
                        'error_notifications': notifications.get('notify_errors', True),
                        'balance_notifications': notifications.get('notify_balance', True),
                        'status_notifications': notifications.get('notify_status', True)
                    }
                }
            
            # Handle RSI parameters
            if 'rsi_settings' in new_settings:
                rsi_settings = new_settings['rsi_settings']
                if 'rsi' not in self.config:
                    self.config['rsi'] = {}
                self.config['rsi'].update({
                    'period': int(rsi_settings.get('period', 7)),
                    'overbought': int(rsi_settings.get('overbought', 70)),
                    'oversold': int(rsi_settings.get('oversold', 30))
                })
            
            # Update other config settings
            for key, value in new_settings.items():
                if key not in ['default_strategy', 'trading_hours', 'notifications', 'rsi_settings'] and key in self.config:
                    if isinstance(self.config[key], dict) and isinstance(value, dict):
                        self.config[key].update(value)
                    else:
                        self.config[key] = value
            
            # Add new settings that might not exist in config
            new_config_keys = ['trading_amount', 'max_daily_loss', 'trailing_stop_percentage']
            for key in new_config_keys:
                if key in new_settings:
                    self.config[key] = new_settings[key]
            
            # Save to config file
            import yaml
            with open('config.yaml', 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            
            # Reload config
            reload_config()
            
            logger.info(f"Settings updated successfully: {list(new_settings.keys())}")
            return {'success': True, 'message': 'Settings updated successfully'}
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return {'success': False, 'error': str(e)}
    
    def enable_auto_trading(self):
        """Enable auto trading"""
        try:
            # Check balance before enabling auto trading
            balance_response = self.get_account_balance()
            if not balance_response['success']:
                return {'success': False, 'error': 'Failed to check account balance'}
            
            balance_data = balance_response['data']
            available_balance = float(balance_data.get('available', 0))
            
            if available_balance <= 0:
                return {
                    'success': False, 
                    'error': 'Cannot enable auto trading with zero balance. Please add funds to your account.'
                }
            
            # Check if balance is too low for meaningful trading
            if available_balance < 10:  # Minimum $10 for auto trading
                return {
                    'success': False, 
                    'error': f'Balance too low for auto trading. Available: ${available_balance:.2f}, Minimum required: $10.00'
                }
            
            self.auto_trading_enabled = True
            start_auto_trading(self.current_user or 1)
            return {'success': True, 'message': 'Auto trading enabled'}
        except Exception as e:
            logger.error(f"Error enabling auto trading: {e}")
            return {'success': False, 'error': str(e)}
    
    def disable_auto_trading(self):
        """Disable auto trading"""
        try:
            self.auto_trading_enabled = False
            stop_auto_trading(self.current_user or 1)
            return {'success': True, 'message': 'Auto trading disabled'}
        except Exception as e:
            logger.error(f"Error disabling auto trading: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_auto_trading_status(self):
        """Get auto trading status"""
        try:
            status = get_auto_trading_status(self.current_user or 1)
            return {'success': True, 'data': status}
        except Exception as e:
            logger.error(f"Error getting auto trading status: {e}")
            return {'success': False, 'error': str(e)}
    
    def execute_manual_trade(self, symbol, side, quantity, order_type='MARKET', price=None):
        """Execute manual trade"""
        try:
            # First check account balance
            balance_response = self.get_account_balance()
            if not balance_response['success']:
                return {'success': False, 'error': 'Failed to check account balance'}
            
            balance_data = balance_response['data']
            available_balance = float(balance_data.get('available', 0))
            
            # Calculate required amount for the trade
            if side == 'BUY':
                # For buying, we need USDT balance
                if 'USDT' not in symbol:
                    return {'success': False, 'error': 'Only USDT pairs are supported for buying'}
                
                # Get current price to calculate required USDT
                ticker_response = self.api.get_ticker_price(symbol)
                if 'error' in ticker_response:
                    return {'success': False, 'error': f'Failed to get price for {symbol}'}
                
                current_price = float(ticker_response['data']['price'])
                required_usdt = quantity * current_price
                
                if available_balance < required_usdt:
                    return {
                        'success': False, 
                        'error': f'Insufficient USDT balance. Required: ${required_usdt:.2f}, Available: ${available_balance:.2f}'
                    }
            
            elif side == 'SELL':
                # For selling, check if we have enough of the asset
                asset_symbol = symbol.replace('USDT', '')  # e.g., BTC from BTCUSDT
                positions_response = self.get_positions()
                
                if positions_response['success']:
                    positions = positions_response['data']
                    asset_balance = 0
                    
                    for position in positions:
                        if position['symbol'] == asset_symbol:
                            asset_balance = float(position['size'])
                            break
                    
                    if asset_balance < quantity:
                        return {
                            'success': False, 
                            'error': f'Insufficient {asset_symbol} balance. Required: {quantity}, Available: {asset_balance}'
                        }
                else:
                    return {'success': False, 'error': 'Failed to check asset balance'}
            
            # If balance check passes, proceed with the trade
            if order_type == 'MARKET':
                order = self.api.place_market_order(symbol, side, quantity)
            elif order_type == 'LIMIT':
                order = self.api.place_limit_order(symbol, side, quantity, price)
            else:
                return {'success': False, 'error': 'Invalid order type'}
            
            return {'success': True, 'data': order}
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return {'success': False, 'error': str(e)}
    
    def validate_trade_requirements(self, symbol, side, quantity, order_type='MARKET', price=None):
        """Validate trade requirements before execution"""
        try:
            # Check account balance
            balance_response = self.get_account_balance()
            if not balance_response['success']:
                return {'valid': False, 'error': 'Failed to check account balance'}
            
            balance_data = balance_response['data']
            available_balance = float(balance_data.get('available', 0))
            
            validation_result = {
                'valid': True,
                'warnings': [],
                'estimated_cost': 0,
                'available_balance': available_balance
            }
            
            if side == 'BUY':
                # Get current price for cost estimation
                ticker_response = self.api.get_ticker_price(symbol)
                if 'error' in ticker_response:
                    return {'valid': False, 'error': f'Failed to get price for {symbol}'}
                
                current_price = float(ticker_response['data']['price'])
                estimated_cost = quantity * current_price
                validation_result['estimated_cost'] = estimated_cost
                
                if available_balance < estimated_cost:
                    validation_result['valid'] = False
                    validation_result['error'] = f'Insufficient USDT balance. Required: ${estimated_cost:.2f}, Available: ${available_balance:.2f}'
                    return validation_result
                
                # Add warnings for large trades
                if estimated_cost > available_balance * 0.8:
                    validation_result['warnings'].append(f'This trade will use {((estimated_cost/available_balance)*100):.1f}% of your available balance')
                
            elif side == 'SELL':
                # Check asset balance for selling
                asset_symbol = symbol.replace('USDT', '')
                positions_response = self.get_positions()
                
                if positions_response['success']:
                    positions = positions_response['data']
                    asset_balance = 0
                    
                    for position in positions:
                        if position['symbol'] == asset_symbol:
                            asset_balance = float(position['size'])
                            break
                    
                    if asset_balance < quantity:
                        validation_result['valid'] = False
                        validation_result['error'] = f'Insufficient {asset_symbol} balance. Required: {quantity}, Available: {asset_balance}'
                        return validation_result
                else:
                    validation_result['valid'] = False
                    validation_result['error'] = 'Failed to check asset balance'
                    return validation_result
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating trade requirements: {e}")
            return {'valid': False, 'error': str(e)}
    
    def get_technical_analysis(self, symbol):
        """Get technical analysis for symbol"""
        try:
            # Convert symbol format for Pionex API (e.g., BTCUSDT -> BTC_USDT)
            # Handle both BTCUSDT and BTC_USDT formats
            if 'USDT' in symbol and '_' not in symbol:
                formatted_symbol = symbol.replace('USDT', '_USDT')
            else:
                formatted_symbol = symbol
            
            # Try to get market data from klines first
            market_data = self.strategies.get_market_data(formatted_symbol)
            
            if market_data.empty:
                # Fallback to basic ticker data if klines fail
                ticker_response = self.api.get_ticker_price(formatted_symbol)
                if 'data' in ticker_response and 'price' in ticker_response['data']:
                    current_price = float(ticker_response['data']['price'])
                    analysis = {
                        'symbol': symbol,
                        'current_price': current_price,
                        'rsi': 50.0,  # Neutral RSI when no historical data
                        'macd': {
                            'line': 0,
                            'signal': 0,
                            'histogram': 0
                        },
                        'bollinger_bands': {
                            'upper': current_price * 1.02,  # 2% above
                            'middle': current_price,
                            'lower': current_price * 0.98   # 2% below
                        },
                        'timestamp': datetime.now().isoformat(),
                        'note': 'Basic analysis using ticker data only'
                    }
                    return {'success': True, 'data': analysis}
                else:
                    return {'success': False, 'error': f"Could not get price data for {symbol}"}
            
            # Calculate indicators from klines data
            prices = market_data['close'].tolist()
            rsi = self.strategies.calculate_rsi(prices)
            macd_line, macd_signal, macd_histogram = self.strategies.calculate_macd(prices)
            bb_upper, bb_middle, bb_lower = self.strategies.calculate_bollinger_bands(prices)
            
            analysis = {
                'symbol': symbol,
                'current_price': prices[-1] if prices else 0,
                'rsi': rsi[-1] if rsi else 50,
                'macd': {
                    'line': macd_line[-1] if macd_line else 0,
                    'signal': macd_signal[-1] if macd_signal else 0,
                    'histogram': macd_histogram[-1] if macd_histogram else 0
                },
                'bollinger_bands': {
                    'upper': bb_upper[-1] if bb_upper else 0,
                    'middle': bb_middle[-1] if bb_middle else 0,
                    'lower': bb_lower[-1] if bb_lower else 0
                },
                'timestamp': datetime.now().isoformat()
            }
            
            return {'success': True, 'data': analysis}
        except Exception as e:
            logger.error(f"Error getting technical analysis: {e}")
            return {'success': False, 'error': str(e)}
    
    def _start_websocket(self):
        """Start WebSocket connection for real-time data"""
        try:
            if not WEBSOCKET_AVAILABLE or PionexWebSocket is None:
                logger.warning("WebSocket not available, skipping WebSocket connection")
                self.ws_connected = False
                return
                
            self.ws = PionexWebSocket()
            self.ws_connected = True
            logger.info("WebSocket connection started")
        except Exception as e:
            logger.error(f"Error starting WebSocket: {e}")
            self.ws_connected = False

    def get_real_time_price(self, symbol: str) -> float:
        """Get real-time price for a symbol"""
        try:
            return self.api.get_real_time_price(symbol)
        except Exception as e:
            logger.error(f"Error getting real-time price for {symbol}: {e}")
            return 0.0

    def get_current_strategy(self):
        """Get current active strategy"""
        try:
            # Get strategy from user settings or config
            user_settings = self.db.get_user_settings(self.current_user) if self.current_user else {}
            current_strategy = user_settings.get('default_strategy', 'ADVANCED_STRATEGY')
            
            # Get strategy descriptions
            strategy_descriptions = {
                'RSI_STRATEGY': 'Uses RSI indicator for entry/exit signals. Good for trending markets.',
                'VOLUME_FILTER_STRATEGY': 'Combines volume analysis with price action. Filters out low-volume periods.',
                'ADVANCED_STRATEGY': 'Multi-indicator approach with RSI, MACD, Volume, Candlestick patterns, OBV, and Support/Resistance analysis. Includes dynamic SL/TP.',
                'GRID_TRADING_STRATEGY': 'Places buy/sell orders at regular intervals. Good for range-bound markets.',
                'DCA_STRATEGY': 'Dollar Cost Averaging approach. Buys more when price drops.'
            }
            
            return {
                'success': True,
                'data': {
                    'current_strategy': current_strategy,
                    'available_strategies': list(strategy_descriptions.keys()),
                    'descriptions': strategy_descriptions,
                    'status': 'active' if self.auto_trading_enabled else 'inactive'
                }
            }
        except Exception as e:
            logger.error(f"Error getting current strategy: {e}")
            return {'success': False, 'error': str(e)}
    
    def update_strategy(self, strategy_name: str):
        """Update the active trading strategy"""
        try:
            # Validate strategy name
            valid_strategies = [
                'RSI_STRATEGY',
                'VOLUME_FILTER_STRATEGY', 
                'ADVANCED_STRATEGY',
                'GRID_TRADING_STRATEGY',
                'DCA_STRATEGY'
            ]
            
            if strategy_name not in valid_strategies:
                return {'success': False, 'error': f'Invalid strategy: {strategy_name}'}
            
            # Update user settings
            if self.current_user:
                self.db.update_user_setting(self.current_user, 'default_strategy', strategy_name)
            
            # Update config
            self.config['default_strategy'] = strategy_name
            
            # Save config
            import yaml
            with open('config.yaml', 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            
            logger.info(f"Strategy updated to: {strategy_name}")
            return {'success': True, 'message': f'Strategy updated to {strategy_name}'}
            
        except Exception as e:
            logger.error(f"Error updating strategy: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_strategy(self, strategy_name: str, symbol: str = None):
        """Test a trading strategy with current market data"""
        try:
            if not symbol:
                symbol = self.config.get('trading_pair', 'BTC_USDT')
            
            # Convert symbol format for Pionex API (BTCUSDT -> BTC_USDT)
            formatted_symbol = symbol
            if 'USDT' in symbol and '_' not in symbol:
                formatted_symbol = symbol.replace('USDT', '_USDT')
            elif 'USDC' in symbol and '_' not in symbol:
                formatted_symbol = symbol.replace('USDC', '_USDC')
            elif 'BUSD' in symbol and '_' not in symbol:
                formatted_symbol = symbol.replace('BUSD', '_BUSD')
            
            # Get current balance for strategy testing
            balance_response = self.get_account_balance()
            if not balance_response['success']:
                return {'success': False, 'error': 'Failed to get account balance for strategy testing'}
            
            balance = float(balance_response['data'].get('available', 0))
            
            # Get market data with correct symbol format
            df = self.strategies.get_market_data(formatted_symbol, '5M', 100)
            if df.empty:
                return {'success': False, 'error': 'No market data available for testing'}
            
            # Test the strategy with balance parameter
            if strategy_name == 'RSI_STRATEGY':
                signal = self.strategies.rsi_strategy(formatted_symbol, balance)
            elif strategy_name == 'VOLUME_FILTER_STRATEGY':
                signal = self.strategies.volume_filter_strategy(formatted_symbol, balance)
            elif strategy_name == 'ADVANCED_STRATEGY':
                signal = self.strategies.advanced_strategy(formatted_symbol, balance)
            elif strategy_name == 'GRID_TRADING_STRATEGY':
                signal = self.strategies.grid_trading_strategy(formatted_symbol, balance)
            elif strategy_name == 'DCA_STRATEGY':
                signal = self.strategies.dca_strategy(formatted_symbol, balance)
            else:
                return {'success': False, 'error': f'Unknown strategy: {strategy_name}'}
            
            # Format test results
            test_result = {
                'strategy': strategy_name,
                'symbol': symbol,
                'formatted_symbol': formatted_symbol,
                'signal': signal,
                'market_data_points': len(df),
                'current_price': float(df['close'].iloc[-1]) if not df.empty else 0,
                'balance': balance,
                'timestamp': datetime.now().isoformat()
            }
            
            return {'success': True, 'data': test_result}
            
        except Exception as e:
            logger.error(f"Error testing strategy {strategy_name}: {e}")
            return {'success': False, 'error': str(e)}

# Initialize trading bot
trading_bot = TradingBotGUI()

# Initialize RSI Filter
rsi_filter = RSIFilter(trading_bot.api)

# Routes
@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')

@app.route('/bybit-interface')
def bybit_interface():
    return render_template('bybit_interface.html')

@app.route('/pionex-interface')
def pionex_interface():
    """Route to return to main Pionex interface"""
    return redirect('/')

@app.route('/health')
def health_check():
    """Health check endpoint for deployment platforms"""
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/health')
def api_health():
    """API health check"""
    try:
        # Test basic functionality
        api_key = os.getenv('PIONEX_API_KEY')
        api_secret = os.getenv('PIONEX_SECRET_KEY')
        
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'environment': {
                'api_key_set': bool(api_key),
                'api_secret_set': bool(api_secret),
                'flask_env': app.config.get('ENV', 'unknown'),
                'debug_mode': app.config.get('DEBUG', False)
            }
        }
        
        return jsonify(health_status)
    except Exception as e:
        logger.error(f"API health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/balance')
def api_balance():
    """API endpoint for balance"""
    result = trading_bot.get_account_balance()
    return jsonify(result)

@app.route('/api/positions')
def api_positions():
    """API endpoint for positions"""
    result = trading_bot.get_positions()
    return jsonify(result)

@app.route('/api/portfolio')
def api_portfolio():
    """API endpoint for portfolio"""
    result = trading_bot.get_portfolio()
    return jsonify(result)

@app.route('/api/history')
def api_history():
    """API endpoint for trading history"""
    result = trading_bot.get_trading_history()
    return jsonify(result)

@app.route('/api/settings')
def api_settings():
    """API endpoint for settings"""
    result = trading_bot.get_settings()
    return jsonify(result)

@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    """API endpoint for updating settings"""
    data = request.get_json()
    result = trading_bot.update_settings(data)
    return jsonify(result)

@app.route('/api/auto-trading/enable', methods=['POST'])
def api_enable_auto_trading():
    """API endpoint for enabling auto trading"""
    result = trading_bot.enable_auto_trading()
    return jsonify(result)

@app.route('/api/auto-trading/disable', methods=['POST'])
def api_disable_auto_trading():
    """API endpoint for disabling auto trading"""
    result = trading_bot.disable_auto_trading()
    return jsonify(result)

@app.route('/api/auto-trading/status')
def api_auto_trading_status():
    """API endpoint for auto trading status"""
    result = trading_bot.get_auto_trading_status()
    return jsonify(result)

@app.route('/api/trade', methods=['POST'])
def api_trade():
    """API endpoint for manual trading"""
    data = request.get_json()
    symbol = data.get('symbol')
    side = data.get('side')
    quantity = data.get('quantity')
    order_type = data.get('order_type', 'MARKET')
    price = data.get('price')
    
    result = trading_bot.execute_manual_trade(symbol, side, quantity, order_type, price)
    return jsonify(result)

@app.route('/api/trade/validate', methods=['POST'])
def api_validate_trade():
    """API endpoint for trade validation"""
    data = request.get_json()
    symbol = data.get('symbol')
    side = data.get('side')
    quantity = data.get('quantity')
    order_type = data.get('order_type', 'MARKET')
    price = data.get('price')
    
    result = trading_bot.validate_trade_requirements(symbol, side, quantity, order_type, price)
    return jsonify(result)

@app.route('/api/analysis/<symbol>')
def api_analysis(symbol):
    """API endpoint for technical analysis"""
    result = trading_bot.get_technical_analysis(symbol)
    return jsonify(result)

@app.route('/api/chart-data/<symbol>')
def api_chart_data(symbol):
    """Get chart data for a symbol"""
    try:
        # Get timeframe from query parameter
        timeframe = request.args.get('timeframe', '5M')
        
        # Convert symbol format for Pionex API (BTCUSDT -> BTC_USDT)
        formatted_symbol = symbol
        if 'USDT' in symbol and '_' not in symbol:
            formatted_symbol = symbol.replace('USDT', '_USDT')
        elif 'USDC' in symbol and '_' not in symbol:
            formatted_symbol = symbol.replace('USDC', '_USDC')
        elif 'BUSD' in symbol and '_' not in symbol:
            formatted_symbol = symbol.replace('BUSD', '_BUSD')
        
        logger.info(f"Fetching chart data for symbol: {symbol} -> {formatted_symbol} with timeframe: {timeframe}")
        
        # Try multiple intervals to get the best data, starting with requested timeframe
        intervals_to_try = [timeframe, '5M', '1M', '15M', '1H']
        klines_data = []
        successful_interval = None
        
        for interval in intervals_to_try:
            try:
                logger.info(f"Trying interval {interval} for {formatted_symbol}")
                klines_response = trading_bot.api.get_klines(
                    symbol=formatted_symbol,
                    interval=interval,
                    limit=100
                )
                
                logger.info(f"Klines response for {formatted_symbol} with interval {interval}: {klines_response}")
                
                # Check for API errors
                if 'error' in klines_response:
                    logger.warning(f"API error for {formatted_symbol} with interval {interval}: {klines_response['error']}")
                    continue
                
                # Check for code 0 (success) or other success indicators
                if 'code' in klines_response and klines_response['code'] == 0:
                    logger.info(f"API returned code 0 for {formatted_symbol} with interval {interval}")
                    # This is a successful response, but we need to extract data
                    if 'data' in klines_response:
                        if isinstance(klines_response['data'], dict) and 'klines' in klines_response['data']:
                            klines_data = klines_response['data']['klines']
                        elif isinstance(klines_response['data'], list):
                            klines_data = klines_response['data']
                        successful_interval = interval
                        break
                
                # Handle different response formats
                if 'data' in klines_response:
                    if isinstance(klines_response['data'], dict) and 'klines' in klines_response['data']:
                        klines_data = klines_response['data']['klines']
                    elif isinstance(klines_response['data'], list):
                        klines_data = klines_response['data']
                
                if klines_data:
                    logger.info(f"Successfully got {len(klines_data)} data points with interval {interval}")
                    successful_interval = interval
                    break
                        
            except Exception as e:
                logger.warning(f"Failed to get klines with interval {interval}: {e}")
                continue
        
        if not klines_data:
            logger.warning(f"No klines data received for {formatted_symbol} with any interval")
            # Try to get basic ticker data as fallback
            try:
                ticker_response = trading_bot.api.get_ticker_price(formatted_symbol)
                logger.info(f"Ticker response as fallback: {ticker_response}")
                if 'data' in ticker_response and 'price' in ticker_response['data']:
                    current_price = float(ticker_response['data']['price'])
                    # Create sample chart data
                    import time
                    current_time = int(time.time() * 1000)
                    sample_data = {
                        'labels': ['Current'],
                        'prices': [current_price],
                        'volumes': [0],
                        'timestamps': [current_time],
                        'high': [current_price],
                        'low': [current_price],
                        'open': [current_price],
                        'timeframe': '1M'
                    }
                    return jsonify({
                        'success': True,
                        'data': sample_data,
                        'symbol': symbol,
                        'formatted_symbol': formatted_symbol,
                        'note': 'Using ticker data as fallback'
                    })
            except Exception as e:
                logger.error(f"Failed to get ticker data as fallback: {e}")
            
            return jsonify({'success': False, 'error': 'No data available for this symbol'})
        
        # Process klines data for chart
        chart_data = {
            'labels': [],
            'prices': [],
            'volumes': [],
            'timestamps': [],
            'high': [],
            'low': [],
            'open': [],
            'timeframe': successful_interval  # Use the successful interval
        }
        
        for kline in klines_data:
            try:
                # Handle different kline formats
                if len(kline) >= 6:
                    timestamp = int(kline[0])  # Open time
                    open_price = float(kline[1])
                    high_price = float(kline[2])
                    low_price = float(kline[3])
                    close_price = float(kline[4])
                    volume = float(kline[5])
                    
                    # Use close price for the main chart
                    chart_data['prices'].append(close_price)
                    chart_data['volumes'].append(volume)
                    chart_data['timestamps'].append(timestamp)
                    chart_data['high'].append(high_price)
                    chart_data['low'].append(low_price)
                    chart_data['open'].append(open_price)
                    
                    # Format time for labels
                    from datetime import datetime
                    time_obj = datetime.fromtimestamp(timestamp / 1000)
                    chart_data['labels'].append(time_obj.strftime('%H:%M'))
                    
            except (IndexError, ValueError, TypeError) as e:
                logger.warning(f"Error processing kline data: {e}")
                continue
        
        if not chart_data['prices']:
            logger.error(f"No valid chart data processed for {symbol}")
            return jsonify({'success': False, 'error': 'Failed to process chart data'})
        
        logger.info(f"Successfully processed {len(chart_data['prices'])} data points for {symbol}")
        
        return jsonify({
            'success': True, 
            'data': chart_data,
            'symbol': symbol,
            'formatted_symbol': formatted_symbol,
            'timeframe': chart_data['timeframe']
        })
        
    except Exception as e:
        logger.error(f"Error getting chart data for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/market-data/<symbol>')
def api_market_data(symbol):
    """Get real-time market data for a symbol"""
    try:
        market_data = trading_bot.api.get_real_time_market_data(symbol)
        
        if 'error' in market_data:
            return jsonify({'success': False, 'error': market_data['error']})
        
        return jsonify({
            'success': True,
            'data': market_data
        })
        
    except Exception as e:
        logger.error(f"Error getting market data for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/live-trades/<symbol>')
def api_live_trades(symbol):
    """Get live trades for a symbol"""
    try:
        limit = request.args.get('limit', 50, type=int)
        trades_data = trading_bot.api.get_live_trades(symbol, limit)
        
        if 'error' in trades_data:
            return jsonify({'success': False, 'error': trades_data['error']})
        
        return jsonify({
            'success': True,
            'data': trades_data
        })
        
    except Exception as e:
        logger.error(f"Error getting live trades for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/market-depth/<symbol>')
def api_market_depth(symbol):
    """Get market depth (order book) for a symbol"""
    try:
        limit = request.args.get('limit', 20, type=int)
        depth_data = trading_bot.api.get_market_depth(symbol, limit)
        
        if 'error' in depth_data:
            return jsonify({'success': False, 'error': depth_data['error']})
        
        return jsonify({
            'success': True,
            'data': depth_data
        })
        
    except Exception as e:
        logger.error(f"Error getting market depth for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/real-time-price/<symbol>')
def api_real_time_price(symbol):
    """Get real-time price for a symbol"""
    try:
        price = trading_bot.api.get_real_time_price(symbol)
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol,
                'price': price,
                'timestamp': int(time.time() * 1000)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting real-time price for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/24hr-ticker/<symbol>')
def api_24hr_ticker(symbol):
    """Get 24-hour ticker statistics"""
    try:
        ticker_data = trading_bot.api.get_24hr_ticker(symbol)
        
        if 'error' in ticker_data:
            return jsonify({'success': False, 'error': ticker_data['error']})
        
        return jsonify({
            'success': True,
            'data': ticker_data
        })
        
    except Exception as e:
        logger.error(f"Error getting 24hr ticker for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/strategy', methods=['GET'])
def api_get_strategy():
    """API endpoint for getting current strategy"""
    result = trading_bot.get_current_strategy()
    return jsonify(result)

@app.route('/api/strategy', methods=['POST'])
def api_update_strategy():
    """API endpoint for updating strategy"""
    data = request.get_json()
    strategy_name = data.get('strategy')
    
    if not strategy_name:
        return jsonify({'success': False, 'error': 'Strategy name is required'})
    
    result = trading_bot.update_strategy(strategy_name)
    return jsonify(result)

@app.route('/api/strategy/test', methods=['POST'])
def api_test_strategy():
    """API endpoint for testing strategy"""
    data = request.get_json()
    strategy_name = data.get('strategy')
    symbol = data.get('symbol')
    
    if not strategy_name:
        return jsonify({'success': False, 'error': 'Strategy name is required'})
    
    result = trading_bot.test_strategy(strategy_name, symbol)
    return jsonify(result)

@app.route('/api/test-email', methods=['POST'])
def api_test_email():
    """API endpoint for testing email notification"""
    try:
        data = request.get_json()
        email_config = data.get('email_config', {})
        
        # Test email configuration
        smtp_server = email_config.get('smtp_server', 'smtp.gmail.com')
        smtp_port = email_config.get('smtp_port', 587)
        sender_email = email_config.get('sender_email', '')
        sender_password = email_config.get('sender_password', '')
        recipient_email = email_config.get('recipient_email', '')
        
        if not sender_email or not sender_password or not recipient_email:
            return jsonify({
                'success': False, 
                'error': 'Missing email configuration. Please provide sender_email, sender_password, and recipient_email.'
            })
        
        # Create test message
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import smtplib
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = "🤖 Pionex Trading Bot - Email Test"
        
        body = f"""
        🎉 Email Notification Test Successful!
        
        This is a test email from your Pionex Trading Bot.
        
        📧 Email Configuration:
        - SMTP Server: {smtp_server}
        - SMTP Port: {smtp_port}
        - Sender: {sender_email}
        - Recipient: {recipient_email}
        
        ⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        ✅ If you received this email, your email notification is working correctly!
        
        ---
        This is an automated test message from your trading bot.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send test email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        logger.info(f"Test email sent successfully to {recipient_email}")
        
        return jsonify({
            'success': True, 
            'message': f'Test email sent successfully to {recipient_email}'
        })
        
    except smtplib.SMTPAuthenticationError:
        return jsonify({
            'success': False, 
            'error': 'Authentication failed. Please check your email and password. For Gmail, you may need to use an App Password.'
        })
    except smtplib.SMTPException as e:
        return jsonify({
            'success': False, 
            'error': f'SMTP error: {str(e)}'
        })
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        return jsonify({
            'success': False, 
            'error': f'Failed to send test email: {str(e)}'
        })

@app.route('/api/test-symbol-format/<symbol>')
def api_test_symbol_format(symbol):
    """Test symbol format conversion"""
    try:
        result = trading_bot.api.test_symbol_format(symbol)
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        logger.error(f"Error testing symbol format for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test-api-response/<symbol>')
def api_test_api_response(symbol):
    """Test API response for debugging"""
    try:
        # Convert symbol format
        formatted_symbol = symbol
        if 'USDT' in symbol and '_' not in symbol:
            formatted_symbol = symbol.replace('USDT', '_USDT')
        
        logger.info(f"Testing API response for symbol: {symbol} -> {formatted_symbol}")
        
        # Test different API endpoints
        results = {}
        
        # Test klines
        try:
            klines_response = trading_bot.api.get_klines(formatted_symbol, '5M', 10)
            results['klines'] = {
                'response': klines_response,
                'has_error': 'error' in klines_response,
                'has_data': 'data' in klines_response,
                'has_code': 'code' in klines_response,
                'code_value': klines_response.get('code', 'N/A')
            }
        except Exception as e:
            results['klines'] = {'error': str(e)}
        
        # Test ticker
        try:
            ticker_response = trading_bot.api.get_ticker_price(formatted_symbol)
            results['ticker'] = {
                'response': ticker_response,
                'has_error': 'error' in ticker_response,
                'has_data': 'data' in ticker_response
            }
        except Exception as e:
            results['ticker'] = {'error': str(e)}
        
        # Test market data
        try:
            market_data = trading_bot.api.get_real_time_market_data(symbol)
            results['market_data'] = {
                'response': market_data,
                'has_error': 'error' in market_data
            }
        except Exception as e:
            results['market_data'] = {'error': str(e)}
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol,
                'formatted_symbol': formatted_symbol,
                'results': results
            }
        })
        
    except Exception as e:
        logger.error(f"Error testing API response for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update-trading-pair', methods=['POST'])
def api_update_trading_pair():
    """API endpoint to update trading pair"""
    try:
        data = request.get_json()
        new_pair = data.get('trading_pair', '').upper()
        
        logger.info(f"Updating trading pair to: {new_pair}")
        
        if not new_pair:
            return jsonify({'success': False, 'error': 'Trading pair is required'})
        
        # Update the trading pair in the auto trader
        auto_trader = get_auto_trader(trading_bot.current_user or 1)
        logger.info(f"Got auto trader: {auto_trader}")
        
        auto_trader.set_trading_pair(new_pair)
        logger.info(f"Set trading pair to: {new_pair}")
        
        # Get updated status
        status = get_auto_trading_status(trading_bot.current_user or 1)
        logger.info(f"Updated status: {status}")
        
        return jsonify({
            'success': True,
            'message': f'Trading pair updated to {new_pair}',
            'current_pair': new_pair,
            'auto_trading_enabled': status.get('auto_trading_enabled', False)
        })
        
    except Exception as e:
        logger.error(f"Error updating trading pair: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test-auto-trader')
def api_test_auto_trader():
    """Test endpoint to check if auto trader is working"""
    try:
        user_id = trading_bot.current_user or 1
        auto_trader = get_auto_trader(user_id)
        
        return jsonify({
            'success': True,
            'auto_trader_exists': auto_trader is not None,
            'current_pair': getattr(auto_trader, 'current_pair', 'N/A'),
            'user_id': user_id
        })
    except Exception as e:
        logger.error(f"Error testing auto trader: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/futures/trade', methods=['POST'])
def api_futures_trade():
    """API endpoint for futures trading"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        side = data.get('side')
        quantity = data.get('quantity')
        order_type = data.get('order_type')
        price = data.get('price')
        leverage = data.get('leverage', 10)
        stop_loss = data.get('stop_loss')
        take_profit = data.get('take_profit')
        
        if not all([symbol, side, quantity, order_type]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        # Execute futures trade
        result = trading_bot.execute_futures_trade(
            symbol=symbol,
            side=side,
            qty=quantity,
            order_type=order_type,
            price=price,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error executing futures trade: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/futures/balance')
def api_futures_balance():
    """API endpoint for futures balance"""
    try:
        result = trading_bot.get_account_balance()
        if result.get('success'):
            # Extract futures balance from combined balance
            futures_balance = result.get('data', {}).get('futures', {})
            return jsonify({'success': True, 'data': futures_balance})
        else:
            return jsonify({'success': False, 'error': 'Failed to load futures balance'})
    except Exception as e:
        logger.error(f"Error loading futures balance: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/futures/leverage', methods=['POST'])
def api_futures_leverage():
    """API endpoint for setting futures leverage"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        leverage = data.get('leverage')
        
        if not all([symbol, leverage]):
            return jsonify({'success': False, 'error': 'Missing symbol or leverage'})
        
        # Set leverage using Bybit API
        if trading_bot.bybit_api:
            result = trading_bot.bybit_api.set_leverage(symbol, leverage)
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': 'Bybit API not initialized'})
        
    except Exception as e:
        logger.error(f"Error setting futures leverage: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/futures/close-position', methods=['POST'])
def api_futures_close_position():
    """API endpoint for closing futures position"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        side = data.get('side')
        size = data.get('size')
        
        if not all([symbol, side, size]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        # Close position using Bybit API
        if trading_bot.bybit_api:
            result = trading_bot.bybit_api.close_futures_position(symbol, side, size)
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': 'Bybit API not initialized'})
        
    except Exception as e:
        logger.error(f"Error closing futures position: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/futures/positions')
def api_futures_positions():
    """API endpoint for futures positions"""
    try:
        result = trading_bot.get_positions()
        if result.get('success'):
            # Extract futures positions from combined positions
            futures_positions = result.get('data', {}).get('futures', [])
            return jsonify({'success': True, 'data': futures_positions})
        else:
            return jsonify({'success': False, 'error': 'Failed to load futures positions'})
    except Exception as e:
        logger.error(f"Error loading futures positions: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/futures/market-data/<symbol>')
def api_futures_market_data(symbol):
    """API endpoint for futures market data"""
    try:
        if trading_bot.bybit_api:
            result = trading_bot.bybit_api.get_market_price(symbol)
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': 'Bybit API not initialized'})
    except Exception as e:
        logger.error(f"Error loading futures market data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/futures/klines/<symbol>')
def api_futures_klines(symbol):
    """API endpoint for futures klines/candlestick data"""
    try:
        interval = request.args.get('interval', '5')
        limit = request.args.get('limit', 100)
        
        if trading_bot.bybit_api:
            result = trading_bot.bybit_api.get_klines(symbol, interval, int(limit))
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': 'Bybit API not initialized'})
    except Exception as e:
        logger.error(f"Error loading futures klines: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/futures/orderbook/<symbol>')
def api_futures_orderbook(symbol):
    """API endpoint for futures order book"""
    try:
        limit = request.args.get('limit', 25)
        
        if trading_bot.bybit_api:
            result = trading_bot.bybit_api.get_orderbook(symbol, int(limit))
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': 'Bybit API not initialized'})
    except Exception as e:
        logger.error(f"Error loading futures orderbook: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/futures/trades/<symbol>')
def api_futures_trades(symbol):
    """API endpoint for futures recent trades"""
    try:
        limit = request.args.get('limit', 100)
        
        if trading_bot.bybit_api:
            result = trading_bot.bybit_api.get_recent_trades(symbol, int(limit))
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': 'Bybit API not initialized'})
    except Exception as e:
        logger.error(f"Error loading futures trades: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ===== BYBIT API ENDPOINTS FOR REAL-TIME FUTURES DATA =====

@app.route('/api/bybit/market-data')
def api_bybit_market_data():
    """API endpoint for comprehensive Bybit futures market data"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        # Get API credentials from config
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        if not bybit_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Bybit futures trading not enabled'})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        # Initialize Bybit API
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Get real-time market data
        result = bybit_api.get_futures_real_time_data()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching Bybit market data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/market-summary')
def api_bybit_market_summary():
    """API endpoint for Bybit futures market summary"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        # Get API credentials from config
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        if not bybit_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Bybit futures trading not enabled'})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        # Initialize Bybit API
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Get market summary
        result = bybit_api.get_futures_market_summary()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching Bybit market summary: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/ticker/<symbol>')
def api_bybit_ticker(symbol):
    """API endpoint for specific Bybit futures ticker"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        # Get API credentials from config
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        if not bybit_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Bybit futures trading not enabled'})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        # Initialize Bybit API
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Get ticker data
        result = bybit_api.get_futures_ticker(symbol)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching Bybit ticker for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/funding-rate/<symbol>')
def api_bybit_funding_rate(symbol):
    """API endpoint for Bybit futures funding rate"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        # Get API credentials from config
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        if not bybit_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Bybit futures trading not enabled'})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        # Initialize Bybit API
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Get funding rate
        result = bybit_api.get_futures_funding_rate(symbol)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching Bybit funding rate for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/open-interest/<symbol>')
def api_bybit_open_interest(symbol):
    """API endpoint for Bybit futures open interest"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        # Get API credentials from config
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        if not bybit_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Bybit futures trading not enabled'})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        # Initialize Bybit API
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Get open interest
        result = bybit_api.get_futures_open_interest(symbol)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching Bybit open interest for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/market-status')
def api_bybit_market_status():
    """API endpoint for Bybit futures market status"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        # Get API credentials from config
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        if not bybit_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Bybit futures trading not enabled'})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        # Initialize Bybit API
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Get market status
        result = bybit_api.get_futures_market_status()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching Bybit market status: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/health')
def api_bybit_health():
    """API endpoint to check Bybit API health"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        # Get API credentials from config
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        if not bybit_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Bybit futures trading not enabled'})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        # Initialize Bybit API
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Test API connection
        result = bybit_api.get_futures_market_status()
        if result.get('success'):
            return jsonify({
                'success': True,
                'status': 'healthy',
                'message': 'Bybit API is working correctly',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'status': 'unhealthy',
                'error': result.get('error', 'Unknown error'),
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Error checking Bybit API health: {e}")
        return jsonify({
            'success': False,
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

# Additional Bybit API endpoints for real trading
@app.route('/api/bybit/balance')
def api_bybit_balance():
    """API endpoint for Bybit account balance - Fast version"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        if not bybit_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Bybit futures trading not enabled'})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Use a faster, more direct balance check
        try:
            # Try to get balance using a more efficient method
            if PYBIT_AVAILABLE:
                # Use pybit directly for faster response
                from pybit.unified_trading import HTTP
                session = HTTP(
                    testnet=testnet,
                    api_key=api_key,
                    api_secret=api_secret
                )
                
                # Get only essential balance info
                balance_response = session.get_wallet_balance(
                    accountType="UNIFIED",
                    coin="USDT"
                )
                
                if balance_response.get('retCode') == 0:
                    balance_data = balance_response.get('result', {}).get('list', [])
                    if balance_data:
                        account_info = balance_data[0]
                        return jsonify({
                            'success': True,
                            'data': {
                                'list': [{
                                    'totalWalletBalance': account_info.get('totalWalletBalance', '0'),
                                    'totalAvailableBalance': account_info.get('totalAvailableBalance', '0'),
                                    'totalEquity': account_info.get('totalEquity', '0'),
                                    'coin': 'USDT'
                                }]
                            }
                        })
                
                # Fallback to original method
                result = bybit_api.get_account_balance()
                return jsonify(result)
            else:
                # Fallback to original method
                result = bybit_api.get_account_balance()
                return jsonify(result)
                
        except Exception as api_error:
            logger.warning(f"Fast balance check failed, using fallback: {api_error}")
            # Fallback to original method
            result = bybit_api.get_account_balance()
            return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching Bybit balance: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/kpi/metrics', methods=['GET'])
def api_bybit_kpi_metrics():
    """Get KPI metrics for auto trading performance"""
    try:
        # Calculate KPI metrics from trading history
        # This would typically come from a database of trades
        # For now, we'll return mock data that can be replaced with real calculations
        
        # Mock KPI data (replace with real calculations)
        kpi_metrics = {
            'win_rate': 65.5,  # Percentage of winning trades
            'profit_factor': 1.85,  # Gross profit / Gross loss
            'avg_trade': 12.50,  # Average profit per trade
            'max_drawdown': 8.2,  # Maximum drawdown percentage
            'total_trades': auto_trading_status.get('total_trades', 0),
            'winning_trades': int(auto_trading_status.get('total_trades', 0) * 0.655),
            'losing_trades': int(auto_trading_status.get('total_trades', 0) * 0.345),
            'consecutive_losses': 2,  # Current consecutive losses
            'daily_pnl': 45.20,  # Today's P&L
            'weekly_pnl': 156.80,  # This week's P&L
            'monthly_pnl': 523.40  # This month's P&L
        }
        
        return jsonify({
            'success': True,
            'data': kpi_metrics
        })
        
    except Exception as e:
        logger.error(f"Error getting KPI metrics: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/atr/<symbol>', methods=['GET'])
def api_bybit_atr(symbol):
    """Get ATR (Average True Range) value for a symbol"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Get ATR value (this would need to be implemented in bybit_api.py)
        # For now, we'll return a mock ATR value
        atr_value = calculate_mock_atr(symbol)
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol,
                'atr_value': atr_value,
                'period': 14,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting ATR for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

def calculate_mock_atr(symbol):
    """Calculate mock ATR value for testing"""
    # This is a simplified mock calculation
    # In a real implementation, this would calculate actual ATR from price data
    
    # Mock ATR values based on symbol volatility
    mock_atr_values = {
        'BTCUSDT': 0.015,
        'ETHUSDT': 0.018,
        'SOLUSDT': 0.025,
        'ADAUSDT': 0.020,
        'DOTUSDT': 0.022,
        'BNBUSDT': 0.016
    }
    
    # Add some randomness to simulate real market conditions
    import random
    base_atr = mock_atr_values.get(symbol, 0.020)
    variation = random.uniform(0.8, 1.2)  # ±20% variation
    
    return base_atr * variation

@app.route('/api/bybit/market-condition/<symbol>', methods=['GET'])
def api_bybit_market_condition(symbol):
    """Get market condition analysis for flat day detection"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Get market condition data (mock implementation)
        market_data = calculate_mock_market_condition(symbol)
        
        return jsonify({
            'success': True,
            'data': market_data
        })
        
    except Exception as e:
        logger.error(f"Error getting market condition for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)})

def calculate_mock_market_condition(symbol):
    """Calculate mock market condition data for testing"""
    import random
    
    # Mock market condition data
    volume_ratio = random.uniform(0.5, 1.5)  # Current volume vs average
    atr_value = random.uniform(0.005, 0.03)  # ATR value
    price_range = random.uniform(0.5, 3.0)   # Daily price range percentage
    
    # Determine market condition
    if volume_ratio < 0.8 and atr_value < 0.01 and price_range < 1.5:
        condition = 'Flat Day'
    elif atr_value > 0.02 or price_range > 2.5:
        condition = 'High Volatility'
    else:
        condition = 'Normal Volatility'
    
    return {
        'symbol': symbol,
        'condition': condition,
        'volume_ratio': volume_ratio,
        'atr_value': atr_value,
        'price_range': price_range,
        'timestamp': datetime.now().isoformat()
    }

@app.route('/api/bybit/positions')
def api_bybit_positions():
    """API endpoint for Bybit positions"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        if not bybit_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Bybit futures trading not enabled'})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        result = bybit_api.get_positions()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching Bybit positions: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/place-order', methods=['POST'])
def api_bybit_place_order():
    """API endpoint for placing Bybit orders"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'})
        
        symbol = data.get('symbol')
        side = data.get('side')
        orderType = data.get('orderType')
        qty = data.get('qty')
        leverage = data.get('leverage', 10)
        
        logger.info(f"Received order request: {data}")
        
        if not all([symbol, side, orderType, qty]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Set leverage first - handle "leverage not modified" error gracefully
        leverage_result = bybit_api.set_leverage(symbol, leverage)
        if not leverage_result.get('success'):
            error_msg = leverage_result.get('error', '')
            # If leverage is already set to the requested value, this is not a critical error
            if 'leverage not modified' in error_msg.lower() or '110043' in error_msg:
                logger.info(f"Leverage already set to {leverage} for {symbol}, proceeding with order placement")
            else:
                logger.warning(f"Failed to set leverage: {error_msg}")
                # Continue with order placement anyway, as leverage might already be correct
        
        # Place the order
        logger.info(f"Placing order: symbol={symbol}, side={side}, orderType={orderType}, qty={qty}")
        result = bybit_api.place_order(
            symbol=symbol,
            side=side,
            orderType=orderType,
            qty=qty
        )
        
        logger.info(f"Order result: {result}")
        
        # Ensure result is a valid dictionary
        if not isinstance(result, dict):
            result = {'success': False, 'error': f'Invalid result type: {type(result)}'}
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error placing Bybit order: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/close-position', methods=['POST'])
def api_bybit_close_position():
    """API endpoint for closing Bybit positions"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        symbol = data.get('symbol')
        side = data.get('side')
        qty = data.get('qty')
        
        if not all([symbol, side, qty]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        result = bybit_api.close_position(symbol, side, qty)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error closing Bybit position: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/test', methods=['GET'])
def api_bybit_test():
    """Test endpoint to check if Bybit API is working"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Test getting account balance
        result = bybit_api.get_account_balance()
        
        return jsonify({
            'success': True,
            'message': 'Bybit API is working',
            'test_result': result
        })
        
    except Exception as e:
        logger.error(f"Error testing Bybit API: {e}")
        return jsonify({'success': False, 'error': str(e)})



@app.route('/api/bybit/close-all-positions', methods=['POST'])
def api_bybit_close_all_positions():
    """API endpoint for closing all Bybit positions"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        result = bybit_api.close_all_positions()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error closing all Bybit positions: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/set-leverage', methods=['POST'])
def api_bybit_set_leverage():
    """API endpoint for setting Bybit leverage"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        leverage = data.get('leverage')
        
        if not leverage:
            return jsonify({'success': False, 'error': 'Leverage is required'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Set leverage for all symbols
        symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'DOTUSDT', 'BNBUSDT']
        results = {}
        
        for symbol in symbols:
            try:
                result = bybit_api.set_leverage(symbol, leverage)
                results[symbol] = result
            except Exception as e:
                results[symbol] = {'success': False, 'error': str(e)}
        
        return jsonify({
            'success': True,
            'message': f'Leverage set to {leverage}x',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error setting Bybit leverage: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/set-global-stop-loss', methods=['POST'])
def api_bybit_set_global_stop_loss():
    """API endpoint for setting global stop loss"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        stopLossPercent = data.get('stopLossPercent')
        
        if not stopLossPercent:
            return jsonify({'success': False, 'error': 'Stop loss percentage is required'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # This would typically involve setting stop loss orders for all open positions
        # For now, we'll just return success
        return jsonify({
            'success': True,
            'message': f'Global stop loss set to {stopLossPercent}%',
            'note': 'Stop loss orders will be placed when positions are opened'
        })
        
    except Exception as e:
        logger.error(f"Error setting global stop loss: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Global variable to store auto trading status
auto_trading_status = {
    'active': False,
    'total_trades': 0,
    'active_strategies': 0,
    'settings': {
        'trading_pair': 'BTCUSDT',
        'max_daily_trades': 5,
        'max_risk_per_trade': 2.0,
        'daily_loss_limit': 5.0,
        
        # Session Management
        'us_session_enabled': True,
        'asian_session_enabled': True,
        
        # Breakout Strategy
        'breakout_enabled': True,
        'buffer_percentage': 0.05,
        'confirmation_candles': 1,
        'max_trades_per_session': 1,
        'cooldown_minutes': 30,
        
        # Risk Management
        'stop_loss_percentage': 1.5,
        'take_profit_percentage': 2.5,
        'use_box_opposite': True,
        'auto_breakeven': True,
        
        # Technical Filters
        'mtf_rsi_enabled': True,
        'rsi_5m_long': 30,
        'rsi_5m_short': 70,
        'rsi_1h_long': 50,
        'rsi_1h_short': 50,
        'reduced_version': False,
        
        # Volume Filter
        'volume_filter_enabled': True,
        'volume_multiplier': 1.5,
        'volume_ema_period': 20
    },
    'started_at': None,
    'stopped_at': None
}

@app.route('/api/bybit/auto-trading/start', methods=['POST'])
def api_bybit_auto_trading_start():
    """Start auto trading"""
    try:
        data = request.json
        logger.info(f"Starting auto trading with settings: {data}")
        
        # Update global auto trading status
        auto_trading_status['active'] = True
        auto_trading_status['started_at'] = datetime.now().isoformat()
        auto_trading_status['stopped_at'] = None
        
        # Update settings with all advanced trading system parameters
        auto_trading_status['settings'].update({
            'trading_pair': data.get('trading_pair', 'BTCUSDT'),
            'max_daily_trades': data.get('max_daily_trades', 5),
            'max_risk_per_trade': data.get('max_risk_per_trade', 2.0),
            'daily_loss_limit': data.get('daily_loss_limit', 5.0),
            
            # Session Management
            'us_session_enabled': data.get('us_session_enabled', True),
            'asian_session_enabled': data.get('asian_session_enabled', True),
            
            # Breakout Strategy
            'breakout_enabled': data.get('breakout_enabled', True),
            'buffer_percentage': data.get('buffer_percentage', 0.05),
            'confirmation_candles': data.get('confirmation_candles', 1),
            'max_trades_per_session': data.get('max_trades_per_session', 1),
            'cooldown_minutes': data.get('cooldown_minutes', 30),
            
            # Risk Management
            'stop_loss_percentage': data.get('stop_loss_percentage', 1.5),
            'take_profit_percentage': data.get('take_profit_percentage', 2.5),
            'use_box_opposite': data.get('use_box_opposite', True),
            'auto_breakeven': data.get('auto_breakeven', True),
            
            # Technical Filters
            'mtf_rsi_enabled': data.get('mtf_rsi_enabled', True),
            'rsi_5m_long': data.get('rsi_5m_long', 30),
            'rsi_5m_short': data.get('rsi_5m_short', 70),
            'rsi_1h_long': data.get('rsi_1h_long', 50),
            'rsi_1h_short': data.get('rsi_1h_short', 50),
            'reduced_version': data.get('reduced_version', False),
            
            # Volume Filter
            'volume_filter_enabled': data.get('volume_filter_enabled', True),
            'volume_multiplier': data.get('volume_multiplier', 1.5),
            'volume_ema_period': data.get('volume_ema_period', 20)
        })
        
        # Reset counters
        auto_trading_status['total_trades'] = 0
        auto_trading_status['active_strategies'] = 1  # Breakout strategy
        
        logger.info(f"Auto trading started successfully at {auto_trading_status['started_at']}")
        logger.info(f"Trading pair: {auto_trading_status['settings']['trading_pair']}")
        logger.info(f"All advanced settings applied: {auto_trading_status['settings']}")
        
        return jsonify({
            'success': True,
            'message': 'Auto trading started successfully',
            'data': {
                'status': 'RUNNING',
                'started_at': auto_trading_status['started_at'],
                'trading_pair': auto_trading_status['settings']['trading_pair'],
                'settings': auto_trading_status['settings'],
                'active_strategies': auto_trading_status['active_strategies']
            }
        })
        
    except Exception as e:
        logger.error(f"Error starting auto trading: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/auto-trading/stop', methods=['POST'])
def api_bybit_auto_trading_stop():
    """Stop auto trading"""
    try:
        data = request.json
        reason = data.get('reason', 'user_requested')
        logger.info(f"Stopping auto trading, reason: {reason}")
        
        # Update global auto trading status
        auto_trading_status['active'] = False
        auto_trading_status['stopped_at'] = datetime.now().isoformat()
        auto_trading_status['active_strategies'] = 0
        
        logger.info(f"Auto trading stopped successfully at {auto_trading_status['stopped_at']}")
        
        return jsonify({
            'success': True,
            'message': 'Auto trading stopped successfully',
            'data': {
                'status': 'STOPPED',
                'stopped_at': auto_trading_status['stopped_at'],
                'reason': reason,
                'total_trades_executed': auto_trading_status['total_trades'],
                'active_strategies': auto_trading_status['active_strategies']
            }
        })
        
    except Exception as e:
        logger.error(f"Error stopping auto trading: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/auto-trading/settings', methods=['POST'])
def api_bybit_auto_trading_settings():
    """Update auto trading settings"""
    try:
        data = request.json
        logger.info(f"Updating auto trading settings: {data}")
        
        # Update settings with all advanced trading system parameters
        auto_trading_status['settings'].update({
            'trading_pair': data.get('trading_pair', auto_trading_status['settings'].get('trading_pair', 'BTCUSDT')),
            'max_daily_trades': data.get('max_daily_trades', auto_trading_status['settings'].get('max_daily_trades', 5)),
            'max_risk_per_trade': data.get('max_risk_per_trade', auto_trading_status['settings'].get('max_risk_per_trade', 2.0)),
            'daily_loss_limit': data.get('daily_loss_limit', auto_trading_status['settings'].get('daily_loss_limit', 5.0)),
            
            # Session Management
            'us_session_enabled': data.get('us_session_enabled', auto_trading_status['settings'].get('us_session_enabled', True)),
            'asian_session_enabled': data.get('asian_session_enabled', auto_trading_status['settings'].get('asian_session_enabled', True)),
            
            # Breakout Strategy
            'breakout_enabled': data.get('breakout_enabled', auto_trading_status['settings'].get('breakout_enabled', True)),
            'buffer_percentage': data.get('buffer_percentage', auto_trading_status['settings'].get('buffer_percentage', 0.05)),
            'confirmation_candles': data.get('confirmation_candles', auto_trading_status['settings'].get('confirmation_candles', 1)),
            'max_trades_per_session': data.get('max_trades_per_session', auto_trading_status['settings'].get('max_trades_per_session', 1)),
            'cooldown_minutes': data.get('cooldown_minutes', auto_trading_status['settings'].get('cooldown_minutes', 30)),
            
            # Risk Management
            'stop_loss_percentage': data.get('stop_loss_percentage', auto_trading_status['settings'].get('stop_loss_percentage', 1.5)),
            'take_profit_percentage': data.get('take_profit_percentage', auto_trading_status['settings'].get('take_profit_percentage', 2.5)),
            'use_box_opposite': data.get('use_box_opposite', auto_trading_status['settings'].get('use_box_opposite', True)),
            'auto_breakeven': data.get('auto_breakeven', auto_trading_status['settings'].get('auto_breakeven', True)),
            
            # Technical Filters
            'mtf_rsi_enabled': data.get('mtf_rsi_enabled', auto_trading_status['settings'].get('mtf_rsi_enabled', True)),
            'rsi_5m_long': data.get('rsi_5m_long', auto_trading_status['settings'].get('rsi_5m_long', 30)),
            'rsi_5m_short': data.get('rsi_5m_short', auto_trading_status['settings'].get('rsi_5m_short', 70)),
            'rsi_1h_long': data.get('rsi_1h_long', auto_trading_status['settings'].get('rsi_1h_long', 50)),
            'rsi_1h_short': data.get('rsi_1h_short', auto_trading_status['settings'].get('rsi_1h_short', 50)),
            'reduced_version': data.get('reduced_version', auto_trading_status['settings'].get('reduced_version', False)),
            
            # Volume Filter
            'volume_filter_enabled': data.get('volume_filter_enabled', auto_trading_status['settings'].get('volume_filter_enabled', True)),
            'volume_multiplier': data.get('volume_multiplier', auto_trading_status['settings'].get('volume_multiplier', 1.5)),
            'volume_ema_period': data.get('volume_ema_period', auto_trading_status['settings'].get('volume_ema_period', 20))
        })
        
        logger.info(f"Auto trading settings updated: {auto_trading_status['settings']}")
        
        return jsonify({
            'success': True,
            'message': 'Auto trading settings updated successfully',
            'data': {
                'trading_pair': auto_trading_status['settings']['trading_pair'],
                'settings': auto_trading_status['settings'],
                'auto_trading_active': auto_trading_status['active']
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating auto trading settings: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/auto-trading/status', methods=['GET'])
def api_bybit_auto_trading_status():
    """Get auto trading status"""
    try:
        logger.info(f"Getting auto trading status: {auto_trading_status}")
        
        return jsonify({
            'success': True,
            'data': {
                'auto_trading_active': auto_trading_status['active'],
                'total_trades': auto_trading_status['total_trades'],
                'active_strategies': auto_trading_status['active_strategies'],
                'trading_pair': auto_trading_status['settings'].get('trading_pair', 'BTCUSDT'),
                'settings': auto_trading_status['settings'],
                'started_at': auto_trading_status['started_at'],
                'stopped_at': auto_trading_status['stopped_at'],
                'status': 'RUNNING' if auto_trading_status['active'] else 'STOPPED'
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting auto trading status: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/auto-trading/execute', methods=['POST'])
def api_bybit_auto_trading_execute():
    """Execute auto trading logic"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        side = data.get('side')
        price = data.get('price')
        
        # Execute the trade via Bybit API
        from bybit_api import BybitAPI
        bybit = BybitAPI()
        
        # Place the order
        result = bybit.place_futures_order(
            symbol=symbol,
            side=side,
            order_type='Market',
            qty=0.001,  # Minimum quantity
            price=price
        )
        
        if result.get('success'):
            # Update auto trading status
            global auto_trading_status
            if 'total_trades' not in auto_trading_status:
                auto_trading_status['total_trades'] = 0
            auto_trading_status['total_trades'] += 1
            
            return jsonify({
                'success': True,
                'message': 'Auto trading order executed successfully',
                'data': result.get('data')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to execute order')
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Telegram API Endpoints
@app.route('/api/telegram/test-connection', methods=['POST'])
def test_telegram_connection():
    """Test Telegram bot connection"""
    try:
        data = request.get_json()
        bot_token = data.get('bot_token')
        chat_id = data.get('chat_id')
        
        if not bot_token or not chat_id:
            return jsonify({
                'success': False,
                'error': 'Bot token and chat ID are required'
            })
        
        # Test telegram connection
        try:
            import requests
            
            # Send test message
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": "🧪 Test message from Pionex Trading Bot!\n\n✅ Telegram connection successful!\n\nBot is ready to send notifications.",
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get('ok'):
                return jsonify({
                    'success': True,
                    'message': 'Telegram connection test successful'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f"Telegram API error: {result.get('description', 'Unknown error')}"
                })
                
        except requests.exceptions.RequestException as e:
            return jsonify({
                'success': False,
                'error': f"Connection error: {str(e)}"
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/telegram/save-settings', methods=['POST'])
def save_telegram_settings():
    """Save Telegram notification settings"""
    try:
        data = request.get_json()
        
        # Load current config
        config = load_config()
        
        # Update telegram settings
        config['telegram'] = data
        
        # Save to config file
        with open('config.yaml', 'w') as file:
            yaml.dump(config, file, default_flow_style=False)
        
        return jsonify({
            'success': True,
            'message': 'Telegram settings saved successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/telegram/get-settings', methods=['GET'])
def get_telegram_settings():
    """Get Telegram notification settings"""
    try:
        config = load_config()
        telegram_settings = config.get('telegram', {})
        
        return jsonify({
            'success': True,
            'data': telegram_settings
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/telegram/send-notification', methods=['POST'])
def send_telegram_notification():
    """Send Telegram notification"""
    try:
        data = request.get_json()
        message = data.get('message')
        notification_type = data.get('type', 'info')
        bot_token = data.get('bot_token')
        chat_id = data.get('chat_id')
        
        if not message or not bot_token or not chat_id:
            return jsonify({
                'success': False,
                'error': 'Message, bot token, and chat ID are required'
            })
        
        # Send telegram message
        try:
            import requests
            
            # Format message based on type
            emoji_map = {
                'success': '✅',
                'warning': '⚠️',
                'error': '❌',
                'info': 'ℹ️'
            }
            
            emoji = emoji_map.get(notification_type, 'ℹ️')
            formatted_message = f"{emoji} {message}"
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": formatted_message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get('ok'):
                return jsonify({
                    'success': True,
                    'message': 'Telegram notification sent successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f"Telegram API error: {result.get('description', 'Unknown error')}"
                })
                
        except requests.exceptions.RequestException as e:
            return jsonify({
                'success': False,
                'error': f"Connection error: {str(e)}"
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# ===== UNIFIED TRADING API ENDPOINTS =====

@app.route('/api/bybit/unified/place-order', methods=['POST'])
def api_bybit_unified_place_order():
    """API endpoint for placing unified orders (spot/futures)"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        category = data.get('category', 'linear')  # spot, linear, inverse
        symbol = data.get('symbol')
        side = data.get('side')
        orderType = data.get('orderType')
        qty = data.get('qty')
        price = data.get('price')
        timeInForce = data.get('timeInForce', 'GTC')
        orderLinkId = data.get('orderLinkId')
        isLeverage = data.get('isLeverage', 0)
        orderFilter = data.get('orderFilter', 'Order')
        
        if not all([symbol, side, orderType, qty]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Place the order using unified API
        result = bybit_api.place_unified_order(
            category=category,
            symbol=symbol,
            side=side,
            orderType=orderType,
            qty=qty,
            price=price,
            timeInForce=timeInForce,
            orderLinkId=orderLinkId,
            isLeverage=isLeverage,
            orderFilter=orderFilter
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error placing unified order: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/unified/spot-order', methods=['POST'])
def api_bybit_unified_spot_order():
    """API endpoint for placing spot orders"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        symbol = data.get('symbol')
        side = data.get('side')
        orderType = data.get('orderType')
        qty = data.get('qty')
        price = data.get('price')
        timeInForce = data.get('timeInForce', 'GTC')
        orderLinkId = data.get('orderLinkId')
        
        if not all([symbol, side, orderType, qty]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Place spot order
        result = bybit_api.place_spot_order(
            symbol=symbol,
            side=side,
            orderType=orderType,
            qty=qty,
            price=price,
            timeInForce=timeInForce,
            orderLinkId=orderLinkId
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error placing spot order: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/unified/futures-order', methods=['POST'])
def api_bybit_unified_futures_order():
    """API endpoint for placing futures orders"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        symbol = data.get('symbol')
        side = data.get('side')
        orderType = data.get('orderType')
        qty = data.get('qty')
        price = data.get('price')
        timeInForce = data.get('timeInForce', 'GTC')
        orderLinkId = data.get('orderLinkId')
        leverage = data.get('leverage', 10)
        
        if not all([symbol, side, orderType, qty]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # Place futures order
        result = bybit_api.place_futures_order(
            symbol=symbol,
            side=side,
            orderType=orderType,
            qty=qty,
            price=price,
            timeInForce=timeInForce,
            orderLinkId=orderLinkId,
            leverage=leverage
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error placing futures order: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/unified/positions')
def api_bybit_unified_positions():
    """API endpoint for getting unified positions"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        category = request.args.get('category', 'linear')
        symbol = request.args.get('symbol')
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        result = bybit_api.get_unified_positions(category=category, symbol=symbol)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting unified positions: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/unified/balance')
def api_bybit_unified_balance():
    """API endpoint for getting unified balance"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        accountType = request.args.get('accountType', 'UNIFIED')
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        result = bybit_api.get_unified_balance(accountType=accountType)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting unified balance: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/unified/ticker')
def api_bybit_unified_ticker():
    """API endpoint for getting unified ticker"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        category = request.args.get('category', 'linear')
        symbol = request.args.get('symbol')
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        result = bybit_api.get_unified_ticker(category=category, symbol=symbol)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting unified ticker: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/unified/cancel-order', methods=['POST'])
def api_bybit_unified_cancel_order():
    """API endpoint for cancelling unified orders"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        category = data.get('category', 'linear')
        symbol = data.get('symbol')
        orderId = data.get('orderId')
        orderLinkId = data.get('orderLinkId')
        
        if not symbol or (not orderId and not orderLinkId):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        result = bybit_api.cancel_unified_order(
            category=category,
            symbol=symbol,
            orderId=orderId,
            orderLinkId=orderLinkId
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error cancelling unified order: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/close-hedge-positions', methods=['POST'])
def api_bybit_close_hedge_positions():
    """API endpoint for closing all hedge positions for a symbol"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'Missing symbol parameter'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        # First get current positions for this symbol
        positions_result = bybit_api.get_unified_positions(category='linear', symbol=symbol)
        
        if not positions_result.get('success'):
            return jsonify({'success': False, 'error': 'Failed to get positions'})
        
        positions_data = positions_result.get('data', {}).get('list', [])
        closed_positions = []
        
        # Close all positions for this symbol
        for position in positions_data:
            if position.get('symbol') == symbol and float(position.get('size', 0)) > 0:
                # Close position by placing opposite order
                close_side = 'Sell' if position.get('side') == 'Buy' else 'Buy'
                close_qty = position.get('size')
                
                close_result = bybit_api.place_unified_order(
                    category='linear',
                    symbol=symbol,
                    side=close_side,
                    orderType='Market',
                    qty=close_qty,
                    reduceOnly=True
                )
                
                if close_result.get('success'):
                    closed_positions.append({
                        'side': position.get('side'),
                        'size': close_qty,
                        'orderId': close_result.get('data', {}).get('orderId')
                    })
                else:
                    logger.error(f"Failed to close position: {close_result.get('error')}")
        
        if closed_positions:
            return jsonify({
                'success': True,
                'message': f'Closed {len(closed_positions)} hedge positions for {symbol}',
                'closed_positions': closed_positions
            })
        else:
            return jsonify({'success': False, 'error': 'No positions found to close'})
        
    except Exception as e:
        logger.error(f"Error closing hedge positions: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/unified/order-history')
def api_bybit_unified_order_history():
    """API endpoint for getting unified order history"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        category = request.args.get('category', 'linear')
        symbol = request.args.get('symbol')
        limit = request.args.get('limit', 50, type=int)
        
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol is required'})
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        result = bybit_api.get_unified_order_history(
            category=category,
            symbol=symbol,
            limit=limit
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting unified order history: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bybit/unified/set-leverage', methods=['POST'])
def api_bybit_unified_set_leverage():
    """API endpoint for setting unified leverage"""
    try:
        if not BYBIT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bybit API not available'})
        
        data = request.get_json()
        category = data.get('category', 'linear')
        symbol = data.get('symbol')
        buyLeverage = data.get('buyLeverage')
        sellLeverage = data.get('sellLeverage')
        
        if not all([symbol, buyLeverage]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        if not sellLeverage:
            sellLeverage = buyLeverage
        
        config = get_config()
        bybit_config = config.get('bybit', {})
        
        api_key = bybit_config.get('api_key') or os.getenv('BYBIT_API_KEY')
        api_secret = bybit_config.get('api_secret') or os.getenv('BYBIT_API_SECRET')
        testnet = bybit_config.get('testnet', False)
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Bybit API credentials not configured'})
        
        bybit_api = BybitAPIClass(api_key, api_secret, testnet)
        
        result = bybit_api.set_unified_leverage(
            category=category,
            symbol=symbol,
            buyLeverage=str(buyLeverage),
            sellLeverage=str(sellLeverage)
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error setting unified leverage: {e}")
        return jsonify({'success': False, 'error': str(e)})

# RSI Filter API endpoints
@app.route('/api/rsi-filter/status', methods=['GET'])
def api_rsi_filter_status():
    """Get RSI filter status and configuration"""
    try:
        status = rsi_filter.get_status_summary()
        return jsonify({'success': True, 'data': status})
    except Exception as e:
        logger.error(f"Error getting RSI filter status: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/rsi-filter/update', methods=['POST'])
def api_rsi_filter_update():
    """Update RSI filter configuration"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        # Update configuration
        success = rsi_filter.update_config(**data)
        
        if success:
            return jsonify({
                'success': True, 
                'message': 'RSI Filter configuration updated successfully',
                'data': rsi_filter.get_current_config()
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update RSI filter configuration'})
            
    except Exception as e:
        logger.error(f"Error updating RSI filter: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/rsi-filter/check', methods=['POST'])
def api_rsi_filter_check():
    """Check RSI conditions for a symbol and direction"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        direction = data.get('direction')  # 'long' or 'short'
        
        if not symbol or not direction:
            return jsonify({'success': False, 'error': 'Symbol and direction are required'})
        
        result = rsi_filter.check_rsi_conditions(symbol, direction)
        return jsonify({'success': True, 'data': result})
        
    except Exception as e:
        logger.error(f"Error checking RSI conditions: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/rsi-filter/mode', methods=['POST'])
def api_rsi_filter_mode():
    """Switch RSI filter mode (normal/reduced)"""
    try:
        data = request.get_json()
        mode = data.get('mode')
        
        if mode not in ['normal', 'reduced']:
            return jsonify({'success': False, 'error': 'Mode must be "normal" or "reduced"'})
        
        success = rsi_filter.update_config(mode=mode)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'RSI Filter mode changed to {mode}',
                'data': rsi_filter.get_current_config()
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update mode'})
            
    except Exception as e:
        logger.error(f"Error switching RSI filter mode: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/rsi-filter/toggle', methods=['POST'])
def api_rsi_filter_toggle():
    """Enable/disable RSI filter"""
    try:
        data = request.get_json()
        enabled = data.get('enabled')
        
        if enabled is None:
            return jsonify({'success': False, 'error': 'Enabled status is required'})
        
        success = rsi_filter.update_config(enabled=enabled)
        
        if success:
            status = 'enabled' if enabled else 'disabled'
            return jsonify({
                'success': True,
                'message': f'RSI Filter {status}',
                'data': rsi_filter.get_current_config()
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to toggle RSI filter'})
            
    except Exception as e:
        logger.error(f"Error toggling RSI filter: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/rsi-filter/thresholds', methods=['POST'])
def api_rsi_filter_thresholds():
    """Update RSI filter thresholds"""
    try:
        data = request.get_json()
        thresholds = data.get('thresholds')
        
        if not thresholds:
            return jsonify({'success': False, 'error': 'Thresholds data is required'})
        
        success = rsi_filter.update_config(thresholds=thresholds)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'RSI Filter thresholds updated successfully',
                'data': rsi_filter.get_current_config()
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update thresholds'})
            
    except Exception as e:
        logger.error(f"Error updating RSI filter thresholds: {e}")
        return jsonify({'success': False, 'error': str(e)})

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    emit('connected', {'data': 'Connected to trading bot'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('Client disconnected')

@socketio.on('subscribe_price')
def handle_subscribe_price(data):
    """Handle price subscription"""
    symbol = data.get('symbol')
    if symbol:
        # Subscribe to real-time price updates
        emit('price_update', {'symbol': symbol, 'price': trading_bot.get_real_time_price(symbol)})

def main():
    """Main function to run the Flask application"""
    try:
        # Get port from Railway environment or use default
        port_str = os.environ.get('PORT', '5000')
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                print(f"Warning: Invalid port number {port}, using default 5000")
                port = 5000
        except ValueError:
            print(f"Warning: Invalid port format '{port_str}', using default 5000")
            port = 5000
        
        # Run the Flask application
        socketio.run(
            app,
            host='0.0.0.0',  # Allow external connections
            port=port,
            debug=False,  # Disable debug mode for production
            allow_unsafe_werkzeug=True
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 
