"""
Fix truncated HTML attributes from PDF extraction.
Reads kome-design-clean.txt and outputs a proper index.html
"""
import re

def fix_truncated_lines(text):
    """Join lines that were truncated at PDF page boundaries."""
    lines = text.split('\n')
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()

        # Check if this line appears truncated (ends mid-attribute or mid-value)
        # Indicators of truncation:
        # 1. Ends with an unclosed quote in an HTML attribute
        # 2. Ends mid-CSS property value
        # 3. Ends mid-JS expression

        # Count quotes to detect unclosed strings in HTML attributes
        # Skip CSS and pure JS lines
        is_html_attr_line = re.search(r'(style|onclick|onmouseenter|onmouseleave|class|id|placeholder|title)="[^"]*$', stripped)
        is_truncated_tag = re.search(r'<(button|div|input|select|label|a|span|textarea|option)\s[^>]*$', stripped) and '"' in stripped
        is_css_truncated = re.search(r'var\(--\w+-c$', stripped)  # e.g., var(--secondary-c

        if is_html_attr_line or is_truncated_tag or is_css_truncated:
            # This line is truncated. Try to join with next line(s)
            combined = stripped
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line:
                    j += 1
                    continue
                combined += next_line
                # Check if the combined line now has matching quotes
                if is_html_attr_line or is_truncated_tag:
                    # Check if all quotes are now balanced
                    in_tag = combined.rfind('<')
                    if in_tag >= 0:
                        tag_part = combined[in_tag:]
                        # If we find a closing > for the tag, we're done
                        if '>' in tag_part[1:]:
                            break
                if is_css_truncated:
                    if combined.rstrip().endswith((';', '{', '}')):
                        break
                j += 1
                if j - i > 3:  # Don't join more than 3 lines
                    break

            fixed_lines.append(combined)
            i = j + 1
        else:
            fixed_lines.append(line)
            i += 1

    return '\n'.join(fixed_lines)


def fix_specific_truncations(html):
    """Fix known truncation patterns from the PDF extraction."""

    # Fix CSS truncations: var(--secondary-c -> var(--secondary-color)
    html = html.replace('var(--secondary-c\n', 'var(--secondary-color)')
    html = re.sub(r'var\(--secondary-c([^o])', r'var(--secondary-color)\1', html)

    # Fix truncated style attributes - close them properly
    # Pattern: style="... followed by a newline without closing quote
    def fix_style_attr(match):
        style_content = match.group(1)
        # If it doesn't end with a quote, add one
        if not style_content.endswith('"'):
            return f'style="{style_content}"'
        return match.group(0)

    return html


def build_proper_html(source_file, output_file):
    """Build a proper HTML file from the clean text source."""

    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove the timestamp header
    lines = content.split('\n')
    if lines[0].startswith('2/14/26'):
        lines = lines[1:]
    content = '\n'.join(lines)

    # Find the three main sections
    style_start = content.find('<style>')
    style_end = content.find('</style>') + len('</style>')
    script_start = content.find('<script>')
    script_end = content.find('</script>') + len('</script>')

    css_section = content[style_start:style_end]

    # HTML body is between </style> and <script>
    # But we need to find the actual body HTML
    # The source has: </style> ... Font Awesome link ... header HTML ... <script>
    body_html_raw = content[style_end:script_start].strip()

    js_section = content[script_start:script_end]

    # Fix CSS truncations
    css_section = css_section.replace(
        "var(--primary-color) 0%, var(--secondary-c",
        "var(--primary-color) 0%, var(--secondary-color) 100%)"
    )

    # Fix body HTML truncations - these are all the inline style/attribute truncations
    # We'll fix them with specific patterns found in the analysis

    fixes = {
        # Nav trigger button
        'onmouseenter="showNav\n': 'onmouseenter="showNavPopup()">\n',
        'onmouseenter="showNav"': 'onmouseenter="showNavPopup()"',

        # Dashboard controls div
        'background: rgba(0,0,0,0.3); border\n': 'background: rgba(0,0,0,0.3); border-radius: 5px;">\n',

        # View controls heading
        'font-size: 14px; margin-bottom: 10px; text\n': 'font-size: 14px; margin-bottom: 10px; text-transform: uppercase;">\n',

        # Full screen button style
        'background: linear-gradient(135deg\n': 'background: linear-gradient(135deg, #0077ff, #0055cc); border: none; color: #fff; border-radius: 5px; cursor: pointer;">\n',

        # Reset button style
        'background: linear-gradient(135deg, #ff\n': 'background: linear-gradient(135deg, #ff4444, #cc0000); border: none; color: #fff; border-radius: 5px; cursor: pointer;">\n',

        # Logout button
        'background: linear-gradient(\n': 'background: linear-gradient(135deg, #ff4444, #cc0000); border: none; color: #fff; border-radius: 5px; cursor: pointer;">\n',

        # Clear watchlist button
        'title="Clear All">Clea\n': 'title="Clear All">Clear All</button>\n',

        # Watchlist search input
        'placeholder="Enter stock symbol (e.g., RELIANCE\n': 'placeholder="Enter stock symbol (e.g., RELIANCE)">\n',

        # No watchlist stocks message
        'No stocks in watchlist. Search and add stoc\n': 'No stocks in watchlist. Search and add stocks above.</div>\n',

        # Quick actions div
        'border-top: 1px solid rgba(255,2\n': 'border-top: 1px solid rgba(255,255,255,0.1);">\n',

        # Quick actions heading
        'font-size: 14px; margin-bottom: 10px; text\n': 'font-size: 14px; margin-bottom: 10px; text-transform: uppercase;">\n',

        # Add Multiple button
        'background: #00\n': 'background: #0077ff; border: none; color: #fff; border-radius: 5px; cursor: pointer;">\n',

        # Import button
        'background: #9d4e\n': 'background: #9d4edd; border: none; color: #fff; border-radius: 5px; cursor: pointer;">\n',

        # Export button
        'background: #00aa\n': 'background: #00aa66; border: none; color: #fff; border-radius: 5px; cursor: pointer;">\n',

        # Refresh button
        'background: #ff99\n': 'background: #ff9900; border: none; color: #fff; border-radius: 5px; cursor: pointer;">\n',

        # Broker page margin
        'border-radius: 10px; margin-\n': 'border-radius: 10px; margin-bottom: 20px;">\n',

        # Broker labels
        'color: #aaa;">Broker N\n': 'color: #aaa;">Broker Name</label>\n',
        'color: #aaa;">Client ID<\n': 'color: #aaa;">Client ID</label>\n',
        'color: #aaa;">API Key<\n': 'color: #aaa;">API Key</label>\n',
        'color: #aaa;">API Secre\n': 'color: #aaa;">API Secret</label>\n',
        'color: #aaa;">Access To\n': 'color: #aaa;">Access Token</label>\n',
        'color: #aaa;">PIN (Opt\n': 'color: #aaa;">PIN (Optional)</label>\n',

        # Broker select style
        'style="width:100%; padding:10px; background\n': 'style="width:100%; padding:10px; background:#333; color:#fff; border:none; border-radius:5px;">\n',

        # Broker input styles
        'style="width:100%; padding:10px; background:#333; color:#fff; bord\n': 'style="width:100%; padding:10px; background:#333; color:#fff; border:none; border-radius:5px;">\n',

        # Broker action buttons
        'style="flex:1; padding:12px; background\n': 'style="flex:1; padding:12px; background:#00aa66; border:none; color:#fff; border-radius:5px; cursor:pointer; font-weight:bold;">\n',
        'style="flex:1; padding:12px; background:\n': 'style="flex:1; padding:12px; background:#ff4444; border:none; color:#fff; border-radius:5px; cursor:pointer; font-weight:bold;">\n',
        'style="flex:1; padding:12px; ba\n': 'style="flex:1; padding:12px; background:#0077ff; border:none; color:#fff; border-radius:5px; cursor:pointer; font-weight:bold;">\n',

        # Saved brokers margin
        'border-radius: 10px; margin-\n': 'border-radius: 10px; margin-bottom: 20px;">\n',
    }

    for old, new in fixes.items():
        body_html_raw = body_html_raw.replace(old, new)

    # Fix JS truncations
    js_fixes = {
        # Ticker data - missing commas and truncated names
        '{ symbol: "BANKNIFTY", price: 47520.30, change: 320.75, name: "NIFTY BANK" }\n': '{ symbol: "BANKNIFTY", price: 47520.30, change: 320.75, name: "NIFTY BANK" },\n',
        'name: "S&P BSE SENSEX"\n': 'name: "S&P BSE SENSEX" },\n',
        'name: "Reliance Industrie\n': 'name: "Reliance Industries" },\n',
        'name: "Tata Consultancy Servic\n': 'name: "Tata Consultancy Services" },\n',
        'name: "HDFC Bank" }\n': 'name: "HDFC Bank" }\n',
    }

    for old, new in js_fixes.items():
        js_section = js_section.replace(old, new)

    # Build the complete HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MUKESH ALGO</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    {css_section}
</head>
<body>
    <!-- ===== HEADER ===== -->
    <div class="header">
        <div class="app-title">
            <span class="bull">&#x1F402;</span>
            <span class="title-text">MUKESH ALGO</span>
            <span class="bear">&#x1F43B;</span>
        </div>

        <!-- USER BOX -->
        <div class="user-box">
            <div class="user-name">Mukeshbhai</div>
            <div class="pl-box" id="plBox">P/L : ₹1,25,430</div>
        </div>

        <!-- LIVE WATCH -->
        <div class="live-watch-container">
            <div class="live-watch">LIVE</div>
            <div class="digital-clock" id="digitalClock">00:00:00</div>
        </div>
    </div>

    <!-- ===== ENHANCED HORIZONTAL MARKET TICKER ===== -->
    <div class="market-ticker-container">
        <div class="ticker-header">LIVE MARKET</div>
        <div class="market-ticker" id="marketTicker">
            <!-- Ticker items will be populated by JavaScript -->
        </div>
    </div>

    <!-- ===== SEPARATE NAVIGATION POPUP (LEFT SIDE) ===== -->
    <button class="nav-hover-trigger" id="navHoverTrigger" onmouseenter="showNavPopup()">
        <i class="fas fa-bars"></i>
    </button>

    <div class="nav-popup" id="navPopup" onmouseleave="hideNavPopup()">
        <div class="nav-popup-header">
            <i class="fas fa-bars"></i> NAVIGATION
        </div>
        <button onclick="showPage('openPositionsPage')">
            <i class="fas fa-chart-line"></i> Open Positions
        </button>
        <button onclick="showPage('orderbookPage')">
            <i class="fas fa-book"></i> Order Book
        </button>
        <button onclick="openScreenerPopup()">
            <i class="fas fa-search"></i> Screener
        </button>
        <button onclick="openStrategyPopup()">
            <i class="fas fa-chess-board"></i> Strategy Creation
        </button>
        <button onclick="showPage('reportPage')">
            <i class="fas fa-chart-bar"></i> Reports
        </button>
        <button onclick="showPage('profilePage')">
            <i class="fas fa-user"></i> Profile
        </button>
        <button onclick="showPage('brokerPage')">
            <i class="fas fa-university"></i> Broker
        </button>
        <button onclick="showPage('marketplacePage')">
            <i class="fas fa-store"></i> Market Place
        </button>
        <button onclick="showPage('paperTradingPage')">
            <i class="fas fa-file-invoice-dollar"></i> Paper Trading
        </button>
        <button onclick="showPage('myPlanPage')">
            <i class="fas fa-calendar-alt"></i> My Plan
        </button>
        <button onclick="showPage('backtestPage')">
            <i class="fas fa-history"></i> Backtest
        </button>
        <button onclick="showPage('settingsPage')">
            <i class="fas fa-cog"></i> Settings
        </button>
        <button onclick="showPage('alPage')">
            <i class="fas fa-robot"></i> AL
        </button>

        <!-- Dashboard Controls -->
        <div style="margin-top: 20px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 5px;">
            <h4 style="color: var(--accent-color); font-size: 14px; margin-bottom: 10px; text-transform: uppercase;">
                <i class="fas fa-expand"></i> VIEW CONTROLS
            </h4>
            <button onclick="fullScreenMode()" style="width:100%; margin-bottom:5px; padding:8px; background: linear-gradient(135deg, #0077ff, #0055cc); border: none; color: #fff; border-radius: 5px; cursor: pointer;">
                <i class="fas fa-expand"></i> Full Screen
            </button>
            <button onclick="resetAllData()" style="width:100%; padding:8px; background: linear-gradient(135deg, #ff4444, #cc0000); border: none; color: #fff; border-radius: 5px; cursor: pointer;">
                <i class="fas fa-redo"></i> Reset Data
            </button>
        </div>

        <button onclick="logOut()" style="margin-top: 20px; width:100%; padding:10px; background: linear-gradient(135deg, #ff4444, #cc0000); border: none; color: #fff; border-radius: 5px; cursor: pointer;">
            <i class="fas fa-sign-out-alt"></i> Log Out
        </button>
    </div>

    <!-- ===== SEPARATE WATCHLIST PANEL (RIGHT SIDE - ALWAYS VISIBLE) ===== -->
    <div class="watchlist-panel" id="watchlistPanel">
        <div class="watchlist-panel-header">
            <span><i class="fas fa-star"></i> WATCHLIST</span>
            <button class="clear-watchlist-btn" id="clearWatchlistBtn" title="Clear All">Clear All</button>
        </div>

        <div class="watchlist-container">
            <div class="search-container">
                <input id="watchlistSearch" placeholder="Enter stock symbol (e.g., RELIANCE)">
                <button id="watchlistSearchBtn">Add Stock</button>
            </div>

            <div class="watchlist-stocks" id="watchlistStocks">
                <div class="no-watchlist-stocks">No stocks in watchlist. Search and add stocks above.</div>
            </div>
        </div>

        <!-- Quick Actions for Watchlist -->
        <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
            <h4 style="color: var(--accent-color); font-size: 14px; margin-bottom: 10px; text-transform: uppercase;">
                <i class="fas fa-bolt"></i> QUICK ACTIONS
            </h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <button onclick="addMultipleStocks()" style="padding: 8px; background: #0077ff; border: none; color: #fff; border-radius: 5px; cursor: pointer; font-size: 12px;">
                    <i class="fas fa-plus-circle"></i> Add Multiple
                </button>
                <button onclick="importWatchlist()" style="padding: 8px; background: #9d4edd; border: none; color: #fff; border-radius: 5px; cursor: pointer; font-size: 12px;">
                    <i class="fas fa-file-import"></i> Import
                </button>
                <button onclick="exportWatchlist()" style="padding: 8px; background: #00aa66; border: none; color: #fff; border-radius: 5px; cursor: pointer; font-size: 12px;">
                    <i class="fas fa-file-export"></i> Export
                </button>
                <button onclick="refreshWatchlist()" style="padding: 8px; background: #ff9900; border: none; color: #fff; border-radius: 5px; cursor: pointer; font-size: 12px;">
                    <i class="fas fa-sync-alt"></i> Refresh
                </button>
            </div>
        </div>
    </div>

    <!-- ===== MAIN CONTENT ===== -->
    <div class="content" id="mainContent">
        <!-- Open Positions Page -->
        <div class="content-page" id="openPositionsPage">
            <div class="open-positions-container">
                <div class="positions-main">
                    <div class="positions-header">
                        <h2><i class="fas fa-chart-line"></i> Open Positions</h2>
                        <button class="add-position-btn" onclick="openAddPositionModal()">
                            <i class="fas fa-plus"></i> Add Position
                        </button>
                    </div>

                    <div style="overflow-x: auto;">
                        <table class="positions-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Symbol</th>
                                    <th>Order Type</th>
                                    <th>Order Condition</th>
                                    <th>Entry Price</th>
                                    <th>Current Price</th>
                                    <th>Buy Qty</th>
                                    <th>Sell Qty</th>
                                    <th>Buy Avg Price</th>
                                    <th>Sell Avg Price</th>
                                    <th>Day P&amp;L</th>
                                    <th>Net P&amp;L</th>
                                    <th>Net %</th>
                                    <th>Source</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="positionsTable">
                                <!-- Positions will be loaded here -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- Other Pages -->
        <div class="content-page hidden" id="orderbookPage">
            <h2><i class="fas fa-book"></i> Order Book &amp; Portfolio</h2>
            <p>Order book content will be displayed here.</p>
        </div>

        <div class="content-page hidden" id="screenerPage">
            <h2><i class="fas fa-search"></i> Stock Screener</h2>
            <p>This page shows advanced stock screening tools.</p>
        </div>

        <div class="content-page hidden" id="strategyCreationPage">
            <h2><i class="fas fa-chess-board"></i> Strategy Creation</h2>
            <p>This page allows you to create trading strategies.</p>
        </div>

        <div class="content-page hidden" id="reportPage">
            <h2><i class="fas fa-chart-bar"></i> Reports</h2>
            <p>This page shows trading reports and analytics.</p>
        </div>

        <!-- ===== ENHANCED BROKER PAGE ===== -->
        <div class="content-page hidden" id="brokerPage">
            <h2><i class="fas fa-university"></i> Broker Management</h2>

            <!-- Broker Form -->
            <div style="background: #1a1a1a; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <h3 style="color: var(--accent-color); margin-bottom: 20px;">
                    <i class="fas fa-plus-circle"></i> Add/Edit Broker
                </h3>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div>
                        <label style="display: block; margin-bottom: 8px; color: #aaa;">Broker Name</label>
                        <select id="brokerSelect" style="width:100%; padding:10px; background:#333; color:#fff; border:none; border-radius:5px;">
                            <option value="">Select Broker</option>
                            <option value="ZERODHA">Zerodha</option>
                            <option value="ANGEL">Angel Broking</option>
                            <option value="UPSTOX">Upstox</option>
                            <option value="ICICI">ICICI Direct</option>
                            <option value="HDFC">HDFC Securities</option>
                            <option value="ALICE">Alice Blue</option>
                            <option value="FIVE">5Paisa</option>
                            <option value="CUSTOM">Custom Broker</option>
                        </select>
                    </div>

                    <div>
                        <label style="display: block; margin-bottom: 8px; color: #aaa;">Client ID</label>
                        <input type="text" id="clientId" placeholder="Enter Client ID" style="width:100%; padding:10px; background:#333; color:#fff; border:none; border-radius:5px;">
                    </div>

                    <div>
                        <label style="display: block; margin-bottom: 8px; color: #aaa;">API Key</label>
                        <input type="password" id="apiKey" placeholder="Enter API Key" style="width:100%; padding:10px; background:#333; color:#fff; border:none; border-radius:5px;">
                    </div>

                    <div>
                        <label style="display: block; margin-bottom: 8px; color: #aaa;">API Secret</label>
                        <input type="password" id="apiSecret" placeholder="Enter API Secret" style="width:100%; padding:10px; background:#333; color:#fff; border:none; border-radius:5px;">
                    </div>

                    <div>
                        <label style="display: block; margin-bottom: 8px; color: #aaa;">Access Token</label>
                        <input type="text" id="accessToken" placeholder="Enter Access Token" style="width:100%; padding:10px; background:#333; color:#fff; border:none; border-radius:5px;">
                    </div>

                    <div>
                        <label style="display: block; margin-bottom: 8px; color: #aaa;">PIN (Optional)</label>
                        <input type="password" id="brokerPin" placeholder="Enter PIN" style="width:100%; padding:10px; background:#333; color:#fff; border:none; border-radius:5px;">
                    </div>
                </div>

                <!-- Action Buttons -->
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button onclick="addEditBroker()" style="flex:1; padding:12px; background:#00aa66; border:none; color:#fff; border-radius:5px; cursor:pointer; font-weight:bold;">
                        <i class="fas fa-save"></i> Add/Update Broker
                    </button>
                    <button onclick="deleteBroker()" style="flex:1; padding:12px; background:#ff4444; border:none; color:#fff; border-radius:5px; cursor:pointer; font-weight:bold;">
                        <i class="fas fa-trash"></i> Delete Broker
                    </button>
                    <button onclick="checkBrokerConnection()" style="flex:1; padding:12px; background:#0077ff; border:none; color:#fff; border-radius:5px; cursor:pointer; font-weight:bold;">
                        <i class="fas fa-plug"></i> Check Connection
                    </button>
                </div>
            </div>

            <!-- Saved Brokers List -->
            <div style="background: #1a1a1a; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <h3 style="color: var(--accent-color); margin-bottom: 15px;">
                    <i class="fas fa-list"></i> Saved Brokers
                </h3>
                <div id="brokerList" style="max-height: 300px; overflow-y: auto;">
                    <!-- Broker list will be loaded here -->
                </div>
            </div>
        </div>

        <div class="content-page hidden" id="profilePage">
            <h2><i class="fas fa-user"></i> Profile</h2>
            <p>User profile content will be displayed here.</p>
        </div>

        <div class="content-page hidden" id="marketplacePage">
            <h2><i class="fas fa-store"></i> Market Place</h2>
            <p>Marketplace content will be displayed here.</p>
        </div>

        <div class="content-page hidden" id="paperTradingPage">
            <h2><i class="fas fa-file-invoice-dollar"></i> Paper Trading</h2>
            <p>Paper trading content will be displayed here.</p>
        </div>

        <div class="content-page hidden" id="myPlanPage">
            <h2><i class="fas fa-calendar-alt"></i> My Plan</h2>
            <p>Plan details will be displayed here.</p>
        </div>

        <div class="content-page hidden" id="backtestPage">
            <h2><i class="fas fa-history"></i> Backtest</h2>
            <p>Backtesting tools will be displayed here.</p>
        </div>

        <div class="content-page hidden" id="settingsPage">
            <h2><i class="fas fa-cog"></i> Settings</h2>
            <p>Settings content will be displayed here.</p>
        </div>

        <div class="content-page hidden" id="alPage">
            <h2><i class="fas fa-robot"></i> AL</h2>
            <p>AI trading tools will be displayed here.</p>
        </div>
    </div>
'''

    # Now add the modals - these are the most complex parts with many truncated attributes
    # We'll write them clean instead of trying to fix the truncated versions

    modals_html = '''
    <!-- ===== ENHANCED ADD POSITION MODAL ===== -->
    <div id="addPositionModal" class="modal" onclick="outsideCloseAddModal(event)">
        <div class="modal-box">
            <div class="modal-header">
                <h3 id="modalSymbolTitle">Add Position</h3>
                <button onclick="closeAddModal()">&#x2716;</button>
            </div>

            <div>
                <div style="margin-bottom:15px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Symbol</label>
                    <input id="positionSymbol" placeholder="Enter stock symbol (e.g., RELIANCE)">
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px">
                    <div>
                        <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Order Type</label>
                        <select id="orderType">
                            <option value="BUY">BUY</option>
                            <option value="SELL">SELL</option>
                        </select>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Order Condition</label>
                        <select id="orderCondition">
                            <option value="Intraday">Intraday</option>
                            <option value="Positional">Positional</option>
                            <option value="BO">BO (Bracket Order)</option>
                            <option value="St">St (Stop Loss)</option>
                            <option value="MSL">MSL (Multiple Stop Loss)</option>
                        </select>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px">
                    <div>
                        <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Buy Qty</label>
                        <input id="buyQty" type="number" placeholder="Buy Qty" value="0">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Sell Qty</label>
                        <input id="sellQty" type="number" placeholder="Sell Qty" value="0">
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px">
                    <div>
                        <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Entry Price</label>
                        <input id="entryPrice" type="number" placeholder="Entry Price">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Current Price</label>
                        <input id="currentPrice" type="number" placeholder="Current Price">
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px">
                    <div>
                        <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Buy Avg Price</label>
                        <input id="buyAvgPrice" type="number" placeholder="Buy Avg Price">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Sell Avg Price</label>
                        <input id="sellAvgPrice" type="number" placeholder="Sell Avg Price">
                    </div>
                </div>

                <!-- ===== ENABLE/DISABLE OPTIONS ===== -->
                <div style="margin: 20px 0; padding: 15px; background: #222; border-radius: 5px;">
                    <h4 style="color: var(--accent-color); margin-bottom: 15px;">
                        <i class="fas fa-toggle-on"></i> Enable/Disable Options
                    </h4>

                    <div class="enable-option" onclick="toggleEnableOption('positionSettings')">
                        <div><i class="fas fa-cog"></i> Position Settings</div>
                        <div class="enable-status enabled" id="positionSettingsStatus"><i class="fas fa-check"></i></div>
                    </div>

                    <div class="enable-option" onclick="toggleEnableOption('partitionSettings')">
                        <div><i class="fas fa-layer-group"></i> Partition Settings</div>
                        <div class="enable-status enabled" id="partitionSettingsStatus"><i class="fas fa-check"></i></div>
                    </div>

                    <div class="enable-option" onclick="toggleEnableOption('trailingSL')">
                        <div><i class="fas fa-chart-line"></i> Trailing Stop Loss</div>
                        <div class="enable-status enabled" id="trailingSLStatus"><i class="fas fa-check"></i></div>
                    </div>

                    <div class="enable-option" onclick="toggleEnableOption('profitLock')">
                        <div><i class="fas fa-lock"></i> Profit Lock</div>
                        <div class="enable-status disabled" id="profitLockStatus"><i class="fas fa-times"></i></div>
                    </div>
                </div>

                <!-- ===== POSITION SETTINGS SECTION ===== -->
                <div class="position-section" id="positionSettingsSection">
                    <div class="position-section-header" onclick="togglePositionSection()">
                        <h4><i class="fas fa-cog"></i> Position Settings</h4>
                        <button class="position-section-toggle" id="positionSectionToggle">
                            <i class="fas fa-chevron-up"></i> Collapse
                        </button>
                    </div>

                    <div class="position-section-body" id="positionSectionBody">
                        <div class="position-row">
                            <div class="position-toggle">
                                <label class="toggle-switch">
                                    <input type="checkbox" id="toggleOrderType" checked>
                                    <span class="toggle-slider"></span>
                                </label>
                                <span class="toggle-label">Order Type</span>
                            </div>
                            <div class="position-controls">
                                <select id="positionOrderType" class="section-input">
                                    <option value="limit">Limit</option>
                                    <option value="market">Market</option>
                                    <option value="sl">Stop Loss (SL)</option>
                                    <option value="market_sl">Market Stop Loss</option>
                                </select>
                            </div>
                        </div>

                        <div class="position-row">
                            <div class="position-toggle">
                                <label class="toggle-switch">
                                    <input type="checkbox" id="togglePart" checked>
                                    <span class="toggle-slider"></span>
                                </label>
                                <span class="toggle-label">Part</span>
                            </div>
                            <div class="position-controls">
                                <select id="positionPart" class="section-input">
                                    <option value="buy">Buy</option>
                                    <option value="sell">Sell</option>
                                </select>
                            </div>
                        </div>

                        <div class="position-row">
                            <div class="position-toggle">
                                <label class="toggle-switch">
                                    <input type="checkbox" id="toggleQty" checked>
                                    <span class="toggle-slider"></span>
                                </label>
                                <span class="toggle-label">Quantity</span>
                            </div>
                            <div class="position-controls">
                                <div style="display: flex; gap: 10px; width: 100%;">
                                    <input id="positionQty" type="number" placeholder="Buy Qty" value="10" class="section-input" style="flex: 1;">
                                    <input id="positionSellQty" type="number" placeholder="Sell Qty" value="0" class="section-input" style="flex: 1;">
                                </div>
                            </div>
                        </div>

                        <div class="position-row" id="trailingSLRow">
                            <div class="position-toggle">
                                <label class="toggle-switch">
                                    <input type="checkbox" id="toggleTrailingSL" checked>
                                    <span class="toggle-slider"></span>
                                </label>
                                <span class="toggle-label">Trailing SL</span>
                            </div>
                            <div class="position-controls">
                                <div style="display: flex; gap: 10px; width: 100%;">
                                    <select id="trailingSLType" style="flex: 1;">
                                        <option value="point">Point</option>
                                        <option value="price">Price</option>
                                        <option value="spot">Spot</option>
                                        <option value="fut">Futures</option>
                                        <option value="mtm">MTM</option>
                                        <option value="indicator">Indicator Based</option>
                                    </select>
                                    <input id="trailingSLValue" type="number" placeholder="Value" style="flex: 1;" value="20">
                                </div>
                            </div>
                        </div>

                        <div id="indicatorOptions" class="indicator-options" style="display:none;">
                            <div>
                                <label class="indicator-label">Period</label>
                                <input id="indicatorPeriod" type="number" placeholder="Period" class="indicator-input" value="14">
                            </div>
                            <div>
                                <label class="indicator-label">Condition</label>
                                <select id="indicatorCondition" class="indicator-input">
                                    <option value="close">Close</option>
                                    <option value="cross">Cross</option>
                                </select>
                            </div>
                        </div>

                        <div class="position-row">
                            <div class="position-toggle">
                                <label class="toggle-switch">
                                    <input type="checkbox" id="toggleTarget" checked>
                                    <span class="toggle-slider"></span>
                                </label>
                                <span class="toggle-label">Target</span>
                            </div>
                            <div class="position-controls">
                                <div style="display: flex; gap: 10px; width: 100%;">
                                    <select id="targetType" style="flex: 1;">
                                        <option value="point">Point</option>
                                        <option value="price">Price</option>
                                        <option value="spot">Spot</option>
                                        <option value="fut">Futures</option>
                                        <option value="mtm">MTM</option>
                                    </select>
                                    <input id="targetValue" type="number" placeholder="Target Value" style="flex: 1;" value="50">
                                </div>
                            </div>
                        </div>

                        <div class="position-row">
                            <div class="position-toggle">
                                <label class="toggle-switch">
                                    <input type="checkbox" id="toggleExit" checked>
                                    <span class="toggle-slider"></span>
                                </label>
                                <span class="toggle-label">Exit</span>
                            </div>
                            <div class="position-controls">
                                <div style="display: flex; gap: 10px; width: 100%;">
                                    <select id="exitType" style="flex: 1;">
                                        <option value="point">Point</option>
                                        <option value="price">Price</option>
                                        <option value="spot">Spot</option>
                                        <option value="fut">Futures</option>
                                        <option value="mtm">MTM</option>
                                    </select>
                                    <input id="exitValue" type="number" placeholder="Exit Value" style="flex: 1;" value="30">
                                </div>
                            </div>
                        </div>

                        <div class="position-row" id="profitLockRow">
                            <div class="position-toggle">
                                <label class="toggle-switch">
                                    <input type="checkbox" id="toggleProfitLock" checked>
                                    <span class="toggle-slider"></span>
                                </label>
                                <span class="toggle-label">Profit Lock</span>
                            </div>
                            <div class="position-controls">
                                <input id="profitLock" type="number" placeholder="Profit Lock Price" class="section-input">
                            </div>
                        </div>

                        <div class="position-row">
                            <div class="position-toggle">
                                <label class="toggle-switch">
                                    <input type="checkbox" id="toggleProfitGap" checked>
                                    <span class="toggle-slider"></span>
                                </label>
                                <span class="toggle-label">Profit Gap</span>
                            </div>
                            <div class="position-controls">
                                <input id="profitGap" type="number" placeholder="Profit Gap Price" class="section-input">
                            </div>
                        </div>

                        <div style="display: flex; gap: 10px; margin-top: 15px;">
                            <button onclick="toggleAllPositionSettings(true)" style="flex:1; padding:10px; background:#00aa66; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                                <i class="fas fa-toggle-on"></i> All ON
                            </button>
                            <button onclick="toggleAllPositionSettings(false)" style="flex:1; padding:10px; background:#ff4444; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                                <i class="fas fa-toggle-off"></i> All OFF
                            </button>
                            <button onclick="resetPositionSettings()" style="flex:1; padding:10px; background:#0077ff; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                                <i class="fas fa-redo"></i> Reset
                            </button>
                        </div>
                    </div>
                </div>

                <!-- ===== PARTITION & ADD QUANTITY SECTION ===== -->
                <div class="partition-section" id="partitionSettingsSection">
                    <div class="partition-section-header" onclick="togglePartitionSection()">
                        <h4><i class="fas fa-layer-group"></i> Partition &amp; Add Quantity</h4>
                        <button class="partition-section-toggle" id="partitionSectionToggle">
                            <i class="fas fa-chevron-up"></i> Collapse
                        </button>
                    </div>

                    <div class="partition-section-body" id="partitionSectionBody">
                        <div class="partition-grid">
                            <div class="partition-column">
                                <div class="partition-item">
                                    <h5><i class="fas fa-chart-pie"></i> Partition Square Off</h5>
                                    <div class="partition-row">
                                        <div>
                                            <label class="indicator-label">Quantity (Number)</label>
                                            <input id="partitionSquareOffQty" type="number" placeholder="0" class="indicator-input" value="2">
                                        </div>
                                        <div>
                                            <label class="indicator-label">Price</label>
                                            <input id="partitionSquareOffPrice" type="number" placeholder="0.00" class="indicator-input">
                                        </div>
                                    </div>
                                </div>

                                <div class="partition-item">
                                    <h5><i class="fas fa-plus-circle"></i> Add Quantity</h5>
                                    <div class="partition-row">
                                        <div>
                                            <label class="indicator-label">Quantity (Number)</label>
                                            <input id="addQty" type="number" placeholder="0" class="indicator-input" value="5">
                                        </div>
                                        <div>
                                            <label class="indicator-label">Price</label>
                                            <input id="addQtyPrice" type="number" placeholder="0.00" class="indicator-input">
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="partition-column">
                                <div class="partition-item">
                                    <h5><i class="fas fa-sliders-h"></i> Additional Settings</h5>
                                    <div style="display: flex; flex-direction: column; gap: 10px;">
                                        <div>
                                            <label class="indicator-label">Max Partition Count</label>
                                            <input id="maxPartitionCount" type="number" placeholder="5" class="indicator-input" value="5">
                                        </div>
                                        <div>
                                            <label class="indicator-label">Auto Square Off %</label>
                                            <input id="autoSquareOffPercent" type="number" placeholder="10" class="indicator-input" value="10">
                                        </div>
                                        <div>
                                            <label class="indicator-label">Re-entry Attempts</label>
                                            <input id="reentryAttempts" type="number" placeholder="3" class="indicator-input" value="3">
                                        </div>
                                    </div>
                                </div>

                                <div class="partition-item">
                                    <h5><i class="fas fa-calculator"></i> Quick Calculate</h5>
                                    <div style="text-align: center;">
                                        <button onclick="calculatePositionSizing()" style="width:100%; padding:10px; background:#0077ff; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                                            Calculate Position
                                        </button>
                                        <div id="calculationResult" style="font-size:14px; color:#aaa; padding:10px; margin-top:10px;">
                                            Enter values to calculate
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div style="margin-bottom:20px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Source</label>
                    <select id="positionSource">
                        <option value="LIVE">LIVE</option>
                        <option value="PAPER">PAPER</option>
                        <option value="SIMULATOR">SIMULATOR</option>
                    </select>
                </div>

                <button class="full-btn success" onclick="addPosition()">Add Position</button>
            </div>
        </div>
    </div>

    <!-- ===== ACTION MODAL ===== -->
    <div id="actionModal" class="modal" onclick="outsideCloseActionModal(event)">
        <div class="modal-box">
            <div class="modal-header">
                <h3 id="actionModalSymbolTitle">Position Actions</h3>
                <button onclick="closeActionModal()">&#x2716;</button>
            </div>

            <div class="tabs">
                <button class="active" onclick="switchActionTab(event,'modify')">Modify</button>
                <button onclick="switchActionTab(event,'exit')">Exit</button>
                <button onclick="switchActionTab(event,'existingCode')">Existing Code</button>
                <button onclick="switchActionTab(event,'settings')">Settings</button>
                <button onclick="switchActionTab(event,'partition')">Partition</button>
            </div>

            <div id="modify" class="tab-content active">
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Stop Loss</label>
                    <input id="modifyStopLoss" type="number" placeholder="Stop Loss Price">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Target</label>
                    <input id="modifyTarget" type="number" placeholder="Target Price">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Trailing SL</label>
                    <input id="modifyTrailingSL" type="number" placeholder="Trailing SL Points">
                </div>
                <button class="full-btn success" onclick="modifyPosition()">Update Position</button>
            </div>

            <div id="exit" class="tab-content">
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Quantity</label>
                    <input id="exitQty" type="number" placeholder="Quantity to Exit">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Exit Price</label>
                    <input id="exitPrice" type="number" placeholder="Exit Price">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Exit Reason</label>
                    <select id="exitReason">
                        <option value="target_hit">Target Hit</option>
                        <option value="stop_loss">Stop Loss Hit</option>
                        <option value="manual">Manual Exit</option>
                        <option value="trailing_sl">Trailing SL Hit</option>
                    </select>
                </div>
                <button class="full-btn danger" onclick="exitPosition()">Exit Position</button>
            </div>

            <div id="existingCode" class="tab-content">
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Strategy Code</label>
                    <textarea id="strategyCode" placeholder="Enter your trading strategy code here..."></textarea>
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Current Code Preview</label>
                    <div class="code-display" id="currentCodeDisplay">
                        <div class="code-line">// Sample Trading Strategy</div>
                        <div class="code-line">if (rsi &lt; 30 &amp;&amp; macd_signal &gt; 0) {</div>
                        <div class="code-line">   entryPrice = currentPrice;</div>
                        <div class="code-line">   stopLoss = entryPrice * 0.98;</div>
                        <div class="code-line">   target = entryPrice * 1.02;</div>
                        <div class="code-line">}</div>
                    </div>
                </div>
                <div style="display:flex;gap:10px">
                    <button class="full-btn info" onclick="saveStrategyCode()">Save Code</button>
                    <button class="full-btn" onclick="testStrategyCode()" style="background:#ff9900">Test Code</button>
                </div>
            </div>

            <div id="settings" class="tab-content">
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Alert Price</label>
                    <input id="alertPrice" type="number" placeholder="Alert Price">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Auto Square Off Time</label>
                    <input id="autoSquareOff" type="time" value="15:15">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Max Loss Amount</label>
                    <input id="maxLoss" type="number" placeholder="Maximum Loss Amount">
                </div>
                <button class="full-btn info" onclick="saveSettings()">Save Settings</button>
            </div>

            <div id="partition" class="tab-content">
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Partition Square Off Qty</label>
                    <input id="actionPartitionSquareOffQty" type="number" placeholder="Quantity">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Partition Square Off Price</label>
                    <input id="actionPartitionSquareOffPrice" type="number" placeholder="Price">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Add Quantity</label>
                    <input id="actionAddQty" type="number" placeholder="Quantity">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Add Qty Price</label>
                    <input id="actionAddQtyPrice" type="number" placeholder="Price">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;margin-bottom:8px;font-size:14px;color:#aaa">Partition Action</label>
                    <select id="partitionAction">
                        <option value="square_off">Square Off Partition</option>
                        <option value="add_qty">Add Quantity</option>
                        <option value="both">Both</option>
                    </select>
                </div>
                <button class="full-btn success" onclick="executePartitionAction()">Execute Partition</button>
            </div>
        </div>
    </div>

    <!-- ===== SCREENER POPUP MODAL ===== -->
    <div id="screenerPopupModal" class="modal" onclick="closeScreenerPopup(event)">
        <div class="modal-box" style="width: 600px;">
            <div class="modal-header">
                <h3><i class="fas fa-search"></i> Stock Screener</h3>
                <button onclick="closeScreenerPopup()">&#x2716;</button>
            </div>

            <div style="display: flex; gap: 10px; margin: 15px 0;">
                <button onclick="openChartink()" style="flex:1; padding:12px; background:#ff9900; border:none; color:#fff; border-radius:5px; cursor:pointer; font-weight:bold;">
                    <i class="fas fa-external-link-alt"></i> Open Chartink
                </button>
            </div>

            <div style="background: #333; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <h4 style="color: var(--accent-color); margin-bottom: 10px;">
                    <i class="fas fa-sliders-h"></i> Indicator Based Screener
                </h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <select id="indicatorSelect" style="padding:8px; background:#444; color:#fff; border:none; border-radius:5px;">
                        <option>Select Indicator</option>
                        <option>RSI (Relative Strength Index)</option>
                        <option>MACD (Moving Average Convergence Divergence)</option>
                        <option>Bollinger Bands</option>
                        <option>Moving Averages</option>
                        <option>Stochastic Oscillator</option>
                    </select>
                    <input id="indicatorValue" type="number" placeholder="Value" style="padding:8px; background:#444; color:#fff; border:none; border-radius:5px;">
                </div>
                <button onclick="deployIndicatorScreener()" style="margin-top:10px; padding:8px 15px; background:#00aa66; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                    <i class="fas fa-play"></i> Deploy Screener
                </button>
            </div>

            <div style="background: #333; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <h4 style="color: var(--accent-color); margin-bottom: 10px;">
                    <i class="fas fa-save"></i> Saved Screeners
                </h4>
                <div id="savedScreenersList" style="margin-bottom:10px;">
                    <div style="padding:8px; background:#444; margin:5px 0; border-radius:3px; cursor:pointer;">
                        <i class="fas fa-chart-line"></i> RSI Oversold Strategy
                    </div>
                    <div style="padding:8px; background:#444; margin:5px 0; border-radius:3px; cursor:pointer;">
                        <i class="fas fa-chart-line"></i> MACD Crossover Strategy
                    </div>
                </div>
                <button onclick="deploySavedScreener()" style="margin-top:5px; padding:8px 15px; background:#0077ff; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                    <i class="fas fa-play"></i> Deploy Saved Screener
                </button>
            </div>

            <div style="display: flex; gap: 10px; margin-top: 15px;">
                <button onclick="createNewScreener()" style="flex:1; padding:10px; background:#9d4edd; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                    <i class="fas fa-plus"></i> Create New Screener
                </button>
            </div>
        </div>
    </div>

    <!-- ===== STRATEGY CREATION POPUP ===== -->
    <div id="strategyCreationPopup" class="modal" onclick="closeStrategyPopup(event)">
        <div class="modal-box" style="width: 600px;">
            <div class="modal-header">
                <h3><i class="fas fa-chess-board"></i> Strategy Creation</h3>
                <button onclick="closeStrategyPopup()">&#x2716;</button>
            </div>

            <div style="text-align: center; padding: 20px 0;">
                <h4 style="color: var(--accent-color); margin-bottom: 20px;">Select Strategy Platform</h4>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                    <button onclick="openOpstra()" style="padding:15px; background:linear-gradient(135deg, #0077ff, #0055cc); border:none; color:#fff; border-radius:10px; cursor:pointer;">
                        <i class="fas fa-chart-pie"></i><br>
                        <strong>Opstra</strong><br>
                        <small>Options Strategy</small>
                    </button>

                    <button onclick="openSensibull()" style="padding:15px; background:linear-gradient(135deg, #00aa66, #008800); border:none; color:#fff; border-radius:10px; cursor:pointer;">
                        <i class="fas fa-bullhorn"></i><br>
                        <strong>Sensibull</strong><br>
                        <small>Options Trading</small>
                    </button>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <button onclick="openMarketPlace()" style="padding:15px; background:linear-gradient(135deg, #ff9900, #cc7700); border:none; color:#fff; border-radius:10px; cursor:pointer;">
                        <i class="fas fa-store"></i><br>
                        <strong>Market Place</strong><br>
                        <small>Strategy Marketplace</small>
                    </button>

                    <button onclick="openCreateStrategy()" style="padding:15px; background:linear-gradient(135deg, #9d4edd, #7b2cbf); border:none; color:#fff; border-radius:10px; cursor:pointer;">
                        <i class="fas fa-plus-circle"></i><br>
                        <strong>Create Strategy</strong><br>
                        <small>Custom Strategy Builder</small>
                    </button>
                </div>
            </div>

            <div style="background: #333; padding: 15px; border-radius: 5px; margin-top: 15px;">
                <h5 style="color: #aaa; margin-bottom: 10px;">Quick Actions:</h5>
                <div style="display: flex; gap: 10px;">
                    <button onclick="backtestStrategy()" style="flex:1; padding:8px; background:#0077ff; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                        <i class="fas fa-history"></i> Backtest
                    </button>
                    <button onclick="optimizeStrategy()" style="flex:1; padding:8px; background:#00aa66; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                        <i class="fas fa-cogs"></i> Optimize
                    </button>
                    <button onclick="shareStrategy()" style="flex:1; padding:8px; background:#9d4edd; border:none; color:#fff; border-radius:5px; cursor:pointer;">
                        <i class="fas fa-share"></i> Share
                    </button>
                </div>
            </div>
        </div>
    </div>
'''

    html += modals_html

    # Now add the JavaScript - read from source but fix truncations
    html += '\n    ' + js_section + '\n'

    html += '</body>\n</html>\n'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Generated {output_file}")
    print(f"File size: {len(html)} characters")


if __name__ == '__main__':
    build_proper_html(
        '/var/lib/freelancer/projects/40172829/kome-design-clean.txt',
        '/var/lib/freelancer/projects/40172829/web_app/templates/index.html'
    )
