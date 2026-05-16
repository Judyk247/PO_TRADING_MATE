#!/usr/bin/env python3
"""
PO TRADING MATE - Pocket Option Auto-Trading Bot
Main Flask Application
"""

# ============================================================
# CRITICAL: eventlet.monkey_patch() MUST be the first thing
# ============================================================
import eventlet
eventlet.monkey_patch()

# ============================================================
# Standard library imports
# ============================================================
import os
import sys
import json
import threading
import time
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# ============================================================
# Print debug info immediately (visible in Render logs)
# ============================================================
print(f"🐍 Python version: {sys.version}")
print(f"📁 Current working directory: {os.getcwd()}")
print(f"📂 Files in directory: {os.listdir('.')}")

# ============================================================
# Third-party imports
# ============================================================
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

# ============================================================
# Local imports (with error handling)
# ============================================================
try:
    from pocket_option.client import PocketOptionClient, OrderDirection
    print("✅ Successfully imported pocket_option.client")
except Exception as e:
    print(f"❌ Failed to import pocket_option.client: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from strategy.strategy import TradingStrategy, Signal
    print("✅ Successfully imported strategy.strategy")
except Exception as e:
    print(f"❌ Failed to import strategy.strategy: {e}")
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# Configure logging
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# Initialize Flask app
# ============================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'po-trading-mate-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

print("✅ Flask app and SocketIO initialized")

# ============================================================
# Global variables
# ============================================================
client: Optional[PocketOptionClient] = None
bot_running = False
bot_thread: Optional[threading.Thread] = None
current_asset = ""
current_amount = 10.0
current_timeframe = "5m"
current_strategy: Optional[TradingStrategy] = None
martingale_enabled = False
martingale_state = {
    "active": False,
    "step": 0,
    "current_amount": 0,
    "total_loss": 0,
    "original_direction": None
}
trade_stats = {
    "total_trades": 0,
    "winning_trades": 0,
    "daily_pl": 0.0,
    "last_trade": None,
    "last_trade_time": None
}
active_subscriptions = []

print("✅ Global variables initialized")

# ============================================================
# Route Handlers
# ============================================================

@app.route('/')
def index():
    """Serve the main dashboard"""
    print("📊 Index route accessed")
    return render_template('index.html')


@app.route('/api/connect', methods=['POST'])
def connect():
    """Connect to Pocket Option using email/password (auto-login)"""
    global client
    
    print("🔵 CONNECT endpoint called")
    
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        account_type = data.get('account_type', 'demo')
        is_demo = account_type == 'demo'
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'})
        
        print(f"📡 Account type: {'DEMO' if is_demo else 'REAL'}")
        print(f"📡 Email: {email}")
        
        # Create client
        client = PocketOptionClient()
        client.set_credentials(email, password, is_demo)
        
        # Authenticate (auto-login with CAPTCHA handling)
        if client.authenticate():
            balance = client.get_balance()
            print(f"✅ Connection successful! Balance: ${balance:.2f}")
            
            # Connect WebSocket
            if client.connect_websocket():
                print("✅ WebSocket connected successfully")
            
            socketio.emit('log', {'message': f'Connected to Pocket Option! Balance: ${balance:.2f}', 'type': 'success'})
            return jsonify({'success': True, 'balance': balance})
        else:
            print("❌ Authentication failed")
            socketio.emit('log', {'message': 'Authentication failed. Check your credentials.', 'type': 'error'})
            return jsonify({'success': False, 'error': 'Authentication failed. Check your email/password.'})
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        traceback.print_exc()
        socketio.emit('log', {'message': f'Connection error: {str(e)}', 'type': 'error'})
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """Disconnect from Pocket Option"""
    global client, bot_running
    
    print("🔵 DISCONNECT endpoint called")
    bot_running = False
    
    if client:
        client.disconnect()
        client = None
    
    socketio.emit('log', {'message': 'Disconnected from Pocket Option', 'type': 'info'})
    return jsonify({'success': True})


@app.route('/api/assets')
def get_assets():
    """Get available assets with 85%+ payout"""
    print("🔵 ASSETS endpoint called")
    
    if not client:
        print("⚠️ No client connected")
        return jsonify([])
    
    assets = client.get_assets()
    result = [
        {
            'symbol': a.symbol,
            'name': a.name,
            'payout': a.payout,
            'min_amount': a.min_amount,
            'max_amount': a.max_amount
        }
        for a in assets
    ]
    print(f"📊 Returning {len(result)} assets")
    return jsonify(result)


@app.route('/api/start_bot', methods=['POST'])
def start_bot():
    """Start auto-trading bot"""
    global bot_running, bot_thread, current_asset, current_amount, current_timeframe
    global current_strategy, martingale_enabled
    
    print("🔵 START_BOT endpoint called")
    
    data = request.json
    current_asset = data.get('asset', 'EURUSD_otc')
    current_amount = float(data.get('amount', 10))
    current_timeframe = data.get('timeframe', '5m')
    martingale_enabled = data.get('martingale', False)
    
    print(f"📡 Bot config - Asset: {current_asset}, Amount: ${current_amount}, Timeframe: {current_timeframe}, Martingale: {martingale_enabled}")
    
    if not client or not client.is_connected:
        print("❌ Not connected to Pocket Option")
        return jsonify({'success': False, 'error': 'Not connected to Pocket Option'})
    
    bot_running = True
    current_strategy = TradingStrategy(timeframe=current_timeframe)
    
    # Reset martingale state
    global martingale_state
    martingale_state = {
        "active": False,
        "step": 0,
        "current_amount": 0,
        "total_loss": 0,
        "original_direction": None
    }
    
    # Start bot thread
    bot_thread = threading.Thread(target=_bot_loop, daemon=True)
    bot_thread.start()
    
    socketio.emit('log', {'message': f'Bot started | Asset: {current_asset} | Amount: ${current_amount} | Timeframe: {current_timeframe}', 'type': 'success'})
    return jsonify({'success': True})


@app.route('/api/stop_bot', methods=['POST'])
def stop_bot():
    """Stop auto-trading bot"""
    global bot_running
    print("🔵 STOP_BOT endpoint called")
    bot_running = False
    socketio.emit('log', {'message': 'Bot stopped', 'type': 'warning'})
    return jsonify({'success': True})


@app.route('/api/manual_trade', methods=['POST'])
def manual_trade():
    """Execute manual trade"""
    print("🔵 MANUAL_TRADE endpoint called")
    
    if not client or not client.is_connected:
        return jsonify({'success': False, 'error': 'Not connected'})
    
    data = request.json
    asset = data.get('asset')
    amount = float(data.get('amount', 10))
    direction = data.get('direction')
    
    print(f"📡 Manual trade - Asset: {asset}, Amount: ${amount}, Direction: {direction}")
    
    order_direction = OrderDirection.CALL if direction == 'CALL' else OrderDirection.PUT
    duration = _get_duration_from_timeframe(current_timeframe)
    
    result = client.buy(asset, amount, order_direction, duration)
    
    if result:
        socketio.emit('log', {'message': f'Manual {direction} trade placed: ${amount} on {asset}', 'type': 'info'})
        return jsonify({'success': True, 'order_id': result.order_id})
    else:
        return jsonify({'success': False, 'error': 'Trade failed'})


def _get_duration_from_timeframe(timeframe: str) -> int:
    """Convert timeframe string to duration in seconds"""
    timeframe_map = {
        '1m': 60,
        '2m': 120,
        '3m': 180,
        '5m': 300
    }
    return timeframe_map.get(timeframe, 60)


def _get_candle_interval(timeframe: str) -> int:
    """Get candle interval in seconds for subscription"""
    interval_map = {
        '1m': 60,
        '2m': 120,
        '3m': 180,
        '5m': 300
    }
    return interval_map.get(timeframe, 60)


def _calculate_time_to_next_candle(timeframe_seconds: int) -> int:
    """Calculate seconds until next candle closes"""
    current_time = time.time()
    candle_start = int(current_time / timeframe_seconds) * timeframe_seconds
    candle_end = candle_start + timeframe_seconds
    signal_time = candle_end - 30
    time_remaining = signal_time - current_time
    return max(0, int(time_remaining))


def _bot_loop():
    """Main bot loop"""
    global martingale_state, trade_stats
    
    print("🔄 Bot loop started")
    timeframe_seconds = _get_candle_interval(current_timeframe)
    candle_data = []
    
    def on_candle(asset, timeframe, candle):
        if asset != current_asset:
            return
        
        candle_data.append({
            'timestamp': candle.timestamp,
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume
        })
        
        while len(candle_data) > 200:
            candle_data.pop(0)
        
        time_remaining = _calculate_time_to_next_candle(timeframe_seconds)
        
        if time_remaining <= 30 and time_remaining >= 0:
            if len(candle_data) >= 50:
                strategy = TradingStrategy(timeframe=current_timeframe)
                signal = strategy.analyze(candle_data)
                
                signal_dict = {
                    'direction': signal.direction,
                    'confidence': signal.confidence,
                    'signal_type': signal.signal_type,
                    'price': signal.price,
                    'expiry_minutes': signal.expiry_minutes,
                    'rules_passed': signal.rules_passed,
                    'details': signal.details,
                    'time_remaining': time_remaining
                }
                
                socketio.emit('signal', signal_dict)
                
                if bot_running and signal.direction in ['CALL', 'PUT'] and signal.confidence >= 60:
                    _execute_trade(signal.direction, signal.price)
    
    if client:
        client.subscribe_candles(current_asset, timeframe_seconds, on_candle)
    
        def on_order_result(result):
            global trade_stats, martingale_state
            
            trade_stats['total_trades'] += 1
            trade_stats['last_trade_time'] = datetime.now()
            
            if result.is_win:
                trade_stats['winning_trades'] += 1
                trade_stats['daily_pl'] += result.profit
                trade_stats['last_trade'] = f"WIN on {result.asset}: +${result.profit:.2f}"
                
                socketio.emit('trade_result', {
                    'is_win': True,
                    'profit': result.profit,
                    'asset': result.asset,
                    'direction': result.direction,
                    'amount': result.amount
                })
                
                if martingale_state['active']:
                    martingale_state = {
                        "active": False,
                        "step": 0,
                        "current_amount": 0,
                        "total_loss": 0,
                        "original_direction": None
                    }
                    socketio.emit('log', {'message': 'Martingale sequence completed - WIN achieved!', 'type': 'success'})
            else:
                trade_stats['daily_pl'] -= result.amount
                trade_stats['last_trade'] = f"LOSS on {result.asset}: -${result.amount:.2f}"
                
                socketio.emit('trade_result', {
                    'is_win': False,
                    'profit': 0,
                    'asset': result.asset,
                    'direction': result.direction,
                    'amount': result.amount
                })
                
                if martingale_enabled and bot_running:
                    if not martingale_state['active']:
                        martingale_state['active'] = True
                        martingale_state['step'] = 1
                        martingale_state['current_amount'] = current_amount
                        martingale_state['total_loss'] = result.amount
                        martingale_state['original_direction'] = result.direction
                    else:
                        martingale_state['step'] += 1
                        martingale_state['current_amount'] = martingale_state['current_amount'] * 2.3
                        martingale_state['total_loss'] += result.amount
                    
                    socketio.emit('log', {
                        'message': f"Martingale activated: Step {martingale_state['step']} | Next trade: ${martingale_state['current_amount'] * 2.3:.2f}",
                        'type': 'warning'
                    })
                    
                    _execute_trade(martingale_state['original_direction'], None, martingale=True)
        
        client.on_order_result(on_order_result)
    
    while bot_running:
        time.sleep(0.1)
    
    print("🔄 Bot loop ended")
    socketio.emit('log', {'message': 'Bot loop ended', 'type': 'info'})


def _execute_trade(direction: str, price: float = None, martingale: bool = False):
    """Execute a trade"""
    global martingale_state
    
    if not client or not client.is_connected:
        return
    
    if martingale and martingale_state['active']:
        amount = martingale_state['current_amount'] * 2.3
    else:
        amount = current_amount
    
    if amount < 1:
        amount = current_amount
    
    duration = _get_duration_from_timeframe(current_timeframe)
    order_direction = OrderDirection.CALL if direction == 'CALL' else OrderDirection.PUT
    
    result = client.buy(current_asset, amount, order_direction, duration)
    
    if result:
        socketio.emit('log', {
            'message': f"Auto-trade: {direction} ${amount:.2f} on {current_asset}",
            'type': 'info'
        })


@socketio.on('connect')
def handle_connect():
    print("🔌 Socket.IO client connected")
    emit('log', {'message': 'Connected to PO TRADING MATE server', 'type': 'success'})


@socketio.on('disconnect')
def handle_disconnect():
    print("🔌 Socket.IO client disconnected")


# ============================================================
# RENDER DEPLOYMENT
# ============================================================

if __name__ == '__main__':
    try:
        print("=" * 60)
        print("🚀 PO TRADING MATE Starting...")
        print("=" * 60)
        
        port = int(os.environ.get('PORT', 10000))
        
        print(f"📍 Port: {port}")
        print(f"📍 Host: 0.0.0.0")
        print(f"📍 Debug: False")
        print("=" * 60)
        
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False
        )
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
