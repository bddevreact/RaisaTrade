import threading
import time
import logging
import psutil
import os
from datetime import datetime, timedelta
from pathlib import Path
import json
import sys

from config_loader import get_config
from auto_trader import get_auto_trader, restart_auto_trading

class Watchdog:
    def __init__(self):
        self.config = get_config()
        self.logger = self._setup_logging()
        self.is_running = False
        self.monitoring_thread = None
        self.stop_event = threading.Event()
        
        # Health tracking
        self.last_heartbeat = {}
        self.failure_count = {}
        self.restart_history = []
        
        # Process monitoring
        self.process_id = os.getpid()
        self.start_time = datetime.now()
        
        # Configuration
        self.heartbeat_interval = self.config.get('watchdog', {}).get('heartbeat_interval', 60)
        self.max_failures = self.config.get('watchdog', {}).get('max_failures', 3)
        self.auto_restart = self.config.get('watchdog', {}).get('auto_restart', True)
        self.memory_threshold = self.config.get('watchdog', {}).get('memory_threshold', 80)  # MB
        self.cpu_threshold = self.config.get('watchdog', {}).get('cpu_threshold', 80)  # %
        
    def _setup_logging(self):
        """Setup watchdog logging"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        logger = logging.getLogger('Watchdog')
        logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(log_dir / 'watchdog.log', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def start(self):
        """Start the watchdog monitoring"""
        if self.is_running:
            self.logger.warning("Watchdog is already running")
            return
        
        self.is_running = True
        self.stop_event.clear()
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        self.logger.info("Watchdog started")
    
    def stop(self):
        """Stop the watchdog monitoring"""
        if not self.is_running:
            self.logger.warning("Watchdog is not running")
            return
        
        self.is_running = False
        self.stop_event.set()
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        self.logger.info("Watchdog stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running and not self.stop_event.is_set():
            try:
                # Check system health
                self._check_system_health()
                
                # Check bot instances
                self._check_bot_instances()
                
                # Check API connectivity
                self._check_api_connectivity()
                
                # Log heartbeat
                self._log_heartbeat()
                
                # Wait for next check
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Wait before retry
    
    def _check_system_health(self):
        """Check system resources"""
        try:
            # Memory usage
            process = psutil.Process(self.process_id)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # CPU usage
            cpu_percent = process.cpu_percent(interval=1)
            
            # Check thresholds
            if memory_mb > self.memory_threshold:
                self.logger.warning(f"High memory usage: {memory_mb:.1f}MB > {self.memory_threshold}MB")
                self._handle_system_warning("High memory usage", f"Memory: {memory_mb:.1f}MB")
            
            if cpu_percent > self.cpu_threshold:
                self.logger.warning(f"High CPU usage: {cpu_percent:.1f}% > {self.cpu_threshold}%")
                self._handle_system_warning("High CPU usage", f"CPU: {cpu_percent:.1f}%")
            
            # Log system stats
            self.logger.debug(f"System stats - Memory: {memory_mb:.1f}MB, CPU: {cpu_percent:.1f}%")
            
        except Exception as e:
            self.logger.error(f"Error checking system health: {e}")
    
    def _check_bot_instances(self):
        """Check all bot instances for health"""
        try:
            from auto_trader import auto_traders
            
            for user_id, trader in auto_traders.items():
                status = trader.get_status()
                
                # Check if bot is supposed to be running but isn't
                if status.get('auto_trading_enabled', False) and not status.get('is_running', False):
                    self.logger.warning(f"Bot instance {user_id} is enabled but not running")
                    self._handle_bot_failure(user_id, "Bot stopped unexpectedly")
                
                # Check for excessive restarts
                restart_count = status.get('restart_count', 0)
                if restart_count > 10:  # More than 10 restarts
                    self.logger.warning(f"Bot instance {user_id} has excessive restarts: {restart_count}")
                    self._handle_bot_failure(user_id, f"Excessive restarts: {restart_count}")
                
                # Update heartbeat
                self.last_heartbeat[user_id] = datetime.now()
                
        except Exception as e:
            self.logger.error(f"Error checking bot instances: {e}")
    
    def _check_api_connectivity(self):
        """Check API connectivity"""
        try:
            from pionex_api import PionexAPI
            
            api = PionexAPI()
            balances = api.get_balances()
            if 'error' in balances:
                self.logger.error(f"API connectivity issue: {balances['error']}")
                self._handle_api_failure(balances['error'])
            else:
                self.logger.debug("API connectivity OK")
                
        except Exception as e:
            self.logger.error(f"Error checking API connectivity: {e}")
            self._handle_api_failure(str(e))
    
    def _handle_system_warning(self, warning_type: str, details: str):
        """Handle system warnings"""
        self.logger.warning(f"System warning: {warning_type} - {details}")
        
        # Send notification if configured
        if self.config.get('notifications', {}).get('telegram', False):
            self._send_notification("⚠️ System Warning", f"{warning_type}: {details}")
    
    def _handle_bot_failure(self, user_id: int, reason: str):
        """Handle bot instance failure"""
        self.logger.error(f"Bot failure for user {user_id}: {reason}")
        
        # Increment failure count
        if user_id not in self.failure_count:
            self.failure_count[user_id] = 0
        self.failure_count[user_id] += 1
        
        # Check if we should restart
        if self.failure_count[user_id] >= self.max_failures:
            self.logger.warning(f"Max failures reached for user {user_id}, restarting bot")
            self._restart_bot(user_id, reason)
            self.failure_count[user_id] = 0  # Reset counter
        else:
            self.logger.info(f"Failure count for user {user_id}: {self.failure_count[user_id]}/{self.max_failures}")
    
    def _handle_api_failure(self, error: str):
        """Handle API failures"""
        self.logger.error(f"API failure: {error}")
        
        # Send notification
        if self.config.get('notifications', {}).get('telegram', False):
            self._send_notification("❌ API Failure", f"API connectivity issue: {error}")
    
    def _restart_bot(self, user_id: int, reason: str):
        """Restart a bot instance"""
        try:
            if self.auto_restart:
                self.logger.info(f"Auto-restarting bot for user {user_id}")
                restart_auto_trading(user_id)
                
                # Log restart
                restart_record = {
                    'user_id': user_id,
                    'reason': reason,
                    'timestamp': datetime.now().isoformat(),
                    'auto_restart': True
                }
                self.restart_history.append(restart_record)
                
                # Send notification
                if self.config.get('notifications', {}).get('telegram', False):
                    self._send_notification("🔄 Auto Restart", f"Bot restarted for user {user_id} due to: {reason}")
            else:
                self.logger.warning(f"Auto-restart disabled, manual intervention required for user {user_id}")
                
        except Exception as e:
            self.logger.error(f"Error restarting bot for user {user_id}: {e}")
    
    def _log_heartbeat(self):
        """Log heartbeat status"""
        try:
            heartbeat_data = {
                'timestamp': datetime.now().isoformat(),
                'uptime': (datetime.now() - self.start_time).total_seconds(),
                'active_instances': len(self.last_heartbeat),
                'failure_counts': self.failure_count,
                'restart_count': len(self.restart_history)
            }
            
            # Save heartbeat to file
            heartbeat_file = Path('logs') / 'heartbeat.json'
            with open(heartbeat_file, 'w') as f:
                json.dump(heartbeat_data, f, indent=2)
            
            self.logger.debug(f"Heartbeat logged: {len(self.last_heartbeat)} active instances")
            
        except Exception as e:
            self.logger.error(f"Error logging heartbeat: {e}")
    
    def _send_notification(self, title: str, message: str):
        """Send notification (placeholder for now)"""
        self.logger.info(f"Notification: {title} - {message}")
    
    def get_status(self) -> dict:
        """Get watchdog status"""
        return {
            'is_running': self.is_running,
            'uptime': (datetime.now() - self.start_time).total_seconds(),
            'active_instances': len(self.last_heartbeat),
            'failure_counts': self.failure_count,
            'restart_history_count': len(self.restart_history),
            'last_heartbeat': {str(k): v.isoformat() for k, v in self.last_heartbeat.items()},
            'config': {
                'heartbeat_interval': self.heartbeat_interval,
                'max_failures': self.max_failures,
                'auto_restart': self.auto_restart,
                'memory_threshold': self.memory_threshold,
                'cpu_threshold': self.cpu_threshold
            }
        }
    
    def get_health_report(self) -> dict:
        """Get detailed health report"""
        try:
            process = psutil.Process(self.process_id)
            memory_info = process.memory_info()
            
            return {
                'system': {
                    'memory_usage_mb': memory_info.rss / 1024 / 1024,
                    'cpu_percent': process.cpu_percent(),
                    'threads': process.num_threads(),
                    'open_files': len(process.open_files()),
                    'connections': len(process.connections())
                },
                'watchdog': self.get_status(),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting health report: {e}")
            return {'error': str(e)}

# Global watchdog instance
watchdog_instance = None

def start_watchdog():
    """Start the watchdog"""
    global watchdog_instance
    if watchdog_instance is None:
        watchdog_instance = Watchdog()
    watchdog_instance.start()
    return watchdog_instance

def stop_watchdog():
    """Stop the watchdog"""
    global watchdog_instance
    if watchdog_instance:
        watchdog_instance.stop()
        watchdog_instance = None

def get_watchdog_status() -> dict:
    """Get watchdog status"""
    global watchdog_instance
    if watchdog_instance:
        return watchdog_instance.get_status()
    return {'is_running': False}

def get_health_report() -> dict:
    """Get health report"""
    global watchdog_instance
    if watchdog_instance:
        return watchdog_instance.get_health_report()
    return {'error': 'Watchdog not running'} 