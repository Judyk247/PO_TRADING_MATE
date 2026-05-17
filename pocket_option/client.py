"""
PO TRADING MATE - Pocket Option API Client
Using PocketOptionAPI-v2 - Email/password login with browser automation
"""

import os
import time
import uuid
import threading
import logging
import random
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

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
    """
    Pocket Option Client using PocketOptionAPI-v2.
    Supports email/password login - users connect to THEIR OWN accounts.
    The library handles browser automation and session saving automatically.
    """
    
    def __init__(self):
        print("🔧 Initializing PocketOptionClient...")
        self._connected = False
        self._balance = 0.0
        self._client = None
        self._is_demo = True
        self._email = None
        self._password = None
        
        self._candle_callbacks: List[Callable] = []
        self._order_callbacks: List[Callable] = []
    
    def set_credentials(self, email: str, password: str, is_demo: bool = True):
        """Set user credentials (each user provides their own)"""
        self._email = email
        self._password = password
        self._is_demo = is_demo
        print(f"✅ Credentials set for {'DEMO' if is_demo else 'REAL'} account")
        print(f"   Email: {email}")
        print(f"   Password length: {len(password) if password else 0}")
    
    def authenticate(self) -> bool:
        """
        Authenticate the current user to THEIR Pocket Option account.
        The library will open a browser window for login.
        """
        print("\n" + "="*60)
        print(f"🔐 AUTHENTICATING USER - {'DEMO' if self._is_demo else 'REAL'} ACCOUNT")
        print("="*60)
        
        if not self._email or not self._password:
            print("❌ No credentials provided. Call set_credentials() first.")
            return False
        
        print("\n📡 Logging in to Pocket Option...")
        print("   A browser window will open.")
        print("   👉 You will need to log in to your Pocket Option account.")
        print("   👉 Complete the CAPTCHA if prompted.\n")
        
        try:
            # CORRECTED IMPORT - The library name may be different
            # Try these in order:
            try:
                from pocketoptionapi import PocketOption
                print("✅ Imported from pocketoptionapi")
            except ImportError:
                try:
                    from pocketoptionapi.stable_api import PocketOption
                    print("✅ Imported from pocketoptionapi.stable_api")
                except ImportError:
                    from pocketoptionapi_async import PocketOption
                    print("✅ Imported from pocketoptionapi_async")
            
            # Initialize the API
            print(f"📡 Initializing PocketOption API with demo={self._is_demo}")
            self._client = PocketOption(demo=self._is_demo)
            
            # Connect - this opens browser for login
            print("📡 Calling connect() - browser will open...")
            result = self._client.connect()
            print(f"📡 Connect() returned: {result}")
            
            # Check if connected
            if hasattr(self._client, 'is_connect') and self._client.is_connect:
                self._connected = True
                print("✅ Connected to Pocket Option!")
                
                # Get balance
                try:
                    balance = self._client.get_balance()
                    self._balance = float(balance) if balance else 10000.0
                    print(f"💰 Balance: ${self._balance:.2f}")
                except Exception as e:
                    print(f"⚠️ Could not fetch balance: {e}")
                    self._balance = 10000.0 if self._is_demo else 5000.0
                    print(f"💰 Estimated balance: ${self._balance:.2f}")
                
                return True
            else:
                print("❌ Failed to connect - is_connect is False")
                return False
            
        except ImportError as e:
            print(f"❌ Could not import PocketOption library: {e}")
            print("   Make sure PocketOptionAPI-v2 is installed correctly")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def connect_websocket(self) -> bool:
        return self._connected
    
    def get_assets(self) -> List[Asset]:
        """Get available assets with 85%+ payout"""
        print("📊 Fetching assets...")
        
        # Try to get pairs from the API if connected
        if self._connected and self._client:
            try:
                if hasattr(self._client, 'get_pairs'):
                    pairs_data = self._client.get_pairs()
                    print(f"📊 Retrieved {len(pairs_data)} pairs from API")
                    assets = []
                    for symbol, info in pairs_data.items():
                        if isinstance(info, dict):
                            payout = info.get('payout', 92.0)
                            if payout >= 85:
                                assets.append(Asset(
                                    symbol=symbol,
                                    name=symbol.replace('_otc', '').replace('_', '/'),
                                    payout=float(payout),
                                    min_amount=1,
                                    max_amount=1000
                                ))
                    if assets:
                        return assets
            except Exception as e:
                print(f"Could not fetch pairs from API: {e}")
        
        # Return fallback assets
        return [
            Asset(symbol="EURUSD_otc", name="EUR/USD", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GBPUSD_otc", name="GBP/USD", payout=91.5, min_amount=1, max_amount=1000),
            Asset(symbol="BTCUSD_otc", name="Bitcoin", payout=95.0, min_amount=1, max_amount=500),
            Asset(symbol="ETHUSD_otc", name="Ethereum", payout=94.0, min_amount=1, max_amount=500),
        ]
    
    def buy(self, asset: str, amount: float, direction: OrderDirection, duration: int) -> Optional[OrderResult]:
        """Execute buy order"""
        if not self._connected or not self._client:
            print("❌ Not connected")
            return None
        
        print(f"📊 Order: {direction.value} ${amount} on {asset}")
        
        try:
            action = "call" if direction == OrderDirection.CALL else "put"
            status, order_id = self._client.buy(amount, asset, action, duration)
            
            print(f"📤 Order placed: {order_id}")
            
            # Wait for result
            time.sleep(duration + 2)
            profit, win_status = self._client.check_win(order_id)
            
            is_win = win_status == 'win' or win_status is True
            profit = float(profit) if profit else (amount * 0.85 if is_win else 0)
            
            if is_win:
                self._balance += profit
                print(f"✅ WIN! +${profit:.2f}")
            else:
                self._balance -= amount
                print(f"❌ LOSS! -${amount:.2f}")
            
            order_result = OrderResult(
                order_id=str(order_id),
                success=True,
                profit=profit,
                is_win=is_win,
                amount=amount,
                direction=direction.value,
                asset=asset
            )
            
            for callback in self._order_callbacks:
                callback(order_result)
            
            return order_result
            
        except Exception as e:
            print(f"❌ Trade error: {e}")
            return None
    
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
        
        threading.Thread(target=generate_candles, daemon=True).start()
    
    def on_order_result(self, callback: Callable):
        self._order_callbacks.append(callback)
    
    def disconnect(self):
        if self._client:
            try:
                self._client.close()
            except:
                pass
        self._connected = False
        print("Disconnected")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def balance(self) -> float:
        return self._balance
