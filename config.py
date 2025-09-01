import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_USERS = os.getenv('ALLOWED_USERS', '').split(',')

# Pionex API Configuration
PIONEX_API_KEY = os.getenv('PIONEX_API_KEY')
PIONEX_SECRET_KEY = os.getenv('PIONEX_SECRET_KEY')
PIONEX_BASE_URL = "https://api.pionex.com"

# Trading Configuration
DEFAULT_LEVERAGE = 10
DEFAULT_MARGIN_TYPE = "isolated"
MAX_POSITION_SIZE = 0.1  # 10% of balance
STOP_LOSS_PERCENTAGE = 1.5  # -1.5%
TAKE_PROFIT_PERCENTAGE = 2.5  # +2.5%
TRAILING_STOP_PERCENTAGE = 1.0  # 1% trailing stop

# RSI Configuration
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Multi-Timeframe RSI Configuration
RSI_5M_OVERSOLD = 30
RSI_5M_OVERBOUGHT = 70
RSI_1H_NEUTRAL = 50

# Volume Filter Configuration
VOLUME_EMA_PERIOD = 20
VOLUME_MULTIPLIER = 1.5  # Volume must be 1.5x EMA

# MACD Configuration
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Database Configuration (for storing user data)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///trading_bot.db')

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = 'trading_bot.log'

# Trading Pairs
SUPPORTED_PAIRS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT',
    'DOTUSDT', 'LINKUSDT', 'MATICUSDT', 'AVAXUSDT', 'UNIUSDT'
]

# Strategy Types
STRATEGY_TYPES = {
    'RSI_STRATEGY': 'RSI Strategy',
    'RSI_MULTI_TF': 'RSI Multi-Timeframe',
    'VOLUME_FILTER': 'Volume Filter Strategy',
    'ADVANCED_STRATEGY': 'Advanced Strategy',
    'GRID_TRADING': 'Grid Trading',
    'DCA': 'Dollar Cost Averaging',
    'MANUAL': 'Manual Trading'
}

# Strategy Descriptions
STRATEGY_DESCRIPTIONS = {
    'RSI_STRATEGY': 'Basic RSI strategy with oversold/overbought signals',
    'RSI_MULTI_TF': 'RSI analysis on 5-minute and 1-hour timeframes for trend confirmation',
    'VOLUME_FILTER': 'RSI strategy with volume filter using EMA(20)',
    'ADVANCED_STRATEGY': 'Combines RSI, MACD, Volume, and Candlestick patterns',
    'GRID_TRADING': 'Automated grid-based trading strategy',
    'DCA': 'Dollar Cost Averaging for regular investments',
    'MANUAL': 'Full manual control without automated decisions'
}

def get_config():
    """Get configuration dictionary"""
    return {
        'telegram_bot_token': TELEGRAM_BOT_TOKEN,
        'allowed_users': ALLOWED_USERS,
        'pionex_api_key': PIONEX_API_KEY,
        'pionex_secret_key': PIONEX_SECRET_KEY,
        'pionex_base_url': PIONEX_BASE_URL,
        'default_leverage': DEFAULT_LEVERAGE,
        'default_margin_type': DEFAULT_MARGIN_TYPE,
        'max_position_size': MAX_POSITION_SIZE,
        'stop_loss_percentage': STOP_LOSS_PERCENTAGE,
        'take_profit_percentage': TAKE_PROFIT_PERCENTAGE,
        'trailing_stop_percentage': TRAILING_STOP_PERCENTAGE,
        'rsi_period': RSI_PERIOD,
        'rsi_overbought': RSI_OVERBOUGHT,
        'rsi_oversold': RSI_OVERSOLD,
        'rsi_5m_oversold': RSI_5M_OVERSOLD,
        'rsi_5m_overbought': RSI_5M_OVERBOUGHT,
        'rsi_1h_neutral': RSI_1H_NEUTRAL,
        'volume_ema_period': VOLUME_EMA_PERIOD,
        'volume_multiplier': VOLUME_MULTIPLIER,
        'macd_fast': MACD_FAST,
        'macd_slow': MACD_SLOW,
        'macd_signal': MACD_SIGNAL,
        'database_url': DATABASE_URL,
        'log_level': LOG_LEVEL,
        'log_file': LOG_FILE,
        'supported_pairs': SUPPORTED_PAIRS,
        'strategy_types': STRATEGY_TYPES,
        'strategy_descriptions': STRATEGY_DESCRIPTIONS,
        'trading_pair': 'BTC_USDT',
        'position_size': 0.5,
        'trading_amount': 100,
        'leverage': 10,
        'max_daily_loss': 500,
        'stop_loss_percentage': 1.5,
        'take_profit_percentage': 2.5,
        'trailing_stop_percentage': 1.0,
        'default_strategy': 'ADVANCED_STRATEGY',
        'trading_hours': {
            'enabled': False,
            'start': '19:30',
            'end': '01:30',
            'timezone': 'UTC-5',
            'exclude_weekends': False,
            'exclude_holidays': False
        },
        'rsi': {
            'period': 7,
            'overbought': 70,
            'oversold': 30
        },
        'volume_filter': {
            'ema_period': 20,
            'multiplier': 1.5
        },
        'notifications': {
            'telegram': {
                'enabled': False,
                'bot_token': TELEGRAM_BOT_TOKEN,
                'user_id': ''
            },
            'email': {
                'enabled': False,
                'recipient_email': '',
                'sender_email': '',
                'sender_password': '',
                'smtp_server': 'smtp.gmail.com'
            },
            'types': {
                'trade_notifications': True,
                'error_notifications': True,
                'balance_notifications': True,
                'status_notifications': True
            }
        }
    } 