import pandas as pd
import ta
from typing import List, Dict

def bollinger_bands(prices: List[float], window: int = 20, n_std: float = 2.0) -> Dict:
    """Calculate Bollinger Bands for a list of prices."""
    if len(prices) < window:
        return {'upper': None, 'middle': None, 'lower': None, 'bandwidth': None}
    df = pd.DataFrame({'close': prices})
    bb = ta.volatility.BollingerBands(df['close'], window=window, window_dev=n_std)
    upper = bb.bollinger_hband().iloc[-1]
    middle = bb.bollinger_mavg().iloc[-1]
    lower = bb.bollinger_lband().iloc[-1]
    bandwidth = upper - lower
    return {'upper': upper, 'middle': middle, 'lower': lower, 'bandwidth': bandwidth}

def on_balance_volume(prices: List[float], volumes: List[float]) -> float:
    """Calculate On-Balance Volume (OBV)."""
    if len(prices) != len(volumes) or len(prices) < 2:
        return 0.0
    df = pd.DataFrame({'close': prices, 'volume': volumes})
    obv = ta.volume.OnBalanceVolumeIndicator(df['close'], df['volume'])
    return obv.on_balance_volume().iloc[-1]

def support_resistance_levels(prices: List[float], window: int = 20) -> Dict:
    """Calculate basic support and resistance levels using rolling window high/low."""
    if len(prices) < window:
        return {'support': None, 'resistance': None}
    df = pd.DataFrame({'close': prices})
    support = df['close'].rolling(window=window).min().iloc[-1]
    resistance = df['close'].rolling(window=window).max().iloc[-1]
    return {'support': support, 'resistance': resistance}

def trendline_slope(prices: List[float], window: int = 20) -> float:
    """Calculate the slope of the trendline using linear regression."""
    if len(prices) < window:
        return 0.0
    y = pd.Series(prices[-window:])
    x = pd.Series(range(window))
    slope = ((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum()
    return slope 