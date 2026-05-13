"""
PO TRADING MATE - Pocket Option API Client
SSID Authentication from Environment Variable
"""

import os
import json
import time
import uuid
import logging
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

import websocket
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
    """Pocket Option Client using SSID from environment variable"""
    
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
    
    def authenticate(self) -> bool:
        """Authenticate using SSID from environment variable"""
        
        # Try to get SSID from environment variable first
        self._ssid = os.environ.get('POCKETOPTION_SSID')
        
        if self._ssid:
            print("✅ Found SSID in environment variables")
            return self._connect_with_ssid()
        
        # Fallback to input (for local testing)
        print("\n" + "="*60)
        print("🔐 POCKET OPTION SSID REQUIRED")
        print("="*60)
        print("To connect, set POCKETOPTION_SSID in Render environment variables")
        print("Or paste your SSID below:\n")
        
        ssid = input("👉 Paste your SSID here: ").strip()
        
        if not ssid:
            print("❌ No SSID provided.")
            return False
        
        self._ssid = ssid
        return self._connect_with_ssid()
    
    def _connect_with_ssid(self) -> bool:
        """Connect using the provided SSID"""
        try:
            # Parse the SSID to extract user info
            if self._ssid and '"user_init"' in self._ssid:
                # Extract JSON part
                if self._ssid.startswith('42["user_init",'):
                    json_part = self._ssid[17:]
                    user_data = json.loads(json_part)
                    self._user_id = user_data.get('id')
                    self._secret = user_data.get('secret')
                    print(f"🔐 User ID: {self._user_id}")
                elif self._ssid.startswith('42["auth",'):
                    json_part = self._ssid[12:]
                    user_data = json.loads(json_part)
                    self._user_id = user_data.get('uid')
                    self._secret = user_data.get('session')
                    print(f"🔐 User ID: {self._user_id}")
            
            # Connect WebSocket
            ws_url = f"{self.WS_URL}"
            print(f"🔌 Connecting WebSocket...")
            
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
                self._ws.send(self._ssid)
                print("✅ Authentication sent")
                
                # Give time for auth to process
                time.sleep(2)
                
                self._balance = self.get_balance()
                print(f"✅ Connected! Balance: ${self._balance:.2f}")
                return True
            else:
                print("❌ WebSocket connection failed")
                return False
                
        except json.JSONDecodeError as e:
            print(f"❌ Invalid SSID format: {e}")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def connect_websocket(self) -> bool:
        return self._connected
    
    def _on_open(self, ws):
        self._connected = True
        print("✅ WebSocket opened")
        for callback in self._connect_callbacks:
            callback(True)
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if isinstance(data, list) and len(data) >= 2:
                msg_type = data[0]
                msg_data = data[1]
                
                if msg_type == 42:
                    self._handle_candle(msg_data)
                elif msg_type == 43:
                    self._handle_order_result(msg_data)
        except:
            pass
    
    def _on_error(self, ws, error):
        print(f"❌ WebSocket error: {error}")
        self._connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        print("🔌 WebSocket disconnected")
        self._connected = False
        for callback in self._connect_callbacks:
            callback(False)
    
    def _handle_candle(self, data: Dict):
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
            print(f"Error parsing order: {e}")
    
    def subscribe_candles(self, asset: str, timeframe: int, callback: Callable):
        self._candle_callbacks.append(callback)
        if self._ws and self._connected:
            subscribe_msg = json.dumps([
                "subscribe-candles",
                {"asset": asset, "timeframe": timeframe}
            ])
            self._ws.send(subscribe_msg)
            print(f"📊 Subscribed to {asset} {timeframe}s candles")
    
    def get_assets(self) -> List[Asset]:
        """Return demo assets"""
        return [
            Asset(symbol="EURUSD_otc", name="EUR/USD", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GBPUSD_otc", name="GBP/USD", payout=91.5, min_amount=1, max_amount=1000),
            Asset(symbol="BTCUSD_otc", name="Bitcoin", payout=95.0, min_amount=1, max_amount=500),
        ]
    
    def buy(self, asset: str, amount: float, direction: OrderDirection, duration: int) -> Optional[OrderResult]:
        if not self._connected or not self._ws:
            print("❌ Not connected")
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
        print(f"📊 Order: {direction.value} ${amount} on {asset}")
        
        return OrderResult(
            order_id=order_id, success=True, profit=0, is_win=False,
            amount=amount, direction=direction.value, asset=asset
        )
    
    def get_balance(self) -> float:
        return 10000.0 if self.is_demo else 5000.0
    
    def on_order_result(self, callback: Callable):
        self._order_callbacks.append(callback)
    
    def on_connect(self, callback: Callable):
        self._connect_callbacks.append(callback)
    
    def disconnect(self):
        if self._ws:
            self._ws.close()
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def balance(self) -> float:
        return self._balance
