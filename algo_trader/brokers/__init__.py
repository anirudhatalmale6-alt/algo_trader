# Broker integrations
from algo_trader.brokers.base import BaseBroker, BrokerOrder
from algo_trader.brokers.upstox import UpstoxBroker
from algo_trader.brokers.alice_blue import AliceBlueBroker
from algo_trader.brokers.zerodha import ZerodhaBroker

# Angel One requires pyotp - import conditionally
try:
    from algo_trader.brokers.angel_one import AngelOneBroker
except ImportError:
    AngelOneBroker = None

# MT5 Broker for Forex/Crypto/Commodities (Exness, XM, Vantage, etc.)
try:
    from algo_trader.brokers.mt5_broker import MT5Broker, MetaTraderBroker
except ImportError:
    MT5Broker = None
    MetaTraderBroker = None
