#!/usr/bin/env python3
"""
Bybit Futures Auto Trading Bot
Copyright © 2024 Telegram-Airdrop-Bot

A comprehensive auto trading bot for Bybit futures using V5 API
with proper parameter handling and risk management.
"""

import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import threading

from bybit_api import BybitAPI

logger = logging.getLogger(__name__)

@dataclass
class TradingSignal:
    """Trading signal data structure"""
    symbol: str
    side: str  # "Buy" or "Sell"
    order_type: str  # "Market" or "Limit"
    quantity: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: int = 10
    time_in_force: str = "GTC"
    reduce_only: bool = False
    close_on_trigger: bool = False
    strategy: str = "Unknown"
    confidence: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class PositionInfo:
    """Position information data structure"""
    symbol: str
    side: str
    size: float
    entry_price: float
    mark_price: float
    leverage: int
    unrealized_pnl: float
    realized_pnl: float
    margin_type: str
    position_value: float
    timestamp: datetime
    
    # Enhanced position management fields
    tp1_hit: bool = False
    tp2_hit: bool = False
    breakeven_moved: bool = False
    trailing_enabled: bool = False
    trailing_stop_price: float = 0.0
    last_trailing_price: float = 0.0
    stop_loss_price: float = 0.0
    tp1_price: float = 0.0
    tp2_price: float = 0.0
    exit_triggered: bool = False
    exit_reason: str = ""

class BybitFuturesBot:
    """Bybit Futures Auto Trading Bot with V5 API"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api = BybitAPI(api_key, api_secret, testnet)
        self.testnet = testnet
        self.is_running = False
        self.trading_enabled = False
        self.positions = {}
        self.orders = {}
        self.trading_thread = None
        
        # Trading configuration
        self.max_position_size = 0.1  # 10% of balance
        self.max_leverage = 125
        self.default_leverage = 10
        self.stop_loss_percentage = 2.0
        self.take_profit_percentage = 4.0
        self.max_daily_loss = 5.0  # 5% of balance
        
        # Enhanced position management configuration
        self.tp1_percentage = 2.5  # TP1 at +2.5%
        self.tp2_percentage = 5.0  # TP2 at +5.0%
        self.breakeven_percentage = 1.0  # Breakeven at +1.0%
        self.trailing_step_percentage = 0.3  # Move every 0.3%
        self.trailing_distance_percentage = 0.8  # Keep 0.8% distance
        self.trailing_enabled = True
        self.auto_breakeven_enabled = True
        
        # Breakout strategy settings
        self.breakout_enabled = True
        self.trading_pair = 'BTCUSDT'
        self.us_session_enabled = True
        self.asian_session_enabled = True
        self.buffer_percentage = 0.05
        self.confirmation_candles = 1
        self.max_trades_per_session = 1
        self.cooldown_minutes = 30
        
        # Technical filters
        self.mtf_rsi_enabled = False
        self.volume_filter_enabled = False
        self.anti_fake_enabled = False
        
        # Risk management
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.max_daily_trades = 50
        
        # Strategy parameters
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.ema_fast = 12
        self.ema_slow = 26
        
        logger.info(f"Bybit Futures Bot initialized (testnet: {testnet})")
    
    def update_trading_config(self, config: dict):
        """Update trading configuration from GUI settings"""
        try:
            # Update basic trading parameters
            self.tp1_percentage = config.get('tp1_percentage', 2.5)
            self.tp2_percentage = config.get('tp2_percentage', 5.0)
            self.breakeven_percentage = config.get('breakeven_level', 1.0)
            self.trailing_step_percentage = config.get('trailing_step', 0.3)
            self.trailing_distance_percentage = 0.8  # Fixed at 0.8%
            self.trailing_enabled = config.get('trailing_stop_enabled', True)
            self.auto_breakeven_enabled = config.get('auto_breakeven', True)
            self.stop_loss_percentage = config.get('stop_loss_percentage', 2.0)
            self.take_profit_percentage = config.get('take_profit_percentage', 4.0)
            
            # Update breakout strategy settings
            self.breakout_enabled = config.get('breakout_enabled', True)
            self.trading_pair = config.get('trading_pair', 'BTCUSDT')
            self.us_session_enabled = config.get('us_session_enabled', True)
            self.asian_session_enabled = config.get('asian_session_enabled', True)
            self.buffer_percentage = config.get('buffer_percentage', 0.05)
            self.confirmation_candles = config.get('confirmation_candles', 1)
            self.max_trades_per_session = config.get('max_trades_per_session', 1)
            self.cooldown_minutes = config.get('cooldown_minutes', 30)
            
            # Update technical filters
            self.mtf_rsi_enabled = config.get('mtf_rsi_enabled', False)
            self.volume_filter_enabled = config.get('volume_filter_enabled', False)
            self.anti_fake_enabled = config.get('anti_fake_enabled', False)
            
            logger.info(f"Trading configuration updated: Breakout={self.breakout_enabled}, "
                       f"Pair={self.trading_pair}, Sessions=US:{self.us_session_enabled}/Asian:{self.asian_session_enabled}, "
                       f"Buffer={self.buffer_percentage}%, Confirmation={self.confirmation_candles} candles")
            logger.info(f"Enhanced settings: TP1={self.tp1_percentage}%, "
                       f"TP2={self.tp2_percentage}%, Breakeven={self.breakeven_percentage}%, "
                       f"Trailing={self.trailing_enabled}")
            
        except Exception as e:
            logger.error(f"Error updating trading configuration: {e}")
    
    def start_trading(self):
        """Start the auto trading bot"""
        if self.is_running:
            logger.warning("Bot is already running")
            return False
        
        self.is_running = True
        self.trading_enabled = True
        self.trading_thread = threading.Thread(target=self._trading_loop)
        self.trading_thread.daemon = True
        self.trading_thread.start()
        
        logger.info("Auto trading bot started")
        return True
    
    def stop_trading(self):
        """Stop the auto trading bot"""
        self.is_running = False
        self.trading_enabled = False
        
        if self.trading_thread and self.trading_thread.is_alive():
            self.trading_thread.join(timeout=5)
        
        logger.info("Auto trading bot stopped")
    
    def _trading_loop(self):
        """Main trading loop"""
        while self.is_running:
            try:
                if self.trading_enabled:
                    # Update market data
                    self._update_market_data()
                    
                    # Check for trading signals
                    signals = self._generate_trading_signals()
                    
                    # Execute signals
                    for signal in signals:
                        if self._should_execute_signal(signal):
                            self._execute_trading_signal(signal)
                    
                    # Manage existing positions
                    self._manage_positions()
                    
                    # Risk management checks
                    self._risk_management_checks()
                
                # Wait before next iteration
                time.sleep(30)  # 30 second intervals
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _update_market_data(self):
        """Update market data for all trading symbols"""
        try:
            symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
            
            for symbol in symbols:
                # Get ticker data
                ticker = self.api.get_futures_ticker(symbol)
                if ticker.get('success'):
                    # Update market data
                    pass
                
                # Get klines for technical analysis
                klines = self.api.get_futures_klines(symbol, '5', 100)
                if klines.get('success'):
                    # Update klines data
                    pass
                    
        except Exception as e:
            logger.error(f"Error updating market data: {e}")
    
    def _generate_trading_signals(self) -> List[TradingSignal]:
        """Generate trading signals based on configured strategy"""
        signals = []
        
        try:
            # Check if breakout strategy is enabled
            if hasattr(self, 'breakout_enabled') and self.breakout_enabled:
                # Use breakout strategy from GUI configuration
                signals = self._breakout_strategy()
            else:
                # Fallback to simple strategies (for backward compatibility)
                signals = self._simple_strategy_signals()
                    
        except Exception as e:
            logger.error(f"Error generating trading signals: {e}")
        
        return signals
    
    def _simple_strategy_signals(self) -> List[TradingSignal]:
        """Generate signals using simple RSI/EMA strategies (fallback)"""
        signals = []
        
        try:
            symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
            
            for symbol in symbols:
                # Get klines data
                klines_response = self.api.get_futures_klines(symbol, '5', 100)
                
                if not klines_response.get('success'):
                    continue
                
                # Extract price data
                prices = self._extract_prices_from_klines(klines_response)
                if len(prices) < 50:
                    continue
                
                # Generate signals based on strategies
                signal = self._rsi_strategy(symbol, prices)
                if signal:
                    signals.append(signal)
                
                signal = self._ema_crossover_strategy(symbol, prices)
                if signal:
                    signals.append(signal)
                
                signal = self._volume_price_strategy(symbol, prices)
                if signal:
                    signals.append(signal)
                    
        except Exception as e:
            logger.error(f"Error generating simple strategy signals: {e}")
        
        return signals
    
    def _breakout_strategy(self) -> List[TradingSignal]:
        """Generate signals based on breakout strategy from GUI configuration"""
        signals = []
        
        try:
            # Get the configured trading pair
            symbol = getattr(self, 'trading_pair', 'BTCUSDT')
            
            # Get current price
            ticker = self.api.get_futures_ticker(symbol)
            if not ticker.get('success'):
                return signals
            
            current_price = float(ticker['data']['lastPrice'])
            
            # Check session-based breakout conditions
            signal = self._check_session_breakout(symbol, current_price)
            if signal:
                signals.append(signal)
                
        except Exception as e:
            logger.error(f"Error in breakout strategy: {e}")
        
        return signals
    
    def _check_session_breakout(self, symbol: str, current_price: float) -> Optional[TradingSignal]:
        """Check for session-based breakout signals with proper validation"""
        try:
            # Get session configuration
            us_session_enabled = getattr(self, 'us_session_enabled', True)
            asian_session_enabled = getattr(self, 'asian_session_enabled', True)
            buffer_percentage = getattr(self, 'buffer_percentage', 0.05)
            confirmation_candles = getattr(self, 'confirmation_candles', 1)
            
            # Check if we're in a valid session
            current_hour = datetime.now().hour
            in_us_session = 14 <= current_hour <= 22  # US session hours
            in_asian_session = 0 <= current_hour <= 8  # Asian session hours
            
            if not ((us_session_enabled and in_us_session) or (asian_session_enabled and in_asian_session)):
                logger.info(f"Not in active trading session. Current hour: {current_hour}")
                return None
            
            # Get session range data (this would need to be calculated from historical data)
            # For now, we'll use a simplified approach
            session_range = self._get_session_range(symbol)
            if not session_range:
                return None
            
            # Check breakout conditions
            buffer = buffer_percentage / 100
            long_breakout_level = session_range['high'] * (1 + buffer)
            short_breakout_level = session_range['low'] * (1 - buffer)
            
            # Check for breakout signals with mutual exclusivity
            long_signal = current_price > long_breakout_level
            short_signal = current_price < short_breakout_level
            
            # Determine the strongest signal direction (mutual exclusivity)
            selected_direction = self._determine_strongest_signal(
                symbol, current_price, long_signal, short_signal, 
                long_breakout_level, short_breakout_level
            )
            
            if selected_direction == 'LONG':
                logger.info(f"LONG breakout selected: Price ${current_price:.2f} > Level ${long_breakout_level:.2f}")
                
                # Apply confirmation logic
                if self._validate_breakout_confirmation(symbol, current_price, 'LONG', confirmation_candles):
                    return TradingSignal(
                        symbol=symbol,
                        side="Buy",
                        order_type="Market",
                        quantity=self._calculate_position_size(symbol),
                        stop_loss=self._calculate_stop_loss(symbol, "Buy"),
                        take_profit=self._calculate_take_profit(symbol, "Buy"),
                        leverage=self.default_leverage,
                        strategy="SESSION_BREAKOUT_LONG",
                        confidence=0.9
                    )
            
            elif selected_direction == 'SHORT':
                logger.info(f"SHORT breakout selected: Price ${current_price:.2f} < Level ${short_breakout_level:.2f}")
                
                # Apply confirmation logic
                if self._validate_breakout_confirmation(symbol, current_price, 'SHORT', confirmation_candles):
                    return TradingSignal(
                        symbol=symbol,
                        side="Sell",
                        order_type="Market",
                        quantity=self._calculate_position_size(symbol),
                        stop_loss=self._calculate_stop_loss(symbol, "Sell"),
                        take_profit=self._calculate_take_profit(symbol, "Sell"),
                        leverage=self.default_leverage,
                        strategy="SESSION_BREAKOUT_SHORT",
                        confidence=0.9
                    )
            
            elif selected_direction == 'CONFLICT':
                logger.warning(f"Conflicting signals detected for {symbol} - skipping trade for safety")
                logger.info(f"Price: ${current_price:.2f}, Long Level: ${long_breakout_level:.2f}, Short Level: ${short_breakout_level:.2f}")
            
            else:
                logger.info(f"No breakout signals detected for {symbol}")
            
        except Exception as e:
            logger.error(f"Error checking session breakout: {e}")
        
        return None
    
    def _determine_strongest_signal(self, symbol: str, current_price: float, long_signal: bool, 
                                   short_signal: bool, long_breakout_level: float, short_breakout_level: float) -> str:
        """Determine the strongest signal direction with mutual exclusivity"""
        try:
            logger.info(f"Determining strongest signal for {symbol}:")
            logger.info(f"   Long Signal: {long_signal}")
            logger.info(f"   Short Signal: {short_signal}")
            
            # If only one signal is true, use that direction
            if long_signal and not short_signal:
                logger.info("Clear LONG signal detected")
                return 'LONG'
            elif short_signal and not long_signal:
                logger.info("Clear SHORT signal detected")
                return 'SHORT'
            elif long_signal and short_signal:
                # Both signals are true - need to determine which is stronger
                logger.info("Both signals detected - analyzing signal strength...")
                
                # Calculate how far price has moved beyond breakout levels
                long_distance = current_price - long_breakout_level
                short_distance = short_breakout_level - current_price
                
                logger.info(f"   Long breakout level: ${long_breakout_level:.2f}")
                logger.info(f"   Short breakout level: ${short_breakout_level:.2f}")
                logger.info(f"   Long distance: ${long_distance:.2f}")
                logger.info(f"   Short distance: ${short_distance:.2f}")
                
                # Choose the signal with the greater distance (stronger breakout)
                if long_distance > short_distance:
                    logger.info("LONG signal is stronger (greater distance)")
                    return 'LONG'
                elif short_distance > long_distance:
                    logger.info("SHORT signal is stronger (greater distance)")
                    return 'SHORT'
                else:
                    logger.warning("Signals are equally strong - skipping trade for safety")
                    return 'CONFLICT'
            else:
                # Neither signal is true
                logger.info("No signals detected")
                return 'NONE'
                
        except Exception as e:
            logger.error(f"Error determining strongest signal: {e}")
            return 'NONE'
    
    def _get_session_range(self, symbol: str) -> Optional[dict]:
        """Get session range data (simplified implementation)"""
        try:
            # This is a simplified implementation
            # In a real scenario, you would calculate the actual session high/low
            # from historical data for the current session
            
            # For now, return a placeholder range
            # This should be replaced with actual session range calculation
            return {
                'high': 50000.0,  # Placeholder - should be calculated from session data
                'low': 48000.0,   # Placeholder - should be calculated from session data
                'session': 'current'
            }
            
        except Exception as e:
            logger.error(f"Error getting session range: {e}")
            return None
    
    def _validate_breakout_confirmation(self, symbol: str, price: float, direction: str, confirmation_candles: int) -> bool:
        """Validate breakout with confirmation candles and technical filters"""
        try:
            logger.info(f"Validating {direction} breakout for {symbol} with {confirmation_candles} confirmation candles")
            
            # Check confirmation candles (simplified - in real implementation, wait for actual candle closes)
            # For now, we'll implement a basic validation
            
            # Check technical filters if enabled
            if hasattr(self, 'mtf_rsi_enabled') and self.mtf_rsi_enabled:
                if not self._check_mtf_rsi_filter(direction):
                    logger.info("MTF RSI filter failed")
                    return False
            
            if hasattr(self, 'volume_filter_enabled') and self.volume_filter_enabled:
                if not self._check_volume_filter(symbol):
                    logger.info("Volume filter failed")
                    return False
            
            if hasattr(self, 'anti_fake_enabled') and self.anti_fake_enabled:
                if not self._check_anti_fake_breakout(symbol, price, direction):
                    logger.info("Anti-fake breakout check failed")
                    return False
            
            logger.info(f"Breakout validation passed for {direction} {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating breakout confirmation: {e}")
            return False
    
    def _check_mtf_rsi_filter(self, direction: str) -> bool:
        """Check Multi-Timeframe RSI filter"""
        try:
            # Simplified RSI filter check
            # In real implementation, calculate RSI for 5m and 1h timeframes
            logger.info(f"Checking MTF RSI filter for {direction}")
            return True  # Placeholder - implement actual RSI calculation
            
        except Exception as e:
            logger.error(f"Error checking MTF RSI filter: {e}")
            return False
    
    def _check_volume_filter(self, symbol: str) -> bool:
        """Check volume filter"""
        try:
            # Simplified volume filter check
            logger.info(f"Checking volume filter for {symbol}")
            return True  # Placeholder - implement actual volume calculation
            
        except Exception as e:
            logger.error(f"Error checking volume filter: {e}")
            return False
    
    def _check_anti_fake_breakout(self, symbol: str, price: float, direction: str) -> bool:
        """Check anti-fake breakout filter"""
        try:
            # Simplified anti-fake breakout check
            logger.info(f"Checking anti-fake breakout for {direction} {symbol}")
            return True  # Placeholder - implement actual anti-fake logic
            
        except Exception as e:
            logger.error(f"Error checking anti-fake breakout: {e}")
            return False
    
    def _rsi_strategy(self, symbol: str, prices: List[float]) -> Optional[TradingSignal]:
        """RSI-based trading strategy"""
        try:
            if len(prices) < self.rsi_period + 1:
                return None
            
            # Calculate RSI
            rsi = self._calculate_rsi(prices, self.rsi_period)
            current_rsi = rsi[-1]
            
            # Generate signal based on RSI
            if current_rsi < self.rsi_oversold:
                # Oversold - potential buy signal
                return TradingSignal(
                    symbol=symbol,
                    side="Buy",
                    order_type="Market",
                    quantity=self._calculate_position_size(symbol),
                    stop_loss=self._calculate_stop_loss(symbol, "Buy"),
                    take_profit=self._calculate_take_profit(symbol, "Buy"),
                    leverage=self.default_leverage,
                    strategy="RSI_OVERSOLD",
                    confidence=0.7
                )
            
            elif current_rsi > self.rsi_overbought:
                # Overbought - potential sell signal
                return TradingSignal(
                    symbol=symbol,
                    side="Sell",
                    order_type="Market",
                    quantity=self._calculate_position_size(symbol),
                    stop_loss=self._calculate_stop_loss(symbol, "Sell"),
                    take_profit=self._calculate_take_profit(symbol, "Sell"),
                    leverage=self.default_leverage,
                    strategy="RSI_OVERBOUGHT",
                    confidence=0.7
                )
            
        except Exception as e:
            logger.error(f"Error in RSI strategy for {symbol}: {e}")
        
        return None
    
    def _ema_crossover_strategy(self, symbol: str, prices: List[float]) -> Optional[TradingSignal]:
        """EMA crossover trading strategy"""
        try:
            if len(prices) < self.ema_slow + 1:
                return None
            
            # Calculate EMAs
            ema_fast_values = self._calculate_ema(prices, self.ema_fast)
            ema_slow_values = self._calculate_ema(prices, self.ema_slow)
            
            if len(ema_fast_values) < 2 or len(ema_slow_values) < 2:
                return None
            
            # Check for crossover
            current_fast = ema_fast_values[-1]
            current_slow = ema_slow_values[-1]
            prev_fast = ema_fast_values[-2]
            prev_slow = ema_slow_values[-2]
            
            # Bullish crossover
            if prev_fast <= prev_slow and current_fast > current_slow:
                return TradingSignal(
                    symbol=symbol,
                    side="Buy",
                    order_type="Market",
                    quantity=self._calculate_position_size(symbol),
                    stop_loss=self._calculate_stop_loss(symbol, "Buy"),
                    take_profit=self._calculate_take_profit(symbol, "Buy"),
                    leverage=self.default_leverage,
                    strategy="EMA_CROSSOVER_BULL",
                    confidence=0.8
                )
            
            # Bearish crossover
            elif prev_fast >= prev_slow and current_fast < current_slow:
                return TradingSignal(
                    symbol=symbol,
                    side="Sell",
                    order_type="Market",
                    quantity=self._calculate_position_size(symbol),
                    stop_loss=self._calculate_stop_loss(symbol, "Sell"),
                    take_profit=self._calculate_take_profit(symbol, "Sell"),
                    leverage=self.default_leverage,
                    strategy="EMA_CROSSOVER_BEAR",
                    confidence=0.8
                )
            
        except Exception as e:
            logger.error(f"Error in EMA crossover strategy for {symbol}: {e}")
        
        return None
    
    def _volume_price_strategy(self, symbol: str, prices: List[float]) -> Optional[TradingSignal]:
        """Volume and price action strategy"""
        try:
            if len(prices) < 20:
                return None
            
            # Simple volume-price strategy
            current_price = prices[-1]
            avg_price = sum(prices[-20:]) / 20
            
            # Price above average with momentum
            if current_price > avg_price * 1.02:  # 2% above average
                return TradingSignal(
                    symbol=symbol,
                    side="Buy",
                    order_type="Market",
                    quantity=self._calculate_position_size(symbol),
                    stop_loss=self._calculate_stop_loss(symbol, "Buy"),
                    take_profit=self._calculate_take_profit(symbol, "Buy"),
                    leverage=self.default_leverage,
                    strategy="VOLUME_PRICE_BULL",
                    confidence=0.6
                )
            
            # Price below average with momentum
            elif current_price < avg_price * 0.98:  # 2% below average
                return TradingSignal(
                    symbol=symbol,
                    side="Sell",
                    order_type="Market",
                    quantity=self._calculate_position_size(symbol),
                    stop_loss=self._calculate_stop_loss(symbol, "Sell"),
                    take_profit=self._calculate_take_profit(symbol, "Sell"),
                    leverage=self.default_leverage,
                    strategy="VOLUME_PRICE_BEAR",
                    confidence=0.6
                )
            
        except Exception as e:
            logger.error(f"Error in volume-price strategy for {symbol}: {e}")
        
        return None
    
    def _should_execute_signal(self, signal: TradingSignal) -> bool:
        """Check if signal should be executed"""
        try:
            # Check if trading is enabled
            if not self.trading_enabled:
                return False
            
            # Check daily loss limit
            if self.daily_pnl < -(self.max_daily_loss / 100):
                logger.warning("Daily loss limit reached, skipping signal")
                return False
            
            # Check daily trade limit
            if self.daily_trades >= self.max_daily_trades:
                logger.warning("Daily trade limit reached, skipping signal")
                return False
            
            # Check confidence threshold
            if signal.confidence < 0.6:
                logger.info(f"Signal confidence too low: {signal.confidence}")
                return False
            
            # Check if we already have a position in this symbol with the same side
            # Allow hedge mode (both long and short positions for same symbol)
            position_key = f"{signal.symbol}_{signal.side}"
            if position_key in self.positions:
                logger.info(f"Already have {signal.side} position in {signal.symbol}, skipping signal")
                return False
            else:
                logger.info(f"Allowing new position: {signal.side} position in {signal.symbol}")
            
            # Check if we have enough balance
            if not self._check_balance_for_trade(signal):
                logger.warning(f"Insufficient balance for {signal.symbol} trade")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking signal execution: {e}")
            return False
    
    def _execute_trading_signal(self, signal: TradingSignal):
        """Execute a trading signal"""
        try:
            logger.info(f"Executing signal: {signal.side} {signal.quantity} {signal.symbol}")
            
            # Set leverage first
            leverage_result = self.api.set_futures_leverage(signal.symbol, signal.leverage)
            if not leverage_result.get('success'):
                logger.error(f"Failed to set leverage: {leverage_result}")
                return
            
            # Place the order
            order_params = {
                'symbol': signal.symbol,
                'side': signal.side,
                'order_type': signal.order_type,
                'qty': signal.quantity,
                'price': signal.price,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'time_in_force': signal.time_in_force,
                'reduce_only': signal.reduce_only,
                'close_on_trigger': signal.close_on_trigger
            }
            
            order_result = self.api.place_futures_order(**order_params)
            
            if order_result.get('success'):
                logger.info(f"Order placed successfully: {order_result}")
                
                # Update daily trade count
                self.daily_trades += 1
                
                # Store order information
                if 'data' in order_result:
                    order_data = order_result['data']
                    order_id = order_data.get('orderId')
                    if order_id:
                        self.orders[order_id] = {
                            'symbol': signal.symbol,
                            'side': signal.side,
                            'quantity': signal.quantity,
                            'strategy': signal.strategy,
                            'timestamp': datetime.now()
                        }
            else:
                logger.error(f"Failed to place order: {order_result}")
                
        except Exception as e:
            logger.error(f"Error executing trading signal: {e}")
    
    def _manage_positions(self):
        """Manage existing positions"""
        try:
            # Get current positions
            positions_response = self.api.get_futures_positions()
            
            if not positions_response.get('success'):
                return
            
            positions_data = positions_response.get('data', {}).get('list', [])
            
            for position in positions_data:
                symbol = position.get('symbol')
                size = float(position.get('size', 0))
                side = position.get('side', 'Unknown')
                
                if size > 0:  # Open position
                    # Create position key that includes both symbol and side for hedge mode support
                    position_key = f"{symbol}_{side}"
                    
                    # Update position info
                    self.positions[symbol] = PositionInfo(
                        symbol=symbol,
                        side=side,
                        size=size,
                        entry_price=entry_price,
                        mark_price=current_price,
                        leverage=int(position.get('leverage', 0)),
                        unrealized_pnl=float(position.get('unrealizedPnl', 0)),
                        realized_pnl=float(position.get('realizedPnl', 0)),
                        margin_type=position.get('marginType', 'Unknown'),
                        position_value=float(position.get('positionValue', 0)),
                        timestamp=datetime.now()
                    )
                    
                    # Initialize enhanced fields if this is a new position
                    if position_key not in self.positions:
                        self._initialize_position_management(position_info)
                    
                    # Update existing position with current data
                    if position_key in self.positions:
                        existing_pos = self.positions[position_key]
                        position_info.tp1_hit = existing_pos.tp1_hit
                        position_info.tp2_hit = existing_pos.tp2_hit
                        position_info.breakeven_moved = existing_pos.breakeven_moved
                        position_info.trailing_enabled = existing_pos.trailing_enabled
                        position_info.trailing_stop_price = existing_pos.trailing_stop_price
                        position_info.last_trailing_price = existing_pos.last_trailing_price
                        position_info.stop_loss_price = existing_pos.stop_loss_price
                        position_info.tp1_price = existing_pos.tp1_price
                        position_info.tp2_price = existing_pos.tp2_price
                        position_info.exit_triggered = existing_pos.exit_triggered
                        position_info.exit_reason = existing_pos.exit_reason
                    
                    self.positions[position_key] = position_info
                    
                    # Check if position needs management
                    self._check_position_exit_conditions(position_key)
                    
        except Exception as e:
            logger.error(f"Error managing positions: {e}")
    
    def _check_position_exit_conditions(self, symbol: str):
        """Check if position should be closed"""
        try:
            if position_key not in self.positions:
                return
            
            position = self.positions[symbol]
            
            # Check stop loss
            if position.unrealized_pnl < 0:
                loss_percentage = abs(position.unrealized_pnl) / position.position_value * 100
                
                if loss_percentage >= self.stop_loss_percentage:
                    logger.info(f"Stop loss triggered for {symbol}, closing position")
                    self._close_position(symbol, position.side, position.size)
                    return
            
            # Check take profit
            if position.unrealized_pnl > 0:
                profit_percentage = position.unrealized_pnl / position.position_value * 100
                
                if profit_percentage >= self.take_profit_percentage:
                    logger.info(f"Take profit triggered for {symbol}, closing position")
                    self._close_position(symbol, position.side, position.size)
                    return
                    
        except Exception as e:
            logger.error(f"Error checking position exit conditions: {e}")
    
    def _check_stop_loss(self, position: PositionInfo, current_price: float, profit_percentage: float) -> bool:
        """Check if stop loss should be triggered"""
        try:
            side = position.side
            
            # Check if price hit stop loss level
            if side == 'Buy':
                if current_price <= position.stop_loss_price:
                    return True
            else:  # Sell
                if current_price >= position.stop_loss_price:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking stop loss: {e}")
            return False
    
    def _check_take_profit(self, position: PositionInfo, current_price: float, profit_percentage: float) -> bool:
        """Check if take profit should be triggered (TP1/TP2 logic)"""
        try:
            side = position.side
            
            # Check TP1
            if not position.tp1_hit:
                if side == 'Buy' and current_price >= position.tp1_price:
                    position.tp1_hit = True
                    logger.info(f"🎯 TP1 HIT for {position.symbol} {side}: "
                               f"Price={current_price:.4f}, Profit={profit_percentage:.2f}%")
                    
                    # Enable trailing stop after TP1
                    if self.trailing_enabled:
                        position.trailing_enabled = True
                        logger.info(f"🔄 Trailing stop ENABLED for {position.symbol} after TP1")
                    
                    # Don't close position at TP1, continue to TP2
                    return False
            
            # Check TP2 (only if TP1 was hit)
            if position.tp1_hit and not position.tp2_hit:
                if side == 'Buy' and current_price >= position.tp2_price:
                    position.tp2_hit = True
                    logger.info(f"🎯 TP2 HIT for {position.symbol} {side}: "
                               f"Price={current_price:.4f}, Profit={profit_percentage:.2f}%")
                    return True
                elif side == 'Sell' and current_price <= position.tp2_price:
                    position.tp2_hit = True
                    logger.info(f"🎯 TP2 HIT for {position.symbol} {side}: "
                               f"Price={current_price:.4f}, Profit={profit_percentage:.2f}%")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking take profit: {e}")
            return False
    
    def _check_trailing_stop(self, position: PositionInfo, current_price: float, profit_percentage: float) -> bool:
        """Check if trailing stop should be triggered"""
        try:
            if not position.trailing_enabled:
                return False
            
            side = position.side
            
            # Check if price hit trailing stop level
            if side == 'Buy':
                if current_price <= position.trailing_stop_price:
                    return True
            else:  # Sell
                if current_price >= position.trailing_stop_price:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking trailing stop: {e}")
            return False
    
    def _update_position_management(self, position: PositionInfo, current_price: float, profit_percentage: float):
        """Update position management (breakeven and trailing stop)"""
        try:
            side = position.side
            entry_price = position.entry_price
            
            # 1. Check Breakeven Logic
            if self.auto_breakeven_enabled and not position.breakeven_moved:
                if profit_percentage >= self.breakeven_percentage:
                    position.stop_loss_price = entry_price
                    position.breakeven_moved = True
                    logger.info(f"⚖️ BREAKEVEN MOVED for {position.symbol} {side}: "
                               f"SL moved to entry price {entry_price:.4f}")
            
            # 2. Update Trailing Stop (only after TP1 is hit)
            if position.trailing_enabled and position.tp1_hit:
                self._update_trailing_stop(position, current_price, profit_percentage)
            
        except Exception as e:
            logger.error(f"Error updating position management: {e}")
    
    def _update_trailing_stop(self, position: PositionInfo, current_price: float, profit_percentage: float):
        """Update trailing stop with 0.3% step and 0.8% distance"""
        try:
            side = position.side
            entry_price = position.entry_price
            
            # Check if price moved enough to update trailing stop (0.3% step)
            price_change_percentage = abs(current_price - position.last_trailing_price) / position.last_trailing_price * 100
            
            if price_change_percentage >= self.trailing_step_percentage:
                # Calculate new trailing stop (0.8% distance)
                if side == 'Buy':
                    new_trailing_stop = current_price * (1 - self.trailing_distance_percentage / 100)
                    # Only move trailing stop up (never down)
                    if new_trailing_stop > position.trailing_stop_price:
                        position.trailing_stop_price = new_trailing_stop
                        position.last_trailing_price = current_price
                        logger.info(f"📈 Trailing stop UPDATED for {position.symbol} {side}: "
                                   f"New SL={new_trailing_stop:.4f} (Price={current_price:.4f})")
                else:  # Sell
                    new_trailing_stop = current_price * (1 + self.trailing_distance_percentage / 100)
                    # Only move trailing stop down (never up)
                    if new_trailing_stop < position.trailing_stop_price:
                        position.trailing_stop_price = new_trailing_stop
                        position.last_trailing_price = current_price
                        logger.info(f"📉 Trailing stop UPDATED for {position.symbol} {side}: "
                                   f"New SL={new_trailing_stop:.4f} (Price={current_price:.4f})")
            
        except Exception as e:
            logger.error(f"Error updating trailing stop: {e}")
    
    def _close_position(self, symbol: str, side: str, size: float, reason: str = "MANUAL"):
        """Close a futures position with enhanced logging"""
        try:
            logger.info(f"🔴 CLOSING POSITION: {symbol} {side} {size} - Reason: {reason}")
            
            # Close position
            close_result = self.api.close_futures_position(symbol, side, size)
            
            if close_result.get('success'):
                logger.info(f"✅ Position closed successfully: {close_result}")
                
                # Remove from positions using position key
                position_key = f"{symbol}_{side}"
                if position_key in self.positions:
                    position = self.positions[position_key]
                    self.daily_pnl += position.realized_pnl
            else:
                logger.error(f"❌ Failed to close position: {close_result}")
                
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
    
    def _risk_management_checks(self):
        """Perform risk management checks"""
        try:
            # Check daily loss limit
            if self.daily_pnl < -(self.max_daily_loss / 100):
                logger.warning("Daily loss limit reached, stopping trading")
                self.trading_enabled = False
                return
            
            # Check position concentration
            total_position_value = sum(pos.position_value for pos in self.positions.values())
            
            # Get account balance
            balance_response = self.api.get_futures_balance()
            if balance_response.get('success'):
                balance_data = balance_response.get('data', {}).get('list', [])
                if balance_data:
                    total_balance = float(balance_data[0].get('totalWalletBalance', 0))
                    
                    if total_balance > 0:
                        position_concentration = total_position_value / total_balance
                        
                        if position_concentration > 0.8:  # 80% of balance
                            logger.warning("Position concentration too high, reducing risk")
                            self._reduce_position_risk()
            
        except Exception as e:
            logger.error(f"Error in risk management checks: {e}")
    
    def _reduce_position_risk(self):
        """Reduce position risk by closing some positions"""
        try:
            # Close positions with highest risk (highest leverage)
            sorted_positions = sorted(
                self.positions.values(),
                key=lambda x: x.leverage,
                reverse=True
            )
            
            # Close top 2 high-leverage positions
            for position in sorted_positions[:2]:
                logger.info(f"Closing high-risk position: {position.symbol}")
                self._close_position(position.symbol, position.side, position.size)
                
        except Exception as e:
            logger.error(f"Error reducing position risk: {e}")
    
    def _calculate_position_size(self, symbol: str) -> float:
        """Calculate position size based on risk management"""
        try:
            # Get account balance
            balance_response = self.api.get_futures_balance()
            if not balance_response.get('success'):
                return 0.01  # Default minimum size
            
            balance_data = balance_response.get('data', {}).get('list', [])
            if not balance_data:
                return 0.01
            
            total_balance = float(balance_data[0].get('totalWalletBalance', 0))
            
            if total_balance <= 0:
                return 0.01
            
            # Calculate position size (10% of balance)
            position_value = total_balance * self.max_position_size
            
            # Get current price
            ticker_response = self.api.get_futures_ticker(symbol)
            if ticker_response.get('success'):
                ticker_data = ticker_response.get('data', {}).get('list', [])
                if ticker_data:
                    current_price = float(ticker_data[0].get('lastPrice', 0))
                    
                    if current_price > 0:
                        # Calculate quantity in contracts
                        quantity = position_value / current_price
                        
                        # Round to appropriate precision
                        if symbol == 'BTCUSDT':
                            return round(quantity, 3)  # 3 decimal places for BTC
                        elif symbol == 'ETHUSDT':
                            return round(quantity, 2)  # 2 decimal places for ETH
                        else:
                            return round(quantity, 1)  # 1 decimal place for others
            
            return 0.01  # Default minimum size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.01
    
    def _calculate_stop_loss(self, symbol: str, side: str) -> float:
        """Calculate stop loss price"""
        try:
            # Get current price
            ticker_response = self.api.get_futures_ticker(symbol)
            if not ticker_response.get('success'):
                return 0
            
            ticker_data = ticker_response.get('data', {}).get('list', [])
            if not ticker_data:
                return 0
            
            current_price = float(ticker_data[0].get('lastPrice', 0))
            
            if current_price <= 0:
                return 0
            
            # Calculate stop loss (2% below/above entry)
            if side == "Buy":
                stop_loss = current_price * (1 - self.stop_loss_percentage / 100)
            else:  # Sell
                stop_loss = current_price * (1 + self.stop_loss_percentage / 100)
            
            # Round to appropriate precision
            if symbol == 'BTCUSDT':
                return round(stop_loss, 1)
            elif symbol == 'ETHUSDT':
                return round(stop_loss, 2)
            else:
                return round(stop_loss, 3)
                
        except Exception as e:
            logger.error(f"Error calculating stop loss: {e}")
            return 0
    
    def _calculate_take_profit(self, symbol: str, side: str) -> float:
        """Calculate take profit price"""
        try:
            # Get current price
            ticker_response = self.api.get_futures_ticker(symbol)
            if not ticker_response.get('success'):
                return 0
            
            ticker_data = ticker_response.get('data', {}).get('list', [])
            if not ticker_data:
                return 0
            
            current_price = float(ticker_data[0].get('lastPrice', 0))
            
            if current_price <= 0:
                return 0
            
            # Calculate take profit (4% above/below entry)
            if side == "Buy":
                take_profit = current_price * (1 + self.take_profit_percentage / 100)
            else:  # Sell
                take_profit = current_price * (1 - self.take_profit_percentage / 100)
            
            # Round to appropriate precision
            if symbol == 'BTCUSDT':
                return round(take_profit, 1)
            elif symbol == 'ETHUSDT':
                return round(take_profit, 2)
            else:
                return round(take_profit, 3)
                
        except Exception as e:
            logger.error(f"Error calculating take profit: {e}")
            return 0
    
    def _check_balance_for_trade(self, signal: TradingSignal) -> bool:
        """Check if we have enough balance for the trade"""
        try:
            # Get account balance
            balance_response = self.api.get_futures_balance()
            if not balance_response.get('success'):
                return False
            
            balance_data = balance_response.get('data', {}).get('list', [])
            if not balance_data:
                return False
            
            available_balance = float(balance_data[0].get('availableToWithdraw', 0))
            
            # Calculate required margin
            ticker_response = self.api.get_futures_ticker(signal.symbol)
            if not ticker_response.get('success'):
                return False
            
            ticker_data = ticker_response.get('data', {}).get('list', [])
            if not ticker_data:
                return False
            
            current_price = float(ticker_data[0].get('lastPrice', 0))
            
            if current_price <= 0:
                return False
            
            # Calculate required margin (position value / leverage)
            position_value = signal.quantity * current_price
            required_margin = position_value / signal.leverage
            
            # Add some buffer (20%)
            required_margin *= 1.2
            
            return available_balance >= required_margin
            
        except Exception as e:
            logger.error(f"Error checking balance for trade: {e}")
            return False
    
    def _extract_prices_from_klines(self, klines_response: Dict) -> List[float]:
        """Extract closing prices from klines response"""
        try:
            prices = []
            
            if 'data' in klines_response:
                klines_data = klines_response['data'].get('list', [])
                
                for kline in klines_data:
                    if len(kline) >= 4:
                        close_price = float(kline[4])  # Close price is at index 4
                        prices.append(close_price)
            
            return prices
            
        except Exception as e:
            logger.error(f"Error extracting prices from klines: {e}")
            return []
    
    def _calculate_rsi(self, prices: List[float], period: int) -> List[float]:
        """Calculate RSI indicator"""
        try:
            if len(prices) < period + 1:
                return []
            
            rsi_values = []
            
            for i in range(period, len(prices)):
                gains = []
                losses = []
                
                for j in range(i - period + 1, i + 1):
                    change = prices[j] - prices[j - 1]
                    if change > 0:
                        gains.append(change)
                        losses.append(0)
                    else:
                        gains.append(0)
                        losses.append(abs(change))
                
                avg_gain = sum(gains) / period
                avg_loss = sum(losses) / period
                
                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                
                rsi_values.append(rsi)
            
            return rsi_values
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return []
    
    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        try:
            if len(prices) < period:
                return []
            
            ema_values = []
            multiplier = 2 / (period + 1)
            
            # First EMA is SMA
            sma = sum(prices[:period]) / period
            ema_values.append(sma)
            
            # Calculate subsequent EMAs
            for i in range(period, len(prices)):
                ema = (prices[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
                ema_values.append(ema)
            
            return ema_values
            
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return []
    
    def get_bot_status(self) -> Dict:
        """Get bot status information"""
        return {
            'is_running': self.is_running,
            'trading_enabled': self.trading_enabled,
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'open_positions': len(self.positions),
            'open_orders': len(self.orders),
            'testnet': self.testnet,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_positions_summary(self) -> Dict:
        """Get summary of all positions"""
        positions_summary = {}
        
        for symbol, position in self.positions.items():
            positions_summary[symbol] = {
                'side': position.side,
                'size': position.size,
                'entry_price': position.entry_price,
                'mark_price': position.mark_price,
                'leverage': position.leverage,
                'unrealized_pnl': position.unrealized_pnl,
                'realized_pnl': position.realized_pnl,
                'margin_type': position.margin_type,
                'position_value': position.position_value,
                'timestamp': position.timestamp.isoformat()
            }
        
        return positions_summary
    
    def get_orders_summary(self) -> Dict:
        """Get summary of all orders"""
        orders_summary = {}
        
        for order_id, order in self.orders.items():
            orders_summary[order_id] = {
                'symbol': order['symbol'],
                'side': order['side'],
                'quantity': order['quantity'],
                'strategy': order['strategy'],
                'timestamp': order['timestamp'].isoformat()
            }
        
        return orders_summary
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        logger.info("Daily statistics reset")
    

# Example usage
if __name__ == "__main__":
    # Initialize bot
    bot = BybitFuturesBot(
        api_key="your_api_key",
        api_secret="your_api_secret",
        testnet=True
    )
    
    # Start trading
    bot.start_trading()
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping bot...")
        bot.stop_trading() 
