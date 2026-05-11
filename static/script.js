// PO TRADING MATE - Frontend JavaScript

// Socket.IO connection
const socket = io();

// DOM Elements
let emailInput, passwordInput, accountTypeSelect, connectBtn, disconnectBtn;
let startBotBtn, stopBotBtn;
let amountSelect, timeframeSelect, assetSelect;
let martingaleOnBtn, martingaleOffBtn;
let manualCallBtn, manualPutBtn;
let soundOnBtn, soundOffBtn;
let signalDisplay, countdownTimer, confidenceBar, confidenceValue;
let rulesList, botStatus, tradeCount, netProfit, lastTrade, logConsole;
let martingaleStatus, martingaleStep, martingaleLoss, martingaleNext;
let balanceDisplay, dailyPLDisplay, winRateDisplay;

// State variables
let isConnected = false;
let isBotRunning = false;
let martingaleEnabled = false;
let soundEnabled = true;
let currentSignal = null;
let tradeHistory = [];
let dailyPL = 0;
let totalTrades = 0;
let winningTrades = 0;
let activeMartingale = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements
    emailInput = document.getElementById('email');
    passwordInput = document.getElementById('password');
    accountTypeSelect = document.getElementById('accountType');
    connectBtn = document.getElementById('connectBtn');
    disconnectBtn = document.getElementById('disconnectBtn');
    startBotBtn = document.getElementById('startBot');
    stopBotBtn = document.getElementById('stopBot');
    amountSelect = document.getElementById('amount');
    timeframeSelect = document.getElementById('timeframe');
    assetSelect = document.getElementById('asset');
    martingaleOnBtn = document.getElementById('martingaleOn');
    martingaleOffBtn = document.getElementById('martingaleOff');
    manualCallBtn = document.getElementById('manualCall');
    manualPutBtn = document.getElementById('manualPut');
    soundOnBtn = document.getElementById('soundOn');
    soundOffBtn = document.getElementById('soundOff');
    signalDisplay = document.getElementById('signalDisplay');
    countdownTimer = document.getElementById('countdownTimer');
    confidenceBar = document.getElementById('confidenceBar');
    confidenceValue = document.getElementById('confidenceValue');
    rulesList = document.getElementById('rulesList');
    botStatus = document.getElementById('botStatus');
    tradeCount = document.getElementById('tradeCount');
    netProfit = document.getElementById('netProfit');
    lastTrade = document.getElementById('lastTrade');
    logConsole = document.getElementById('logConsole');
    martingaleStatus = document.getElementById('martingaleStatus');
    martingaleStep = document.getElementById('martingaleStep');
    martingaleLoss = document.getElementById('martingaleLoss');
    martingaleNext = document.getElementById('martingaleNext');
    balanceDisplay = document.getElementById('balance');
    dailyPLDisplay = document.getElementById('dailyPL');
    winRateDisplay = document.getElementById('winRate');

    // Event Listeners
    connectBtn.addEventListener('click', connectToPocketOption);
    disconnectBtn.addEventListener('click', disconnectFromPocketOption);
    startBotBtn.addEventListener('click', startBot);
    stopBotBtn.addEventListener('click', stopBot);
    martingaleOnBtn.addEventListener('click', () => setMartingale(true));
    martingaleOffBtn.addEventListener('click', () => setMartingale(false));
    manualCallBtn.addEventListener('click', () => executeManualTrade('CALL'));
    manualPutBtn.addEventListener('click', () => executeManualTrade('PUT'));
    soundOnBtn.addEventListener('click', () => setSound(true));
    soundOffBtn.addEventListener('click', () => setSound(false));
    
    // Quick preset amounts
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            amountSelect.value = btn.dataset.amount;
        });
    });
    
    // Tab switching
    document.querySelectorAll('.tab-btn, .nav-item').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            switchTab(tabId);
        });
    });
    
    // Timeframe change
    timeframeSelect.addEventListener('change', () => {
        addLog(`⏱️ Timeframe changed to ${timeframeSelect.value}`, 'info');
        if (isBotRunning) {
            addLog('⚠️ Bot will use new timeframe for next signals', 'warning');
        }
    });
    
    // Socket event handlers
    socket.on('connect', () => {
        addLog('🔌 WebSocket connected to server', 'success');
    });
    
    socket.on('signal', (data) => {
        updateSignalDisplay(data);
    });
    
    socket.on('trade_result', (data) => {
        updateTradeResult(data);
    });
    
    socket.on('balance_update', (data) => {
        balanceDisplay.textContent = `$${data.balance.toFixed(2)}`;
    });
    
    socket.on('log', (data) => {
        addLog(data.message, data.type);
    });
    
    addLog('🚀 PO TRADING MATE initialized', 'success');
    addLog('📡 Enter your Pocket Option credentials and click CONNECT', 'info');
});

function switchTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn, .nav-item').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll(`[data-tab="${tabId}"]`).forEach(btn => {
        btn.classList.add('active');
    });
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabId).classList.add('active');
}

async function connectToPocketOption() {
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    const accountType = accountTypeSelect.value;
    
    if (!email || !password) {
        addLog('❌ Please enter email and password', 'error');
        return;
    }
    
    addLog(`🔐 Connecting to Pocket Option (${accountType.toUpperCase()})...`, 'info');
    
    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, account_type: accountType })
        });
        
        const data = await response.json();
        
        if (data.success) {
            isConnected = true;
            document.querySelector('.status-dot').classList.remove('disconnected');
            document.querySelector('.status-dot').classList.add('connected');
            document.getElementById('statusText').textContent = 'Connected';
            balanceDisplay.textContent = `$${data.balance.toFixed(2)}`;
            addLog(`✅ Connected successfully! Balance: $${data.balance.toFixed(2)}`, 'success');
            
            // Load assets
            await loadAssets();
        } else {
            addLog(`❌ Connection failed: ${data.error}`, 'error');
        }
    } catch (error) {
        addLog(`❌ Connection error: ${error.message}`, 'error');
    }
}

async function disconnectFromPocketOption() {
    try {
        await fetch('/api/disconnect', { method: 'POST' });
        isConnected = false;
        isBotRunning = false;
        document.querySelector('.status-dot').classList.remove('connected');
        document.querySelector('.status-dot').classList.add('disconnected');
        document.getElementById('statusText').textContent = 'Disconnected';
        botStatus.textContent = '⏹ STOPPED';
        botStatus.classList.remove('running');
        botStatus.classList.add('stopped');
        addLog('🔌 Disconnected from Pocket Option', 'info');
    } catch (error) {
        addLog(`❌ Disconnect error: ${error.message}`, 'error');
    }
}

async function loadAssets() {
    try {
        const response = await fetch('/api/assets');
        const assets = await response.json();
        
        assetSelect.innerHTML = '';
        assets.forEach(asset => {
            const option = document.createElement('option');
            option.value = asset.symbol;
            option.textContent = `${asset.name} - ${asset.payout}% payout`;
            assetSelect.appendChild(option);
        });
        
        addLog(`📊 Loaded ${assets.length} assets with 85%+ payout`, 'success');
    } catch (error) {
        addLog(`❌ Failed to load assets: ${error.message}`, 'error');
    }
}

function startBot() {
    if (!isConnected) {
        addLog('❌ Please connect to Pocket Option first', 'error');
        return;
    }
    
    isBotRunning = true;
    botStatus.textContent = '▶ RUNNING';
    botStatus.classList.remove('stopped');
    botStatus.classList.add('running');
    addLog('🤖 Bot started - Auto-trading enabled', 'success');
    
    // Start bot on server
    fetch('/api/start_bot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            asset: assetSelect.value,
            amount: parseFloat(amountSelect.value),
            timeframe: timeframeSelect.value,
            martingale: martingaleEnabled
        })
    });
}

function stopBot() {
    isBotRunning = false;
    botStatus.textContent = '⏹ STOPPED';
    botStatus.classList.remove('running');
    botStatus.classList.add('stopped');
    addLog('🛑 Bot stopped - Auto-trading disabled', 'warning');
    
    fetch('/api/stop_bot', { method: 'POST' });
}

function setMartingale(enabled) {
    martingaleEnabled = enabled;
    if (enabled) {
        martingaleOnBtn.className = 'toggle-btn toggle-on';
        martingaleOffBtn.className = 'toggle-btn toggle-off';
        martingaleStatus.style.display = 'flex';
        addLog('♻️ Martingale ENABLED - 2.3x recovery after losses', 'success');
    } else {
        martingaleOnBtn.className = 'toggle-btn toggle-off';
        martingaleOffBtn.className = 'toggle-btn toggle-on';
        martingaleStatus.style.display = 'none';
        addLog('♻️ Martingale DISABLED - Single trades only', 'info');
    }
}

async function executeManualTrade(direction) {
    if (!isConnected) {
        addLog('❌ Please connect to Pocket Option first', 'error');
        return;
    }
    
    const asset = assetSelect.value;
    const amount = parseFloat(amountSelect.value);
    
    addLog(`💰 Manual ${direction} trade: $${amount} on ${asset}`, 'info');
    
    try {
        const response = await fetch('/api/manual_trade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asset, amount, direction })
        });
        
        const result = await response.json();
        
        if (result.success) {
            addLog(`✅ Manual trade executed: ${direction} on ${asset}`, 'success');
        } else {
            addLog(`❌ Manual trade failed: ${result.error}`, 'error');
        }
    } catch (error) {
        addLog(`❌ Trade error: ${error.message}`, 'error');
    }
}

function setSound(enabled) {
    soundEnabled = enabled;
    if (enabled) {
        soundOnBtn.className = 'sound-btn sound-on';
        soundOffBtn.className = 'sound-btn sound-off';
        addLog('🔊 Sound alerts ENABLED', 'info');
    } else {
        soundOnBtn.className = 'sound-btn sound-off';
        soundOffBtn.className = 'sound-btn sound-on';
        addLog('🔇 Sound alerts DISABLED', 'info');
    }
}

function updateSignalDisplay(signal) {
    currentSignal = signal;
    
    // Update signal box
    let signalClass = 'signal-hold';
    let signalText = 'HOLD';
    if (signal.direction === 'CALL') {
        signalClass = 'signal-call';
        signalText = '🟢 CALL SIGNAL 🟢';
    } else if (signal.direction === 'PUT') {
        signalClass = 'signal-put';
        signalText = '🔴 PUT SIGNAL 🔴';
    } else {
        signalText = '⚪ HOLD ⚪';
    }
    
    signalDisplay.className = `signal-display ${signalClass}`;
    signalDisplay.innerHTML = `
        <div class="signal-direction">${signalText}</div>
        <div class="signal-price">Entry: $${signal.price.toFixed(5)}</div>
        <div class="signal-details">
            Type: ${signal.signal_type.toUpperCase()} | Payout: 85%+ | Expiry: ${signal.expiry_minutes}m
        </div>
    `;
    
    // Update confidence meter
    confidenceBar.style.width = `${signal.confidence}%`;
    confidenceValue.textContent = `${signal.confidence}%`;
    
    // Update rules list
    rulesList.innerHTML = signal.rules_passed.map(rule => `<li>${rule}</li>`).join('');
    
    // Play sound if enabled
    if (soundEnabled && signal.direction !== 'HOLD') {
        playSound(signal.direction);
    }
    
    // Update countdown
    if (signal.time_remaining) {
        countdownTimer.innerHTML = `⏰ SIGNAL READY - ${signal.time_remaining} SECONDS REMAINING ⏰`;
    }
    
    addLog(`📊 Signal: ${signal.direction} with ${signal.confidence}% confidence (${signal.signal_type})`, 'info');
}

function updateTradeResult(result) {
    totalTrades++;
    if (result.is_win) {
        winningTrades++;
        dailyPL += result.profit;
        addLog(`✅ TRADE WIN: ${result.direction} on ${result.asset} | Profit: $${result.profit.toFixed(2)}`, 'success');
        
        if (soundEnabled) {
            playSound('win');
        }
        
        // Reset Martingale display if active
        if (activeMartingale) {
            activeMartingale = null;
            martingaleStatus.style.display = 'none';
        }
    } else {
        dailyPL -= result.amount;
        addLog(`❌ TRADE LOSS: ${result.direction} on ${result.asset} | Loss: $${result.amount.toFixed(2)}`, 'error');
        
        if (soundEnabled) {
            playSound('loss');
        }
        
        // Update Martingale display if enabled and bot is running
        if (martingaleEnabled && isBotRunning && result.next_martingale) {
            activeMartingale = result.martingale_state;
            martingaleStatus.style.display = 'flex';
            martingaleStep.textContent = activeMartingale.step;
            martingaleLoss.textContent = `$${activeMartingale.total_loss.toFixed(2)}`;
            martingaleNext.textContent = `$${activeMartingale.next_amount.toFixed(2)}`;
            addLog(`♻️ Martingale activated: Step ${activeMartingale.step} | Next trade: $${activeMartingale.next_amount.toFixed(2)}`, 'warning');
        }
    }
    
    // Update statistics
    tradeCount.textContent = totalTrades;
    netProfit.textContent = `${dailyPL >= 0 ? '+' : ''}$${dailyPL.toFixed(2)}`;
    const winRate = totalTrades > 0 ? (winningTrades / totalTrades * 100) : 0;
    winRateDisplay.textContent = `${winRate.toFixed(1)}%`;
    dailyPLDisplay.textContent = `${dailyPL >= 0 ? '+' : ''}$${dailyPL.toFixed(2)}`;
    
    lastTrade.textContent = `${result.direction} on ${result.asset} - ${result.is_win ? 'WIN' : 'LOSS'} ${result.is_win ? `+$${result.profit.toFixed(2)}` : `-$${result.amount.toFixed(2)}`}`;
}

function playSound(type) {
    // Simple beep using Web Audio API
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    if (type === 'CALL' || type === 'win') {
        oscillator.frequency.value = 880;
        gainNode.gain.value = 0.3;
        oscillator.start();
        oscillator.stop(audioContext.currentTime + 0.3);
    } else if (type === 'PUT' || type === 'loss') {
        oscillator.frequency.value = 440;
        gainNode.gain.value = 0.3;
        oscillator.start();
        oscillator.stop(audioContext.currentTime + 0.5);
    }
}

function addLog(message, type) {
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    const timestamp = new Date().toLocaleTimeString();
    let icon = '📌';
    if (type === 'success') icon = '✅';
    else if (type === 'error') icon = '❌';
    else if (type === 'warning') icon = '⚠️';
    else if (type === 'info') icon = 'ℹ️';
    
    logEntry.innerHTML = `[${timestamp}] ${icon} ${message}`;
    logConsole.appendChild(logEntry);
    logConsole.scrollTop = logConsole.scrollHeight;
    
    // Keep only last 100 logs
    while (logConsole.children.length > 100) {
        logConsole.removeChild(logConsole.firstChild);
    }
}
