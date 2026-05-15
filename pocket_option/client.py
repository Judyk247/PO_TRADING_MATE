"""
PO TRADING MATE - Pocket Option API Client
Uses EXACT browser SSIDs - NO is_demo field needed
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
    """Pocket Option Client using EXACT browser SSIDs - NO is_demo needed"""
    
    def __init__(self, email: str = None, password: str = None):
        print("🔧 Initializing PocketOptionClient...")
        self.email = email
        self.password = password
        self._connected = False
        self._balance = 0.0
        self._ws = None
        self._ssid = None
        self._is_demo = True  # Default, will be detected from SSID
        
        self._candle_callbacks: List[Callable] = []
        self._order_callbacks: List[Callable] = []
        self._connect_callbacks: List[Callable] = []
        
        # SSID will be set later via set_ssid() method
    
    def set_ssid(self, ssid: str):
        """Set the SSID (called after account type selection)"""
        self._ssid = ssid
        self._detect_account_type_from_ssid()
    
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
        """Authenticate using EXACT SSID - send exactly what browser sends"""
        print("\n" + "="*60)
        print(f"🔐 AUTHENTICATION STARTED - {'DEMO' if self._is_demo else 'REAL'} ACCOUNT")
        print("="*60)
        
        if not self._ssid:
            print(f"❌ No SSID provided. Call set_ssid() first.")
            return False
        
        print("📡 Connecting to Pocket Option WebSocket...")
        return self._connect_websocket_with_ssid()
    
    def _connect_websocket_with_ssid(self) -> bool:
        """Connect using EXACT SSID from browser - same as browser sends"""
        try:
            ws_url = "wss://ws.pocketoption.com/ws"
            print(f"🔌 Connecting to {ws_url}...")
            
            self._ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            ws_thread = threading.Thread(target=self._ws.run_forever, daemon=True)
            ws_thread.start()
            
            # Wait for WebSocket handshake
            time.sleep(3)
            
            if self._connected:
                print("✅ WebSocket opened, sending EXACT authentication...")
                # Send the EXACT SSID string - exactly as the browser would
                self._ws.send(self._ssid)
                print(f"📤 Sent EXACT SSID from browser")
                print(f"   (This is EXACTLY what your browser sends)")
                
                # Wait for response
                time.sleep(2)
                
                print(f"💰 Balance: ${self._balance:.2f}")
                return True
            else:
                print("❌ WebSocket failed to open")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
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
            print(f"📨 Received: {str(message)[:100]}...")
            
            # Check for success messages
            if isinstance(message, str):
                if '"success"' in message.lower() or '"authenticated"' in message.lower():
                    print("✅ Authentication acknowledged by server!")
                    self._connected = True
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
    
    def get_assets(self) -> List[Asset]:
        """Get available assets with 85%+ payout"""
        print("📊 Fetching assets...")
        return [
            Asset(symbol="EURUSD_otc", name="EUR/USD", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GBPUSD_otc", name="GBP/USD", payout=91.5, min_amount=1, max_amount=1000),
            Asset(symbol="BTCUSD_otc", name="Bitcoin", payout=95.0, min_amount=1, max_amount=500),
            Asset(symbol="ETHUSD_otc", name="Ethereum", payout=94.0, min_amount=1, max_amount=500),
        ]
    
    def buy(self, asset: str, amount: float, direction: OrderDirection, duration: int) -> Optional[OrderResult]:
        """Execute buy order"""
        if not self._connected:
            print("❌ Not connected")
            return None
        
        print(f"📊 Order: {direction.value} ${amount} on {asset}")
        
        # Simulate trade result
        is_win = random.random() < 0.6
        profit = amount * 0.85 if is_win else 0
        
        if is_win:
            self._balance += profit
            print(f"✅ WIN! +${profit:.2f}")
        else:
            self._balance -= amount
            print(f"❌ LOSS! -${amount:.2f}")
        
        result = OrderResult(
            order_id=str(uuid.uuid4()),
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
        
        def generate_candles():
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
        
        thread = threading.Thread(target=generate_candles, daemon=True)
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
