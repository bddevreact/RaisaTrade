// Global variables
let socket;
let charts = {};
let updateInterval;
let livePairs = new Set();

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeSocket();
    initializeEventListeners();
    loadInitialData();
    startAutoUpdate();
    // Seed with default/top symbols to show some live pairs initially
    ['BTC_USDT','ETH_USDT','DOT_USDT'].forEach(addLivePair);
});

// Add event listener for change trading pair button
document.addEventListener('DOMContentLoaded', function() {
    const changePairBtn = document.getElementById('change-trading-pair-btn');
    if (changePairBtn) {
        changePairBtn.addEventListener('click', function() {
            showTradingPairModal();
        });
    }
});

// Show trading pair selection modal
function showTradingPairModal() {
    const modal = `
        <div class="modal fade" id="tradingPairModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Select Trading Pair</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>
                            <strong>Current Pair:</strong> <span id="current-pair-display">BTC_USDT</span>
                        </div>
                        
                        <div class="row">
                            <div class="col-6 mb-2">
                                <button class="btn btn-outline-primary w-100 trading-pair-btn" data-pair="BTC_USDT">
                                    <strong>BTC/USDT</strong><br><small>Bitcoin</small>
                                </button>
                            </div>
                            <div class="col-6 mb-2">
                                <button class="btn btn-outline-primary w-100 trading-pair-btn" data-pair="ETH_USDT">
                                    <strong>ETH/USDT</strong><br><small>Ethereum</small>
                                </button>
                            </div>
                            <div class="col-6 mb-2">
                                <button class="btn btn-outline-primary w-100 trading-pair-btn" data-pair="DOT_USDT">
                                    <strong>DOT/USDT</strong><br><small>Polkadot</small>
                                </button>
                            </div>
                            <div class="col-6 mb-2">
                                <button class="btn btn-outline-primary w-100 trading-pair-btn" data-pair="ADA_USDT">
                                    <strong>ADA/USDT</strong><br><small>Cardano</small>
                                </button>
                            </div>
                            <div class="col-6 mb-2">
                                <button class="btn btn-outline-primary w-100 trading-pair-btn" data-pair="SOL_USDT">
                                    <strong>SOL/USDT</strong><br><small>Solana</small>
                                </button>
                            </div>
                            <div class="col-6 mb-2">
                                <button class="btn btn-outline-primary w-100 trading-pair-btn" data-pair="XRP_USDT">
                                    <strong>XRP/USDT</strong><br><small>Ripple</small>
                                </button>
                            </div>
                        </div>
                        
                        <div class="mt-3">
                            <label class="form-label">Or enter custom pair:</label>
                            <div class="input-group">
                                <input type="text" class="form-control" id="custom-trading-pair" placeholder="e.g., LINK_USDT">
                                <button class="btn btn-primary" type="button" id="set-custom-pair">Set</button>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('tradingPairModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modal);
    
    // Show current pair
    const currentPairDisplay = document.getElementById('current-pair-display');
    if (currentPairDisplay) {
        const currentPair = document.getElementById('current-trading-pair');
        if (currentPair) {
            currentPairDisplay.textContent = currentPair.textContent;
        }
    }
    
    // Add event listeners
    const tradingPairBtns = document.querySelectorAll('.trading-pair-btn');
    tradingPairBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const pair = this.getAttribute('data-pair');
            updateTradingPair(pair);
        });
    });
    
    // Custom pair input
    const setCustomPairBtn = document.getElementById('set-custom-pair');
    if (setCustomPairBtn) {
        setCustomPairBtn.addEventListener('click', function() {
            const customPair = document.getElementById('custom-trading-pair').value.trim().toUpperCase();
            if (customPair) {
                updateTradingPair(customPair);
            }
        });
    }
    
    // Show modal
    const modalElement = document.getElementById('tradingPairModal');
    const bsModal = new bootstrap.Modal(modalElement);
    bsModal.show();
}

// Update trading pair
function updateTradingPair(newPair) {
    console.log('Updating trading pair to:', newPair);
    
    fetch('/api/update-trading-pair', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            trading_pair: newPair
        })
    })
    .then(response => {
        console.log('Response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Response data:', data);
        if (data.success) {
            // Update the trading pair display directly
            const tradingPairDisplay = document.getElementById('trading-pair-display');
            
            console.log('Found tradingPairDisplay:', tradingPairDisplay);
            
            if (tradingPairDisplay) {
                const pairInfo = newPair.split('_');
                const baseCurrency = pairInfo[0];
                const quoteCurrency = pairInfo[1] || 'USDT';
                
                tradingPairDisplay.innerHTML = `
                    <div class="d-flex align-items-center justify-content-center">
                        <i class="fas fa-chart-line me-2"></i>
                        <div>
                            <small class="text-muted d-block">Trading Pair</small>
                            <strong id="current-trading-pair">${baseCurrency}/${quoteCurrency}</strong>
                            <br><small class="text-muted">${newPair}</small>
                        </div>
                    </div>
                `;
                console.log('Updated trading-pair-display element with new pair:', newPair);
                addLivePair(newPair);
            } else {
                console.error('trading-pair-display element not found!');
            }
            
            // Also update the auto trading status to refresh everything
            loadAutoTradingStatus();
            
            // Show success message
            showNotification('✅ Trading pair updated successfully!', 'success');
            
            // Close modal
            const modal = document.getElementById('tradingPairModal');
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        } else {
            console.error('Failed to update trading pair:', data.error);
            showNotification('❌ Failed to update trading pair: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error updating trading pair:', error);
        showNotification('❌ Error updating trading pair', 'error');
    });
}

// Initialize WebSocket connection
function initializeSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to server');
        updateConnectionStatus(true);
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateConnectionStatus(false);
    });
    
    socket.on('price_update', function(data) {
        updatePriceDisplay(data);
    });
    
    socket.on('connected', function(data) {
        console.log('Socket connected:', data);
    });
}

// Initialize event listeners
function initializeEventListeners() {
    // Auto trading buttons
    document.getElementById('enable-auto-trading').addEventListener('click', enableAutoTrading);
    document.getElementById('disable-auto-trading').addEventListener('click', disableAutoTrading);
    
    // Trade form
    document.getElementById('execute-trade').addEventListener('click', executeTrade);
    document.getElementById('trade-order-type').addEventListener('change', toggleLimitPrice);
    
    // Analysis
    document.getElementById('run-analysis').addEventListener('click', runAnalysis);
    
    // Settings
    document.getElementById('save-settings').addEventListener('click', saveSettings);
    
    // Test email button
    const testEmailBtn = document.getElementById('test-email-btn');
    if (testEmailBtn) {
        testEmailBtn.addEventListener('click', testEmailNotification);
    }
    
    // Trading hours toggle
    const tradingHoursEnabled = document.getElementById('trading-hours-enabled');
    if (tradingHoursEnabled) {
        tradingHoursEnabled.addEventListener('change', toggleTradingHoursConfig);
    }
    
    // Strategy management
    const defaultStrategySelect = document.getElementById('default-strategy');
    if (defaultStrategySelect) {
        defaultStrategySelect.addEventListener('change', function() {
            updateStrategy(this.value);
            updateStrategyDescription(this.value);
        });
    }
    
    const testStrategyBtn = document.getElementById('test-strategy');
    if (testStrategyBtn) {
        testStrategyBtn.addEventListener('click', function() {
            const strategySelect = document.getElementById('default-strategy');
            const selectedStrategy = strategySelect ? strategySelect.value : 'ADVANCED_STRATEGY';
            testStrategy(selectedStrategy);
        });
    }
    
    // Chart symbol change
    document.getElementById('chart-symbol').addEventListener('change', function() {
        loadChartData(this.value);
    });
    
    // Chart timeframe change
    document.getElementById('chart-timeframe').addEventListener('change', function() {
        const symbol = document.getElementById('chart-symbol').value;
        loadChartData(symbol, this.value);
    });
    
    // Load chart data when Charts tab is clicked
    document.getElementById('charts-tab').addEventListener('click', function() {
        const symbol = document.getElementById('chart-symbol').value;
        
        // Add a small delay to ensure the tab is active before loading chart
        setTimeout(() => {
            loadChartData(symbol);
        }, 100);
        
        // Load real-time market data
        loadAllMarketData();
        loadLiveTrades(symbol);
        loadMarketDepth(symbol);
        
        // Set up real-time updates
        setInterval(() => {
            loadAllMarketData();
            loadLiveTrades(symbol);
            loadMarketDepth(symbol);
        }, 10000); // Update every 10 seconds
        
        // Ensure the selected symbol is tracked as live
        addLivePair(symbol);
    });
    
    // Update modal balance when trade modal opens
    const tradeModal = document.getElementById('tradeModal');
    if (tradeModal) {
        tradeModal.addEventListener('show.bs.modal', updateModalBalance);
    }
    
    // Load current strategy when settings modal opens
    const settingsModal = document.getElementById('settingsModal');
    if (settingsModal) {
        settingsModal.addEventListener('show.bs.modal', function() {
            loadCurrentStrategy();
        });
    }
}

// Initialize trading pair display with default values
function initializeTradingPairDisplay() {
    const tradingPairDisplay = document.getElementById('trading-pair-display');
    
    if (tradingPairDisplay) {
        const defaultPair = 'BTC_USDT';
        const pairInfo = defaultPair.split('_');
        const baseCurrency = pairInfo[0];
        const quoteCurrency = pairInfo[1] || 'USDT';
        
        tradingPairDisplay.innerHTML = `
            <div class="d-flex align-items-center justify-content-center">
                <i class="fas fa-chart-line me-2"></i>
                <div>
                    <small class="text-muted d-block">Trading Pair</small>
                    <strong id="current-trading-pair">${baseCurrency}/${quoteCurrency}</strong>
                    <br><small class="text-muted">${defaultPair}</small>
                </div>
            </div>
        `;
        console.log('Initialized trading pair display with default pair:', defaultPair);
    } else {
        console.error('trading-pair-display element not found during initialization!');
    }
}

// Load initial data
function loadInitialData() {
    loadBalance();
    loadPositions();
    loadHistory();
    loadSettings();
    loadAutoTradingStatus();
    loadActiveStrategies();
    initializeTradingPairDisplay(); // Initialize trading pair display
}

// Start auto update
function startAutoUpdate() {
    updateInterval = setInterval(() => {
        loadBalance();
        loadPositions();
        loadAutoTradingStatus();
        updateRealTimePrices();
    }, 30000); // Update every 30 seconds
}

// Update real-time prices
function updateRealTimePrices() {
    const symbols = ['BTC_USDT', 'ETH_USDT', 'DOT_USDT'];
    
    symbols.forEach(symbol => {
        fetch(`/api/real-time-price/${symbol}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updatePriceDisplay(symbol, data.data.price);
                }
            })
            .catch(error => {
                console.error(`Error updating price for ${symbol}:`, error);
            });
    });
}

// Update price display
function updatePriceDisplay(symbol, price) {
    const priceElement = document.getElementById(`price-${symbol}`);
    if (priceElement) {
        const formattedPrice = formatCurrency(price);
        priceElement.textContent = formattedPrice;
        
        // Add price change animation
        priceElement.classList.add('price-update');
        setTimeout(() => {
            priceElement.classList.remove('price-update');
        }, 1000);
    }
}

// Wait for container to be available
function waitForContainer(containerId, maxAttempts = 10) {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        
        const checkContainer = () => {
            attempts++;
            const container = document.getElementById(containerId);
            
            if (container) {
                resolve(container);
            } else if (attempts >= maxAttempts) {
                reject(new Error(`Container ${containerId} not found after ${maxAttempts} attempts`));
            } else {
                setTimeout(checkContainer, 100);
            }
        };
        
        checkContainer();
    });
}

// Load real-time market data for all top cryptocurrencies
function loadAllMarketData() {
    const symbols = Array.from(livePairs.size ? livePairs : new Set(['BTC_USDT', 'ETH_USDT', 'DOT_USDT', 'ADA_USDT', 'SOL_USDT']));
    // Add a small delay to ensure DOM is fully loaded
    setTimeout(() => {
        symbols.forEach(symbol => {
            loadRealTimeMarketData(symbol);
        });
    }, 100);
}

// Load real-time market data
function loadRealTimeMarketData(symbol) {
    console.log(`Loading market data for ${symbol}...`);
    
    fetch(`/api/market-data/${symbol}`)
        .then(response => response.json())
        .then(data => {
            console.log(`Market data response for ${symbol}:`, data);
            if (data.success) {
                // Wait for container to be available before updating
                waitForContainer(`market-data-${symbol}`)
                    .then(() => {
                        updateMarketDataDisplay(symbol, data.data);
                    })
                    .catch(error => {
                        console.error(`Container not found for ${symbol}:`, error);
                        // Try to create the container if it doesn't exist
                        createMarketDataContainer(symbol);
                    });
            } else {
                console.error(`Error loading market data for ${symbol}:`, data.error);
                // Show error in the container if available
                waitForContainer(`market-data-${symbol}`)
                    .then(container => {
                        container.innerHTML = `
                            <div class="alert alert-warning">
                                <i class="fas fa-exclamation-triangle me-2"></i>
                                Failed to load market data: ${data.error}
                            </div>
                        `;
                    })
                    .catch(error => {
                        console.error(`Container not found for ${symbol}:`, error);
                    });
            }
        })
        .catch(error => {
            console.error(`Error loading market data for ${symbol}:`, error);
            // Show error in the container if available
            waitForContainer(`market-data-${symbol}`)
                .then(container => {
                    container.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-circle me-2"></i>
                            Network error: ${error.message}
                        </div>
                    `;
                })
                .catch(containerError => {
                    console.error(`Container not found for ${symbol}:`, containerError);
                });
        });
}

// Update market data display
function updateMarketDataDisplay(symbol, marketData) {
    const container = document.getElementById(`market-data-${symbol}`);
    
    if (container) {
        try {
            const priceChange = marketData.priceChangePercent || 0;
            const priceChangeClass = priceChange >= 0 ? 'text-success' : 'text-danger';
            const priceChangeIcon = priceChange >= 0 ? '▲' : '▼';
            const currentPrice = marketData.price || 0;
            const high = marketData.high || 0;
            const low = marketData.low || 0;
            const volume = marketData.volume || 0;
            
            container.innerHTML = `
                <div class="text-center">
                    <div class="h4 mb-2 fw-bold">$${currentPrice.toFixed(2)}</div>
                    <div class="h6 ${priceChangeClass} mb-2">
                        ${priceChangeIcon} ${Math.abs(priceChange).toFixed(2)}%
                    </div>
                    <div class="row text-muted small">
                        <div class="col-6">
                            <div>High: $${high.toFixed(2)}</div>
                            <div>Low: $${low.toFixed(2)}</div>
                        </div>
                        <div class="col-6">
                            <div>Vol: ${volume.toFixed(0)}</div>
                            <div class="text-truncate">${symbol.replace('_USDT', '')}</div>
                        </div>
                    </div>
                </div>
            `;
            
            // Add price change animation
            container.classList.add('price-update');
            setTimeout(() => {
                container.classList.remove('price-update');
            }, 1000);
            
        } catch (error) {
            console.error(`Error updating market data display for ${symbol}:`, error);
            container.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error displaying market data: ${error.message}
                </div>
            `;
        }
    } else {
        console.error(`Market data container not found for ${symbol}`);
    }
}

// Load live trades
function loadLiveTrades(symbol, limit = 20) {
    // Ensure container exists
    const containerId = `live-trades-${symbol}`;
    if (!document.getElementById(containerId)) {
        const parent = document.getElementById('live-trades-container');
        if (parent) {
            const div = document.createElement('div');
            div.id = containerId;
            div.innerHTML = `<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Loading live trades...</p></div>`;
            parent.innerHTML = '';
            parent.appendChild(div);
        }
    }
    fetch(`/api/live-trades/${symbol}?limit=${limit}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateLiveTradesDisplay(symbol, data.data.trades);
            } else {
                console.error(`Error loading live trades for ${symbol}:`, data.error);
            }
        })
        .catch(error => {
            console.error(`Error loading live trades for ${symbol}:`, error);
        });
}

// Update live trades display
function updateLiveTradesDisplay(symbol, trades) {
    const container = document.getElementById(`live-trades-${symbol}`);
    if (container) {
        // Check if trades is an array and has data
        if (trades && Array.isArray(trades) && trades.length > 0) {
            const tradesHtml = trades.slice(0, 10).map(trade => {
                const side = trade.side === 'BUY' ? 'text-success' : 'text-danger';
                const sideIcon = trade.side === 'BUY' ? '▲' : '▼';
                const time = new Date(trade.time || trade.timestamp || Date.now()).toLocaleTimeString();
                
                return `
                    <div class="d-flex justify-content-between align-items-center py-1">
                        <span class="${side}">${sideIcon} $${parseFloat(trade.price || 0).toFixed(2)}</span>
                        <span class="text-muted">${parseFloat(trade.qty || trade.quantity || 0).toFixed(4)}</span>
                        <small class="text-muted">${time}</small>
                    </div>
                `;
            }).join('');
            
            container.innerHTML = tradesHtml;
        } else {
            // Show no trades message
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fas fa-info-circle me-2"></i>
                    No recent trades available
                </div>
            `;
        }
    } else {
        console.error(`Live trades container not found for ${symbol}`);
    }
}

// Load market depth
function loadMarketDepth(symbol, limit = 20) {
    // Ensure container exists
    const containerId = `market-depth-${symbol}`;
    if (!document.getElementById(containerId)) {
        const parent = document.getElementById('market-depth-container');
        if (parent) {
            const div = document.createElement('div');
            div.id = containerId;
            div.innerHTML = `<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Loading market depth...</p></div>`;
            parent.innerHTML = '';
            parent.appendChild(div);
        }
    }
    fetch(`/api/market-depth/${symbol}?limit=${limit}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateMarketDepthDisplay(symbol, data.data);
            } else {
                console.error(`Error loading market depth for ${symbol}:`, data.error);
            }
        })
        .catch(error => {
            console.error(`Error loading market depth for ${symbol}:`, error);
        });
}

// Update market depth display
function updateMarketDepthDisplay(symbol, depthData) {
    const container = document.getElementById(`market-depth-${symbol}`);
    if (container) {
        const asks = depthData.asks.slice(0, 10);
        const bids = depthData.bids.slice(0, 10);
        
        const asksHtml = asks.map(ask => `
            <div class="d-flex justify-content-between align-items-center py-1">
                <span class="text-danger">$${parseFloat(ask[0]).toFixed(2)}</span>
                <span class="text-muted">${parseFloat(ask[1]).toFixed(4)}</span>
            </div>
        `).join('');
        
        const bidsHtml = bids.map(bid => `
            <div class="d-flex justify-content-between align-items-center py-1">
                <span class="text-success">$${parseFloat(bid[0]).toFixed(2)}</span>
                <span class="text-muted">${parseFloat(bid[1]).toFixed(4)}</span>
            </div>
        `).join('');
        
        container.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6 class="text-danger">Asks</h6>
                    ${asksHtml}
                </div>
                <div class="col-md-6">
                    <h6 class="text-success">Bids</h6>
                    ${bidsHtml}
                </div>
            </div>
        `;
    }
}

// Enhanced chart data loading with real-time updates
function loadChartDataWithRealtime(symbol, timeframe = '5M') {
    // Load initial chart data
    loadChartData(symbol, timeframe);
    
    // Set up real-time updates
    setInterval(() => {
        loadChartData(symbol, timeframe);
    }, 60000); // Update every minute
}

// Update connection status
function updateConnectionStatus(connected) {
    const statusElement = document.getElementById('connection-status');
    const textElement = document.getElementById('connection-text');
    
    if (statusElement && textElement) {
        if (connected) {
            statusElement.className = 'status-indicator status-online';
            textElement.textContent = 'Connected';
        } else {
            statusElement.className = 'status-indicator status-offline';
            textElement.textContent = 'Disconnected';
        }
    }
}

// Load account balance
function loadBalance() {
    fetch('/api/balance')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateBalanceDisplay(data.data);
            } else {
                showToast('Error', 'Failed to load balance: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error loading balance:', error);
            showToast('Error', 'Failed to load balance', 'error');
        });
}

// Update balance display
function updateBalanceDisplay(balance) {
    const totalBalance = parseFloat(balance.total || 0);
    const availableBalance = parseFloat(balance.available || 0);
    const frozenBalance = parseFloat(balance.frozen || 0);
    
    const totalBalanceElement = document.getElementById('total-balance');
    const availableBalanceElement = document.getElementById('available-balance');
    const frozenBalanceElement = document.getElementById('frozen-balance');

    if (totalBalanceElement) totalBalanceElement.textContent = formatCurrency(totalBalance);
    if (availableBalanceElement) availableBalanceElement.textContent = formatCurrency(availableBalance);
    if (frozenBalanceElement) frozenBalanceElement.textContent = formatCurrency(frozenBalance);
}

// Load positions
function loadPositions() {
    fetch('/api/positions')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updatePositionsTable(data.data);
            } else {
                showToast('Error', 'Failed to load positions: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error loading positions:', error);
            showToast('Error', 'Failed to load positions', 'error');
        });
}

// Update positions table
function updatePositionsTable(positions) {
    const tbody = document.getElementById('positions-table');
    
    if (!tbody) {
        console.error('Positions table not found');
        return;
    }

    if (!positions || positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">No open positions</td></tr>';
        return;
    }
    
    let html = '';
    let totalInvestment = 0;
    
    positions.forEach(position => {
        const size = parseFloat(position.size || 0);
        const entryPrice = parseFloat(position.entryPrice || 0);
        const markPrice = parseFloat(position.markPrice || 0);
        const pnl = parseFloat(position.unrealizedPnl || 0);
        const roe = parseFloat(position.roe || 0);
        const symbol = position.symbol || '';
        
        // Calculate investment amount (size * entry price)
        const investmentAmount = size * entryPrice;
        totalInvestment += investmentAmount;
        
        const pnlClass = pnl >= 0 ? 'text-success' : 'text-danger';
        const roeClass = roe >= 0 ? 'text-success' : 'text-danger';
        
        html += `
            <tr>
                <td><strong>${symbol}</strong></td>
                <td>${size.toFixed(4)}</td>
                <td>$${entryPrice.toFixed(4)}</td>
                <td>$${markPrice.toFixed(4)}</td>
                <td><span class="investment-amount">$${investmentAmount.toFixed(2)}</span></td>
                <td class="${pnlClass}">$${pnl.toFixed(2)}</td>
                <td class="${roeClass}">${roe.toFixed(2)}%</td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="closePosition('${symbol}')">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    // Add total investment summary row
    if (totalInvestment > 0) {
        html += `
            <tr class="total-investment-row">
                <td colspan="4"><strong>Total Investment:</strong></td>
                <td><span class="investment-amount">$${totalInvestment.toFixed(2)}</span></td>
                <td colspan="3"></td>
            </tr>
        `;
    }
    
    tbody.innerHTML = html;
}

// Load trading history
function loadHistory() {
    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateHistoryTable(data.data);
            } else {
                showToast('Error', 'Failed to load history: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error loading history:', error);
            showToast('Error', 'Failed to load history', 'error');
        });
}

// Update history table
function updateHistoryTable(history) {
    const tbody = document.getElementById('history-table');
    
    if (!tbody) {
        console.error('History table not found');
        return;
    }

    if (!history || history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No trading history</td></tr>';
        return;
    }
    
    let html = '';
    history.forEach(trade => {
        const time = new Date(trade.time || trade.timestamp).toLocaleString();
        const symbol = trade.symbol || '';
        const side = trade.side || '';
        const size = parseFloat(trade.size || 0);
        const price = parseFloat(trade.price || 0);
        const fee = parseFloat(trade.fee || 0);
        const pnl = parseFloat(trade.pnl || 0);
        
        const sideClass = side === 'BUY' ? 'text-success' : 'text-danger';
        const pnlClass = pnl >= 0 ? 'text-success' : 'text-danger';
        
        html += `
            <tr>
                <td>${time}</td>
                <td><strong>${symbol}</strong></td>
                <td class="${sideClass}">${side}</td>
                <td>${size.toFixed(4)}</td>
                <td>$${price.toFixed(4)}</td>
                <td>$${fee.toFixed(4)}</td>
                <td class="${pnlClass}">$${pnl.toFixed(2)}</td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// Load settings
function loadSettings() {
    fetch('/api/settings')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateSettingsForm(data.data);
            } else {
                showToast('Error', 'Failed to load settings: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error loading settings:', error);
            showToast('Error', 'Failed to load settings', 'error');
        });
}

// Update settings form
function updateSettingsForm(settings) {
    const tradingPairElement = document.getElementById('setting-trading-pair');
    const positionSizeElement = document.getElementById('setting-position-size');
    const leverageElement = document.getElementById('setting-leverage');
    const tradingAmountElement = document.getElementById('setting-trading-amount');
    const maxDailyLossElement = document.getElementById('setting-max-daily-loss');
    const stopLossElement = document.getElementById('setting-stop-loss');
    const takeProfitElement = document.getElementById('setting-take-profit');
    const trailingStopElement = document.getElementById('setting-trailing-stop');
    const defaultStrategyElement = document.getElementById('default-strategy');

    // Basic trading settings
    if (tradingPairElement) tradingPairElement.value = settings.trading_pair || 'DOT_USDT';
    if (positionSizeElement) positionSizeElement.value = settings.position_size || 0.5;
    if (leverageElement) leverageElement.value = settings.leverage || 10;
    if (tradingAmountElement) tradingAmountElement.value = settings.trading_amount || 100;
    if (maxDailyLossElement) maxDailyLossElement.value = settings.max_daily_loss || 500;
    if (stopLossElement) stopLossElement.value = settings.stop_loss_percentage || 1.5;
    if (takeProfitElement) takeProfitElement.value = settings.take_profit_percentage || 2.5;
    if (trailingStopElement) trailingStopElement.value = settings.trailing_stop_percentage || 1.0;
    if (defaultStrategyElement) defaultStrategyElement.value = settings.default_strategy || 'ADVANCED_STRATEGY';

    // Trading hours settings
    const tradingHours = settings.trading_hours || {};
    const tradingHoursEnabled = document.getElementById('trading-hours-enabled');
    const tradingStartTime = document.getElementById('trading-start-time');
    const tradingEndTime = document.getElementById('trading-end-time');
    const tradingTimezone = document.getElementById('trading-timezone');
    const excludeWeekends = document.getElementById('exclude-weekends');
    const excludeHolidays = document.getElementById('exclude-holidays');

    if (tradingHoursEnabled) tradingHoursEnabled.checked = tradingHours.enabled !== false;
    if (tradingStartTime) tradingStartTime.value = tradingHours.start || '19:30';
    if (tradingEndTime) tradingEndTime.value = tradingHours.end || '01:30';
    if (tradingTimezone) tradingTimezone.value = tradingHours.timezone || 'UTC-5';
    if (excludeWeekends) excludeWeekends.checked = tradingHours.exclude_weekends || false;
    if (excludeHolidays) excludeHolidays.checked = tradingHours.exclude_holidays || false;

    // RSI settings
    const rsiSettings = settings.rsi || {};
    const rsiPeriod = document.getElementById('rsi-period');
    const rsiOverbought = document.getElementById('rsi-overbought');
    const rsiOversold = document.getElementById('rsi-oversold');

    if (rsiPeriod) rsiPeriod.value = rsiSettings.period || 7;
    if (rsiOverbought) rsiOverbought.value = rsiSettings.overbought || 70;
    if (rsiOversold) rsiOversold.value = rsiSettings.oversold || 30;

    // Notification settings
    const notifications = settings.notifications || {};
    const telegramEnabled = document.getElementById('telegram-enabled');
    const telegramToken = document.getElementById('telegram-token');
    const telegramUserId = document.getElementById('telegram-user-id');
    const emailEnabled = document.getElementById('email-enabled');
    const notificationEmail = document.getElementById('notification-email');
    const smtpServer = document.getElementById('smtp-server');
    const senderEmail = document.getElementById('sender-email');
    const senderPassword = document.getElementById('sender-password');

    if (telegramEnabled) telegramEnabled.checked = notifications.telegram?.enabled || false;
    if (telegramToken) telegramToken.value = notifications.telegram?.bot_token || '';
    if (telegramUserId) telegramUserId.value = notifications.telegram?.user_id || '';
    if (emailEnabled) emailEnabled.checked = notifications.email?.enabled || false;
    if (notificationEmail) notificationEmail.value = notifications.email?.recipient_email || '';
    if (smtpServer) smtpServer.value = notifications.email?.smtp_server || 'smtp.gmail.com';
    if (senderEmail) senderEmail.value = notifications.email?.sender_email || '';
    if (senderPassword) senderPassword.value = notifications.email?.sender_password || '';

    // Notification types
    const notifyTrades = document.getElementById('notify-trades');
    const notifyErrors = document.getElementById('notify-errors');
    const notifyBalance = document.getElementById('notify-balance');
    const notifyStatus = document.getElementById('notify-status');

    if (notifyTrades) notifyTrades.checked = notifications.types?.trade_notifications !== false;
    if (notifyErrors) notifyErrors.checked = notifications.types?.error_notifications !== false;
    if (notifyBalance) notifyBalance.checked = notifications.types?.balance_notifications !== false;
    if (notifyStatus) notifyStatus.checked = notifications.types?.status_notifications !== false;

    // Toggle trading hours config visibility
    toggleTradingHoursConfig();
}

// Load auto trading status
function loadAutoTradingStatus() {
    fetch('/api/auto-trading/status')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateAutoTradingStatus(data.data);
            } else {
                console.error('Failed to load auto trading status:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading auto trading status:', error);
        });
}

// Update auto trading status
function updateAutoTradingStatus(status) {
    const statusElement = document.getElementById('auto-trading-status');
    const textElement = document.getElementById('auto-trading-text');
    const tradingLiveIndicator = document.getElementById('trading-live-indicator');
    
    if (statusElement && textElement) {
        if (status.auto_trading_enabled) {
            statusElement.className = 'status-indicator status-online';
            textElement.textContent = 'Enabled';
            
            // Animate TRADING LIVE indicator when enabled
            if (tradingLiveIndicator) {
                tradingLiveIndicator.classList.add('trading-live-active');
                tradingLiveIndicator.classList.remove('trading-live-inactive');
                
                // Add pulsing animation
                tradingLiveIndicator.style.animation = 'pulse 2s infinite';
                
                // Change text to animated version
                tradingLiveIndicator.innerHTML = `
                    <div class="trading-live-content">
                        <i class="fas fa-broadcast-tower me-2 animate-pulse"></i>
                        <span class="trading-live-text">TRADING LIVE</span>
                        <div class="trading-live-dots">
                            <span class="dot"></span>
                            <span class="dot"></span>
                            <span class="dot"></span>
                        </div>
                    </div>
                `;
            }
        } else {
            statusElement.className = 'status-indicator status-offline';
            textElement.textContent = 'Disabled';
            
            // Animate TRADING LIVE indicator when disabled
            if (tradingLiveIndicator) {
                tradingLiveIndicator.classList.add('trading-live-inactive');
                tradingLiveIndicator.classList.remove('trading-live-active');
                
                // Remove pulsing animation
                tradingLiveIndicator.style.animation = 'none';
                
                // Change text to inactive version
                tradingLiveIndicator.innerHTML = `
                    <div class="trading-live-content">
                        <i class="fas fa-pause-circle me-2"></i>
                        <span class="trading-live-text">TRADING OFF</span>
                    </div>
                `;
            }
        }
    }
    
    // Update trading pair display - always update this
    const tradingPairDisplay = document.getElementById('trading-pair-display');
    if (tradingPairDisplay) {
        const tradingPair = status.current_pair || 'BTC_USDT';
        const pairInfo = tradingPair.split('_');
        const baseCurrency = pairInfo[0];
        const quoteCurrency = pairInfo[1] || 'USDT';
        
        tradingPairDisplay.innerHTML = `
            <div class="d-flex align-items-center justify-content-center">
                <i class="fas fa-chart-line me-2"></i>
                <div>
                    <small class="text-muted d-block">Trading Pair</small>
                    <strong id="current-trading-pair">${baseCurrency}/${quoteCurrency}</strong>
                    <br><small class="text-muted">${tradingPair}</small>
                </div>
            </div>
        `;
        console.log('Updated trading pair display from status:', tradingPair);
        addLivePair(tradingPair);
    }
    
    // If no status provided, still initialize the display
    if (!status || Object.keys(status).length === 0) {
        initializeTradingPairDisplay();
    }
}

// Enable auto trading
function enableAutoTrading() {
    showLoading('enable-auto-trading');
    
    fetch('/api/auto-trading/enable', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        hideLoading('enable-auto-trading');
        if (data.success) {
            showToast('Success', 'Auto trading enabled', 'success');
            loadAutoTradingStatus();
            loadActiveStrategies(); // Refresh active strategies
        } else {
            showToast('Error', 'Failed to enable auto trading: ' + data.error, 'error');
        }
    })
    .catch(error => {
        hideLoading('enable-auto-trading');
        console.error('Error enabling auto trading:', error);
        showToast('Error', 'Failed to enable auto trading', 'error');
    });
}

// Disable auto trading
function disableAutoTrading() {
    showLoading('disable-auto-trading');
    
    fetch('/api/auto-trading/disable', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        hideLoading('disable-auto-trading');
        if (data.success) {
            showToast('Success', 'Auto trading disabled', 'success');
            loadAutoTradingStatus();
            loadActiveStrategies(); // Refresh active strategies
        } else {
            showToast('Error', 'Failed to disable auto trading: ' + data.error, 'error');
        }
    })
    .catch(error => {
        hideLoading('disable-auto-trading');
        console.error('Error disabling auto trading:', error);
        showToast('Error', 'Failed to disable auto trading', 'error');
    });
}

// Execute trade
async function executeTrade() {
    const symbol = document.getElementById('trade-symbol').value;
    const side = document.querySelector('input[name="trade-side"]:checked').value;
    const orderType = document.getElementById('trade-order-type').value;
    const quantity = parseFloat(document.getElementById('trade-quantity').value);
    const price = parseFloat(document.getElementById('trade-price').value);
    
    if (!symbol || !quantity) {
        showToast('Error', 'Please fill in all required fields', 'error');
        return;
    }
    
    if (orderType === 'LIMIT' && !price) {
        showToast('Error', 'Please enter a price for limit orders', 'error');
        return;
    }
    
    // Check balance before executing trade
    const totalBalance = parseFloat(document.getElementById('total-balance').textContent.replace(/[^0-9.-]+/g, ''));
    const availableBalance = parseFloat(document.getElementById('available-balance').textContent.replace(/[^0-9.-]+/g, ''));
    
    if (side === 'BUY' && availableBalance <= 0) {
        showToast('Error', 'Insufficient balance to execute buy order. Please add funds to your account.', 'error');
        return;
    }
    
    // Show confirmation for large trades
    const estimatedCost = side === 'BUY' ? quantity * (price || 50000) : 0; // Rough estimate
    if (side === 'BUY' && estimatedCost > availableBalance * 0.5) {
        const confirmTrade = confirm(
            `This trade will use approximately $${estimatedCost.toFixed(2)} from your available balance of $${availableBalance.toFixed(2)}. Do you want to proceed?`
        );
        if (!confirmTrade) {
            return;
        }
    }
    
    showLoading('execute-trade');
    
    try {
        const validationResult = await validateTrade(symbol, side, quantity, orderType, price);
        if (validationResult.valid) {
            const tradeData = {
                symbol: symbol,
                side: side,
                quantity: quantity,
                order_type: orderType
            };
            
            if (price) {
                tradeData.price = price;
            }
            
            const response = await fetch('/api/trade', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(tradeData)
            });
            const data = await response.json();
            
            hideLoading('execute-trade');
            if (data.success) {
                showToast('Success', 'Trade executed successfully', 'success');
                document.getElementById('trade-form').reset();
                bootstrap.Modal.getInstance(document.getElementById('tradeModal')).hide();
                loadPositions();
                loadHistory();
                loadBalance(); // Refresh balance after trade
            } else {
                showToast('Error', 'Failed to execute trade: ' + data.error, 'error');
            }
        } else {
            hideLoading('execute-trade');
            showToast('Error', 'Trade validation failed: ' + validationResult.error, 'error');
        }
    } catch (error) {
        hideLoading('execute-trade');
        console.error('Error executing trade:', error);
        showToast('Error', 'Failed to execute trade', 'error');
    }
}

// Toggle limit price field
function toggleLimitPrice() {
    const orderType = document.getElementById('trade-order-type').value;
    const limitPriceGroup = document.getElementById('limit-price-group');
    
    if (limitPriceGroup) {
        if (orderType === 'LIMIT') {
            limitPriceGroup.style.display = 'block';
            document.getElementById('trade-price').required = true;
        } else {
            limitPriceGroup.style.display = 'none';
            document.getElementById('trade-price').required = false;
        }
    }
}

// Run analysis
function runAnalysis() {
    const symbol = document.getElementById('analysis-symbol').value;
    
    if (!symbol) {
        showToast('Error', 'Please select a symbol', 'error');
        return;
    }
    
    showLoading('run-analysis');
    
    fetch(`/api/analysis/${symbol}`)
        .then(response => response.json())
        .then(data => {
            hideLoading('run-analysis');
            if (data.success) {
                updateAnalysisResults(data.data);
                document.getElementById('analysis-results').style.display = 'block';
            } else {
                showToast('Error', 'Failed to run analysis: ' + data.error, 'error');
            }
        })
        .catch(error => {
            hideLoading('run-analysis');
            console.error('Error running analysis:', error);
            showToast('Error', 'Failed to run analysis', 'error');
        });
}

// Update analysis results
function updateAnalysisResults(analysis) {
    const rsi = analysis.rsi || 50;
    const macd = analysis.macd?.line || 0;
    const signal = analysis.macd?.signal || 0;
    
    const rsiValueElement = document.getElementById('rsi-value');
    const macdValueElement = document.getElementById('macd-value');
    const rsiStatusElement = document.getElementById('rsi-status');
    const macdStatusElement = document.getElementById('macd-status');
    const signalElement = document.getElementById('signal-value');

    if (rsiValueElement) rsiValueElement.textContent = rsi.toFixed(2);
    if (macdValueElement) macdValueElement.textContent = macd.toFixed(4);
    
    // Update RSI status
    if (rsiStatusElement) {
        if (rsi > 70) {
            rsiStatusElement.textContent = 'Overbought';
            rsiStatusElement.className = 'metric-label text-danger';
        } else if (rsi < 30) {
            rsiStatusElement.textContent = 'Oversold';
            rsiStatusElement.className = 'metric-label text-success';
        } else {
            rsiStatusElement.textContent = 'Neutral';
            rsiStatusElement.className = 'metric-label text-warning';
        }
    }
    
    // Update MACD status
    if (macdStatusElement) {
        if (macd > signal) {
            macdStatusElement.textContent = 'Bullish';
            macdStatusElement.className = 'metric-label text-success';
        } else {
            macdStatusElement.textContent = 'Bearish';
            macdStatusElement.className = 'metric-label text-danger';
        }
    }
    
    // Update signal
    if (signalElement) {
        let recommendation = 'HOLD';
        let signalClass = 'text-warning';
        
        if (rsi < 30 && macd > signal) {
            recommendation = 'BUY';
            signalClass = 'text-success';
        } else if (rsi > 70 && macd < signal) {
            recommendation = 'SELL';
            signalClass = 'text-danger';
        }
        
        signalElement.textContent = recommendation;
        signalElement.className = `metric-value ${signalClass}`;
    }
}

// Load active strategies
function loadActiveStrategies() {
    fetch('/api/strategy')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateActiveStrategiesDisplay(data.data);
            } else {
                console.error('Error loading strategies:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading strategies:', error);
        });
}

// Load current strategy
function loadCurrentStrategy() {
    fetch('/api/strategy')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const strategySelect = document.getElementById('default-strategy');
                const strategyStatus = document.getElementById('strategy-status');
                
                if (strategySelect) {
                    strategySelect.value = data.data.current_strategy;
                }
                
                if (strategyStatus) {
                    // Check if auto trading is enabled
                    const autoTradingStatusElement = document.getElementById('auto-trading-text');
                    const isAutoTradingEnabled = autoTradingStatusElement && autoTradingStatusElement.textContent === 'Enabled';
                    
                    strategyStatus.textContent = isAutoTradingEnabled ? 'Active' : 'Inactive';
                    strategyStatus.className = isAutoTradingEnabled ? 'badge bg-success me-2' : 'badge bg-warning me-2';
                }
            } else {
                console.error('Error loading current strategy:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading current strategy:', error);
        });
}

// Update active strategies display
function updateActiveStrategiesDisplay(strategyData) {
    const activeStrategiesContainer = document.getElementById('active-strategies');
    
    if (!activeStrategiesContainer) {
        console.error('Active strategies container not found');
        return;
    }
    
    if (!strategyData.current_strategy) {
        activeStrategiesContainer.innerHTML = '<p class="text-muted">No active strategies</p>';
        return;
    }
    
    const strategyName = strategyData.current_strategy;
    const strategyStatus = strategyData.status;
    const description = strategyData.descriptions ? strategyData.descriptions[strategyName] : '';
    
    // Check if auto trading is enabled by looking at the auto trading status
    const autoTradingStatusElement = document.getElementById('auto-trading-text');
    const isAutoTradingEnabled = autoTradingStatusElement && autoTradingStatusElement.textContent === 'Enabled';
    
    const statusBadge = isAutoTradingEnabled ? 
        '<span class="badge bg-success me-2">Active</span>' : 
        '<span class="badge bg-warning me-2">Inactive</span>';
    
    activeStrategiesContainer.innerHTML = `
        <div class="card mb-3">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${strategyName.replace(/_/g, ' ')}</h6>
                        <p class="text-muted small mb-2">${description || 'No description available'}</p>
                    </div>
                    ${statusBadge}
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-outline-primary" onclick="testStrategy('${strategyName}')">
                        <i class="fas fa-play me-1"></i>Test
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="editStrategy('${strategyName}')">
                        <i class="fas fa-edit me-1"></i>Edit
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Test strategy function
function testStrategy(strategyName) {
    const symbol = document.getElementById('chart-symbol').value || 'BTC_USDT';
    
    fetch('/api/strategy/test', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            strategy: strategyName,
            symbol: symbol
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Success', `Strategy test completed. Signal: ${data.data.signal?.action || 'No signal'}`, 'success');
        } else {
            showToast('Error', data.error || 'Strategy test failed', 'error');
        }
    })
    .catch(error => {
        console.error('Error testing strategy:', error);
        showToast('Error', 'Strategy test failed', 'error');
    });
}

// Update strategy function
function updateStrategy(strategyName) {
    fetch('/api/strategy', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ strategy: strategyName })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Success', `Strategy updated to ${strategyName}`, 'success');
            // Reload active strategies to reflect the change
            loadActiveStrategies();
        } else {
            showToast('Error', data.error || 'Failed to update strategy', 'error');
        }
    })
    .catch(error => {
        console.error('Error updating strategy:', error);
        showToast('Error', 'Failed to update strategy', 'error');
    });
}

// Edit strategy function
function editStrategy(strategyName) {
    // Open settings modal and set the strategy
    const strategySelect = document.getElementById('default-strategy');
    if (strategySelect) {
        strategySelect.value = strategyName;
    }
    
    // Show settings modal
    const settingsModal = new bootstrap.Modal(document.getElementById('settingsModal'));
    settingsModal.show();
}

// Update settings to include strategy management
function saveSettings() {
    const settings = {
        trading_pair: document.getElementById('setting-trading-pair').value,
        position_size: parseFloat(document.getElementById('setting-position-size').value),
        leverage: parseInt(document.getElementById('setting-leverage').value),
        trading_amount: parseFloat(document.getElementById('setting-trading-amount').value),
        max_daily_loss: parseFloat(document.getElementById('setting-max-daily-loss').value),
        stop_loss_percentage: parseFloat(document.getElementById('setting-stop-loss').value),
        take_profit_percentage: parseFloat(document.getElementById('setting-take-profit').value),
        trailing_stop_percentage: parseFloat(document.getElementById('setting-trailing-stop').value),
        default_strategy: document.getElementById('default-strategy').value,
        trading_hours: {
            enabled: document.getElementById('trading-hours-enabled').checked,
            start: document.getElementById('trading-start-time').value,
            end: document.getElementById('trading-end-time').value,
            timezone: document.getElementById('trading-timezone').value,
            exclude_weekends: document.getElementById('exclude-weekends').checked,
            exclude_holidays: document.getElementById('exclude-holidays').checked
        },
        rsi: {
            period: parseInt(document.getElementById('rsi-period').value),
            overbought: parseFloat(document.getElementById('rsi-overbought').value),
            oversold: parseFloat(document.getElementById('rsi-oversold').value)
        },
        notifications: {
            telegram: {
                enabled: document.getElementById('telegram-enabled').checked,
                bot_token: document.getElementById('telegram-token').value,
                user_id: document.getElementById('telegram-user-id').value
            },
            email: {
                enabled: document.getElementById('email-enabled').checked,
                recipient_email: document.getElementById('notification-email').value,
                sender_email: document.getElementById('sender-email').value,
                sender_password: document.getElementById('sender-password').value,
                smtp_server: document.getElementById('smtp-server').value
            }
        },
        types: {
            trade_notifications: document.getElementById('notify-trades').checked,
            error_notifications: document.getElementById('notify-errors').checked,
            balance_notifications: document.getElementById('notify-balance').checked,
            status_notifications: document.getElementById('notify-status').checked
        }
    };
    
    showLoading('save-settings');
    
    fetch('/api/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        hideLoading('save-settings');
        if (data.success) {
            showToast('Success', 'Settings saved successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('settingsModal')).hide();
            // Reload active strategies after saving settings
            loadActiveStrategies();
        } else {
            showToast('Error', 'Failed to save settings: ' + data.error, 'error');
        }
    })
    .catch(error => {
        hideLoading('save-settings');
        console.error('Error saving settings:', error);
        showToast('Error', 'Failed to save settings', 'error');
    });
}

// Load chart data
function loadChartData(symbol, timeframe = '5M') {
    const chartCanvas = document.getElementById('price-chart');
    if (!chartCanvas) {
        console.warn('Price chart canvas not found - chart tab may not be active');
        // Don't return, try to create the canvas if container exists
        const chartContainer = document.querySelector('#charts .card-body');
        if (chartContainer) {
            chartContainer.innerHTML = '<canvas id="price-chart" height="400"></canvas>';
            const newCanvas = document.getElementById('price-chart');
            if (newCanvas) {
                const ctx = newCanvas.getContext('2d');
                loadChartDataInternal(symbol, timeframe, ctx, chartContainer);
                return;
            }
        }
        console.error('Could not create price chart canvas');
        return;
    }
    
    const ctx = chartCanvas.getContext('2d');
    const chartContainer = chartCanvas.parentElement;
    loadChartDataInternal(symbol, timeframe, ctx, chartContainer);
}

// Internal function to load chart data
function loadChartDataInternal(symbol, timeframe, ctx, chartContainer) {
    if (charts.priceChart) {
        charts.priceChart.destroy();
    }
    
    // Show loading state
    if (chartContainer) {
        chartContainer.innerHTML = '<div class="chart-loading"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    }
    
    // Fetch real chart data from API with timeframe
    fetch(`/api/chart-data/${symbol}?timeframe=${timeframe}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                createChart(ctx, data.data, symbol, chartContainer);
            } else {
                // Fallback to sample data if API fails
                console.warn('Failed to load chart data:', data.error);
                createSampleChart(ctx, symbol, data.error, chartContainer);
            }
        })
        .catch(error => {
            console.error('Error loading chart data:', error);
            createSampleChart(ctx, symbol, 'Network error: ' + error.message, chartContainer);
        });
}

// Create chart with real data
function createChart(ctx, chartData, symbol, chartContainer) {
    if (!chartContainer) {
        console.error('Chart container not found for chart creation');
        return;
    }
    
    // Recreate the canvas element
    chartContainer.innerHTML = '<canvas id="price-chart" height="400"></canvas>';
    const newCanvas = document.getElementById('price-chart');
    if (!newCanvas) {
        console.error('Failed to create new canvas element');
        return;
    }
    const newCtx = newCanvas.getContext('2d');
    
    // Check if we have OHLC data for candlestick chart
    const hasOHLC = chartData.high && chartData.low && chartData.open && chartData.prices;
    
    runWhenConnected(newCanvas, () => {
    if (hasOHLC && chartData.high.length > 0) {
        createCandlestickChart(newCtx, chartData, symbol, chartContainer);
    } else {
        createLineChart(newCtx, chartData, symbol, chartContainer);
    }
    });
}

// Create candlestick chart
function createCandlestickChart(ctx, chartData, symbol, chartContainer) {
    const datasets = [
        {
            label: `${symbol} Price`,
            data: chartData.prices.map((price, index) => ({
                x: chartData.labels[index],
                y: price
            })),
            borderColor: '#3498db',
            backgroundColor: 'rgba(52, 152, 219, 0.1)',
            tension: 0.4,
            fill: false,
            pointRadius: 0
        }
    ];
    
    // Add volume as secondary dataset if available
    if (chartData.volumes && chartData.volumes.length > 0) {
        const maxVolume = Math.max(...chartData.volumes);
        datasets.push({
            label: 'Volume',
            data: chartData.volumes.map((volume, index) => ({
                x: chartData.labels[index],
                y: (volume / maxVolume) * Math.max(...chartData.prices) * 0.3
            })),
            borderColor: '#e74c3c',
            backgroundColor: 'rgba(231, 76, 60, 0.3)',
            tension: 0.4,
            fill: true,
            pointRadius: 0,
            yAxisID: 'y1'
        });
    }
    
    charts.priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#ffffff'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#3498db',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            const label = context.dataset.label || '';
                            const value = context.parsed.y;
                            if (label.includes('Volume')) {
                                const volumeIndex = context.dataIndex;
                                const actualVolume = chartData.volumes[volumeIndex];
                                return `${label}: ${actualVolume.toLocaleString()}`;
                            }
                            return `${label}: $${value.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: '#ffffff',
                        maxTicksLimit: 10
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: {
                        color: '#ffffff',
                        callback: function(value) {
                            return '$' + value.toFixed(2);
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: false,
                    position: 'right',
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

// Create line chart (fallback)
function createLineChart(ctx, chartData, symbol, chartContainer) {
    if (!chartContainer) {
        console.error('Chart container not found for chart creation');
        return;
    }
    
    charts.priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: `${symbol} Price`,
                data: chartData.prices,
                borderColor: '#3498db',
                backgroundColor: 'rgba(52, 152, 219, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 2,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#ffffff'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#3498db',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: '#ffffff',
                        maxTicksLimit: 10
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    ticks: {
                        color: '#ffffff',
                        callback: function(value) {
                            return '$' + value.toFixed(2);
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            }
        }
    });
}

// Create sample chart as fallback
function createSampleChart(ctx, symbol, errorMessage, chartContainer) {
    if (!chartContainer) {
        console.error('Chart container not found for sample chart creation');
        return;
    }
    
    // Recreate the canvas element
    chartContainer.innerHTML = '<canvas id="price-chart" height="400"></canvas>';
    const newCanvas = document.getElementById('price-chart');
    if (!newCanvas) {
        console.error('Failed to create new canvas element for sample chart');
        return;
    }
    const newCtx = newCanvas.getContext('2d');
    
    // Create sample data
    const labels = [];
    const prices = [];
    const now = new Date();
    
    for (let i = 24; i >= 0; i--) {
        const time = new Date(now.getTime() - i * 60 * 60 * 1000);
        labels.push(time.toLocaleTimeString());
        prices.push(Math.random() * 1000 + 50000); // Sample price
    }
    
    const chartTitle = `${symbol} Price (Sample Data)`;
    
    runWhenConnected(newCanvas, () => {
    charts.priceChart = new Chart(newCtx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: chartTitle,
                data: prices,
                borderColor: '#e74c3c',
                backgroundColor: 'rgba(231, 76, 60, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 2,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#ffffff'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#e74c3c',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: '#ffffff',
                        maxTicksLimit: 10
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    ticks: {
                        color: '#ffffff',
                        callback: function(value) {
                            return '$' + value.toFixed(2);
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            }
        }
        });
    });
}

// Close position
function closePosition(symbol) {
    if (confirm(`Are you sure you want to close the position for ${symbol}?`)) {
        // This would be implemented to close the position
        showToast('Info', 'Position close functionality not implemented yet', 'info');
    }
}

// Update price display
function updatePriceDisplay(data) {
    // This would update real-time price displays
    console.log('Price update:', data);
}

// Update modal balance display
function updateModalBalance() {
    try {
        // Get balance elements with null checks
        const totalBalanceElement = document.getElementById('total-balance');
        const availableBalanceElement = document.getElementById('available-balance');
        const frozenBalanceElement = document.getElementById('frozen-balance');
        
        // Get modal balance elements
        const modalTotalBalanceElement = document.getElementById('modal-total-balance');
        const modalAvailableBalanceElement = document.getElementById('modal-available-balance');
        const modalFrozenBalanceElement = document.getElementById('modal-frozen-balance');
        
        // Check if all required elements exist
        if (!totalBalanceElement || !availableBalanceElement || !frozenBalanceElement) {
            console.warn('Balance elements not found, skipping modal balance update');
            return;
        }
        
        if (!modalTotalBalanceElement || !modalAvailableBalanceElement || !modalFrozenBalanceElement) {
            console.warn('Modal balance elements not found, skipping modal balance update');
            return;
        }
        
        // Parse balance values with error handling
        let totalBalance = 0;
        let availableBalance = 0;
        let frozenBalance = 0;
        
        try {
            totalBalance = parseFloat(totalBalanceElement.textContent.replace(/[^0-9.-]+/g, '')) || 0;
            availableBalance = parseFloat(availableBalanceElement.textContent.replace(/[^0-9.-]+/g, '')) || 0;
            frozenBalance = parseFloat(frozenBalanceElement.textContent.replace(/[^0-9.-]+/g, '')) || 0;
        } catch (e) {
            console.error('Error parsing balance values:', e);
            totalBalance = availableBalance = frozenBalance = 0;
        }
        
        // Update modal balance display
        modalTotalBalanceElement.textContent = formatCurrency(totalBalance);
        modalAvailableBalanceElement.textContent = formatCurrency(availableBalance);
        if (modalFrozenBalanceElement) {
            modalFrozenBalanceElement.textContent = formatCurrency(frozenBalance);
        }
        
    } catch (error) {
        console.error('Error updating modal balance:', error);
    }
}

// Show loading state
function showLoading(buttonId) {
    const button = document.getElementById(buttonId);
    const loading = button ? button.querySelector('.loading') : null;
    
    if (!loading) {
        console.warn(`Loading element not found for button: ${buttonId}`);
        return;
    }
    
    if (button) button.disabled = true;
    loading.style.display = 'inline-block';
    
    // Hide all other content in the button
    if (button) {
        const otherElements = button.querySelectorAll(':not(.loading)');
        otherElements.forEach(el => el.style.display = 'none');
    }
}

// Hide loading state
function hideLoading(buttonId) {
    const button = document.getElementById(buttonId);
    const loading = button ? button.querySelector('.loading') : null;
    
    if (!loading) {
        console.warn(`Loading element not found for button: ${buttonId}`);
        return;
    }
    
    if (button) button.disabled = false;
    loading.style.display = 'none';
    
    // Show all other content in the button
    if (button) {
        const otherElements = button.querySelectorAll(':not(.loading)');
        otherElements.forEach(el => el.style.display = 'inline');
    }
}

// Show toast notification
function showToast(title, message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastTitle = document.getElementById('toast-title');
    const toastMessage = document.getElementById('toast-message');
    
    if (toastTitle) toastTitle.textContent = title;
    if (toastMessage) toastMessage.textContent = message;
    
    // Set toast color based on type
    if (toast) toast.className = `toast ${type === 'error' ? 'bg-danger' : type === 'success' ? 'bg-success' : 'bg-info'}`;
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

// Format percentage
function formatPercentage(value) {
    return `${value.toFixed(2)}%`;
}

// Validate trade before execution
function validateTrade(symbol, side, quantity, orderType, price) {
    return new Promise((resolve, reject) => {
        const tradeData = {
            symbol: symbol,
            side: side,
            quantity: quantity,
            order_type: orderType
        };
        
        if (price) {
            tradeData.price = price;
        }
        
        fetch('/api/trade/validate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(tradeData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.valid) {
                resolve(data);
            } else {
                reject(new Error(data.error));
            }
        })
        .catch(error => {
            reject(error);
        });
    });
}

// Check if user has sufficient balance for trading
function checkBalanceForTrade(side, quantity, estimatedPrice = 50000) {
    const availableBalance = parseFloat(document.getElementById('available-balance').textContent.replace(/[^0-9.-]+/g, ''));
    
    if (side === 'BUY') {
        const estimatedCost = quantity * estimatedPrice;
        
        if (availableBalance <= 0) {
            return {
                canTrade: false,
                message: 'Insufficient balance. Please add funds to your account.',
                type: 'error'
            };
        }
        
        if (estimatedCost > availableBalance) {
            return {
                canTrade: false,
                message: `Insufficient balance. Estimated cost: $${estimatedCost.toFixed(2)}, Available: $${availableBalance.toFixed(2)}`,
                type: 'error'
            };
        }
        
        if (estimatedCost > availableBalance * 0.8) {
            return {
                canTrade: true,
                message: `Warning: This trade will use ${((estimatedCost/availableBalance)*100).toFixed(1)}% of your available balance.`,
                type: 'warning'
            };
        }
        
        return {
            canTrade: true,
            message: 'Sufficient balance available.',
            type: 'success'
        };
    }
    
    return {
        canTrade: true,
        message: 'Sell order - checking asset balance...',
        type: 'info'
    };
}

// Toggle trading hours config visibility
function toggleTradingHoursConfig() {
    const tradingHoursConfig = document.getElementById('trading-hours-config');
    const toggleIcon = document.getElementById('trading-hours-toggle-icon');
    
    if (tradingHoursConfig && toggleIcon) {
        if (tradingHoursConfig.style.display === 'none') {
            tradingHoursConfig.style.display = 'block';
            toggleIcon.classList.remove('fa-chevron-down');
            toggleIcon.classList.add('fa-chevron-up');
        } else {
            tradingHoursConfig.style.display = 'none';
            toggleIcon.classList.remove('fa-chevron-up');
            toggleIcon.classList.add('fa-chevron-down');
        }
    }
}

// Update strategy description
function updateStrategyDescription(strategyName) {
    const strategyDescriptionElement = document.getElementById('strategy-description');
    if (strategyDescriptionElement) {
        const strategyDescriptions = {
            'ADVANCED_STRATEGY': 'A sophisticated strategy that combines technical indicators and market sentiment to make informed decisions.',
            'SIMPLE_BUY_HOLD': 'A simple buy and hold strategy for long-term investments.',
            'SIMPLE_SELL_HOLD': 'A simple sell and hold strategy for short-term trades.',
            'RSI_STRATEGY': 'A strategy based on Relative Strength Index (RSI) to identify overbought and oversold conditions.',
            'MACD_STRATEGY': 'A strategy based on Moving Average Convergence Divergence (MACD) to identify bullish and bearish trends.',
            'TRAILING_STOP_STRATEGY': 'A strategy that uses a trailing stop to manage risk and protect profits.',
            'STOP_LOSS_STRATEGY': 'A strategy that uses a stop loss to limit losses on open positions.',
            'TAKE_PROFIT_STRATEGY': 'A strategy that uses a take profit to lock in profits on open positions.',
            'VOLUME_STRATEGY': 'A strategy that uses volume to identify potential trading opportunities.',
            'PRICE_ACTION_STRATEGY': 'A strategy that reacts to price action and market movements.',
            'HEDGE_STRATEGY': 'A strategy that uses short positions to hedge against long positions.',
            'SPREAD_STRATEGY': 'A strategy that focuses on the spread between buy and sell prices.',
            'CROSSOVER_STRATEGY': 'A strategy that uses moving averages to identify crossover points.',
            'DIVERGENCE_STRATEGY': 'A strategy that uses price divergence to identify potential trading opportunities.',
            'VOLATILITY_STRATEGY': 'A strategy that uses volatility to identify potential trading opportunities.',
            'NEWS_DRIVEN_STRATEGY': 'A strategy that reacts to news and market sentiment.',
            'FUNDAMENTAL_STRATEGY': 'A strategy that focuses on fundamental analysis and economic indicators.',
            'TECHNICAL_STRATEGY': 'A strategy that focuses on technical analysis and chart patterns.',
            'GAMING_STRATEGY': 'A strategy that focuses on short-term, high-risk, high-reward trades.',
            'RISK_MANAGEMENT_STRATEGY': 'A strategy that focuses on risk management and capital preservation.',
            'EMOTIONAL_STRATEGY': 'A strategy that focuses on emotional trading and psychological factors.',
            'SYSTEMATIC_STRATEGY': 'A strategy that uses pre-defined rules and algorithms to make decisions.',
            'ADAPTIVE_STRATEGY': 'A strategy that adapts to market conditions and continuously optimizes itself.',
            'CUSTOM_STRATEGY': 'A custom strategy created by the user.',
            'DEFAULT': 'No specific strategy description available.'
        };
        strategyDescriptionElement.textContent = strategyDescriptions[strategyName] || strategyDescriptions['DEFAULT'];
    }
}

// Test email notification
function testEmailNotification() {
    const emailEnabled = document.getElementById('email-enabled').checked;
    const notificationEmail = document.getElementById('notification-email').value;
    const smtpServer = document.getElementById('smtp-server').value;
    const senderEmail = document.getElementById('sender-email').value;
    const senderPassword = document.getElementById('sender-password').value;

    if (!emailEnabled) {
        showToast('Error', 'Email notifications are not enabled. Please enable them in settings.', 'error');
        return;
    }

    if (!notificationEmail) {
        showToast('Error', 'Please enter recipient email address.', 'error');
        return;
    }

    if (!senderEmail) {
        showToast('Error', 'Please enter sender email address.', 'error');
        return;
    }

    if (!senderPassword) {
        showToast('Error', 'Please enter sender password (App Password for Gmail).', 'error');
        return;
    }

    if (!smtpServer) {
        showToast('Error', 'SMTP server is not configured. Please configure it in settings.', 'error');
        return;
    }

    showLoading('test-email-btn');

    const emailConfig = {
        smtp_server: smtpServer,
        smtp_port: 587,
        sender_email: senderEmail,
        sender_password: senderPassword,
        recipient_email: notificationEmail
    };

    console.log('Sending email config:', emailConfig);

    fetch('/api/test-email', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            email_config: emailConfig
        })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading('test-email-btn');
        console.log('Email test response:', data);
        if (data.success) {
            showToast('Success', 'Email test sent successfully! Check your inbox.', 'success');
        } else {
            showToast('Error', 'Failed to send email test: ' + data.error, 'error');
        }
    })
    .catch(error => {
        hideLoading('test-email-btn');
        console.error('Error testing email:', error);
        showToast('Error', 'Failed to send email test: ' + error.message, 'error');
    });
}

// Test market data loading
function testMarketData(symbol = 'BTC_USDT') {
    console.log(`Testing market data for ${symbol}...`);
    
    // Test API endpoint directly
    fetch(`/api/market-data/${symbol}`)
        .then(response => response.json())
        .then(data => {
            console.log('Market data test response:', data);
            if (data.success) {
                console.log('Market data:', data.data);
                updateMarketDataDisplay(symbol, data.data);
            } else {
                console.error('Market data test failed:', data.error);
            }
        })
        .catch(error => {
            console.error('Market data test error:', error);
        });
}

// Make test function available globally
window.testMarketData = testMarketData;

// Test chart loading
function testChartLoading(symbol = 'BTC_USDT') {
    console.log(`Testing chart loading for ${symbol}...`);
    
    // Check if charts tab is active
    const chartsTab = document.getElementById('charts-tab');
    const chartsPane = document.getElementById('charts');
    
    if (chartsTab && chartsPane) {
        // Make sure charts tab is active
        if (!chartsPane.classList.contains('active')) {
            console.log('Charts tab not active, activating...');
            // Simulate tab click
            chartsTab.click();
        }
        
        // Wait a bit then load chart
        setTimeout(() => {
            loadChartData(symbol);
        }, 200);
    } else {
        console.error('Charts tab elements not found');
    }
}

// Make test function available globally
window.testChartLoading = testChartLoading;

// Create market data container if it doesn't exist
function createMarketDataContainer(symbol) {
    const containerId = `market-data-${symbol}`;
    const existingContainer = document.getElementById(containerId);
    
    if (existingContainer) {
        console.log(`Container ${containerId} already exists`);
        return existingContainer;
    }
    
    // Find the top-crypto-market-data container
    const topCryptoContainer = document.getElementById('top-crypto-market-data');
    if (!topCryptoContainer) {
        console.error('top-crypto-market-data container not found');
        return null;
    }
    
    // Create the container dynamically
    const cryptoName = symbol.replace('_USDT', '');
    const colorClass = getCryptoColorClass(symbol);
    const headerClass = getCryptoHeaderClass(symbol);
    const headerText = getCryptoDisplayName(symbol);
    
    const containerHtml = `
        <div class="col-md-6 col-lg-4 mb-3">
            <div class="card ${colorClass}">
                <div class="card-header ${headerClass}">
                    <h6 class="mb-0">${headerText}</h6>
                </div>
                <div class="card-body">
                    <div id="${containerId}">
                        <div class="text-center">
                            <div class="spinner-border spinner-border-sm" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p class="mt-2">Loading market data...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Insert the new container
    topCryptoContainer.insertAdjacentHTML('beforeend', containerHtml);
    
    console.log(`Created container for ${symbol}`);
    return document.getElementById(containerId);
}

// Get crypto color class
function getCryptoColorClass(symbol) {
    const colorMap = {
        'BTC_USDT': 'border-primary',
        'ETH_USDT': 'border-success',
        'DOT_USDT': 'border-warning',
        'ADA_USDT': 'border-info',
        'SOL_USDT': 'border-danger'
    };
    return colorMap[symbol] || 'border-secondary';
}

// Get crypto header class
function getCryptoHeaderClass(symbol) {
    const headerMap = {
        'BTC_USDT': 'bg-primary text-white',
        'ETH_USDT': 'bg-success text-white',
        'DOT_USDT': 'bg-warning text-dark',
        'ADA_USDT': 'bg-info text-white',
        'SOL_USDT': 'bg-danger text-white'
    };
    return headerMap[symbol] || 'bg-secondary text-white';
}

// Get crypto display name
function getCryptoDisplayName(symbol) {
    const nameMap = {
        'BTC_USDT': 'Bitcoin (BTC)',
        'ETH_USDT': 'Ethereum (ETH)',
        'DOT_USDT': 'Polkadot (DOT)',
        'ADA_USDT': 'Cardano (ADA)',
        'SOL_USDT': 'Solana (SOL)'
    };
    return nameMap[symbol] || symbol;
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    if (socket) {
        socket.disconnect();
    }
});

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Add to body
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

function renderLivePairs() {
    const container = document.getElementById('live-pairs-list');
    if (!container) return;
    const pairs = Array.from(livePairs);
    if (pairs.length === 0) {
        container.innerHTML = '<span class="text-muted">No live pairs</span>';
        return;
    }
    container.innerHTML = pairs.map(p => `
        <span class="badge bg-secondary d-flex align-items-center">
            <i class="fas fa-circle me-1" style="font-size:8px"></i>${p}
            <button class="btn btn-sm btn-link text-light ms-2 p-0" onclick="removeLivePair('${p}')" title="Remove">
                <i class="fas fa-times"></i>
            </button>
        </span>
    `).join(' ');
}

function addLivePair(pair) {
    if (!pair) return;
    livePairs.add(pair.toUpperCase());
    renderLivePairs();
}

function removeLivePair(pair) {
    livePairs.delete(pair.toUpperCase());
    renderLivePairs();
}

window.removeLivePair = removeLivePair;

function runWhenConnected(node, fn, attempts = 20) {
    if (node && node.isConnected) {
        fn();
    } else if (attempts > 0) {
        setTimeout(() => runWhenConnected(node, fn, attempts - 1), 50);
    } else {
        // Fallback: run anyway to avoid stalling
        fn();
    }
} 