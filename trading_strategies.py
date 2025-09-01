import pandas as pd
import numpy as np
import ta
from typing import Dict, List, Tuple
from pionex_api import PionexAPI
from config_loader import get_config
from indicators import bollinger_bands, on_balance_volume, support_resistance_levels, trendline_slope
import time
import logging
import yaml

class TradingStrategies:
    def __init__(self, api: PionexAPI):
        self.api = api
        self.logger = logging.getLogger(__name__)
    
    def calculate_rsi(self, prices: List[float], period: int = None) -> List[float]:
        """Calculate RSI and return the full list of values"""
        config = get_config()
        if period is None:
            period = config['rsi']['period']
        if len(prices) < period:
            return [50.0] * len(prices)
        df = pd.DataFrame({'close': prices})
        rsi = ta.momentum.RSIIndicator(df['close'], window=period)
        return rsi.rsi().tolist()
    
    def calculate_ema(self, data: List[float], period: int = None) -> List[float]:
        """Calculate EMA and return the full list of values"""
        config = get_config()
        if period is None:
            period = config['volume_filter']['ema_period']
        if len(data) < period:
            return data
        df = pd.DataFrame({'value': data})
        ema = ta.trend.EMAIndicator(df['value'], window=period)
        return ema.ema_indicator().tolist()
    
    def calculate_macd(self, prices: List[float], fast: int = None, slow: int = None, signal: int = None) -> Tuple[List[float], List[float], List[float]]:
        """Calculate MACD and return (macd_line, signal_line, histogram) as lists"""
        config = get_config()
        if fast is None:
            fast = config['macd']['fast']
        if slow is None:
            slow = config['macd']['slow']
        if signal is None:
            signal = config['macd']['signal']
        if len(prices) < slow:
            return ([0] * len(prices), [0] * len(prices), [0] * len(prices))
        df = pd.DataFrame({'close': prices})
        macd = ta.trend.MACD(df['close'], window_fast=fast, window_slow=slow, window_sign=signal)
        return (
            macd.macd().tolist(),
            macd.macd_signal().tolist(),
            macd.macd_diff().tolist()
        )
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> Tuple[List[float], List[float], List[float]]:
        """Calculate Bollinger Bands and return (upper, middle, lower) as lists"""
        if len(prices) < period:
            return ([prices[-1]] * len(prices), [prices[-1]] * len(prices), [prices[-1]] * len(prices))
        df = pd.DataFrame({'close': prices})
        bb = ta.volatility.BollingerBands(df['close'], window=period, window_dev=std_dev)
        return (
            bb.bollinger_hband().tolist(),
            bb.bollinger_mavg().tolist(),
            bb.bollinger_lband().tolist()
        )
    
    def analyze_candlestick_patterns(self, df: pd.DataFrame) -> Dict:
        """Analyze candlestick patterns with enhanced recognition"""
        if df.empty or len(df) < 3:
            return {'pattern': 'none', 'signal': 'neutral', 'strength': 0}
        
        # Get last few candles for pattern analysis
        current = df.iloc[-1]
        previous = df.iloc[-2]
        pre_previous = df.iloc[-3] if len(df) >= 3 else previous
        
        patterns = []
        signal_strength = 0
        
        # Calculate basic measurements
        current_body = abs(current['close'] - current['open'])
        current_range = current['high'] - current['low']
        previous_body = abs(previous['close'] - previous['open'])
        previous_range = previous['high'] - previous['low']
        
        # Body ratio for pin bars
        current_body_ratio = current_body / current_range if current_range > 0 else 0
        previous_body_ratio = previous_body / previous_range if previous_range > 0 else 0
        
        # 1. Engulfing Patterns
        bullish_engulfing = (
            current['open'] < previous['close'] and
            current['close'] > previous['open'] and
            current_body > previous_body * 1.2
        )
        
        bearish_engulfing = (
            current['open'] > previous['close'] and
            current['close'] < previous['open'] and
            current_body > previous_body * 1.2
        )
        
        if bullish_engulfing:
            patterns.append('bullish_engulfing')
            signal_strength += 2
        elif bearish_engulfing:
            patterns.append('bearish_engulfing')
            signal_strength -= 2
        
        # 2. Pin Bar Patterns (Hammer/Shooting Star)
        # Hammer (bullish pin bar)
        hammer = (
            current_body_ratio < 0.3 and
            current['close'] > current['open'] and
            (current['high'] - current['close']) < (current['open'] - current['low']) * 0.3 and
            (current['open'] - current['low']) > current_body * 2
        )
        
        # Shooting star (bearish pin bar)
        shooting_star = (
            current_body_ratio < 0.3 and
            current['close'] < current['open'] and
            (current['close'] - current['low']) < (current['high'] - current['open']) * 0.3 and
            (current['high'] - current['open']) > current_body * 2
        )
        
        if hammer:
            patterns.append('hammer')
            signal_strength += 1.5
        elif shooting_star:
            patterns.append('shooting_star')
            signal_strength -= 1.5
        
        # 3. Doji Patterns
        doji = current_body_ratio < 0.1
        if doji:
            patterns.append('doji')
            signal_strength += 0.5  # Neutral signal
        
        # 4. Marubozu (Strong trend candles)
        bullish_marubozu = (
            current['close'] > current['open'] and
            current_body_ratio > 0.8 and
            current['open'] == current['low'] and
            current['close'] == current['high']
        )
        
        bearish_marubozu = (
            current['close'] < current['open'] and
            current_body_ratio > 0.8 and
            current['open'] == current['high'] and
            current['close'] == current['low']
        )
        
        if bullish_marubozu:
            patterns.append('bullish_marubozu')
            signal_strength += 1
        elif bearish_marubozu:
            patterns.append('bearish_marubozu')
            signal_strength -= 1
        
        # 5. Three White Soldiers / Three Black Crows
        if len(df) >= 3:
            last_3 = df.iloc[-3:]
            three_white_soldiers = all(
                row['close'] > row['open'] and
                row['close'] > row['open'] * 1.01  # At least 1% gain
                for _, row in last_3.iterrows()
            )
            
            three_black_crows = all(
                row['close'] < row['open'] and
                row['close'] < row['open'] * 0.99  # At least 1% loss
                for _, row in last_3.iterrows()
            )
            
            if three_white_soldiers:
                patterns.append('three_white_soldiers')
                signal_strength += 2.5
            elif three_black_crows:
                patterns.append('three_black_crows')
                signal_strength -= 2.5
        
        # 6. Morning Star / Evening Star
        if len(df) >= 3:
            morning_star = (
                pre_previous['close'] < pre_previous['open'] and  # First day bearish
                previous_body_ratio < 0.3 and  # Second day small body
                current['close'] > current['open'] and  # Third day bullish
                current['close'] > (pre_previous['open'] + pre_previous['close']) / 2  # Closes above midpoint
            )
            
            evening_star = (
                pre_previous['close'] > pre_previous['open'] and  # First day bullish
                previous_body_ratio < 0.3 and  # Second day small body
                current['close'] < current['open'] and  # Third day bearish
                current['close'] < (pre_previous['open'] + pre_previous['close']) / 2  # Closes below midpoint
            )
            
            if morning_star:
                patterns.append('morning_star')
                signal_strength += 3
            elif evening_star:
                patterns.append('evening_star')
                signal_strength -= 3
        
        # Determine overall signal
        if signal_strength > 1:
            signal = 'bullish'
        elif signal_strength < -1:
            signal = 'bearish'
        else:
            signal = 'neutral'
        
        return {
            'pattern': ', '.join(patterns) if patterns else 'none',
            'signal': signal,
            'strength': abs(signal_strength),
            'patterns_detected': patterns
        }
    
    def get_market_data(self, symbol: str, interval: str = '1M', limit: int = 100) -> pd.DataFrame:
        """Get market data as DataFrame"""
        try:
            # Use correct interval format for Pionex
            interval_map = {
                '1m': '1M',
                '5m': '5M', 
                '15m': '15M',
                '30m': '30M',
                '1h': '1H',
                '4h': '4H',
                '1d': '1D'
            }
            
            api_interval = interval_map.get(interval.lower(), interval.upper())
            
            response = self.api.get_klines(symbol, api_interval, limit)
            
            if 'error' in response:
                self.logger.error(f"Error getting market data: {response['error']}")
                return pd.DataFrame()
            
            # Extract klines data
            klines_data = []
            if 'data' in response:
                if isinstance(response['data'], dict) and 'klines' in response['data']:
                    klines_data = response['data']['klines']
                elif isinstance(response['data'], list):
                    klines_data = response['data']
            
            if not klines_data:
                self.logger.warning(f"No klines data received for {symbol}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(klines_data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            
            # Convert to numeric
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Convert timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            self.logger.info(f"Retrieved {len(df)} data points for {symbol} ({api_interval})")
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting market data for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_basic_market_data(self, symbol: str) -> Dict:
        """Get basic market data when klines are not available"""
        try:
            # Get current ticker data
            ticker_response = self.api.get_ticker_price(symbol)
            if 'error' in ticker_response:
                return {'error': ticker_response['error']}
            
            current_price = float(ticker_response['data']['price'])
            
            # Create basic market data structure
            market_data = {
                'symbol': symbol,
                'current_price': current_price,
                'timestamp': int(time.time() * 1000),
                'data_available': True,
                'source': 'ticker'
            }
            
            return market_data
        except Exception as e:
            return {'error': f"Failed to get market data: {str(e)}"}

    def calculate_simple_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI with limited data points"""
        if len(prices) < period + 1:
            return 50.0  # Neutral RSI if not enough data
        
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
        
        if len(gains) < period:
            return 50.0
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def rsi_multi_timeframe_strategy(self, symbol: str, balance: float, position_size: float = None) -> Dict:
        """RSI Multi-timeframe Strategy"""
        config = get_config()
        try:
            # Get market data for different timeframes
            df_5m = self.get_market_data(symbol, '5M', 100)
            df_1h = self.get_market_data(symbol, '1H', 100)
            
            if df_5m.empty or df_1h.empty:
                return {"action": "HOLD", "reason": "No market data available"}
            
            # Calculate RSI for different timeframes
            rsi_5m_list = self.calculate_rsi(df_5m['close'].tolist(), config['rsi']['period'])
            rsi_1h_list = self.calculate_rsi(df_1h['close'].tolist(), config['rsi']['period'])
            
            rsi_5m = rsi_5m_list[-1] if rsi_5m_list else 50.0
            rsi_1h = rsi_1h_list[-1] if rsi_1h_list else 50.0
            
            # Get current price - fix the response handling
            ticker_response = self.api.get_ticker_price(symbol)
            current_price = 0
            
            if 'error' not in ticker_response and 'data' in ticker_response:
                price_data = ticker_response['data']
                if isinstance(price_data, dict) and 'price' in price_data:
                    current_price = float(price_data['price'])
                elif isinstance(price_data, str):
                    current_price = float(price_data)
            
            if current_price == 0:
                # Fallback to last close price from market data
                current_price = df_5m['close'].iloc[-1] if not df_5m.empty else 0
                if current_price == 0:
                    return {"action": "HOLD", "reason": "Unable to get current price"}
            
            # Calculate position size
            if position_size is None:
                position_size = config['position_size']
            position_value = balance * position_size
            quantity = position_value / current_price
            
            # Multi-timeframe RSI logic
            buy_signals = 0
            sell_signals = 0
            
            # 5M RSI signals
            if rsi_5m < config['rsi']['oversold']:
                buy_signals += 1
            elif rsi_5m > config['rsi']['overbought']:
                sell_signals += 1
            
            # 1H RSI signals
            if rsi_1h < config['rsi']['oversold']:
                buy_signals += 1
            elif rsi_1h > config['rsi']['overbought']:
                sell_signals += 1
            
            # Decision logic
            if buy_signals >= 2:
                return {
                    "action": "BUY",
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": current_price,
                    "rsi_5m": rsi_5m,
                    "rsi_1h": rsi_1h,
                    "signals": buy_signals,
                    "reason": f"Multi-TF RSI: {buy_signals}/2 buy signals (5M:{rsi_5m:.2f}, 1H:{rsi_1h:.2f})"
                }
            elif sell_signals >= 2:
                return {
                    "action": "SELL",
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": current_price,
                    "rsi_5m": rsi_5m,
                    "rsi_1h": rsi_1h,
                    "signals": sell_signals,
                    "reason": f"Multi-TF RSI: {sell_signals}/2 sell signals (5M:{rsi_5m:.2f}, 1H:{rsi_1h:.2f})"
                }
            else:
                return {
                    "action": "HOLD",
                    "symbol": symbol,
                    "rsi_5m": rsi_5m,
                    "rsi_1h": rsi_1h,
                    "signals": max(buy_signals, sell_signals),
                    "reason": f"Multi-TF RSI: Mixed signals - {buy_signals} buy, {sell_signals} sell"
                }
                
        except Exception as e:
            return {"action": "HOLD", "reason": f"Error in Multi-TF RSI strategy: {str(e)}"}

    def volume_filter_strategy(self, symbol: str, balance: float, position_size: float = None) -> Dict:
        """Volume Filter Strategy"""
        config = get_config()
        try:
            # Get market data with working interval
            df = self.get_market_data(symbol, '5M', 100)
            
            if df.empty:
                return {"action": "HOLD", "reason": "No market data available"}
            
            # Calculate volume EMA
            volume_ema_list = self.calculate_ema(df['volume'].tolist(), config['volume_filter']['ema_period'])
            volume_ema = volume_ema_list[-1] if volume_ema_list else df['volume'].iloc[-1]
            
            # Get current volume
            current_volume = df['volume'].iloc[-1] if not df.empty else 0
            
            # Get current price - fix the response handling
            ticker_response = self.api.get_ticker_price(symbol)
            current_price = 0
            
            if 'error' not in ticker_response and 'data' in ticker_response:
                price_data = ticker_response['data']
                if isinstance(price_data, dict) and 'price' in price_data:
                    current_price = float(price_data['price'])
                elif isinstance(price_data, str):
                    current_price = float(price_data)
            
            if current_price == 0:
                # Fallback to last close price from market data
                current_price = df['close'].iloc[-1] if not df.empty else 0
                if current_price == 0:
                    return {"action": "HOLD", "reason": "Unable to get current price"}
            
            # Calculate position size
            if position_size is None:
                position_size = config['position_size']
            position_value = balance * position_size
            quantity = position_value / current_price
            
            # Volume Filter Logic
            volume_multiplier = config['volume_filter']['multiplier']
            volume_threshold = volume_ema * volume_multiplier
            
            if current_volume > volume_threshold:
                # High volume - potential trend continuation
                return {
                    "action": "BUY",
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": current_price,
                    "volume": current_volume,
                    "volume_ema": volume_ema,
                    "reason": f"Volume Filter: High volume ({current_volume:.2f} > {volume_threshold:.2f})"
                }
            else:
                return {
                    "action": "HOLD",
                    "symbol": symbol,
                    "volume": current_volume,
                    "volume_ema": volume_ema,
                    "reason": f"Volume Filter: Low volume ({current_volume:.2f} < {volume_threshold:.2f})"
                }
                
        except Exception as e:
            return {"action": "HOLD", "reason": f"Error in Volume Filter strategy: {str(e)}"}

    def advanced_strategy(self, symbol: str, balance: float, position_size: float = None) -> Dict:
        """Advanced Strategy combining multiple indicators"""
        config = get_config()
        try:
            # Get market data with working interval
            df = self.get_market_data(symbol, '5M', 100)
            
            if df.empty:
                return {"action": "HOLD", "reason": "No market data available"}
            
            # Calculate indicators
            rsi_list = self.calculate_rsi(df['close'].tolist(), config['rsi']['period'])
            rsi = rsi_list[-1] if rsi_list else 50.0
            
            ema_list = self.calculate_ema(df['close'].tolist(), 20)
            ema = ema_list[-1] if ema_list else df['close'].iloc[-1]
            
            macd_line, macd_signal, macd_histogram = self.calculate_macd(df['close'].tolist())
            macd_current = macd_line[-1] if macd_line else 0
            macd_signal_current = macd_signal[-1] if macd_signal else 0
            
            # Get current price - fix the response handling
            ticker_response = self.api.get_ticker_price(symbol)
            current_price = 0
            
            if 'error' not in ticker_response and 'data' in ticker_response:
                price_data = ticker_response['data']
                if isinstance(price_data, dict) and 'price' in price_data:
                    current_price = float(price_data['price'])
                elif isinstance(price_data, str):
                    current_price = float(price_data)
            
            if current_price == 0:
                # Fallback to last close price from market data
                current_price = df['close'].iloc[-1] if not df.empty else 0
                if current_price == 0:
                    return {"action": "HOLD", "reason": "Unable to get current price"}
            
            # Calculate position size
            if position_size is None:
                position_size = config['position_size']
            position_value = balance * position_size
            quantity = position_value / current_price
            
            # Advanced Strategy Logic
            buy_signals = 0
            sell_signals = 0
            
            # RSI signals
            if rsi < config['rsi']['oversold']:
                buy_signals += 1
            elif rsi > config['rsi']['overbought']:
                sell_signals += 1
            
            # EMA signals
            if current_price > ema:
                buy_signals += 1
            else:
                sell_signals += 1
            
            # MACD signals
            if macd_current > macd_signal_current:
                buy_signals += 1
            else:
                sell_signals += 1
            
            # Decision logic
            if buy_signals >= 2:
                return {
                    "action": "BUY",
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": current_price,
                    "rsi": rsi,
                    "ema": ema,
                    "macd": macd_current,
                    "signals": buy_signals,
                    "reason": f"Advanced: {buy_signals}/3 buy signals (RSI:{rsi:.2f}, EMA:{ema:.2f}, MACD:{macd_current:.2f})"
                }
            elif sell_signals >= 2:
                return {
                    "action": "SELL",
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": current_price,
                    "rsi": rsi,
                    "ema": ema,
                    "macd": macd_current,
                    "signals": sell_signals,
                    "reason": f"Advanced: {sell_signals}/3 sell signals (RSI:{rsi:.2f}, EMA:{ema:.2f}, MACD:{macd_current:.2f})"
                }
            else:
                return {
                    "action": "HOLD",
                    "symbol": symbol,
                    "rsi": rsi,
                    "ema": ema,
                    "macd": macd_current,
                    "signals": max(buy_signals, sell_signals),
                    "reason": f"Advanced: Mixed signals - {buy_signals} buy, {sell_signals} sell"
                }
                
        except Exception as e:
            return {"action": "HOLD", "reason": f"Error in Advanced strategy: {str(e)}"}
    
    def rsi_strategy(self, symbol: str, balance: float, position_size: float = None) -> Dict:
        """RSI-based trading strategy"""
        config = get_config()
        try:
            # Get market data with working interval
            df = self.get_market_data(symbol, '5M', 100)
            if df.empty:
                return {"action": "HOLD", "reason": "No market data available"}
            
            # Calculate RSI
            rsi_list = self.calculate_rsi(df['close'].tolist(), config['rsi']['period'])
            rsi = rsi_list[-1] if rsi_list else 50.0
            
            # Get current price
            ticker = self.api.get_ticker_price(symbol)
            current_price = float(ticker.get('data', {}).get('price', 0)) if 'data' in ticker else 0
            
            if current_price == 0:
                return {"action": "HOLD", "reason": "Unable to get current price"}
            
            # Calculate position size in USDT
            if position_size is None:
                position_size = config['position_size']
            position_value = balance * position_size
            quantity = position_value / current_price
            
            # RSI Strategy Logic
            if rsi < config['rsi']['oversold']:
                return {
                    "action": "BUY",
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": current_price,
                    "rsi": rsi,
                    "stop_loss": current_price * (1 - config['stop_loss_percentage'] / 100),  # -1.5%
                    "take_profit": current_price * (1 + config['take_profit_percentage'] / 100),  # +2.5%
                    "reason": f"RSI oversold ({rsi:.2f})"
                }
            elif rsi > config['rsi']['overbought']:
                return {
                    "action": "SELL",
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": current_price,
                    "rsi": rsi,
                    "stop_loss": current_price * (1 + config['stop_loss_percentage'] / 100),  # +1.5%
                    "take_profit": current_price * (1 - config['take_profit_percentage'] / 100),  # -2.5%
                    "reason": f"RSI overbought ({rsi:.2f})"
                }
            else:
                return {
                    "action": "HOLD",
                    "symbol": symbol,
                    "rsi": rsi,
                    "reason": f"RSI neutral ({rsi:.2f})"
                }
                
        except Exception as e:
            return {"action": "HOLD", "reason": f"Strategy error: {str(e)}"}
    
    def grid_trading_strategy(self, symbol: str, balance: float, grid_levels: int = None) -> Dict:
        """Grid trading strategy"""
        config = get_config()
        try:
            ticker = self.api.get_ticker_price(symbol)
            current_price = float(ticker.get('data', {}).get('price', 0)) if 'data' in ticker else 0
            
            if current_price == 0:
                return {"action": "HOLD", "reason": "Unable to get current price"}
            
            # Calculate grid levels
            if grid_levels is None:
                grid_levels = config['grid_trading']['levels']
            grid_spacing = config['grid_trading']['spacing']
            grid_prices = []
            
            for i in range(grid_levels):
                price = current_price * (1 + (i - grid_levels//2) * grid_spacing)
                grid_prices.append(price)
            
            # Find closest grid level
            closest_grid = min(grid_prices, key=lambda x: abs(x - current_price))
            
            if current_price < closest_grid:
                return {
                    "action": "BUY",
                    "symbol": symbol,
                    "quantity": (balance * config['grid_trading']['position_size']) / current_price,
                    "price": current_price,
                    "stop_loss": current_price * (1 - config['stop_loss_percentage'] / 100),
                    "take_profit": current_price * (1 + config['take_profit_percentage'] / 100),
                    "reason": f"Grid buy at {current_price:.2f}"
                }
            elif current_price > closest_grid:
                return {
                    "action": "SELL",
                    "symbol": symbol,
                    "quantity": (balance * config['grid_trading']['position_size']) / current_price,
                    "price": current_price,
                    "stop_loss": current_price * (1 + config['stop_loss_percentage'] / 100),
                    "take_profit": current_price * (1 - config['take_profit_percentage'] / 100),
                    "reason": f"Grid sell at {current_price:.2f}"
                }
            else:
                return {
                    "action": "HOLD",
                    "reason": f"At grid level {closest_grid:.2f}"
                }
                
        except Exception as e:
            return {"action": "HOLD", "reason": f"Grid strategy error: {str(e)}"}
    
    def dca_strategy(self, symbol: str, balance: float, dca_amount: float = None) -> Dict:
        """Dollar Cost Averaging strategy"""
        config = get_config()
        try:
            ticker = self.api.get_ticker_price(symbol)
            current_price = float(ticker.get('data', {}).get('price', 0)) if 'data' in ticker else 0
            
            if current_price == 0:
                return {"action": "HOLD", "reason": "Unable to get current price"}
            
            # Simple DCA - buy fixed amount
            if dca_amount is None:
                dca_amount = config['dca_strategy']['amount']
            quantity = dca_amount / current_price
            
            return {
                "action": "BUY",
                "symbol": symbol,
                "quantity": quantity,
                "price": current_price,
                "stop_loss": current_price * (1 - config['stop_loss_percentage'] / 100),
                "take_profit": current_price * (1 + config['take_profit_percentage'] / 100),
                "reason": f"DCA buy ${dca_amount}"
            }
            
        except Exception as e:
            return {"action": "HOLD", "reason": f"DCA strategy error: {str(e)}"}
    
    def get_strategy_signal(self, strategy: str, symbol: str, balance: float, **kwargs) -> Dict:
        """Get trading signal based on selected strategy"""
        config = get_config()
        if strategy == "RSI_STRATEGY":
            return self.rsi_strategy(symbol, balance, config['position_size'])
        elif strategy == "RSI_MULTI_TF":
            return self.rsi_multi_timeframe_strategy(symbol, balance, config['position_size'])
        elif strategy == "VOLUME_FILTER":
            return self.volume_filter_strategy(symbol, balance, config['position_size'])
        elif strategy == "ADVANCED_STRATEGY":
            return self.advanced_strategy(symbol, balance, config['position_size'])
        elif strategy == "GRID_TRADING":
            return self.grid_trading_strategy(symbol, balance, config['grid_trading']['levels'])
        elif strategy == "DCA":
            return self.dca_strategy(symbol, balance, config['dca_strategy']['amount'])
        else:
            return {"action": "HOLD", "reason": "Unknown strategy"}
    
    def calculate_portfolio_metrics(self, positions: List[Dict]) -> Dict:
        """Calculate portfolio performance metrics"""
        if not positions:
            return {"total_value": 0, "total_pnl": 0, "win_rate": 0}
        
        total_value = 0
        total_pnl = 0
        winning_positions = 0
        
        for position in positions:
            if 'unrealizedPnl' in position:
                pnl = float(position['unrealizedPnl'])
                total_pnl += pnl
                if pnl > 0:
                    winning_positions += 1
            
            if 'positionValue' in position:
                total_value += float(position['positionValue'])
        
        win_rate = (winning_positions / len(positions)) * 100 if positions else 0
        
        return {
            "total_value": total_value,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "position_count": len(positions)
        }
    
    def calculate_trailing_stop(self, entry_price: float, current_price: float, 
                               trailing_percentage: float = None, tp_hit: bool = False) -> float:
        """Calculate trailing stop loss with enhanced logic"""
        config = get_config()
        if trailing_percentage is None:
            trailing_percentage = config['trailing_stop']['percentage']
        
        # Only enable trailing stop after TP is hit
        if not tp_hit:
            return entry_price * (1 - config.get('stop_loss_percentage', 1.5) / 100)
        
        if current_price > entry_price:
            # For long positions, trailing stop moves up
            return max(entry_price * (1 - trailing_percentage / 100), 
                      current_price * (1 - trailing_percentage / 100))
        else:
            # For short positions, trailing stop moves down
            return min(entry_price * (1 + trailing_percentage / 100), 
                      current_price * (1 + trailing_percentage / 100))
    
    def calculate_dynamic_mobile_sl(self, entry_price: float, current_price: float, 
                                   tp_hit: bool = False, profit_lock_percentage: float = 0.5) -> float:
        """Calculate dynamic mobile stop loss that adjusts upward after TP"""
        config = get_config()
        
        if not tp_hit:
            # Use regular stop loss before TP is hit
            return entry_price * (1 - config.get('stop_loss_percentage', 1.5) / 100)
        
        # After TP is hit, implement dynamic mobile SL
        if current_price > entry_price:
            # For profitable long positions
            profit_percentage = ((current_price - entry_price) / entry_price) * 100
            
            if profit_percentage >= profit_lock_percentage:
                # Lock in profits by moving SL to entry price
                return entry_price
            else:
                # Gradually move SL up as price increases
                mobile_sl = entry_price + (current_price - entry_price) * 0.3
                return max(mobile_sl, entry_price * (1 - config.get('stop_loss_percentage', 1.5) / 100))
        else:
            # For short positions
            profit_percentage = ((entry_price - current_price) / entry_price) * 100
            
            if profit_percentage >= profit_lock_percentage:
                # Lock in profits by moving SL to entry price
                return entry_price
            else:
                # Gradually move SL down as price decreases
                mobile_sl = entry_price - (entry_price - current_price) * 0.3
                return min(mobile_sl, entry_price * (1 + config.get('stop_loss_percentage', 1.5) / 100))
    
    def should_update_trailing_stop(self, entry_price: float, current_price: float, 
                                   current_stop: float, trailing_percentage: float = None, tp_hit: bool = False) -> Tuple[bool, float]:
        """Check if trailing stop should be updated with enhanced logic"""
        config = get_config()
        if trailing_percentage is None:
            trailing_percentage = config['trailing_stop']['percentage']
        
        # Only update if TP has been hit
        if not tp_hit:
            return False, current_stop
        
        new_stop = self.calculate_trailing_stop(entry_price, current_price, trailing_percentage, tp_hit)
        
        if current_price > entry_price:
            # For long positions, update if new stop is higher
            should_update = new_stop > current_stop
        else:
            # For short positions, update if new stop is lower
            should_update = new_stop < current_stop
        
        return should_update, new_stop
    
    def calculate_dynamic_stop_loss(self, entry_price: float, current_price: float, 
                                   symbol: str, atr_period: int = 14, multiplier: float = 2.0) -> float:
        """Calculate dynamic stop loss based on ATR (Average True Range)"""
        try:
            # Get market data for ATR calculation with correct interval
            df = self.get_market_data(symbol, '5M', atr_period + 10)
            if df.empty or len(df) < atr_period:
                # Fallback to percentage-based SL
                config = get_config()
                return entry_price * (1 - config.get('stop_loss_percentage', 1.5) / 100)
            
            # Calculate ATR
            high = df['high'].tolist()
            low = df['low'].tolist()
            close = df['close'].tolist()
            
            true_ranges = []
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                true_ranges.append(max(tr1, tr2, tr3))
            
            if len(true_ranges) < atr_period:
                config = get_config()
                return entry_price * (1 - config.get('stop_loss_percentage', 1.5) / 100)
            
            # Calculate ATR
            atr = sum(true_ranges[-atr_period:]) / atr_period
            
            # Dynamic stop loss based on ATR
            dynamic_sl = entry_price - (atr * multiplier)
            
            # Ensure minimum stop loss
            config = get_config()
            min_sl_percentage = config.get('stop_loss_percentage', 1.5)
            min_sl = entry_price * (1 - min_sl_percentage / 100)
            
            return max(dynamic_sl, min_sl)
            
        except Exception as e:
            self.logger.error(f"Error calculating dynamic stop loss: {e}")
            config = get_config()
            return entry_price * (1 - config.get('stop_loss_percentage', 1.5) / 100)
    
    def calculate_dynamic_take_profit(self, entry_price: float, current_price: float,
                                     symbol: str, atr_period: int = 14, multiplier: float = 3.0) -> float:
        """Calculate dynamic take profit based on ATR and market volatility"""
        try:
            # Get market data for ATR calculation with correct interval
            df = self.get_market_data(symbol, '5M', atr_period + 10)
            if df.empty or len(df) < atr_period:
                # Fallback to percentage-based TP
                config = get_config()
                return entry_price * (1 + config.get('take_profit_percentage', 2.5) / 100)
            
            # Calculate ATR
            high = df['high'].tolist()
            low = df['low'].tolist()
            close = df['close'].tolist()
            
            true_ranges = []
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                true_ranges.append(max(tr1, tr2, tr3))
            
            if len(true_ranges) < atr_period:
                config = get_config()
                return entry_price * (1 + config.get('take_profit_percentage', 2.5) / 100)
            
            # Calculate ATR
            atr = sum(true_ranges[-atr_period:]) / atr_period
            
            # Dynamic take profit based on ATR
            dynamic_tp = entry_price + (atr * multiplier)
            
            # Ensure minimum take profit
            config = get_config()
            min_tp_percentage = config.get('take_profit_percentage', 2.5)
            min_tp = entry_price * (1 + min_tp_percentage / 100)
            
            return max(dynamic_tp, min_tp)
            
        except Exception as e:
            self.logger.error(f"Error calculating dynamic take profit: {e}")
            config = get_config()
            return entry_price * (1 + config.get('take_profit_percentage', 2.5) / 100)

    def calculate_on_balance_volume(self, prices: List[float], volumes: List[float]) -> Dict:
        """Calculate On-Balance Volume (OBV) with trend strength analysis"""
        if len(prices) < 2 or len(volumes) < 2:
            return {'obv': 0, 'trend': 'neutral', 'strength': 0, 'divergence': False}
        
        try:
            # Calculate OBV
            obv_values = [volumes[0]]  # Start with first volume
            
            for i in range(1, len(prices)):
                if prices[i] > prices[i-1]:
                    # Price up, add volume
                    obv_values.append(obv_values[-1] + volumes[i])
                elif prices[i] < prices[i-1]:
                    # Price down, subtract volume
                    obv_values.append(obv_values[-1] - volumes[i])
                else:
                    # Price unchanged, OBV unchanged
                    obv_values.append(obv_values[-1])
            
            # Calculate OBV trend
            recent_obv = obv_values[-10:] if len(obv_values) >= 10 else obv_values
            obv_slope = self.calculate_trend_slope(recent_obv)
            
            # Determine trend strength
            if obv_slope > 0:
                trend = 'bullish'
                strength = min(abs(obv_slope) / 1000, 1.0)  # Normalize strength
            elif obv_slope < 0:
                trend = 'bearish'
                strength = min(abs(obv_slope) / 1000, 1.0)  # Normalize strength
            else:
                trend = 'neutral'
                strength = 0
            
            # Detect divergence
            price_trend = 'up' if prices[-1] > prices[-5] else 'down' if prices[-1] < prices[-5] else 'sideways'
            obv_trend = 'up' if obv_values[-1] > obv_values[-5] else 'down' if obv_values[-1] < obv_values[-5] else 'sideways'
            
            divergence = False
            if price_trend != obv_trend and price_trend != 'sideways' and obv_trend != 'sideways':
                divergence = True
            
            return {
                'obv': obv_values[-1],
                'trend': trend,
                'strength': strength,
                'divergence': divergence,
                'obv_values': obv_values,
                'price_trend': price_trend,
                'obv_trend': obv_trend
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating OBV: {e}")
            return {'obv': 0, 'trend': 'neutral', 'strength': 0, 'divergence': False}
    
    def analyze_volume_trend_strength(self, prices: List[float], volumes: List[float]) -> Dict:
        """Analyze volume trend strength and patterns"""
        if len(prices) < 10 or len(volumes) < 10:
            return {'strength': 0, 'pattern': 'insufficient_data', 'signal': 'neutral'}
        
        try:
            # Calculate volume moving averages
            volume_ma_short = sum(volumes[-5:]) / 5
            volume_ma_long = sum(volumes[-20:]) / 20
            
            # Current volume vs averages
            current_volume = volumes[-1]
            volume_ratio_short = current_volume / volume_ma_short if volume_ma_short > 0 else 1
            volume_ratio_long = current_volume / volume_ma_long if volume_ma_long > 0 else 1
            
            # Volume trend strength
            recent_volumes = volumes[-10:]
            volume_slope = self.calculate_trend_slope(recent_volumes)
            
            # Determine volume pattern
            if volume_ratio_short > 2.0 and volume_ratio_long > 1.5:
                pattern = 'volume_spike'
                signal = 'strong'
            elif volume_ratio_short > 1.5 and volume_ratio_long > 1.2:
                pattern = 'volume_increase'
                signal = 'moderate'
            elif volume_ratio_short < 0.5 and volume_ratio_long < 0.8:
                pattern = 'volume_decrease'
                signal = 'weak'
            else:
                pattern = 'normal_volume'
                signal = 'neutral'
            
            # Volume trend strength (0-1 scale)
            strength = min(abs(volume_slope) / 1000, 1.0)
            
            return {
                'strength': strength,
                'pattern': pattern,
                'signal': signal,
                'volume_ratio_short': volume_ratio_short,
                'volume_ratio_long': volume_ratio_long,
                'volume_slope': volume_slope
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing volume trend strength: {e}")
            return {'strength': 0, 'pattern': 'error', 'signal': 'neutral'}
    
    def calculate_support_resistance_levels(self, prices: List[float], window: int = 20) -> Dict:
        """Calculate support and resistance levels with trend line analysis"""
        if len(prices) < window:
            return {'support': None, 'resistance': None, 'trend': 'neutral'}
        
        try:
            # Find local minima and maxima
            minima = []
            maxima = []
            
            for i in range(1, len(prices) - 1):
                if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                    minima.append((i, prices[i]))
                elif prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                    maxima.append((i, prices[i]))
            
            # Calculate support level (from recent minima)
            support_levels = []
            for idx, price in minima[-5:]:  # Last 5 minima
                support_levels.append(price)
            
            # Calculate resistance level (from recent maxima)
            resistance_levels = []
            for idx, price in maxima[-5:]:  # Last 5 maxima
                resistance_levels.append(price)
            
            # Find strongest support and resistance
            current_price = prices[-1]
            
            # Support: closest level below current price
            valid_supports = [s for s in support_levels if s < current_price]
            support = max(valid_supports) if valid_supports else None
            
            # Resistance: closest level above current price
            valid_resistances = [r for r in resistance_levels if r > current_price]
            resistance = min(valid_resistances) if valid_resistances else None
            
            # Trend analysis
            recent_prices = prices[-window:]
            trend_slope = self.calculate_trend_slope(recent_prices)
            
            if trend_slope > 0.01:
                trend = 'uptrend'
            elif trend_slope < -0.01:
                trend = 'downtrend'
            else:
                trend = 'sideways'
            
            return {
                'support': support,
                'resistance': resistance,
                'trend': trend,
                'support_levels': support_levels,
                'resistance_levels': resistance_levels,
                'trend_slope': trend_slope
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating support/resistance: {e}")
            return {'support': None, 'resistance': None, 'trend': 'neutral'}
    
    def calculate_trend_slope(self, prices: List[float]) -> float:
        """Calculate trend slope using linear regression"""
        if len(prices) < 2:
            return 0.0
        
        try:
            x = list(range(len(prices)))
            y = prices
            
            # Simple linear regression
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))
            
            # Calculate slope
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
            
            return slope
            
        except Exception as e:
            self.logger.error(f"Error calculating trend slope: {e}")
            return 0.0
    
    def analyze_price_action(self, prices: List[float], volumes: List[float] = None) -> Dict:
        """Analyze price action patterns and market structure"""
        if len(prices) < 10:
            return {'structure': 'insufficient_data', 'breakout': False, 'consolidation': False}
        
        try:
            # Calculate price ranges
            recent_prices = prices[-10:]
            price_range = max(recent_prices) - min(recent_prices)
            avg_price = sum(recent_prices) / len(recent_prices)
            
            # Detect consolidation
            range_percentage = (price_range / avg_price) * 100
            consolidation = range_percentage < 5  # Less than 5% range
            
            # Detect breakout
            current_price = prices[-1]
            previous_high = max(prices[-20:-1])
            previous_low = min(prices[-20:-1])
            
            breakout_up = current_price > previous_high * 1.01  # 1% above previous high
            breakout_down = current_price < previous_low * 0.99  # 1% below previous low
            
            # Market structure
            if breakout_up:
                structure = 'bullish_breakout'
            elif breakout_down:
                structure = 'bearish_breakout'
            elif consolidation:
                structure = 'consolidation'
            else:
                structure = 'trending'
            
            return {
                'structure': structure,
                'breakout': breakout_up or breakout_down,
                'consolidation': consolidation,
                'range_percentage': range_percentage,
                'breakout_direction': 'up' if breakout_up else 'down' if breakout_down else None
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing price action: {e}")
            return {'structure': 'error', 'breakout': False, 'consolidation': False} 

class RSIFilter:
    """
    RSI Multi-Timeframe Filter with real-time management capabilities
    Supports Normal and Reduced modes, enable/disable control, and editable thresholds
    """
    
    def __init__(self, api: PionexAPI):
        self.api = api
        self.logger = logging.getLogger(__name__)
        self.config = get_config()
        
        # Load initial configuration
        self._load_config()
        
        # Real-time state
        self.enabled = self.config.get('rsi_filter', {}).get('enabled', True)
        self.mode = self.config.get('rsi_filter', {}).get('mode', 'normal')
        self.thresholds = self.config.get('rsi_filter', {}).get('thresholds', {
            'long': {'rsi_5m': 30, 'rsi_1h': 50},
            'short': {'rsi_5m': 70, 'rsi_1h': 50}
        })
        self.timeframes = self.config.get('rsi_filter', {}).get('timeframes', {
            'short': '5m',
            'long': '1h'
        })
        
        self.logger.info(f"RSI Filter initialized - Enabled: {self.enabled}, Mode: {self.mode}")
    
    def _load_config(self):
        """Load configuration from config file"""
        try:
            self.config = get_config()
        except Exception as e:
            self.logger.error(f"Error loading RSI filter config: {e}")
    
    def update_config(self, **kwargs):
        """Update RSI filter configuration in real-time"""
        try:
            if 'enabled' in kwargs:
                self.enabled = kwargs['enabled']
                self.logger.info(f"RSI Filter {'enabled' if self.enabled else 'disabled'}")
            
            if 'mode' in kwargs:
                self.mode = kwargs['mode']
                self.logger.info(f"RSI Filter mode changed to: {self.mode}")
            
            if 'thresholds' in kwargs:
                self.thresholds.update(kwargs['thresholds'])
                self.logger.info(f"RSI Filter thresholds updated: {self.thresholds}")
            
            # Update config file
            self._save_config()
            
            return True
        except Exception as e:
            self.logger.error(f"Error updating RSI filter config: {e}")
            return False
    
    def _save_config(self):
        """Save current configuration to config file"""
        try:
            # Load current config
            config = get_config()
            
            # Update RSI filter section
            if 'rsi_filter' not in config:
                config['rsi_filter'] = {}
            
            config['rsi_filter'].update({
                'enabled': self.enabled,
                'mode': self.mode,
                'thresholds': self.thresholds,
                'timeframes': self.timeframes
            })
            
            # Save config
            with open('config.yaml', 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
                
        except Exception as e:
            self.logger.error(f"Error saving RSI filter config: {e}")
    
    def get_current_config(self):
        """Get current RSI filter configuration"""
        return {
            'enabled': self.enabled,
            'mode': self.mode,
            'thresholds': self.thresholds,
            'timeframes': self.timeframes
        }
    
    def check_rsi_conditions(self, symbol: str, direction: str) -> Dict:
        """
        Check RSI conditions for a given symbol and direction
        Returns: {'valid': bool, 'rsi_5m': float, 'rsi_1h': float, 'message': str}
        """
        if not self.enabled:
            return {
                'valid': True,
                'rsi_5m': None,
                'rsi_1h': None,
                'message': 'RSI Filter disabled'
            }
        
        try:
            # Get RSI values for both timeframes
            rsi_5m = self._get_rsi_value(symbol, '5m')
            rsi_1h = self._get_rsi_value(symbol, '1h')
            
            if rsi_5m is None or rsi_1h is None:
                return {
                    'valid': False,
                    'rsi_5m': rsi_5m,
                    'rsi_1h': rsi_1h,
                    'message': 'Unable to calculate RSI values'
                }
            
            # Get thresholds for the direction
            thresholds = self.thresholds.get(direction.lower(), {})
            rsi_5m_threshold = thresholds.get('rsi_5m', 50)
            rsi_1h_threshold = thresholds.get('rsi_1h', 50)
            
            # Apply mode-specific logic
            if self.mode == 'reduced':
                # Reduced mode: Only check one timeframe
                if direction.lower() == 'long':
                    valid = rsi_5m < rsi_5m_threshold
                    message = f"Reduced mode LONG: RSI 5m ({rsi_5m:.2f}) < {rsi_5m_threshold}"
                else:  # short
                    valid = rsi_5m > rsi_5m_threshold
                    message = f"Reduced mode SHORT: RSI 5m ({rsi_5m:.2f}) > {rsi_5m_threshold}"
            else:
                # Normal mode: Check both timeframes
                if direction.lower() == 'long':
                    valid = rsi_5m < rsi_5m_threshold and rsi_1h < rsi_1h_threshold
                    message = f"Normal mode LONG: RSI 5m ({rsi_5m:.2f}) < {rsi_5m_threshold} AND RSI 1h ({rsi_1h:.2f}) < {rsi_1h_threshold}"
                else:  # short
                    valid = rsi_5m > rsi_5m_threshold and rsi_1h > rsi_1h_threshold
                    message = f"Normal mode SHORT: RSI 5m ({rsi_5m:.2f}) > {rsi_5m_threshold} AND RSI 1h ({rsi_1h:.2f}) > {rsi_1h_threshold}"
            
            return {
                'valid': valid,
                'rsi_5m': rsi_5m,
                'rsi_1h': rsi_1h,
                'message': message
            }
            
        except Exception as e:
            self.logger.error(f"Error checking RSI conditions for {symbol} {direction}: {e}")
            return {
                'valid': False,
                'rsi_5m': None,
                'rsi_1h': None,
                'message': f'Error: {str(e)}'
            }
    
    def _get_rsi_value(self, symbol: str, timeframe: str) -> float:
        """Get RSI value for a specific symbol and timeframe"""
        try:
            # Get candlestick data
            candles = self.api.get_candles(symbol, timeframe, limit=100)
            if not candles or len(candles) < 14:
                self.logger.warning(f"Insufficient data for RSI calculation: {symbol} {timeframe}")
                return None
            
            # Extract close prices
            prices = [float(candle['close']) for candle in candles]
            
            # Calculate RSI
            rsi_values = self.calculate_rsi(prices, period=14)
            if not rsi_values:
                return None
            
            return rsi_values[-1]  # Return latest RSI value
            
        except Exception as e:
            self.logger.error(f"Error getting RSI value for {symbol} {timeframe}: {e}")
            return None
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """Calculate RSI values"""
        try:
            if len(prices) < period + 1:
                return []
            
            df = pd.DataFrame({'close': prices})
            rsi = ta.momentum.RSIIndicator(df['close'], window=period)
            return rsi.rsi().tolist()
            
        except Exception as e:
            self.logger.error(f"Error calculating RSI: {e}")
            return []
    
    def get_status_summary(self) -> Dict:
        """Get a summary of the RSI filter status"""
        return {
            'enabled': self.enabled,
            'mode': self.mode,
            'thresholds': self.thresholds,
            'timeframes': self.timeframes,
            'status': 'Active' if self.enabled else 'Disabled'
        } 