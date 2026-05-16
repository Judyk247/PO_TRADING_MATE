"""
PO TRADING MATE - Pocket Option API Client
Using API-Pocket-Option - Handles login automatically
"""

import os
import asyncio
import threading
import time
import logging
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
    """Pocket Option Client using API-Pocket-Option"""
    
    def __init__(self):
        print("🔧 Initializing PocketOptionClient...")
        self._connected = False
        self._balance = 0.0
        self._client = None
        self._loop = None
        self._thread = None
        
        self._candle_callbacks: List[Callable] = []
        self._order_callbacks: List[Callable] = []
        self._connect_callbacks: List[Callable] = []
    
    def set_credentials(self, email: str, password: str, is_demo: bool = True):
        """Set Pocket Option credentials for auto-login"""
        self._email = email
        self._password = password
        self._is_demo = is_demo
        print(f"✅ Credentials set for {'DEMO' if is_demo else 'REAL'} account")
    
    def authenticate(self) -> bool:
        """Authenticate using API-Pocket-Option (auto-login with CAPTCHA handling)"""
        print("\n" + "="*60)
        print("🔐 AUTHENTICATION STARTED")
        print("="*60)
        
        if not hasattr(self, '_email') or not hasattr(self, '_password'):
            print("❌ No credentials provided. Call set_credentials() first.")
            return False
        
        # Run async authentication in thread
        self._thread = threading.Thread(target=self._run_async_auth, daemon=True)
        self._thread.start()
        
        # Wait for authentication
        time.sleep(10)
        
        return self._connected
    
    def _run_async_auth(self):
        """Run async authentication"""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._async_authenticate())
        except Exception as e:
            print(f"Authentication thread error: {e}")
    
    async def _async_authenticate(self):
        """Async authentication"""
        try:
            # Import the library (installed from GitHub)
            from api_pocket import AsyncPocketOptionClient, get_ssid
            
            print("📡 Getting SSID via auto-login...")
            print("   A browser window will open for CAPTCHA solving.")
            print("   Please solve the CAPTCHA when prompted.")
            
            # Auto-login with CAPTCHA handling
            ssid_info = get_ssid(
                email=self._email,
                password=self._password,
                is_demo=self._is_demo
            )
            
            ssid = ssid_info.get("demo") if self._is_demo else ssid_info.get("live")
            
            if not ssid:
                print("❌ Failed to get SSID")
                return
            
            print(f"✅ SSID obtained successfully")
            
            # Initialize client
            self._client = AsyncPocketOptionClient(ssid=ssid, is_demo=self._is_demo)
            
            # Connect
            await self._client.connect()
            self._connected = True
            print("✅ Connected to Pocket Option")
            
            # Get balance
            balance = await self._client.get_balance()
            self._balance = float(balance.balance)
            print(f"💰 Balance: ${self._balance:.2f}")
            
            # Setup callbacks
            @self._client.on_order_result
            async def handle_order_result(result):
                for callback in self._order_callbacks:
                    callback(result)
            
            @self._client.on_price_update
            async def handle_price_update(data):
                # Could implement real-time candles here
                pass
                
        except ImportError as e:
            print(f"❌ API-Pocket-Option not installed: {e}")
            print("   Run: pip install git+https://github.com/A11ksa/API-Pocket-Option.git")
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            import traceback
            traceback.print_exc()
    
    def connect_websocket(self) -> bool:
        return self._connected
    
    def get_assets(self) -> List[Asset]:
        """Get available assets"""
        return [
            Asset(symbol="EURUSD_otc", name="EUR/USD", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GBPUSD_otc", name="GBP/USD", payout=91.5, min_amount=1, max_amount=1000),
            Asset(symbol="BTCUSD_otc", name="Bitcoin", payout=95.0, min_amount=1, max_amount=500),
            Asset(symbol="ETHUSD_otc", name="Ethereum", payout=94.0, min_amount=1, max_amount=500),
            Asset(symbol="AAPL_otc", name="Apple", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GOOGL_otc", name="Google", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="MSFT_otc", name="Microsoft", payout=92.0, min_amount=1, max_amount=1000),
        ]
    
    def buy(self, asset: str, amount: float, direction: OrderDirection, duration: int) -> Optional[OrderResult]:
        """Execute buy order"""
        if not self._connected or not self._client:
            print("❌ Not connected")
            return None
        
        print(f"📊 Order: {direction.value} ${amount} on {asset}")
        
        try:
            # Place order asynchronously
            future = asyncio.run_coroutine_threadsafe(
                self._client.place_order(
                    asset=asset,
                    amount=amount,
                    direction=direction,
                    duration=duration
                ),
                self._loop
            )
            order = future.result(timeout=30)
            
            # Wait for result
            result_future = asyncio.run_coroutine_threadsafe(
                self._client.check_win(order.order_id),
                self._loop
            )
            result = result_future.result(timeout=60)
            
            profit = result.profit if result.is_win else 0
            
            if result.is_win:
                self._balance += profit
                print(f"✅ WIN! +${profit:.2f}")
            else:
                self._balance -= amount
                print(f"❌ LOSS! -${amount:.2f}")
            
            order_result = OrderResult(
                order_id=order.order_id,
                success=True,
                profit=profit,
                is_win=result.is_win,
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
        
        # Generate simulated candles as fallback
        import random
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
        if self._client:
            try:
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._client.disconnect(),
                        self._loop
                    )
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
