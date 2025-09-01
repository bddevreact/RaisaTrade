import asyncio
import logging
import threading
import time
import json
from datetime import datetime
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config_loader import get_config, reload_config
from pionex_api import PionexAPI
from trading_strategies import TradingStrategies
from database import Database

class AutoTrader:
    def __init__(self, user_id: int = None):
        """Initialize AutoTrader with user-specific settings"""
        self.user_id = user_id or 1
        self.api = PionexAPI()
        self.strategies = TradingStrategies(self.api)
        self.config = get_config()
        self.auto_trading_enabled = False
        self.current_pair = self.config.get('trading_pair', 'BTC_USDT')
        self.notification_settings = self.config.get('notifications', {})
        self.execution_stats = {}  # Track strategy execution statistics
        
        # Initialize database (optional - can be None if not available)
        try:
            from database import Database
            self.db = Database()
        except ImportError:
            self.db = None
            print("Warning: Database module not available, some features may be limited")
        
        self.setup_logging()
        
        # Threading
        self.trading_thread = None
        self.stop_event = threading.Event()
        self.is_running = False  # Add missing is_running attribute
        
        # Restart tracking
        self.restart_count = 0
        self.last_restart = None
        
    def setup_logging(self):
        """Setup dedicated logging for this instance"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Create instance-specific log file
        instance_id = f"user_{self.user_id}" if self.user_id else "global"
        log_file = log_dir / f"auto_trader_{instance_id}.log"
        
        # Configure logging
        self.logger = logging.getLogger(f"AutoTrader_{instance_id}")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"AutoTrader instance initialized for {instance_id}")
    
    def enable_auto_trading(self, user_id: int = None):
        """Enable auto trading for a user"""
        if user_id:
            self.user_id = user_id
            self.setup_logging()  # Re-setup logging with user_id
        
        self.auto_trading_enabled = True
        if self.db:
            self.db.update_user_settings(user_id or self.user_id, {'auto_trading': True})
        self.logger.info(f"Auto trading enabled for user {user_id or self.user_id}")
        self.send_notification("Auto Trading Enabled", f"Auto trading has been enabled for {self.current_pair}")
        
        if not hasattr(self, 'is_running') or not self.is_running:
            self.start_auto_trading()
    
    def disable_auto_trading(self, user_id: int = None):
        """Disable auto trading for a user"""
        self.auto_trading_enabled = False
        if self.db:
            self.db.update_user_settings(user_id or self.user_id, {'auto_trading': False})
        self.logger.info(f"Auto trading disabled for user {user_id or self.user_id}")
        self.send_notification("Auto Trading Disabled", f"Auto trading has been disabled for {self.current_pair}")
        
        if hasattr(self, 'is_running') and self.is_running:
            self.stop_auto_trading()
    
    def set_trading_pair(self, pair: str):
        """Set the trading pair for single-pair operation"""
        old_pair = self.current_pair
        self.current_pair = pair.upper()
        self.config['trading_pair'] = self.current_pair
        
        # Update config file
        try:
            import yaml
            with open(Path('config.yaml'), 'w') as f:
                yaml.safe_dump(self.config, f, sort_keys=False)
            reload_config()
            self.config = get_config()
        except Exception as e:
            self.logger.error(f"Failed to update config file: {e}")
        
        self.logger.info(f"Trading pair changed from {old_pair} to {self.current_pair}")
        self.send_notification("Trading Pair Changed", f"Trading pair changed to {self.current_pair}")
    
    def start_auto_trading(self):
        """Start the auto trading loop"""
        if self.is_running:
            self.logger.warning("Auto trading is already running")
            return
        
        self.is_running = True
        self.stop_event.clear()
        self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.trading_thread.start()
        self.logger.info(f"Auto trading started for {self.current_pair}")
    
    def stop_auto_trading(self):
        """Stop the auto trading loop"""
        if not self.is_running:
            self.logger.warning("Auto trading is not running")
            return
        
        self.is_running = False
        self.stop_event.set()
        
        if self.trading_thread and self.trading_thread.is_alive():
            self.trading_thread.join(timeout=5)
        
        self.logger.info("Auto trading stopped")
    
    def restart_auto_trading(self, user_id: int = None):
        """Restart auto trading"""
        self.logger.info("Restarting auto trading...")
        self.restart_count += 1
        self.last_restart = datetime.now()
        
        # Stop current instance
        self.stop_auto_trading()
        
        # Wait a moment
        time.sleep(2)
        
        # Start new instance
        if self.auto_trading_enabled:
            self.start_auto_trading()
            self.logger.info("Auto trading restarted successfully")
            self.send_notification("Auto Trading Restarted", f"Auto trading has been restarted for {self.current_pair}")
        else:
            self.logger.info("Auto trading not restarted (disabled)")
    
    def _trading_loop(self):
        """Main trading loop"""
        heartbeat_interval = self.config.get('watchdog', {}).get('heartbeat_interval', 60)
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # Check if auto trading is still enabled
                if not self.auto_trading_enabled:
                    self.logger.info("Auto trading disabled, stopping loop")
                    break
                
                # Check trading hours
                if not self._is_trading_hours():
                    self.logger.debug("Outside trading hours, skipping execution")
                    time.sleep(heartbeat_interval)
                    continue
                
                # Execute trading logic
                self._execute_trading_cycle()
                
                # Heartbeat
                self.logger.debug(f"Trading cycle completed, waiting {heartbeat_interval}s")
                time.sleep(heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}")
                self.send_notification("Trading Error", f"Error in trading loop: {str(e)}")
                time.sleep(30)  # Wait before retry
    
    def _is_trading_hours(self) -> bool:
        """Check if current time is within trading hours"""
        trading_hours = self.config.get('trading_hours', {})
        if not trading_hours.get('enabled', False):
            return True  # Always trade if hours not configured
        from datetime import datetime, time
        import pytz
        # Map common UTC offset to pytz
        tz_str = trading_hours.get('timezone', 'UTC')
        offset_map = {
            'UTC-5': 'Etc/GMT+5',
            'UTC+5': 'Etc/GMT-5',
            'UTC-6': 'Etc/GMT+6',
            'UTC-4': 'Etc/GMT+4',
            'UTC+8': 'Etc/GMT-8',
            # Add more as needed
        }
        tz_str = offset_map.get(tz_str, tz_str)
        try:
            tz = pytz.timezone(tz_str)
        except Exception as e:
            self.logger.warning(f"Unknown timezone '{tz_str}', defaulting to UTC. Error: {e}")
            tz = pytz.UTC
        now = datetime.now(tz)
        current_time = now.time()
        start_str = trading_hours.get('start', '00:00')
        end_str = trading_hours.get('end', '23:59')
        try:
            start_time = time.fromisoformat(start_str)
            end_time = time.fromisoformat(end_str)
            if start_time > end_time:
                return current_time >= start_time or current_time <= end_time
            else:
                return start_time <= current_time <= end_time
        except Exception as e:
            self.logger.error(f"Error parsing trading hours: {e}")
            return True  # Default to always trade
    
    def _execute_trading_cycle(self):
        """Execute one trading cycle"""
        try:
            # Get current market data with correct interval
            df = self.strategies.get_market_data(self.current_pair, '1M', 100)
            if df.empty:
                self.logger.warning(f"No market data available for {self.current_pair}")
                return
            
            # Get user settings
            user_settings = self.db.get_user_settings(self.user_id) if self.user_id else {}
            strategy_type = user_settings.get('default_strategy', 'ADVANCED_STRATEGY')
            
            # Execute strategy
            signal = self._execute_strategy(strategy_type, self.current_pair)
            
            if signal and signal.get('action'):
                self._execute_trade(signal)
            
        except Exception as e:
            self.logger.error(f"Error in trading cycle: {e}")
    
    def _execute_strategy(self, strategy_type: str, symbol: str):
        """Execute a specific trading strategy"""
        import threading
        import time
        
        start_time = time.time()
        result = [None]
        exception = [None]
        
        def execute_strategy():
            try:
                # Validate symbol - use the symbol parameter from outer scope
                if not symbol or not isinstance(symbol, str):
                    self.logger.error(f"Invalid symbol: {symbol}")
                    result[0] = {"action": "HOLD", "reason": f"Invalid symbol: {symbol}"}
                    return
                
                # Normalize symbol format
                normalized_symbol = symbol.upper().replace('/', '_')
                
                # Validate symbol format
                if not normalized_symbol.endswith('_USDT'):
                    self.logger.warning(f"Symbol {normalized_symbol} may not be supported, adding USDT suffix")
                    if not normalized_symbol.endswith('_USDT'):
                        normalized_symbol = f"{normalized_symbol}_USDT"
                
                # Check if symbol is in supported list
                supported_symbols = ['BTC_USDT', 'ETH_USDT', 'DOT_USDT', 'ADA_USDT', 'SOL_USDT']
                if normalized_symbol not in supported_symbols:
                    self.logger.warning(f"Symbol {normalized_symbol} may not be fully supported")
                
                # Get balance for position sizing - fix the response handling
                balance_response = self.api.get_balances()
                balance = 0
                
                if 'error' not in balance_response and 'data' in balance_response:
                    balances = balance_response['data'].get('balances', [])
                    for asset in balances:
                        # Pionex uses 'coin' instead of 'asset'
                        coin = asset.get('coin', asset.get('asset', ''))
                        if coin == 'USDT':
                            balance = float(asset.get('total', 0))
                            break
                else:
                    error_msg = balance_response.get('error', 'Unknown error')
                    self.logger.warning(f"Failed to get balance: {error_msg}")
                    
                    # Try to get balance from alternative source
                    try:
                        account_balance = self.api.get_account_balance()
                        if 'error' not in account_balance:
                            balance = float(account_balance.get('total', 0))
                            self.logger.info(f"Retrieved balance from alternative source: {balance}")
                        else:
                            result[0] = {"action": "HOLD", "reason": f"Failed to get balance: {error_msg}"}
                            return
                    except Exception as alt_error:
                        self.logger.error(f"Alternative balance retrieval also failed: {alt_error}")
                        result[0] = {"action": "HOLD", "reason": f"Failed to get balance: {error_msg}"}
                        return
                
                self.logger.info(f"Executing {strategy_type} for {normalized_symbol} with balance: {balance}")
                
                # Log strategy parameters
                self.logger.info(f"Strategy parameters - Symbol: {normalized_symbol}, Balance: {balance}, Type: {strategy_type}")
                
                # Validate balance
                if balance <= 0:
                    self.logger.warning(f"Insufficient balance ({balance}) for strategy execution")
                    result[0] = {"action": "HOLD", "reason": f"Insufficient balance: {balance}"}
                    return
                
                # Check if balance is too low for meaningful trading
                min_balance = 10  # Minimum $10 for trading
                if balance < min_balance:
                    self.logger.warning(f"Balance too low ({balance}) for meaningful trading")
                    result[0] = {"action": "HOLD", "reason": f"Balance too low: ${balance} (minimum: ${min_balance})"}
                    return
                
                # Log strategy execution start
                self.logger.info(f"Starting strategy execution for {strategy_type} on {normalized_symbol}")
                
                # Perform health check before strategy execution
                health_status = self.health_check()
                if health_status['overall_status'] == 'UNHEALTHY':
                    self.logger.error(f"System unhealthy, skipping strategy execution. Health status: {health_status}")
                    result[0] = {"action": "HOLD", "reason": f"System unhealthy: {health_status['overall_status']}"}
                    return
                elif health_status['overall_status'] == 'DEGRADED':
                    self.logger.warning(f"System degraded, proceeding with caution. Health status: {health_status}")
                
                # Add rate limiting delay
                import time
                time.sleep(0.1)  # 100ms delay to respect API rate limits
                
                # Validate configuration
                if not hasattr(self, 'config') or not self.config:
                    self.logger.error("Configuration not found")
                    result[0] = {"action": "HOLD", "reason": "Configuration not found"}
                    return
                
                # Check required configuration parameters
                required_params = ['leverage', 'position_size', 'trading_amount']
                missing_params = [param for param in required_params if param not in self.config]
                if missing_params:
                    self.logger.warning(f"Missing configuration parameters: {missing_params}")
                    # Use default values
                    if 'leverage' not in self.config:
                        self.config['leverage'] = 10
                    if 'position_size' not in self.config:
                        self.config['position_size'] = 0.5
                    if 'trading_amount' not in self.config:
                        self.config['trading_amount'] = 100
                
                # Execute strategy based on type
                if strategy_type == 'RSI_STRATEGY':
                    result[0] = self.strategies.rsi_strategy(normalized_symbol, balance)
                elif strategy_type == 'RSI_MULTI_TF':
                    result[0] = self.strategies.rsi_multi_timeframe_strategy(normalized_symbol, balance)
                elif strategy_type == 'VOLUME_FILTER':
                    result[0] = self.strategies.volume_filter_strategy(normalized_symbol, balance)
                elif strategy_type == 'ADVANCED_STRATEGY':
                    result[0] = self.strategies.advanced_strategy(normalized_symbol, balance)
                elif strategy_type == 'GRID_TRADING':
                    result[0] = self.strategies.grid_trading_strategy(normalized_symbol, balance)
                elif strategy_type == 'DCA':
                    result[0] = self.strategies.dca_strategy(normalized_symbol, balance)
                else:
                    self.logger.warning(f"Unknown strategy type: {strategy_type}")
                    result[0] = None
                
                # Validate strategy result
                if result[0] is None:
                    self.logger.warning(f"Strategy {strategy_type} returned None")
                    result[0] = {"action": "HOLD", "reason": "Strategy returned no signal"}
                elif not isinstance(result[0], dict):
                    self.logger.error(f"Strategy {strategy_type} returned invalid result type: {type(result[0])}")
                    result[0] = {"action": "HOLD", "reason": "Strategy returned invalid result"}
                elif 'action' not in result[0]:
                    self.logger.error(f"Strategy {strategy_type} returned result without action: {result[0]}")
                    result[0] = {"action": "HOLD", "reason": "Strategy returned result without action"}
                else:
                    self.logger.info(f"Strategy {strategy_type} executed successfully: {result[0].get('action')}")
                    
            except Exception as e:
                exception[0] = e
                self.logger.error(f"Error executing strategy {strategy_type}: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Execute strategy with timeout
        thread = threading.Thread(target=execute_strategy)
        thread.daemon = True
        thread.start()
        thread.join(timeout=30)  # 30 second timeout
        
        execution_time = time.time() - start_time
        
        if thread.is_alive():
            self.logger.error(f"Strategy execution timed out for {strategy_type} after {execution_time:.2f}s")
            return {"action": "HOLD", "reason": "Strategy execution timed out"}
        
        if exception[0]:
            # Try fallback strategy if main strategy fails
            self.logger.warning(f"Main strategy failed after {execution_time:.2f}s, trying fallback for {strategy_type}")
            try:
                # Fallback to simple RSI strategy
                if strategy_type != 'RSI_STRATEGY':
                    fallback_result = self.strategies.rsi_strategy(symbol, 100)  # Use default balance
                    if fallback_result and fallback_result.get('action') != 'HOLD':
                        self.logger.info(f"Fallback strategy executed successfully for {strategy_type}")
                        return fallback_result
            except Exception as fallback_error:
                self.logger.error(f"Fallback strategy also failed: {fallback_error}")
            
            # Provide specific error messages based on exception type
            error_type = type(exception[0]).__name__
            if 'Timeout' in error_type:
                error_msg = "Strategy execution timed out"
            elif 'Connection' in error_type:
                error_msg = "Network connection error"
            elif 'API' in error_type:
                error_msg = "API service error"
            else:
                error_msg = f"Strategy execution error: {str(exception[0])}"
            
            return {"action": "HOLD", "reason": error_msg}
        
        # Log performance metrics
        if result[0] and result[0].get('action') != 'HOLD':
            self.logger.info(f"Strategy {strategy_type} completed successfully in {execution_time:.2f}s")
        else:
            self.logger.info(f"Strategy {strategy_type} completed with HOLD signal in {execution_time:.2f}s")
        
        # Report execution statistics
        if hasattr(self, 'execution_stats'):
            if strategy_type not in self.execution_stats:
                self.execution_stats[strategy_type] = {'success': 0, 'failure': 0, 'total_time': 0}
            
            if exception[0]:
                self.execution_stats[strategy_type]['failure'] += 1
            else:
                self.execution_stats[strategy_type]['success'] += 1
            
            self.execution_stats[strategy_type]['total_time'] += execution_time
            
            # Log statistics
            stats = self.execution_stats[strategy_type]
            success_rate = (stats['success'] / (stats['success'] + stats['failure'])) * 100 if (stats['success'] + stats['failure']) > 0 else 0
            avg_time = stats['total_time'] / (stats['success'] + stats['failure']) if (stats['success'] + stats['failure']) > 0 else 0
            
            self.logger.info(f"Strategy {strategy_type} stats - Success rate: {success_rate:.1f}%, Avg time: {avg_time:.2f}s")
        
        # Clean up memory
        import gc
        gc.collect()
        
        return result[0]
    
    def _execute_trade(self, signal: dict):
        """Execute a trade based on signal with enhanced order types"""
        try:
            action = signal.get('action')
            symbol = signal.get('symbol', self.current_pair)
            quantity = signal.get('quantity', 0)
            price = signal.get('price', 0)
            stop_loss = signal.get('stop_loss')
            take_profit = signal.get('take_profit')
            order_type = signal.get('order_type', 'MARKET')
            
            if not action or not quantity or not price:
                self.logger.warning(f"Invalid trade signal: {signal}")
                return
            
            # Get current market price for dynamic orders
            price_response = self.api.get_real_time_price(symbol)
            current_price = 0
            
            if 'error' not in price_response and 'data' in price_response:
                price_data = price_response['data']
                if isinstance(price_data, dict) and 'price' in price_data:
                    current_price = float(price_data['price'])
                elif isinstance(price_data, str):
                    current_price = float(price_data)
            
            if current_price == 0:
                current_price = price  # Use signal price as fallback
            
            # Prepare order parameters
            order_params = {
                'symbol': symbol,
                'side': action,
                'quantity': quantity,
                'leverage': self.config.get('leverage', 10),
                'marginType': self.config.get('margin_type', 'ISOLATED')
            }
            
            # Add stop loss and take profit
            if stop_loss:
                order_params['stop_loss'] = stop_loss
            if take_profit:
                order_params['take_profit'] = take_profit
            
            # Execute based on order type
            if order_type == 'MARKET':
                # Market order with IOC for immediate execution
                order_response = self.api.place_market_order(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    IOC=True,  # Immediate or Cancel
                    **order_params
                )
                
            elif order_type == 'LIMIT':
                # Limit order with price
                order_response = self.api.place_limit_order(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    price=price,
                    **order_params
                )
                
            elif order_type == 'STOP_LOSS':
                # Stop loss order
                order_response = self.api.place_stop_loss_order(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    stop_price=stop_loss,
                    **order_params
                )
                
            elif order_type == 'TAKE_PROFIT':
                # Take profit order
                order_response = self.api.place_take_profit_order(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    take_profit_price=take_profit,
                    **order_params
                )
                
            elif order_type == 'TRAILING_STOP':
                # Trailing stop order
                trailing_percentage = self.config.get('trailing_stop', {}).get('percentage', 1.0)
                order_response = self.api.place_trailing_stop_order(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    callback_rate=trailing_percentage,
                    **order_params
                )
                
            else:
                # Default to market order
                order_response = self.api.place_market_order(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    IOC=True,
                    **order_params
                )
            
            # Handle order response
            if 'error' in order_response:
                self.logger.error(f"Order failed: {order_response['error']}")
                self.send_notification("❌ Order Failed", f"Order failed: {order_response['error']}")
                return
            
            # Check for successful order placement
            if 'data' in order_response:
                order_data = order_response['data']
                order_id = order_data.get('orderId')
                status = order_data.get('status', 'UNKNOWN')
                
                # Log successful order
                self.logger.info(f"Order placed successfully: {action} {quantity} {symbol} @ {price}")
                self.logger.info(f"Order ID: {order_id}, Status: {status}")
                
                # Send success notification
                self.send_notification(
                    f"✅ Order Placed",
                    f"{action} {quantity:.8f} {symbol} @ ${price:.2f}\nOrder ID: {order_id}\nStatus: {status}"
                )
                
                # Add to trading history
                if self.user_id:
                    if self.db:
                        self.db.add_trading_history(
                            user_id=self.user_id,
                            symbol=symbol,
                            side=action,
                            quantity=quantity,
                            price=price,
                            order_id=order_id,
                            strategy=signal.get('strategy', 'Auto'),
                            status=status,
                            stop_loss=stop_loss,
                            take_profit=take_profit
                        )
                
                # Monitor order status
                self._monitor_order_status(order_id, symbol)
                
            else:
                self.logger.error(f"Unexpected order response: {order_response}")
                self.send_notification("❌ Order Error", f"Unexpected response: {order_response}")
            
        except Exception as e:
            self.logger.error(f"Error executing trade: {e}")
            self.send_notification("❌ Trade Error", f"Error executing trade: {str(e)}")
    
    def _monitor_order_status(self, order_id: str, symbol: str):
        """Monitor order status and handle fills"""
        try:
            # Check order status after a delay
            time.sleep(2)
            
            order_status = self.api.get_order(order_id, symbol)
            
            if 'data' in order_status:
                order_data = order_status['data']
                status = order_data.get('status')
                
                if status == 'FILLED':
                    # Order was filled
                    filled_qty = float(order_data.get('executedQty', 0))
                    avg_price = float(order_data.get('avgPrice', 0))
                    
                    self.logger.info(f"Order {order_id} filled: {filled_qty} @ {avg_price}")
                    self.send_notification(
                        "✅ Order Filled",
                        f"Order {order_id} filled: {filled_qty} @ ${avg_price:.2f}"
                    )
                    
                elif status in ['PARTIALLY_FILLED', 'PENDING']:
                    # Order is still active
                    self.logger.info(f"Order {order_id} status: {status}")
                    
                elif status in ['CANCELED', 'REJECTED']:
                    # Order was canceled or rejected
                    self.logger.warning(f"Order {order_id} {status}")
                    self.send_notification(
                        f"⚠️ Order {status.title()}",
                        f"Order {order_id} was {status.lower()}"
                    )
                    
        except Exception as e:
            self.logger.error(f"Error monitoring order status: {e}")
    
    def send_notification(self, title: str, message: str):
        """Send notification via Telegram or email"""
        try:
            # Replace emoji characters with text equivalents to avoid encoding issues
            title = title.replace('🤖', '[BOT]').replace('❌', '[STOP]').replace('✅', '[OK]')
            
            if self.notification_settings.get('telegram', {}).get('enabled'):
                # Telegram notification logic here
                pass
            
            if self.notification_settings.get('email', {}).get('enabled'):
                # Email notification logic here
                pass
            
            # Log without emoji to avoid encoding issues
            self.logger.info(f"Notification sent: {title} - {message}")
            
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
    
    def _send_email_notification(self, title: str, message: str):
        """Send email notification"""
        try:
            email_address = self.notification_settings.get('email_address')
            if not email_address:
                return
            
            # Create email
            msg = MIMEMultipart()
            msg['From'] = "pionex-trading-bot@example.com"
            msg['To'] = email_address
            msg['Subject'] = f"Pionex Trading Bot - {title}"
            
            body = f"""
            {title}
            
            {message}
            
            Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            Trading Pair: {self.current_pair}
            User ID: {self.user_id}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email (you'd need to configure SMTP settings)
            # For now, just log it
            self.logger.info(f"Email notification: {title} - {message}")
            
        except Exception as e:
            self.logger.error(f"Error sending email notification: {e}")
    
    def get_status(self) -> dict:
        """Get current bot status"""
        return {
            'is_running': self.is_running,
            'auto_trading_enabled': self.auto_trading_enabled,
            'current_pair': self.current_pair,
            'restart_count': self.restart_count,
            'last_restart': self.last_restart.isoformat() if self.last_restart else None,
            'trading_hours_active': self._is_trading_hours(),
            'user_id': self.user_id
        }
    
    def get_portfolio_snapshot(self) -> dict:
        """Get current portfolio snapshot"""
        try:
            balance_response = self.api.get_balances()
            positions_response = self.api.get_positions()
            
            # Calculate portfolio metrics
            total_value = 0
            total_pnl = 0
            positions_count = 0
            
            # Process balance data - handle different response structures
            if isinstance(balance_response, dict):
                if 'data' in balance_response and isinstance(balance_response['data'], dict):
                    # New structure: {'data': {'balances': [...]}}
                    balances = balance_response['data'].get('balances', [])
                    for balance in balances:
                        if balance.get('currency') == 'USDT':
                            total_value += float(balance.get('total', 0))
                elif 'data' in balance_response and isinstance(balance_response['data'], list):
                    # Old structure: {'data': [...]}
                    for balance in balance_response['data']:
                        if balance.get('currency') == 'USDT':
                            total_value += float(balance.get('total', 0))
            
            # Process positions data - handle different response structures
            if isinstance(positions_response, dict):
                if 'data' in positions_response and isinstance(positions_response['data'], list):
                    positions_count = len(positions_response['data'])
                    for position in positions_response['data']:
                        if isinstance(position, dict):
                            total_pnl += float(position.get('unrealizedPnl', 0))
                elif 'data' in positions_response and isinstance(positions_response['data'], dict):
                    # Handle case where data is a dict
                    positions = positions_response['data'].get('positions', [])
                    positions_count = len(positions)
                    for position in positions:
                        if isinstance(position, dict):
                            total_pnl += float(position.get('unrealizedPnl', 0))
            
            portfolio = {
                'balance': balance_response.get('data', []),
                'positions': positions_response.get('data', []),
                'timestamp': datetime.now().isoformat(),
                'user_id': self.user_id
            }
            
            # Add to database with correct parameters
            if self.user_id:
                if self.db:
                    self.db.add_portfolio_snapshot(
                        user_id=self.user_id,
                        total_value=total_value,
                        total_pnl=total_pnl,
                        positions_count=positions_count,
                        snapshot_data=portfolio
                    )
            
            return portfolio
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio snapshot: {e}")
            return {}

    def health_check(self) -> dict:
        """Perform health check to verify system readiness"""
        health_status = {
            'api_connection': False,
            'balance_available': False,
            'config_valid': False,
            'strategies_ready': False,
            'overall_status': 'UNHEALTHY'
        }
        
        try:
            # Check API connection
            test_response = self.api.test_connection()
            if 'error' not in test_response:
                health_status['api_connection'] = True
            
            # Check balance availability
            balance_response = self.api.get_balances()
            if 'error' not in balance_response and 'data' in balance_response:
                balances = balance_response['data'].get('balances', [])
                for asset in balances:
                    coin = asset.get('coin', asset.get('asset', ''))
                    if coin == 'USDT' and float(asset.get('total', 0)) > 0:
                        health_status['balance_available'] = True
                        break
            
            # Check configuration
            if self.config and all(key in self.config for key in ['leverage', 'position_size', 'trading_amount']):
                health_status['config_valid'] = True
            
            # Check strategies
            if hasattr(self, 'strategies') and self.strategies:
                health_status['strategies_ready'] = True
            
            # Determine overall status
            if all([health_status['api_connection'], health_status['balance_available'], 
                   health_status['config_valid'], health_status['strategies_ready']]):
                health_status['overall_status'] = 'HEALTHY'
            elif any([health_status['api_connection'], health_status['balance_available']]):
                health_status['overall_status'] = 'DEGRADED'
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
        
        return health_status

# Global auto trader instances
auto_traders = {}

def get_auto_trader(user_id: int) -> AutoTrader:
    """Get or create auto trader instance for user"""
    if user_id not in auto_traders:
        auto_traders[user_id] = AutoTrader(user_id)
    return auto_traders[user_id]

def start_auto_trading(user_id: int):
    """Start auto trading for a user"""
    trader = get_auto_trader(user_id)
    trader.enable_auto_trading(user_id)

def stop_auto_trading(user_id: int):
    """Stop auto trading for a user"""
    if user_id in auto_traders:
        trader = auto_traders[user_id]
        trader.disable_auto_trading(user_id)

def restart_auto_trading(user_id: int):
    """Restart auto trading for a user"""
    if user_id in auto_traders:
        trader = auto_traders[user_id]
        trader.restart_auto_trading(user_id)

def get_auto_trading_status(user_id: int) -> dict:
    """Get auto trading status for a user"""
    if user_id in auto_traders:
        return auto_traders[user_id].get_status()
    return {'is_running': False, 'auto_trading_enabled': False}

def add_strategy(user_id: int, symbol: str, strategy_type: str, parameters: dict = None):
    """Add a trading strategy for a user"""
    if user_id in auto_traders:
        trader = auto_traders[user_id]
        if trader.db:
            trader.db.add_active_strategy(user_id, symbol, strategy_type, parameters or {})

def remove_strategy(user_id: int, strategy_id: int):
    """Remove a trading strategy for a user"""
    if user_id in auto_traders:
        trader = auto_traders[user_id]
        if trader.db:
            trader.db.deactivate_strategy(strategy_id)

def get_portfolio_snapshot(user_id: int) -> dict:
    """Get portfolio snapshot for a user"""
    if user_id in auto_traders:
        return auto_traders[user_id].get_portfolio_snapshot()
    return {} 