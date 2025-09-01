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
        """Generate trading signals based on technical analysis"""
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
            logger.error(f"Error generating trading signals: {e}")
        
        return signals
    
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
            
            # Check if we already have a position in this symbol
            if signal.symbol in self.positions:
                logger.info(f"Already have position in {signal.symbol}, skipping signal")
                return False
            
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
                
                if size > 0:  # Open position
                    # Update position info
                    self.positions[symbol] = PositionInfo(
                        symbol=symbol,
                        side=position.get('side', 'Unknown'),
                        size=size,
                        entry_price=float(position.get('entryPrice', 0)),
                        mark_price=float(position.get('markPrice', 0)),
                        leverage=int(position.get('leverage', 0)),
                        unrealized_pnl=float(position.get('unrealizedPnl', 0)),
                        realized_pnl=float(position.get('realizedPnl', 0)),
                        margin_type=position.get('marginType', 'Unknown'),
                        position_value=float(position.get('positionValue', 0)),
                        timestamp=datetime.now()
                    )
                    
                    # Check if position needs management
                    self._check_position_exit_conditions(symbol)
                    
        except Exception as e:
            logger.error(f"Error managing positions: {e}")
    
    def _check_position_exit_conditions(self, symbol: str):
        """Check if position should be closed"""
        try:
            if symbol not in self.positions:
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
    
    def _close_position(self, symbol: str, side: str, size: float):
        """Close a futures position"""
        try:
            logger.info(f"Closing position: {symbol} {side} {size}")
            
            # Close position
            close_result = self.api.close_futures_position(symbol, side, size)
            
            if close_result.get('success'):
                logger.info(f"Position closed successfully: {close_result}")
                
                # Remove from positions
                if symbol in self.positions:
                    del self.positions[symbol]
                
                # Update daily PnL
                if symbol in self.positions:
                    position = self.positions[symbol]
                    self.daily_pnl += position.realized_pnl
            else:
                logger.error(f"Failed to close position: {close_result}")
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
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
    
    def update_trading_config(self, config: Dict):
        """Update trading configuration"""
        try:
            if 'max_position_size' in config:
                self.max_position_size = config['max_position_size']
            
            if 'default_leverage' in config:
                self.default_leverage = config['default_leverage']
            
            if 'stop_loss_percentage' in config:
                self.stop_loss_percentage = config['stop_loss_percentage']
            
            if 'take_profit_percentage' in config:
                self.take_profit_percentage = config['take_profit_percentage']
            
            if 'max_daily_loss' in config:
                self.max_daily_loss = config['max_daily_loss']
            
            if 'rsi_period' in config:
                self.rsi_period = config['rsi_period']
            
            if 'ema_fast' in config:
                self.ema_fast = config['ema_fast']
            
            if 'ema_slow' in config:
                self.ema_slow = config['ema_slow']
            
            logger.info("Trading configuration updated")
            
        except Exception as e:
            logger.error(f"Error updating trading configuration: {e}")

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