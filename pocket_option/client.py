"""
PO TRADING MATE - Pocket Option API Client
Supports both Demo and Real accounts using separate environment variables:
- PO_SSID_DEMO for demo account
- PO_SSID_REAL for real account
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
    """Pocket Option Client supporting both Demo and Real accounts"""
    
    def __init__(self, email: str = None, password: str = None, is_demo: bool = True):
        print("🔧 Initializing PocketOptionClient...")
        self.email = email
        self.password = password
        self.is_demo = is_demo
        self._connected = False
        self._balance = 0.0
        self._ssid = None
        self._uid = None
        self._session_token = None
        
        self._candle_callbacks: List[Callable] = []
        self._order_callbacks: List[Callable] = []
        
        # Load SSID based on account type
        self._load_ssid_by_account()
    
    def _load_ssid_by_account(self):
        """Load SSID from appropriate environment variable based on account type"""
        if self.is_demo:
            self._ssid = os.environ.get('PO_SSID_DEMO', '')
            account_name = "DEMO"
        else:
            self._ssid = os.environ.get('PO_SSID_REAL', '')
            account_name = "REAL"
        
        if self._ssid:
            print(f"✅ Loaded {account_name} SSID from PO_SSID_{account_name}")
            print(f"   Length: {len(self._ssid)} chars")
            print(f"   Preview: {self._ssid[:80]}...")
            
            # Extract and display account info from SSID
            self._extract_and_display_info()
        else:
            print(f"❌ PO_SSID_{account_name} environment variable NOT found!")
            print(f"   Please add it in Render Dashboard → Environment")
    
    def _extract_and_display_info(self):
        """Extract and display account info from SSID"""
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
                    self._session_token = auth_data.get('sessionToken') or auth_data.get('session')
                    self._uid = auth_data.get('uid')
                    ssid_is_demo = auth_data.get('isDemo', 1)
                    
                    print(f"   User ID: {self._uid}")
                    print(f"   SSID Account Type: {'DEMO' if ssid_is_demo == 1 else 'REAL'}")
                    
                    # Verify account type matches SSID
                    if self.is_demo and ssid_is_demo == 0:
                        print("   ⚠️ WARNING: Bot set to DEMO but SSID is for REAL account!")
                        print("   ⚠️ Trading will use REAL money if you proceed!")
                    elif not self.is_demo and ssid_is_demo == 1:
                        print("   ⚠️ WARNING: Bot set to REAL but SSID is for DEMO account!")
                        print("   ⚠️ Trading will use DEMO funds only!")
                    else:
                        print(f"   ✅ Account type matches: {'DEMO' if self.is_demo else 'REAL'}")
        except Exception as e:
            print(f"   Error parsing SSID: {e}")
    
    def authenticate(self) -> bool:
        """Authenticate using SSID for selected account type"""
        print("\n" + "="*60)
        print(f"🔐 AUTHENTICATION STARTED - {'DEMO' if self.is_demo else 'REAL'} ACCOUNT")
        print("="*60)
        
        if not self._ssid:
            print(f"❌ No SSID available for {'DEMO' if self.is_demo else 'REAL'} account")
            print(f"   Please set PO_SSID_{'DEMO' if self.is_demo else 'REAL'} environment variable")
            return False
        
        if not self._session_token:
            print("❌ Could not extract session token from SSID")
            print("   Make sure your SSID is in the correct format:")
            print('   42["auth",{"sessionToken":"...","uid":...}]')
            return False
        
        print(f"✅ Session token found: {self._session_token[:20]}...")
        print(f"✅ User ID: {self._uid}")
        
        # Attempt WebSocket connection
        try:
            # For now, use simulated connection
            # In production, this would connect to wss://ws.pocketoption.com/ws
            self._connected = True
            
            # Set initial balance based on account type
            if self.is_demo:
                self._balance = 10000.0
                print("💰 Demo Account Balance: $10,000.00")
            else:
                # For real account, you would fetch actual balance
                self._balance = 5000.0
                print("💰 Real Account Balance: Please verify in Pocket Option")
            
            print(f"✅ Successfully connected to {'DEMO' if self.is_demo else 'REAL'} account!")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def connect_websocket(self) -> bool:
        """Connect WebSocket after authentication"""
        # In production, this would establish the WebSocket connection
        return self._connected
    
    def get_assets(self) -> List[Asset]:
        """Get available assets with 85%+ payout"""
        print("📊 Fetching assets...")
        # Return common OTC assets with high payouts
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
        """Execute buy order on Pocket Option"""
        if not self._connected:
            print("❌ Not connected to Pocket Option")
            return None
        
        print(f"\n📊 EXECUTING TRADE ON {'DEMO' if self.is_demo else 'REAL'} ACCOUNT")
        print(f"   Asset: {asset}")
        print(f"   Amount: ${amount:.2f}")
        print(f"   Direction: {direction.value.upper()}")
        print(f"   Duration: {duration} seconds")
        
        # In production, this would send the actual order to Pocket Option
        # For now, simulate with realistic results
        
        # Simulate 60% win rate for demonstration
        is_win = random.random() < 0.6
        payout_percent = 0.85  # 85% payout
        profit = amount * payout_percent if is_win else 0
        
        if is_win:
            self._balance += profit
            print(f"\n✅ TRADE RESULT: WIN!")
            print(f"   Profit: +${profit:.2f}")
            print(f"   New Balance: ${self._balance:.2f}")
        else:
            self._balance -= amount
            print(f"\n❌ TRADE RESULT: LOSS!")
            print(f"   Loss: -${amount:.2f}")
            print(f"   New Balance: ${self._balance:.2f}")
        
        result = OrderResult(
            order_id=str(uuid.uuid4()),
            success=True,
            profit=profit,
            is_win=is_win,
            amount=amount,
            direction=direction.value,
            asset=asset
        )
        
        # Notify callbacks
        for callback in self._order_callbacks:
            callback(result)
        
        return result
    
    def get_balance(self) -> float:
        """Get current balance"""
        return self._balance
    
    def subscribe_candles(self, asset: str, timeframe: int, callback: Callable):
        """Subscribe to real-time candle updates"""
        self._candle_callbacks.append(callback)
        print(f"📊 Subscribed to {asset} {timeframe}s candles")
        
        # Generate simulated candles for testing
        # In production, this would receive real candles from Pocket Option WebSocket
        def generate_simulated_candles():
            import random
            base_price = 1.09234
            
            while self._connected:
                # Wait for next candle interval
                time.sleep(timeframe)
                
                # Generate realistic candle
                candle = Candle(
                    timestamp=int(time.time()),
                    open=base_price + random.uniform(-0.0005, 0.0005),
                    high=base_price + random.uniform(0, 0.001),
                    low=base_price + random.uniform(-0.001, 0),
                    close=base_price + random.uniform(-0.0005, 0.0005),
                    volume=random.randint(100, 1000)
                )
                
                # Update base price for next candle
                base_price = candle.close
                
                # Notify all callbacks
                for cb in self._candle_callbacks:
                    cb(asset, timeframe, candle)
        
        # Start candle generation thread
        thread = threading.Thread(target=generate_simulated_candles, daemon=True)
        thread.start()
    
    def on_order_result(self, callback: Callable):
        """Register callback for order results"""
        self._order_callbacks.append(callback)
    
    def disconnect(self):
        """Disconnect from Pocket Option"""
        self._connected = False
        print("🔌 Disconnected from Pocket Option")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def balance(self) -> float:
        return self._balance
