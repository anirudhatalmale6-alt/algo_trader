# Algo Trader - Pine Script & Chartink Trading Platform

A desktop application for automated trading using Pine Script strategies with support for Indian brokers.

## Features

- **Pine Script Interpreter**: Copy-paste TradingView Pine Script strategies (v5/v6) and execute them
- **Multi-Broker Support**: Upstox, Alice Blue (more brokers coming)
- **Backtesting**: Test strategies on historical data
- **Real-time Trading**: Execute trades automatically based on strategy signals
- **Multiple Accounts**: Handle multiple broker accounts simultaneously
- **Chartink Integration**: (Coming in Phase 2)

## Supported Indicators

- Moving Averages: SMA, EMA, WMA, VWMA, RMA
- Oscillators: RSI, MACD, Stochastic, CCI, Williams %R, MFI
- Volatility: ATR, Bollinger Bands
- Trend: ADX, SuperTrend
- Volume: OBV, VWAP
- And more...

## Installation

1. Install Python 3.9 or higher

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python -m algo_trader.main
```

## Configuration

### Broker Setup

1. Get API credentials from your broker:
   - **Upstox**: https://account.upstox.com/developer/apps
   - **Alice Blue**: Contact Alice Blue support for ANT API access

2. In the application:
   - Go to Settings tab
   - Click "Add Broker"
   - Enter your API Key and Secret
   - Click "Get Login URL" and authenticate

### Creating a Strategy

1. Go to "Strategies" tab
2. Enter a strategy name
3. Paste your Pine Script code
4. Click "Validate" to check syntax
5. Click "Save Strategy"
6. Click "Activate" to enable for live trading

## Example Pine Script Strategy

```pine
//@version=5
strategy("Moving Average Crossover", overlay=true)

// Input parameters
fast_length = input.int(10, "Fast MA Length")
slow_length = input.int(20, "Slow MA Length")

// Calculate indicators
fast_ma = ta.sma(close, fast_length)
slow_ma = ta.sma(close, slow_length)

// Entry conditions
if ta.crossover(fast_ma, slow_ma)
    strategy.entry("Long", strategy.long)

if ta.crossunder(fast_ma, slow_ma)
    strategy.close("Long")
```

## Project Structure

```
algo_trader/
├── core/
│   ├── config.py          # Configuration management
│   ├── database.py        # SQLite database
│   ├── order_manager.py   # Order routing
│   └── strategy_engine.py # Strategy execution
├── brokers/
│   ├── base.py           # Base broker class
│   ├── upstox.py         # Upstox integration
│   └── alice_blue.py     # Alice Blue integration
├── strategies/
│   ├── indicators.py     # Technical indicators
│   ├── pine_parser.py    # Pine Script parser
│   └── pine_interpreter.py # Pine Script executor
├── ui/
│   ├── main_window.py    # Main application window
│   ├── broker_dialog.py  # Broker configuration
│   └── strategy_editor.py # Pine Script editor
└── main.py               # Entry point
```

## Roadmap

### Phase 1 (Current)
- [x] Core framework
- [x] Upstox integration
- [x] Alice Blue integration
- [x] Basic Pine Script interpreter
- [x] Desktop UI

### Phase 2
- [ ] Chartink integration
- [ ] More broker integrations (Zerodha, Dhan, Fyers)
- [ ] Advanced Pine Script features

### Phase 3
- [ ] Full backtesting engine with historical data
- [ ] Performance analytics

### Phase 4
- [ ] Advanced Pine Script features
- [ ] Strategy optimization
- [ ] Paper trading mode

## Disclaimer

This software is for educational purposes only. Trading in financial markets involves risk. Past performance is not indicative of future results. Always test strategies thoroughly before live trading.

## License

Private use only. Not for distribution.
