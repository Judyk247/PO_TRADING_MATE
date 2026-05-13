"""
PO TRADING MATE - Pocket Option API Client
Email/Password authentication, market data, trade execution
"""

# ============================================================
# DNS FIX: Force using Google's public DNS to resolve pocketoption.com
# This fixes the "Failed to resolve 'pocketoption.com'" error on Render
# ============================================================
import dns.resolver
# Override default DNS resolver to use Google's public DNS servers
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '8.8.4.4']

# ============================================================
# Regular imports
# ============================================================
import json
import time
import uuid
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum

# Force socket to use the DNS resolver we just configured
import socket
import dns.message
import dns.query

# Patch socket.getaddrinfo to use our custom DNS resolver
original_getaddrinfo = socket.getaddrinfo

def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Override DNS resolution to use Google DNS"""
    try:
        # If it's pocketoption.com, resolve it manually
        if 'pocketoption.com' in host:
            # Use dnspython to resolve with Google DNS
            query = dns.message.make_query(host, dns.rdatatype.A)
            response = dns.query.udp(query, '8.8.8.8', timeout=5)
            if response.answer:
                for answer in response.answer:
                    for item in answer.items:
                        if item.rdtype == dns.rdatatype.A:
                            ip_address = str(item)
                            # Call original with the resolved IP
                            return original_getaddrinfo(ip_address, port, family, type, proto, flags)
    except Exception as e:
        print(f"DNS resolution fallback error: {e}")
    
    # Fall back to original
    return original_getaddrinfo(host, port, family, type, proto, flags)

# Apply the patch
socket.getaddrinfo = patched_getaddrinfo

import websocket
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderDirection(Enum):
    """Trade direction for Pocket Option"""
    CALL = "call"
    PUT = "put"


@dataclass
class Asset:
    """Trading asset"""
    symbol: str
    name: str
    payout: float
    min_amount: float
    max_amount: float
    is_active: bool = True


@dataclass
class Candle:
    """OHLC candle data"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass
class OrderResult:
    """Trade result"""
    order_id: str
    success: bool
    profit: float
    is_win: bool
    amount: float
    direction: str
    asset: str


class PocketOptionClient:
    """Pocket Option API Client"""
    
    BASE_URL = "https://pocketoption.com"
    WS_URL = "wss://ws.pocketoption.com/ws"
    
    def __init__(self, email: str = None, password: str = None, is_demo: bool = True):
        self.email = email
        self.password = password
        self.is_demo = is_demo
        self._ssid = None
        self._ws = None
        self._connected = False
        self._balance = 0.0
        
        self._candle_callbacks: List[Callable] = []
        self._order_callbacks: List[Callable] = []
        self._connect_callbacks: List[Callable] = []
    
    def authenticate(self) -> bool:
        """Authenticate with Pocket Option"""
        try:
            # Create session with timeout
            session = requests.Session()
            session.timeout = 30
            
            # First request to get cookies
            print(f"🔍 Connecting to {self.BASE_URL}...")
            response = session.get(f"{self.BASE_URL}/en", headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }, timeout=30)
            
            print(f"📡 Got response: HTTP {response.status_code}")
            
            login_data = {
                "email": self.email,
                "password": self.password,
                "action": "login",
                "remember": "1",
                "accountType": "1" if self.is_demo else "0"
            }
            
            print(f"🔐 Attempting login for {self.email}...")
            # FIXED: Changed from /api/v1/login to /login
            response = session.post(
                f"{self.BASE_URL}/login",
                json=login_data,
                headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Login failed: HTTP {response.status_code}")
                print(f"❌ Login failed: HTTP {response.status_code}")
                return False
            
            result = response.json()
            if result.get("status") != "success":
                logger.error(f"Login failed: {result.get('message', 'Unknown error')}")
                print(f"❌ Login failed: {result.get('message', 'Unknown error')}")
                return False
            
            for cookie in session.cookies:
                if cookie.name == "ssid":
                    self._ssid = cookie.value
                    break
            
            if not self._ssid:
                logger.error("Failed to extract SSID")
                print("❌ Failed to extract SSID from cookies")
                return False
            
            self._balance = self.get_balance()
            logger.info(f"✅ Authenticated! Balance: ${self._balance:.2f}")
            print(f"✅ Authenticated! Balance: ${self._balance:.2f}")
            return True
            
        except requests.exceptions.Timeout:
            logger.error("Authentication timeout - server took too long to respond")
            print("❌ Authentication timeout - server took too long to respond")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            print(f"❌ Connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            print(f"❌ Authentication error: {e}")
            return False
    
    def connect_websocket(self) -> bool:
        """Establish WebSocket connection"""
        if not self._ssid:
            logger.error("No SSID. Run authenticate() first.")
            return False
        
        try:
            ws_url = f"{self.WS_URL}?ssid={self._ssid}"
            print(f"🔌 Connecting WebSocket to {self.WS_URL}...")
            
            self._ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            ws_thread = threading.Thread(target=self._ws.run_forever, daemon=True)
            ws_thread.start()
            
            # Wait for connection
            time.sleep(3)
            if self._connected:
                print("✅ WebSocket connected successfully")
            else:
                print("⚠️ WebSocket connection may have failed")
            return self._connected
            
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            print(f"❌ WebSocket error: {e}")
            return False
    
    def _on_open(self, ws):
        self._connected = True
        logger.info("✅ WebSocket connected")
        print("✅ WebSocket connection opened")
        
        # Send initial subscription
        subscribe_msg = {
            "name": "subscribe",
            "msg": {"session": self._ssid}
        }
        ws.send(json.dumps(subscribe_msg))
        
        for callback in self._connect_callbacks:
            callback(True)
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if isinstance(data, list) and len(data) >= 2:
                msg_type = data[0]
                msg_data = data[1]
                
                if msg_type == 42:  # Candle data
                    self._handle_candle(msg_data)
                elif msg_type == 43:  # Order result
                    self._handle_order_result(msg_data)
        except:
            pass
    
    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")
        print(f"❌ WebSocket error: {error}")
        self._connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        logger.info("WebSocket disconnected")
        print("🔌 WebSocket disconnected")
        self._connected = False
        
        for callback in self._connect_callbacks:
            callback(False)
    
    def _handle_candle(self, data: Dict):
        """Process candle data"""
        if not isinstance(data, dict):
            return
        
        try:
            asset = data.get("asset", "")
            timeframe = data.get("timeframe", 0)
            candle_data = data.get("candle", {})
            
            if candle_data:
                candle = Candle(
                    timestamp=candle_data.get("timestamp", 0),
                    open=float(candle_data.get("open", 0)),
                    high=float(candle_data.get("high", 0)),
                    low=float(candle_data.get("low", 0)),
                    close=float(candle_data.get("close", 0)),
                    volume=candle_data.get("volume", 0)
                )
                
                for callback in self._candle_callbacks:
                    callback(asset, timeframe, candle)
        except Exception as e:
            logger.error(f"Error parsing candle: {e}")
    
    def _handle_order_result(self, data: Dict):
        """Process order result"""
        try:
            result = OrderResult(
                order_id=data.get("order_id", ""),
                success=data.get("success", False),
                profit=float(data.get("profit", 0)),
                is_win=data.get("win", False),
                amount=float(data.get("amount", 0)),
                direction=data.get("direction", ""),
                asset=data.get("asset", "")
            )
            
            for callback in self._order_callbacks:
                callback(result)
        except Exception as e:
            logger.error(f"Error parsing order result: {e}")
    
    def subscribe_candles(self, asset: str, timeframe: int, callback: Callable):
        """Subscribe to candle updates"""
        self._candle_callbacks.append(callback)
        
        if self._ws and self._connected:
            subscribe_msg = {
                "name": "subscribe-candles",
                "msg": {"asset": asset, "timeframe": timeframe}
            }
            self._ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to {asset} {timeframe}s candles")
            print(f"📊 Subscribed to {asset} {timeframe}s candles")
    
    def get_assets(self) -> List[Asset]:
        """Get all assets with 85%+ payout"""
        try:
            print("📊 Fetching available assets...")
            response = requests.get(
                f"{self.BASE_URL}/api/v1/assets",
                headers={"Cookie": f"ssid={self._ssid}", "X-Requested-With": "XMLHttpRequest"},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"⚠️ Assets API returned HTTP {response.status_code}")
                return []
            
            assets_data = response.json()
            assets = []
            
            for asset_data in assets_data:
                payout = float(asset_data.get("payout", 0))
                if payout >= 85:
                    assets.append(Asset(
                        symbol=asset_data.get("symbol", ""),
                        name=asset_data.get("name", ""),
                        payout=payout,
                        min_amount=float(asset_data.get("min_amount", 1)),
                        max_amount=float(asset_data.get("max_amount", 1000)),
                        is_active=asset_data.get("active", True)
                    ))
            
            print(f"✅ Loaded {len(assets)} assets with 85%+ payout")
            return sorted(assets, key=lambda x: x.payout, reverse=True)
            
        except Exception as e:
            logger.error(f"Error fetching assets: {e}")
            print(f"❌ Error fetching assets: {e}")
            return []
    
    def buy(self, asset: str, amount: float, direction: OrderDirection, duration: int) -> Optional[OrderResult]:
        """Execute buy order"""
        if not self._connected or not self._ws:
            logger.error("WebSocket not connected")
            return None
        
        order_id = str(uuid.uuid4())
        
        order_msg = {
            "name": "buy",
            "msg": {
                "order_id": order_id,
                "asset": asset,
                "amount": amount,
                "action": direction.value,
                "duration": duration,
                "accountType": 1 if self.is_demo else 0
            }
        }
        
        self._ws.send(json.dumps(order_msg))
        logger.info(f"📊 Order: {direction.value} ${amount} on {asset}")
        print(f"📊 Order placed: {direction.value} ${amount} on {asset}")
        
        return OrderResult(
            order_id=order_id,
            success=True,
            profit=0,
            is_win=False,
            amount=amount,
            direction=direction.value,
            asset=asset
        )
    
    def get_balance(self) -> float:
        """Get current balance"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/api/v1/balance",
                headers={"Cookie": f"ssid={self._ssid}", "X-Requested-With": "XMLHttpRequest"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self._balance = float(data.get("balance", self._balance))
            
            return self._balance
            
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return self._balance
    
    def on_order_result(self, callback: Callable):
        self._order_callbacks.append(callback)
    
    def on_connect(self, callback: Callable):
        self._connect_callbacks.append(callback)
    
    def disconnect(self):
        if self._ws:
            self._ws.close()
        self._connected = False
        logger.info("Disconnected")
        print("🔌 Disconnected from Pocket Option")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def balance(self) -> float:
        return self._balance
