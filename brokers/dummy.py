import logging
from typing import Dict
from copy import deepcopy
from commons.enums import OrderStatus, PositionStatus, PositionType, LogType
from commons.models import Order, Position
from engine.utils import get_instrument_by_token
from errors.system_defined import BrokerError
from pricefeed import get_quote

logger = logging.getLogger(__name__)

orders: Dict[str, Order] = {}


def login():
    return True


def logout():
    return True


def get_fund():
    return 10000000, 0


def place_order(order: Order):
    order.broker_order_id = order.id
    order.status = OrderStatus.WORKING
    orders[order.id] = deepcopy(order)
    logger.debug(f"OrderUpdate: {order}")
    return order.broker_order_id


def modify_order():
    return True


def cancel_order():
    return True


def get_order_details(broker_order_id: str):
    order = orders.get(broker_order_id)
    if order.status in [OrderStatus.OPEN, OrderStatus.WORKING]:
        ltp = get_quote(order.instrument_id)
        if not ltp:
            raise ValueError
        ltp = float(ltp)
        order.average_trade_price = ltp
        order.traded_quantity = order.quantity
        order.status = OrderStatus.FILLED
    return order


def fetch_orderbook():
    for _, order in orders.items():
        if order.status in [OrderStatus.OPEN, OrderStatus.WORKING]:
            ltp = get_quote(order.instrument_id)
            instrument = get_instrument_by_token(order.instrument_id)
            order.average_trade_price = ltp
            order.traded_quantity = order.quantity
            order.status = OrderStatus.FILLED
            if not ltp:
                order.status = OrderStatus.REJECTED
                order.error_message = f"ltp not found for {instrument.trading_symbol}"
            else:
                ltp = float(ltp)
            logger.debug(
                {
                    "id": order.id,
                    "instrument_id": order.instrument_id,
                    "product_type": order.product_type.name,
                    "order_type": order.order_type.name,
                    "side": order.side.name,
                    "limit_price": order.limit_price,
                    "trigger_price": order.trigger_price,
                    "quantity": order.quantity,
                    "creation_time": order.creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "broker_order_id": order.broker_order_id,
                    "average_trade_price": order.average_trade_price,
                    "traded_quantity": order.traded_quantity,
                    "status": order.status.name,
                    "error_code": order.error_code,
                    "error_message": order.error_message,
                    "last_update_time": order.last_update_time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )
            instrument = get_instrument_by_token(order.instrument_id)
            logger.info(f"{instrument.trading_symbol} :: Side={order.side.name}, Qty={order.traded_quantity}, Price={order.average_trade_price}")


def sync_position(position: Position):
    net_buy_qty = 0
    net_sell_qty = 0
    buy_prices = []
    sell_pricess = []
    for order in position.orders:
        if order.broker_order_id in orders:
            broker_order = orders[order.broker_order_id]
            order.traded_quantity = broker_order.traded_quantity
            order.average_trade_price = broker_order.average_trade_price
            if order.side == PositionType.BUY:
                net_buy_qty += order.traded_quantity
                buy_prices.append(order.average_trade_price)
            else:
                net_sell_qty += order.traded_quantity
                sell_pricess.append(order.average_trade_price)
            order.status = broker_order.status
            if order.status in [OrderStatus.REJECTED, OrderStatus.WORKING]:
                position.status = PositionStatus.ERROR
                order.error_code = broker_order.error_code
                order.error_message = broker_order.error_message
                logger.debug(f"Order {order.broker_order_id} rejected with {order.error_message}")
                raise BrokerError(
                    f"{order.error_message}"
                )
            order.error_code = broker_order.error_code
            order.error_message = broker_order.error_message
    if (
        net_buy_qty == position.net_buy_quantity
        and net_sell_qty == position.net_sell_quantity
    ):
        if buy_prices:
            position.buy_average_price = sum(buy_prices) / len(buy_prices)
        if sell_pricess:
            position.sell_average_price = sum(sell_pricess) / len(sell_pricess)
        position.buy_value = position.buy_average_price * position.net_buy_quantity
        position.sell_value = position.sell_average_price * position.net_sell_quantity
        position.net_quantity = net_buy_qty - net_sell_qty
        position.status = PositionStatus.COMPLETE
