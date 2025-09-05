#!/usr/bin/env python3
"""
Bybit Paper Trading Bot - Works Without Private API Access
"""

import time
import logging
from datetime import datetime
from bybit_api import BybitAPI as BybitAPIV5

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PaperTradingBot:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api = BybitAPIV5(api_key, api_secret, testnet=True)
        
        # Paper trading state
        self.is_running = False
        self.paper_balance = 10000.0  # Start with $10,000 paper money
        self.positions = {}
        self.orders = []
        self.trade_history = []
        
        # Trading configuration
        self.max_position_size = 0.02  # 2% of balance
        self.default_leverage = 3
        self.stop_loss_percentage = 1.0
        self.take_profit_percentage = 2.0
        self.max_daily_loss = 2.0
        
        # Technical analysis parameters
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.ema_fast = 12
        self.ema_slow = 26
        
        logger.info("Paper Trading Bot initialized")
    
    def start_trading(self):
        """Start paper trading"""
        self.is_running = True
        logger.info("Paper trading bot started")
        
        while self.is_running:
            try:
                # Collect market data
                self._update_market_data()
                
                # Generate trading signals
                signals = self._generate_trading_signals()
                
                # Execute paper trades
                for signal in signals:
                    self._execute_paper_trade(signal)
                
                # Manage existing positions
                self._manage_paper_positions()
                
                # Wait before next iteration
                time.sleep(30)  # 30 second intervals
                
            except KeyboardInterrupt:
                logger.info("Paper trading stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in paper trading loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def stop_trading(self):
        """Stop paper trading"""
        self.is_running = False
        logger.info("Paper trading bot stopped")
    
    def _update_market_data(self):
        """Update market data from public endpoints"""
        try:
            # Get market summary (public endpoint - should work)
            market_data = self.api.get_futures_market_summary()
            if market_data.get('success'):
                logger.info("Market data updated successfully")
                # Store market data for analysis
                self.current_market_data = market_data['data']
            else:
                logger.warning("Failed to update market data")
                
        except Exception as e:
            logger.error(f"Error updating market data: {e}")
    
    def _generate_trading_signals(self):
        """Generate trading signals based on technical analysis"""
        signals = []
        
        try:
            # Get klines for BTCUSDT (public endpoint)
            klines_response = self.api.get_futures_klines('BTCUSDT', '5', 100)
            
            if klines_response.get('success'):
                prices = self._extract_prices_from_klines(klines_response)
                
                if len(prices) >= 50:
                    # Calculate RSI
                    rsi_values = self._calculate_rsi(prices, self.rsi_period)
                    if rsi_values:
                        current_rsi = rsi_values[-1]
                        
                        # RSI Strategy
                        if current_rsi < self.rsi_oversold:
                            signals.append({
                                'symbol': 'BTCUSDT',
                                'side': 'Buy',
                                'strategy': 'RSI_Oversold',
                                'strength': (self.rsi_oversold - current_rsi) / self.rsi_oversold,
                                'price': prices[-1]
                            })
                        elif current_rsi > self.rsi_overbought:
                            signals.append({
                                'symbol': 'BTCUSDT',
                                'side': 'Sell',
                                'strategy': 'RSI_Overbought',
                                'strength': (current_rsi - self.rsi_overbought) / (100 - self.rsi_overbought),
                                'price': prices[-1]
                            })
                    
                    # Calculate EMA
                    ema_fast_values = self._calculate_ema(prices, self.ema_fast)
                    ema_slow_values = self._calculate_ema(prices, self.ema_slow)
                    
                    if len(ema_fast_values) >= 2 and len(ema_slow_values) >= 2:
                        current_fast = ema_fast_values[-1]
                        current_slow = ema_slow_values[-1]
                        prev_fast = ema_fast_values[-2]
                        prev_slow = ema_slow_values[-2]
                        
                        # EMA Crossover Strategy
                        if prev_fast <= prev_slow and current_fast > current_slow:
                            signals.append({
                                'symbol': 'BTCUSDT',
                                'side': 'Buy',
                                'strategy': 'EMA_Bullish_Crossover',
                                'strength': 0.8,
                                'price': prices[-1]
                            })
                        elif prev_fast >= prev_slow and current_fast < current_slow:
                            signals.append({
                                'symbol': 'BTCUSDT',
                                'side': 'Sell',
                                'strategy': 'EMA_Bearish_Crossover',
                                'strength': 0.8,
                                'price': prices[-1]
                            })
        
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
        
        return signals
    
    def _execute_paper_trade(self, signal):
        """Execute a paper trade based on signal"""
        try:
            symbol = signal['symbol']
            side = signal['side']
            strategy = signal['strategy']
            price = signal['price']
            strength = signal['strength']
            
            # Check if we already have a position with the same side
            # Allow hedge mode (both long and short positions for same symbol)
            position_key = f"{symbol}_{side}"
            if position_key in self.positions:
                logger.info(f"Already have {side} position in {symbol}, skipping signal")
                return
            else:
                logger.info(f"Allowing new position: {side} position in {symbol}")
            
            # Calculate position size
            position_value = self.paper_balance * self.max_position_size * strength
            quantity = position_value / price
            
            # Create paper position
            position = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'entry_price': price,
                'entry_time': datetime.now(),
                'strategy': strategy,
                'stop_loss': price * (1 - self.stop_loss_percentage/100) if side == 'Buy' else price * (1 + self.stop_loss_percentage/100),
                'take_profit': price * (1 + self.take_profit_percentage/100) if side == 'Buy' else price * (1 - self.take_profit_percentage/100),
                'leverage': self.default_leverage
            }
            
            self.positions[position_key] = position
            
            # Record trade
            trade = {
                'time': datetime.now(),
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': price,
                'strategy': strategy,
                'type': 'OPEN'
            }
            self.trade_history.append(trade)
            
            logger.info(f"PAPER TRADE: {side} {quantity} {symbol} @ ${price:.2f} via {strategy}")
            
        except Exception as e:
            logger.error(f"Error executing paper trade: {e}")
    
    def _manage_paper_positions(self):
        """Manage existing paper positions"""
        try:
            current_time = datetime.now()
            
            for position_key, position in list(self.positions.items()):
                symbol = position['symbol']
                # Get current price
                ticker = self.api.get_futures_ticker(symbol)
                if ticker.get('success') and ticker['data'].get('list'):
                    current_price = float(ticker['data']['list'][0].get('lastPrice', 0))
                    
                    if current_price > 0:
                        # Check stop loss
                        if position['side'] == 'Buy':
                            if current_price <= position['stop_loss']:
                                self._close_paper_position(position_key, current_price, 'Stop Loss')
                            elif current_price >= position['take_profit']:
                                self._close_paper_position(position_key, current_price, 'Take Profit')
                        else:  # Sell position
                            if current_price >= position['stop_loss']:
                                self._close_paper_position(position_key, current_price, 'Stop Loss')
                            elif current_price <= position['take_profit']:
                                self._close_paper_position(position_key, current_price, 'Take Profit')
        
        except Exception as e:
            logger.error(f"Error managing positions: {e}")
    
    def _close_paper_position(self, position_key, price, reason):
        """Close a paper position"""
        try:
            position = self.positions[position_key]
            
            # Calculate P&L
            if position['side'] == 'Buy':
                pnl = (price - position['entry_price']) * position['quantity']
            else:
                pnl = (position['entry_price'] - price) * position['quantity']
            
            # Update paper balance
            self.paper_balance += pnl
            
            # Record closing trade
            trade = {
                'time': datetime.now(),
                'symbol': symbol,
                'side': 'Sell' if position['side'] == 'Buy' else 'Buy',
                'quantity': position['quantity'],
                'price': price,
                'strategy': position['strategy'],
                'type': 'CLOSE',
                'reason': reason,
                'pnl': pnl
            }
            self.trade_history.append(trade)
            
            # Remove position
            del self.positions[position_key]
            
            logger.info(f"PAPER POSITION CLOSED: {position['symbol']} @ ${price:.2f} - {reason} - PnL: ${pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error closing paper position: {e}")
    
    def get_status(self):
        """Get bot status"""
        return {
            'is_running': self.is_running,
            'paper_balance': self.paper_balance,
            'open_positions': len(self.positions),
            'total_trades': len(self.trade_history),
            'positions': self.positions,
            'recent_trades': self.trade_history[-5:] if self.trade_history else []
        }
    
    def _extract_prices_from_klines(self, klines_response):
        """Extract closing prices from klines data"""
        try:
            if klines_response.get('success') and klines_response['data'].get('list'):
                klines = klines_response['data']['list']
                prices = []
                for kline in klines:
                    if len(kline) >= 4:
                        prices.append(float(kline[4]))  # Close price
                return prices
        except Exception as e:
            logger.error(f"Error extracting prices: {e}")
        return []
    
    def _calculate_rsi(self, prices, period):
        """Calculate RSI indicator"""
        try:
            if len(prices) < period + 1:
                return []
            
            gains = []
            losses = []
            
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            
            rsi_values = []
            
            for i in range(period, len(prices)):
                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                
                rsi_values.append(rsi)
                
                # Update averages
                if i < len(prices) - 1:
                    avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                    avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            return rsi_values
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return []
    
    def _calculate_ema(self, prices, period):
        """Calculate EMA indicator"""
        try:
            if len(prices) < period:
                return []
            
            ema_values = []
            multiplier = 2 / (period + 1)
            
            # First EMA is SMA
            sma = sum(prices[:period]) / period
            ema_values.append(sma)
            
            # Calculate EMA
            for i in range(period, len(prices)):
                ema = (prices[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
                ema_values.append(ema)
            
            return ema_values
            
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return []

def main():
    """Main function"""
    print("🤖 Bybit Paper Trading Bot")
    print("=" * 50)
    
    # Initialize bot with new API key
    api_key = "hqtW8Wu0LIKkkXl7zW"
    api_secret = "tkjQxgMREM810JYEJ9ndhkOC3MS64yCtxaRb"
    
    bot = PaperTradingBot(api_key, api_secret)
    
    print("✅ Bot initialized successfully")
    print("📊 Starting paper trading session...")
    print("💡 This bot works with public data only - no real trades!")
    
    try:
        # Start paper trading
        bot.start_trading()
    except KeyboardInterrupt:
        print("\n👋 Paper trading stopped by user")
    
    # Show final status
    status = bot.get_status()
    print(f"\n📊 Final Status:")
    print(f"   Paper Balance: ${status['paper_balance']:.2f}")
    print(f"   Total Trades: {status['total_trades']}")
    print(f"   Open Positions: {status['open_positions']}")

if __name__ == "__main__":
    main() 
