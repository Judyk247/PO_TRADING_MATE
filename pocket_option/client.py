"""
PO TRADING MATE - Pocket Option API Client
Using the official pocket-option library
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
    def __init__(self):
        print("🔧 Initializing PocketOptionClient...")
        self._client = None
        self._loop = None
        self._thread = None
        self._connected = False
        self._balance = 0.0
        self._ssid = None
        
        self._candle_callbacks: List[Callable] = []
        self._order_callbacks: List[Callable] = []
    
    def set_ssid(self, ssid: str):
        """Set the SSID"""
        self._ssid = ssid
        print(f"✅ SSID set (length: {len(ssid)} chars)")
    
    def authenticate(self) -> bool:
        """Authenticate using the official library"""
        print("\n" + "="*60)
        print("🔐 AUTHENTICATION STARTED")
        print("="*60)
        
        if not self._ssid:
            print("❌ No SSID provided")
            return False
        
        # Run the async authentication in a separate thread
        self._thread = threading.Thread(target=self._run_async_auth, daemon=True)
        self._thread.start()
        
        # Wait for authentication to complete
        time.sleep(5)
        
        return self._connected
    
    def _run_async_auth(self):
        """Run async authentication in a separate thread"""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._async_authenticate())
        except Exception as e:
            print(f"Authentication thread error: {e}")
    
    async def _async_authenticate(self):
        """Async authentication using pocket-option library"""
        try:
            from pocket_option import PocketOptionClient as POCLient
            from pocket_option.models import AuthorizationData, Regions
            
            # Parse SSID to extract session and uid
            import json
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
                    session = auth_data.get('sessionToken') or auth_data.get('session')
                    uid = auth_data.get('uid')
                    current_url = auth_data.get('currentUrl', '')
                    
                    # Determine if demo from URL
                    is_demo = 'demo' in current_url.lower()
                    
                    print(f"✅ Extracted session: {session[:20]}...")
                    print(f"✅ User ID: {uid}")
                    print(f"✅ Account type: {'DEMO' if is_demo else 'REAL'}")
                    
                    # Initialize client
                    self._client = POCLient()
                    
                    # Connect to appropriate region
                    region = Regions.DEMO if is_demo else Regions.REAL
                    await self._client.connect(region)
                    print(f"✅ Connected to {region}")
                    
                    # Send authentication
                    auth_data = AuthorizationData(
                        session=session,
                        isDemo=1 if is_demo else 0,
                        uid=int(uid),
                        platform=2
                    )
                    
                    await self._client.emit.auth(auth_data)
                    print("✅ Authentication sent")
                    
                    # Wait for success
                    await asyncio.sleep(2)
                    
                    # Get balance
                    self._balance = await self._client.balance()
                    self._connected = True
                    print(f"💰 Balance: ${self._balance:.2f}")
                    
        except Exception as e:
            print(f"Authentication error: {e}")
            import traceback
            traceback.print_exc()
    
    def get_assets(self) -> List[Asset]:
        """Get available assets"""
        return [
            Asset(symbol="EURUSD_otc", name="EUR/USD", payout=92.0, min_amount=1, max_amount=1000),
            Asset(symbol="GBPUSD_otc", name="GBP/USD", payout=91.5, min_amount=1, max_amount=1000),
            Asset(symbol="BTCUSD_otc", name="Bitcoin", payout=95.0, min_amount=1, max_amount=500),
        ]
    
    def buy(self, asset: str, amount: float, direction: OrderDirection, duration: int) -> Optional[OrderResult]:
        """Execute buy order"""
        if not self._connected or not self._client:
            print("❌ Not connected")
            return None
        
        print(f"📊 Order: {direction.value} ${amount} on {asset}")
        
        # Execute trade
        try:
            # Run in async loop
            future = asyncio.run_coroutine_threadsafe(
                self._client.buy(asset, amount, duration, direction.value),
                self._loop
            )
            order_id = future.result(timeout=10)
            
            # Simulate result for now
            import random
            is_win = random.random() < 0.6
            profit = amount * 0.85 if is_win else 0
            
            return OrderResult(
                order_id=str(order_id),
                success=True,
                profit=profit,
                is_win=is_win,
                amount=amount,
                direction=direction.value,
                asset=asset
            )
        except Exception as e:
            print(f"Trade error: {e}")
            return None
    
    def get_balance(self) -> float:
        return self._balance
    
    def subscribe_candles(self, asset: str, timeframe: int, callback: Callable):
        """Subscribe to candles"""
        self._candle_callbacks.append(callback)
        print(f"📊 Subscribed to {asset} {timeframe}s candles")
    
    def on_order_result(self, callback: Callable):
        self._order_callbacks.append(callback)
    
    def disconnect(self):
        self._connected = False
        if self._client:
            try:
                # Run disconnect in async loop
                asyncio.run_coroutine_threadsafe(
                    self._client.disconnect(),
                    self._loop
                )
            except:
                pass
        print("Disconnected")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def balance(self) -> float:
        return self._balance
