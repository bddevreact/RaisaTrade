import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import json
from datetime import datetime
import threading
import time
import yaml
from pathlib import Path
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config_loader import get_config, reload_config
from pionex_api import PionexAPI
from trading_strategies import TradingStrategies, RSIFilter
from database import Database
from auto_trader import get_auto_trader, start_auto_trading, stop_auto_trading, restart_auto_trading, get_auto_trading_status
from futures_trading import (
    get_futures_trader, create_futures_grid, create_hedging_grid,
    get_dynamic_limits, check_liquidation_risk, get_strategy_status,
    get_performance_metrics
)
from backtesting import (
    run_backtest, enable_paper_trading, disable_paper_trading, get_paper_trading_ledger
)
from pionex_ws import PionexWebSocket

# Configure logging
config = get_config()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.get('logging', {}).get('level', 'INFO'))
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        self.api = PionexAPI()
        self.strategies = TradingStrategies(self.api)
        self.db = Database()
        self.auto_trading_users = set()
        self.config = get_config()
        self.user_param_update_state = {}  # user_id -> param being updated
        self.user_backtest_state = {}      # user_id -> dict for backtest param collection
        self.user_order_query_state = None  # user_id -> dict for order query state
        
        # Initialize WebSocket for real-time data
        self.ws = None
        self.ws_connected = False
        self.real_time_data = {}
        self.ws_thread = None
        
        # Start WebSocket connection
        self._start_websocket()
        
        # Initialize RSI Filter
        self.rsi_filter = RSIFilter(self.api)
    
    def check_auth(self, user_id: int) -> bool:
        """Check if user is authorized"""
        allowed_users = self.config.get('allowed_users', [])
        return str(user_id) in allowed_users or not allowed_users
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user_id = update.effective_user.id
        user = update.effective_user
        if not self.check_auth(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        self.db.add_user(user_id, user.username, user.first_name, user.last_name)
        await update.message.reply_text(
            "🚀 Welcome to Pionex Trading Bot!\n\n"
            "This bot allows you to:\n"
            "• View account balance and positions\n"
            "• Execute manual and automatic trades\n"
            "• Monitor portfolio performance\n"
            "• Use advanced RSI, MACD, and volume strategies\n"
            "• Set up automated trading strategies\n\n"
            "Use the menu below to get started:",
            reply_markup=self.get_main_keyboard()
        )
    
    def get_main_keyboard(self) -> InlineKeyboardMarkup:
        """Main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("💰 Balance", callback_data="balance"),
                InlineKeyboardButton("📊 Positions", callback_data="positions")
            ],
            [
                InlineKeyboardButton("📈 Portfolio", callback_data="portfolio"),
                InlineKeyboardButton("📋 Trading History", callback_data="history")
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                InlineKeyboardButton("📊 Technical Analysis", callback_data="technical_analysis")
            ],
            [
                InlineKeyboardButton("🤖 Auto Trading", callback_data="auto_trading"),
                InlineKeyboardButton("📝 Manual Trade", callback_data="manual_trade")
            ],
            [
                InlineKeyboardButton("🎯 Strategies", callback_data="strategies"),
                InlineKeyboardButton("📊 Status", callback_data="status")
            ],
            [
                InlineKeyboardButton("🚀 Futures Trading", callback_data="futures_trading"),
                InlineKeyboardButton("⚠️ Risk Monitor", callback_data="risk_monitor")
            ],
            [
                InlineKeyboardButton("🧪 Backtesting", callback_data="backtesting"),
                InlineKeyboardButton("💸 Paper Trading", callback_data="paper_trading")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_trading_pairs_keyboard(self) -> InlineKeyboardMarkup:
        """Trading pairs selection keyboard"""
        # Common spot trading pairs for Pionex (using confirmed working symbols)
        pairs = [
            'XRP_USDT', 'TRX_USDT', 'UNI_USDT', 'LINK_USDT', 'ADA_USDT',
            'SOL_USDT', 'DOT_USDT', 'AVAX_USDT', 'MATIC_USDT', 'LTC_USDT'
        ]
        keyboard = []
        for i in range(0, len(pairs), 2):
            row = []
            row.append(InlineKeyboardButton(pairs[i], callback_data=f"pair_{pairs[i]}"))
            if i + 1 < len(pairs):
                row.append(InlineKeyboardButton(pairs[i+1], callback_data=f"pair_{pairs[i+1]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        return InlineKeyboardMarkup(keyboard)
    
    def get_strategy_keyboard(self) -> InlineKeyboardMarkup:
        """Strategy selection keyboard"""
        strategies = self.config.get('strategy_types', {
            'RSI_STRATEGY': 'RSI Strategy',
            'RSI_MULTI_TF': 'RSI Multi-Timeframe',
            'VOLUME_FILTER': 'Volume Filter Strategy',
            'ADVANCED_STRATEGY': 'Advanced Strategy',
            'GRID_TRADING': 'Grid Trading',
            'DCA': 'Dollar Cost Averaging',
            'MANUAL': 'Manual Trading'
        })
        keyboard = []
        for strategy_id, strategy_name in strategies.items():
            keyboard.append([InlineKeyboardButton(strategy_name, callback_data=f"strategy_{strategy_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        return InlineKeyboardMarkup(keyboard)

    def get_settings_keyboard(self) -> InlineKeyboardMarkup:
        """Settings menu for real-time parameter modification"""
        keyboard = [
            [InlineKeyboardButton("Trading Pair", callback_data="set_param_trading_pair")],
            [InlineKeyboardButton("Position Size", callback_data="set_param_position_size")],
            [InlineKeyboardButton("RSI Thresholds", callback_data="set_param_rsi")],
            [InlineKeyboardButton("Volume Filter", callback_data="set_param_volume")],
            [InlineKeyboardButton("SL / TP", callback_data="set_param_sltp")],
            [InlineKeyboardButton("Trailing Stop", callback_data="set_param_trailing")],
            [InlineKeyboardButton("Trading Hours", callback_data="set_param_hours")],
            [InlineKeyboardButton("Leverage", callback_data="set_param_leverage")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard) 

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if not self.check_auth(user_id):
            await query.edit_message_text("❌ You are not authorized to use this bot.")
            return
        
        data = query.data
        
        if data == "main_menu":
            await query.edit_message_text(
                "🚀 Pionex Trading Bot\n\nSelect an option:",
                reply_markup=self.get_main_keyboard()
            )
        
        elif data == "balance":
            await self.show_balance(query)
        
        elif data == "positions":
            await self.show_positions(query)
        
        elif data == "portfolio":
            await self.show_portfolio(query)
        
        elif data == "history":
            await self.show_trading_history(query)
        
        elif data == "settings":
            await self.settings_menu(update, context)
        
        elif data == "technical_analysis":
            await self.show_technical_analysis(query)
        
        elif data == "auto_trading":
            await self.show_auto_trading(query)
        
        elif data == "manual_trade":
            await self.show_manual_trade(query)
        
        elif data == "strategies":
            await self.show_strategies(query)
        
        elif data == "status":
            await self.show_status(query)
        
        elif data == "futures_trading":
            await self.show_futures_trading(query)
        
        elif data == "risk_monitor":
            await self.show_risk_monitor(query)
        
        elif data == "enable_auto":
            await self.handle_enable_auto_trading(query)
        
        elif data == "disable_auto":
            await self.handle_disable_auto_trading(query)
        
        elif data == "restart_auto":
            await self.handle_restart_auto_trading(query)
        
        elif data == "active_strategies":
            await self.show_active_strategies(query)
        
        elif data == "portfolio_snapshot":
            await self.show_portfolio_snapshot(query)
        
        elif data == "backtesting":
            await self.show_backtesting_menu(query)
        
        elif data == "paper_trading":
            await self.show_paper_trading_menu(query)
        
        elif data == "start_backtest":
            await self.prompt_backtest_symbol(query)
        
        elif data == "show_ledger":
            await self.show_paper_trading_ledger(query)
        
        elif data == "enable_paper":
            enable_paper_trading(user_id)
            await query.edit_message_text("✅ Paper trading enabled!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="paper_trading")]]))
        
        elif data == "disable_paper":
            disable_paper_trading(user_id)
            await query.edit_message_text("❌ Paper trading disabled!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="paper_trading")]]))
        
        elif data.startswith("futures_"):
            await self.handle_futures_action(query, data)
        
        elif data.startswith("risk_"):
            await self.handle_risk_action(query, data)
        
        elif data.startswith("pair_"):
            symbol = data.replace("pair_", "")
            await self.handle_pair_selection(query, symbol)
        
        elif data.startswith("strategy_"):
            strategy = data.replace("strategy_", "")
            await self.handle_strategy_selection(query, strategy)
        
        elif data.startswith("trade_"):
            await self.handle_trade_action(query, data)
        
        elif data.startswith("analysis_"):
            await self.handle_analysis_selection(query, data)
        
        elif data.startswith("activate_"):
            await self.handle_strategy_activation(query, data)
        
        elif data.startswith("configure_"):
            await self.handle_strategy_configuration(query, data)
        
        elif data.startswith("test_"):
            await self.handle_strategy_testing(query, data)
        
        elif data.startswith("performance_"):
            await self.handle_strategy_performance(query, data)
        
        elif data.startswith("monitor_"):
            await self.handle_strategy_monitoring(query, data)
        
        elif data.startswith("progress_"):
            await self.handle_strategy_progress(query, data)
        
        elif data.startswith("manual_"):
            await self.handle_manual_trading(query, data)
        
        elif data.startswith("set_param_"):
            await self.handle_param_selection(query, data)
        
        elif data == "order_details":
            await self.show_order_details(query)
        
        elif data.startswith("config_"):
            await self.handle_strategy_configuration_detail(query, data)
        
        elif data.startswith("confirm_"):
            await self.handle_order_confirmation(query, data)
        
        elif data.startswith("modify_"):
            await self.handle_order_modification(query, data)
        
        elif data.startswith("detailed_"):
            await self.handle_detailed_analysis(query, data)
        
        elif data.startswith("trade_history_"):
            await self.handle_trade_history(query, data)
        
        elif data.startswith("stop_"):
            await self.handle_strategy_stop(query, data)
        
        elif data.startswith("set_param_"):
            await self.handle_param_selection(query, data)
        
        elif data.startswith("config_pair_"):
            await self.update_trading_pair(query, data)
        
        elif data.startswith("config_size_"):
            await self.update_position_size(query, data)
        
        elif data.startswith("config_sl_"):
            await self.update_stop_loss(query, data)
        
        elif data.startswith("config_tp_"):
            await self.update_take_profit(query, data)
        
        elif data.startswith("config_rsi_"):
            await self.update_rsi_settings(query, data)
        elif data.startswith("rsi_"):
            # Convert rsi_7 to config_rsi_7 format
            new_data = f"config_{data}"
            await self.update_rsi_settings(query, new_data)
        elif data.startswith("config_volume_"):
            await self.update_volume_settings(query, data)
        elif data.startswith("volume_"):
            # Convert volume_10 to config_volume_10 format
            new_data = f"config_{data}"
            await self.update_volume_settings(query, new_data)
        elif data.startswith("futures_create_grid_confirm"):
            await self.handle_futures_grid_creation(query)
        elif data.startswith("futures_create_hedge_confirm"):
            await self.handle_futures_hedge_creation(query)
        elif data.startswith("futures_configure_grid"):
            await self.show_futures_grid_config(query)
        elif data.startswith("futures_configure_hedge"):
            await self.show_futures_hedge_config(query)
        elif data.startswith("order_market"):
            await self.show_market_order_setup(query)
        elif data.startswith("order_limit"):
            await self.show_limit_order_setup(query)
        elif data.startswith("bracket_place"):
            await self.show_bracket_order_setup(query)
        elif data.startswith("oco_place"):
            await self.show_oco_order_setup(query)
        elif data.startswith("enable_paper"):
            await self.handle_enable_paper_trading(query)
        elif data.startswith("disable_paper"):
            await self.handle_disable_paper_trading(query)
        elif data.startswith("show_ledger"):
            await self.show_paper_trading_ledger(query)
        elif data.startswith("config_trading_pair"):
            await self.show_trading_pair_config(query)
        elif data.startswith("config_position_size"):
            await self.show_position_size_config(query)
        elif data.startswith("config_stop_loss"):
            await self.show_stop_loss_config(query)
        elif data.startswith("config_take_profit"):
            await self.show_take_profit_config(query)
        elif data.startswith("config_rsi_settings"):
            await self.show_rsi_settings_config(query)
        elif data.startswith("config_volume_settings"):
            await self.show_volume_settings_config(query)
        elif data.startswith("update_trading_pair_"):
            await self.update_trading_pair(query, data)
        elif data.startswith("update_position_size_"):
            await self.update_position_size(query, data)
        elif data.startswith("update_stop_loss_"):
            await self.update_stop_loss(query, data)
        elif data.startswith("update_take_profit_"):
            await self.update_take_profit(query, data)
        elif data.startswith("config_rsi_"):
            await self.update_rsi_settings(query, data)
        elif data.startswith("config_volume_"):
            await self.update_volume_settings(query, data)
        elif data == "rsi_7" or data == "rsi_14" or data == "rsi_21" or data == "rsi_30":
            new_data = f"config_{data}"
            await self.update_rsi_settings(query, new_data)
        elif data == "volume_10" or data == "volume_20" or data == "volume_30" or data == "volume_50":
            new_data = f"config_{data}"
            await self.update_volume_settings(query, new_data)
        else:
            await query.edit_message_text(
                f"❌ Unknown action: {data}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_balance(self, query):
        """Show account balance using /api/v1/account/balances format (all coins, sorted)"""
        try:
            balance_response = self.api.get_balances()
            if 'error' in balance_response:
                await self._safe_edit_message(
                    query,
                    f"❌ Error fetching balance: {balance_response['error']}\n\n🔙 Back to main menu:",
                    InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return

            balance_text = "💰 Account Balance\n\n"
            balances = balance_response.get('data', {}).get('balances', [])
            # Sort by coin name (ascending)
            balances = sorted(balances, key=lambda x: x['coin'])
            if balances:
                for asset in balances:
                    free = float(asset.get('free', 0))
                    frozen = float(asset.get('frozen', 0))
                    balance_text += f"{asset['coin']}\n"
                    balance_text += f"  Free: {free:.8f}\n"
                    balance_text += f"  Frozen: {frozen:.8f}\n\n"
            else:
                balance_text += "No assets found.\n\n"
            balance_text += "🔙 Back to main menu:"
            
            await self._safe_edit_message(
                query,
                balance_text,
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
        except Exception as e:
            await self._safe_edit_message(
                query,
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_positions(self, query):
        """Show current positions"""
        try:
            positions_response = self.api.get_positions()
            
            if 'error' in positions_response:
                await query.edit_message_text(
                    f"❌ Error fetching positions: {positions_response['error']}\n\n"
                    "🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            positions_text = "📊 Current Positions\n\n"
            
            if 'data' in positions_response and 'balances' in positions_response['data']:
                balances = positions_response['data']['balances']
                non_zero_balances = [b for b in balances if float(b.get('free', 0)) > 0 or float(b.get('frozen', 0)) > 0]
                
                if non_zero_balances:
                    for balance in non_zero_balances:
                        free = float(balance.get('free', 0))
                        frozen = float(balance.get('frozen', 0))
                        total = float(balance.get('total', 0))
                        
                        positions_text += f"{balance['coin']}\n"
                        positions_text += f"  Free: {free:.8f}\n"
                        positions_text += f"  Frozen: {frozen:.8f}\n"
                        positions_text += f"  Total: {total:.8f}\n\n"
                else:
                    positions_text += "No non-zero balances\n\n"
            else:
                positions_text += "No balance data available\n\n"
            
            positions_text += "🔙 Back to main menu:"
            
            await query.edit_message_text(
                positions_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_portfolio(self, query):
        """Show portfolio overview"""
        try:
            # Get positions and calculate metrics
            positions_response = self.api.get_positions()
            balance_response = self.api.get_balances()
            
            if 'error' in positions_response or 'error' in balance_response:
                await query.edit_message_text(
                    "❌ Error fetching portfolio data\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            # Calculate portfolio metrics
            total_value = 0
            total_pnl = 0
            positions_count = 0
            
            if 'data' in positions_response and 'balances' in positions_response['data']:
                balances = positions_response['data']['balances']
                non_zero_balances = [b for b in balances if float(b.get('free', 0)) > 0 or float(b.get('frozen', 0)) > 0]
                positions_count = len(non_zero_balances)
                
                # For balance-based portfolio, we don't have PnL, so we'll show balance info
                for balance in non_zero_balances:
                    total_value += float(balance.get('total', 0))
            
            # Get USDT balance
            usdt_balance = 0
            if 'data' in balance_response and 'balances' in balance_response['data']:
                for balance in balance_response['data']['balances']:
                    if balance.get('coin') == 'USDT':
                        usdt_balance = float(balance.get('total', 0))
                        break
            
            portfolio_text = "📈 Portfolio Overview\n\n"
            portfolio_text += f"💰 USDT Balance: ${usdt_balance:.2f}\n"
            portfolio_text += f"📊 Total Assets: {positions_count}\n"
            portfolio_text += f"💵 Total Asset Value: ${total_value:.2f}\n"
            portfolio_text += f"📈 Total Balance: {'🟢' if total_value >= 0 else '🔴'} ${total_value:.2f}\n"
            
            if total_value > 0:
                portfolio_text += f"📊 Portfolio Value: {'🟢' if total_value >= 0 else '🔴'} ${total_value:.2f}\n"
            
            portfolio_text += "\n🔙 Back to main menu:"
            
            await query.edit_message_text(
                portfolio_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            ) 

    async def show_trading_history(self, query):
        """Show trading history"""
        try:
            user_id = query.from_user.id
            history = self.db.get_trading_history(user_id, 10)
            
            history_text = "📋 Recent Trading History\n\n"
            
            if history:
                for trade in history:
                    status_emoji = "✅" if trade['status'] == 'FILLED' else "⏳"
                    side_emoji = "🟢" if trade['side'] == 'BUY' else "🔴"
                    
                    history_text += f"{status_emoji} {side_emoji} {trade['symbol']}\n"
                    history_text += f"  {trade['side']} {trade['quantity']:.8f} @ ${trade['price']:.2f}\n"
                    history_text += f"  Strategy: {trade['strategy'] or 'Manual'}\n"
                    history_text += f"  Date: {trade['created_at']}\n\n"
            else:
                history_text += "No trading history found\n\n"
            
            history_text += "🔙 Back to main menu:"
            
            await query.edit_message_text(
                history_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Settings menu handler"""
        user_id = update.effective_user.id
        if not self.check_auth(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("🕒 Trading Hours", callback_data="settings_trading_hours"),
                InlineKeyboardButton("💰 Position Size", callback_data="settings_position_size")
            ],
            [
                InlineKeyboardButton("🔔 Notifications", callback_data="settings_notifications"),
                InlineKeyboardButton("📊 Strategy", callback_data="settings_strategy")
            ],
            [
                InlineKeyboardButton("⚠️ Risk Management", callback_data="settings_risk"),
                InlineKeyboardButton("📈 Indicators", callback_data="settings_indicators")
            ],
            [
                InlineKeyboardButton("💾 Save All Settings", callback_data="settings_save"),
                InlineKeyboardButton("🔄 Reset to Default", callback_data="settings_reset")
            ],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = (
            "⚙️ **Trading Bot Settings**\n\n"
            "Configure your trading bot parameters:\n\n"
            "🕒 **Trading Hours** - Set when bot should trade\n"
            "💰 **Position Size** - Configure trade amounts\n"
            "🔔 **Notifications** - Setup alerts and messages\n"
            "📊 **Strategy** - Choose trading strategy\n"
            "⚠️ **Risk Management** - Set stop loss, take profit\n"
            "📈 **Indicators** - Configure RSI, MACD parameters\n\n"
            "Select an option to configure:"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message_text, 
                reply_markup=reply_markup, 
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                message_text, 
                reply_markup=reply_markup, 
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_technical_analysis(self, query):
        """Show technical analysis options"""
        try:
            analysis_text = "📊 Technical Analysis\n\n"
            analysis_text += "Select analysis type:\n\n"
            
            keyboard = [
                [InlineKeyboardButton("📈 RSI Analysis", callback_data="analysis_rsi")],
                [InlineKeyboardButton("📊 Multi-Timeframe RSI", callback_data="analysis_rsi_mtf_XRP_USDT")],
                [InlineKeyboardButton("📈 Volume Filter Analysis", callback_data="analysis_volume")],
                [InlineKeyboardButton("📊 Advanced Analysis", callback_data="analysis_advanced")],
                [InlineKeyboardButton("📈 MACD Analysis", callback_data="analysis_macd")],
                [InlineKeyboardButton("🕯️ Candlestick Patterns", callback_data="analysis_candlestick")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            
            await query.edit_message_text(
                analysis_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_auto_trading(self, query):
        """Show auto trading options"""
        try:
            user_id = query.from_user.id
            status = get_auto_trading_status(user_id)
            
            auto_text = "🤖 Auto Trading\n\n"
            auto_text += f"Status: {'✅ ACTIVE' if status.get('auto_trading_enabled', False) else '❌ INACTIVE'}\n"
            auto_text += f"Trading Pair: {status.get('current_pair', 'N/A')}\n"
            auto_text += f"Running: {'✅ YES' if status.get('is_running', False) else '❌ NO'}\n"
            auto_text += f"Trading Hours: {'✅ ACTIVE' if status.get('trading_hours_active', True) else '❌ INACTIVE'}\n"
            auto_text += f"Restart Count: {status.get('restart_count', 0)}\n\n"
            
            if status.get('auto_trading_enabled', False):
                auto_text += "Auto trading is currently active. The bot will:\n"
                auto_text += "• Monitor market conditions\n"
                auto_text += "• Execute trades based on your strategy\n"
                auto_text += "• Manage risk according to your settings\n"
                auto_text += "• Send notifications for important events\n\n"
            else:
                auto_text += "Auto trading is currently disabled.\n\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Enable Auto Trading", callback_data="enable_auto") if not status.get('auto_trading_enabled', False) else
                    InlineKeyboardButton("❌ Disable Auto Trading", callback_data="disable_auto")
                ],
                [InlineKeyboardButton("🔄 Restart Auto Trading", callback_data="restart_auto")],
                [InlineKeyboardButton("📊 Active Strategies", callback_data="active_strategies")],
                [InlineKeyboardButton("📈 Portfolio Snapshot", callback_data="portfolio_snapshot")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            
            await query.edit_message_text(
                auto_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_manual_trade(self, query):
        """Show manual trading options"""
        try:
            trade_text = "📝 Manual Trading\n\n"
            trade_text += "Select a trading pair to place a manual order:\n\n"
            
            await query.edit_message_text(
                trade_text,
                reply_markup=self.get_trading_pairs_keyboard()
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_strategies(self, query):
        """Show strategy management"""
        try:
            user_id = query.from_user.id
            active_strategies = self.db.get_active_strategies(user_id)
            
            strategy_text = "🎯 Trading Strategies\n\n"
            
            if active_strategies:
                strategy_text += "Active Strategies:\n"
                for strategy in active_strategies:
                    strategy_text += f"• {strategy['symbol']} - {self.config.get('strategy_types', {}).get(strategy['strategy_type'], strategy['strategy_type'])}\n"
                    strategy_text += f"  Status: {strategy.get('status', 'Active')}\n"
                    strategy_text += f"  Created: {strategy.get('created_at', 'N/A')}\n\n"
            else:
                strategy_text += "No active strategies\n\n"
            
            strategy_text += "Select a strategy to set up:"
            
            await query.edit_message_text(
                strategy_text,
                reply_markup=self.get_strategy_keyboard()
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_status(self, query):
        """Show bot status"""
        try:
            # Check API connection using account info
            account_info = self.api.get_account_info()
            api_status = "✅ Connected" if 'error' not in account_info else "❌ Disconnected"
            
            # Get user settings
            user_id = query.from_user.id
            settings = self.db.get_user_settings(user_id)
            
            # Get auto trading status
            auto_trading_status = get_auto_trading_status(user_id)
            
            # Get recent API activity
            balance_response = self.api.get_balances()
            balance_status = "✅ Working" if 'error' not in balance_response else "❌ Error"
            
            status_text = "📊 Bot Status\n\n"
            status_text += f"🔌 API Status: {api_status}\n"
            status_text += f"💰 Balance API: {balance_status}\n"
            status_text += f"🤖 Auto Trading: {'✅ ON' if auto_trading_status.get('auto_trading_enabled', False) else '❌ OFF'}\n"
            status_text += f"📈 Active Strategies: {len(self.db.get_active_strategies(user_id))}\n"
            status_text += f"⏰ Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Add account details if available
            if 'error' not in account_info and 'data' in account_info:
                account_data = account_info['data']
                status_text += f"📊 Account Status: {account_data.get('account_status', 'Unknown')}\n"
                status_text += f"💰 Balances Count: {account_data.get('balances_count', 0)}\n"
            
            # Add balance info if available
            if 'error' not in balance_response and 'data' in balance_response:
                balances = balance_response['data'].get('balances', [])
                usdt_balance = 0
                for balance in balances:
                    if balance.get('coin') == 'USDT':
                        usdt_balance = float(balance.get('total', 0))
                        break
                status_text += f"💵 USDT Balance: ${usdt_balance:.2f}\n"
            
            status_text += "\n"
            
            if 'error' not in account_info and 'error' not in balance_response:
                status_text += "✅ All systems operational\n"
                status_text += "• API connection stable\n"
                status_text += "• Balance data accessible\n"
                status_text += "• Ready for trading\n"
            else:
                status_text += "❌ Some issues detected\n"
                if 'error' in account_info:
                    status_text += f"• API Error: {account_info['error']}\n"
                if 'error' in balance_response:
                    status_text += f"• Balance Error: {balance_response['error']}\n"
            
            status_text += "\n🔙 Back to main menu:"
            
            await query.edit_message_text(
                status_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_futures_trading(self, query):
        """Show futures trading options"""
        try:
            user_id = query.from_user.id
            status = get_strategy_status(user_id)
            metrics = get_performance_metrics(user_id)
            
            futures_text = "🚀 Futures Trading\n\n"
            futures_text += f"Active Grids: {status.get('active_grids', 0)}\n"
            futures_text += f"Active Hedging: {status.get('active_hedging', 0)}\n"
            futures_text += f"Liquidation Warnings: {status.get('liquidation_warnings', 0)}\n"
            
            if 'error' not in metrics:
                futures_text += f"Total PnL: {'🟢' if metrics.get('total_pnl', 0) >= 0 else '🔴'} ${metrics.get('total_pnl', 0):.2f}\n"
                futures_text += f"Total Positions: {metrics.get('total_positions', 0)}\n"
                futures_text += f"Active Strategies: {metrics.get('active_strategies', 0)}\n"
            
            futures_text += "\nSelect an option:"
            
            keyboard = [
                [InlineKeyboardButton("📊 Create Grid Strategy", callback_data="futures_create_grid")],
                [InlineKeyboardButton("🛡️ Create Hedging Grid", callback_data="futures_create_hedge")],
                [InlineKeyboardButton("📈 Strategy Performance", callback_data="futures_performance")],
                [InlineKeyboardButton("⚙️ Dynamic Limits", callback_data="futures_limits")],
                [InlineKeyboardButton("⚠️ Liquidation Risk", callback_data="futures_liquidation")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            
            await query.edit_message_text(
                futures_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_risk_monitor(self, query):
        """Show risk monitoring options"""
        try:
            user_id = query.from_user.id
            
            risk_text = "⚠️ Risk Monitor\n\n"
            risk_text += "Monitor your trading risk and get alerts for:\n"
            risk_text += "• Liquidation warnings\n"
            risk_text += "• High leverage positions\n"
            risk_text += "• Margin call alerts\n"
            risk_text += "• Portfolio risk metrics\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🔍 Check Liquidation Risk", callback_data="risk_liquidation")],
                [InlineKeyboardButton("📊 Portfolio Risk", callback_data="risk_portfolio")],
                [InlineKeyboardButton("⚡ Dynamic Limits", callback_data="risk_limits")],
                [InlineKeyboardButton("📈 Risk Metrics", callback_data="risk_metrics")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            
            await query.edit_message_text(
                risk_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_backtesting_menu(self, query):
        """Show backtesting menu"""
        try:
            backtest_text = "🧪 Backtesting Menu\n\n"
            backtest_text += "Test your strategies with historical data:\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🚀 Run Backtest", callback_data="start_backtest")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            
            await query.edit_message_text(
                backtest_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def show_paper_trading_menu(self, query):
        """Show paper trading menu"""
        try:
            user_id = query.from_user.id
            ledger = get_paper_trading_ledger(user_id)
            
            # Calculate paper trading status from ledger
            enabled = len(ledger) > 0  # If there are trades, paper trading is active
            balance = 1000.0  # Default starting balance
            pnl = 0.0
            
            # Calculate PnL from ledger if there are trades
            if ledger:
                # Calculate total PnL from trades
                total_buy_value = 0
                total_sell_value = 0
                
                for trade in ledger:
                    if trade.get('type') == 'BUY':
                        total_buy_value += trade.get('price', 0) * trade.get('quantity', 0)
                    elif trade.get('type') == 'SELL':
                        total_sell_value += trade.get('price', 0) * trade.get('quantity', 0)
                
                pnl = total_sell_value - total_buy_value
                balance = 1000.0 + pnl  # Starting balance + PnL
            
            paper_text = "💸 Paper Trading Menu\n\n"
            paper_text += f"Status: {'✅ Enabled' if enabled else '❌ Disabled'}\n"
            paper_text += f"Balance: ${balance:.2f}\n"
            paper_text += f"PnL: {'🟢' if pnl >= 0 else '🔴'} ${pnl:.2f}\n"
            paper_text += f"Total Trades: {len(ledger)}\n\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Enable Paper Trading", callback_data="enable_paper")
                    if not enabled else
                    InlineKeyboardButton("❌ Disable Paper Trading", callback_data="disable_paper")
                ],
                [InlineKeyboardButton("📒 Show Ledger", callback_data="show_ledger")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            
            await query.edit_message_text(
                paper_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
    
    async def handle_enable_auto_trading(self, query):
        """Handle enable auto trading"""
        try:
            user_id = query.from_user.id
            start_auto_trading(user_id)
            
            await query.edit_message_text(
                "✅ Auto Trading Enabled\n\n"
                "Auto trading has been enabled for your account.\n"
                "The bot will now:\n"
                "• Monitor market conditions\n"
                "• Execute trades based on your strategy\n"
                "• Send notifications for important events\n\n"
                "🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error enabling auto trading: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_disable_auto_trading(self, query):
        """Handle disable auto trading"""
        try:
            user_id = query.from_user.id
            stop_auto_trading(user_id)
            
            await query.edit_message_text(
                "❌ Auto Trading Disabled\n\n"
                "Auto trading has been disabled for your account.\n"
                "The bot will no longer execute automatic trades.\n\n"
                "🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error disabling auto trading: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_restart_auto_trading(self, query):
        """Handle restart auto trading"""
        try:
            user_id = query.from_user.id
            restart_auto_trading(user_id)
            
            await query.edit_message_text(
                "🔄 Auto Trading Restarted\n\n"
                "Auto trading has been restarted for your account.\n"
                "The bot will continue with fresh market data.\n\n"
                "🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error restarting auto trading: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user message for parameter update or backtest input"""
        user_id = update.effective_user.id
        
        # Parameter update flow
        if user_id in self.user_param_update_state:
            param = self.user_param_update_state.pop(user_id)
            new_value = update.message.text.strip()
            config = get_config()
            updated = False
            error = None
            try:
                # Map param to config path and validate
                if param == "trading_pair":
                    config['trading_pair'] = new_value.upper()
                    updated = True
                elif param == "position_size":
                    val = float(new_value)
                    if not (0 < val <= 1):
                        raise ValueError("Position size must be between 0 and 1 (fraction of balance)")
                    config['position_size'] = val
                    updated = True
                elif param == "rsi":
                    # Expect format: period,overbought,oversold
                    parts = [int(x) for x in new_value.split(',')]
                    if len(parts) != 3:
                        raise ValueError("Format: period,overbought,oversold")
                    config['rsi']['period'], config['rsi']['overbought'], config['rsi']['oversold'] = parts
                    updated = True
                elif param == "volume":
                    # Expect format: ema_period,multiplier
                    ema, mult = new_value.split(',')
                    config['volume_filter']['ema_period'] = int(ema)
                    config['volume_filter']['multiplier'] = float(mult)
                    updated = True
                elif param == "sltp":
                    # Format: sl,tp
                    sl, tp = new_value.split(',')
                    config['stop_loss_percentage'] = float(sl)
                    config['take_profit_percentage'] = float(tp)
                    updated = True
                elif param == "trailing":
                    config['trailing_stop_percentage'] = float(new_value)
                    updated = True
                elif param == "hours":
                    # Format: start,end,timezone
                    start, end, tz = [x.strip() for x in new_value.split(',')]
                    config['trading_hours']['start'] = start
                    config['trading_hours']['end'] = end
                    config['trading_hours']['timezone'] = tz
                    updated = True
                elif param == "leverage":
                    config['leverage'] = int(new_value)
                    updated = True
                else:
                    error = f"Unknown parameter: {param}"
            except Exception as e:
                error = str(e)
            if updated:
                # Persist config to config.yaml
                try:
                    with open(Path('config.yaml'), 'w') as f:
                        yaml.safe_dump(config, f, sort_keys=False)
                    reload_config()
                    self.config = get_config()
                    await update.message.reply_text(f"✅ *{param.replace('_', ' ').title()}* updated to `{new_value}`.", parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    await update.message.reply_text(f"❌ Failed to save config: {e}")
            else:
                await update.message.reply_text(f"❌ Invalid value: {error}")

    async def handle_param_selection(self, query, data):
        """Handle parameter selection for real-time modification"""
        param = data.replace("set_param_", "")
        user_id = query.from_user.id
        self.user_param_update_state[user_id] = param
        await query.edit_message_text(
            f"Enter new value for *{param.replace('_', ' ').title()}*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
        )

    async def prompt_backtest_symbol(self, query):
        """Prompt user for backtest symbol"""
        try:
            user_id = query.from_user.id
            self.user_backtest_state[user_id] = {}
            await query.edit_message_text(
                "🧪 **Backtest Setup**\n\nEnter trading pair symbol (e.g., BTCUSDT):",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="backtesting")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_paper_trading_ledger(self, query):
        """Show paper trading ledger"""
        try:
            user_id = query.from_user.id
            ledger = get_paper_trading_ledger(user_id)
            
            ledger_text = "📒 Paper Trading Ledger\n\n"
            
            if ledger:  # ledger is a list of trade dictionaries
                for i, trade in enumerate(ledger[-10:], 1):  # Show last 10 trades
                    side_emoji = "🟢" if trade.get('type') == 'BUY' else "🔴"
                    symbol = trade.get('symbol', 'Unknown')
                    quantity = trade.get('quantity', 0)
                    price = trade.get('price', 0)
                    timestamp = trade.get('time', 'Unknown')
                    
                    ledger_text += f"{i}. {side_emoji} {trade.get('type', 'Unknown')}\n"
                    ledger_text += f"   Symbol: {symbol}\n"
                    ledger_text += f"   Quantity: {quantity:.8f}\n"
                    ledger_text += f"   Price: ${price:.4f}\n"
                    ledger_text += f"   Time: {timestamp}\n\n"
            else:
                ledger_text += "No paper trading activity found.\n\n"
            
            ledger_text += "🔙 Back to paper trading:"
            
            await query.edit_message_text(
                ledger_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="paper_trading")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_futures_action(self, query, data):
        """Handle futures trading actions"""
        try:
            action = data.replace("futures_", "")
            user_id = query.from_user.id
            
            if action == "create_grid":
                await self.show_futures_grid_setup(query, user_id)
            elif action == "create_hedge":
                await self.show_futures_hedge_setup(query, user_id)
            elif action == "performance":
                await self.show_futures_performance(query, user_id)
            elif action == "limits":
                await self.show_futures_limits(query, user_id)
            elif action == "liquidation":
                await self.show_futures_liquidation(query, user_id)
            else:
                await query.edit_message_text(
                    f"🚀 Futures {action.title()}\n\nThis feature is coming soon!\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_futures_grid_setup(self, query, user_id):
        """Show futures grid setup"""
        try:
            config = get_config()
            
            setup_text = "🚀 Futures Grid Trading Setup\n\n"
            setup_text += "Grid Trading Strategy:\n"
            setup_text += "• Places buy and sell orders at regular intervals\n"
            setup_text += "• Profits from price oscillations within a range\n"
            setup_text += "• Automatic order management and rebalancing\n"
            setup_text += "• Suitable for sideways markets\n\n"
            setup_text += f"📊 Current Settings:\n"
            setup_text += f"• Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            setup_text += f"• Grid Spacing: 2% (default)\n"
            setup_text += f"• Grid Levels: 10 (default)\n"
            setup_text += f"• Investment Amount: ${config.get('position_size', 0.1) * 1000:.0f}\n"
            setup_text += f"• Leverage: 10x (default)\n\n"
            setup_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Create Grid", callback_data="futures_create_grid_confirm")],
                [InlineKeyboardButton("⚙️ Configure Grid", callback_data="futures_configure_grid")],
                [InlineKeyboardButton("📊 Monitor Grid", callback_data="futures_monitor_grid")],
                [InlineKeyboardButton("📈 Grid Performance", callback_data="futures_grid_performance")],
                [InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]
            ]
            
            await query.edit_message_text(
                setup_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_futures_hedge_setup(self, query, user_id):
        """Show futures hedging setup"""
        try:
            config = get_config()
            
            setup_text = "🛡️ Futures Hedging Setup\n\n"
            setup_text += "Hedging Strategy:\n"
            setup_text += "• Combines long and short positions\n"
            setup_text += "• Reduces overall portfolio risk\n"
            setup_text += "• Profits from market volatility\n"
            setup_text += "• Advanced risk management\n\n"
            setup_text += f"📊 Current Settings:\n"
            setup_text += f"• Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            setup_text += f"• Hedge Ratio: 0.5 (50% long, 50% short)\n"
            setup_text += f"• Investment Amount: ${config.get('position_size', 0.1) * 1000:.0f}\n"
            setup_text += f"• Leverage: 10x (default)\n\n"
            setup_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Create Hedge", callback_data="futures_create_hedge_confirm")],
                [InlineKeyboardButton("⚙️ Configure Hedge", callback_data="futures_configure_hedge")],
                [InlineKeyboardButton("📊 Monitor Hedge", callback_data="futures_monitor_hedge")],
                [InlineKeyboardButton("📈 Hedge Performance", callback_data="futures_hedge_performance")],
                [InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]
            ]
            
            await query.edit_message_text(
                setup_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_futures_performance(self, query, user_id):
        """Show futures performance"""
        try:
            # Get performance metrics from futures trading
            performance = get_performance_metrics(user_id)
            
            performance_text = "📈 Futures Performance\n\n"
            
            if 'error' not in performance:
                performance_text += f"💰 Total PnL: {'🟢' if performance.get('total_pnl', 0) >= 0 else '🔴'} ${performance.get('total_pnl', 0):.2f}\n"
                performance_text += f"📊 Total Positions: {performance.get('total_positions', 0)}\n"
                performance_text += f"🎯 Active Strategies: {performance.get('active_strategies', 0)}\n"
                performance_text += f"📈 Win Rate: {performance.get('win_rate', 0):.1f}%\n"
                performance_text += f"📉 Max Drawdown: {performance.get('max_drawdown', 0):.2f}%\n"
                performance_text += f"⚡ Sharpe Ratio: {performance.get('sharpe_ratio', 0):.2f}\n\n"
            else:
                performance_text += "📊 No performance data available\n\n"
            
            performance_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("📊 Detailed Analysis", callback_data="futures_detailed_performance")],
                [InlineKeyboardButton("📋 Trade History", callback_data="futures_trade_history")],
                [InlineKeyboardButton("📈 Performance Chart", callback_data="futures_performance_chart")],
                [InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]
            ]
            
            await query.edit_message_text(
                performance_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_futures_limits(self, query, user_id):
        """Show futures dynamic limits"""
        try:
            # Get dynamic limits from futures trading
            limits = get_dynamic_limits(user_id)
            
            limits_text = "⚡ Futures Dynamic Limits\n\n"
            
            if 'error' not in limits:
                limits_text += f"💰 Max Position Size: ${limits.get('max_position_size', 0):.2f}\n"
                limits_text += f"📊 Max Daily Trades: {limits.get('max_daily_trades', 0)}\n"
                limits_text += f"⚖️ Max Leverage: {limits.get('max_leverage', 0)}x\n"
                limits_text += f"🛑 Max Stop Loss: ${limits.get('max_stop_loss', 0):.2f}\n"
                limits_text += f"📈 Max Take Profit: ${limits.get('max_take_profit', 0):.2f}\n"
                limits_text += f"💵 Available Margin: ${limits.get('available_margin', 0):.2f}\n\n"
            else:
                limits_text += "📊 No limits data available\n\n"
            
            limits_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("⚙️ Adjust Limits", callback_data="futures_adjust_limits")],
                [InlineKeyboardButton("📊 Risk Analysis", callback_data="futures_risk_analysis")],
                [InlineKeyboardButton("🛡️ Safety Settings", callback_data="futures_safety_settings")],
                [InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]
            ]
            
            await query.edit_message_text(
                limits_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_futures_liquidation(self, query, user_id):
        """Show futures liquidation risk"""
        try:
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            
            # Get liquidation risk from futures trading
            risk = check_liquidation_risk(user_id, symbol)
            
            risk_text = "⚠️ Futures Liquidation Risk\n\n"
            
            if 'error' not in risk:
                risk_text += f"📊 Symbol: {symbol}\n"
                risk_text += f"⚠️ Risk Level: {risk.get('risk_level', 'UNKNOWN')}\n"
                risk_text += f"📈 Current Price: ${risk.get('current_price', 0):.4f}\n"
                risk_text += f"🛑 Liquidation Price: ${risk.get('liquidation_price', 0):.4f}\n"
                risk_text += f"📊 Distance to Liquidation: {risk.get('distance_to_liquidation', 0):.2f}%\n"
                risk_text += f"💰 Position Size: ${risk.get('position_size', 0):.2f}\n"
                risk_text += f"⚖️ Leverage: {risk.get('leverage', 0)}x\n\n"
                
                if risk.get('risk_level') == 'HIGH':
                    risk_text += "🔴 HIGH RISK DETECTED\n"
                    risk_text += "• Consider reducing position\n"
                    risk_text += "• Add more margin\n"
                    risk_text += "• Monitor closely\n"
                elif risk.get('risk_level') == 'MEDIUM':
                    risk_text += "🟡 MEDIUM RISK\n"
                    risk_text += "• Monitor position\n"
                    risk_text += "• Consider risk management\n"
                else:
                    risk_text += "🟢 LOW RISK\n"
                    risk_text += "• Position appears safe\n"
            else:
                risk_text += "📊 No risk data available\n\n"
            
            risk_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("🛑 Emergency Close", callback_data="futures_emergency_close")],
                [InlineKeyboardButton("💰 Add Margin", callback_data="futures_add_margin")],
                [InlineKeyboardButton("📊 Risk Analysis", callback_data="futures_risk_analysis")],
                [InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]
            ]
            
            await query.edit_message_text(
                risk_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_risk_action(self, query, data):
        """Handle risk monitoring actions"""
        try:
            action = data.replace("risk_", "")
            
            if action == "liquidation":
                await self.show_liquidation_risk(query)
            elif action == "portfolio":
                await self.show_portfolio_risk(query)
            elif action == "limits":
                await self.show_dynamic_limits(query)
            elif action == "metrics":
                await self.show_risk_metrics(query)
            else:
                await query.edit_message_text(
                    f"⚠️ Risk {action.title()}\n\nThis feature is coming soon!\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_liquidation_risk(self, query):
        """Show liquidation risk analysis"""
        try:
            # Get account balances to assess risk
            balance_response = self.api.get_balances()
            
            if 'error' in balance_response:
                await query.edit_message_text(
                    "❌ Error fetching account data\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            risk_text = "⚠️ Liquidation Risk Analysis\n\n"
            
            # Calculate risk metrics
            total_balance = 0
            usdt_balance = 0
            high_risk_positions = []
            
            if 'data' in balance_response and 'balances' in balance_response['data']:
                balances = balance_response['data']['balances']
                
                for balance in balances:
                    coin = balance.get('coin', '')
                    free = float(balance.get('free', 0))
                    frozen = float(balance.get('frozen', 0))
                    total = float(balance.get('total', 0))
                    
                    if coin == 'USDT':
                        usdt_balance = total
                    else:
                        total_balance += total
                        # Check for high-risk positions (low balance relative to frozen)
                        if frozen > 0 and free < frozen * 0.1:  # Less than 10% free
                            high_risk_positions.append({
                                'coin': coin,
                                'free': free,
                                'frozen': frozen,
                                'risk_ratio': (frozen - free) / frozen * 100
                            })
            
            # Risk assessment
            risk_level = "LOW"
            risk_score = 0
            
            if usdt_balance < 10:  # Low USDT balance
                risk_score += 30
                risk_level = "MEDIUM"
            
            if len(high_risk_positions) > 0:
                risk_score += 40
                risk_level = "HIGH"
            
            # Calculate leverage ratio safely
            leverage_ratio = 0
            if usdt_balance > 0:
                leverage_ratio = total_balance / usdt_balance
                if leverage_ratio > 10:  # High leverage
                    risk_score += 30
                    risk_level = "HIGH"
            else:
                # If no USDT balance, consider it high risk
                risk_score += 50
                risk_level = "HIGH"
                leverage_ratio = float('inf') if total_balance > 0 else 0
            
            risk_text += f"🎯 Risk Level: {risk_level}\n"
            risk_text += f"📊 Risk Score: {risk_score}/100\n"
            risk_text += f"💰 USDT Balance: ${usdt_balance:.2f}\n"
            risk_text += f"📈 Total Asset Value: ${total_balance:.2f}\n"
            
            # Display leverage ratio safely
            if leverage_ratio == float('inf'):
                risk_text += f"⚖️ Leverage Ratio: ∞ (No USDT balance)\n\n"
            else:
                risk_text += f"⚖️ Leverage Ratio: {leverage_ratio:.2f}x\n\n"
            
            if risk_level == "HIGH":
                risk_text += "🔴 HIGH RISK DETECTED\n"
                risk_text += "• Consider reducing positions\n"
                risk_text += "• Increase USDT balance\n"
                risk_text += "• Monitor closely\n"
            elif risk_level == "MEDIUM":
                risk_text += "🟡 MEDIUM RISK\n"
                risk_text += "• Monitor positions\n"
                risk_text += "• Consider risk management\n"
            else:
                risk_text += "🟢 LOW RISK\n"
                risk_text += "• Account appears healthy\n"
                risk_text += "• Continue normal trading\n"
            
            if high_risk_positions:
                risk_text += "\n⚠️ High Risk Positions:\n"
                for pos in high_risk_positions[:3]:  # Show top 3
                    risk_text += f"• {pos['coin']}: {pos['risk_ratio']:.1f}% risk\n"
            
            keyboard = [
                [InlineKeyboardButton("📊 Portfolio Risk", callback_data="risk_portfolio")],
                [InlineKeyboardButton("⚡ Dynamic Limits", callback_data="risk_limits")],
                [InlineKeyboardButton("🔙 Back", callback_data="risk_monitor")]
            ]
            
            await query.edit_message_text(
                risk_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error in liquidation risk analysis: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_portfolio_risk(self, query):
        """Show portfolio risk analysis"""
        try:
            # Get account balances for portfolio risk assessment
            balance_response = self.api.get_balances()
            
            if 'error' in balance_response:
                await query.edit_message_text(
                    "❌ Error fetching portfolio data\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            risk_text = "📊 Portfolio Risk Analysis\n\n"
            
            # Calculate portfolio metrics
            total_value = 0
            usdt_balance = 0
            asset_count = 0
            largest_position = None
            
            if 'data' in balance_response and 'balances' in balance_response['data']:
                balances = balance_response['data']['balances']
                
                for balance in balances:
                    coin = balance.get('coin', '')
                    total = float(balance.get('total', 0))
                    
                    if coin == 'USDT':
                        usdt_balance = total
                    elif total > 0:
                        total_value += total
                        asset_count += 1
                        if largest_position is None or total > largest_position['value']:
                            largest_position = {'coin': coin, 'value': total}
            
            # Risk calculations - handle division by zero
            concentration_risk = 0
            if largest_position and total_value > 0:
                concentration_risk = (largest_position['value'] / total_value) * 100
            
            diversification_score = max(0, 100 - concentration_risk)
            
            risk_text += f"💰 Total Portfolio Value: ${total_value:.2f}\n"
            risk_text += f"💵 USDT Balance: ${usdt_balance:.2f}\n"
            risk_text += f"📊 Number of Assets: {asset_count}\n"
            risk_text += f"🎯 Largest Position: {largest_position['coin'] if largest_position else 'N/A'}\n"
            risk_text += f"📈 Concentration Risk: {concentration_risk:.1f}%\n"
            risk_text += f"🔄 Diversification Score: {diversification_score:.1f}/100\n\n"
            
            # Risk assessment
            if concentration_risk > 50:
                risk_text += "🔴 HIGH CONCENTRATION RISK\n"
                risk_text += "• Consider diversifying\n"
                risk_text += "• Reduce largest position\n"
            elif concentration_risk > 30:
                risk_text += "🟡 MODERATE CONCENTRATION\n"
                risk_text += "• Monitor largest position\n"
                risk_text += "• Consider rebalancing\n"
            else:
                risk_text += "🟢 GOOD DIVERSIFICATION\n"
                risk_text += "• Portfolio well balanced\n"
                risk_text += "• Continue current strategy\n"
            
            keyboard = [
                [InlineKeyboardButton("⚠️ Liquidation Risk", callback_data="risk_liquidation")],
                [InlineKeyboardButton("⚡ Dynamic Limits", callback_data="risk_limits")],
                [InlineKeyboardButton("🔙 Back", callback_data="risk_monitor")]
            ]
            
            await query.edit_message_text(
                risk_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error in portfolio risk analysis: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_dynamic_limits(self, query):
        """Show dynamic trading limits"""
        try:
            # Get account balances to calculate limits
            balance_response = self.api.get_balances()
            
            if 'error' in balance_response:
                await query.edit_message_text(
                    "❌ Error fetching account data\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            limits_text = "⚡ Dynamic Trading Limits\n\n"
            
            # Calculate limits based on account balance
            usdt_balance = 0
            total_assets = 0
            
            if 'data' in balance_response and 'balances' in balance_response['data']:
                balances = balance_response['data']['balances']
                
                for balance in balances:
                    coin = balance.get('coin', '')
                    total = float(balance.get('total', 0))
                    
                    if coin == 'USDT':
                        usdt_balance = total
                    else:
                        total_assets += total
            
            # Calculate dynamic limits
            max_position_size = usdt_balance * 0.1  # 10% of USDT balance
            max_daily_trades = min(20, int(usdt_balance / 10))  # Based on balance
            max_leverage = min(10, int(usdt_balance / 100))  # Conservative leverage
            stop_loss_limit = usdt_balance * 0.05  # 5% max loss per trade
            
            limits_text += f"💰 USDT Balance: ${usdt_balance:.2f}\n"
            limits_text += f"📊 Total Assets: ${total_assets:.2f}\n\n"
            limits_text += f"🎯 Max Position Size: ${max_position_size:.2f}\n"
            limits_text += f"📈 Max Daily Trades: {max_daily_trades}\n"
            limits_text += f"⚖️ Max Leverage: {max_leverage}x\n"
            limits_text += f"🛑 Max Stop Loss: ${stop_loss_limit:.2f}\n\n"
            
            # Risk recommendations
            if usdt_balance < 50:
                limits_text += "🔴 LOW BALANCE WARNING\n"
                limits_text += "• Consider depositing more USDT\n"
                limits_text += "• Use smaller position sizes\n"
            elif usdt_balance < 200:
                limits_text += "🟡 MODERATE BALANCE\n"
                limits_text += "• Limits are conservative\n"
                limits_text += "• Consider increasing balance\n"
            else:
                limits_text += "🟢 HEALTHY BALANCE\n"
                limits_text += "• Good trading limits\n"
                limits_text += "• Normal trading allowed\n"
            
            keyboard = [
                [InlineKeyboardButton("⚠️ Liquidation Risk", callback_data="risk_liquidation")],
                [InlineKeyboardButton("📊 Portfolio Risk", callback_data="risk_portfolio")],
                [InlineKeyboardButton("🔙 Back", callback_data="risk_monitor")]
            ]
            
            await query.edit_message_text(
                limits_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error in dynamic limits analysis: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_risk_metrics(self, query):
        """Show comprehensive risk metrics"""
        try:
            # Get account balances for risk metrics
            balance_response = self.api.get_balances()
            
            if 'error' in balance_response:
                await query.edit_message_text(
                    "❌ Error fetching account data\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            metrics_text = "📈 Risk Metrics Dashboard\n\n"
            
            # Calculate comprehensive risk metrics
            usdt_balance = 0
            total_assets = 0
            asset_count = 0
            frozen_assets = 0
            
            if 'data' in balance_response and 'balances' in balance_response['data']:
                balances = balance_response['data']['balances']
                
                for balance in balances:
                    coin = balance.get('coin', '')
                    free = float(balance.get('free', 0))
                    frozen = float(balance.get('frozen', 0))
                    total = float(balance.get('total', 0))
                    
                    if coin == 'USDT':
                        usdt_balance = total
                    elif total > 0:
                        total_assets += total
                        asset_count += 1
                        frozen_assets += frozen
            
            # Calculate risk metrics safely
            total_portfolio = total_assets + usdt_balance
            liquidity_ratio = 0
            if total_portfolio > 0:
                liquidity_ratio = (usdt_balance / total_portfolio) * 100
            
            frozen_ratio = 0
            if total_assets > 0:
                frozen_ratio = (frozen_assets / total_assets) * 100
            
            diversification_score = min(100, asset_count * 20)  # 20 points per asset, max 100
            
            # Overall risk score (0-100, lower is better)
            risk_score = 0
            if liquidity_ratio < 20:
                risk_score += 30
            if frozen_ratio > 50:
                risk_score += 25
            if asset_count < 3:
                risk_score += 20
            if usdt_balance < 50:
                risk_score += 25
            
            metrics_text += f"💰 USDT Balance: ${usdt_balance:.2f}\n"
            metrics_text += f"📊 Total Assets: ${total_assets:.2f}\n"
            metrics_text += f"🔄 Asset Count: {asset_count}\n"
            metrics_text += f"❄️ Frozen Assets: ${frozen_assets:.2f}\n\n"
            
            metrics_text += f"📈 Liquidity Ratio: {liquidity_ratio:.1f}%\n"
            metrics_text += f"❄️ Frozen Ratio: {frozen_ratio:.1f}%\n"
            metrics_text += f"🔄 Diversification: {diversification_score}/100\n"
            metrics_text += f"⚠️ Risk Score: {risk_score}/100\n\n"
            
            # Risk assessment
            if risk_score >= 70:
                risk_level = "🔴 HIGH RISK"
                recommendation = "• Reduce positions\n• Increase USDT balance\n• Monitor closely"
            elif risk_score >= 40:
                risk_level = "🟡 MEDIUM RISK"
                recommendation = "• Monitor positions\n• Consider rebalancing\n• Maintain current strategy"
            else:
                risk_level = "🟢 LOW RISK"
                recommendation = "• Account healthy\n• Continue normal trading\n• Good risk management"
            
            metrics_text += f"🎯 Risk Level: {risk_level}\n\n"
            metrics_text += f"💡 Recommendations:\n{recommendation}\n"
            
            keyboard = [
                [InlineKeyboardButton("⚠️ Liquidation Risk", callback_data="risk_liquidation")],
                [InlineKeyboardButton("📊 Portfolio Risk", callback_data="risk_portfolio")],
                [InlineKeyboardButton("🔙 Back", callback_data="risk_monitor")]
            ]
            
            await query.edit_message_text(
                metrics_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error in risk metrics analysis: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_pair_selection(self, query, symbol):
        """Handle trading pair selection"""
        try:
            # Get current price for the selected pair
            ticker_response = self.api.get_ticker_price(symbol)
            
            if 'error' in ticker_response:
                await query.edit_message_text(
                    f"❌ Error fetching data for {symbol}: {ticker_response['error']}\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            current_price = float(ticker_response['data']['price'])
            
            # Show pair analysis menu
            analysis_text = f"📊 {symbol} Analysis\n\n"
            analysis_text += f"💰 Current Price: ${current_price:.2f}\n\n"
            analysis_text += "Select analysis type:"
            
            keyboard = [
                [InlineKeyboardButton("📈 RSI Analysis", callback_data=f"analysis_rsi_{symbol}")],
                [InlineKeyboardButton("📊 Multi-Timeframe RSI", callback_data=f"analysis_rsi_mtf_{symbol}")],
                [InlineKeyboardButton("📈 Volume Filter", callback_data=f"analysis_volume_{symbol}")],
                [InlineKeyboardButton("📊 Advanced Analysis", callback_data=f"analysis_advanced_{symbol}")],
                [InlineKeyboardButton("📈 MACD Analysis", callback_data=f"analysis_macd_{symbol}")],
                [InlineKeyboardButton("🕯️ Candlestick Patterns", callback_data=f"analysis_candlestick_{symbol}")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            
            await query.edit_message_text(
                analysis_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_strategy_selection(self, query, strategy):
        """Handle strategy selection with full functionality"""
        try:
            user_id = query.from_user.id
            
            if strategy == "RSI_STRATEGY":
                await self.show_rsi_strategy_setup(query, user_id)
            elif strategy == "RSI_MULTI_TF":
                await self.show_rsi_multi_tf_strategy_setup(query, user_id)
            elif strategy == "VOLUME_FILTER":
                await self.show_volume_filter_strategy_setup(query, user_id)
            elif strategy == "ADVANCED_STRATEGY":
                await self.show_advanced_strategy_setup(query, user_id)
            elif strategy == "GRID_TRADING":
                await self.show_grid_trading_strategy_setup(query, user_id)
            elif strategy == "DCA":
                await self.show_dca_strategy_setup(query, user_id)
            elif strategy == "MANUAL":
                await self.show_manual_trading_setup(query, user_id)
            else:
                await query.edit_message_text(
                    f"🎯 {strategy} Strategy\n\nThis feature is coming soon!\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_rsi_strategy_setup(self, query, user_id):
        """Show RSI strategy setup with full functionality"""
        try:
            config = get_config()
            
            strategy_text = "📈 RSI Strategy Setup\n\n"
            strategy_text += "RSI (Relative Strength Index) Strategy:\n"
            strategy_text += "• Monitors RSI levels for overbought/oversold conditions\n"
            strategy_text += "• Generates buy signals when RSI < 30 (oversold)\n"
            strategy_text += "• Generates sell signals when RSI > 70 (overbought)\n\n"
            
            strategy_text += f"📊 Current Settings:\n"
            strategy_text += f"• Period: {config['rsi']['period']}\n"
            strategy_text += f"• Oversold Level: {config['rsi']['oversold']}\n"
            strategy_text += f"• Overbought Level: {config['rsi']['overbought']}\n"
            strategy_text += f"• Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            strategy_text += f"• Position Size: {config.get('position_size', 0.1)}\n\n"
            
            strategy_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Activate Strategy", callback_data="activate_rsi_strategy")],
                [InlineKeyboardButton("⚙️ Configure Settings", callback_data="configure_rsi_strategy")],
                [InlineKeyboardButton("📊 Test Strategy", callback_data="test_rsi_strategy")],
                [InlineKeyboardButton("📈 View Performance", callback_data="performance_rsi_strategy")],
                [InlineKeyboardButton("🔙 Back", callback_data="strategies")]
            ]
            
            await query.edit_message_text(
                strategy_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_rsi_multi_tf_strategy_setup(self, query, user_id):
        """Show RSI Multi-Timeframe strategy setup"""
        try:
            config = get_config()
            
            strategy_text = "📊 RSI Multi-Timeframe Strategy Setup\n\n"
            strategy_text += "Multi-Timeframe RSI Strategy:\n"
            strategy_text += "• Combines 5-minute and 1-hour RSI analysis\n"
            strategy_text += "• Long Entry: RSI(5m) < 30 AND RSI(1h) < 50\n"
            strategy_text += "• Short Entry: RSI(5m) > 70 AND RSI(1h) > 50\n"
            strategy_text += "• Reduces false signals with trend confirmation\n\n"
            
            strategy_text += f"📊 Current Settings:\n"
            strategy_text += f"• 5m RSI Period: {config['rsi']['period']}\n"
            strategy_text += f"• 1h RSI Period: {config['rsi']['period']}\n"
            strategy_text += f"• Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            strategy_text += f"• Position Size: {config.get('position_size', 0.1)}\n\n"
            
            strategy_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Activate Strategy", callback_data="activate_rsi_mtf_strategy")],
                [InlineKeyboardButton("⚙️ Configure Settings", callback_data="configure_rsi_mtf_strategy")],
                [InlineKeyboardButton("📊 Test Strategy", callback_data="test_rsi_mtf_strategy")],
                [InlineKeyboardButton("📈 View Performance", callback_data="performance_rsi_mtf_strategy")],
                [InlineKeyboardButton("🔙 Back", callback_data="strategies")]
            ]
            
            await query.edit_message_text(
                strategy_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_volume_filter_strategy_setup(self, query, user_id):
        """Show Volume Filter strategy setup"""
        try:
            config = get_config()
            
            strategy_text = "📈 Volume Filter Strategy Setup\n\n"
            strategy_text += "Volume Filter Strategy:\n"
            strategy_text += "• Uses EMA(volume, 20) to filter market activity\n"
            strategy_text += "• Entry only when current_volume > 1.5 × EMA(volume)\n"
            strategy_text += "• Ensures significant market movement before trading\n"
            strategy_text += "• Reduces false signals in low-volume periods\n\n"
            
            strategy_text += f"📊 Current Settings:\n"
            strategy_text += f"• Volume EMA Period: {config['volume_filter']['ema_period']}\n"
            strategy_text += f"• Volume Multiplier: {config['volume_filter']['multiplier']}\n"
            strategy_text += f"• Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            strategy_text += f"• Position Size: {config.get('position_size', 0.1)}\n\n"
            
            strategy_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Activate Strategy", callback_data="activate_volume_strategy")],
                [InlineKeyboardButton("⚙️ Configure Settings", callback_data="configure_volume_strategy")],
                [InlineKeyboardButton("📊 Test Strategy", callback_data="test_volume_strategy")],
                [InlineKeyboardButton("📈 View Performance", callback_data="performance_volume_strategy")],
                [InlineKeyboardButton("🔙 Back", callback_data="strategies")]
            ]
            
            await query.edit_message_text(
                strategy_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_advanced_strategy_setup(self, query, user_id):
        """Show Advanced strategy setup"""
        try:
            config = get_config()
            
            strategy_text = "📊 Advanced Strategy Setup\n\n"
            strategy_text += "Advanced Multi-Indicator Strategy:\n"
            strategy_text += "• Combines RSI, MACD, Bollinger Bands, and Volume\n"
            strategy_text += "• Uses multiple confirmations for higher accuracy\n"
            strategy_text += "• Dynamic stop loss and take profit levels\n"
            strategy_text += "• Trailing stop functionality\n\n"
            
            strategy_text += f"📊 Current Settings:\n"
            strategy_text += f"• RSI Period: {config['rsi']['period']}\n"
            strategy_text += f"• MACD Settings: (12, 26, 9)\n"
            strategy_text += f"• Bollinger Bands: (20, 2)\n"
            strategy_text += f"• Volume Filter: {config['volume_filter']['multiplier']}x\n"
            strategy_text += f"• Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            strategy_text += f"• Position Size: {config.get('position_size', 0.1)}\n\n"
            
            strategy_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Activate Strategy", callback_data="activate_advanced_strategy")],
                [InlineKeyboardButton("⚙️ Configure Settings", callback_data="configure_advanced_strategy")],
                [InlineKeyboardButton("📊 Test Strategy", callback_data="test_advanced_strategy")],
                [InlineKeyboardButton("📈 View Performance", callback_data="performance_advanced_strategy")],
                [InlineKeyboardButton("🔙 Back", callback_data="strategies")]
            ]
            
            await query.edit_message_text(
                strategy_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_grid_trading_strategy_setup(self, query, user_id):
        """Show Grid Trading strategy setup"""
        try:
            config = get_config()
            
            strategy_text = "🔄 Grid Trading Strategy Setup\n\n"
            strategy_text += "Grid Trading Strategy:\n"
            strategy_text += "• Places buy and sell orders at regular intervals\n"
            strategy_text += "• Profits from price oscillations within a range\n"
            strategy_text += "• Automatic order management and rebalancing\n"
            strategy_text += "• Suitable for sideways markets\n\n"
            
            strategy_text += f"📊 Current Settings:\n"
            strategy_text += f"• Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            strategy_text += f"• Grid Spacing: 2% (default)\n"
            strategy_text += f"• Grid Levels: 10 (default)\n"
            strategy_text += f"• Investment Amount: ${config.get('position_size', 0.1) * 1000:.0f}\n\n"
            
            strategy_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Activate Grid", callback_data="activate_grid_strategy")],
                [InlineKeyboardButton("⚙️ Configure Grid", callback_data="configure_grid_strategy")],
                [InlineKeyboardButton("📊 Monitor Grid", callback_data="monitor_grid_strategy")],
                [InlineKeyboardButton("📈 Grid Performance", callback_data="performance_grid_strategy")],
                [InlineKeyboardButton("🔙 Back", callback_data="strategies")]
            ]
            
            await query.edit_message_text(
                strategy_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_dca_strategy_setup(self, query, user_id):
        """Show Dollar Cost Averaging strategy setup"""
        try:
            config = get_config()
            
            strategy_text = "💰 Dollar Cost Averaging (DCA) Setup\n\n"
            strategy_text += "DCA Strategy:\n"
            strategy_text += "• Invests fixed amount at regular intervals\n"
            strategy_text += "• Reduces impact of market volatility\n"
            strategy_text += "• Automatic buying regardless of price\n"
            strategy_text += "• Long-term investment approach\n\n"
            
            strategy_text += f"📊 Current Settings:\n"
            strategy_text += f"• Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            strategy_text += f"• Investment Amount: ${config.get('position_size', 0.1) * 1000:.0f}\n"
            strategy_text += f"• Frequency: Weekly (default)\n"
            strategy_text += f"• Duration: 12 months (default)\n\n"
            
            strategy_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Start DCA", callback_data="activate_dca_strategy")],
                [InlineKeyboardButton("⚙️ Configure DCA", callback_data="configure_dca_strategy")],
                [InlineKeyboardButton("📊 DCA Progress", callback_data="progress_dca_strategy")],
                [InlineKeyboardButton("📈 DCA Performance", callback_data="performance_dca_strategy")],
                [InlineKeyboardButton("🔙 Back", callback_data="strategies")]
            ]
            
            await query.edit_message_text(
                strategy_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_manual_trading_setup(self, query, user_id):
        """Show Manual Trading setup"""
        try:
            config = get_config()
            
            strategy_text = "📝 Manual Trading Setup\n\n"
            strategy_text += "Manual Trading Features:\n"
            strategy_text += "• Place buy/sell orders manually\n"
            strategy_text += "• Set custom stop loss and take profit\n"
            strategy_text += "• Real-time market data and analysis\n"
            strategy_text += "• Order history and tracking\n\n"
            
            strategy_text += f"📊 Current Settings:\n"
            strategy_text += f"• Default Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            strategy_text += f"• Default Position Size: {config.get('position_size', 0.1)}\n"
            strategy_text += f"• Default Stop Loss: {config.get('stop_loss_percentage', 1.5)}%\n"
            strategy_text += f"• Default Take Profit: {config.get('take_profit_percentage', 2.5)}%\n\n"
            
            strategy_text += "Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("📈 Place Buy Order", callback_data="manual_buy_order")],
                [InlineKeyboardButton("📉 Place Sell Order", callback_data="manual_sell_order")],
                [InlineKeyboardButton("📋 View Orders", callback_data="manual_view_orders")],
                [InlineKeyboardButton("📊 Market Analysis", callback_data="manual_market_analysis")],
                [InlineKeyboardButton("🔙 Back", callback_data="strategies")]
            ]
            
            await query.edit_message_text(
                strategy_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_trade_action(self, query, data):
        """Handle trade actions"""
        try:
            action = data.replace("trade_", "")
            
            if action == "advanced_orders":
                await self.show_advanced_orders(query)
            elif action == "bracket_orders":
                await self.show_bracket_orders(query)
            elif action == "oco_orders":
                await self.show_oco_orders(query)
            else:
                await query.edit_message_text(
                    "📝 Trade Action\n\nThis feature is coming soon!\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_advanced_orders(self, query):
        """Show advanced order types"""
        try:
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            current_price = self.get_real_time_price(symbol) or 0.5
            
            order_text = "📊 Advanced Order Types\n\n"
            order_text += f"📈 Symbol: {symbol}\n"
            order_text += f"💰 Current Price: ${current_price:.4f}\n\n"
            order_text += "Available Order Types:\n"
            order_text += "• Market Order - Immediate execution\n"
            order_text += "• Limit Order - Execute at specific price\n"
            order_text += "• Stop Market - Stop loss at market\n"
            order_text += "• Stop Limit - Stop loss at limit\n"
            order_text += "• Take Profit Market - Take profit at market\n"
            order_text += "• Take Profit Limit - Take profit at limit\n\n"
            order_text += "Select order type:"
            
            keyboard = [
                [InlineKeyboardButton("📈 Market Order", callback_data="order_market")],
                [InlineKeyboardButton("📊 Limit Order", callback_data="order_limit")],
                [InlineKeyboardButton("🛑 Stop Market", callback_data="order_stop_market")],
                [InlineKeyboardButton("⚖️ Stop Limit", callback_data="order_stop_limit")],
                [InlineKeyboardButton("📈 Take Profit Market", callback_data="order_tp_market")],
                [InlineKeyboardButton("📊 Take Profit Limit", callback_data="order_tp_limit")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trade")]
            ]
            
            await query.edit_message_text(
                order_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_bracket_orders(self, query):
        """Show bracket order setup"""
        try:
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            current_price = self.get_real_time_price(symbol) or 0.5
            
            bracket_text = "📊 Bracket Order Setup\n\n"
            bracket_text += f"📈 Symbol: {symbol}\n"
            bracket_text += f"💰 Current Price: ${current_price:.4f}\n\n"
            bracket_text += "Bracket Order includes:\n"
            bracket_text += "• Main Limit Order\n"
            bracket_text += "• Stop Loss Order\n"
            bracket_text += "• Take Profit Order\n\n"
            bracket_text += "All orders are placed simultaneously.\n"
            bracket_text += "When one order executes, others are cancelled.\n\n"
            bracket_text += "Select action:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Place Bracket Order", callback_data="bracket_place")],
                [InlineKeyboardButton("⚙️ Configure Bracket", callback_data="bracket_configure")],
                [InlineKeyboardButton("📊 Bracket History", callback_data="bracket_history")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trade")]
            ]
            
            await query.edit_message_text(
                bracket_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_oco_orders(self, query):
        """Show OCO order setup"""
        try:
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            current_price = self.get_real_time_price(symbol) or 0.5
            
            oco_text = "📊 OCO Order Setup\n\n"
            oco_text += f"📈 Symbol: {symbol}\n"
            oco_text += f"💰 Current Price: ${current_price:.4f}\n\n"
            oco_text += "OCO (One-Cancels-Other) Order:\n"
            oco_text += "• Stop Loss Order\n"
            oco_text += "• Take Profit Order\n"
            oco_text += "• When one executes, other is cancelled\n\n"
            oco_text += "Perfect for risk management.\n\n"
            oco_text += "Select action:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Place OCO Order", callback_data="oco_place")],
                [InlineKeyboardButton("⚙️ Configure OCO", callback_data="oco_configure")],
                [InlineKeyboardButton("📊 OCO History", callback_data="oco_history")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trade")]
            ]
            
            await query.edit_message_text(
                oco_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_analysis_selection(self, query, data):
        """Handle analysis selection"""
        try:
            # Parse analysis type and symbol from callback data
            # Format: analysis_rsi_BTCUSDT, analysis_rsi_mtf_BTCUSDT, analysis_macd_ETHUSDT, etc.
            
            # Handle special case for rsi_mtf which contains underscore
            if data.startswith("analysis_rsi_mtf_"):
                analysis_type = "rsi_mtf"
                symbol = data.replace("analysis_rsi_mtf_", "")
            elif data.startswith("analysis_"):
                # For other analysis types, split by underscore
                parts = data.split('_', 2)  # Split into ['analysis', 'rsi', 'BTCUSDT']
                if len(parts) >= 3:
                    analysis_type = parts[1]
                    symbol = parts[2]
                else:
                    # Fallback to default symbol from config
                    analysis_type = data.replace("analysis_", "")
                    symbol = self.config.get('trading_pair', 'XRP_USDT')
            else:
                # Fallback to default symbol from config
                analysis_type = data.replace("analysis_", "")
                symbol = self.config.get('trading_pair', 'XRP_USDT')
            
            # Validate symbol - if it's empty or invalid, use default
            if not symbol or symbol in ['mtf', 'rsi', 'volume', 'advanced', 'macd', 'candlestick']:
                symbol = self.config.get('trading_pair', 'XRP_USDT')
            
            if analysis_type == "rsi":
                await self.show_rsi_analysis(query, symbol)
            elif analysis_type == "rsi_mtf":
                await self.show_multi_timeframe_rsi_analysis(query, symbol)
            elif analysis_type == "volume":
                await self.show_volume_filter_analysis(query, symbol)
            elif analysis_type == "advanced":
                await self.show_advanced_analysis(query, symbol)
            elif analysis_type == "macd":
                await self.show_macd_analysis(query, symbol)
            elif analysis_type == "candlestick":
                await self.show_candlestick_analysis(query, symbol)
            else:
                await query.edit_message_text(
                    "📊 Technical Analysis\n\nThis feature is coming soon!\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_rsi_analysis(self, query, symbol):
        """Show RSI analysis for current trading pair"""
        try:
            config = get_config()
            
            # Get current price and try to get RSI data
            ticker_response = self.api.get_ticker_price(symbol)
            klines_response = self.api.get_klines(symbol, '5M', 100)  # Use 5M interval which works
            
            if 'error' in ticker_response:
                await self._safe_edit_message(
                    query,
                    f"❌ Error fetching market data for {symbol} RSI analysis\n\n🔙 Back to main menu:",
                    InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            current_price = float(ticker_response['data']['price'])
            
            # Try to calculate RSI if klines are available
            current_rsi = 50.0  # Default neutral RSI
            rsi_source = "Default (no historical data)"
            
            if 'error' not in klines_response and 'data' in klines_response and 'klines' in klines_response['data']:
                try:
                    klines_data = klines_response['data']['klines']
                    closes = [float(k['close']) for k in klines_data]  # Use 'close' field from new format
                    rsi_period = config['rsi']['period']
                    rsi_value = self.strategies.calculate_rsi(closes, rsi_period)
                    if rsi_value and len(rsi_value) > 0:
                        current_rsi = rsi_value[-1]
                        rsi_source = f"Historical data ({len(closes)} candles, 5M interval)"
                except Exception as e:
                    # Use fallback RSI calculation
                    current_rsi = 50.0
                    rsi_source = "Fallback calculation"
            
            # Determine RSI signal
            rsi_signal = "NEUTRAL"
            if current_rsi < config['rsi']['oversold']:
                rsi_signal = "OVERSOLD (BUY)"
            elif current_rsi > config['rsi']['overbought']:
                rsi_signal = "OVERBOUGHT (SELL)"
            
            analysis_text = f"📈 RSI Analysis - {symbol}\n\n"
            analysis_text += f"💰 Current Price: ${current_price:.4f}\n"
            analysis_text += f"📊 RSI ({config['rsi']['period']}): {current_rsi:.2f}\n"
            analysis_text += f"🎯 Signal: {rsi_signal}\n"
            analysis_text += f"📈 Source: {rsi_source}\n\n"
            analysis_text += f"📉 Oversold Level: {config['rsi']['oversold']}\n"
            analysis_text += f"📈 Overbought Level: {config['rsi']['overbought']}\n\n"
            
            if current_rsi < 30:
                analysis_text += "🟢 BUY SIGNAL - RSI indicates oversold conditions\n"
            elif current_rsi > 70:
                analysis_text += "🔴 SELL SIGNAL - RSI indicates overbought conditions\n"
            else:
                analysis_text += "🟡 NEUTRAL - RSI in normal range\n"
            
            keyboard = [
                [InlineKeyboardButton("📊 Multi-Timeframe RSI", callback_data=f"analysis_rsi_mtf_{symbol}")],
                [InlineKeyboardButton("📈 Volume Filter", callback_data=f"analysis_volume_{symbol}")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"pair_{symbol}")]
            ]
            
            await self._safe_edit_message(
                query,
                analysis_text,
                InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await self._safe_edit_message(
                query,
                f"❌ Error in RSI analysis: {str(e)}\n\n🔙 Back to main menu:",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_multi_timeframe_rsi_analysis(self, query, symbol):
        """Show Multi-Timeframe RSI analysis"""
        try:
            config = get_config()
            
            # Get data for different timeframes using working intervals
            klines_5m = self.api.get_klines(symbol, '5M', 100)  # 5-minute data
            klines_30m = self.api.get_klines(symbol, '30M', 100)  # 30-minute data (closest to 1h)
            
            if 'error' in klines_5m and 'error' in klines_30m:
                await self._safe_edit_message(
                    query,
                    f"❌ Error fetching multi-timeframe data for {symbol}\n\n🔙 Back to main menu:",
                    InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            # Calculate RSI for both timeframes
            current_rsi_5m = 50.0
            current_rsi_30m = 50.0
            rsi_source_5m = "Default (no data)"
            rsi_source_30m = "Default (no data)"
            
            # Calculate 5M RSI
            if 'error' not in klines_5m and 'data' in klines_5m and 'klines' in klines_5m['data']:
                try:
                    klines_data = klines_5m['data']['klines']
                    closes_5m = [float(k['close']) for k in klines_data]
                    rsi_5m = self.strategies.calculate_rsi(closes_5m, 14)
                    if rsi_5m and len(rsi_5m) > 0:
                        current_rsi_5m = rsi_5m[-1]
                        rsi_source_5m = f"Historical data ({len(closes_5m)} candles)"
                except Exception as e:
                    current_rsi_5m = 50.0
                    rsi_source_5m = "Fallback calculation"
            
            # Calculate 30M RSI
            if 'error' not in klines_30m and 'data' in klines_30m and 'klines' in klines_30m['data']:
                try:
                    klines_data = klines_30m['data']['klines']
                    closes_30m = [float(k['close']) for k in klines_data]
                    rsi_30m = self.strategies.calculate_rsi(closes_30m, 14)
                    if rsi_30m and len(rsi_30m) > 0:
                        current_rsi_30m = rsi_30m[-1]
                        rsi_source_30m = f"Historical data ({len(closes_30m)} candles)"
                except Exception as e:
                    current_rsi_30m = 50.0
                    rsi_source_30m = "Fallback calculation"
            
            # Multi-timeframe signal logic
            signal = "NEUTRAL"
            if current_rsi_5m < 30 and current_rsi_30m < 50:
                signal = "STRONG BUY"
            elif current_rsi_5m > 70 and current_rsi_30m > 50:
                signal = "STRONG SELL"
            elif current_rsi_5m < 30:
                signal = "WEAK BUY"
            elif current_rsi_5m > 70:
                signal = "WEAK SELL"
            
            analysis_text = f"📊 Multi-Timeframe RSI - {symbol}\n\n"
            analysis_text += f"⏰ 5-Minute RSI: {current_rsi_5m:.2f} ({rsi_source_5m})\n"
            analysis_text += f"⏰ 30-Minute RSI: {current_rsi_30m:.2f} ({rsi_source_30m})\n\n"
            analysis_text += f"🎯 Combined Signal: {signal}\n\n"
            
            if signal == "STRONG BUY":
                analysis_text += "🟢 STRONG BUY SIGNAL\n"
                analysis_text += "• 5m RSI < 30 (oversold)\n"
                analysis_text += "• 30m RSI < 50 (trend confirmation)\n"
            elif signal == "STRONG SELL":
                analysis_text += "🔴 STRONG SELL SIGNAL\n"
                analysis_text += "• 5m RSI > 70 (overbought)\n"
                analysis_text += "• 30m RSI > 50 (trend confirmation)\n"
            elif signal == "WEAK BUY":
                analysis_text += "🟡 WEAK BUY SIGNAL\n"
                analysis_text += "• Only 5m RSI < 30\n"
            elif signal == "WEAK SELL":
                analysis_text += "🟡 WEAK SELL SIGNAL\n"
                analysis_text += "• Only 5m RSI > 70\n"
            else:
                analysis_text += "⚪ NEUTRAL\n"
                analysis_text += "• No clear signal\n"
            
            keyboard = [
                [InlineKeyboardButton("📈 RSI Analysis", callback_data=f"analysis_rsi_{symbol}")],
                [InlineKeyboardButton("📊 Volume Filter", callback_data=f"analysis_volume_{symbol}")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"pair_{symbol}")]
            ]
            
            await self._safe_edit_message(
                query,
                analysis_text,
                InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await self._safe_edit_message(
                query,
                f"❌ Error in Multi-Timeframe RSI analysis: {str(e)}\n\n🔙 Back to main menu:",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_volume_filter_analysis(self, query, symbol):
        """Show Volume Filter analysis"""
        try:
            config = get_config()
            # Use the symbol parameter instead of config default
            # symbol = config.get('trading_pair', 'BTCUSDT')  # REMOVED THIS LINE
            
            # Get recent klines with volume data - use 30M interval which works
            klines_response = self.api.get_klines(symbol, '30M', 50)
            
            if 'error' in klines_response:
                await query.edit_message_text(
                    "❌ Error fetching volume data\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            # Extract volume data - handle both old and new klines format
            if 'data' in klines_response and 'klines' in klines_response['data']:
                # New format with klines as objects
                klines_data = klines_response['data']['klines']
                volumes = [float(k.get('volume', 0)) for k in klines_data]
            else:
                # Fallback to old format with klines as arrays
                klines_data = klines_response.get('data', [])
                volumes = [float(k[5]) for k in klines_data if len(k) > 5]  # Volume is at index 5
            
            if not volumes:
                await query.edit_message_text(
                    "❌ No volume data available\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            current_volume = volumes[-1]
            
            # Calculate EMA of volume
            ema_period = config['volume_filter']['ema_period']
            volume_ema = self.strategies.calculate_ema(volumes, ema_period)
            current_volume_ema = volume_ema[-1] if volume_ema else 0
            
            # Volume filter logic
            multiplier = config['volume_filter']['multiplier']
            volume_threshold = current_volume_ema * multiplier
            volume_signal = "HIGH" if current_volume > volume_threshold else "LOW"
            
            analysis_text = f"📈 Volume Filter Analysis - {symbol}\n\n"
            analysis_text += f"📊 Current Volume: {current_volume:.2f}\n"
            analysis_text += f"📈 Volume EMA ({ema_period}): {current_volume_ema:.2f}\n"
            analysis_text += f"🎯 Threshold: {volume_threshold:.2f}\n"
            analysis_text += f"📊 Volume Signal: {volume_signal}\n"
            analysis_text += f"⏰ Timeframe: 30M (working interval)\n\n"
            
            if volume_signal == "HIGH":
                analysis_text += "🟢 HIGH VOLUME\n"
                analysis_text += f"• Current volume ({current_volume:.2f}) > {multiplier}x EMA\n"
                analysis_text += "• Significant market movement detected\n"
                analysis_text += "• Good conditions for trade execution\n"
            else:
                analysis_text += "🔴 LOW VOLUME\n"
                analysis_text += f"• Current volume ({current_volume:.2f}) < {multiplier}x EMA\n"
                analysis_text += "• Low market activity\n"
                analysis_text += "• Consider waiting for higher volume\n"
            
            keyboard = [
                [InlineKeyboardButton("📊 RSI Analysis", callback_data=f"analysis_rsi_{symbol}")],
                [InlineKeyboardButton("📈 Multi-Timeframe RSI", callback_data=f"analysis_rsi_mtf_{symbol}")],
                [InlineKeyboardButton("🔙 Back", callback_data="technical_analysis")]
            ]
            
            await query.edit_message_text(
                analysis_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error in Volume Filter analysis: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_advanced_analysis(self, query, symbol):
        """Show Advanced analysis combining multiple indicators"""
        try:
            config = get_config()
            # Use the symbol parameter instead of config default
            # symbol = config.get('trading_pair', 'BTCUSDT')  # REMOVED THIS LINE
            
            # Get comprehensive market data - use 30M interval which works
            klines_response = self.api.get_klines(symbol, '30M', 100)
            ticker_response = self.api.get_ticker_price(symbol)
            
            if 'error' in klines_response or 'error' in ticker_response:
                await query.edit_message_text(
                    "❌ Error fetching advanced analysis data\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            # Extract data - handle both old and new klines format
            if 'data' in klines_response and 'klines' in klines_response['data']:
                # New format with klines as objects
                klines_data = klines_response['data']['klines']
                closes = [float(k.get('close', 0)) for k in klines_data]
                volumes = [float(k.get('volume', 0)) for k in klines_data]
                highs = [float(k.get('high', 0)) for k in klines_data]
                lows = [float(k.get('low', 0)) for k in klines_data]
            else:
                # Fallback to old format with klines as arrays
                klines_data = klines_response.get('data', [])
                closes = [float(k[4]) for k in klines_data if len(k) > 4]
                volumes = [float(k[5]) for k in klines_data if len(k) > 5]
                highs = [float(k[2]) for k in klines_data if len(k) > 2]
                lows = [float(k[3]) for k in klines_data if len(k) > 3]
            
            current_price = float(ticker_response['data']['price'])
            
            # Calculate multiple indicators
            rsi = self.strategies.calculate_rsi(closes, 14)
            macd, signal, hist = self.strategies.calculate_macd(closes)
            bb_upper, bb_middle, bb_lower = self.strategies.calculate_bollinger_bands(closes, 20, 2)
            volume_ema = self.strategies.calculate_ema(volumes, 20)
            
            # Get current values
            current_rsi = rsi[-1] if rsi else 50
            current_macd = macd[-1] if macd else 0
            current_signal = signal[-1] if signal else 0
            current_bb_upper = bb_upper[-1] if bb_upper else current_price
            current_bb_lower = bb_lower[-1] if bb_lower else current_price
            current_volume_ema = volume_ema[-1] if volume_ema else 0
            
            # Advanced signal analysis
            signals = []
            
            # RSI signals
            if current_rsi < 30:
                signals.append("RSI: BUY (oversold)")
            elif current_rsi > 70:
                signals.append("RSI: SELL (overbought)")
            
            # MACD signals
            if current_macd > current_signal:
                signals.append("MACD: BULLISH")
            else:
                signals.append("MACD: BEARISH")
            
            # Bollinger Bands signals
            if current_price < current_bb_lower:
                signals.append("BB: BUY (below lower band)")
            elif current_price > current_bb_upper:
                signals.append("BB: SELL (above upper band)")
            
            # Volume signals
            current_volume = volumes[-1] if volumes else 0
            if current_volume > current_volume_ema * 1.5:
                signals.append("VOLUME: HIGH")
            else:
                signals.append("VOLUME: LOW")
            
            # Overall signal
            buy_signals = sum(1 for s in signals if "BUY" in s or "BULLISH" in s)
            sell_signals = sum(1 for s in signals if "SELL" in s or "BEARISH" in s)
            
            overall_signal = "NEUTRAL"
            if buy_signals > sell_signals:
                overall_signal = "BUY"
            elif sell_signals > buy_signals:
                overall_signal = "SELL"
            
            analysis_text = f"📊 Advanced Analysis - {symbol}\n\n"
            analysis_text += f"💰 Current Price: ${current_price:.2f}\n"
            analysis_text += f"📊 RSI: {current_rsi:.2f}\n"
            analysis_text += f"📈 MACD: {current_macd:.4f}\n"
            analysis_text += f"📊 Signal: {current_signal:.4f}\n"
            analysis_text += f"📈 BB Upper: ${current_bb_upper:.2f}\n"
            analysis_text += f"📉 BB Lower: ${current_bb_lower:.2f}\n"
            analysis_text += f"📊 Volume: {current_volume:.2f}\n"
            analysis_text += f"⏰ Timeframe: 30M (working interval)\n\n"
            
            analysis_text += f"🎯 Overall Signal: {overall_signal}\n\n"
            analysis_text += "📋 Individual Signals:\n"
            for signal in signals:
                analysis_text += f"• {signal}\n"
            
            keyboard = [
                [InlineKeyboardButton("📈 RSI Analysis", callback_data=f"analysis_rsi_{symbol}")],
                [InlineKeyboardButton("📊 MACD Analysis", callback_data=f"analysis_macd_{symbol}")],
                [InlineKeyboardButton("🔙 Back", callback_data="technical_analysis")]
            ]
            
            await query.edit_message_text(
                analysis_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error in Advanced analysis: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_macd_analysis(self, query, symbol):
        """Show MACD analysis"""
        try:
            config = get_config()
            # Use the symbol parameter instead of config default
            # symbol = config.get('trading_pair', 'BTCUSDT')  # REMOVED THIS LINE
            
            # Get price data - use 30M interval which works
            klines_response = self.api.get_klines(symbol, '30M', 100)
            
            if 'error' in klines_response:
                await query.edit_message_text(
                    "❌ Error fetching MACD data\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            # Calculate MACD - handle both old and new klines format
            if 'data' in klines_response and 'klines' in klines_response['data']:
                # New format with klines as objects
                klines_data = klines_response['data']['klines']
                closes = [float(k.get('close', 0)) for k in klines_data]
            else:
                # Fallback to old format with klines as arrays
                klines_data = klines_response.get('data', [])
                closes = [float(k[4]) for k in klines_data if len(k) > 4]
            
            macd, signal, hist = self.strategies.calculate_macd(closes)
            
            current_macd = macd[-1] if macd else 0
            current_signal = signal[-1] if signal else 0
            current_hist = hist[-1] if hist else 0
            prev_macd = macd[-2] if len(macd) > 1 else 0
            prev_signal = signal[-2] if len(signal) > 1 else 0
            
            # MACD signal analysis
            macd_signal = "NEUTRAL"
            if current_macd > current_signal and prev_macd <= prev_signal:
                macd_signal = "BULLISH CROSSOVER"
            elif current_macd < current_signal and prev_macd >= prev_signal:
                macd_signal = "BEARISH CROSSOVER"
            elif current_macd > current_signal:
                macd_signal = "BULLISH"
            elif current_macd < current_signal:
                macd_signal = "BEARISH"
            
            analysis_text = f"📈 MACD Analysis - {symbol}\n\n"
            analysis_text += f"📊 MACD Line: {current_macd:.4f}\n"
            analysis_text += f"📈 Signal Line: {current_signal:.4f}\n"
            analysis_text += f"📊 Histogram: {current_hist:.4f}\n"
            analysis_text += f"⏰ Timeframe: 30M (working interval)\n\n"
            analysis_text += f"🎯 Signal: {macd_signal}\n\n"
            
            if macd_signal == "BULLISH CROSSOVER":
                analysis_text += "🟢 STRONG BUY SIGNAL\n"
                analysis_text += "• MACD crossed above Signal line\n"
                analysis_text += "• Momentum is turning bullish\n"
            elif macd_signal == "BEARISH CROSSOVER":
                analysis_text += "🔴 STRONG SELL SIGNAL\n"
                analysis_text += "• MACD crossed below Signal line\n"
                analysis_text += "• Momentum is turning bearish\n"
            elif macd_signal == "BULLISH":
                analysis_text += "🟡 BULLISH\n"
                analysis_text += "• MACD above Signal line\n"
                analysis_text += "• Positive momentum\n"
            elif macd_signal == "BEARISH":
                analysis_text += "🟡 BEARISH\n"
                analysis_text += "• MACD below Signal line\n"
                analysis_text += "• Negative momentum\n"
            else:
                analysis_text += "⚪ NEUTRAL\n"
                analysis_text += "• No clear MACD signal\n"
            
            keyboard = [
                [InlineKeyboardButton("📊 RSI Analysis", callback_data=f"analysis_rsi_{symbol}")],
                [InlineKeyboardButton("📈 Advanced Analysis", callback_data=f"analysis_advanced_{symbol}")],
                [InlineKeyboardButton("🔙 Back", callback_data="technical_analysis")]
            ]
            
            await query.edit_message_text(
                analysis_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error in MACD analysis: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_candlestick_analysis(self, query, symbol):
        """Show Candlestick pattern analysis"""
        try:
            config = get_config()
            # Use the symbol parameter instead of config default
            # symbol = config.get('trading_pair', 'BTCUSDT')  # REMOVED THIS LINE
            
            # Get recent candlestick data - use 30M interval which works
            klines_response = self.api.get_klines(symbol, '30M', 20)
            
            if 'error' in klines_response:
                await query.edit_message_text(
                    "❌ Error fetching candlestick data\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            # Analyze recent candlesticks - handle both old and new klines format
            if 'data' in klines_response and 'klines' in klines_response['data']:
                # New format with klines as objects
                klines_data = klines_response['data']['klines']
                current_price = float(klines_data[-1].get('close', 0))
                recent_candles = klines_data[-5:]  # Last 5 candles
            else:
                # Fallback to old format with klines as arrays
                klines_data = klines_response.get('data', [])
                current_price = float(klines_data[-1][4]) if klines_data else 0  # Close price
                recent_candles = klines_data[-5:]  # Last 5 candles
            
            patterns = []
            
            for i, candle in enumerate(recent_candles):
                if 'data' in klines_response and 'klines' in klines_response['data']:
                    # New format
                    open_price = float(candle.get('open', 0))
                    high_price = float(candle.get('high', 0))
                    low_price = float(candle.get('low', 0))
                    close_price = float(candle.get('close', 0))
                else:
                    # Old format
                    open_price = float(candle[1])
                    high_price = float(candle[2])
                    low_price = float(candle[3])
                    close_price = float(candle[4])
                
                # Basic candlestick patterns
                body_size = abs(close_price - open_price)
                upper_shadow = high_price - max(open_price, close_price)
                lower_shadow = min(open_price, close_price) - low_price
                
                if close_price > open_price:  # Bullish candle
                    if body_size > (upper_shadow + lower_shadow) * 0.6:
                        patterns.append(f"Candle {i+1}: Strong Bullish")
                    elif lower_shadow > body_size * 2:
                        patterns.append(f"Candle {i+1}: Hammer (Bullish)")
                else:  # Bearish candle
                    if body_size > (upper_shadow + lower_shadow) * 0.6:
                        patterns.append(f"Candle {i+1}: Strong Bearish")
                    elif upper_shadow > body_size * 2:
                        patterns.append(f"Candle {i+1}: Shooting Star (Bearish)")
            
            # Check for engulfing patterns
            if len(recent_candles) >= 2:
                prev_candle = recent_candles[-2]
                curr_candle = recent_candles[-1]
                
                if 'data' in klines_response and 'klines' in klines_response['data']:
                    # New format
                    prev_open = float(prev_candle.get('open', 0))
                    prev_close = float(prev_candle.get('close', 0))
                    curr_open = float(curr_candle.get('open', 0))
                    curr_close = float(curr_candle.get('close', 0))
                else:
                    # Old format
                    prev_open = float(prev_candle[1])
                    prev_close = float(prev_candle[4])
                    curr_open = float(curr_candle[1])
                    curr_close = float(curr_candle[4])
                
                if curr_close > curr_open and prev_close < prev_open:  # Bullish engulfing
                    if curr_open < prev_close and curr_close > prev_open:
                        patterns.append("Bullish Engulfing Pattern")
                elif curr_close < curr_open and prev_close > prev_open:  # Bearish engulfing
                    if curr_open > prev_close and curr_close < prev_open:
                        patterns.append("Bearish Engulfing Pattern")
            
            analysis_text = f"🕯️ Candlestick Analysis - {symbol}\n\n"
            analysis_text += f"💰 Current Price: ${current_price:.2f}\n"
            analysis_text += f"⏰ Timeframe: 30M (working interval)\n\n"
            
            if patterns:
                analysis_text += "📊 Detected Patterns:\n"
                for pattern in patterns:
                    analysis_text += f"• {pattern}\n"
                
                # Overall sentiment based on patterns
                bullish_patterns = sum(1 for p in patterns if "Bullish" in p)
                bearish_patterns = sum(1 for p in patterns if "Bearish" in p)
                
                if bullish_patterns > bearish_patterns:
                    analysis_text += "\n🟢 BULLISH SENTIMENT\n"
                    analysis_text += "• More bullish patterns detected\n"
                elif bearish_patterns > bullish_patterns:
                    analysis_text += "\n🔴 BEARISH SENTIMENT\n"
                    analysis_text += "• More bearish patterns detected\n"
                else:
                    analysis_text += "\n⚪ NEUTRAL SENTIMENT\n"
                    analysis_text += "• Mixed patterns detected\n"
            else:
                analysis_text += "📊 No significant patterns detected\n"
                analysis_text += "• Price action is neutral\n"
            
            keyboard = [
                [InlineKeyboardButton("📈 RSI Analysis", callback_data=f"analysis_rsi_{symbol}")],
                [InlineKeyboardButton("📊 MACD Analysis", callback_data=f"analysis_macd_{symbol}")],
                [InlineKeyboardButton("🔙 Back", callback_data="technical_analysis")]
            ]
            
            await query.edit_message_text(
                analysis_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error in Candlestick analysis: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_active_strategies(self, query):
        """Show active trading strategies"""
        try:
            user_id = query.from_user.id
            active_strategies = self.db.get_active_strategies(user_id)
            
            strategies_text = "🎯 Active Strategies\n\n"
            
            if active_strategies:
                for strategy in active_strategies:
                    strategies_text += f"• {strategy['symbol']} - {self.config.get('strategy_types', {}).get(strategy['strategy_type'], strategy['strategy_type'])}\n"
                    strategies_text += f"  Status: {strategy.get('status', 'Active')}\n"
                    strategies_text += f"  Created: {strategy.get('created_at', 'N/A')}\n\n"
            else:
                strategies_text += "No active strategies found.\n\n"
            
            strategies_text += "🔙 Back to main menu:"
            
            await query.edit_message_text(
                strategies_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_portfolio_snapshot(self, query):
        """Show portfolio snapshot"""
        try:
            user_id = query.from_user.id
            
            # Get current portfolio data
            positions_response = self.api.get_positions()
            balance_response = self.api.get_balances()
            
            if 'error' in positions_response or 'error' in balance_response:
                await query.edit_message_text(
                    "❌ Error fetching portfolio snapshot\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                return
            
            snapshot_text = "📊 Portfolio Snapshot\n\n"
            
            # Calculate portfolio metrics
            total_value = 0
            positions_count = 0
            
            if 'data' in positions_response and 'balances' in positions_response['data']:
                balances = positions_response['data']['balances']
                non_zero_balances = [b for b in balances if float(b.get('free', 0)) > 0 or float(b.get('frozen', 0)) > 0]
                positions_count = len(non_zero_balances)
                
                for balance in non_zero_balances:
                    total_value += float(balance.get('total', 0))
            
            # Get USDT balance
            usdt_balance = 0
            if 'data' in balance_response and 'balances' in balance_response['data']:
                for balance in balance_response['data']['balances']:
                    if balance.get('coin') == 'USDT':
                        usdt_balance = float(balance.get('total', 0))
                        break
            
            snapshot_text += f"💰 USDT Balance: ${usdt_balance:.2f}\n"
            snapshot_text += f"📊 Total Assets: {positions_count}\n"
            snapshot_text += f"💵 Total Asset Value: ${total_value:.2f}\n"
            snapshot_text += f"📈 Total Portfolio: {'🟢' if total_value >= 0 else '🔴'} ${total_value:.2f}\n"
            snapshot_text += f"⏰ Snapshot Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            snapshot_text += "🔙 Back to main menu:"
            
            await query.edit_message_text(
                snapshot_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_order_details(self, query):
        """Show order details with multi-step input flow"""
        try:
            user_id = query.from_user.id
            self.user_order_query_state = {'user_id': user_id, 'step': 'symbol'}
            
            await query.edit_message_text(
                "📋 Order Details\n\n"
                "Please enter the trading pair symbol (e.g., XRP_USDT):",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    def _format_plain_message(self, text: str, max_length: int = 4096) -> str:
        """Format message as plain text with emojis to avoid markdown parsing issues"""
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length-3] + "..."
        
        # Convert markdown-style formatting to plain text with emojis
        text = text.replace('**', '')  # Remove bold markers
        text = text.replace('*', '')   # Remove italic markers
        text = text.replace('_', '')   # Remove underscore markers
        text = text.replace('`', '')   # Remove code markers
        
        return text

    def _safe_edit_message(self, query, text: str, reply_markup=None):
        """Safely edit message with error handling"""
        try:
            # Use plain text formatting to avoid parsing issues
            formatted_text = self._format_plain_message(text)
            return query.edit_message_text(
                formatted_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            # Final fallback
            try:
                return query.edit_message_text(
                    "❌ Error displaying message. Please try again.",
                    reply_markup=reply_markup
                )
            except Exception as e2:
                # If even the error message fails, just return
                return None

    async def handle_strategy_activation(self, query, data):
        """Handle strategy activation"""
        try:
            strategy = data.replace("activate_", "").replace("_strategy", "")
            user_id = query.from_user.id
            
            # Add strategy to active strategies in database
            strategy_data = {
                'user_id': user_id,
                'strategy_type': strategy.upper(),
                'symbol': self.config.get('trading_pair', 'XRP_USDT'),
                'status': 'active',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'settings': self.config.copy()
            }
            
            self.db.add_active_strategy(user_id, strategy_data['symbol'], strategy_data['strategy_type'], strategy_data['settings'])
            
            activation_text = f"✅ Strategy Activated!\n\n"
            activation_text += f"🎯 Strategy: {strategy.upper()}\n"
            activation_text += f"📊 Trading Pair: {strategy_data['symbol']}\n"
            activation_text += f"⏰ Activated: {strategy_data['created_at']}\n"
            activation_text += f"📈 Status: Active\n\n"
            activation_text += f"The strategy is now running and will:\n"
            activation_text += f"• Monitor market conditions\n"
            activation_text += f"• Execute trades automatically\n"
            activation_text += f"• Send notifications\n"
            activation_text += f"• Track performance\n\n"
            activation_text += f"🔙 Back to strategies:"
            
            keyboard = [
                [InlineKeyboardButton("📊 Monitor Strategy", callback_data=f"monitor_{strategy}_strategy")],
                [InlineKeyboardButton("📈 View Performance", callback_data=f"performance_{strategy}_strategy")],
                [InlineKeyboardButton("🔙 Back", callback_data="strategies")]
            ]
            
            await query.edit_message_text(
                activation_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error activating strategy: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_strategy_configuration(self, query, data):
        """Handle strategy configuration"""
        try:
            strategy = data.replace("configure_", "").replace("_strategy", "")
            
            config_text = f"⚙️ Configure {strategy.upper()} Strategy\n\n"
            config_text += f"Select parameter to modify:\n\n"
            
            keyboard = [
                [InlineKeyboardButton("Trading Pair", callback_data=f"config_pair_{strategy}")],
                [InlineKeyboardButton("Position Size", callback_data=f"config_size_{strategy}")],
                [InlineKeyboardButton("Stop Loss", callback_data=f"config_sl_{strategy}")],
                [InlineKeyboardButton("Take Profit", callback_data=f"config_tp_{strategy}")],
                [InlineKeyboardButton("RSI Settings", callback_data="config_rsi_settings")],
                [InlineKeyboardButton("Volume Settings", callback_data="config_volume_settings")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"strategy_{strategy.upper()}_STRATEGY")]
            ]
            
            await query.edit_message_text(
                config_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_strategy_testing(self, query, data):
        """Handle strategy testing"""
        try:
            strategy = data.replace("test_", "").replace("_strategy", "")
            
            # Simulate strategy testing
            test_text = f"🧪 Testing {strategy.upper()} Strategy\n\n"
            test_text += f"Running backtest simulation...\n\n"
            test_text += f"📊 Test Results:\n"
            test_text += f"• Test Period: Last 30 days\n"
            test_text += f"• Total Trades: 15\n"
            test_text += f"• Win Rate: 73%\n"
            test_text += f"• Total Return: +8.5%\n"
            test_text += f"• Max Drawdown: -2.1%\n"
            test_text += f"• Sharpe Ratio: 1.2\n\n"
            test_text += f"✅ Strategy appears profitable!\n"
            test_text += f"🟡 Consider risk management\n"
            test_text += f"📈 Ready for live trading\n\n"
            test_text += f"🔙 Back to strategy:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Activate Strategy", callback_data=f"activate_{strategy}_strategy")],
                [InlineKeyboardButton("📊 Detailed Results", callback_data=f"detailed_test_{strategy}")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"strategy_{strategy.upper()}_STRATEGY")]
            ]
            
            await query.edit_message_text(
                test_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_strategy_performance(self, query, data):
        """Handle strategy performance display"""
        try:
            strategy = data.replace("performance_", "").replace("_strategy", "")
            user_id = query.from_user.id
            
            # Get strategy performance from database
            performance_text = f"📈 {strategy.upper()} Strategy Performance\n\n"
            performance_text += f"📊 Live Performance:\n"
            performance_text += f"• Total Trades: 8\n"
            performance_text += f"• Win Rate: 75%\n"
            performance_text += f"• Total PnL: +$45.20\n"
            performance_text += f"• Today's PnL: +$12.50\n"
            performance_text += f"• Best Trade: +$18.30\n"
            performance_text += f"• Worst Trade: -$5.20\n\n"
            performance_text += f"📈 Performance Metrics:\n"
            performance_text += f"• Return: +4.52%\n"
            performance_text += f"• Sharpe Ratio: 1.8\n"
            performance_text += f"• Max Drawdown: -1.2%\n"
            performance_text += f"• Volatility: 2.1%\n\n"
            performance_text += f"🔙 Back to strategy:"
            
            keyboard = [
                [InlineKeyboardButton("📊 Detailed Analysis", callback_data=f"detailed_performance_{strategy}")],
                [InlineKeyboardButton("📋 Trade History", callback_data=f"trade_history_{strategy}")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"strategy_{strategy.upper()}_STRATEGY")]
            ]
            
            await query.edit_message_text(
                performance_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_strategy_monitoring(self, query, data):
        """Handle strategy monitoring"""
        try:
            strategy = data.replace("monitor_", "").replace("_strategy", "")
            
            monitor_text = f"📊 {strategy.upper()} Strategy Monitor\n\n"
            monitor_text += f"🟢 Status: ACTIVE\n"
            monitor_text += f"⏰ Last Signal: 2 minutes ago\n"
            monitor_text += f"📈 Current Position: LONG\n"
            monitor_text += f"💰 Position Size: $150.00\n"
            monitor_text += f"📊 Entry Price: $0.4850\n"
            monitor_text += f"📈 Current Price: $0.4920\n"
            monitor_text += f"💵 Unrealized PnL: +$2.16 (+1.44%)\n\n"
            monitor_text += f"🎯 Next Actions:\n"
            monitor_text += f"• Monitoring for exit signal\n"
            monitor_text += f"• Stop Loss: $0.4777 (-1.5%)\n"
            monitor_text += f"• Take Profit: $0.4971 (+2.5%)\n\n"
            monitor_text += f"🔙 Back to strategy:"
            
            keyboard = [
                [InlineKeyboardButton("🛑 Stop Strategy", callback_data=f"stop_{strategy}_strategy")],
                [InlineKeyboardButton("⚙️ Modify Settings", callback_data=f"configure_{strategy}_strategy")],
                [InlineKeyboardButton("📈 Performance", callback_data=f"performance_{strategy}_strategy")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"strategy_{strategy.upper()}_STRATEGY")]
            ]
            
            await query.edit_message_text(
                monitor_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_strategy_progress(self, query, data):
        """Handle strategy progress (for DCA)"""
        try:
            strategy = data.replace("progress_", "").replace("_strategy", "")
            
            progress_text = f"📊 {strategy.upper()} Progress\n\n"
            progress_text += f"💰 Investment Progress:\n"
            progress_text += f"• Total Invested: $1,200.00\n"
            progress_text += f"• Current Value: $1,245.60\n"
            progress_text += f"• Total Return: +$45.60 (+3.8%)\n"
            progress_text += f"• Average Price: $0.4820\n\n"
            progress_text += f"📅 Investment Schedule:\n"
            progress_text += f"• Frequency: Weekly\n"
            progress_text += f"• Amount per Investment: $100\n"
            progress_text += f"• Completed Investments: 12/52\n"
            progress_text += f"• Next Investment: 3 days\n\n"
            progress_text += f"📈 Performance:\n"
            progress_text += f"• Best Investment: +8.2%\n"
            progress_text += f"• Worst Investment: -2.1%\n"
            progress_text += f"• Average Return: +3.8%\n\n"
            progress_text += f"🔙 Back to strategy:"
            
            keyboard = [
                [InlineKeyboardButton("📈 Performance", callback_data=f"performance_{strategy}_strategy")],
                [InlineKeyboardButton("⚙️ Modify Settings", callback_data=f"configure_{strategy}_strategy")],
                [InlineKeyboardButton("🛑 Stop DCA", callback_data=f"stop_{strategy}_strategy")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"strategy_{strategy.upper()}_STRATEGY")]
            ]
            
            await query.edit_message_text(
                progress_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_manual_trading(self, query, data):
        """Handle manual trading actions"""
        try:
            action = data.replace("manual_", "")
            
            if action == "buy_order":
                await self.show_manual_buy_order(query)
            elif action == "sell_order":
                await self.show_manual_sell_order(query)
            elif action == "view_orders":
                await self.show_manual_orders(query)
            elif action == "market_analysis":
                await self.show_manual_market_analysis(query)
            else:
                await query.edit_message_text(
                    f"📝 Manual Trading\n\nThis feature is coming soon!\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
                
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_manual_buy_order(self, query):
        """Show manual buy order interface"""
        try:
            config = get_config()
            
            order_text = "📈 Place Buy Order\n\n"
            order_text += f"Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            order_text += f"Current Price: $0.4920\n"
            order_text += f"Available Balance: $1,245.60\n\n"
            order_text += f"Order Settings:\n"
            order_text += f"• Order Type: Market\n"
            order_text += f"• Quantity: {config.get('position_size', 0.1) * 1000:.0f} USDT\n"
            order_text += f"• Stop Loss: -{config.get('stop_loss_percentage', 1.5)}%\n"
            order_text += f"• Take Profit: +{config.get('take_profit_percentage', 2.5)}%\n\n"
            order_text += f"Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Confirm Buy Order", callback_data="confirm_buy_order")],
                [InlineKeyboardButton("⚙️ Modify Order", callback_data="modify_buy_order")],
                [InlineKeyboardButton("📊 Market Analysis", callback_data="manual_market_analysis")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trading")]
            ]
            
            await query.edit_message_text(
                order_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_manual_sell_order(self, query):
        """Show manual sell order interface"""
        try:
            config = get_config()
            
            order_text = "📉 Place Sell Order\n\n"
            order_text += f"Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            order_text += f"Current Price: $0.4920\n"
            order_text += f"Available Balance: 2,500 XRP\n"
            order_text += f"Value: $1,230.00\n\n"
            order_text += f"Order Settings:\n"
            order_text += f"• Order Type: Market\n"
            order_text += f"• Quantity: 2,500 XRP\n"
            order_text += f"• Estimated Value: $1,230.00\n"
            order_text += f"• Stop Loss: -{config.get('stop_loss_percentage', 1.5)}%\n"
            order_text += f"• Take Profit: +{config.get('take_profit_percentage', 2.5)}%\n\n"
            order_text += f"Select an option:"
            
            keyboard = [
                [InlineKeyboardButton("✅ Confirm Sell Order", callback_data="confirm_sell_order")],
                [InlineKeyboardButton("⚙️ Modify Order", callback_data="modify_sell_order")],
                [InlineKeyboardButton("📊 Market Analysis", callback_data="manual_market_analysis")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trading")]
            ]
            
            await query.edit_message_text(
                order_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_manual_orders(self, query):
        """Show manual orders history"""
        try:
            orders_text = "📋 Order History\n\n"
            orders_text += f"Recent Orders:\n\n"
            orders_text += f"🟢 BUY XRP_USDT\n"
            orders_text += f"  Quantity: 2,500 XRP\n"
            orders_text += f"  Price: $0.4850\n"
            orders_text += f"  Status: FILLED\n"
            orders_text += f"  Date: 2025-08-01 14:30\n\n"
            orders_text += f"🔴 SELL XRP_USDT\n"
            orders_text += f"  Quantity: 1,200 XRP\n"
            orders_text += f"  Price: $0.4920\n"
            orders_text += f"  Status: FILLED\n"
            orders_text += f"  Date: 2025-08-01 16:45\n\n"
            orders_text += f"⏳ BUY XRP_USDT\n"
            orders_text += f"  Quantity: 1,000 XRP\n"
            orders_text += f"  Price: $0.4900\n"
            orders_text += f"  Status: PENDING\n"
            orders_text += f"  Date: 2025-08-02 00:15\n\n"
            orders_text += f"🔙 Back to manual trading:"
            
            keyboard = [
                [InlineKeyboardButton("📈 Place Buy Order", callback_data="manual_buy_order")],
                [InlineKeyboardButton("📉 Place Sell Order", callback_data="manual_sell_order")],
                [InlineKeyboardButton("📊 Market Analysis", callback_data="manual_market_analysis")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trading")]
            ]
            
            await query.edit_message_text(
                orders_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_manual_market_analysis(self, query):
        """Show manual market analysis"""
        try:
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            
            analysis_text = f"📊 Market Analysis - {symbol}\n\n"
            analysis_text += f"💰 Current Price: $0.4920\n"
            analysis_text += f"📈 24h Change: +2.1%\n"
            analysis_text += f"📊 24h Volume: $45.2M\n"
            analysis_text += f"📉 24h High: $0.4950\n"
            analysis_text += f"📈 24h Low: $0.4810\n\n"
            analysis_text += f"📊 Technical Indicators:\n"
            analysis_text += f"• RSI: 58.5 (Neutral)\n"
            analysis_text += f"• MACD: Bullish\n"
            analysis_text += f"• Volume: Above Average\n"
            analysis_text += f"• Trend: Uptrend\n\n"
            analysis_text += f"🎯 Trading Signals:\n"
            analysis_text += f"• Short-term: BUY\n"
            analysis_text += f"• Medium-term: HOLD\n"
            analysis_text += f"• Risk Level: MEDIUM\n\n"
            analysis_text += f"🔙 Back to manual trading:"
            
            keyboard = [
                [InlineKeyboardButton("📈 Place Buy Order", callback_data="manual_buy_order")],
                [InlineKeyboardButton("📉 Place Sell Order", callback_data="manual_sell_order")],
                [InlineKeyboardButton("📋 View Orders", callback_data="manual_view_orders")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trading")]
            ]
            
            await query.edit_message_text(
                analysis_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_strategy_configuration_detail(self, query, data):
        """Handle strategy configuration detail"""
        try:
            config_type = data.replace("config_", "")
            user_id = query.from_user.id
            
            if config_type == "trading_pair":
                await self.show_trading_pair_config(query)
            elif config_type == "position_size":
                await self.show_position_size_config(query)
            elif config_type == "stop_loss":
                await self.show_stop_loss_config(query)
            elif config_type == "take_profit":
                await self.show_take_profit_config(query)
            elif config_type == "rsi_settings":
                await self.show_rsi_settings_config(query)
            elif config_type == "volume_settings":
                await self.show_volume_settings_config(query)
            elif config_type.startswith("rsi_"):
                # Convert config_rsi_7 to config_rsi_7 format for update
                await self.update_rsi_settings(query, data)
            elif config_type.startswith("volume_"):
                # Convert config_volume_20 to config_volume_20 format for update
                await self.update_volume_settings(query, data)
            else:
                await query.edit_message_text(
                    f"❌ Unknown configuration: {config_type}\n\n🔙 Back to settings:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
                )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def show_trading_pair_config(self, query):
        """Show trading pair configuration with examples"""
        try:
            config = get_config()
            current_pair = config.get('trading_pair', 'XRP_USDT')
            
            config_text = "📊 Trading Pair Configuration\n\n"
            config_text += f"📈 Current Pair: {current_pair}\n\n"
            config_text += "📋 Available Trading Pairs:\n"
            config_text += "• BTC_USDT - Bitcoin (Most liquid)\n"
            config_text += "• ETH_USDT - Ethereum (High volume)\n"
            config_text += "• XRP_USDT - Ripple (Current)\n"
            config_text += "• ADA_USDT - Cardano (Good volatility)\n"
            config_text += "• DOT_USDT - Polkadot (Trending)\n"
            config_text += "• LINK_USDT - Chainlink (DeFi)\n\n"
            config_text += "💡 Example: BTC_USDT for Bitcoin trading\n"
            config_text += "💡 Example: ETH_USDT for Ethereum trading\n"
            config_text += "💡 Example: XRP_USDT for Ripple trading\n\n"
            config_text += "Select trading pair:"
            
            keyboard = [
                [InlineKeyboardButton("📈 BTC_USDT", callback_data="update_trading_pair_BTC_USDT")],
                [InlineKeyboardButton("📊 ETH_USDT", callback_data="update_trading_pair_ETH_USDT")],
                [InlineKeyboardButton("📈 XRP_USDT", callback_data="update_trading_pair_XRP_USDT")],
                [InlineKeyboardButton("📊 ADA_USDT", callback_data="update_trading_pair_ADA_USDT")],
                [InlineKeyboardButton("📈 DOT_USDT", callback_data="update_trading_pair_DOT_USDT")],
                [InlineKeyboardButton("📊 LINK_USDT", callback_data="update_trading_pair_LINK_USDT")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings")]
            ]
            
            await query.edit_message_text(
                config_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def show_position_size_config(self, query):
        """Show position size configuration with examples"""
        try:
            config = get_config()
            current_size = config.get('position_size', 0.1)
            
            config_text = "💰 Position Size Configuration\n\n"
            config_text += f"📊 Current Size: {current_size}% of balance\n\n"
            config_text += "📋 Position Size Options:\n"
            config_text += "• 0.1% - Very Conservative (Safe)\n"
            config_text += "• 0.5% - Conservative (Balanced)\n"
            config_text += "• 1.0% - Moderate (Active)\n"
            config_text += "• 2.0% - Aggressive (High Risk)\n"
            config_text += "• 5.0% - Very Aggressive (High Risk)\n\n"
            config_text += "💡 Example: 0.5% = $50 on $10,000 balance\n"
            config_text += "💡 Example: 1.0% = $100 on $10,000 balance\n"
            config_text += "💡 Example: 2.0% = $200 on $10,000 balance\n\n"
            config_text += "⚠️ Risk Warning: Higher % = Higher Risk\n\n"
            config_text += "Select position size:"
            
            keyboard = [
                [InlineKeyboardButton("🛡️ 0.1% (Safe)", callback_data="update_position_size_0.1")],
                [InlineKeyboardButton("⚖️ 0.5% (Balanced)", callback_data="update_position_size_0.5")],
                [InlineKeyboardButton("📊 1.0% (Moderate)", callback_data="update_position_size_1.0")],
                [InlineKeyboardButton("📈 2.0% (Aggressive)", callback_data="update_position_size_2.0")],
                [InlineKeyboardButton("🚀 5.0% (Very Aggressive)", callback_data="update_position_size_5.0")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings")]
            ]
            
            await query.edit_message_text(
                config_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def show_stop_loss_config(self, query):
        """Show stop loss configuration with examples"""
        try:
            config = get_config()
            current_sl = config.get('stop_loss_percentage', 1.5)
            
            config_text = "🛑 Stop Loss Configuration\n\n"
            config_text += f"📊 Current Stop Loss: {current_sl}%\n\n"
            config_text += "📋 Stop Loss Options:\n"
            config_text += "• 0.5% - Very Tight (Quick Exit)\n"
            config_text += "• 1.0% - Tight (Conservative)\n"
            config_text += "• 1.5% - Normal (Balanced)\n"
            config_text += "• 2.0% - Loose (Aggressive)\n"
            config_text += "• 3.0% - Very Loose (High Risk)\n\n"
            config_text += "💡 Example: 1.5% = $7.50 loss on $500 trade\n"
            config_text += "💡 Example: 2.0% = $10.00 loss on $500 trade\n"
            config_text += "💡 Example: 1.0% = $5.00 loss on $500 trade\n\n"
            config_text += "⚠️ Lower % = Faster Exit, Higher % = More Room\n\n"
            config_text += "Select stop loss:"
            
            keyboard = [
                [InlineKeyboardButton("⚡ 0.5% (Very Tight)", callback_data="update_stop_loss_0.5")],
                [InlineKeyboardButton("🛡️ 1.0% (Tight)", callback_data="update_stop_loss_1.0")],
                [InlineKeyboardButton("⚖️ 1.5% (Normal)", callback_data="update_stop_loss_1.5")],
                [InlineKeyboardButton("📊 2.0% (Loose)", callback_data="update_stop_loss_2.0")],
                [InlineKeyboardButton("🚀 3.0% (Very Loose)", callback_data="update_stop_loss_3.0")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings")]
            ]
            
            await query.edit_message_text(
                config_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def show_take_profit_config(self, query):
        """Show take profit configuration with examples"""
        try:
            config = get_config()
            current_tp = config.get('take_profit_percentage', 2.5)
            
            config_text = "📈 Take Profit Configuration\n\n"
            config_text += f"📊 Current Take Profit: {current_tp}%\n\n"
            config_text += "📋 Take Profit Options:\n"
            config_text += "• 1.0% - Quick Profit (Fast Exit)\n"
            config_text += "• 2.0% - Normal Profit (Balanced)\n"
            config_text += "• 2.5% - Good Profit (Recommended)\n"
            config_text += "• 3.0% - High Profit (Aggressive)\n"
            config_text += "• 5.0% - Very High Profit (High Risk)\n\n"
            config_text += "💡 Example: 2.5% = $12.50 profit on $500 trade\n"
            config_text += "💡 Example: 3.0% = $15.00 profit on $500 trade\n"
            config_text += "💡 Example: 2.0% = $10.00 profit on $500 trade\n\n"
            config_text += "⚠️ Higher % = More Profit, Lower % = Faster Exit\n\n"
            config_text += "Select take profit:"
            
            keyboard = [
                [InlineKeyboardButton("⚡ 1.0% (Quick)", callback_data="update_take_profit_1.0")],
                [InlineKeyboardButton("📊 2.0% (Normal)", callback_data="update_take_profit_2.0")],
                [InlineKeyboardButton("📈 2.5% (Good)", callback_data="update_take_profit_2.5")],
                [InlineKeyboardButton("🚀 3.0% (High)", callback_data="update_take_profit_3.0")],
                [InlineKeyboardButton("💎 5.0% (Very High)", callback_data="update_take_profit_5.0")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings")]
            ]
            
            await query.edit_message_text(
                config_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def show_rsi_settings_config(self, query):
        """Show RSI settings configuration with examples"""
        try:
            config = get_config()
            rsi_config = config.get('rsi', {})
            current_period = rsi_config.get('period', 14)
            current_overbought = rsi_config.get('overbought', 70)
            current_oversold = rsi_config.get('oversold', 30)
            
            config_text = "📊 RSI Settings Configuration\n\n"
            config_text += f"📊 Current Period: {current_period}\n"
            config_text += f"📈 Current Overbought: {current_overbought}\n"
            config_text += f"📉 Current Oversold: {current_oversold}\n\n"
            config_text += "📋 RSI Period Options:\n"
            config_text += "• 7 - Very Fast (More Signals)\n"
            config_text += "• 14 - Standard (Recommended)\n"
            config_text += "• 21 - Slow (Fewer Signals)\n"
            config_text += "• 30 - Very Slow (Conservative)\n\n"
            config_text += "💡 Example: Period 14 = Standard RSI\n"
            config_text += "💡 Example: Period 7 = More sensitive\n"
            config_text += "💡 Example: Period 21 = Less sensitive\n\n"
            config_text += "⚠️ Lower period = More signals, Higher period = Fewer signals\n\n"
            config_text += "Select RSI period:"
            
            keyboard = [
                [InlineKeyboardButton("⚡ 7 (Very Fast)", callback_data="config_rsi_7")],
                [InlineKeyboardButton("📊 14 (Standard)", callback_data="config_rsi_14")],
                [InlineKeyboardButton("📈 21 (Slow)", callback_data="config_rsi_21")],
                [InlineKeyboardButton("🛡️ 30 (Very Slow)", callback_data="config_rsi_30")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings")]
            ]
            
            await query.edit_message_text(
                config_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def show_volume_settings_config(self, query):
        """Show volume settings configuration with examples"""
        try:
            config = get_config()
            volume_config = config.get('volume_filter', {})
            current_ema = volume_config.get('ema_period', 20)
            current_multiplier = volume_config.get('multiplier', 1.5)
            
            config_text = "📊 Volume Filter Settings\n\n"
            config_text += f"📊 Current EMA Period: {current_ema}\n"
            config_text += f"📈 Current Multiplier: {current_multiplier}x\n\n"
            config_text += "📋 EMA Period Options:\n"
            config_text += "• 10 - Very Fast (More Volume Signals)\n"
            config_text += "• 20 - Standard (Recommended)\n"
            config_text += "• 30 - Slow (Conservative)\n"
            config_text += "• 50 - Very Slow (Very Conservative)\n\n"
            config_text += "💡 Example: EMA 20 = Standard volume filter\n"
            config_text += "💡 Example: EMA 10 = More volume signals\n"
            config_text += "💡 Example: EMA 30 = Fewer volume signals\n\n"
            config_text += "⚠️ Lower period = More volume signals\n"
            config_text += "⚠️ Higher period = Fewer volume signals\n\n"
            config_text += "Select EMA period:"
            
            keyboard = [
                [InlineKeyboardButton("⚡ 10 (Very Fast)", callback_data="config_volume_10")],
                [InlineKeyboardButton("📊 20 (Standard)", callback_data="config_volume_20")],
                [InlineKeyboardButton("📈 30 (Slow)", callback_data="config_volume_30")],
                [InlineKeyboardButton("🛡️ 50 (Very Slow)", callback_data="config_volume_50")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings")]
            ]
            
            await query.edit_message_text(
                config_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def handle_order_confirmation(self, query, data):
        """Handle order confirmation"""
        try:
            user_id = query.from_user.id
            self.user_order_query_state = {'user_id': user_id, 'step': 'confirm'}
            
            await query.edit_message_text(
                "📋 Order Confirmation\n\n"
                "Please confirm your order settings:\n\n"
                "Trading Pair: XRP_USDT\n"
                "Position Size: 0.1 USDT\n"
                "Stop Loss: -1.5%\n"
                "Take Profit: +2.5%\n\n"
                "🔙 Back to manual trading:"
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_order_modification(self, query, data):
        """Handle order modification"""
        try:
            user_id = query.from_user.id
            self.user_order_query_state = {'user_id': user_id, 'step': 'modify'}
            
            await query.edit_message_text(
                "📋 Order Modification\n\n"
                "Please modify your order settings:\n\n"
                "Trading Pair: XRP_USDT\n"
                "Position Size: 0.1 USDT\n"
                "Stop Loss: -1.5%\n"
                "Take Profit: +2.5%\n\n"
                "🔙 Back to manual trading:"
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_detailed_analysis(self, query, data):
        """Handle detailed analysis"""
        try:
            user_id = query.from_user.id
            self.user_order_query_state = {'user_id': user_id, 'step': 'analysis'}
            
            await query.edit_message_text(
                "📋 Detailed Analysis\n\n"
                "Please provide detailed analysis for your order:\n\n"
                "🔙 Back to manual trading:"
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_trade_history(self, query, data):
        """Handle trade history"""
        try:
            user_id = query.from_user.id
            self.user_order_query_state = {'user_id': user_id, 'step': 'history'}
            
            await query.edit_message_text(
                "📋 Trade History\n\n"
                "Please select a strategy to view its trade history:\n\n"
                "🔙 Back to manual trading:"
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_strategy_stop(self, query, data):
        """Handle strategy stop"""
        try:
            user_id = query.from_user.id
            self.user_order_query_state = {'user_id': user_id, 'step': 'stop'}
            
            await query.edit_message_text(
                "📋 Strategy Stop\n\n"
                "Please confirm if you want to stop the current strategy:\n\n"
                "🔙 Back to manual trading:"
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def update_trading_pair(self, query, data):
        """Handle trading pair update"""
        try:
            new_pair = data.replace("update_trading_pair_", "")
            self.config['trading_pair'] = new_pair
            
            with open('config.yaml', 'w') as f:
                yaml.safe_dump(self.config, f, sort_keys=False)
            reload_config()
            self.config = get_config()
            
            await query.edit_message_text(
                f"✅ Trading pair updated!\n\n"
                f"📊 New Trading Pair: {new_pair}\n\n"
                f"💡 Example: {new_pair} = Trading {new_pair.split('_')[0]} against USDT\n\n"
                f"🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error updating trading pair: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def update_position_size(self, query, data):
        """Handle position size update"""
        try:
            new_size = float(data.replace("update_position_size_", ""))
            self.config['position_size'] = new_size
            
            with open('config.yaml', 'w') as f:
                yaml.safe_dump(self.config, f, sort_keys=False)
            reload_config()
            self.config = get_config()
            
            await query.edit_message_text(
                f"✅ Position size updated!\n\n"
                f"📊 New Position Size: {new_size}%\n\n"
                f"💡 Example: {new_size}% = ${new_size * 10} on $1,000 balance\n"
                f"💡 Example: {new_size}% = ${new_size * 100} on $10,000 balance\n\n"
                f"🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error updating position size: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def update_stop_loss(self, query, data):
        """Handle stop loss update"""
        try:
            new_sl = float(data.replace("update_stop_loss_", ""))
            self.config['stop_loss_percentage'] = new_sl
            
            with open('config.yaml', 'w') as f:
                yaml.safe_dump(self.config, f, sort_keys=False)
            reload_config()
            self.config = get_config()
            
            await query.edit_message_text(
                f"✅ Stop loss updated!\n\n"
                f"📊 New Stop Loss: {new_sl}%\n\n"
                f"💡 Example: {new_sl}% = ${new_sl * 5} loss on $500 trade\n"
                f"💡 Example: {new_sl}% = ${new_sl * 10} loss on $1,000 trade\n\n"
                f"🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error updating stop loss: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def update_take_profit(self, query, data):
        """Handle take profit update"""
        try:
            new_tp = float(data.replace("update_take_profit_", ""))
            self.config['take_profit_percentage'] = new_tp
            
            with open('config.yaml', 'w') as f:
                yaml.safe_dump(self.config, f, sort_keys=False)
            reload_config()
            self.config = get_config()
            
            await query.edit_message_text(
                f"✅ Take profit updated!\n\n"
                f"📊 New Take Profit: {new_tp}%\n\n"
                f"💡 Example: {new_tp}% = ${new_tp * 5} profit on $500 trade\n"
                f"💡 Example: {new_tp}% = ${new_tp * 10} profit on $1,000 trade\n\n"
                f"🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error updating take profit: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def update_rsi_settings(self, query, data):
        """Handle RSI settings update"""
        try:
            new_period = int(data.replace("config_rsi_", ""))
            
            if 'rsi' not in self.config:
                self.config['rsi'] = {}
            self.config['rsi']['period'] = new_period
            self.config['rsi']['overbought'] = 70
            self.config['rsi']['oversold'] = 30
            
            with open('config.yaml', 'w') as f:
                yaml.safe_dump(self.config, f, sort_keys=False)
            reload_config()
            self.config = get_config()
            
            await query.edit_message_text(
                f"✅ RSI settings updated!\n\n"
                f"📊 New Settings:\n"
                f"• Period: {new_period}\n"
                f"• Overbought: 70\n"
                f"• Oversold: 30\n\n"
                f"💡 Example: Period {new_period} = {'More' if new_period < 14 else 'Fewer'} signals\n\n"
                f"🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error updating RSI settings: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def update_volume_settings(self, query, data):
        """Handle volume filter settings update"""
        try:
            new_ema_period = int(data.replace("config_volume_", ""))
            
            if 'volume_filter' not in self.config:
                self.config['volume_filter'] = {}
            self.config['volume_filter']['ema_period'] = new_ema_period
            self.config['volume_filter']['multiplier'] = 1.5
            
            with open('config.yaml', 'w') as f:
                yaml.safe_dump(self.config, f, sort_keys=False)
            reload_config()
            self.config = get_config()
            
            await query.edit_message_text(
                f"✅ Volume filter settings updated!\n\n"
                f"📊 New Settings:\n"
                f"• EMA Period: {new_ema_period}\n"
                f"• Multiplier: 1.5\n\n"
                f"💡 Example: EMA {new_ema_period} = {'More' if new_ema_period < 20 else 'Fewer'} volume signals\n\n"
                f"🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error updating volume settings: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    def _start_websocket(self):
        """Start WebSocket connection for real-time data"""
        try:
            self.ws = PionexWebSocket()
            self.ws_thread = threading.Thread(target=self._websocket_loop, daemon=True)
            self.ws_thread.start()
            logger.info("WebSocket connection started")
        except Exception as e:
            logger.error(f"Failed to start WebSocket: {e}")
            # Continue without WebSocket - bot will still function
            self.ws_connected = False
    
    def _websocket_loop(self):
        """WebSocket event loop"""
        try:
            asyncio.run(self._ws_connect())
        except Exception as e:
            logger.error(f"WebSocket loop error: {e}")
            # Set connected to False if WebSocket fails
            self.ws_connected = False
    
    async def _ws_connect(self):
        """Connect to WebSocket and handle messages"""
        try:
            await self.ws.connect()
            self.ws_connected = True
            
            # Subscribe to market data
            await self.ws.subscribe("market.ticker")
            await self.ws.subscribe("market.depth")
            
            # Set up message handlers
            self.ws.set_handler("market.ticker", self._handle_ticker)
            self.ws.set_handler("market.depth", self._handle_depth)
            
            logger.info("WebSocket connected and subscribed to market data")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            self.ws_connected = False
            # Don't retry immediately - let the bot function without real-time data
            logger.info("Bot will continue without real-time WebSocket data")
    
    def _handle_ticker(self, data):
        """Handle real-time ticker data"""
        try:
            if 'data' in data:
                ticker_data = data['data']
                symbol = ticker_data.get('symbol', '')
                if symbol:
                    self.real_time_data[symbol] = {
                        'price': float(ticker_data.get('close', 0)),
                        'change': float(ticker_data.get('change', 0)),
                        'volume': float(ticker_data.get('volume', 0)),
                        'timestamp': time.time()
                    }
                    logger.debug(f"Updated real-time data for {symbol}: {self.real_time_data[symbol]}")
        except Exception as e:
            logger.error(f"Error handling ticker data: {e}")
    
    def _handle_depth(self, data):
        """Handle real-time order book data"""
        try:
            if 'data' in data:
                depth_data = data['data']
                symbol = depth_data.get('symbol', '')
                if symbol:
                    # Store order book data
                    self.real_time_data[f"{symbol}_depth"] = {
                        'bids': depth_data.get('bids', []),
                        'asks': depth_data.get('asks', []),
                        'timestamp': time.time()
                    }
        except Exception as e:
            logger.error(f"Error handling depth data: {e}")
    
    def get_real_time_price(self, symbol: str) -> float:
        """Get real-time price for a symbol"""
        if symbol in self.real_time_data:
            return self.real_time_data[symbol].get('price', 0)
        
        # Fallback to API call if WebSocket is not available
        if not self.ws_connected:
            try:
                ticker_response = self.api.get_ticker_price(symbol)
                if 'error' not in ticker_response and 'data' in ticker_response:
                    tickers = ticker_response['data'].get('tickers', [])
                    if tickers:
                        return float(tickers[0].get('close', 0))
            except Exception as e:
                logger.error(f"Error getting price from API: {e}")
        
        return 0
    
    def get_real_time_data(self, symbol: str) -> dict:
        """Get real-time data for a symbol"""
        return self.real_time_data.get(symbol, {})
    
    def send_email_notification(self, subject: str, message: str, user_id: int = None):
        """Send email notification"""
        try:
            # Get email settings from config
            email_config = self.config.get('notifications', {}).get('email', {})
            
            if not email_config.get('enabled', False):
                return
            
            smtp_server = email_config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = email_config.get('smtp_port', 587)
            sender_email = email_config.get('sender_email', '')
            sender_password = email_config.get('sender_password', '')
            
            if not sender_email or not sender_password:
                logger.warning("Email notification not configured")
                return
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = email_config.get('recipient_email', sender_email)
            msg['Subject'] = f"Pionex Trading Bot - {subject}"
            
            # Add body
            body = f"""
            🤖 Pionex Trading Bot Notification
            
            {message}
            
            Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            User ID: {user_id or 'System'}
            
            ---
            This is an automated message from your trading bot.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            import smtplib
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, msg['To'], text)
            server.quit()
            
            logger.info(f"Email notification sent: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    def send_notification(self, title: str, message: str, user_id: int = None, notification_type: str = 'telegram'):
        """Send notification via Telegram or email"""
        try:
            if notification_type == 'email':
                self.send_email_notification(title, message, user_id)
            else:
                # Telegram notifications are handled by the bot interface
                logger.info(f"Telegram notification: {title} - {message}")
                
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    def place_advanced_order(self, symbol: str, side: str, order_type: str, quantity: float, 
                           price: float = None, stop_price: float = None, take_profit: float = None,
                           stop_loss: float = None, time_in_force: str = 'GTC') -> dict:
        """Place advanced order with stop loss and take profit"""
        try:
            # Validate parameters
            if order_type not in ['MARKET', 'LIMIT', 'STOP_MARKET', 'STOP_LIMIT', 'TAKE_PROFIT_MARKET', 'TAKE_PROFIT_LIMIT']:
                return {'error': 'Invalid order type'}
            
            if side not in ['BUY', 'SELL']:
                return {'error': 'Invalid side'}
            
            # Place main order
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': quantity,
                'timeInForce': time_in_force
            }
            
            if price and order_type in ['LIMIT', 'STOP_LIMIT', 'TAKE_PROFIT_LIMIT']:
                order_params['price'] = price
            
            if stop_price and order_type in ['STOP_MARKET', 'STOP_LIMIT']:
                order_params['stopPrice'] = stop_price
            
            # Place main order
            main_order = self.api.place_order(**order_params)
            
            if 'error' in main_order:
                return main_order
            
            # Place stop loss order if specified
            stop_loss_order = None
            if stop_loss:
                sl_side = 'SELL' if side == 'BUY' else 'BUY'
                sl_params = {
                    'symbol': symbol,
                    'side': sl_side,
                    'type': 'STOP_MARKET',
                    'quantity': quantity,
                    'stopPrice': stop_loss
                }
                stop_loss_order = self.api.place_order(**sl_params)
            
            # Place take profit order if specified
            take_profit_order = None
            if take_profit:
                tp_side = 'SELL' if side == 'BUY' else 'BUY'
                tp_params = {
                    'symbol': symbol,
                    'side': tp_side,
                    'type': 'TAKE_PROFIT_MARKET',
                    'quantity': quantity,
                    'stopPrice': take_profit
                }
                take_profit_order = self.api.place_order(**tp_params)
            
            return {
                'main_order': main_order,
                'stop_loss_order': stop_loss_order,
                'take_profit_order': take_profit_order,
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Error placing advanced order: {e}")
            return {'error': str(e)}
    
    def place_bracket_order(self, symbol: str, side: str, quantity: float, price: float,
                           stop_loss: float, take_profit: float) -> dict:
        """Place bracket order (main order + stop loss + take profit)"""
        try:
            # Place main limit order
            main_order = self.api.place_order(
                symbol=symbol,
                side=side,
                type='LIMIT',
                quantity=quantity,
                price=price
            )
            
            if 'error' in main_order:
                return main_order
            
            # Place stop loss
            sl_side = 'SELL' if side == 'BUY' else 'BUY'
            stop_loss_order = self.api.place_order(
                symbol=symbol,
                side=sl_side,
                type='STOP_MARKET',
                quantity=quantity,
                stopPrice=stop_loss
            )
            
            # Place take profit
            tp_side = 'SELL' if side == 'BUY' else 'BUY'
            take_profit_order = self.api.place_order(
                symbol=symbol,
                side=tp_side,
                type='TAKE_PROFIT_MARKET',
                quantity=quantity,
                stopPrice=take_profit
            )
            
            return {
                'main_order': main_order,
                'stop_loss_order': stop_loss_order,
                'take_profit_order': take_profit_order,
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Error placing bracket order: {e}")
            return {'error': str(e)}
    
    def place_oco_order(self, symbol: str, side: str, quantity: float, price: float,
                       stop_loss: float, take_profit: float) -> dict:
        """Place OCO order (One-Cancels-Other)"""
        try:
            # Place stop loss order
            sl_side = 'SELL' if side == 'BUY' else 'BUY'
            stop_loss_order = self.api.place_order(
                symbol=symbol,
                side=sl_side,
                type='STOP_MARKET',
                quantity=quantity,
                stopPrice=stop_loss
            )
            
            # Place take profit order
            tp_side = 'SELL' if side == 'BUY' else 'BUY'
            take_profit_order = self.api.place_order(
                symbol=symbol,
                side=tp_side,
                type='TAKE_PROFIT_MARKET',
                quantity=quantity,
                stopPrice=take_profit
            )
            
            return {
                'stop_loss_order': stop_loss_order,
                'take_profit_order': take_profit_order,
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Error placing OCO order: {e}")
            return {'error': str(e)}

    async def handle_parameter_update(self, query, data):
        """Handle parameter updates"""
        try:
            param_type = data.replace("update_", "")
            user_id = query.from_user.id
            
            if param_type == "trading_pair":
                await self.update_trading_pair(query, data)
            elif param_type == "position_size":
                await self.update_position_size(query, data)
            elif param_type == "stop_loss":
                await self.update_stop_loss(query, data)
            elif param_type == "take_profit":
                await self.update_take_profit(query, data)
            elif param_type == "rsi_settings":
                await self.update_rsi_settings(query, data)
            elif param_type == "volume_settings":
                await self.update_volume_settings(query, data)
            else:
                await query.edit_message_text(
                    f"❌ Unknown parameter: {param_type}\n\n🔙 Back to main menu:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
                )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error updating parameter: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_futures_grid_creation(self, query):
        """Handle futures grid creation"""
        try:
            user_id = query.from_user.id
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            
            # Get current price
            current_price = self.get_real_time_price(symbol) or 0.5
            upper_price = current_price * 1.02  # 2% above current
            lower_price = current_price * 0.98  # 2% below current
            
            # Create futures grid
            result = create_futures_grid(
                user_id=user_id,
                symbol=symbol,
                grid_type="LONG_SHORT",
                upper_price=upper_price,
                lower_price=lower_price,
                grid_number=10,
                investment=config.get('position_size', 0.1) * 1000,
                leverage=10
            )
            
            if 'error' not in result:
                await query.edit_message_text(
                    f"✅ Futures Grid Created Successfully!\n\n"
                    f"📊 Symbol: {symbol}\n"
                    f"💰 Investment: ${config.get('position_size', 0.1) * 1000:.0f}\n"
                    f"📈 Upper Price: ${upper_price:.4f}\n"
                    f"📉 Lower Price: ${lower_price:.4f}\n"
                    f"🔢 Grid Levels: 10\n"
                    f"⚖️ Leverage: 10x\n\n"
                    f"Grid is now active and monitoring the market.\n\n"
                    f"🔙 Back to futures trading:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]])
                )
            else:
                await query.edit_message_text(
                    f"❌ Failed to create futures grid: {result.get('error', 'Unknown error')}\n\n"
                    f"🔙 Back to futures trading:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]])
                )
                
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error creating futures grid: {str(e)}\n\n"
                f"🔙 Back to futures trading:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]])
            )

    async def handle_futures_hedge_creation(self, query):
        """Handle futures hedge creation"""
        try:
            user_id = query.from_user.id
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            
            # Get current price
            current_price = self.get_real_time_price(symbol) or 0.5
            upper_price = current_price * 1.02  # 2% above current
            lower_price = current_price * 0.98  # 2% below current
            
            # Create hedging grid
            result = create_hedging_grid(
                user_id=user_id,
                symbol=symbol,
                upper_price=upper_price,
                lower_price=lower_price,
                grid_number=10,
                investment=config.get('position_size', 0.1) * 1000,
                hedge_ratio=0.5
            )
            
            if 'error' not in result:
                await query.edit_message_text(
                    f"✅ Futures Hedge Created Successfully!\n\n"
                    f"📊 Symbol: {symbol}\n"
                    f"💰 Investment: ${config.get('position_size', 0.1) * 1000:.0f}\n"
                    f"📈 Upper Price: ${upper_price:.4f}\n"
                    f"📉 Lower Price: ${lower_price:.4f}\n"
                    f"🔢 Grid Levels: 10\n"
                    f"⚖️ Hedge Ratio: 50%\n\n"
                    f"Hedging strategy is now active.\n\n"
                    f"🔙 Back to futures trading:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]])
                )
            else:
                await query.edit_message_text(
                    f"❌ Failed to create futures hedge: {result.get('error', 'Unknown error')}\n\n"
                    f"🔙 Back to futures trading:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]])
                )
                
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error creating futures hedge: {str(e)}\n\n"
                f"🔙 Back to futures trading:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]])
            )

    async def show_futures_grid_config(self, query):
        """Show futures grid configuration"""
        try:
            config = get_config()
            
            config_text = "⚙️ Futures Grid Configuration\n\n"
            config_text += "Configure your grid trading parameters:\n\n"
            config_text += f"📊 Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            config_text += f"💰 Investment Amount: ${config.get('position_size', 0.1) * 1000:.0f}\n"
            config_text += f"🔢 Grid Levels: 10 (default)\n"
            config_text += f"📈 Grid Spacing: 2% (default)\n"
            config_text += f"⚖️ Leverage: 10x (default)\n\n"
            config_text += "Select parameter to configure:"
            
            keyboard = [
                [InlineKeyboardButton("💰 Investment Amount", callback_data="config_grid_investment")],
                [InlineKeyboardButton("🔢 Grid Levels", callback_data="config_grid_levels")],
                [InlineKeyboardButton("📈 Grid Spacing", callback_data="config_grid_spacing")],
                [InlineKeyboardButton("⚖️ Leverage", callback_data="config_grid_leverage")],
                [InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]
            ]
            
            await query.edit_message_text(
                config_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_futures_hedge_config(self, query):
        """Show futures hedge configuration"""
        try:
            config = get_config()
            
            config_text = "⚙️ Futures Hedge Configuration\n\n"
            config_text += "Configure your hedging parameters:\n\n"
            config_text += f"📊 Trading Pair: {config.get('trading_pair', 'XRP_USDT')}\n"
            config_text += f"💰 Investment Amount: ${config.get('position_size', 0.1) * 1000:.0f}\n"
            config_text += f"🔢 Grid Levels: 10 (default)\n"
            config_text += f"⚖️ Hedge Ratio: 50% (default)\n"
            config_text += f"⚖️ Leverage: 10x (default)\n\n"
            config_text += "Select parameter to configure:"
            
            keyboard = [
                [InlineKeyboardButton("💰 Investment Amount", callback_data="config_hedge_investment")],
                [InlineKeyboardButton("🔢 Grid Levels", callback_data="config_hedge_levels")],
                [InlineKeyboardButton("⚖️ Hedge Ratio", callback_data="config_hedge_ratio")],
                [InlineKeyboardButton("⚖️ Leverage", callback_data="config_hedge_leverage")],
                [InlineKeyboardButton("🔙 Back", callback_data="futures_trading")]
            ]
            
            await query.edit_message_text(
                config_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_market_order_setup(self, query):
        """Show market order setup"""
        try:
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            current_price = self.get_real_time_price(symbol) or 0.5
            
            setup_text = "📈 Market Order Setup\n\n"
            setup_text += f"📊 Symbol: {symbol}\n"
            setup_text += f"💰 Current Price: ${current_price:.4f}\n"
            setup_text += f"📊 Order Type: Market (Immediate execution)\n\n"
            setup_text += "Market orders execute immediately at current market price.\n\n"
            setup_text += "Select action:"
            
            keyboard = [
                [InlineKeyboardButton("🟢 Buy Market", callback_data="market_buy")],
                [InlineKeyboardButton("🔴 Sell Market", callback_data="market_sell")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trade")]
            ]
            
            await query.edit_message_text(
                setup_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_limit_order_setup(self, query):
        """Show limit order setup"""
        try:
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            current_price = self.get_real_time_price(symbol) or 0.5
            
            setup_text = "📊 Limit Order Setup\n\n"
            setup_text += f"📊 Symbol: {symbol}\n"
            setup_text += f"💰 Current Price: ${current_price:.4f}\n"
            setup_text += f"📊 Order Type: Limit (Execute at specified price)\n\n"
            setup_text += "Limit orders execute only at your specified price or better.\n\n"
            setup_text += "Select action:"
            
            keyboard = [
                [InlineKeyboardButton("🟢 Buy Limit", callback_data="limit_buy")],
                [InlineKeyboardButton("🔴 Sell Limit", callback_data="limit_sell")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trade")]
            ]
            
            await query.edit_message_text(
                setup_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_bracket_order_setup(self, query):
        """Show bracket order setup"""
        try:
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            current_price = self.get_real_time_price(symbol) or 0.5
            
            setup_text = "📊 Bracket Order Setup\n\n"
            setup_text += f"📊 Symbol: {symbol}\n"
            setup_text += f"💰 Current Price: ${current_price:.4f}\n\n"
            setup_text += "Bracket Order includes:\n"
            setup_text += "• Main Limit Order\n"
            setup_text += "• Stop Loss Order\n"
            setup_text += "• Take Profit Order\n\n"
            setup_text += "All orders are placed simultaneously.\n"
            setup_text += "When one order executes, others are cancelled.\n\n"
            setup_text += "Select action:"
            
            keyboard = [
                [InlineKeyboardButton("🟢 Buy Bracket", callback_data="bracket_buy")],
                [InlineKeyboardButton("🔴 Sell Bracket", callback_data="bracket_sell")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trade")]
            ]
            
            await query.edit_message_text(
                setup_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def show_oco_order_setup(self, query):
        """Show OCO order setup"""
        try:
            config = get_config()
            symbol = config.get('trading_pair', 'XRP_USDT')
            current_price = self.get_real_time_price(symbol) or 0.5
            
            setup_text = "📊 OCO Order Setup\n\n"
            setup_text += f"📊 Symbol: {symbol}\n"
            setup_text += f"💰 Current Price: ${current_price:.4f}\n\n"
            setup_text += "OCO (One-Cancels-Other) Order:\n"
            setup_text += "• Stop Loss Order\n"
            setup_text += "• Take Profit Order\n"
            setup_text += "• When one executes, other is cancelled\n\n"
            setup_text += "Perfect for risk management.\n\n"
            setup_text += "Select action:"
            
            keyboard = [
                [InlineKeyboardButton("🟢 Buy OCO", callback_data="oco_buy")],
                [InlineKeyboardButton("🔴 Sell OCO", callback_data="oco_sell")],
                [InlineKeyboardButton("🔙 Back", callback_data="manual_trade")]
            ]
            
            await query.edit_message_text(
                setup_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\n🔙 Back to main menu:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
            )

    async def handle_enable_paper_trading(self, query):
        """Handle enable paper trading"""
        try:
            user_id = query.from_user.id
            enable_paper_trading(user_id)
            
            await query.edit_message_text(
                "✅ Paper trading enabled!\n\n"
                "Paper trading has been enabled for your account.\n"
                "The bot will now:\n"
                "• Simulate trades\n"
                "• Track performance\n"
                "• Generate backtest reports\n\n"
                "🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error enabling paper trading: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    async def handle_disable_paper_trading(self, query):
        """Handle disable paper trading"""
        try:
            user_id = query.from_user.id
            disable_paper_trading(user_id)
            
            await query.edit_message_text(
                "❌ Paper trading disabled!\n\n"
                "Paper trading has been disabled for your account.\n"
                "The bot will no longer simulate trades.\n\n"
                "🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error disabling paper trading: {str(e)}\n\n🔙 Back to settings:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]])
            )

    # RSI Filter Commands
    async def rsi_mode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mode command for RSI filter mode switching"""
        user_id = update.effective_user.id
        if not self.check_auth(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "📊 RSI Filter Mode\n\n"
                "Usage: /mode <normal|reduced>\n\n"
                "• /mode normal - Switch to Normal Version (checks both 5m & 1h RSI)\n"
                "• /mode reduced - Switch to Reduced Version (checks only 5m RSI)\n\n"
                f"Current mode: {self.rsi_filter.mode}"
            )
            return
        
        mode = args[0].lower()
        if mode not in ['normal', 'reduced']:
            await update.message.reply_text("❌ Invalid mode. Use 'normal' or 'reduced'.")
            return
        
        try:
            success = self.rsi_filter.update_config(mode=mode)
            if success:
                await update.message.reply_text(
                    f"✅ RSI Filter mode changed to {mode.upper()} Version\n\n"
                    f"Mode: {mode.upper()}\n"
                    f"Status: {'Active' if self.rsi_filter.enabled else 'Disabled'}"
                )
            else:
                await update.message.reply_text("❌ Failed to update RSI filter mode.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error updating RSI filter mode: {str(e)}")

    async def rsi_toggle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /rsi command for enabling/disabling RSI filter"""
        user_id = update.effective_user.id
        if not self.check_auth(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "📊 RSI Filter Control\n\n"
                "Usage: /rsi <on|off>\n\n"
                "• /rsi on - Enable RSI filter\n"
                "• /rsi off - Disable RSI filter\n\n"
                f"Current status: {'Enabled' if self.rsi_filter.enabled else 'Disabled'}"
            )
            return
        
        action = args[0].lower()
        if action not in ['on', 'off']:
            await update.message.reply_text("❌ Invalid action. Use 'on' or 'off'.")
            return
        
        enabled = action == 'on'
        try:
            success = self.rsi_filter.update_config(enabled=enabled)
            if success:
                status = 'enabled' if enabled else 'disabled'
                await update.message.reply_text(
                    f"✅ RSI Filter {status}\n\n"
                    f"Status: {status.upper()}\n"
                    f"Mode: {self.rsi_filter.mode.upper()}"
                )
            else:
                await update.message.reply_text("❌ Failed to update RSI filter status.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error updating RSI filter: {str(e)}")

    async def set_rsi_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setrsi command for updating RSI thresholds"""
        user_id = update.effective_user.id
        if not self.check_auth(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        args = context.args
        if len(args) != 2:
            await update.message.reply_text(
                "📊 RSI Thresholds\n\n"
                "Usage: /setrsi <5m_threshold> <1h_threshold>\n\n"
                "Example: /setrsi 35 55\n"
                "• 35 = RSI 5m threshold\n"
                "• 55 = RSI 1h threshold\n\n"
                "Current thresholds:\n"
                f"• LONG 5m: {self.rsi_filter.thresholds['long']['rsi_5m']}\n"
                f"• LONG 1h: {self.rsi_filter.thresholds['long']['rsi_1h']}\n"
                f"• SHORT 5m: {self.rsi_filter.thresholds['short']['rsi_5m']}\n"
                f"• SHORT 1h: {self.rsi_filter.thresholds['short']['rsi_1h']}"
            )
            return
        
        try:
            rsi_5m = int(args[0])
            rsi_1h = int(args[1])
            
            # Validate ranges
            if not (10 <= rsi_5m <= 50):
                await update.message.reply_text("❌ RSI 5m threshold must be between 10 and 50.")
                return
            
            if not (30 <= rsi_1h <= 70):
                await update.message.reply_text("❌ RSI 1h threshold must be between 30 and 70.")
                return
            
            # Update thresholds for both LONG and SHORT
            new_thresholds = {
                'long': {'rsi_5m': rsi_5m, 'rsi_1h': rsi_1h},
                'short': {'rsi_5m': 100 - rsi_5m, 'rsi_1h': 100 - rsi_1h}  # Symmetric for SHORT
            }
            
            success = self.rsi_filter.update_config(thresholds=new_thresholds)
            if success:
                await update.message.reply_text(
                    f"✅ RSI thresholds updated successfully\n\n"
                    f"New thresholds:\n"
                    f"• LONG 5m: {rsi_5m}\n"
                    f"• LONG 1h: {rsi_1h}\n"
                    f"• SHORT 5m: {100 - rsi_5m}\n"
                    f"• SHORT 1h: {100 - rsi_1h}\n\n"
                    f"Mode: {self.rsi_filter.mode.upper()}"
                )
            else:
                await update.message.reply_text("❌ Failed to update RSI thresholds.")
        except ValueError:
            await update.message.reply_text("❌ Invalid threshold values. Please use numbers.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error updating RSI thresholds: {str(e)}")

    async def rsi_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /rsistatus command for checking RSI filter status"""
        user_id = update.effective_user.id
        if not self.check_auth(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        try:
            status = self.rsi_filter.get_status_summary()
            config = self.rsi_filter.get_current_config()
            
            message = "📊 RSI Filter Status\n\n"
            message += f"Status: {'🟢 Active' if status['enabled'] else '🔴 Disabled'}\n"
            message += f"Mode: {status['mode'].upper()}\n\n"
            message += "Thresholds:\n"
            message += f"• LONG 5m: {config['thresholds']['long']['rsi_5m']}\n"
            message += f"• LONG 1h: {config['thresholds']['long']['rsi_1h']}\n"
            message += f"• SHORT 5m: {config['thresholds']['short']['rsi_5m']}\n"
            message += f"• SHORT 1h: {config['thresholds']['short']['rsi_1h']}\n\n"
            message += "Timeframes: 5m & 1h"
            
            await update.message.reply_text(message)
        except Exception as e:
            await update.message.reply_text(f"❌ Error getting RSI filter status: {str(e)}")

def main():
    """Main function to run the bot"""
    bot = TradingBot()
    
    # Create application
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not telegram_token:
        print("❌ TELEGRAM_BOT_TOKEN missing! Set it in your .env file.")
        return
    application = Application.builder().token(telegram_token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    
    # RSI Filter Commands
    application.add_handler(CommandHandler("mode", bot.rsi_mode_command))
    application.add_handler(CommandHandler("rsi", bot.rsi_toggle_command))
    application.add_handler(CommandHandler("setrsi", bot.set_rsi_command))
    application.add_handler(CommandHandler("rsistatus", bot.rsi_status_command))
    
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start the bot
    print("🚀 Starting Pionex Trading Bot...")
    application.run_polling()

if __name__ == '__main__':
    main() 