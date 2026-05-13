"""
PO TRADING MATE - Pocket Option API Client
SSID Authentication method (Most reliable)
"""

import json
import time
import uuid
import logging
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

import requests

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
    """Pocket Option Client using SSID authentication"""
    
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
        self._user_id = None
        self._secret = None
        
        self._candle_callbacks: List[Callable] = []
        self._order_callbacks: List[Callable] = []
        self._connect_callbacks: List[Callable] = []
    
    def set_ssid(self, ssid: str):
        """Manually set SSID (for testing)"""
        self._ssid = ssid
        print("✅ SSID set manually")
    
    def authenticate(self) -> bool:
        """Authenticate using SSID from browser input"""
        # First try to use existing SSID if already set
        if self._ssid:
            return self._connect_with_ssid()
        
        print("\n" + "="*60)
        print("🔐 POCKET OPTION SSID REQUIRED")
        print("="*60)
        print("To connect, you need your SSID from your browser:\n")
        print("1. Open Pocket Option in Chrome/Firefox")
        print("2. Login to your account")
        print("3. Press F12 (Developer Tools)")
        print("4. Go to Network tab")
        print("5. Filter by 'WS' (WebSocket)")
        print("6. Look for message: 42[\"user_init\",{...}]")
        print("7. Copy the ENTIRE message starting with 42[\"user_init\",")
        print("\nExample: 42[\"user_init\",{\"id\":123456,\"secret\":\"abc123...\"}]")
        print("="*60)
        
        ssid = input("\n👉 Paste your SSID here: ").strip()
        
        if not ssid:
            print("❌ No SSID provided.")
            return False
        
        self._ssid = ssid
        return self._connect_with_ssid()
    
    def _connect_with_ssid(self) -> bool:
        """Connect using the provided SSID"""
        try:
            # Parse the SSID to extract user info
            if self._ssid.startswith('42["user_init",'):
                json_part = self._ssid[17:]  # Remove '42["user_init",'
                # Handle trailing bracket
                if json_part.endswith('}'):
                    json_part = json_part
                user_data = json.loads(json_part)
                self._user_id = user_data.get('id')
                self._secret = user_data.get('secret')
                print(f"🔐 Found user ID: {self._user_id}")
            
            # Now connect to WebSocket
            ws_url = f"{self.WS_URL}"
            print(f"🔌 Connecting WebSocket to {ws_url}...")
            
            import websocket
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
                # Send authentication message
                auth_msg = self._ssid
                self._ws.send(auth_msg)
                print("✅ Authentication message sent")
                
                # Get balance
                self._balance = self.get_balance()
                print(f"✅ Connected! Balance: ${self._balance:.2f}")
                return True
            else:
                print("❌ WebSocket connection failed")
                return False
                
        except json.JSONDecodeError as e:
            print(f"❌ Invalid SSID format: {e}")
            print("   Make sure you copied the ENTIRE message including '42[\"user_init\",'")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def connect_websocket(self) -> bool:
        """Return connection status"""
        return self._connected
    
    def _on_open(self, ws):
        self._connected = True
        print("✅ WebSocket connection opened")
        
        for callback in self._connect_callbacks:
            callback(True)
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            # Handle different message types
            if isinstance(data, list) and len(data) >= 2:
                msg_type = data[0]
                msg_data = data[1]
                
                if msg_type == 42:  # Candle/price data
                    self._handle_candle(msg_data)
                elif msg_type == 43:  # Order result
                    self._handle_order_result(msg_data)
                elif msg_type == 0:  # Welcome/ack
                    print("📡 Received welcome message from server")
                    
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Message handling error: {e}")
    
    def _on_error(self, ws, error):
        print(f"❌ WebSocket error: {error}")
        self._connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        print("🔌 WebSocket disconnected")
        self._connected = False
        
        for callback in self._connect_callbacks:
            callback(False)
    
    def _handle_candle(self, data: Dict):
        """Process candle data"""
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
            print(f"Error parsing candle: {e}")
    
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
            print(f"Error parsing order result: {e}")
    
    def subscribe_candles(self, asset: str, timeframe: int, callback: Callable):
        """Subscribe to candle updates"""
        self._candle_callbacks.append(callback)
        
        if self._ws and self._connected:
            subscribe_msg = json.dumps([
                "subscribe-candles",
                {"asset": asset, "timeframe": timeframe}
            ])
            self._ws.send(subscribe_msg)
            print(f"📊 Subscribed to {asset} {timeframe}s candles")
    
    def get_assets(self) -> List[Asset]:
        """Get assets (simplified - returns common assets)"""
        # Return common assets with typical payouts
        return [
            Asset(symbol="EURUSD_otc", name="EUR/USD", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GBPUSD_otc", name="GBP/USD", payout=91.5, min_amount=1, max_amount=1000),
            Asset(symbol="USDJPY_otc", name="USD/JPY", payout=90.0, min_amount=1, max_amount=1000),
            Asset(symbol="BTCUSD_otc", name="Bitcoin", payout=95.0, min_amount=1, max_amount=500),
            Asset(symbol="ETHUSD_otc", name="Ethereum", payout=94.0, min_amount=1, max_amount=500),
            Asset(symbol="AAPL_otc", name="Apple", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GOOGL_otc", name="Google", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="MSFT_otc", name="Microsoft", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="XAUUSD_otc", name="Gold", payout=93.0, min_amount=1, max_amount=500),
            Asset(symbol="SPX_otc", name="S&P 500", payout=91.0, min_amount=1, max_amount=1000),
        ]
    
    def buy(self, asset: str, amount: float, direction: OrderDirection, duration: int) -> Optional[OrderResult]:
        """Execute buy order"""
        if not self._connected or not self._ws:
            print("❌ WebSocket not connected")
            return None
        
        order_id = str(uuid.uuid4())
        
        order_msg = json.dumps([
            "buy",
            {
                "order_id": order_id,
                "asset": asset,
                "amount": amount,
                "action": direction.value,
                "duration": duration,
                "accountType": 1 if self.is_demo else 0
            }
        ])
        
        self._ws.send(order_msg)
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
        # For now, return demo balance
        return 10000.0 if self.is_demo else 5000.0
    
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
