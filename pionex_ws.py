import asyncio
import json
import logging
import websockets
from typing import Callable, Dict, Any, Optional

class PionexWebSocket:
    def __init__(self, api_key=None, secret_key=None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.ws = None
        self.connected = False
        self.logger = logging.getLogger(__name__)
        
        # Updated WebSocket URLs based on Pionex documentation
        self.BASE_URLS = [
            "wss://ws.pionex.com/ws",
            "wss://api.pionex.com/ws",
            "wss://api.pionex.com/stream",
            "wss://ws.pionex.com"
        ]
        
        self.current_url_index = 0
        self.reconnect_delay = 5
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        self.subscriptions = set()
        self.handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}

    async def connect(self):
        """Connect to WebSocket with fallback to REST API"""
        try:
            url = self.BASE_URLS[self.current_url_index]
            self.logger.info(f"Connecting to {url}")
            
            # Simplified headers for better compatibility
            headers = {
                'User-Agent': 'PionexTradingBot/1.0',
                'Accept': '*/*'
            }
            
            if self.api_key:
                headers['X-API-Key'] = self.api_key
            
            self.ws = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.connected = True
            self.reconnect_attempts = 0
            self.logger.info(f"Successfully connected to {url}")
            return True
            
        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {str(e)}")
            self.connected = False
            
            # Try next URL
            self.current_url_index = (self.current_url_index + 1) % len(self.BASE_URLS)
            
            if self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                self.logger.info(f"Retrying connection in {self.reconnect_delay} seconds...")
                await asyncio.sleep(self.reconnect_delay)
                return await self.connect()
            else:
                self.logger.warning("All WebSocket URLs failed. Falling back to REST API.")
                return False

    async def disconnect(self):
        self._stop = True
        if self.ws:
            await self.ws.close()
        self.connected = False

    async def subscribe(self, channel: str, params: Dict[str, Any] = None):
        if not self.connected:
            self.logger.warning("WebSocket not connected. Subscription will be sent after reconnect.")
        sub_msg = {"event": "subscribe", "channel": channel}
        if params:
            sub_msg.update(params)
        self.subscriptions.add(json.dumps(sub_msg))
        if self.ws and self.connected:
            await self.ws.send(json.dumps(sub_msg))
            self.logger.info(f"Subscribed to {channel} {params if params else ''}")

    async def unsubscribe(self, channel: str, params: Dict[str, Any] = None):
        unsub_msg = {"event": "unsubscribe", "channel": channel}
        if params:
            unsub_msg.update(params)
        if self.ws and self.connected:
            await self.ws.send(json.dumps(unsub_msg))
            self.logger.info(f"Unsubscribed from {channel} {params if params else ''}")
        self.subscriptions.discard(json.dumps(unsub_msg))

    async def _resubscribe_all(self):
        for sub in self.subscriptions:
            await self.ws.send(sub)
            self.logger.info(f"Resubscribed: {sub}")

    async def _on_message(self, message: str):
        try:
            data = json.loads(message)
            channel = data.get("channel")
            if channel and channel in self.handlers:
                await self.handlers[channel](data)
            else:
                self.logger.debug(f"Received message: {data}")
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    def set_handler(self, channel: str, handler: Callable[[Dict[str, Any]], None]):
        self.handlers[channel] = handler

# Example usage (to be integrated in main bot):
# ws = PionexWebSocket(api_key, secret_key)
# asyncio.run(ws.connect())
# await ws.subscribe('market.ticker', {"symbol": "BTCUSDT"}) 