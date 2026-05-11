"""
PO TRADING MATE - Complete Trading Strategy
- 1m, 2m, 3m: Trend Following
- 5m: Reversal Trading

NOTE: This strategy works with OR without TA-Lib, pandas, numpy.
If libraries are not available, it uses manual calculations (slower but works).
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Try to import pandas and numpy - they are optional now
try:
    import pandas as pd
    import numpy as np
    PANDAS_NUMPY_AVAILABLE = True
except ImportError:
    PANDAS_NUMPY_AVAILABLE = False
    # Create dummy classes for type hints when pandas/numpy not available
    class pd:
        class DataFrame:
            pass
    class np:
        @staticmethod
        def zeros(size):
            return [0] * size
    print("⚠️ pandas/numpy not installed. Using pure Python calculations (slower but works).")


@dataclass
class Signal:
    """Trading signal output"""
    direction: str  # "CALL", "PUT", or "HOLD"
    confidence: int  # 0-100
    signal_type: str  # "trend" or "reversal"
    expiry_minutes: int
    price: float
    timestamp: str
    rules_passed: List[str]
    details: Dict


class TradingStrategy:
    """
    Complete trading strategy
    
    TREND FOLLOWING (1m, 2m, 3m):
    - EMA-150 slope + price position
    - Alligator aligned & expanding
    - Stochastic in 20-40 (CALL) or 60-80 (PUT)
    - ATR volatility filter
    - Fractal support/resistance
    - 3-candle trend pattern
    
    REVERSAL (5m):
    - EMA-150 overshoot
    - Alligator contracting/crossing
    - Stochastic oversold (<20) or overbought (>80)
    - Historical bias (min 2 reversals)
    - Fractal support/resistance
    - 3-candle reversal pattern
    """
    
    def __init__(self, timeframe: str = '5m'):
        self.timeframe = timeframe
        self.is_trend = timeframe in ['1m', '2m', '3m']
        self.is_reversal = timeframe == '5m'
        
        self.params = {
            'alligator_jaw': 15,
            'alligator_teeth': 8,
            'alligator_lips': 5,
            'ema_period': 150,
            'stoch_k': 14,
            'stoch_d': 3,
            'oversold': 20,
            'overbought': 80,
            'atr_period': 14,
            'candle_body_threshold': 0.6,
            'doji_threshold': 0.3,
            'reversal_lookback': 10,
            'fractal_threshold': 0.002,  # 0.2%
            'min_reversals': 2
        }
        
        # Expiry mapping
        self.expiry_map = {
            '1m': 2,
            '2m': 3,
            '3m': 4,
            '5m': 5
        }
    
    def analyze(self, candles: List[Dict]) -> Signal:
        """
        Analyze market data and return trading signal
        
        Args:
            candles: List of OHLCV dicts with keys:
                     timestamp, open, high, low, close, volume
        
        Returns:
            Signal object with direction and confidence
        """
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
        
        # Use pandas/numpy if available, otherwise use pure Python
        if PANDAS_NUMPY_AVAILABLE:
            return self._analyze_with_pandas(candles)
        else:
            return self._analyze_pure_python(candles)
    
    def _analyze_with_pandas(self, candles: List[Dict]) -> Signal:
        """Analyze using pandas/numpy (faster)"""
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        df['close'] = pd.to_numeric(df['close'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['open'] = pd.to_numeric(df['open'])
        
        # Calculate indicators
        df = self._calculate_indicators_pandas(df)
        
        # Get latest index
        i = len(df) - 1
        
        # Store current price
        current_price = float(df['close'].iloc[i])
        
        # Generate signal based on timeframe
        if self.is_trend:
            return self._generate_trend_signal_pandas(df, i, current_price)
        else:
            return self._generate_reversal_signal_pandas(df, i, current_price)
    
    def _analyze_pure_python(self, candles: List[Dict]) -> Signal:
        """Analyze using pure Python (slower but works without pandas/numpy)"""
        # Extract values as lists
        closes = [c['close'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        opens = [c['open'] for c in candles]
        
        current_price = closes[-1]
        
        # Calculate indicators manually
        indicators = self._calculate_indicators_pure(closes, highs, lows, opens)
        
        # Generate signal based on timeframe
        if self.is_trend:
            return self._generate_trend_signal_pure(indicators, current_price)
        else:
            return self._generate_reversal_signal_pure(indicators, current_price)
    
    def _calculate_indicators_pandas(self, df):
        """Calculate indicators using pandas (fast)"""
        df = df.copy()
        
        # Alligator (Simple Moving Averages)
        df['jaw'] = df['close'].rolling(window=self.params['alligator_jaw']).mean()
        df['teeth'] = df['close'].rolling(window=self.params['alligator_teeth']).mean()
        df['lips'] = df['close'].rolling(window=self.params['alligator_lips']).mean()
        
        # EMA-150
        df['ema_150'] = df['close'].ewm(span=self.params['ema_period'], adjust=False).mean()
        
        # EMA Slope
        df['ema_slope'] = df['ema_150'].diff()
        
        # Stochastic Oscillator
        lowest_low = df['low'].rolling(window=self.params['stoch_k']).min()
        highest_high = df['high'].rolling(window=self.params['stoch_k']).max()
        df['stoch_k'] = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
        df['stoch_d'] = df['stoch_k'].rolling(window=self.params['stoch_d']).mean()
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.params['atr_period']).mean()
        
        # Median ATR
        lookback = 10 if self.timeframe == '5m' else 5
        df['atr_median'] = df['atr'].rolling(window=lookback).median()
        
        # Fractals
        df['fractal_high'] = self._calc_fractals_pandas(df['high'].values, 'high')
        df['fractal_low'] = self._calc_fractals_pandas(df['low'].values, 'low')
        
        # Reversal counts (only needed for 5m)
        if self.is_reversal:
            df['reversal_count_buy'] = self._calc_reversal_count_pandas(df, 'buy')
            df['reversal_count_sell'] = self._calc_reversal_count_pandas(df, 'sell')
        
        return df
    
    def _calculate_indicators_pure(self, closes, highs, lows, opens):
        """Calculate indicators using pure Python (no pandas/numpy)"""
        n = len(closes)
        indicators = {}
        
        # Alligator (SMA)
        jaw_period = self.params['alligator_jaw']
        teeth_period = self.params['alligator_teeth']
        lips_period = self.params['alligator_lips']
        
        indicators['jaw'] = self._sma(closes, jaw_period)
        indicators['teeth'] = self._sma(closes, teeth_period)
        indicators['lips'] = self._sma(closes, lips_period)
        
        # EMA-150
        ema_period = self.params['ema_period']
        indicators['ema_150'] = self._ema(closes, ema_period)
        
        # EMA Slope
        indicators['ema_slope'] = [0] * n
        for i in range(1, n):
            indicators['ema_slope'][i] = indicators['ema_150'][i] - indicators['ema_150'][i-1]
        
        # Stochastic
        k_period = self.params['stoch_k']
        d_period = self.params['stoch_d']
        indicators['stoch_k'], indicators['stoch_d'] = self._stochastic(highs, lows, closes, k_period, d_period)
        
        # ATR
        atr_period = self.params['atr_period']
        indicators['atr'] = self._atr(highs, lows, closes, atr_period)
        
        # Median ATR
        lookback = 10 if self.timeframe == '5m' else 5
        indicators['atr_median'] = self._median(indicators['atr'], lookback)
        
        # Fractals
        indicators['fractal_high'] = self._calc_fractals_pure(highs, 'high')
        indicators['fractal_low'] = self._calc_fractals_pure(lows, 'low')
        
        # Reversal counts (only for 5m)
        if self.is_reversal:
            indicators['reversal_count_buy'] = self._calc_reversal_count_pure(lows, indicators['fractal_low'], 'buy')
            indicators['reversal_count_sell'] = self._calc_reversal_count_pure(highs, indicators['fractal_high'], 'sell')
        
        return indicators
    
    def _sma(self, data, period):
        """Simple Moving Average - pure Python"""
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(data[i])  # Not enough data
            else:
                sma = sum(data[i-period+1:i+1]) / period
                result.append(sma)
        return result
    
    def _ema(self, data, period):
        """Exponential Moving Average - pure Python"""
        result = []
        multiplier = 2 / (period + 1)
        
        for i in range(len(data)):
            if i == 0:
                result.append(data[0])
            elif i < period:
                # Simple average until we have enough data
                result.append(sum(data[:i+1]) / (i+1))
            else:
                ema = (data[i] - result[i-1]) * multiplier + result[i-1]
                result.append(ema)
        return result
    
    def _stochastic(self, highs, lows, closes, k_period, d_period):
        """Stochastic Oscillator - pure Python"""
        k_values = []
        d_values = []
        
        for i in range(len(closes)):
            if i < k_period - 1:
                k_values.append(50.0)  # Default
                d_values.append(50.0)
            else:
                highest_high = max(highs[i-k_period+1:i+1])
                lowest_low = min(lows[i-k_period+1:i+1])
                if highest_high == lowest_low:
                    k = 50.0
                else:
                    k = 100 * (closes[i] - lowest_low) / (highest_high - lowest_low)
                k_values.append(k)
                
                # D is SMA of K
                if i < d_period - 1:
                    d = k
                else:
                    d = sum(k_values[i-d_period+1:i+1]) / d_period
                d_values.append(d)
        
        return k_values, d_values
    
    def _atr(self, highs, lows, closes, period):
        """Average True Range - pure Python"""
        tr_values = []
        
        for i in range(len(highs)):
            if i == 0:
                tr = highs[i] - lows[i]
            else:
                high_low = highs[i] - lows[i]
                high_close = abs(highs[i] - closes[i-1])
                low_close = abs(lows[i] - closes[i-1])
                tr = max(high_low, high_close, low_close)
            tr_values.append(tr)
        
        # SMA of TR
        return self._sma(tr_values, period)
    
    def _median(self, data, period):
        """Rolling median - pure Python"""
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(data[i])
            else:
                window = sorted(data[i-period+1:i+1])
                mid = len(window) // 2
                if len(window) % 2 == 0:
                    median = (window[mid-1] + window[mid]) / 2
                else:
                    median = window[mid]
                result.append(median)
        return result
    
    def _calc_fractals_pandas(self, price_series, price_type):
        """Calculate fractals using numpy (fast)"""
        fractals = np.zeros(len(price_series))
        
        for i in range(2, len(price_series) - 2):
            if price_type == 'high':
                if (price_series[i] > price_series[i-2] and 
                    price_series[i] > price_series[i-1] and 
                    price_series[i] > price_series[i+1] and 
                    price_series[i] > price_series[i+2]):
                    fractals[i] = 1
            else:
                if (price_series[i] < price_series[i-2] and 
                    price_series[i] < price_series[i-1] and 
                    price_series[i] < price_series[i+1] and 
                    price_series[i] < price_series[i+2]):
                    fractals[i] = 1
        return fractals
    
    def _calc_fractals_pure(self, price_series, price_type):
        """Calculate fractals using pure Python"""
        fractals = [0] * len(price_series)
        
        for i in range(2, len(price_series) - 2):
            if price_type == 'high':
                if (price_series[i] > price_series[i-2] and 
                    price_series[i] > price_series[i-1] and 
                    price_series[i] > price_series[i+1] and 
                    price_series[i] > price_series[i+2]):
                    fractals[i] = 1
            else:
                if (price_series[i] < price_series[i-2] and 
                    price_series[i] < price_series[i-1] and 
                    price_series[i] < price_series[i+1] and 
                    price_series[i] < price_series[i+2]):
                    fractals[i] = 1
        return fractals
    
    def _calc_reversal_count_pandas(self, df, signal_type):
        """Count reversals using pandas"""
        reversal_count = pd.Series(0, index=df.index)
        lookback = self.params['reversal_lookback']
        threshold_pct = self.params['fractal_threshold']
        
        for i in range(lookback, len(df)):
            if signal_type == 'buy':
                current_low = df['low'].iloc[i]
                threshold = current_low * threshold_pct
                
                count = 0
                for j in range(i - lookback, i):
                    if df['fractal_low'].iloc[j] == 1:
                        low_price = df['low'].iloc[j]
                        if abs(low_price - current_low) < threshold:
                            count += 1
                reversal_count.iloc[i] = count
            else:
                current_high = df['high'].iloc[i]
                threshold = current_high * threshold_pct
                
                count = 0
                for j in range(i - lookback, i):
                    if df['fractal_high'].iloc[j] == 1:
                        high_price = df['high'].iloc[j]
                        if abs(high_price - current_high) < threshold:
                            count += 1
                reversal_count.iloc[i] = count
        
        return reversal_count
    
    def _calc_reversal_count_pure(self, prices, fractals, signal_type):
        """Count reversals using pure Python"""
        n = len(prices)
        reversal_count = [0] * n
        lookback = self.params['reversal_lookback']
        threshold_pct = self.params['fractal_threshold']
        
        for i in range(lookback, n):
            current_price = prices[i]
            threshold = current_price * threshold_pct
            
            count = 0
            for j in range(i - lookback, i):
                if fractals[j] == 1:
                    if abs(prices[j] - current_price) < threshold:
                        count += 1
            reversal_count[i] = count
        
        return reversal_count
    
    def _check_three_candle_pattern_pandas(self, df, i, pattern):
        """Check 3-candle pattern using pandas"""
        if i < 2:
            return False
        
        c1 = df.iloc[i-2]
        c2 = df.iloc[i-1]
        c3 = df.iloc[i]
        
        c1_body = abs(c1['close'] - c1['open'])
        c1_range = c1['high'] - c1['low']
        c2_body = abs(c2['close'] - c2['open'])
        c2_range = c2['high'] - c2['low']
        c3_body = abs(c3['close'] - c3['open'])
        c3_range = c3['high'] - c3['low']
        
        body_threshold = self.params['candle_body_threshold']
        doji_threshold = self.params['doji_threshold']
        
        if pattern == 'trend_buy':
            bearish = c1['close'] < c1['open'] and (c1_body / c1_range) > body_threshold if c1_range > 0 else False
            indecision = (c2_body / c2_range) < doji_threshold if c2_range > 0 else False
            bullish = c3['close'] > c3['open'] and (c3_body / c3_range) > body_threshold if c3_range > 0 else False
            return bearish and indecision and bullish and c3['close'] > c2['high']
            
        elif pattern == 'trend_sell':
            bullish = c1['close'] > c1['open'] and (c1_body / c1_range) > body_threshold if c1_range > 0 else False
            indecision = (c2_body / c2_range) < doji_threshold if c2_range > 0 else False
            bearish = c3['close'] < c3['open'] and (c3_body / c3_range) > body_threshold if c3_range > 0 else False
            return bullish and indecision and bearish and c3['close'] < c2['low']
            
        elif pattern == 'reversal_buy':
            bearish = c1['close'] < c1['open'] and (c1_body / c1_range) > body_threshold if c1_range > 0 else False
            indecision = (c2_body / c2_range) < doji_threshold if c2_range > 0 else False
            bullish = c3['close'] > c3['open'] and (c3_body / c3_range) > body_threshold if c3_range > 0 else False
            return bearish and indecision and bullish and c3['close'] > c2['high']
            
        elif pattern == 'reversal_sell':
            bullish = c1['close'] > c1['open'] and (c1_body / c1_range) > body_threshold if c1_range > 0 else False
            indecision = (c2_body / c2_range) < doji_threshold if c2_range > 0 else False
            bearish = c3['close'] < c3['open'] and (c3_body / c3_range) > body_threshold if c3_range > 0 else False
            return bullish and indecision and bearish and c3['close'] < c2['low']
        
        return False
    
    def _check_price_near_fractal_pandas(self, df, i, signal_type):
        """Check if price is near fractal support/resistance using pandas"""
        current_price = df['close'].iloc[i]
        threshold = current_price * self.params['fractal_threshold']
        
        if signal_type == 'buy':
            for j in range(max(0, i-5), i+1):
                if df['fractal_low'].iloc[j] == 1:
                    low_price = df['low'].iloc[j]
                    if abs(current_price - low_price) < threshold:
                        return True
        else:
            for j in range(max(0, i-5), i+1):
                if df['fractal_high'].iloc[j] == 1:
                    high_price = df['high'].iloc[j]
                    if abs(current_price - high_price) < threshold:
                        return True
        return False
    
    def _generate_trend_signal_pandas(self, df, i, current_price):
        """Generate trend following signal using pandas"""
        rules_passed = []
        
        call_conditions = []
        put_conditions = []
        
        # 1. EMA Condition
        ema_call = df['ema_slope'].iloc[i] > 0 and df['close'].iloc[i] > df['ema_150'].iloc[i]
        ema_put = df['ema_slope'].iloc[i] < 0 and df['close'].iloc[i] < df['ema_150'].iloc[i]
        call_conditions.append(ema_call)
        put_conditions.append(ema_put)
        if e
