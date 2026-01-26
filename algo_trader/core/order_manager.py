"""
Order Manager - Handles order routing and execution across brokers
"""
from typing import Dict, Optional, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from .database import Database


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"  # Stop Loss
    SL_M = "SL-M"  # Stop Loss Market


class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class Exchange(Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"  # NSE F&O
    BFO = "BFO"  # BSE F&O
    MCX = "MCX"  # Commodities
    CDS = "CDS"  # Currency


@dataclass
class Order:
    """Order data class"""
    symbol: str
    transaction_type: TransactionType
    quantity: int
    order_type: OrderType = OrderType.MARKET
    price: float = None
    trigger_price: float = None
    exchange: Exchange = Exchange.NSE
    product: str = "CNC"  # CNC for delivery, MIS for intraday, NRML for F&O
    strategy_id: int = None
    broker: str = None
    order_id: int = None
    broker_order_id: str = None
    status: OrderStatus = OrderStatus.PENDING
    message: str = None
    created_at: datetime = None

    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'transaction_type': self.transaction_type.value,
            'quantity': self.quantity,
            'order_type': self.order_type.value,
            'price': self.price,
            'trigger_price': self.trigger_price,
            'exchange': self.exchange.value,
            'product': self.product,
            'strategy_id': self.strategy_id,
            'broker': self.broker,
            'order_id': self.order_id,
            'broker_order_id': self.broker_order_id,
            'status': self.status.value,
            'message': self.message
        }


class OrderManager:
    """
    Manages order routing and execution across multiple brokers
    """

    def __init__(self, database: Database):
        self.db = database
        self.brokers = {}  # broker_name -> broker_instance
        self.active_orders = {}  # order_id -> Order

    def register_broker(self, name: str, broker_instance):
        """Register a broker for order execution"""
        self.brokers[name] = broker_instance
        logger.info(f"Registered broker: {name}")

    def unregister_broker(self, name: str):
        """Unregister a broker"""
        if name in self.brokers:
            del self.brokers[name]
            logger.info(f"Unregistered broker: {name}")

    def get_available_brokers(self) -> List[str]:
        """Get list of registered brokers"""
        return list(self.brokers.keys())

    def place_order(self, order: Order, broker_name: str) -> Order:
        """
        Place an order through specified broker
        """
        if broker_name not in self.brokers:
            order.status = OrderStatus.ERROR
            order.message = f"Broker '{broker_name}' not registered"
            logger.error(order.message)
            return order

        broker = self.brokers[broker_name]
        order.broker = broker_name
        order.created_at = datetime.now()

        # Save order to database
        order.order_id = self.db.save_order(
            broker=broker_name,
            symbol=order.symbol,
            order_type=order.order_type.value,
            transaction_type=order.transaction_type.value,
            quantity=order.quantity,
            price=order.price,
            trigger_price=order.trigger_price,
            exchange=order.exchange.value,
            strategy_id=order.strategy_id
        )

        try:
            # Execute order through broker
            logger.info(f"Placing order: {order.symbol} {order.transaction_type.value} {order.quantity} @ {order.order_type.value}")
            result = broker.place_order(order)

            if result.get('success'):
                order.broker_order_id = result.get('order_id')
                order.status = OrderStatus.OPEN
                order.message = "Order placed successfully"
            else:
                order.status = OrderStatus.REJECTED
                order.message = result.get('message', 'Order rejected')

        except Exception as e:
            order.status = OrderStatus.ERROR
            order.message = str(e)
            logger.error(f"Order execution failed: {e}")

        # Update order status in database
        self.db.update_order_status(
            order_id=order.order_id,
            status=order.status.value,
            broker_order_id=order.broker_order_id,
            message=order.message
        )

        self.active_orders[order.order_id] = order
        return order

    def cancel_order(self, order_id: int) -> bool:
        """Cancel an open order"""
        if order_id not in self.active_orders:
            logger.warning(f"Order {order_id} not found in active orders")
            return False

        order = self.active_orders[order_id]
        if order.broker not in self.brokers:
            logger.error(f"Broker {order.broker} not registered")
            return False

        broker = self.brokers[order.broker]
        try:
            result = broker.cancel_order(order.broker_order_id)
            if result.get('success'):
                order.status = OrderStatus.CANCELLED
                self.db.update_order_status(order_id, OrderStatus.CANCELLED.value)
                logger.info(f"Order {order_id} cancelled")
                return True
            else:
                logger.error(f"Cancel failed: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False

    def get_order_status(self, order_id: int) -> Optional[Order]:
        """Get current status of an order"""
        return self.active_orders.get(order_id)

    def sync_order_status(self, broker_name: str):
        """Sync order statuses from broker"""
        if broker_name not in self.brokers:
            return

        broker = self.brokers[broker_name]
        try:
            orders = broker.get_orders()
            for broker_order in orders:
                # Find matching order and update status
                for order_id, order in self.active_orders.items():
                    if order.broker_order_id == broker_order.get('order_id'):
                        new_status = self._map_broker_status(broker_order.get('status'))
                        if new_status != order.status:
                            order.status = new_status
                            self.db.update_order_status(order_id, new_status.value)
                            logger.info(f"Order {order_id} status updated to {new_status.value}")
        except Exception as e:
            logger.error(f"Failed to sync order status: {e}")

    def _map_broker_status(self, broker_status: str) -> OrderStatus:
        """Map broker-specific status to OrderStatus enum"""
        status_map = {
            'complete': OrderStatus.COMPLETE,
            'completed': OrderStatus.COMPLETE,
            'open': OrderStatus.OPEN,
            'pending': OrderStatus.PENDING,
            'cancelled': OrderStatus.CANCELLED,
            'rejected': OrderStatus.REJECTED,
            'error': OrderStatus.ERROR
        }
        return status_map.get(broker_status.lower(), OrderStatus.PENDING)

    def get_positions(self, broker_name: str) -> List[Dict]:
        """Get current positions from broker"""
        if broker_name not in self.brokers:
            return []
        return self.brokers[broker_name].get_positions()

    def get_holdings(self, broker_name: str) -> List[Dict]:
        """Get holdings from broker"""
        if broker_name not in self.brokers:
            return []
        return self.brokers[broker_name].get_holdings()
