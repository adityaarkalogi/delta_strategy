import logging
from queue import Queue
import threading
from typing import Dict
from config import Config
from commons.models import Order, Position
from commons.enums import BrokerType
from errors.system_defined import NotSupportedError, UnknownError
from brokers import xts, dummy
from brokers.utils import slice_order


logger = logging.getLogger(__name__)

output_queue = Queue()


def get_fund():
    try:
        if Config.BROKER == BrokerType.XTS.name:
            return xts.get_fund()
        elif Config.BROKER == BrokerType.DUMMY.name:
            return dummy.get_fund()
        else:
            raise NotSupportedError(f"{Config.BROKER} is not supported")
    except:
        raise UnknownError()


def place_order(order: Order, lot_size: int, freeze_qty: int):
    logger.info(f"Place order with id {order.id}")
    logger.debug(f"Order details: {order}")
    try:
        if Config.BROKER == BrokerType.DUMMY.name:
            broker_order_id = dummy.place_order(order)
            order.broker_order_id  = broker_order_id
            order.child_orders[order.broker_order_id] = order
            return
        slice_order(order, lot_size, freeze_qty)
        placed_child_orders = []
        for child_order in order.child_orders.values(): 
            if Config.BROKER == BrokerType.XTS.name:
                broker_order_id = xts.place_order(child_order)
                child_order.broker_order_id  = broker_order_id
                placed_child_orders.append(child_order)
            else:
                raise NotSupportedError(f"{Config.BROKER} is not supported")
        order.child_orders.clear()
        for placed_child_order in placed_child_orders:
            order.child_orders[placed_child_order.broker_order_id] = placed_child_order
    except:
        raise UnknownError()


def modify_order(broker_order_id: str):
    logger.info(f"Modify order with id {broker_order_id}")
    try:
        if Config.BROKER == BrokerType.XTS.name:
            xts.modify_order(broker_order_id)
        elif Config.BROKER == BrokerType.DUMMY.name:
            dummy.modify_order(broker_order_id)
        else:
            raise NotSupportedError(f"{Config.BROKER} is not supported")
    except:
        raise UnknownError()


def cancel_order(broker_order_id: str):
    logger.info(f"Cancel order with id {broker_order_id}")
    try:
        if Config.BROKER == BrokerType.XTS.name:
            xts.cancel_order(broker_order_id)
        elif Config.BROKER == BrokerType.DUMMY.name:
            dummy.cancel_order(broker_order_id)
        else:
            raise NotSupportedError(f"{Config.BROKER} is not supported")
    except:
        raise UnknownError()


def get_order_details(broker_order_id: str):
    logger.info(f"Get order details with id {broker_order_id}")
    try:
        if Config.BROKER == BrokerType.XTS.name:
            xts.get_order_details(broker_order_id)
        elif Config.BROKER == BrokerType.DUMMY.name:
            dummy.get_order_details(broker_order_id)
        else:
            raise NotSupportedError(f"{Config.BROKER} is not supported")
    except:
        raise UnknownError()
    

def fetch_orderbook():
    try:
        if Config.BROKER == BrokerType.XTS.name:
            xts.fetch_orderbook()
        elif Config.BROKER == BrokerType.DUMMY.name:
            dummy.fetch_orderbook()
        else:
            raise NotSupportedError(f"{Config.BROKER} is not supported")
    except Exception as ex:
        logger.warning(f"Error in fetch_orderbook {ex}")

    
def sync_position(position: Position):
    try:
        if Config.BROKER == BrokerType.XTS.name:
            xts.sync_position(position)
        elif Config.BROKER == BrokerType.DUMMY.name:
            dummy.sync_position(position)
        else:
            raise NotSupportedError(f"{Config.BROKER} is not supported")
    except Exception as ex:
        raise ex
