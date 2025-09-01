import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import logging
from pathlib import Path

from config_loader import get_config
from pionex_api import PionexAPI
from trading_strategies import TradingStrategies

class Backtester:
    def __init__(self, user_id: int = None):
        self.user_id = user_id
        self.api = PionexAPI()
        self.config = get_config()
        self.strategies = TradingStrategies(self.api)
        self.logger = self._setup_logging()
        self.paper_trading = self.config.get('backtesting', {}).get('paper_trading', True)
        self.ledger = []  # Simulated trades for paper trading

    def _setup_logging(self):
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        instance_id = f"user_{self.user_id}" if self.user_id else "global"
        logger = logging.getLogger(f"Backtester_{instance_id}")
        logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(log_dir / f"backtesting_{instance_id}.log")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        return logger

    def fetch_historical_klines(self, symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
        klines = self.api.get_klines(symbol, interval, limit)
        if 'error' in klines or 'data' not in klines:
            self.logger.error(f"Error fetching klines: {klines.get('error', 'No data')}")
            return pd.DataFrame()
        df = pd.DataFrame(klines['data'])
        # Assume columns: open_time, open, high, low, close, volume, ...
        df.columns = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'num_trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'][:len(df.columns)]
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close'] = df['close'].astype(float)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df

    def run_backtest(self, symbol: str, strategy: str, interval: str = '1h', period: int = 500, initial_balance: float = 1000.0, **kwargs) -> Dict:
        df = self.fetch_historical_klines(symbol, interval, period)
        if df.empty:
            return {'error': 'No historical data available'}
        balance = initial_balance
        position = 0
        entry_price = 0
        trades = []
        equity_curve = [balance]
        for i in range(20, len(df)):
            price = df['close'].iloc[i]
            # Get signal from strategy
            if strategy == 'RSI_STRATEGY':
                signal = self.strategies.rsi_strategy(symbol, balance)
            elif strategy == 'RSI_MULTI_TF':
                signal = self.strategies.rsi_multi_timeframe_strategy(symbol, balance)
            elif strategy == 'VOLUME_FILTER':
                signal = self.strategies.volume_filter_strategy(symbol, balance)
            elif strategy == 'ADVANCED_STRATEGY':
                signal = self.strategies.advanced_strategy(symbol, balance)
            elif strategy == 'GRID_TRADING':
                signal = self.strategies.grid_trading_strategy(symbol, balance)
            elif strategy == 'DCA':
                signal = self.strategies.dca_strategy(symbol, balance)
            else:
                return {'error': f'Unknown strategy: {strategy}'}
            action = signal.get('action')
            # Simulate trade
            if action == 'BUY' and position == 0:
                position = balance / price
                entry_price = price
                balance = 0
                trades.append({'type': 'BUY', 'price': price, 'time': df['open_time'].iloc[i]})
            elif action == 'SELL' and position > 0:
                balance = position * price
                trades.append({'type': 'SELL', 'price': price, 'time': df['open_time'].iloc[i]})
                position = 0
                entry_price = 0
            equity = balance + position * price
            equity_curve.append(equity)
        # Final close
        if position > 0:
            balance = position * df['close'].iloc[-1]
            trades.append({'type': 'SELL', 'price': df['close'].iloc[-1], 'time': df['open_time'].iloc[-1]})
            position = 0
        final_equity = balance
        pnl = final_equity - initial_balance
        returns = np.diff(equity_curve) / equity_curve[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        max_drawdown = np.max(np.maximum.accumulate(equity_curve) - equity_curve)
        win_trades = [t for t in trades if t['type'] == 'SELL' and t['price'] > entry_price]
        win_rate = len(win_trades) / (len([t for t in trades if t['type'] == 'SELL']) or 1)
        result = {
            'symbol': symbol,
            'strategy': strategy,
            'interval': interval,
            'initial_balance': initial_balance,
            'final_balance': final_equity,
            'pnl': pnl,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trades': trades,
            'equity_curve': equity_curve
        }
        self.logger.info(f"Backtest result: {result}")
        return result

    def enable_paper_trading(self):
        self.paper_trading = True
        self.logger.info("Paper trading enabled")

    def disable_paper_trading(self):
        self.paper_trading = False
        self.logger.info("Paper trading disabled")

    def record_paper_trade(self, trade: Dict):
        self.ledger.append(trade)
        self.logger.info(f"Paper trade recorded: {trade}")

    def get_paper_trading_ledger(self) -> List[Dict]:
        return self.ledger

# Global backtester instances
backtesters = {}

def get_backtester(user_id: int) -> Backtester:
    if user_id not in backtesters:
        backtesters[user_id] = Backtester(user_id)
    return backtesters[user_id]

def run_backtest(user_id: int, symbol: str, strategy: str, interval: str = '1h', period: int = 500, initial_balance: float = 1000.0, **kwargs) -> Dict:
    backtester = get_backtester(user_id)
    return backtester.run_backtest(symbol, strategy, interval, period, initial_balance, **kwargs)

def enable_paper_trading(user_id: int):
    backtester = get_backtester(user_id)
    backtester.enable_paper_trading()

def disable_paper_trading(user_id: int):
    backtester = get_backtester(user_id)
    backtester.disable_paper_trading()

def record_paper_trade(user_id: int, trade: Dict):
    backtester = get_backtester(user_id)
    backtester.record_paper_trade(trade)

def get_paper_trading_ledger(user_id: int) -> List[Dict]:
    backtester = get_backtester(user_id)
    return backtester.get_paper_trading_ledger() 