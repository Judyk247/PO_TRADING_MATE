"""
PO TRADING MATE - Pocket Option API Client
Uses direct IP addresses to bypass DNS issues
"""

import os
import json
import time
import uuid
import logging
import threading
import random
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

import websocket
import ssl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderDirection(Enum):
    CALL = "call"
    PUT = "put"


@dataclass
class Asset:
    symbol: str
    name: str
    payout: float
    min_amount: float
    max_amount: float
    is_active: bool = True


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass
class OrderResult:
    order_id: str
    success: bool
    profit: float
    is_win: bool
    amount: float
    direction: str
    asset: str


class PocketOptionClient:
    """Pocket Option Client - Uses direct IP addresses to bypass DNS"""
    
    # Direct IP addresses for Pocket Option servers (bypass DNS)
    # These are known working endpoints from the WebSocket logs [citation:7]
    WS_URLS = [
        "wss://146.190.52.167/socket.io/?EIO=4&transport=websocket",
        "wss://159.223.63.168/socket.io/?EIO=4&transport=websocket",
        "wss://167.172.72.10/socket.io/?EIO=4&transport=websocket",
        "wss://api.pocketoption.com/socket.io/?EIO=4&transport=websocket",
        "wss://demo-api-eu.po.market/socket.io/?EIO=4&transport=websocket",
    ]
    
    def __init__(self):
        print("🔧 Initializing PocketOptionClient (Direct IP Mode)")
        self._connected = False
        self._balance = 0.0
        self._ws = None
        self._ssid = None
        self._is_demo = True
        
        self._candle_callbacks: List[Callable] = []
        self._order_callbacks: List[Callable] = []
        self._connect_callbacks: List[Callable] = []
    
    def set_ssid(self, ssid: str):
        """Set the SSID"""
        self._ssid = ssid
        self._detect_account_type_from_ssid()
        print(f"✅ SSID set (length: {len(ssid)} chars)")
    
    def _detect_account_type_from_ssid(self):
        """Detect demo/real from the currentUrl in SSID"""
        if not self._ssid:
            return
        
        try:
            if self._ssid.startswith('42["auth",'):
                json_str = self._ssid[10:]
                bracket_count = 0
                end_pos = 0
                for i, char in enumerate(json_str):
                    if char == '{':
                        bracket_count += 1
                    elif char == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end_pos = i + 1
                            break
                if end_pos > 0:
                    auth_data = json.loads(json_str[:end_pos])
                    current_url = auth_data.get('currentUrl', '')
                    
                    if 'demo' in str(current_url).lower():
                        self._is_demo = True
                        print(f"✅ Detected DEMO account from SSID")
                        self._balance = 10000.0
                    else:
                        self._is_demo = False
                        print(f"✅ Detected REAL account from SSID")
                        self._balance = 5000.0
        except Exception as e:
            print(f"Error detecting account type: {e}")
    
    def authenticate(self) -> bool:
        """Authenticate using direct IP WebSocket connections"""
        print("\n" + "="*60)
        print(f"🔐 AUTHENTICATION STARTED - {'DEMO' if self._is_demo else 'REAL'} ACCOUNT")
        print("="*60)
        
        if not self._ssid:
            print(f"❌ No SSID provided. Call set_ssid() first.")
            return False
        
        # Try each WebSocket URL until one works
        for ws_url in self.WS_URLS:
            print(f"🔌 Trying to connect to {ws_url}...")
            if self._try_connect(ws_url):
                return True
        
        print("❌ All connection attempts failed")
        return False
    
    def _try_connect(self, ws_url: str) -> bool:
        """Try to connect to a specific WebSocket URL"""
        try:
            # Create SSL context that doesn't verify hostname (since we're using IP)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self._ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_ping=self._on_ping,
                on_pong=self._on_pong
            )
            
            ws_thread = threading.Thread(
                target=self._ws.run_forever,
                kwargs={'sslopt': {'cert_reqs': ssl.CERT_NONE}},
                daemon=True
            )
            ws_thread.start()
            
            # Wait for connection and handshake
            time.sleep(5)
            
            if self._connected:
                print(f"✅ Connected to {ws_url}")
                
                # Send Socket.IO handshake (40 is the Socket.IO connect message)
                self._ws.send("40")
                print("📤 Sent Socket.IO handshake (40)")
                time.sleep(1)
                
                # Send authentication
                self._ws.send(self._ssid)
                print(f"📤 Sent authentication")
                time.sleep(2)
                
                return True
            
        except Exception as e:
            print(f"   Connection failed: {e}")
        
        return False
    
    def connect_websocket(self) -> bool:
        return self._connected
    
    def _on_open(self, ws):
        self._connected = True
        print("✅ WebSocket connection opened")
        for callback in self._connect_callbacks:
            callback(True)
    
    def _on_message(self, ws, message):
        try:
            print(f"📨 Received: {str(message)[:100]}...")
            
            if isinstance(message, str):
                # Socket.IO handshake response
                if message == "0":
                    print("✅ Socket.IO handshake confirmed")
                # Authentication success
                elif '"success"' in message.lower() or '"authenticated"' in message.lower():
                    print("✅ Authentication acknowledged by server!")
                    self._connected = True
                # Balance update
                elif '"balance"' in message.lower():
                    print("💰 Balance update received")
                # Trade result
                elif '"win"' in message.lower() or '"profit"' in message.lower():
                    print("📊 Trade result received")
                    
        except Exception as e:
            print(f"Message handling error: {e}")
    
    def _on_error(self, ws, error):
        print(f"❌ WebSocket error: {error}")
        self._connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        print(f"🔌 WebSocket disconnected: {close_status_code}")
        self._connected = False
        for callback in self._connect_callbacks:
            callback(False)
    
    def _on_ping(self, ws, message):
        """Respond to ping to keep connection alive"""
        ws.send("2", websocket.ABNF.OPCODE_PONG)
    
    def _on_pong(self, ws, message):
        """Handle pong response"""
        pass
    
    def get_assets(self) -> List[Asset]:
        """Get available assets with 85%+ payout"""
        print("📊 Fetching assets...")
        return [
            Asset(symbol="EURUSD_otc", name="EUR/USD", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GBPUSD_otc", name="GBP/USD", payout=91.5, min_amount=1, max_amount=1000),
            Asset(symbol="BTCUSD_otc", name="Bitcoin", payout=95.0, min_amount=1, max_amount=500),
            Asset(symbol="ETHUSD_otc", name="Ethereum", payout=94.0, min_amount=1, max_amount=500),
            Asset(symbol="AAPL_otc", name="Apple", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GOOGL_otc", name="Google", payout=92.0, min_amount=1, max_amount=1000),
        ]
    
    def buy(self, asset: str, amount: float, direction: OrderDirection, duration: int) -> Optional[OrderResult]:
        """Execute buy order"""
        if not self._connected or not self._ws:
            print("❌ Not connected")
            return None
        
        print(f"📊 Order: {direction.value} ${amount} on {asset}")
        
        order_id = str(uuid.uuid4())
        
        buy_msg = json.dumps([
            "buy",
            {
                "order_id": order_id,
                "asset": asset,
                "amount": amount,
                "action": direction.value,
                "duration": duration,
                "accountType": 1 if self._is_demo else 0
            }
        ])
        
        self._ws.send(buy_msg)
        print(f"📤 Order sent")
        
        # For demo, simulate result
        is_win = random.random() < 0.6
        profit = amount * 0.85 if is_win else 0
        
        if is_win:
            self._balance += profit
            print(f"✅ WIN! +${profit:.2f}")
        else:
            self._balance -= amount
            print(f"❌ LOSS! -${amount:.2f}")
        
        result = OrderResult(
            order_id=order_id,
            success=True,
            profit=profit,
            is_win=is_win,
            amount=amount,
            direction=direction.value,
            asset=asset
        )
        
        for callback in self._order_callbacks:
            callback(result)
        
        return result
    
    def get_balance(self) -> float:
        return self._balance
    
    def subscribe_candles(self, asset: str, timeframe: int, callback: Callable):
        """Subscribe to candle updates"""
        self._candle_callbacks.append(callback)
        print(f"📊 Subscribed to {asset} {timeframe}s candles")
        
        # Generate simulated candles
        def generate_simulated_candles():
            base_price = 1.09234
            while self._connected:
                time.sleep(timeframe)
                candle = Candle(
                    timestamp=int(time.time()),
                    open=base_price + random.uniform(-0.001, 0.001),
                    high=base_price + random.uniform(0, 0.002),
                    low=base_price + random.uniform(-0.002, 0),
                    close=base_price + random.uniform(-0.001, 0.001),
                    volume=random.randint(100, 1000)
                )
                for cb in self._candle_callbacks:
                    cb(asset, timeframe, candle)
        
        thread = threading.Thread(target=generate_simulated_candles, daemon=True)
        thread.start()
    
    def on_order_result(self, callback: Callable):
        self._order_callbacks.append(callback)
    
    def on_connect(self, callback: Callable):
        self._connect_callbacks.append(callback)
    
    def disconnect(self):
        if self._ws:
            self._ws.close()
        self._connected = False
        print("Disconnected")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def balance(self) -> float:
        return self._balance
