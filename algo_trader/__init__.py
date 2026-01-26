"""
Algo Trader - Pine Script & Chartink Based Trading Platform
"""

__version__ = "1.0.0"
__author__ = "Anirudha Talmale"

from .core.config import Config
from .core.database import Database
from .core.order_manager import OrderManager
from .core.strategy_engine import StrategyEngine
