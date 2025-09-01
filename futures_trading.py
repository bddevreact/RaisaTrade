import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

# Global futures trading state
_futures_trader_instance = None
_futures_trading_enabled = False
_futures_positions = {}
_futures_orders = {}

def get_futures_trader():
    """Get the futures trader instance"""
    global _futures_trader_instance
    if _futures_trader_instance is None:
        _futures_trader_instance = FuturesTrader()
    return _futures_trader_instance

def create_futures_grid(symbol: str, grid_config: Dict) -> Dict:
    """Create a futures grid trading strategy"""
    try:
        logger.info(f"Creating futures grid for {symbol} with config: {grid_config}")
        
        # Validate grid configuration
        required_fields = ['upper_price', 'lower_price', 'grid_number', 'investment_amount']
        for field in required_fields:
            if field not in grid_config:
                return {'success': False, 'error': f'Missing required field: {field}'}
        
        # Calculate grid parameters
        upper_price = float(grid_config['upper_price'])
        lower_price = float(grid_config['lower_price'])
        grid_number = int(grid_config['grid_number'])
        investment_amount = float(grid_config['investment_amount'])
        
        if upper_price <= lower_price:
            return {'success': False, 'error': 'Upper price must be greater than lower price'}
        
        if grid_number < 2:
            return {'success': False, 'error': 'Grid number must be at least 2'}
        
        # Calculate grid intervals
        price_interval = (upper_price - lower_price) / (grid_number - 1)
        grid_prices = [lower_price + i * price_interval for i in range(grid_number)]
        
        # Calculate order sizes
        order_size = investment_amount / grid_number
        
        # Create grid orders
        grid_orders = []
        for i, price in enumerate(grid_prices):
            order = {
                'symbol': symbol,
                'side': 'BUY' if i % 2 == 0 else 'SELL',
                'price': price,
                'quantity': order_size / price,
                'order_type': 'LIMIT',
                'grid_level': i + 1,
                'status': 'PENDING'
            }
            grid_orders.append(order)
        
        # Store grid configuration
        grid_id = f"grid_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        _futures_positions[grid_id] = {
            'symbol': symbol,
            'config': grid_config,
            'orders': grid_orders,
            'created_at': datetime.now().isoformat(),
            'status': 'ACTIVE'
        }
        
        logger.info(f"Futures grid created with ID: {grid_id}")
        return {
            'success': True,
            'grid_id': grid_id,
            'orders': grid_orders,
            'message': f'Futures grid created successfully with {len(grid_orders)} orders'
        }
        
    except Exception as e:
        logger.error(f"Error creating futures grid: {e}")
        return {'success': False, 'error': str(e)}

def create_hedging_grid(symbol: str, hedge_config: Dict) -> Dict:
    """Create a hedging grid strategy"""
    try:
        logger.info(f"Creating hedging grid for {symbol} with config: {hedge_config}")
        
        # Validate hedge configuration
        required_fields = ['base_position', 'hedge_ratio', 'price_range']
        for field in required_fields:
            if field not in hedge_config:
                return {'success': False, 'error': f'Missing required field: {field}'}
        
        base_position = float(hedge_config['base_position'])
        hedge_ratio = float(hedge_config['hedge_ratio'])
        price_range = float(hedge_config['price_range'])
        
        # Create hedging orders
        hedge_orders = []
        current_price = 50000  # Example price - in real implementation, get from market
        
        # Create buy orders below current price
        for i in range(5):
            price = current_price - (i + 1) * price_range
            quantity = base_position * hedge_ratio / price
            order = {
                'symbol': symbol,
                'side': 'BUY',
                'price': price,
                'quantity': quantity,
                'order_type': 'LIMIT',
                'hedge_level': i + 1,
                'status': 'PENDING'
            }
            hedge_orders.append(order)
        
        # Create sell orders above current price
        for i in range(5):
            price = current_price + (i + 1) * price_range
            quantity = base_position * hedge_ratio / price
            order = {
                'symbol': symbol,
                'side': 'SELL',
                'price': price,
                'quantity': quantity,
                'order_type': 'LIMIT',
                'hedge_level': i + 1,
                'status': 'PENDING'
            }
            hedge_orders.append(order)
        
        # Store hedge configuration
        hedge_id = f"hedge_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        _futures_positions[hedge_id] = {
            'symbol': symbol,
            'config': hedge_config,
            'orders': hedge_orders,
            'created_at': datetime.now().isoformat(),
            'status': 'ACTIVE',
            'type': 'hedge'
        }
        
        logger.info(f"Hedging grid created with ID: {hedge_id}")
        return {
            'success': True,
            'hedge_id': hedge_id,
            'orders': hedge_orders,
            'message': f'Hedging grid created successfully with {len(hedge_orders)} orders'
        }
        
    except Exception as e:
        logger.error(f"Error creating hedging grid: {e}")
        return {'success': False, 'error': str(e)}

def get_dynamic_limits(symbol: str) -> Dict:
    """Get dynamic trading limits for a symbol"""
    try:
        # In a real implementation, this would fetch limits from the exchange
        # For now, return simulated limits
        limits = {
            'symbol': symbol,
            'min_order_size': 0.001,
            'max_order_size': 1000.0,
            'min_price_increment': 0.01,
            'max_leverage': 125,
            'min_margin': 0.01,
            'max_position_size': 10000.0,
            'price_precision': 2,
            'quantity_precision': 6
        }
        
        return {'success': True, 'limits': limits}
    except Exception as e:
        logger.error(f"Error getting dynamic limits: {e}")
        return {'success': False, 'error': str(e)}

def check_liquidation_risk(symbol: str, position_size: float, leverage: float) -> Dict:
    """Check liquidation risk for a position"""
    try:
        # Simulate liquidation risk calculation
        current_price = 50000  # Example price
        margin_ratio = 0.1  # Example margin ratio
        maintenance_margin = 0.05  # Example maintenance margin
        
        # Calculate liquidation price
        liquidation_price = current_price * (1 - 1/leverage + maintenance_margin)
        
        # Calculate risk level
        price_distance = abs(current_price - liquidation_price) / current_price
        risk_level = 'LOW' if price_distance > 0.2 else 'MEDIUM' if price_distance > 0.1 else 'HIGH'
        
        risk_assessment = {
            'symbol': symbol,
            'position_size': position_size,
            'leverage': leverage,
            'current_price': current_price,
            'liquidation_price': liquidation_price,
            'margin_ratio': margin_ratio,
            'risk_level': risk_level,
            'price_distance': price_distance,
            'recommendation': 'REDUCE_POSITION' if risk_level == 'HIGH' else 'MONITOR'
        }
        
        return {'success': True, 'risk_assessment': risk_assessment}
    except Exception as e:
        logger.error(f"Error checking liquidation risk: {e}")
        return {'success': False, 'error': str(e)}

def get_strategy_status(strategy_id: str = None) -> Dict:
    """Get status of futures trading strategies"""
    try:
        if strategy_id:
            if strategy_id in _futures_positions:
                return {'success': True, 'strategy': _futures_positions[strategy_id]}
            else:
                return {'success': False, 'error': f'Strategy {strategy_id} not found'}
        
        # Return all strategies
        strategies = []
        for strategy_id, strategy_data in _futures_positions.items():
            strategies.append({
                'id': strategy_id,
                'symbol': strategy_data['symbol'],
                'type': strategy_data.get('type', 'grid'),
                'status': strategy_data['status'],
                'created_at': strategy_data['created_at'],
                'order_count': len(strategy_data['orders'])
            })
        
        return {'success': True, 'strategies': strategies}
    except Exception as e:
        logger.error(f"Error getting strategy status: {e}")
        return {'success': False, 'error': str(e)}

def get_performance_metrics(strategy_id: str = None) -> Dict:
    """Get performance metrics for futures trading"""
    try:
        # Simulate performance metrics
        metrics = {
            'total_pnl': 1250.75,
            'daily_pnl': 125.30,
            'total_trades': 89,
            'win_rate': 0.72,
            'max_drawdown': -0.08,
            'sharpe_ratio': 1.45,
            'profit_factor': 2.1,
            'avg_trade_duration': '2.5 hours',
            'best_trade': 450.25,
            'worst_trade': -125.50
        }
        
        if strategy_id:
            # Add strategy-specific metrics
            metrics['strategy_id'] = strategy_id
            metrics['strategy_type'] = 'futures_grid'
        
        return {'success': True, 'metrics': metrics}
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return {'success': False, 'error': str(e)}

class FuturesTrader:
    def __init__(self):
        self.enabled = False
        self.positions = {}
        self.orders = {}
    
    def create_grid(self, symbol: str, config: Dict) -> Dict:
        """Create a futures grid"""
        return create_futures_grid(symbol, config)
    
    def create_hedge(self, symbol: str, config: Dict) -> Dict:
        """Create a hedging strategy"""
        return create_hedging_grid(symbol, config)
    
    def get_limits(self, symbol: str) -> Dict:
        """Get trading limits"""
        return get_dynamic_limits(symbol)
    
    def check_risk(self, symbol: str, position_size: float, leverage: float) -> Dict:
        """Check liquidation risk"""
        return check_liquidation_risk(symbol, position_size, leverage)
    
    def get_status(self, strategy_id: str = None) -> Dict:
        """Get strategy status"""
        return get_strategy_status(strategy_id)
    
    def get_performance(self, strategy_id: str = None) -> Dict:
        """Get performance metrics"""
        return get_performance_metrics(strategy_id)
    
    def close_position(self, symbol: str) -> Dict:
        """Close a futures position"""
        try:
            logger.info(f"Closing position for {symbol}")
            # In a real implementation, this would close the position
            return {'success': True, 'message': f'Position closed for {symbol}'}
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {'success': False, 'error': str(e)}
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """Cancel all orders for a symbol"""
        try:
            logger.info(f"Canceling all orders for {symbol}")
            # In a real implementation, this would cancel all orders
            return {'success': True, 'message': f'All orders canceled for {symbol}'}
        except Exception as e:
            logger.error(f"Error canceling orders: {e}")
            return {'success': False, 'error': str(e)} 