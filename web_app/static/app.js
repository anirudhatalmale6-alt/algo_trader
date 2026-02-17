// ===== GLOBAL VARIABLES =====
let positions = [];
let watchlistStocks = [];
let currentPositionIndex = -1;
let navPopupTimeout = null;
let positionSectionCollapsed = false;
let partitionSectionCollapsed = false;
let enableOptions = {
    positionSettings: true,
    partitionSettings: true,
    trailingSL: true,
    profitLock: false
};

// Stock database for search (50 stocks)
const stockDatabase = [
    { symbol: "RELIANCE", name: "Reliance Industries Ltd", exchange: "NSE", sector: "Oil & Gas" },
    { symbol: "TCS", name: "Tata Consultancy Services", exchange: "NSE", sector: "IT" },
    { symbol: "INFY", name: "Infosys Limited", exchange: "NSE", sector: "IT" },
    { symbol: "HDFCBANK", name: "HDFC Bank Limited", exchange: "NSE", sector: "Banking" },
    { symbol: "ICICIBANK", name: "ICICI Bank Limited", exchange: "NSE", sector: "Banking" },
    { symbol: "HINDUNILVR", name: "Hindustan Unilever Ltd", exchange: "NSE", sector: "FMCG" },
    { symbol: "SBIN", name: "State Bank of India", exchange: "NSE", sector: "Banking" },
    { symbol: "BHARTIARTL", name: "Bharti Airtel Ltd", exchange: "NSE", sector: "Telecom" },
    { symbol: "ITC", name: "ITC Limited", exchange: "NSE", sector: "FMCG" },
    { symbol: "LT", name: "Larsen & Toubro Ltd", exchange: "NSE", sector: "Construction" },
    { symbol: "KOTAKBANK", name: "Kotak Mahindra Bank", exchange: "NSE", sector: "Banking" },
    { symbol: "AXISBANK", name: "Axis Bank Limited", exchange: "NSE", sector: "Banking" },
    { symbol: "WIPRO", name: "Wipro Limited", exchange: "NSE", sector: "IT" },
    { symbol: "SUNPHARMA", name: "Sun Pharmaceutical", exchange: "NSE", sector: "Pharma" },
    { symbol: "TITAN", name: "Titan Company Ltd", exchange: "NSE", sector: "Consumer Goods" },
    { symbol: "TATAMOTORS", name: "Tata Motors Ltd", exchange: "NSE", sector: "Automobile" },
    { symbol: "BAJFINANCE", name: "Bajaj Finance Ltd", exchange: "NSE", sector: "Finance" },
    { symbol: "HCLTECH", name: "HCL Technologies", exchange: "NSE", sector: "IT" },
    { symbol: "ASIANPAINT", name: "Asian Paints Ltd", exchange: "NSE", sector: "Paints" },
    { symbol: "MARUTI", name: "Maruti Suzuki India", exchange: "NSE", sector: "Automobile" },
    { symbol: "ONGC", name: "Oil & Natural Gas Corp", exchange: "NSE", sector: "Oil & Gas" },
    { symbol: "NTPC", name: "NTPC Limited", exchange: "NSE", sector: "Power" },
    { symbol: "POWERGRID", name: "Power Grid Corp", exchange: "NSE", sector: "Power" },
    { symbol: "TATASTEEL", name: "Tata Steel Ltd", exchange: "NSE", sector: "Metal" },
    { symbol: "JSWSTEEL", name: "JSW Steel Ltd", exchange: "NSE", sector: "Metal" },
    { symbol: "ULTRACEMCO", name: "UltraTech Cement Ltd", exchange: "NSE", sector: "Cement" },
    { symbol: "ADANIENT", name: "Adani Enterprises Ltd", exchange: "NSE", sector: "Conglomerate" },
    { symbol: "ADANIPORTS", name: "Adani Ports & SEZ", exchange: "NSE", sector: "Infrastructure" },
    { symbol: "TECHM", name: "Tech Mahindra Ltd", exchange: "NSE", sector: "IT" },
    { symbol: "NESTLEIND", name: "Nestle India Ltd", exchange: "NSE", sector: "FMCG" },
    { symbol: "BAJAJFINSV", name: "Bajaj Finserv Ltd", exchange: "NSE", sector: "Finance" },
    { symbol: "DRREDDY", name: "Dr Reddy's Laboratories", exchange: "NSE", sector: "Pharma" },
    { symbol: "CIPLA", name: "Cipla Limited", exchange: "NSE", sector: "Pharma" },
    { symbol: "DIVISLAB", name: "Divi's Laboratories", exchange: "NSE", sector: "Pharma" },
    { symbol: "APOLLOHOSP", name: "Apollo Hospitals", exchange: "NSE", sector: "Healthcare" },
    { symbol: "EICHERMOT", name: "Eicher Motors Ltd", exchange: "NSE", sector: "Automobile" },
    { symbol: "COALINDIA", name: "Coal India Limited", exchange: "NSE", sector: "Mining" },
    { symbol: "BPCL", name: "Bharat Petroleum Corp", exchange: "NSE", sector: "Oil & Gas" },
    { symbol: "IOC", name: "Indian Oil Corporation", exchange: "NSE", sector: "Oil & Gas" },
    { symbol: "GRASIM", name: "Grasim Industries Ltd", exchange: "NSE", sector: "Cement" },
    { symbol: "BRITANNIA", name: "Britannia Industries", exchange: "NSE", sector: "FMCG" },
    { symbol: "HEROMOTOCO", name: "Hero MotoCorp Ltd", exchange: "NSE", sector: "Automobile" },
    { symbol: "PIDILITIND", name: "Pidilite Industries", exchange: "NSE", sector: "Chemicals" },
    { symbol: "SHREECEM", name: "Shree Cement Ltd", exchange: "NSE", sector: "Cement" },
    { symbol: "DABUR", name: "Dabur India Ltd", exchange: "NSE", sector: "FMCG" },
    { symbol: "HAVELLS", name: "Havells India Ltd", exchange: "NSE", sector: "Electricals" },
    { symbol: "VEDL", name: "Vedanta Limited", exchange: "NSE", sector: "Metal" },
    { symbol: "TATAPOWER", name: "Tata Power Company", exchange: "NSE", sector: "Power" },
    { symbol: "BANKBARODA", name: "Bank of Baroda", exchange: "NSE", sector: "Banking" },
    { symbol: "INDUSINDBK", name: "IndusInd Bank Ltd", exchange: "NSE", sector: "Banking" },
    // ===== FUTURES =====
    { symbol: "NIFTY FUT", name: "NIFTY 27 MAR FUT", exchange: "NFO", sector: "Index Futures" },
    { symbol: "BANKNIFTY FUT", name: "BANKNIFTY 27 MAR FUT", exchange: "NFO", sector: "Index Futures" },
    { symbol: "FINNIFTY FUT", name: "FINNIFTY 27 MAR FUT", exchange: "NFO", sector: "Index Futures" },
    { symbol: "MIDCPNIFTY FUT", name: "MIDCPNIFTY 27 MAR FUT", exchange: "NFO", sector: "Index Futures" },
    { symbol: "RELIANCE FUT", name: "RELIANCE 27 MAR FUT", exchange: "NFO", sector: "Stock Futures" },
    { symbol: "TCS FUT", name: "TCS 27 MAR FUT", exchange: "NFO", sector: "Stock Futures" },
    { symbol: "INFY FUT", name: "INFY 27 MAR FUT", exchange: "NFO", sector: "Stock Futures" },
    { symbol: "HDFCBANK FUT", name: "HDFCBANK 27 MAR FUT", exchange: "NFO", sector: "Stock Futures" },
    { symbol: "SBIN FUT", name: "SBIN 27 MAR FUT", exchange: "NFO", sector: "Stock Futures" },
    { symbol: "TATAMOTORS FUT", name: "TATAMOTORS 27 MAR FUT", exchange: "NFO", sector: "Stock Futures" },
    { symbol: "BAJFINANCE FUT", name: "BAJFINANCE 27 MAR FUT", exchange: "NFO", sector: "Stock Futures" },
    { symbol: "ITC FUT", name: "ITC 27 MAR FUT", exchange: "NFO", sector: "Stock Futures" },
    // ===== NIFTY OPTIONS =====
    { symbol: "NIFTY 22000 CE", name: "NIFTY 27 MAR 22000 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22000 PE", name: "NIFTY 27 MAR 22000 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22100 CE", name: "NIFTY 27 MAR 22100 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22100 PE", name: "NIFTY 27 MAR 22100 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22200 CE", name: "NIFTY 27 MAR 22200 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22200 PE", name: "NIFTY 27 MAR 22200 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22300 CE", name: "NIFTY 27 MAR 22300 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22300 PE", name: "NIFTY 27 MAR 22300 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22400 CE", name: "NIFTY 27 MAR 22400 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22400 PE", name: "NIFTY 27 MAR 22400 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22500 CE", name: "NIFTY 27 MAR 22500 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22500 PE", name: "NIFTY 27 MAR 22500 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22600 CE", name: "NIFTY 27 MAR 22600 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22600 PE", name: "NIFTY 27 MAR 22600 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22700 CE", name: "NIFTY 27 MAR 22700 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22700 PE", name: "NIFTY 27 MAR 22700 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22800 CE", name: "NIFTY 27 MAR 22800 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22800 PE", name: "NIFTY 27 MAR 22800 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22900 CE", name: "NIFTY 27 MAR 22900 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 22900 PE", name: "NIFTY 27 MAR 22900 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 23000 CE", name: "NIFTY 27 MAR 23000 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "NIFTY 23000 PE", name: "NIFTY 27 MAR 23000 PE", exchange: "NFO", sector: "Index Options" },
    // ===== BANKNIFTY OPTIONS =====
    { symbol: "BANKNIFTY 47000 CE", name: "BANKNIFTY 27 MAR 47000 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "BANKNIFTY 47000 PE", name: "BANKNIFTY 27 MAR 47000 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "BANKNIFTY 47500 CE", name: "BANKNIFTY 27 MAR 47500 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "BANKNIFTY 47500 PE", name: "BANKNIFTY 27 MAR 47500 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "BANKNIFTY 48000 CE", name: "BANKNIFTY 27 MAR 48000 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "BANKNIFTY 48000 PE", name: "BANKNIFTY 27 MAR 48000 PE", exchange: "NFO", sector: "Index Options" },
    { symbol: "BANKNIFTY 48500 CE", name: "BANKNIFTY 27 MAR 48500 CE", exchange: "NFO", sector: "Index Options" },
    { symbol: "BANKNIFTY 48500 PE", name: "BANKNIFTY 27 MAR 48500 PE", exchange: "NFO", sector: "Index Options" },
    // ===== STOCK OPTIONS =====
    { symbol: "RELIANCE 3000 CE", name: "RELIANCE 27 MAR 3000 CE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "RELIANCE 3000 PE", name: "RELIANCE 27 MAR 3000 PE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "RELIANCE 2900 CE", name: "RELIANCE 27 MAR 2900 CE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "RELIANCE 2900 PE", name: "RELIANCE 27 MAR 2900 PE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "HDFCBANK 1650 CE", name: "HDFCBANK 27 MAR 1650 CE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "HDFCBANK 1650 PE", name: "HDFCBANK 27 MAR 1650 PE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "TCS 3800 CE", name: "TCS 27 MAR 3800 CE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "TCS 3800 PE", name: "TCS 27 MAR 3800 PE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "INFY 1550 CE", name: "INFY 27 MAR 1550 CE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "INFY 1550 PE", name: "INFY 27 MAR 1550 PE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "SBIN 630 CE", name: "SBIN 27 MAR 630 CE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "SBIN 630 PE", name: "SBIN 27 MAR 630 PE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "TATAMOTORS 750 CE", name: "TATAMOTORS 27 MAR 750 CE", exchange: "NFO", sector: "Stock Options" },
    { symbol: "TATAMOTORS 750 PE", name: "TATAMOTORS 27 MAR 750 PE", exchange: "NFO", sector: "Stock Options" }
];

// Simulated price data for watchlist stocks
const stockPrices = {};
function initStockPrices() {
    const basePrices = {
        RELIANCE: 2985.60, TCS: 3845.25, INFY: 1560.80, HDFCBANK: 1645.90,
        ICICIBANK: 1085.40, HINDUNILVR: 2540.75, SBIN: 628.30, BHARTIARTL: 1425.60,
        ITC: 445.20, LT: 3520.80, KOTAKBANK: 1780.50, AXISBANK: 1125.40,
        WIPRO: 485.30, SUNPHARMA: 1245.60, TITAN: 3280.90, TATAMOTORS: 745.30,
        BAJFINANCE: 6980.40, HCLTECH: 1580.25, ASIANPAINT: 2845.60, MARUTI: 10520.30,
        ONGC: 265.40, NTPC: 345.80, POWERGRID: 285.60, TATASTEEL: 142.30,
        JSWSTEEL: 865.40, ULTRACEMCO: 9845.20, ADANIENT: 2680.50, ADANIPORTS: 1245.30,
        TECHM: 1320.60, NESTLEIND: 2480.90, BAJAJFINSV: 1645.80, DRREDDY: 5480.30,
        CIPLA: 1425.60, DIVISLAB: 3680.40, APOLLOHOSP: 5845.20, EICHERMOT: 4520.80,
        COALINDIA: 385.40, BPCL: 545.60, IOC: 142.80, GRASIM: 2280.40,
        BRITANNIA: 4980.30, HEROMOTOCO: 4245.60, PIDILITIND: 2680.40, SHREECEM: 25480.60,
        DABUR: 545.80, HAVELLS: 1480.30, VEDL: 285.40, TATAPOWER: 385.60,
        BANKBARODA: 245.80, INDUSINDBK: 1045.30,
        // Futures
        "NIFTY FUT": 22465.50, "BANKNIFTY FUT": 47580.25, "FINNIFTY FUT": 21250.40,
        "MIDCPNIFTY FUT": 9845.30, "RELIANCE FUT": 2990.80, "TCS FUT": 3852.40,
        "INFY FUT": 1565.20, "HDFCBANK FUT": 1650.60, "SBIN FUT": 630.80,
        "TATAMOTORS FUT": 748.50, "BAJFINANCE FUT": 6995.30, "ITC FUT": 447.60,
        // NIFTY Options
        "NIFTY 22000 CE": 485.30, "NIFTY 22000 PE": 35.20,
        "NIFTY 22100 CE": 395.40, "NIFTY 22100 PE": 48.60,
        "NIFTY 22200 CE": 310.80, "NIFTY 22200 PE": 65.40,
        "NIFTY 22300 CE": 235.60, "NIFTY 22300 PE": 88.20,
        "NIFTY 22400 CE": 168.40, "NIFTY 22400 PE": 118.50,
        "NIFTY 22500 CE": 112.80, "NIFTY 22500 PE": 158.30,
        "NIFTY 22600 CE": 72.40, "NIFTY 22600 PE": 210.60,
        "NIFTY 22700 CE": 42.80, "NIFTY 22700 PE": 275.40,
        "NIFTY 22800 CE": 22.60, "NIFTY 22800 PE": 348.20,
        "NIFTY 22900 CE": 11.40, "NIFTY 22900 PE": 430.80,
        "NIFTY 23000 CE": 5.80, "NIFTY 23000 PE": 520.40,
        // BANKNIFTY Options
        "BANKNIFTY 47000 CE": 680.50, "BANKNIFTY 47000 PE": 125.30,
        "BANKNIFTY 47500 CE": 345.80, "BANKNIFTY 47500 PE": 280.60,
        "BANKNIFTY 48000 CE": 142.30, "BANKNIFTY 48000 PE": 520.40,
        "BANKNIFTY 48500 CE": 48.60, "BANKNIFTY 48500 PE": 845.20,
        // Stock Options
        "RELIANCE 3000 CE": 65.40, "RELIANCE 3000 PE": 78.20,
        "RELIANCE 2900 CE": 125.80, "RELIANCE 2900 PE": 38.40,
        "HDFCBANK 1650 CE": 42.60, "HDFCBANK 1650 PE": 45.80,
        "TCS 3800 CE": 85.40, "TCS 3800 PE": 38.20,
        "INFY 1550 CE": 35.60, "INFY 1550 PE": 22.80,
        "SBIN 630 CE": 18.40, "SBIN 630 PE": 16.50,
        "TATAMOTORS 750 CE": 22.80, "TATAMOTORS 750 PE": 25.40
    };
    stockDatabase.forEach(stock => {
        const base = basePrices[stock.symbol] || (Math.random() * 3000 + 100);
        const changeAmt = (Math.random() - 0.45) * base * 0.03;
        stockPrices[stock.symbol] = {
            price: base,
            change: parseFloat(changeAmt.toFixed(2)),
            changePct: parseFloat(((changeAmt / base) * 100).toFixed(2))
        };
    });
}
initStockPrices();

// Watchlist pagination
let wlCurrentPage = 1;
const WL_PER_PAGE = 10;
let wlActiveTab = 'watchlist';

// Broker instruments (loaded from API after broker connection)
let brokerInstruments = [];
let instrumentsLoaded = false;
let instrumentsLoading = false;

// Fetch instruments from broker API (just triggers server-side download, doesn't load all to browser)
function fetchBrokerInstruments() {
    if (instrumentsLoading) return;
    instrumentsLoading = true;

    // Just trigger the server to download & cache instrument lists
    // We don't load 50k+ instruments into browser memory
    // Instead, search API will be used for lookups
    fetch('/api/instruments?exchanges=NSE,NFO')
        .then(r => r.json())
        .then(data => {
            if (data.success && data.count > 0) {
                instrumentsLoaded = true;
                console.log(`Server loaded ${data.count} instruments from broker (search via API)`);
            } else {
                console.log('No broker instruments available, using local database');
            }
            instrumentsLoading = false;
            updateWlCount();
        })
        .catch(err => {
            console.log('Instrument fetch error (using local database):', err);
            instrumentsLoading = false;
            updateWlCount();
        });
}

// Local search fallback (when broker instruments not loaded)
function searchInstrumentsLocal(query) {
    query = query.toUpperCase();
    let results = [];
    for (let i = 0; i < stockDatabase.length && results.length < 15; i++) {
        const s = stockDatabase[i];
        if (s.symbol.includes(query) || s.name.toUpperCase().includes(query)) {
            results.push({
                symbol: s.symbol,
                name: s.name,
                exchange: s.exchange,
                token: 0
            });
        }
    }
    return results.filter(r => !watchlistStocks.includes(r.symbol));
}

// ===== MARKET TICKER DATA WITH INDICES =====
let tickerData = [
    { symbol: "NIFTY", price: 22450.75, change: 125.50, name: "NIFTY 50" },
    { symbol: "BANKNIFTY", price: 47520.30, change: 320.75, name: "NIFTY BANK" },
    { symbol: "SENSEX", price: 73845.25, change: 280.40, name: "S&P BSE SENSEX" },
    { symbol: "INDIAVIX", price: 13.25, change: -0.45, name: "INDIA VIX" },
    { symbol: "RELIANCE", price: 2985.60, change: 12.50, name: "Reliance Industries" },
    { symbol: "TCS", price: 3845.25, change: -24.50, name: "Tata Consultancy Services" },
    { symbol: "INFY", price: 1560.80, change: 8.20, name: "Infosys Limited" },
    { symbol: "HDFCBANK", price: 1645.90, change: -5.30, name: "HDFC Bank" }
];


// ===== LIVE CLOCK =====
function updateClock() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-IN', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('digitalClock').textContent = timeString;
}


// ===== NAVIGATION POPUP FUNCTIONS =====
function showNavPopup() {
    clearTimeout(navPopupTimeout);
    document.getElementById('navPopup').classList.add('show');
}

function hideNavPopup() {
    navPopupTimeout = setTimeout(() => {
        document.getElementById('navPopup').classList.remove('show');
    }, 300);
}


// Keep popup open when hovering over it
document.getElementById('navPopup').addEventListener('mouseenter', () => {
    clearTimeout(navPopupTimeout);
});

// ===== MARKET TICKER FUNCTIONS =====
function populateMarketTicker() {
    const ticker = document.getElementById('marketTicker');
    ticker.innerHTML = '';

    // Duplicate data for seamless scrolling
    const duplicateData = [...tickerData, ...tickerData];

    duplicateData.forEach((stock, index) => {
        const changeClass = stock.change >= 0 ? 'positive' : 'negative';
        const changeSign = stock.change >= 0 ? '+' : '';

        const tickerItem = document.createElement('div');
        tickerItem.className = 'ticker-item-horizontal';
        tickerItem.dataset.symbol = stock.symbol;
        tickerItem.dataset.index = index % tickerData.length;
        tickerItem.innerHTML = `
            <span class="ticker-symbol">${stock.symbol}</span>
            <span class="ticker-price">${stock.price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
            <span class="ticker-change ${changeClass}">${changeSign}${stock.change.toFixed(2)}</span>
        `;
        ticker.appendChild(tickerItem);
    });
}

// ===== WATCHLIST FUNCTIONS =====
function loadWatchlist() {
    const savedWatchlist = localStorage.getItem('mukeshAlgoWatchlist');
    if (savedWatchlist) {
        watchlistStocks = JSON.parse(savedWatchlist);
    } else {
        watchlistStocks = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC", "BHARTIARTL", "WIPRO", "TITAN"];
        saveWatchlist();
    }
    wlCurrentPage = 1;
    renderWatchlist();
    initWatchlistSearch();
}

function saveWatchlist() {
    localStorage.setItem('mukeshAlgoWatchlist', JSON.stringify(watchlistStocks));
}

function addToWatchlistBySymbol(symbol) {
    if (watchlistStocks.includes(symbol)) return;
    if (watchlistStocks.length >= 50) {
        alert("Maximum 50 stocks allowed in watchlist!");
        return;
    }
    watchlistStocks.push(symbol);
    saveWatchlist();
    renderWatchlist();
}

function removeFromWatchlist(symbol) {
    const index = watchlistStocks.indexOf(symbol);
    if (index !== -1) {
        watchlistStocks.splice(index, 1);
        saveWatchlist();
        renderWatchlist();
    }
}

function clearWatchlist() {
    if (watchlistStocks.length > 0 && confirm("Clear all stocks from watchlist?")) {
        watchlistStocks = [];
        saveWatchlist();
        renderWatchlist();
    }
}

function updateWlCount() {
    const countEl = document.getElementById('wlCount');
    if (countEl) countEl.textContent = watchlistStocks.length + '/50';
}

function renderWatchlist() {
    const watchlistDiv = document.getElementById('watchlistStocks');
    updateWlCount();

    if (watchlistStocks.length === 0) {
        watchlistDiv.innerHTML = '<div class="wl-empty">No stocks in watchlist.<br>Search and add stocks above.</div>';
        renderWlPagination();
        return;
    }

    const totalPages = Math.ceil(watchlistStocks.length / WL_PER_PAGE);
    if (wlCurrentPage > totalPages) wlCurrentPage = totalPages;
    const startIdx = (wlCurrentPage - 1) * WL_PER_PAGE;
    const pageStocks = watchlistStocks.slice(startIdx, startIdx + WL_PER_PAGE);

    let html = '';
    pageStocks.forEach(symbol => {
        // Look up from local database, determine exchange from symbol pattern
        let stockInfo = stockDatabase.find(s => s.symbol === symbol);
        if (!stockInfo) {
            // Auto-detect exchange for broker instruments (F&O symbols from Alice Blue)
            let exchange = 'NSE';
            if (symbol.match(/\d{2}[A-Z]{3}\d{2}[CP]\d+/) || symbol.includes('FUT') ||
                symbol.match(/\d+CE$/) || symbol.match(/\d+PE$/)) {
                exchange = 'NFO';
            }
            stockInfo = { name: symbol, exchange: exchange, sector: '' };
        }
        const priceData = stockPrices[symbol] || { price: 0, change: 0, changePct: 0 };
        const changeClass = priceData.change > 0 ? 'wl-positive' : priceData.change < 0 ? 'wl-negative' : 'wl-neutral';
        const changeSign = priceData.change > 0 ? '+' : '';

        html += `
        <div class="wl-item ${changeClass}" data-symbol="${symbol}">
            <div class="wl-item-left">
                <div class="wl-item-symbol">
                    ${symbol}
                    <span class="wl-item-exchange exchange-${stockInfo.exchange.toLowerCase()}">${stockInfo.exchange}</span>
                </div>
                <div class="wl-item-name">${stockInfo.name}</div>
            </div>
            <div class="wl-item-right">
                <div class="wl-item-price">${priceData.price.toFixed(2)}</div>
                <div class="wl-item-change">
                    <span class="change-abs">${changeSign}${priceData.change.toFixed(2)}</span>
                    <span class="change-pct">(${changeSign}${priceData.changePct.toFixed(2)}%)</span>
                </div>
            </div>
            <div class="wl-item-actions">
                <button class="wl-action-buy" onclick="event.stopPropagation(); openAddPositionModalForSymbol('${symbol}', 'BUY')">B</button>
                <button class="wl-action-sell" onclick="event.stopPropagation(); openAddPositionModalForSymbol('${symbol}', 'SELL')">S</button>
                <button class="wl-action-more" onclick="event.stopPropagation(); openChart('${symbol}')" title="Chart"><i class="fas fa-chart-line"></i></button>
                <button class="wl-action-delete" onclick="event.stopPropagation(); removeFromWatchlist('${symbol}')" title="Remove"><i class="fas fa-times"></i></button>
            </div>
        </div>`;
    });

    watchlistDiv.innerHTML = html;
    renderWlPagination();
}

function renderWlPagination() {
    const paginationDiv = document.getElementById('wlPagination');
    if (!paginationDiv) return;
    const totalPages = Math.ceil(watchlistStocks.length / WL_PER_PAGE);
    if (totalPages <= 1) {
        paginationDiv.innerHTML = '';
        return;
    }
    let html = '';
    for (let i = 1; i <= totalPages; i++) {
        html += `<button class="wl-page-btn ${i === wlCurrentPage ? 'active' : ''}" onclick="goToWlPage(${i})">${i}</button>`;
    }
    paginationDiv.innerHTML = html;
}

function goToWlPage(page) {
    wlCurrentPage = page;
    renderWatchlist();
}

function switchWatchlistTab(tab) {
    wlActiveTab = tab;
    document.querySelectorAll('.wl-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.wl-tab[data-tab="${tab}"]`).classList.add('active');

    if (tab === 'watchlist') {
        renderWatchlist();
    } else if (tab === 'predefined') {
        document.getElementById('watchlistStocks').innerHTML = '<div class="wl-empty">Predefined watchlists will be available after broker login.</div>';
        document.getElementById('wlPagination').innerHTML = '';
    } else if (tab === 'optionchain') {
        document.getElementById('watchlistStocks').innerHTML = '<div class="wl-empty">Option Chain view will be available after broker login.</div>';
        document.getElementById('wlPagination').innerHTML = '';
    }
}

function toggleWatchlistSettings() {
    if (confirm("Clear all stocks from watchlist?")) {
        clearWatchlist();
    }
}

// Watchlist search autocomplete
function initWatchlistSearch() {
    const searchInput = document.getElementById('watchlistSearch');
    const resultsDiv = document.getElementById('wlSearchResults');
    if (!searchInput || !resultsDiv) return;

    let searchTimeout = null;
    searchInput.addEventListener('input', function() {
        const query = this.value.trim();
        if (query.length < 2) {
            resultsDiv.style.display = 'none';
            return;
        }

        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            if (instrumentsLoaded) {
                // Server-side search (broker instruments loaded on server)
                fetch('/api/instruments/search?q=' + encodeURIComponent(query))
                    .then(r => r.json())
                    .then(data => {
                        if (data.success && data.results) {
                            const matches = data.results.filter(s => !watchlistStocks.includes(s.symbol));
                            renderSearchResults(matches, resultsDiv);
                        }
                    })
                    .catch(() => {
                        const matches = searchInstrumentsLocal(query);
                        renderSearchResults(matches, resultsDiv);
                    });
            } else {
                const matches = searchInstrumentsLocal(query);
                renderSearchResults(matches, resultsDiv);
            }
        }, 200);
    });

    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            const query = this.value.trim().toUpperCase();
            // Try adding the first visible search result
            const firstResult = resultsDiv.querySelector('.wl-search-result-item');
            if (firstResult) {
                firstResult.click();
            } else {
                // Fallback to local search
                const matches = searchInstrumentsLocal(query);
                if (matches.length > 0) {
                    addToWatchlistBySymbol(matches[0].symbol);
                    this.value = '';
                    resultsDiv.style.display = 'none';
                }
            }
        }
        if (e.key === 'Escape') {
            resultsDiv.style.display = 'none';
        }
    });

    // Close results when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !resultsDiv.contains(e.target)) {
            resultsDiv.style.display = 'none';
        }
    });
}

function renderSearchResults(matches, resultsDiv) {
    if (matches.length === 0) {
        resultsDiv.innerHTML = '<div style="padding: 10px; color: #666; font-size: 12px; text-align: center;">No results found</div>';
        resultsDiv.style.display = 'block';
        return;
    }
    resultsDiv.innerHTML = matches.map(s => {
        const exchClass = (s.exchange || 'NSE').toLowerCase() === 'nfo' || (s.exchange || '').toLowerCase() === 'bfo' ? 'exchange-nfo' : '';
        // Escape single quotes in symbol for onclick
        const safeSymbol = (s.symbol || '').replace(/'/g, "\\'");
        const expiry = s.expiry ? `<span style="color:#666;font-size:10px;margin-left:4px;">${s.expiry}</span>` : '';
        return `
            <div class="wl-search-result-item" onclick="addToWatchlistFromSearch('${safeSymbol}')">
                <div>
                    <span class="sr-symbol">${s.symbol}</span>
                    <span class="sr-name">${s.name || s.symbol}</span>
                    ${expiry}
                </div>
                <span class="sr-exchange ${exchClass}">${s.exchange || 'NSE'}</span>
            </div>
        `;
    }).join('');
    resultsDiv.style.display = 'block';
}

function addToWatchlistFromSearch(symbol) {
    addToWatchlistBySymbol(symbol);
    document.getElementById('watchlistSearch').value = '';
    document.getElementById('wlSearchResults').style.display = 'none';
}

function refreshWatchlist() {
    // Simulate price updates
    stockDatabase.forEach(stock => {
        if (stockPrices[stock.symbol]) {
            const p = stockPrices[stock.symbol];
            const fluctuation = (Math.random() - 0.5) * p.price * 0.005;
            p.change = parseFloat((p.change + fluctuation).toFixed(2));
            p.changePct = parseFloat(((p.change / p.price) * 100).toFixed(2));
        }
    });
    renderWatchlist();
}

function exportWatchlist() {
    if (watchlistStocks.length === 0) {
        alert("Watchlist is empty!");
        return;
    }
    const csvContent = "data:text/csv;charset=utf-8," + watchlistStocks.join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "watchlist.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function importWatchlist() {
    const symbols = prompt("Enter stock symbols separated by commas (e.g., RELIANCE, TCS, INFY):");
    if (symbols) {
        const symbolList = symbols.split(',').map(s => s.trim().toUpperCase()).filter(s => s.length > 0);
        let addedCount = 0;
        symbolList.forEach(symbol => {
            if (!watchlistStocks.includes(symbol) && watchlistStocks.length < 50) {
                watchlistStocks.push(symbol);
                addedCount++;
            }
        });
        saveWatchlist();
        renderWatchlist();
        alert(`Added ${addedCount} new stocks to watchlist.`);
    }
}

// Keep addMultipleStocks as alias
function addMultipleStocks() { importWatchlist(); }


// ===== ENABLE/DISABLE OPTIONS =====
function toggleEnableOption(option) {
    enableOptions[option] = !enableOptions[option];

    const statusElement = document.getElementById(`${option}Status`);
    const sectionElement = document.getElementById(`${option}Section`);

    if (enableOptions[option]) {
        statusElement.className = 'enable-status enabled';
        statusElement.innerHTML = '<i class="fas fa-check"></i>';

        if (sectionElement) {
            sectionElement.style.display = 'block';
        }

        // Enable specific controls
        if (option === 'trailingSL') {
            document.getElementById('trailingSLRow').style.display = 'flex';
        }
        if (option === 'profitLock') {
            document.getElementById('profitLockRow').style.display = 'flex';
        }
    } else {
        statusElement.className = 'enable-status disabled';
        statusElement.innerHTML = '<i class="fas fa-times"></i>';

        if (sectionElement) {
            sectionElement.style.display = 'none';
        }

        // Disable specific controls
        if (option === 'trailingSL') {
            document.getElementById('trailingSLRow').style.display = 'none';
        }
        if (option === 'profitLock') {
            document.getElementById('profitLockRow').style.display = 'none';
        }
    }

    // Update the enable option UI
    const optionElement = event.target.closest('.enable-option');
    if (optionElement) {
        if (enableOptions[option]) {
            optionElement.classList.add('active');
        } else {
            optionElement.classList.remove('active');
        }
    }
}

// ===== POSITION SECTION TOGGLE FUNCTIONS =====
function togglePositionSection() {
    const sectionBody = document.getElementById('positionSectionBody');
    const toggleBtn = document.getElementById('positionSectionToggle');

    positionSectionCollapsed = !positionSectionCollapsed;

    if (positionSectionCollapsed) {
        sectionBody.classList.add('collapsed');
        toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i> Expand';
    } else {
        sectionBody.classList.remove('collapsed');
        toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i> Collapse';
    }
}


function togglePartitionSection() {
    const sectionBody = document.getElementById('partitionSectionBody');
    const toggleBtn = document.getElementById('partitionSectionToggle');

    partitionSectionCollapsed = !partitionSectionCollapsed;

    if (partitionSectionCollapsed) {
        sectionBody.classList.add('collapsed');
        toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i> Expand';
    } else {
        sectionBody.classList.remove('collapsed');
        toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i> Collapse';
    }
}

// ===== POSITION SETTINGS TOGGLE FUNCTIONS =====
function initializePositionToggles() {
    // Add event listeners to all toggle switches
    const toggles = [
        'toggleOrderType', 'togglePart', 'toggleQty', 'toggleTrailingSL',
        'toggleTarget', 'toggleExit', 'toggleProfitLock', 'toggleProfitGap'
    ];

    toggles.forEach(toggleId => {
        const toggle = document.getElementById(toggleId);
        const controlId = toggleId.replace('toggle', 'position').replace('toggle', '');
        let control;

        if (toggleId === 'toggleOrderType') control = document.getElementById('positionOrderType');
        else if (toggleId === 'togglePart') control = document.getElementById('positionPart');
        else if (toggleId === 'toggleQty') {
            // For quantity, we have two controls
            document.getElementById('positionQty').disabled = !toggle.checked;
            document.getElementById('positionSellQty').disabled = !toggle.checked;
        }
        else if (toggleId === 'toggleTrailingSL') {
            control = document.getElementById('trailingSLValue');
            document.getElementById('trailingSLType').disabled = !toggle.checked;
        }
        else if (toggleId === 'toggleTarget') {
            control = document.getElementById('targetValue');
            document.getElementById('targetType').disabled = !toggle.checked;
        }
        else if (toggleId === 'toggleExit') {
            control = document.getElementById('exitValue');
            document.getElementById('exitType').disabled = !toggle.checked;
        }
        else if (toggleId === 'toggleProfitLock') control = document.getElementById('profitLock');
        else if (toggleId === 'toggleProfitGap') control = document.getElementById('profitGap');

        if (control && control.id !== 'positionQty' && control.id !== 'positionSellQty') {
            control.disabled = !toggle.checked;
        }

        toggle.addEventListener('change', function() {
            const isChecked = this.checked;

            if (toggleId === 'toggleQty') {
                document.getElementById('positionQty').disabled = !isChecked;
                document.getElementById('positionSellQty').disabled = !isChecked;
            }
            else if (toggleId === 'toggleTrailingSL') {
                document.getElementById('trailingSLValue').disabled = !isChecked;
                document.getElementById('trailingSLType').disabled = !isChecked;

                // Show/hide indicator options
                if (isChecked && document.getElementById('trailingSLType').value === 'indicator') {
                    document.getElementById('indicatorOptions').style.display = 'grid';
                    document.getElementById('indicatorPeriod').disabled = false;
                    document.getElementById('indicatorCondition').disabled = false;
                } else {
                    document.getElementById('indicatorOptions').style.display = 'none';
                    document.getElementById('indicatorPeriod').disabled = true;
                    document.getElementById('indicatorCondition').disabled = true;
                }
            }
            else if (toggleId === 'toggleTarget') {
                document.getElementById('targetValue').disabled = !isChecked;
                document.getElementById('targetType').disabled = !isChecked;
            }
            else if (toggleId === 'toggleExit') {
                document.getElementById('exitValue').disabled = !isChecked;
                document.getElementById('exitType').disabled = !isChecked;
            }
            else if (control) {
                control.disabled = !isChecked;
            }
        });
    });

    // Add event listener for trailing SL type change
    document.getElementById('trailingSLType').addEventListener('change', function() {
        const toggleTrailingSL = document.getElementById('toggleTrailingSL');

        if (toggleTrailingSL.checked && this.value === 'indicator') {
            document.getElementById('indicatorOptions').style.display = 'grid';
            document.getElementById('indicatorPeriod').disabled = false;
            document.getElementById('indicatorCondition').disabled = false;
        } else {
            document.getElementById('indicatorOptions').style.display = 'none';
            document.getElementById('indicatorPeriod').disabled = true;
            document.getElementById('indicatorCondition').disabled = true;
        }
    });
}

function toggleAllPositionSettings(state) {
    const toggles = [
        'toggleOrderType', 'togglePart', 'toggleQty', 'toggleTrailingSL',
        'toggleTarget', 'toggleExit', 'toggleProfitLock', 'toggleProfitGap'
    ];

    toggles.forEach(toggleId => {
        const toggle = document.getElementById(toggleId);
        toggle.checked = state;

        // Trigger change event
        const event = new Event('change');
        toggle.dispatchEvent(event);
    });

    // Show success message
    const status = state ? 'enabled' : 'disabled';
    alert(`All position settings ${status}`);
}

function resetPositionSettings() {
    // Reset toggle states
    toggleAllPositionSettings(true);

    // Reset values
    document.getElementById('positionOrderType').value = 'limit';
    document.getElementById('positionPart').value = 'buy';
    document.getElementById('positionQty').value = '10';
    document.getElementById('positionSellQty').value = '0';
    document.getElementById('trailingSLType').value = 'point';
    document.getElementById('trailingSLValue').value = '20';
    document.getElementById('targetType').value = 'point';
    document.getElementById('targetValue').value = '50';
    document.getElementById('exitType').value = 'point';
    document.getElementById('exitValue').value = '30';
    document.getElementById('profitLock').value = '';
    document.getElementById('profitGap').value = '';

    // Reset indicator options
    document.getElementById('indicatorOptions').style.display = 'none';
    document.getElementById('indicatorPeriod').value = '14';
    document.getElementById('indicatorCondition').value = 'close';

    alert('Position settings reset to defaults');
}

// ===== PARTITION & ADD QUANTITY FUNCTIONS =====
function calculatePositionSizing() {
    const entryPrice = parseFloat(document.getElementById('entryPrice').value) || 0;
    const positionQty = parseFloat(document.getElementById('positionQty').value) || 0;
    const positionSellQty = parseFloat(document.getElementById('positionSellQty').value) || 0;
    const partitionSquareOffQty = parseFloat(document.getElementById('partitionSquareOffQty').value) || 0;
    const partitionSquareOffPrice = parseFloat(document.getElementById('partitionSquareOffPrice').value) || 0;
    const addQty = parseFloat(document.getElementById('addQty').value) || 0;
    const addQtyPrice = parseFloat(document.getElementById('addQtyPrice').value) || 0;

    if (!entryPrice) {
        document.getElementById('calculationResult').innerHTML = "Please enter Entry Price to calculate.";
        document.getElementById('calculationResult').style.color = "#ff4444";
        return;
    }

    const totalQty = positionQty + positionSellQty;
    if (totalQty === 0) {
        document.getElementById('calculationResult').innerHTML = "Please enter quantity to calculate.";
        document.getElementById('calculationResult').style.color = "#ff4444";
        return;
    }

    let result = `<strong>Position Calculation:</strong><br>`;
    result += `Total Quantity: ${totalQty}<br>`;
    result += `Entry Price: ₹${entryPrice.toFixed(2)}<br>`;

    let partitionProfit = 0;
    if (partitionSquareOffQty > 0 && partitionSquareOffPrice > 0) {
        partitionProfit = (partitionSquareOffPrice - entryPrice) * partitionSquareOffQty;
        result += `Partition Profit: ₹${partitionProfit.toFixed(2)}<br>`;
    }

    let addQtyCost = 0;
    if (addQty > 0 && addQtyPrice > 0) {
        addQtyCost = addQty * addQtyPrice;
        result += `Add Quantity Cost: ₹${addQtyCost.toFixed(2)}<br>`;
    }

    const totalInvestment = (entryPrice * totalQty) + addQtyCost;
    result += `Total Investment: ₹${totalInvestment.toFixed(2)}<br>`;

    if (partitionProfit > 0) {
        const roi = (partitionProfit / totalInvestment) * 100;
        result += `ROI from Partition: ${roi.toFixed(2)}%`;
    }

    document.getElementById('calculationResult').innerHTML = result;
    document.getElementById('calculationResult').style.color = "#00ff88";
}

// ===== POSITIONS MANAGEMENT =====
function loadPositions() {
    const savedPositions = localStorage.getItem('mukeshAlgoPositions');
    if (savedPositions) {
        positions = JSON.parse(savedPositions);
    } else {
        // Default sample positions
        positions = [
            {
                symbol: "RELIANCE",
                orderType: "BUY",
                orderCondition: "Intraday",
                entryPrice: 2450.50,
                currentPrice: 2465.75,
                buyQty: 10,
                sellQty: 0,
                buyAvgPrice: 2445.00,
                sellAvgPrice: 0,
                source: "LIVE",
                stopLoss: 2400.00,
                target: 2500.00,
                trailingSL: 0,
                entryTime: new Date().toISOString(),
                positionSettings: {
                    orderType: "limit",
                    part: "buy",
                    qty: 10,
                    trailingSL: {
                        type: "point",
                        value: 20
                    },
                    target: {
                        type: "point",
                        value: 50
                    },
                    exit: {
                        type: "point",
                        value: 30
                    },
                    profitLock: 2475,
                    profitGap: 5,
                    partitionSquareOffQty: 2,
                    partitionSquareOffPrice: 2470,
                    addQty: 5,
                    addQtyPrice: 2430
                }
            },
            {
                symbol: "TCS",
                orderType: "SELL",
                orderCondition: "Positional",
                entryPrice: 3850.00,
                currentPrice: 3825.50,
                buyQty: 0,
                sellQty: 5,
                buyAvgPrice: 0,
                sellAvgPrice: 3830.00,
                source: "PAPER",
                stopLoss: 3900.00,
                target: 3800.00,
                trailingSL: 20,
                entryTime: new Date(Date.now() - 86400000).toISOString(),
                positionSettings: {
                    orderType: "market",
                    part: "sell",
                    qty: 5,
                    trailingSL: {
                        type: "price",
                        value: 25
                    },
                    target: {
                        type: "price",
                        value: 3800
                    },
                    exit: {
                        type: "price",
                        value: 3810
                    },
                    profitLock: 3815,
                    profitGap: 10,
                    partitionSquareOffQty: 1,
                    partitionSquareOffPrice: 3815,
                    addQty: 2,
                    addQtyPrice: 3880
                }
            }
        ];
        savePositions();
    }

    renderPositions();
    updatePLSummary();
}

function savePositions() {
    localStorage.setItem('mukeshAlgoPositions', JSON.stringify(positions));
}

function renderPositions() {
    const table = document.getElementById('positionsTable');

    if (positions.length === 0) {
        table.innerHTML = `
           <tr>
             <td colspan="15" style="text-align:center;padding:30px;color:#888;font-size:14px;">
                No open positions. Click "Add Position" to create one.
             </td>
           </tr>
        `;
        return;
    }

    let html = "";
    positions.forEach((p, i) => {
        const buyValue = p.buyAvgPrice * p.buyQty;
        const sellValue = p.sellAvgPrice * p.sellQty;
        const currentValue = p.currentPrice * (p.buyQty - p.sellQty);
        const pl = currentValue - (buyValue - sellValue);
        const plPercent = (pl / (buyValue - sellValue)) * 100;

        let plClass = pl >= 0 ? "pl-positive" : "pl-negative";
        let orderTypeClass = p.orderType === 'BUY' ? 'order-type-buy' : 'order-type-sell';
        let conditionClass = `condition-${p.orderCondition.toLowerCase().replace(/\s+/g, '-')}`;

        // Get position settings info for tooltip
        const posSettings = p.positionSettings || {};
        const posInfo = posSettings.orderType ? `
          <div style="font-size:12px;color:#aaa;margin-top:5px;">
            Type: ${posSettings.orderType.toUpperCase()} |
            Part: ${posSettings.part.toUpperCase()} |
            TSL: ${posSettings.trailingSL?.type || 'N/A'}
          </div>
        ` : '';

        html += `
        <tr>
          <td>${i + 1}</td>
          <td class="symbol-cell">
             ${p.symbol}
             ${posInfo}
             <div class="quick-popup">
               <button class="q-btn buy" onclick="openAddPositionModalForSymbol('${p.symbol}', 'BUY')">BUY</button>
               <button class="q-btn sell" onclick="openAddPositionModalForSymbol('${p.symbol}', 'SELL')">SELL</button>
               <button class="q-btn chart" onclick="openChart('${p.symbol}')">CHART</button>
               <button class="q-btn depth" onclick="openDepth('${p.symbol}')">DEPTH</button>
               <button class="q-btn delete-btn-main" onclick="deletePosition(${i})" title="Delete">DEL</button>
               <div class="q-btn more">MORE
                  <div class="more-menu-main">
                    <div onclick="viewPositionDetails(${i})">View Details</div>
                    <div onclick="modifyPositionSettings(${i})">Modify Settings</div>
                    <div onclick="executePartitionSquareOff(${i})">Partition Square Off</div>
                    <div onclick="executeAddQuantity(${i})">Add Quantity</div>
                    <div onclick="openInfo('${p.symbol}')">INFO</div>
                    <div onclick="openGTT('${p.symbol}')">GTT</div>
                    <div onclick="openOptionChain('${p.symbol}')">OPTION CHAIN</div>
                    <div onclick="setAlert('${p.symbol}')">ALERT</div>
                  </div>
               </div>
             </div>
          </td>
          <td><span class="${orderTypeClass}">${p.orderType}</span></td>
          <td><span class="order-condition ${conditionClass}">${p.orderCondition}</span></td>
          <td>${p.entryPrice.toFixed(2)}</td>
          <td>${p.currentPrice.toFixed(2)}</td>
          <td class="buy-qty">${p.buyQty}</td>
          <td class="sell-qty">${p.sellQty}</td>
          <td>${p.buyAvgPrice ? p.buyAvgPrice.toFixed(2) : '-'}</td>
          <td>${p.sellAvgPrice ? p.sellAvgPrice.toFixed(2) : '-'}</td>
          <td class="${plClass}">${pl >= 0 ? '+' : ''}${pl.toFixed(2)}</td>
          <td class="${plClass}">${pl >= 0 ? '+' : ''}${pl.toFixed(2)}</td>
          <td class="${plClass}">${pl >= 0 ? '+' : ''}${plPercent.toFixed(2)}%</td>
          <td>
             <div class="source-wrap">
                <button class="source-btn">${p.source}</button>
                <div class="source-menu">
                  <div onclick="changeSource(${i}, 'LIVE')">LIVE</div>
                  <div onclick="changeSource(${i}, 'PAPER')">PAPER</div>
                  <div onclick="changeSource(${i}, 'SIMULATOR')">SIMULATOR</div>
                </div>
             </div>
          </td>
          <td><button class="action-btn" onclick="openActionModal('${p.symbol}', ${i})">ACTION</button></td>
        </tr>`;
    });

    table.innerHTML = html;
}


function updatePLSummary() {
    let realizedPL = 1250.50;
    let unrealizedPL = 0;
    let dayPL = 325.75;

    positions.forEach(position => {
        const pl = (position.currentPrice - position.entryPrice) * (position.buyQty - position.sellQty);
        if (position.orderType === 'SELL') {
            unrealizedPL -= pl;
        } else {
            unrealizedPL += pl;
        }
    });

    const netPL = realizedPL + unrealizedPL;

    const plBox = document.getElementById('plBox');
    const formattedPL = netPL >= 0 ?
        `+₹${Math.abs(netPL).toLocaleString('en-IN', {minimumFractionDigits: 2})}` :
        `-₹${Math.abs(netPL).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;

    plBox.textContent = `P/L : ${formattedPL}`;
    plBox.style.color = netPL >= 0 ? 'var(--success-color)' : 'var(--danger-color)';
    plBox.style.background = netPL >= 0 ?
        'linear-gradient(135deg, #0a3d0a 0%, #1a5c1a 100%)' :
        'linear-gradient(135deg, #3d0a0a 0%, #5c1a1a 100%)';
}

function updateCurrentPrices() {
    positions.forEach(position => {
        const changePercent = (Math.random() - 0.5) / 100;
        position.currentPrice = position.currentPrice * (1 + changePercent);
    });

    savePositions();
    renderPositions();
    updatePLSummary();
}

function updateMarketData() {
    // Update ticker data with random changes
    tickerData.forEach(stock => {
        const change = (Math.random() - 0.5) * 10;
        stock.price += change;
        stock.change = change;
    });

    populateMarketTicker();
    updateCurrentPrices();
}

// ===== POSITION MODAL FUNCTIONS =====
function openAddPositionModal() {
    document.getElementById('modalSymbolTitle').textContent = 'Add Position';
    document.getElementById('positionSymbol').value = '';
    document.getElementById('positionSymbol').removeAttribute('readonly');

    // Reset main form
    document.getElementById('orderType').value = 'BUY';
    document.getElementById('orderCondition').value = 'Intraday';
    document.getElementById('buyQty').value = '10';
    document.getElementById('sellQty').value = '0';
    document.getElementById('entryPrice').value = '';
    document.getElementById('currentPrice').value = '';
    document.getElementById('buyAvgPrice').value = '';
    document.getElementById('sellAvgPrice').value = '';
    document.getElementById('positionSource').value = 'LIVE';

    // Reset enable options
    Object.keys(enableOptions).forEach(option => {
        const statusElement = document.getElementById(`${option}Status`);
        const optionElement = document.querySelector(`[onclick="toggleEnableOption('${option}')"]`);

        if (enableOptions[option]) {
            statusElement.className = 'enable-status enabled';
            statusElement.innerHTML = '<i class="fas fa-check"></i>';
            if (optionElement) optionElement.classList.add('active');
        } else {
            statusElement.className = 'enable-status disabled';
            statusElement.innerHTML = '<i class="fas fa-times"></i>';
            if (optionElement) optionElement.classList.remove('active');
        }
    });

    // Reset position settings
    document.getElementById('positionOrderType').value = 'limit';
    document.getElementById('positionPart').value = 'buy';
    document.getElementById('positionQty').value = '10';
    document.getElementById('positionSellQty').value = '0';
    document.getElementById('trailingSLType').value = 'point';
    document.getElementById('trailingSLValue').value = '20';
    document.getElementById('indicatorOptions').style.display = 'none';
    document.getElementById('indicatorPeriod').value = '14';
    document.getElementById('indicatorCondition').value = 'close';

    document.getElementById('targetType').value = 'point';
    document.getElementById('targetValue').value = '50';
    document.getElementById('exitType').value = 'point';
    document.getElementById('exitValue').value = '30';
    document.getElementById('profitLock').value = '';
    document.getElementById('profitGap').value = '';

    // Reset partition & add quantity fields
    document.getElementById('partitionSquareOffQty').value = '2';
    document.getElementById('partitionSquareOffPrice').value = '';
    document.getElementById('addQty').value = '5';
    document.getElementById('addQtyPrice').value = '';
    document.getElementById('maxPartitionCount').value = '5';
    document.getElementById('autoSquareOffPercent').value = '10';
    document.getElementById('reentryAttempts').value = '3';
    document.getElementById('calculationResult').innerHTML = 'Enter values to calculate position sizing.';
    document.getElementById('calculationResult').style.color = '#aaa';

    // Reset toggle states
    toggleAllPositionSettings(true);

    // Reset section states
    positionSectionCollapsed = false;
    document.getElementById('positionSectionBody').classList.remove('collapsed');
    document.getElementById('positionSectionToggle').innerHTML = '<i class="fas fa-chevron-up"></i> Collapse';

    partitionSectionCollapsed = false;
    document.getElementById('partitionSectionBody').classList.remove('collapsed');
    document.getElementById('partitionSectionToggle').innerHTML = '<i class="fas fa-chevron-up"></i> Collapse';

    // Apply enable/disable states
    Object.keys(enableOptions).forEach(option => {
        const sectionElement = document.getElementById(`${option}Section`);
        if (sectionElement) {
            sectionElement.style.display = enableOptions[option] ? 'block' : 'none';
        }
    });

    document.getElementById('addPositionModal').style.display = 'flex';
}

function openAddPositionModalForSymbol(symbol, orderType = 'BUY') {
    document.getElementById('modalSymbolTitle').textContent = `Add Position - ${symbol}`;
    document.getElementById('positionSymbol').value = symbol;
    document.getElementById('positionSymbol').setAttribute('readonly', true);
    document.getElementById('orderType').value = orderType;
    document.getElementById('positionPart').value = orderType.toLowerCase();

    // Set default prices based on symbol
    const basePrice = symbol === 'RELIANCE' ? 2450 :
        symbol === 'TCS' ? 3850 :
        symbol === 'INFY' ? 1550 :
        Math.random() * 2000 + 1000;

    document.getElementById('entryPrice').value = basePrice.toFixed(2);
    document.getElementById('currentPrice').value = basePrice.toFixed(2);
    document.getElementById('buyAvgPrice').value = basePrice.toFixed(2);
    document.getElementById('sellAvgPrice').value = (basePrice * 1.02).toFixed(2);

    if (orderType === 'BUY') {
        document.getElementById('buyQty').value = 10;
        document.getElementById('sellQty').value = 0;
        document.getElementById('positionQty').value = 10;
        document.getElementById('positionSellQty').value = 0;
    } else {
        document.getElementById('buyQty').value = 0;
        document.getElementById('sellQty').value = 10;
        document.getElementById('positionQty').value = 0;
        document.getElementById('positionSellQty').value = 10;
    }

    // Set default position settings
    const slValue = basePrice * 0.02;
    const targetValue = basePrice * 0.03;

    document.getElementById('trailingSLValue').value = slValue.toFixed(2);
    document.getElementById('targetValue').value = targetValue.toFixed(2);
    document.getElementById('exitValue').value = (slValue * 0.5).toFixed(2);

    document.getElementById('profitLock').value = (basePrice * 1.01).toFixed(2);
    document.getElementById('profitGap').value = (basePrice * 0.005).toFixed(2);

    // Set partition & add quantity defaults
    document.getElementById('partitionSquareOffPrice').value = (basePrice * 1.01).toFixed(2);
    document.getElementById('addQtyPrice').value = (basePrice * 0.99).toFixed(2);

    // Reset toggle states
    toggleAllPositionSettings(true);

    document.getElementById('addPositionModal').style.display = 'flex';
}

function closeAddModal() {
    document.getElementById('addPositionModal').style.display = 'none';
}

function outsideCloseAddModal(e) {
    if (e.target.id === "addPositionModal") closeAddModal();
}

function addPosition() {
    const symbol = document.getElementById('positionSymbol').value.trim().toUpperCase();
    const orderType = document.getElementById('orderType').value;
    const orderCondition = document.getElementById('orderCondition').value;
    const buyQty = parseInt(document.getElementById('buyQty').value) || 0;
    const sellQty = parseInt(document.getElementById('sellQty').value) || 0;
    const entryPrice = parseFloat(document.getElementById('entryPrice').value);
    const currentPrice = parseFloat(document.getElementById('currentPrice').value) || entryPrice;
    const buyAvgPrice = parseFloat(document.getElementById('buyAvgPrice').value) || entryPrice;
    const sellAvgPrice = parseFloat(document.getElementById('sellAvgPrice').value) || 0;
    const source = document.getElementById('positionSource').value;

    // Get enable options
    const positionSettingsEnabled = enableOptions.positionSettings;
    const partitionSettingsEnabled = enableOptions.partitionSettings;
    const trailingSLEnabled = enableOptions.trailingSL;
    const profitLockEnabled = enableOptions.profitLock;

    // Get toggle states
    const orderTypeEnabled = document.getElementById('toggleOrderType').checked && positionSettingsEnabled;
    const partEnabled = document.getElementById('togglePart').checked && positionSettingsEnabled;
    const qtyEnabled = document.getElementById('toggleQty').checked && positionSettingsEnabled;
    const trailingSLChecked = document.getElementById('toggleTrailingSL').checked && positionSettingsEnabled;
    const targetEnabled = document.getElementById('toggleTarget').checked && positionSettingsEnabled;
    const exitEnabled = document.getElementById('toggleExit').checked && positionSettingsEnabled;
    const profitLockChecked = document.getElementById('toggleProfitLock').checked && positionSettingsEnabled;
    const profitGapEnabled = document.getElementById('toggleProfitGap').checked && positionSettingsEnabled;

    // New position section fields
    const positionOrderType = orderTypeEnabled ? document.getElementById('positionOrderType').value : 'limit';
    const positionPart = partEnabled ? document.getElementById('positionPart').value : 'buy';
    const positionQty = qtyEnabled ? parseInt(document.getElementById('positionQty').value) || 0 : 0;
    const positionSellQty = qtyEnabled ? parseInt(document.getElementById('positionSellQty').value) || 0 : 0;
    const trailingSLType = trailingSLChecked ? document.getElementById('trailingSLType').value : 'point';
    const trailingSLValue = trailingSLChecked ? parseFloat(document.getElementById('trailingSLValue').value) || 0 : 0;
    const indicatorPeriod = document.getElementById('indicatorPeriod').value;
    const indicatorCondition = document.getElementById('indicatorCondition').value;
    const targetType = targetEnabled ? document.getElementById('targetType').value : 'point';
    const targetValue = targetEnabled ? parseFloat(document.getElementById('targetValue').value) || 0 : 0;
    const exitType = exitEnabled ? document.getElementById('exitType').value : 'point';
    const exitValue = exitEnabled ? parseFloat(document.getElementById('exitValue').value) || 0 : 0;
    const profitLock = profitLockChecked ? parseFloat(document.getElementById('profitLock').value) || 0 : 0;
    const profitGap = profitGapEnabled ? parseFloat(document.getElementById('profitGap').value) || 0 : 0;

    // Partition & Add Quantity fields
    const partitionSquareOffQty = partitionSettingsEnabled ? parseInt(document.getElementById('partitionSquareOffQty').value) || 0 : 0;
    const partitionSquareOffPrice = partitionSettingsEnabled ? parseFloat(document.getElementById('partitionSquareOffPrice').value) || 0 : 0;
    const addQty = partitionSettingsEnabled ? parseInt(document.getElementById('addQty').value) || 0 : 0;
    const addQtyPrice = partitionSettingsEnabled ? parseFloat(document.getElementById('addQtyPrice').value) || 0 : 0;
    const maxPartitionCount = partitionSettingsEnabled ? parseInt(document.getElementById('maxPartitionCount').value) || 5 : 5;
    const autoSquareOffPercent = partitionSettingsEnabled ? parseFloat(document.getElementById('autoSquareOffPercent').value) || 10 : 10;
    const reentryAttempts = partitionSettingsEnabled ? parseInt(document.getElementById('reentryAttempts').value) || 3 : 3;

    if (!symbol) {
        alert("Please enter a stock symbol");
        return;
    }

    if (!entryPrice) {
        alert("Please enter an entry price");
        return;
    }

    if (!buyQty && !sellQty && !positionQty && !positionSellQty) {
        alert("Please enter either buy or sell quantity");
        return;
    }

    const finalQty = positionQty || buyQty || sellQty || positionSellQty;

    const newPosition = {
        symbol: symbol,
        orderType: orderType,
        orderCondition: orderCondition,
        entryPrice: entryPrice,
        currentPrice: currentPrice,
        buyQty: buyQty || positionQty,
        sellQty: sellQty || positionSellQty,
        buyAvgPrice: buyAvgPrice,
        sellAvgPrice: sellAvgPrice,
        source: source,
        stopLoss: entryPrice * 0.98,
        target: entryPrice * 1.02,
        trailingSL: 0,
        entryTime: new Date().toISOString(),

        // New position settings with toggle states
        positionSettings: {
            enabled: positionSettingsEnabled,
            orderType: positionOrderType,
            part: positionPart,
            qty: finalQty,
            trailingSL: {
                type: trailingSLType,
                value: trailingSLValue,
                indicator: trailingSLType === 'indicator' ? {
                    period: indicatorPeriod,
                    condition: indicatorCondition
                } : null,
                enabled: trailingSLChecked && trailingSLEnabled
            },
            target: {
                type: targetType,
                value: targetValue,
                enabled: targetEnabled
            },
            exit: {
                type: exitType,
                value: exitValue,
                enabled: exitEnabled
            },
            profitLock: profitLock,
            profitLockEnabled: profitLockChecked && profitLockEnabled,
            profitGap: profitGap,
            profitGapEnabled: profitGapEnabled,

            // Partition & Add Quantity settings
            partitionEnabled: partitionSettingsEnabled,
            partitionSquareOffQty: partitionSquareOffQty,
            partitionSquareOffPrice: partitionSquareOffPrice,
            addQty: addQty,
            addQtyPrice: addQtyPrice,
            maxPartitionCount: maxPartitionCount,
            autoSquareOffPercent: autoSquareOffPercent,
            reentryAttempts: reentryAttempts
        }
    };

    positions.push(newPosition);
    savePositions();
    renderPositions();
    updatePLSummary();
    closeAddModal();

    alert(`${orderType} position added for ${symbol} with position settings`);
}

// ===== ACTION MODAL FUNCTIONS =====
function openActionModal(symbol, index) {
    currentPositionIndex = index;
    const position = positions[index];

    document.getElementById('actionModalSymbolTitle').textContent = `Position Actions - ${symbol}`;

    // Set current values for modify tab
    document.getElementById('modifyStopLoss').value = position.stopLoss || '';
    document.getElementById('modifyTarget').value = position.target || '';
    document.getElementById('modifyTrailingSL').value = position.trailingSL || '';

    // Set values for exit tab
    const totalQty = Math.abs(position.buyQty - position.sellQty);
    document.getElementById('exitQty').value = totalQty;
    document.getElementById('exitPrice').value = position.currentPrice.toFixed(2);

    // Set values for partition tab
    const posSettings = position.positionSettings || {};
    document.getElementById('actionPartitionSquareOffQty').value = posSettings.partitionSquareOffQty || 0;
    document.getElementById('actionPartitionSquareOffPrice').value = posSettings.partitionSquareOffPrice || '';
    document.getElementById('actionAddQty').value = posSettings.addQty || 0;
    document.getElementById('actionAddQtyPrice').value = posSettings.addQtyPrice || '';

    // Load existing code if any
    const savedCode = localStorage.getItem(`strategyCode_${symbol}`);
    if (savedCode) {
        document.getElementById('strategyCode').value = savedCode;
    }

    document.getElementById('actionModal').style.display = 'flex';
}

function closeActionModal() {
    document.getElementById('actionModal').style.display = 'none';
    currentPositionIndex = -1;
}

function outsideCloseActionModal(e) {
    if (e.target.id === "actionModal") closeActionModal();
}


function switchActionTab(e, tabId) {
    // Remove active class from all tabs
    document.querySelectorAll('.tabs button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Add active class to clicked tab
    e.target.classList.add('active');

    // Hide all tab content
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Show selected tab content
    document.getElementById(tabId).classList.add('active');
}

function modifyPosition() {
    if (currentPositionIndex === -1) return;

    const stopLoss = parseFloat(document.getElementById('modifyStopLoss').value);
    const target = parseFloat(document.getElementById('modifyTarget').value);
    const trailingSL = parseFloat(document.getElementById('modifyTrailingSL').value);

    positions[currentPositionIndex].stopLoss = stopLoss;
    positions[currentPositionIndex].target = target;
    positions[currentPositionIndex].trailingSL = trailingSL;

    savePositions();
    renderPositions();

    alert(`Position modified for ${positions[currentPositionIndex].symbol}`);
    closeActionModal();
}

function exitPosition() {
    if (currentPositionIndex === -1) return;

    const exitQty = parseInt(document.getElementById('exitQty').value);
    const exitPrice = parseFloat(document.getElementById('exitPrice').value);
    const exitReason = document.getElementById('exitReason').value;

    const position = positions[currentPositionIndex];
    const totalQty = Math.abs(position.buyQty - position.sellQty);

    if (exitQty > totalQty) {
        alert("Exit quantity cannot be greater than position quantity");
        return;
    }

    // In real app, you would handle partial exits
    positions.splice(currentPositionIndex, 1);
    savePositions();
    renderPositions();
    updatePLSummary();

    alert(`Position exited for ${position.symbol} at ₹${exitPrice}`);
    closeActionModal();
}

function saveStrategyCode() {
    const code = document.getElementById('strategyCode').value;
    if (code.trim() && currentPositionIndex !== -1) {
        const symbol = positions[currentPositionIndex].symbol;
        localStorage.setItem(`strategyCode_${symbol}`, code);
        alert("Strategy code saved successfully!");
    } else {
        alert("Please enter some code");
    }
}

function testStrategyCode() {
    const code = document.getElementById('strategyCode').value;
    if (code.trim()) {
        alert("Strategy code tested (simulation). In real app, this would execute the code in a sandbox.");
    } else {
        alert("Please enter some code to test");
    }
}


function saveSettings() {
    const alertPrice = parseFloat(document.getElementById('alertPrice').value);
    const autoSquareOff = document.getElementById('autoSquareOff').value;
    const maxLoss = parseFloat(document.getElementById('maxLoss').value);

    if (currentPositionIndex !== -1) {
        positions[currentPositionIndex].alertPrice = alertPrice;
        positions[currentPositionIndex].autoSquareOff = autoSquareOff;
        positions[currentPositionIndex].maxLoss = maxLoss;

        savePositions();
        alert("Settings saved for position!");
    }
    closeActionModal();
}


function executePartitionAction() {
    if (currentPositionIndex === -1) return;

    const partitionQty = parseFloat(document.getElementById('actionPartitionSquareOffQty').value) || 0;
    const partitionPrice = parseFloat(document.getElementById('actionPartitionSquareOffPrice').value) || 0;
    const addQty = parseFloat(document.getElementById('actionAddQty').value) || 0;
    const addPrice = parseFloat(document.getElementById('actionAddQtyPrice').value) || 0;
    const actionType = document.getElementById('partitionAction').value;

    const position = positions[currentPositionIndex];

    if (actionType === 'square_off' || actionType === 'both') {
        if (partitionQty > 0) {
            const profit = (partitionPrice - position.entryPrice) * partitionQty;

            alert(`Partition square off: ${partitionQty} units at ₹${partitionPrice.toFixed(2)}. P/L: ₹${profit.toFixed(2)}`);

            // Update position
            if (position.orderType === 'BUY') {
                position.buyQty = Math.max(0, position.buyQty - partitionQty);
            } else {
                position.sellQty = Math.max(0, position.sellQty - partitionQty);
            }
        }
    }

    if (actionType === 'add_qty' || actionType === 'both') {
        if (addQty > 0) {
            alert(`Added ${addQty} units at ₹${addPrice.toFixed(2)}`);

            // Update position
            if (position.orderType === 'BUY') {
                position.buyQty += addQty;
                // Recalculate average price
                const totalCost = (position.buyAvgPrice * (position.buyQty - addQty)) + (addPrice * addQty);
                position.buyAvgPrice = totalCost / position.buyQty;
            } else {
                position.sellQty += addQty;
                // Recalculate average price
                const totalCost = (position.sellAvgPrice * (position.sellQty - addQty)) + (addPrice * addQty);
                position.sellAvgPrice = totalCost / position.sellQty;
            }
        }
    }

    savePositions();
    renderPositions();
    updatePLSummary();
    closeActionModal();
}


// ===== POSITION MANAGEMENT FUNCTIONS =====
function deletePosition(index) {
    if (confirm(`Delete position for ${positions[index].symbol}?`)) {
        positions.splice(index, 1);
        savePositions();
        renderPositions();
        updatePLSummary();
    }
}

function changeSource(index, source) {
    positions[index].source = source;
    savePositions();
    renderPositions();
    alert(`Source changed to ${source} for ${positions[index].symbol}`);
}

// New function to view position details
function viewPositionDetails(index) {
    const position = positions[index];
    const posSettings = position.positionSettings || {};

    let details = `
       <strong>Position Details for ${position.symbol}</strong><br><br>
       <strong>Order Details:</strong><br>
       - Order Type: ${position.orderType}<br>
       - Order Condition: ${position.orderCondition}<br>
       - Entry Price: ₹${position.entryPrice.toFixed(2)}<br>
       - Current Price: ₹${position.currentPrice.toFixed(2)}<br>
       - Buy Qty: ${position.buyQty}<br>
       - Sell Qty: ${position.sellQty}<br><br>
    `;

    if (posSettings.orderType) {
        details += `
        <strong>Position Settings:</strong><br>
        - Order Type: ${posSettings.orderType.toUpperCase()} ${posSettings.orderTypeEnabled !== false ? '✅' : '❌'}<br>
        - Part: ${posSettings.part.toUpperCase()} ${posSettings.partEnabled !== false ? '✅' : '❌'}<br>
        - Quantity: ${posSettings.qty} ${posSettings.qtyEnabled !== false ? '✅' : '❌'}<br>
        - Trailing SL: ${posSettings.trailingSL?.type || 'N/A'} (${posSettings.trailingSL?.value || '0'}) ${posSettings.trailingSL?.enabled ? '✅' : '❌'}<br>
        - Target: ${posSettings.target?.type || 'N/A'} (${posSettings.target?.value || '0'}) ${posSettings.target?.enabled ? '✅' : '❌'}<br>
        - Exit: ${posSettings.exit?.type || 'N/A'} (${posSettings.exit?.value || '0'}) ${posSettings.exit?.enabled ? '✅' : '❌'}<br>
        - Profit Lock: ₹${posSettings.profitLock || '0'} ${posSettings.profitLockEnabled ? '✅' : '❌'}<br>
        - Profit Gap: ₹${posSettings.profitGap || '0'} ${posSettings.profitGapEnabled ? '✅' : '❌'}<br>
        `;

        // Partition & Add Quantity details
        if (posSettings.partitionSquareOffQty || posSettings.addQty) {
            details += `<strong>Partition & Add Quantity:</strong><br>`;
            if (posSettings.partitionSquareOffQty) {
                details += `- Partition Square Off Qty: ${posSettings.partitionSquareOffQty}<br>`;
                details += `- Partition Square Off Price: ₹${posSettings.partitionSquareOffPrice || '0.00'}<br>`;
            }
            if (posSettings.addQty) {
                details += `- Add Quantity: ${posSettings.addQty}<br>`;
                details += `- Add Quantity Price: ₹${posSettings.addQtyPrice || '0.00'}<br>`;
            }
        }
    }

    alert(details);
}

// New function to modify position settings
function modifyPositionSettings(index) {
    const position = positions[index];
    const posSettings = position.positionSettings || {};

    // Open the add position modal with existing values
    openAddPositionModalForSymbol(position.symbol, position.orderType);

    // Fill position settings
    if (posSettings.orderType) {
        document.getElementById('positionOrderType').value = posSettings.orderType;
        document.getElementById('positionPart').value = posSettings.part;
        document.getElementById('positionQty').value = posSettings.qty || position.buyQty;
        document.getElementById('trailingSLType').value = posSettings.trailingSL?.type || 'point';
        document.getElementById('trailingSLValue').value = posSettings.trailingSL?.value || 0;
        document.getElementById('targetType').value = posSettings.target?.type || 'point';
        document.getElementById('targetValue').value = posSettings.target?.value || 0;
        document.getElementById('exitType').value = posSettings.exit?.type || 'point';
        document.getElementById('exitValue').value = posSettings.exit?.value || 0;
        document.getElementById('profitLock').value = posSettings.profitLock || 0;
        document.getElementById('profitGap').value = posSettings.profitGap || 0;

        // Set toggle states
        document.getElementById('toggleOrderType').checked = posSettings.orderTypeEnabled !== false;
        document.getElementById('togglePart').checked = posSettings.partEnabled !== false;
        document.getElementById('toggleQty').checked = posSettings.qtyEnabled !== false;
        document.getElementById('toggleTrailingSL').checked = posSettings.trailingSL?.enabled !== false;
        document.getElementById('toggleTarget').checked = posSettings.target?.enabled !== false;
        document.getElementById('toggleExit').checked = posSettings.exit?.enabled !== false;
        document.getElementById('toggleProfitLock').checked = posSettings.profitLockEnabled || false;
        document.getElementById('toggleProfitGap').checked = posSettings.profitGapEnabled || false;

        // Trigger change events
        document.getElementById('toggleOrderType').dispatchEvent(new Event('change'));
        document.getElementById('togglePart').dispatchEvent(new Event('change'));
        document.getElementById('toggleQty').dispatchEvent(new Event('change'));
        document.getElementById('toggleTrailingSL').dispatchEvent(new Event('change'));
        document.getElementById('toggleTarget').dispatchEvent(new Event('change'));
        document.getElementById('toggleExit').dispatchEvent(new Event('change'));
        document.getElementById('toggleProfitLock').dispatchEvent(new Event('change'));
        document.getElementById('toggleProfitGap').dispatchEvent(new Event('change'));

        // Partition & Add Quantity settings
        document.getElementById('partitionSquareOffQty').value = posSettings.partitionSquareOffQty || 0;
        document.getElementById('partitionSquareOffPrice').value = posSettings.partitionSquareOffPrice || '';
        document.getElementById('addQty').value = posSettings.addQty || 0;
        document.getElementById('addQtyPrice').value = posSettings.addQtyPrice || '';
        document.getElementById('maxPartitionCount').value = posSettings.maxPartitionCount || 5;
        document.getElementById('autoSquareOffPercent').value = posSettings.autoSquareOffPercent || 10;
        document.getElementById('reentryAttempts').value = posSettings.reentryAttempts || 3;

        // Handle indicator options
        if (posSettings.trailingSL?.type === 'indicator') {
            document.getElementById('indicatorOptions').style.display = 'grid';
            if (posSettings.trailingSL.indicator) {
                document.getElementById('indicatorPeriod').value = posSettings.trailingSL.indicator.period;
                document.getElementById('indicatorCondition').value = posSettings.trailingSL.indicator.condition;
            }
        }
    }

    // Change modal title
    document.getElementById('modalSymbolTitle').textContent = `Modify Position - ${position.symbol}`;

    // Update the addPosition function to handle modification
    const originalAddPosition = window.addPosition;
    window.addPosition = function() {
        // Remove old position
        positions.splice(index, 1);
        // Call original function to add modified position
        originalAddPosition();
        // Restore original function
        window.addPosition = originalAddPosition;
    };
}

function executePartitionSquareOff(positionIndex) {
    const position = positions[positionIndex];
    if (!position) return;

    const posSettings = position.positionSettings || {};
    const partitionQty = posSettings.partitionSquareOffQty || 0;
    const partitionPrice = posSettings.partitionSquareOffPrice || position.currentPrice;

    if (partitionQty <= 0) {
        alert("No partition square off quantity set for this position");
        return;
    }

    const confirmMsg = `Square off ${partitionQty} units of ${position.symbol} at ₹${partitionPrice.toFixed(2)}?`;

    if (confirm(confirmMsg)) {
        // In real app, this would execute the trade
        const profit = (partitionPrice - position.entryPrice) * partitionQty;
        const profitType = profit >= 0 ? "Profit" : "Loss";

        alert(`Partition square off executed!\n${partitionQty} units of ${position.symbol} at ₹${partitionPrice.toFixed(2)}\n${profitType}: ₹${Math.abs(profit).toFixed(2)}`);

        // Update position quantity
        if (position.orderType === 'BUY') {
            position.buyQty = Math.max(0, position.buyQty - partitionQty);
        } else {
            position.sellQty = Math.max(0, position.sellQty - partitionQty);
        }

        savePositions();
        renderPositions();
        updatePLSummary();
    }
}

function executeAddQuantity(positionIndex) {
    const position = positions[positionIndex];
    if (!position) return;

    const posSettings = position.positionSettings || {};
    const addQty = posSettings.addQty || 0;
    const addPrice = posSettings.addQtyPrice || position.currentPrice;

    if (addQty <= 0) {
        alert("No add quantity set for this position");
        return;
    }

    const confirmMsg = `Add ${addQty} units to ${position.symbol} position at ₹${addPrice.toFixed(2)}?`;

    if (confirm(confirmMsg)) {
        // In real app, this would execute the trade
        alert(`Added ${addQty} units to ${position.symbol} position at ₹${addPrice.toFixed(2)}`);

        // Update position
        if (position.orderType === 'BUY') {
            position.buyQty += addQty;
            // Recalculate average price
            const totalCost = (position.buyAvgPrice * (position.buyQty - addQty)) + (addPrice * addQty);
            position.buyAvgPrice = totalCost / position.buyQty;
        } else {
            position.sellQty += addQty;
            // Recalculate average price
            const totalCost = (position.sellAvgPrice * (position.sellQty - addQty)) + (addPrice * addQty);
            position.sellAvgPrice = totalCost / position.sellQty;
        }

        savePositions();
        renderPositions();
        updatePLSummary();
    }
}

// ===== UTILITY FUNCTIONS =====
function openChart(symbol) {
    alert(`Opening chart for ${symbol}`);
}

function openDepth(symbol) {
    alert(`Opening market depth for ${symbol}`);
}

function openInfo(symbol) {
    alert(`Opening info for ${symbol}`);
}

function openGTT(symbol) {
    alert(`Opening GTT for ${symbol}`);
}

function openOptionChain(symbol) {
    alert(`Opening option chain for ${symbol}`);
}

function setAlert(symbol) {
    const price = prompt(`Set price alert for ${symbol}:`);
    if (price) {
        alert(`Alert set for ${symbol} at ₹${price}`);
    }
}

// ===== PAGE NAVIGATION =====
function showPage(pageId) {
    const pages = document.querySelectorAll('.content-page');
    pages.forEach(page => {
        page.classList.add('hidden');
    });
    document.getElementById(pageId).classList.remove('hidden');

    // Update active button in navigation
    const buttons = document.querySelectorAll('.nav-popup button');
    buttons.forEach(btn => {
        btn.classList.remove('active');
        if (btn.onclick && btn.onclick.toString().includes(pageId)) {
            btn.classList.add('active');
        }
    });

    // Hide navigation popup after clicking
    hideNavPopup();
}


// ===== SCREENER POPUP FUNCTIONS =====
function openScreenerPopup() {
    document.getElementById('screenerPopupModal').style.display = 'flex';
    hideNavPopup();
}

function closeScreenerPopup(e) {
    if (!e || e.target.id === "screenerPopupModal") {
        document.getElementById('screenerPopupModal').style.display = 'none';
    }
}

function openChartink() {
    window.open('https://chartink.com/screener', '_blank');
    closeScreenerPopup();
}

function deployIndicatorScreener() {
    const indicator = document.getElementById('indicatorSelect').value;
    const value = document.getElementById('indicatorValue').value;

    if (indicator === 'Select Indicator' || !value) {
        alert('Please select an indicator and enter a value');
        return;
    }

    alert(`Indicator Based Screener Deployed!\n${indicator} = ${value}`);
    closeScreenerPopup();
}

function deploySavedScreener() {
    alert('Saved Screener Deployed!');
    closeScreenerPopup();
}

function createNewScreener() {
    alert('Create New Screener - Opening Screener Builder');
    closeScreenerPopup();
}


// ===== STRATEGY CREATION POPUP FUNCTIONS =====
function openStrategyPopup() {
    document.getElementById('strategyCreationPopup').style.display = 'flex';
    hideNavPopup();
}

function closeStrategyPopup(e) {
    if (!e || e.target.id === "strategyCreationPopup") {
        document.getElementById('strategyCreationPopup').style.display = 'none';
    }
}

function openOpstra() {
    window.open('https://opstra.definedge.com', '_blank');
    closeStrategyPopup();
}

function openSensibull() {
    window.open('https://sensibull.com', '_blank');
    closeStrategyPopup();
}

function openMarketPlace() {
    showPage('marketplacePage');
    closeStrategyPopup();
}

function openCreateStrategy() {
    alert('Opening Strategy Creation Page');
    // You can redirect to your strategy creation page here
    closeStrategyPopup();
}

function backtestStrategy() {
    showPage('backtestPage');
    closeStrategyPopup();
}

function optimizeStrategy() {
    alert('Strategy Optimization Feature');
}

function shareStrategy() {
    alert('Share Strategy Feature');
}

// ===== BROKER MANAGEMENT FUNCTIONS =====
// ===== BROKER CONNECTION (REAL API) =====
let brokerConnected = false;

function loadBrokers() {
    const brokerList = document.getElementById('brokerList');
    const savedBrokers = localStorage.getItem('mukeshAlgoBrokers');

    if (!savedBrokers) {
        brokerList.innerHTML = '<div style="text-align:center; color:#888; padding:20px;">No connection history yet.</div>';
        return;
    }

    const brokers = JSON.parse(savedBrokers);
    let html = '';
    brokers.slice(-5).reverse().forEach(broker => {
        const statusColor = broker.status === 'connected' ? '#00ff88' : '#ff4444';
        html += `
          <div style="background:#2a2a2a; padding:10px 12px; margin-bottom:6px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
            <div>
               <strong style="color:var(--accent-color); font-size:13px;">${broker.name}</strong>
               <span style="font-size:11px; color:#888; margin-left:8px;">ID: ${broker.clientId}</span>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
               <span style="font-size:10px; color:#888;">${broker.time || ''}</span>
               <span style="font-size:11px; color:${statusColor}; font-weight:600;">${broker.status.toUpperCase()}</span>
            </div>
          </div>`;
    });
    brokerList.innerHTML = html;
}

function updateBrokerStatus(connected, brokerName) {
    brokerConnected = connected;
    const dot = document.getElementById('brokerStatusDot');
    const text = document.getElementById('brokerStatusText');
    const detail = document.getElementById('brokerStatusDetail');

    if (connected) {
        dot.style.background = '#00ff88';
        text.textContent = `Connected to ${brokerName}`;
        text.style.color = '#00ff88';
        detail.textContent = 'Real-time data active. Watchlist prices updating.';
    } else {
        dot.style.background = '#ff4444';
        text.textContent = 'Not Connected';
        text.style.color = '#fff';
        detail.textContent = 'Configure and connect a broker below';
    }
}

function checkBrokerStatusOnLoad() {
    fetch('/api/broker/status')
        .then(r => r.json())
        .then(data => {
            if (data.success && data.connected) {
                updateBrokerStatus(true, data.broker);
                startLtpUpdates();
            }
        })
        .catch(() => {});
}

function brokerGetLoginUrl() {
    const brokerType = document.getElementById('brokerSelect').value;
    const userId = document.getElementById('clientId').value.trim();
    const apiKey = document.getElementById('apiKey').value.trim();
    const appCode = document.getElementById('apiSecret').value.trim();

    if (!userId) { alert('User ID required'); return; }
    if (!apiKey) { alert('Secret Key required'); return; }
    if (!appCode && brokerType === 'alice_blue') { alert('App Code required'); return; }

    const btn = document.getElementById('btnGetLoginUrl');
    btn.textContent = 'Getting Login URL...';
    btn.disabled = true;

    fetch('/api/broker/login-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            broker_type: brokerType,
            api_key: apiKey,
            api_secret: appCode,
            app_code: appCode,
            user_id: userId,
            redirect_uri: window.location.origin + '/callback'
        })
    })
    .then(r => r.json())
    .then(data => {
        btn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Step 1: Get Login URL';
        btn.disabled = false;

        if (data.success && data.login_url) {
            document.getElementById('loginUrlDisplay').value = data.login_url;
            document.getElementById('loginUrlSection').style.display = 'block';
            document.getElementById('authCodeSection').style.display = 'block';

            // Auto-open login URL in new tab
            window.open(data.login_url, '_blank');
        } else {
            showAuthResult(false, data.message || 'Failed to get login URL');
        }
    })
    .catch(err => {
        btn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Step 1: Get Login URL';
        btn.disabled = false;
        showAuthResult(false, 'Network error: ' + err.message);
    });
}

function brokerAuthenticate() {
    const authCode = document.getElementById('authCodeInput').value.trim();
    if (!authCode) { alert('Please paste the authorization code'); return; }

    const btn = document.getElementById('btnAuthenticate');
    btn.textContent = 'Authenticating...';
    btn.disabled = true;

    fetch('/api/broker/authenticate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auth_code: authCode })
    })
    .then(r => r.json())
    .then(data => {
        btn.innerHTML = '<i class="fas fa-check-circle"></i> Step 2: Authenticate';
        btn.disabled = false;

        if (data.success) {
            showAuthResult(true, 'Connected to ' + (data.broker || 'broker') + ' successfully!');
            updateBrokerStatus(true, data.broker || 'Alice Blue');

            // Save to history
            const brokerName = document.getElementById('brokerSelect').options[document.getElementById('brokerSelect').selectedIndex].text;
            const clientId = document.getElementById('clientId').value;
            let brokers = JSON.parse(localStorage.getItem('mukeshAlgoBrokers') || '[]');
            brokers.push({
                name: brokerName,
                clientId: clientId,
                status: 'connected',
                time: new Date().toLocaleString('en-IN')
            });
            localStorage.setItem('mukeshAlgoBrokers', JSON.stringify(brokers));
            loadBrokers();

            // Start real-time price updates
            startLtpUpdates();
        } else {
            showAuthResult(false, data.message || 'Authentication failed');
        }
    })
    .catch(err => {
        btn.innerHTML = '<i class="fas fa-check-circle"></i> Step 2: Authenticate';
        btn.disabled = false;
        showAuthResult(false, 'Network error: ' + err.message);
    });
}

function showAuthResult(success, message) {
    const el = document.getElementById('authResult');
    el.style.display = 'block';
    el.style.background = success ? 'rgba(0,170,102,0.15)' : 'rgba(255,68,68,0.15)';
    el.style.border = `1px solid ${success ? '#00aa66' : '#ff4444'}`;
    el.style.color = success ? '#00ff88' : '#ff4444';
    el.innerHTML = `<i class="fas fa-${success ? 'check-circle' : 'times-circle'}"></i> ${message}`;
}

// ===== REAL-TIME LTP UPDATES FOR WATCHLIST =====
let ltpUpdateInterval = null;

function startLtpUpdates() {
    if (ltpUpdateInterval) clearInterval(ltpUpdateInterval);
    // Update immediately then every 3 seconds
    updateWatchlistLtp();
    ltpUpdateInterval = setInterval(updateWatchlistLtp, 3000);
}

function updateWatchlistLtp() {
    if (!brokerConnected) return;

    // Get visible watchlist symbols
    const visibleItems = document.querySelectorAll('.wl-item');
    if (visibleItems.length === 0) return;

    visibleItems.forEach(item => {
        const symbol = item.dataset.symbol;
        if (!symbol) return;

        // Determine exchange from symbol pattern
        let exchange = 'NSE';
        if (symbol.match(/\d{2}[A-Z]{3}\d{2}[CP]/) || symbol.match(/FUT$/)) {
            exchange = 'NFO';
        }

        fetch(`/api/ltp/${encodeURIComponent(symbol)}?exchange=${exchange}`)
            .then(r => r.json())
            .then(data => {
                if (data.success && data.ltp > 0) {
                    const priceEl = item.querySelector('.wl-item-price');
                    if (priceEl) {
                        const oldPrice = parseFloat(priceEl.textContent) || 0;
                        const newPrice = data.ltp;
                        priceEl.textContent = newPrice.toFixed(2);

                        // Update stored price data
                        if (stockPrices[symbol]) {
                            stockPrices[symbol].price = newPrice;
                        } else {
                            stockPrices[symbol] = { price: newPrice, change: 0, changePct: 0 };
                        }

                        // Flash effect on price change
                        if (oldPrice !== 0 && oldPrice !== newPrice) {
                            priceEl.style.transition = 'none';
                            priceEl.style.background = newPrice > oldPrice ? 'rgba(0,204,102,0.3)' : 'rgba(255,68,68,0.3)';
                            setTimeout(() => {
                                priceEl.style.transition = 'background 0.5s';
                                priceEl.style.background = 'transparent';
                            }, 300);
                        }
                    }
                }
            })
            .catch(() => {}); // Silent fail for individual symbols
    });
}

// Keep old function names as no-ops for compatibility
function addEditBroker() { brokerGetLoginUrl(); }
function deleteBroker() {}
function checkBrokerConnection() { checkBrokerStatusOnLoad(); }
function editBroker() {}
function testBrokerConnection() { checkBrokerStatusOnLoad(); }


// Initialize brokers when page loads
function initializeBrokerPage() {
    loadBrokers();
    checkBrokerStatusOnLoad();
}

// ===== FULL SCREEN MODE =====
function fullScreenMode() {
    const elem = document.documentElement;

    if (!document.fullscreenElement) {
        if (elem.requestFullscreen) {
            elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        } else if (elem.msRequestFullscreen) {
            elem.msRequestFullscreen();
        }
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
}


// Handle fullscreen change
document.addEventListener('fullscreenchange', updateFullscreenStyles);
document.addEventListener('webkitfullscreenchange', updateFullscreenStyles);
document.addEventListener('msfullscreenchange', updateFullscreenStyles);


function updateFullscreenStyles() {
    const isFullscreen = document.fullscreenElement ||
        document.webkitFullscreenElement ||
        document.msFullscreenElement;

    const header = document.querySelector('.header');
    const ticker = document.querySelector('.market-ticker-container');
    const navTrigger = document.getElementById('navHoverTrigger');
    const content = document.getElementById('mainContent');
    const watchlistPanel = document.getElementById('watchlistPanel');

    if (isFullscreen) {
        header.style.display = 'none';
        ticker.style.display = 'none';
        navTrigger.style.display = 'none';
        watchlistPanel.style.display = 'none';

        content.style.margin = '0';
        content.style.padding = '20px';
        content.style.width = '100%';
        content.style.height = '100vh';
        content.style.position = 'fixed';
        content.style.top = '0';
        content.style.left = '0';
        content.style.zIndex = '10000';
        content.style.background = 'var(--dark-bg)';
        content.style.overflow = 'auto';
    } else {
        header.style.display = 'flex';
        ticker.style.display = 'block';
        navTrigger.style.display = 'block';
        watchlistPanel.style.display = 'block';

        content.style.margin = '';
        content.style.padding = '';
        content.style.width = '';
        content.style.height = '';
        content.style.position = '';
        content.style.top = '';
        content.style.left = '';
        content.style.zIndex = '';
        content.style.background = '';
        content.style.overflow = '';
    }
}


function resetAllData() {
    if (confirm('This will reset ALL positions, watchlist and brokers. Are you sure?')) {
        localStorage.removeItem('mukeshAlgoPositions');
        localStorage.removeItem('mukeshAlgoWatchlist');
        localStorage.removeItem('mukeshAlgoBrokers');
        positions = [];
        watchlistStocks = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC", "BHARTIARTL", "WIPRO", "TITAN"];
        saveWatchlist();
        renderPositions();
        renderWatchlist();
        loadBrokers();
        updatePLSummary();
        alert('All data has been reset!');
    }
}

function logOut() {
    if (confirm('Are you sure you want to log out?')) {
        alert('Logging out...');
        // In a real application, you would redirect to login page
        // window.location.href = '/login';
    }
}

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', function() {
    // Initialize clock
    updateClock();
    setInterval(updateClock, 1000);

    // Initialize market ticker
    populateMarketTicker();

    // Load watchlist
    loadWatchlist();

    // Try to fetch broker instruments (will use local DB as fallback)
    fetchBrokerInstruments();

    // Load positions
    loadPositions();

    // Initialize broker page
    initializeBrokerPage();

    // Initialize position toggles
    initializePositionToggles();

    // Show open positions page by default
    showPage('openPositionsPage');

    // Watchlist price auto-refresh every 5 seconds
    setInterval(function() {
        if (wlActiveTab === 'watchlist') refreshWatchlist();
    }, 5000);

    // Start market data updates
    setInterval(updateMarketData, 5000);

    // Initial market data update
    updateMarketData();

    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAddModal();
            closeActionModal();
            closeScreenerPopup();
            closeStrategyPopup();
        }
        if (e.key === 'F11') {
            e.preventDefault();
            fullScreenMode();
        }
        if (e.ctrlKey && e.key === 'p') {
            e.preventDefault();
            openAddPositionModal();
        }
    });
});
