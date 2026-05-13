"""
PO TRADING MATE - Trading Strategy (Simplified Working Version)
"""

from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

@dataclass
class Signal:
    direction: str
    confidence: int
    signal_type: str
    expiry_minutes: int
    price: float
    timestamp: str
    rules_passed: List[str]
    details: Dict


class TradingStrategy:
    def __init__(self, timeframe: str = '5m'):
        self.timeframe = timeframe
        self.is_trend = timeframe in ['1m', '2m', '3m']
        self.is_reversal = timeframe == '5m'
        self.expiry_map = {'1m': 2, '2m': 3, '3m': 4, '5m': 5}
    
    def analyze(self, candles: List[Dict]) -> Signal:
        if len(candles) < 50:
            return Signal(
                direction="HOLD",
                confidence=0,
                signal_type="trend" if self.is_trend else "reversal",
                expiry_minutes=self.expiry_map.get(self.timeframe, 5),
                price=candles[-1]['close'] if candles else 0,
                timestamp=datetime.now().isoformat(),
                rules_passed=["Insufficient data"],
                details={"error": f"Need 50+ candles, have {len(candles)}"}
            )
        
        current_price = candles[-1]['close']
        
        # Simple trend detection for demo
        closes = [c['close'] for c in candles[-20:]]
        if closes[-1] > closes[-5]:
            direction = "CALL"
            confidence = 75
            rules_passed = ["✓ Price increasing (simplified strategy)"]
        elif closes[-1] < closes[-5]:
            direction = "PUT"
            confidence = 75
            rules_passed = ["✓ Price decreasing (simplified strategy)"]
        else:
            direction = "HOLD"
            confidence = 50
            rules_passed = ["No clear direction (simplified strategy)"]
        
        return Signal(
            direction=direction,
            confidence=confidence,
            signal_type="trend" if self.is_trend else "reversal",
            expiry_minutes=self.expiry_map.get(self.timeframe, 2),
            price=current_price,
            timestamp=datetime.now().isoformat(),
            rules_passed=rules_passed,
            details={"mode": "simplified_working_version"}
  )
