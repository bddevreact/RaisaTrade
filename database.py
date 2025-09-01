#!/usr/bin/env python3
"""
Database Management for Pionex Trading Bot
Copyright © 2024 Telegram-Airdrop-Bot
https://github.com/Telegram-Airdrop-Bot/autotradebot

Database operations for storing trading data, user settings, and logs.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class Database:
    """Simple file-based database for storing trading data"""
    
    def __init__(self, db_dir='data'):
        """Initialize database with file-based storage"""
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(exist_ok=True)
        
        # Initialize data files
        self.trades_file = self.db_dir / 'trades.json'
        self.settings_file = self.db_dir / 'settings.json'
        self.portfolio_file = self.db_dir / 'portfolio.json'
        self.logs_file = self.db_dir / 'logs.json'
        
        # Create files if they don't exist
        self._init_files()
        
        logger.info(f"Database initialized in {self.db_dir}")
    
    def _init_files(self):
        """Initialize database files with empty structures"""
        files_to_init = {
            self.trades_file: [],
            self.settings_file: {},
            self.portfolio_file: {},
            self.logs_file: []
        }
        
        for file_path, default_data in files_to_init.items():
            if not file_path.exists():
                self._write_json(file_path, default_data)
                logger.info(f"Created {file_path}")
    
    def _read_json(self, file_path):
        """Read JSON data from file"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None
    
    def _write_json(self, file_path, data):
        """Write JSON data to file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Error writing {file_path}: {e}")
            return False
    
    def add_trade(self, trade_data):
        """Add a new trade to the database"""
        try:
            trades = self._read_json(self.trades_file) or []
            
            # Add timestamp if not present
            if 'timestamp' not in trade_data:
                trade_data['timestamp'] = datetime.now().isoformat()
            
            trades.append(trade_data)
            
            # Keep only last 1000 trades to prevent file from growing too large
            if len(trades) > 1000:
                trades = trades[-1000:]
            
            if self._write_json(self.trades_file, trades):
                logger.info(f"Trade added: {trade_data.get('symbol', 'Unknown')}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding trade: {e}")
            return False
    
    def get_recent_trades(self, limit=50):
        """Get recent trades from database"""
        try:
            trades = self._read_json(self.trades_file) or []
            return trades[-limit:] if trades else []
        except Exception as e:
            logger.error(f"Error getting recent trades: {e}")
            return []
    
    def get_trades_by_symbol(self, symbol, limit=50):
        """Get trades for a specific symbol"""
        try:
            trades = self._read_json(self.trades_file) or []
            symbol_trades = [trade for trade in trades if trade.get('symbol') == symbol]
            return symbol_trades[-limit:] if symbol_trades else []
        except Exception as e:
            logger.error(f"Error getting trades for {symbol}: {e}")
            return []
    
    def save_user_setting(self, user_id, key, value):
        """Save user setting"""
        try:
            settings = self._read_json(self.settings_file) or {}
            
            if str(user_id) not in settings:
                settings[str(user_id)] = {}
            
            settings[str(user_id)][key] = value
            
            if self._write_json(self.settings_file, settings):
                logger.info(f"Setting saved for user {user_id}: {key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving user setting: {e}")
            return False
    
    def get_user_settings(self, user_id):
        """Get all settings for a user"""
        try:
            settings = self._read_json(self.settings_file) or {}
            return settings.get(str(user_id), {})
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            return {}
    
    def update_user_setting(self, user_id, key, value):
        """Update user setting (alias for save_user_setting)"""
        return self.save_user_setting(user_id, key, value)
    
    def update_user_settings(self, user_id, settings_dict):
        """Update multiple user settings at once"""
        try:
            settings = self._read_json(self.settings_file) or {}
            
            if str(user_id) not in settings:
                settings[str(user_id)] = {}
            
            # Update multiple settings
            for key, value in settings_dict.items():
                settings[str(user_id)][key] = value
            
            if self._write_json(self.settings_file, settings):
                logger.info(f"Updated {len(settings_dict)} settings for user {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating user settings: {e}")
            return False
    
    def save_portfolio_snapshot(self, portfolio_data):
        """Save portfolio snapshot"""
        try:
            portfolio = self._read_json(self.portfolio_file) or {}
            
            # Add timestamp
            portfolio_data['timestamp'] = datetime.now().isoformat()
            
            # Keep only last 100 snapshots
            snapshots = portfolio.get('snapshots', [])
            snapshots.append(portfolio_data)
            
            if len(snapshots) > 100:
                snapshots = snapshots[-100:]
            
            portfolio['snapshots'] = snapshots
            portfolio['last_updated'] = datetime.now().isoformat()
            
            if self._write_json(self.portfolio_file, portfolio):
                logger.info("Portfolio snapshot saved")
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving portfolio snapshot: {e}")
            return False
    
    def get_portfolio_history(self, limit=50):
        """Get portfolio history"""
        try:
            portfolio = self._read_json(self.portfolio_file) or {}
            snapshots = portfolio.get('snapshots', [])
            return snapshots[-limit:] if snapshots else []
        except Exception as e:
            logger.error(f"Error getting portfolio history: {e}")
            return []
    
    def add_log(self, log_data):
        """Add log entry"""
        try:
            logs = self._read_json(self.logs_file) or []
            
            # Add timestamp if not present
            if 'timestamp' not in log_data:
                log_data['timestamp'] = datetime.now().isoformat()
            
            logs.append(log_data)
            
            # Keep only last 1000 logs
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            if self._write_json(self.logs_file, logs):
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding log: {e}")
            return False
    
    def get_recent_logs(self, limit=100):
        """Get recent logs"""
        try:
            logs = self._read_json(self.logs_file) or []
            return logs[-limit:] if logs else []
        except Exception as e:
            logger.error(f"Error getting recent logs: {e}")
            return []
    
    def clear_old_data(self, days=30):
        """Clear old data to prevent file bloat"""
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            # Clear old trades
            trades = self._read_json(self.trades_file) or []
            trades = [trade for trade in trades if self._parse_timestamp(trade.get('timestamp', 0)) > cutoff_date]
            self._write_json(self.trades_file, trades)
            
            # Clear old logs
            logs = self._read_json(self.logs_file) or []
            logs = [log for log in logs if self._parse_timestamp(log.get('timestamp', 0)) > cutoff_date]
            self._write_json(self.logs_file, logs)
            
            logger.info(f"Cleared data older than {days} days")
            return True
        except Exception as e:
            logger.error(f"Error clearing old data: {e}")
            return False
    
    def _parse_timestamp(self, timestamp):
        """Parse timestamp to unix timestamp"""
        try:
            if isinstance(timestamp, (int, float)):
                return timestamp
            elif isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.timestamp()
            else:
                return 0
        except Exception:
            return 0
    
    def get_database_stats(self):
        """Get database statistics"""
        try:
            stats = {
                'trades_count': len(self._read_json(self.trades_file) or []),
                'settings_count': len(self._read_json(self.settings_file) or {}),
                'portfolio_snapshots': len(self._read_json(self.portfolio_file) or {}),
                'logs_count': len(self._read_json(self.logs_file) or []),
                'db_directory': str(self.db_dir),
                'last_updated': datetime.now().isoformat()
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
    
    def backup_database(self, backup_dir='backup'):
        """Create backup of database files"""
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            files_to_backup = [
                self.trades_file,
                self.settings_file,
                self.portfolio_file,
                self.logs_file
            ]
            
            for file_path in files_to_backup:
                if file_path.exists():
                    backup_file = backup_path / f"{file_path.stem}_{timestamp}.json"
                    with open(file_path, 'r', encoding='utf-8') as src:
                        with open(backup_file, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
            
            logger.info(f"Database backup created in {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False 