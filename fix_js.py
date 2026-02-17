"""Fix truncated JavaScript lines in index.html"""

# Map of truncated line endings -> their completions
# Each key is the truncated portion, value is the full correct text
JS_FIXES = {
    # Ticker template literal
    """stock.price.toLocaleString('en-IN', {minimumF""":
    """stock.price.toLocaleString('en-IN', {minimumFractionDigits: 2})}""",

    """${changeSign}${stock.change""":
    """${changeSign}${stock.change.toFixed(2)}</span>""",

    # Watchlist render template
    """onclick="openAddPositionModalForSymbo""":
    """onclick="openAddPositionModalForSymbol('${symbol}')">""",

    """onclick="openAddPositio""":
    """onclick="openAddPositionModalForSymbol('${symbol}', 'BUY')">BUY""",

    """onclick="openAddPositio\n""":
    """onclick="openAddPositionModalForSymbol('${symbol}', 'SELL')">SELL""",

    """onclick="openChart('${\n""":
    """onclick="openChart('${symbol}')">CHART""",

    """onclick="openDepth('\n""":
    """onclick="openDepth('${symbol}')">DEPTH""",

    """onclick="removeFromWatchlist('${s""":
    """onclick="removeFromWatchlist('${symbol}')">""",

    # Position toggle controls
    """control = document.getElementById('posit""":
    """control = document.getElementById('positionOrderType');""",

    """control = document.getElementById('positio""":
    """control = document.getElementById('positionPart');""",

    # Partition functions
    """parseFloat(document.getElementById('partitio""":
    """parseFloat(document.getElementById('partitionSquareOffPrice').value) || 0;""",

    # Empty positions message
    """style="text-align:center;padding:30px;color:#888;font-""":
    """style="text-align:center;padding:30px;color:#888;font-size:16px;">""",

    # Order type class
    """'order-type-buy' : 'order-type-se""":
    """'order-type-buy' : 'order-type-sell';""",

    # Condition class - fix truncation
    """p.orderCondition.toLowerCase().replace(/\\s""":
    """p.orderCondition.toLowerCase().replace(/\\s+/g, '-')}\`;""",

    # Toggle checks
    """document.getElementById('toggleOrderType').check""":
    """document.getElementById('toggleOrderType').checked && positionSettingsEnabled;""",

    """document.getElementById('toggleExit').checked && positio""":
    """document.getElementById('toggleExit').checked && positionSettingsEnabled;""",

    """document.getElementById('toggleProfitLock').check""":
    """document.getElementById('toggleProfitLock').checked && profitLockEnabled;""",

    """document.getElementById('toggleProfitGap').checke""":
    """document.getElementById('toggleProfitGap').checked && positionSettingsEnabled;""",

    """parseInt(document.getElementById('posit""":
    """parseInt(document.getElementById('positionQty').value) || 0;""",

    """document.getElementById('trailingS""":
    """document.getElementById('trailingSLType').value : 'point';""",

    """document.getElementById('indicatorCondition').valu""":
    """document.getElementById('indicatorCondition').value;""",

    # Modify position
    """parseFloat(document.getElementById('modifyTrailingSL').valu""":
    """parseFloat(document.getElementById('modifyTrailingSL').value);""",

    # Partition confirm
    """partitionPrice.toFixed""":
    """partitionPrice.toFixed(2)}?`;""",

    # View details - truncated template lines
    """${posSettings.orderType.toUpperCase()} ${posSettings.orderTy""":
    """${posSettings.orderType.toUpperCase()} ${posSettings.orderTypeEnabled !== false ? '✅' : '❌'}<br>""",

    """${posSettings.partitionSquareO""":
    """${posSettings.partitionSquareOffPrice || '0.00'}<br>""",

    # Modify position settings
    """posSettings.orderTy""":
    """posSettings.orderType;""",

    """posSettings.trailingS""":
    """posSettings.trailingSL?.type || 'point';""",

    """posSettings.profitLo""":
    """posSettings.profitLockEnabled !== false;""",

    """posSettings.profitGa""":
    """posSettings.profitGapEnabled !== false;""",

    """new Event('chan""":
    """new Event('change'));""",

    """posSettings.par""":
    """posSettings.partitionSquareOffQty || 0;""",

    """posSettings.maxPar""":
    """posSettings.maxPartitionCount || 5;""",

    """posSettings.auto""":
    """posSettings.autoSquareOffPercent || 10;""",

    """posSettings.reentryAtt""":
    """posSettings.reentryAttempts || 3;""",

    """posSettings.trailing""":
    """posSettings.trailingSL?.indicator?.period || '14';""",

    # Add quantity cost calculation
    """(position.sellAvgPrice * (position.sellQty - addQty)) + (add""":
    """(position.sellAvgPrice * (position.sellQty - addQty)) + (addQty * addPrice);""",

    # Broker list template
    """"background:#2a2a2a; padding:12px; margin-bottom:8px; border""":
    """"background:#2a2a2a; padding:12px; margin-bottom:8px; border-radius:5px; display:flex; justify-content:space-between; align-items:center;">""",
}

def fix_js_in_html(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Apply all fixes
    for truncated, fixed in JS_FIXES.items():
        if truncated in content:
            content = content.replace(truncated, fixed)

    # Additional specific line fixes that need more context

    # Fix: No stocks message in renderWatchlist
    content = content.replace(
        """'<div class="no-watchlist-stocks">No stocks in watc""",
        """'<div class="no-watchlist-stocks">No stocks in watchlist. Search and add stocks above.</div>'"""
    )

    # Fix: ticker price format
    content = content.replace(
        """{minimumFractionDigits: 2})}""" + '\n' + """                            <span""",
        """{minimumFractionDigits: 2})}</span>
                            <span"""
    )

    # Fix renderWatchlist template truncations
    content = content.replace(
        """style="display:flex; justify-content:space-between; align-items:center;\n""",
        """style="display:flex; justify-content:space-between; align-items:center;">\n"""
    )

    # Fix: watchlist buy/sell/chart/depth buttons
    content = content.replace(
        """class="watchlist-btn watchlist-buy-btn" onclick="openAddPositionModalForSymbol('${symbol}', 'BUY')">BUY""",
        """class="watchlist-btn watchlist-buy-btn" onclick="openAddPositionModalForSymbol('${symbol}', 'BUY')">BUY</button>"""
    )
    content = content.replace(
        """class="watchlist-btn watchlist-sell-btn" onclick="openAddPositionModalForSymbol('${symbol}', 'SELL')">SELL""",
        """class="watchlist-btn watchlist-sell-btn" onclick="openAddPositionModalForSymbol('${symbol}', 'SELL')">SELL</button>"""
    )
    content = content.replace(
        """class="watchlist-btn watchlist-chart-btn" onclick="openChart('${symbol}')">CHART""",
        """class="watchlist-btn watchlist-chart-btn" onclick="openChart('${symbol}')">CHART</button>"""
    )
    content = content.replace(
        """class="watchlist-btn watchlist-depth-btn" onclick="openDepth('${symbol}')">DEPTH""",
        """class="watchlist-btn watchlist-depth-btn" onclick="openDepth('${symbol}')">DEPTH</button>"""
    )

    # Fix: stockInfo fallback
    content = content.replace(
        """const stockInfo = stockDatabase.find(stock => stock.symbol === symbol) || {""",
        """const stockInfo = stockDatabase.find(stock => stock.symbol === symbol) || { symbol: symbol, name: symbol, sector: 'N/A' };"""
    )

    # Fix: addPosition symbol trim
    content = content.replace(
        """document.getElementById('positionSymbol').value.trim().toUpp""",
        """document.getElementById('positionSymbol').value.trim().toUpperCase();"""
    )

    # Fix: currentPrice parse
    content = content.replace(
        """parseFloat(document.getElementById('currentPrice').value""",
        """parseFloat(document.getElementById('currentPrice').value);"""
    )
    content = content.replace(
        """parseFloat(document.getElementById('buyAvgPrice').value""",
        """parseFloat(document.getElementById('buyAvgPrice').value) || 0;"""
    )
    content = content.replace(
        """parseFloat(document.getElementById('sellAvgPrice').value)""",
        """parseFloat(document.getElementById('sellAvgPrice').value) || 0;"""
    )

    # Fix: P/L calc position multiplier
    content = content.replace(
        """(position.currentPrice - position.entryPrice) * (position.buyQty - po""",
        """(position.currentPrice - position.entryPrice) * (position.buyQty - position.sellQty);"""
    )

    # Fix: position settings field truncations
    content = content.replace(
        """document.getElementById('positionQty').value) || 0;""" + '\n' + """                    const positionSellQty = qtyEnabled ? parseInt(document.getElementById('posit""",
        """document.getElementById('positionQty').value) || 0;
                    const positionSellQty = qtyEnabled ? parseInt(document.getElementById('positionSellQty').value) || 0 : 0;"""
    )

    # Fix: trailing SL getElementById
    content = content.replace(
        """document.getElementById('trailingSLType').value : 'point';""" + '\n' + """                    const trailingSLValue = trailingSLChecked ? parseFloat(document.getElementBy""",
        """document.getElementById('trailingSLType').value : 'point';
                    const trailingSLValue = trailingSLChecked ? parseFloat(document.getElementById('trailingSLValue').value) || 0 : 0;"""
    )

    # Fix: target type/value
    content = content.replace(
        """document.getElementById('targetType').val""",
        """document.getElementById('targetType').value : 'point';"""
    )
    content = content.replace(
        """parseFloat(document.getElementById('targ""",
        """parseFloat(document.getElementById('targetValue').value) || 0 : 0;"""
    )

    # Fix: exit type/value
    content = content.replace(
        """document.getElementById('exitType').value : 'po""",
        """document.getElementById('exitType').value : 'point';"""
    )
    content = content.replace(
        """parseFloat(document.getElementById('exitValu""",
        """parseFloat(document.getElementById('exitValue').value) || 0 : 0;"""
    )

    # Fix: profitLock/profitGap
    content = content.replace(
        """parseFloat(document.getElementById('pr""" + '\n' + """                    const profitGap""",
        """parseFloat(document.getElementById('profitLock').value) || 0 : 0;
                    const profitGap"""
    )
    content = content.replace(
        """parseFloat(document.getElementById('profitGap').value) || 0 : 0;""" + '\n',
        """parseFloat(document.getElementById('profitGap').value) || 0 : 0;\n"""
    )

    # Fix: partition settings reads
    content = content.replace(
        """parseInt(document.getElementById('partitionSquareOffQty').value) || 0 : 0;\n                    const partitionSquareOffPrice = partitionSettingsEnabled ? parseFloat(docume""",
        """parseInt(document.getElementById('partitionSquareOffQty').value) || 0 : 0;
                    const partitionSquareOffPrice = partitionSettingsEnabled ? parseFloat(document.getElementById('partitionSquareOffPrice').value) || 0 : 0;"""
    )

    content = content.replace(
        """parseInt(document.getElementById('addQty').value) || 0 : 0;\n                    const addQtyPrice = partitionSettingsEnabled ? parseFloat(document.getEleme""",
        """parseInt(document.getElementById('addQty').value) || 0 : 0;
                    const addQtyPrice = partitionSettingsEnabled ? parseFloat(document.getElementById('addQtyPrice').value) || 0 : 0;"""
    )

    content = content.replace(
        """parseInt(document.getElementById('maxPartitionCount').value) || 0 : 5;\n                    const autoSquareOffPercent = partitionSettingsEnabled ? parseFloat(documen""",
        """parseInt(document.getElementById('maxPartitionCount').value) || 0 : 5;
                    const autoSquareOffPercent = partitionSettingsEnabled ? parseFloat(document.getElementById('autoSquareOffPercent').value) || 0 : 10;"""
    )

    content = content.replace(
        """parseInt(document.getElementById('reentryAttempts').value) || 0 : 3;\n""",
        """parseInt(document.getElementById('reentryAttempts').value) || 0 : 3;\n"""
    )

    # Fix: action modal title
    content = content.replace(
        """`Position A""",
        """`Position Actions - ${symbol}`;"""
    )

    # Fix: partition action confirms
    content = content.replace(
        """const partitionPrice = posSettings.partitionSquareOffPrice || position.currentP""",
        """const partitionPrice = posSettings.partitionSquareOffPrice || position.currentPrice;"""
    )

    content = content.replace(
        """`Square off ${partitionQty} units of ${position.symbol} at ₹""",
        """`Square off ${partitionQty} units of ${position.symbol} at ₹${partitionPrice.toFixed(2)}?`;"""
    )

    content = content.replace(
        """`Partition square off executed!\\n${partitionQty} units of ${position.sym""",
        """`Partition square off executed!\\n${partitionQty} units of ${position.symbol}`;"""
    )

    content = content.replace(
        """`Add ${addQty} units to ${position.symbol} position at ₹${""",
        """`Add ${addQty} units to ${position.symbol} position at ₹${addPrice.toFixed(2)}?`;"""
    )

    content = content.replace(
        """`Added ${addQty} units to ${position.symbol} position at ₹${addPrice.t""",
        """`Added ${addQty} units to ${position.symbol} position at ₹${addPrice.toFixed(2)}`;"""
    )

    # Fix: buy qty recalculation
    content = content.replace(
        """(position.buyAvgPrice * (position.buyQty - addQty)) + (a""",
        """(position.buyAvgPrice * (position.buyQty - addQty)) + (addQty * addPrice);"""
    )
    content = content.replace(
        """(position.buyAvgPrice * (position.buyQty - addQty)) + (ad""",
        """(position.buyAvgPrice * (position.buyQty - addQty)) + (addQty * addPrice);"""
    )

    # Fix: broker list truncations
    content = content.replace(
        """'<div style="text-align:center; color:#888; padding:20""",
        """'<div style="text-align:center; color:#888; padding:20px;">No brokers saved yet.</div>';"""
    )

    content = content.replace(
        """Client ID: ${broker.clientId}</div""",
        """Client ID: ${broker.clientId}</div>"""
    )

    content = content.replace(
        """color:#${broker.status === 'connected' ? '00ff""",
        """color:#${broker.status === 'connected' ? '00ff88' : 'ff4444'};">Status: ${broker.status}</div>"""
    )

    content = content.replace(
        """style="padding:5px 10px; backgr""",
        """style="padding:5px 10px; background:#0077ff; border:none; color:#fff; border-radius:3px; cursor:pointer;">"""
    )

    content = content.replace(
        """style="padding:5px 1""",
        """style="padding:5px 10px; background:#00aa66; border:none; color:#fff; border-radius:3px; cursor:pointer;">"""
    )

    # Fix: broker edit
    content = content.replace(
        """broker.name.replace(' ', '').""",
        """broker.name.replace(' ', '').toUpperCase();"""
    )

    content = content.replace(
        """'Update and click \"Add/Update Broker\" to save c""",
        """'Update and click \"Add/Update Broker\" to save changes.');"""
    )

    # Fix: other truncated function calls
    content = content.replace(
        """const optionElement = document.querySelector(`[onclick="toggleEnableOpti""",
        """const optionElement = document.querySelector(`[onclick="toggleEnableOption('${option}')"]`);"""
    )

    content = content.replace(
        """document.getElementById('positionSectionBody').classList.remove('collapsed')""" + '\n' + """                    document.getElementById('positionSectionToggle').innerHTML = '<i class="fas f""",
        """document.getElementById('positionSectionBody').classList.remove('collapsed');
                    document.getElementById('positionSectionToggle').innerHTML = '<i class="fas fa-chevron-up"></i> Collapse';"""
    )

    content = content.replace(
        """document.getElementById('partitionSectionBody').classList.remove('collapsed')""" + '\n' + """                    document.getElementById('partitionSectionToggle').innerHTML = '<i class="fas""",
        """document.getElementById('partitionSectionBody').classList.remove('collapsed');
                    document.getElementById('partitionSectionToggle').innerHTML = '<i class="fas fa-chevron-up"></i> Collapse';"""
    )

    # Fix: modal symbol title
    content = content.replace(
        """`Add Position - ${""",
        """`Add Position - ${symbol}`;"""
    )

    content = content.replace(
        """`Modify Position""",
        """`Modify Position - ${position.symbol}`;"""
    )

    # Fix: indicator toggle check
    content = content.replace(
        """if (isChecked && document.getElementById('trailingSLType').value === 'i""",
        """if (isChecked && document.getElementById('trailingSLType').value === 'indicator') {"""
    )

    # Fix: trailing SL type change listener
    content = content.replace(
        """document.getElementById('trailingSLType').addEventListener('change', function""",
        """document.getElementById('trailingSLType').addEventListener('change', function() {"""
    )

    # Fix: addToWatchlist event listener
    content = content.replace(
        """document.getElementById('watchlistSearchBtn').addEventListener('click', addTo""",
        """document.getElementById('watchlistSearchBtn').addEventListener('click', addToWatchlist);"""
    )

    content = content.replace(
        """document.getElementById('watchlistSearch').addEventListener('keydown', func""",
        """document.getElementById('watchlistSearch').addEventListener('keydown', function(e) {"""
    )

    content = content.replace(
        """document.getElementById('clearWatchlistBtn').addEventListener('click', clearW""",
        """document.getElementById('clearWatchlistBtn').addEventListener('click', clearWatchlist);"""
    )

    # Fix: addMultipleStocks prompt
    content = content.replace(
        """const symbols = prompt(\"Enter multiple stock symbols separated by commas (""",
        """const symbols = prompt(\"Enter multiple stock symbols separated by commas (e.g., RELIANCE, TCS, INFY):\");"""
    )

    content = content.replace(
        """symbols.split(',').map(s => s.trim().toUpperCase()).filter(s =""",
        """symbols.split(',').map(s => s.trim().toUpperCase()).filter(s => s.length > 0);"""
    )

    # Fix: positionOrderType fields
    content = content.replace(
        """document.getElementById('po""" + '\n',
        """document.getElementById('positionOrderType').value : 'limit';\n"""
    )

    # Fix: confirmMsg in resetAllData
    content = content.replace(
        """if (confirm('This will reset ALL positions, watchlist and brokers. Are you sure?'))""",
        """if (confirm('This will reset ALL positions, watchlist and brokers. Are you sure?')) {"""
    )

    # Fix: partition square off entry calc
    content = content.replace(
        """parseFloat(document.getElementById('partition""" + '\n' + """                   const partitionSquareOffPrice""",
        """parseFloat(document.getElementById('partitionSquareOffQty').value) || 0;
                   const partitionSquareOffPrice"""
    )

    content = content.replace(
        """parseFloat(document.getElementById('partitio""" + '\n' + """                   const addQty""",
        """parseFloat(document.getElementById('partitionSquareOffPrice').value) || 0;
                   const addQty"""
    )

    content = content.replace(
        """parseFloat(document.getElementById('addQtyPrice').value""" + '\n',
        """parseFloat(document.getElementById('addQtyPrice').value) || 0;\n"""
    )

    # Fix: calculationResult innerHTML
    content = content.replace(
        """document.getElementById('calculationResult').innerHTML = \"Please enter En""",
        """document.getElementById('calculationResult').innerHTML = \"Please enter Entry Price first.\";"""
    )

    content = content.replace(
        """document.getElementById('calculationResult').innerHTML = \"Please enter qu""",
        """document.getElementById('calculationResult').innerHTML = \"Please enter quantity values.\";"""
    )

    # Fix: partition profit calc
    content = content.replace(
        """(partitionSquareOffPrice - entryPrice) * partitionSquareOffQ""",
        """(partitionSquareOffPrice - entryPrice) * partitionSquareOffQty;"""
    )

    # Fix: profitLock getElementById
    content = content.replace(
        """control = document.getElementById('p""" + '\n' + """                         else if (toggleId === 'toggleProfitGap') control = document.getElementById('p""",
        """control = document.getElementById('profitLock');
                         else if (toggleId === 'toggleProfitGap') control = document.getElementById('profitGap');"""
    )

    # Fix: positionInitialize button checks
    content = content.replace(
        """control = document.getElementById('positionOrderType');""" + '\n' + """                         else if (toggleId === 'togglePart') control = document.getElementById('positionPart');""",
        """control = document.getElementById('positionOrderType');
                         else if (toggleId === 'togglePart') control = document.getElementById('positionPart');"""
    )

    # Fix: condition class regex
    content = content.replace(
        """p.orderCondition.toLowerCase().replace(/\\s+/g, '-')}\`;""",
        """p.orderCondition.toLowerCase().replace(/\\s+/g, '-')}\`;"""
    )

    # Fix: position settings partition & price
    content = content.replace(
        """document.getElementById('partitionSquareOffPrice').value = posSettings.partitionSquareOffQty || 0;""",
        """document.getElementById('partitionSquareOffPrice').value = posSettings.partitionSquareOffPrice || '';"""
    )

    # Fix: action modal partition values
    content = content.replace(
        """document.getElementById('actionPartitionSquareOffQty').value = posSettings.p""",
        """document.getElementById('actionPartitionSquareOffQty').value = posSettings.partitionSquareOffQty || 0;"""
    )
    content = content.replace(
        """document.getElementById('actionPartitionSquareOffPrice').value = posSettings""",
        """document.getElementById('actionPartitionSquareOffPrice').value = posSettings.partitionSquareOffPrice || 0;"""
    )
    content = content.replace(
        """document.getElementById('actionAddQtyPrice').value = posSettings.addQtyPric""",
        """document.getElementById('actionAddQtyPrice').value = posSettings.addQtyPrice || 0;"""
    )

    # Fix: 'Enter values to ca' truncation
    content = content.replace(
        """document.getElementById('calculationResult').innerHTML = 'Enter values to ca""",
        """document.getElementById('calculationResult').innerHTML = 'Enter values to calculate';"""
    )

    # Fix: position details view truncations
    content = content.replace(
        """${posSettings.part.toUpperCase()} ${posSettings.partEnabled !== false""",
        """${posSettings.part.toUpperCase()} ${posSettings.partEnabled !== false ? '✅' : '❌'}<br>"""
    )
    content = content.replace(
        """${posSettings.qty} ${posSettings.qtyEnabled !== false ? '✅' : '❌'}<br""",
        """${posSettings.qty} ${posSettings.qtyEnabled !== false ? '✅' : '❌'}<br>"""
    )
    content = content.replace(
        """${posSettings.trailingSL?.type || 'N/A'} (${posSettings.trailingSL?""",
        """${posSettings.trailingSL?.type || 'N/A'} (${posSettings.trailingSL?.value || '0'}) ${posSettings.trailingSL?.enabled ? '✅' : '❌'}<br>"""
    )
    content = content.replace(
        """${posSettings.target?.type || 'N/A'} (${posSettings.target?.value || '""",
        """${posSettings.target?.type || 'N/A'} (${posSettings.target?.value || '0'}) ${posSettings.target?.enabled ? '✅' : '❌'}<br>"""
    )
    content = content.replace(
        """${posSettings.exit?.type || 'N/A'} (${posSettings.exit?.value || '0'}) ${po""",
        """${posSettings.exit?.type || 'N/A'} (${posSettings.exit?.value || '0'}) ${posSettings.exit?.enabled ? '✅' : '❌'}<br>"""
    )
    content = content.replace(
        """₹${posSettings.profitLock || '0'} ${posSettings.profitLockEnable""",
        """₹${posSettings.profitLock || '0'} ${posSettings.profitLockEnabled ? '✅' : '❌'}<br>"""
    )
    content = content.replace(
        """₹${posSettings.profitGap || '0'} ${posSettings.profitGapEnabled""",
        """₹${posSettings.profitGap || '0'} ${posSettings.profitGapEnabled ? '✅' : '❌'}<br>"""
    )

    # Fix: partition square off details
    content = content.replace(
        """Partition Square Off Qty: ${posSettings.partitionSquareOffQ""",
        """Partition Square Off Qty: ${posSettings.partitionSquareOffQty}<br>"""
    )

    # Fix: partition square off price
    content = content.replace(
        """Partition Square Off Price: ₹${posSettings.partitionSquareOffPrice || '0.00'}<br>""",
        """Partition Square Off Price: ₹${posSettings.partitionSquareOffPrice || '0.00'}<br>"""
    )

    # Fix: add qty price
    content = content.replace(
        """Add Quantity Price: ₹${posSettings.addQtyPrice || '0.00'}<b""",
        """Add Quantity Price: ₹${posSettings.addQtyPrice || '0.00'}<br>"""
    )

    # Fix: modify position settings values
    content = content.replace(
        """document.getElementById('positionQty').value = posSettings.qty || position.""",
        """document.getElementById('positionQty').value = posSettings.qty || position.buyQty;"""
    )
    content = content.replace(
        """document.getElementById('trailingSLType').value = posSettings.trailingSL?.ty""",
        """document.getElementById('trailingSLType').value = posSettings.trailingSL?.type || 'point';"""
    )
    content = content.replace(
        """document.getElementById('trailingSLValue').value = posSettings.trailingSL?.v""",
        """document.getElementById('trailingSLValue').value = posSettings.trailingSL?.value || 0;"""
    )
    content = content.replace(
        """document.getElementById('targetType').value = posSettings.target?.type || '""",
        """document.getElementById('targetType').value = posSettings.target?.type || 'point';"""
    )
    content = content.replace(
        """document.getElementById('targetValue').value = posSettings.target?.value ||""",
        """document.getElementById('targetValue').value = posSettings.target?.value || 0;"""
    )
    content = content.replace(
        """document.getElementById('exitType').value = posSettings.exit?.type || 'point""",
        """document.getElementById('exitType').value = posSettings.exit?.type || 'point';"""
    )

    content = content.replace(
        """document.getElementById('partitionSquareOffQty').value = posSettings.partitionSquareOffQty || 0;""" + '\n' + """                       document.getElementById('partitionSquareOffPrice').value = posSettings.partitionSquareOffPrice || '';""",
        """document.getElementById('partitionSquareOffQty').value = posSettings.partitionSquareOffQty || 0;
                       document.getElementById('partitionSquareOffPrice').value = posSettings.partitionSquareOffPrice || '';"""
    )

    content = content.replace(
        """document.getElementById('addQtyPrice').value = posSettings.addQtyPrice |""",
        """document.getElementById('addQtyPrice').value = posSettings.addQtyPrice || '';"""
    )

    content = content.replace(
        """document.getElementById('maxPartitionCount').value = posSettings.maxPartitionCount || 5;""",
        """document.getElementById('maxPartitionCount').value = posSettings.maxPartitionCount || 5;"""
    )

    content = content.replace(
        """document.getElementById('autoSquareOffPercent').value = posSettings.autoSquareOffPercent || 10;""",
        """document.getElementById('autoSquareOffPercent').value = posSettings.autoSquareOffPercent || 10;"""
    )

    content = content.replace(
        """document.getElementById('reentryAttempts').value = posSettings.reentryAttempts || 3;""",
        """document.getElementById('reentryAttempts').value = posSettings.reentryAttempts || 3;"""
    )

    content = content.replace(
        """document.getElementById('indicatorPeriod').value = posSettings.trailingSL?.indicator?.period || '14';""",
        """document.getElementById('indicatorPeriod').value = posSettings.trailingSL?.indicator?.period || '14';"""
    )
    content = content.replace(
        """document.getElementById('indicatorCondition').value = posSettings.trai""",
        """document.getElementById('indicatorCondition').value = posSettings.trailingSL?.indicator?.condition || 'close';"""
    )

    # Fix: strategy code test alert
    content = content.replace(
        """alert(\"Strategy code tested (simulation). In real app, this would execute the c""",
        """alert(\"Strategy code tested (simulation). In real app, this would execute the code.\");"""
    )

    # Fix: partition square off confirm
    content = content.replace(
        """`Square off ${partitionQty} units of ${position.symbol} at ₹${partitionPrice.toFixed(2)}?`;\n""",
        """`Square off ${partitionQty} units of ${position.symbol} at ₹${partitionPrice.toFixed(2)}?`;\n"""
    )

    # Fix: partition amount at toFixed
    content = content.replace(
        """₹${partitionPrice.toFixed(2)}?`;""" + '\n\n\n                    if (confirm(confirmMsg',
        """₹${partitionPrice.toFixed(2)}?`;

                    if (confirm(confirmMsg"""
    )

    # Fix: add qty confirmMsg
    content = content.replace(
        """`Add ${addQty} units to ${position.symbol} position at ₹${addPrice.toFixed(2)}?`;\n\n\n                    if (confirm(confirmMsg""",
        """`Add ${addQty} units to ${position.symbol} position at ₹${addPrice.toFixed(2)}?`;

                    if (confirm(confirmMsg"""
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print("JS fixes applied")

    # Verify: count remaining potential issues
    lines = content.split('\n')
    in_script = False
    issues = 0
    for i, line in enumerate(lines, 1):
        stripped = line.rstrip()
        if '<script>' in stripped:
            in_script = True
            continue
        if '</script>' in stripped:
            in_script = False
            continue
        if not in_script:
            continue

        s = stripped.lstrip()
        if not s or s.startswith('//') or s.startswith('/*') or s.startswith('*'):
            continue

        # Very basic check for common truncation indicators
        if len(s) > 85 and s[-1] not in ';{}()],\'">/':
            if not s.endswith(('true', 'false', 'null', 'undefined', '0', 'event')):
                issues += 1
                if issues <= 20:
                    print(f"  Potential issue line {i}: ...{s[-50:]}")

    print(f"Remaining potential issues: {issues}")


if __name__ == '__main__':
    fix_js_in_html('/var/lib/freelancer/projects/40172829/web_app/templates/index.html')
