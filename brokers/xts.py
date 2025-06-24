import logging
import requests
from copy import deepcopy
from datetime import datetime
from typing import Dict
from commons.enums import BrokerType, OrderStatus, OrderType, PositionStatus, ExchangeType, LogType
from commons.models import Order, OrderUpdate, Position, PositionType, Instrument
from data import Cache
from config import Config
from data import Cache
from engine.utils import get_instrument_by_token
from errors.system_defined import BrokerError
import pricefeed
# import log_manager

logger = logging.getLogger(__name__)

orders: Dict[str, Order] = {}


def host_lookup():
    if not Config.HOST_LOOKUP:
        return
    url = Config.HOST_LOOKUP
    payload = {
        "accesspassword": "2021HostLookUpAccess",
        "version": "interactive_1.0.1",
    }
    logger.debug(f"Payload: {payload}")
    response = requests.post(url, json=payload, timeout=Config.EXTERNAL_REQUEST_TIMEOUT)
    logger.debug(f"Response: {response.text}")
    if response.status_code == 200 and response.json()["type"] == True:
        response_json = response.json()
        Config.LOOKUP_KEY = response_json["result"]["uniqueKey"]
        Config.BASE_URL = response_json["result"]["connectionString"]
    else:
        error_message = response.json()["description"]
        raise Exception(error_message)


def login():
    if Config.BROKER == BrokerType.DUMMY.name:
        return
    host_lookup()
    url = Config.BASE_URL + "/user/session"
    headers = {"Content-Type": "application/json"}
    payload = {
        "appKey": Config.API_KEY,
        "secretKey": Config.API_SECRET,
        "source": "WebAPI",
        "uniqueKey": Config.LOOKUP_KEY,
    }
    logger.debug(f"Payload: {payload}")
    response = requests.post(
        url, json=payload, headers=headers, timeout=Config.EXTERNAL_REQUEST_TIMEOUT
    )
    logger.debug(f"Response: {response.text}")
    if response.status_code == 200 and response.json()["type"] == "success":
        response_json = response.json()
        Config.ACCESS_TOKEN = response_json["result"]["token"]
        return True
    else:
        error_message = response.json()["description"]
        raise Exception(error_message)


def logout():
    return True


def get_fund():
    url = Config.BASE_URL + f"/user/balance?clientID={Config.XTS_CLIENT_ID}"
    headers = {
        "Content-Type": "application/json",
        "authorization": Config.ACCESS_TOKEN,
    }
    try:
        response = requests.get(url, headers=headers, timeout=Config.EXTERNAL_REQUEST_TIMEOUT)
        response.raise_for_status()
        limits = response.json()["result"]["BalanceList"][0]["limitObject"]
        net_margin_available = float(limits['RMSSubLimits']['netMarginAvailable'])
        margin_utilized = float(limits['RMSSubLimits']['marginUtilized'])
        Cache().push("netMarginAvailable", net_margin_available)
        Cache().push("marginUtilized", margin_utilized)
    except Exception as ex:
        logger.debug(f"Error in get fund={ex}")
        net_margin_available = float(Cache().pull("netMarginAvailable"))
        margin_utilized = float(Cache().pull("marginUtilized"))
        
    return net_margin_available, margin_utilized


def place_order(order: Order):
    client_id = "*****" if Config.IS_PRO_ID else Config.XTS_CLIENT_ID
    url = Config.BASE_URL + f"/orders?clientID={client_id}"
    headers = {
        "Content-Type": "application/json",
        "authorization": Config.ACCESS_TOKEN,
    }
    instrument: Instrument = Cache().pull(order.instrument_id)
    exchange = instrument.exchange
    if exchange == ExchangeType.NFO:
        exchange = "NSEFO"
    else:
        exchange = "BSEFO"
        
    payload = {
        "exchangeSegment": exchange,
        "exchangeInstrumentID": instrument.exchange_token,
        "productType": order.product_type.name,
        "orderType": order.order_type.name,
        "orderSide": order.side.name,
        "disclosedQuantity": 0,
        "orderQuantity": order.quantity,
        "limitPrice": order.limit_price,
        "stopPrice": order.trigger_price,
        "orderUniqueIdentifier": "OnlyBroker",
        "timeInForce": "DAY",
        "clientID": client_id
    }
    logger.debug(f"Payload: {payload}")
    response = requests.post(
        url, headers=headers, json=payload, timeout=Config.EXTERNAL_REQUEST_TIMEOUT
    )
    logger.debug(f"Response: {response.text}")
    if response.status_code == 200 and response.json()["type"] == "success":
        broker_order_id = response.json()["result"]["AppOrderID"]
        order.status = OrderStatus.WORKING
        orders[broker_order_id] = deepcopy(order)
        return broker_order_id
    else:
        error_message = response.json()["description"]
        raise Exception(error_message)


def modify_order(broker_order_id: str, modified_order: Order):
    client_id = "*****" if Config.IS_PRO_ID else Config.XTS_CLIENT_ID
    url = Config.BASE_URL + f"/orders?clientID={client_id}"
    headers = {
        "Content-Type": "application/json",
        "authorization": Config.ACCESS_TOKEN,
    }
    payload = {
        "appOrderID": broker_order_id,
        "modifiedProductType": modified_order.product_type.name,
        "modifiedOrderType": modified_order.order_type.name,
        "modifiedOrderQuantity": modified_order.quantity,
        "modifiedDisclosedQuantity": 0,
        "modifiedLimitPrice": modified_order.limit_price,
        "modifiedStopPrice": modified_order.trigger_price,
        "modifiedTimeInForce": "DAY",
        "clientID": client_id,
    }
    logger.debug(f"Payload: {payload}")
    response = requests.put(
        url, headers=headers, json=payload, timeout=Config.EXTERNAL_REQUEST_TIMEOUT
    )
    logger.debug(f"Response: {response.text}")
    if response.status_code == 200 and response.json()["type"] == "success":
        return True


def cancel_order(broker_order_id: str):
    client_id = "*****" if Config.IS_PRO_ID else Config.XTS_CLIENT_ID
    url = (
        Config.BASE_URL
        + f"/orders?clientID={client_id}&appOrderID="
        + broker_order_id
    )
    headers = {
        "Content-Type": "application/json",
        "authorization": Config.ACCESS_TOKEN,
    }
    response = requests.delete(
        url, headers=headers, timeout=Config.EXTERNAL_REQUEST_TIMEOUT
    )
    logger.debug(f"Response: {response.text}")
    if response.status_code == 200 and response.json()["type"] == "success":
        return True
    else:
        error_message = response.json()["description"]
        raise Exception(error_message)


def get_order_details(broker_order_id: str):
    url = (
        Config.BASE_URL
        + f"/orders?clientID={Config.XTS_CLIENT_ID}&appOrderID="
        + broker_order_id
    )
    headers = {
        "Content-Type": "application/json",
        "authorization": Config.ACCESS_TOKEN,
    }
    response = requests.get(url, headers=headers, timeout=10)
    logger.debug(f"Response {response.text}")
    if response.status_code == 200 and response.json()["type"] == "success":
        response_json = response.json()
        latest_update = response_json["result"][-1]
        order_status = latest_update["OrderStatus"]
        if order_status == "Filled":
            status = OrderStatus.FILLED
        elif order_status == "Rejected":
            status = OrderStatus.CANCELLED
            error_code = 9017
            error_message = latest_update["CancelRejectReason"]
        elif order_status == "Cancelled":
            status = OrderStatus.CANCELLED
            error_code = 9017
            error_message = latest_update["CancelRejectReason"]
        last_update_time = datetime.strptime(
            latest_update["ExchangeTransactTime"], "%d-%m-%Y %H:%M:%S"
        )
        if (
            "OrderAverageTradedPrice" in latest_update
            and latest_update["OrderAverageTradedPrice"] != ""
        ):
            average_trade_price = float(latest_update["OrderAverageTradedPrice"])
        if (
            "CumulativeQuantity" in latest_update
            and latest_update["CumulativeQuantity"] != ""
        ):
            traded_quantity = int(latest_update["CumulativeQuantity"])

    else:
        error_code = 9999
        error_message = response.json()["description"]

    return OrderUpdate(
        broker_order_id,
        average_trade_price,
        traded_quantity,
        status,
        last_update_time,
        error_code,
        error_message,
    )


def fetch_orderbook():
    
    if Config.IS_DEALER_API:
        url = Config.BASE_URL + f"/orders/dealerorderbook"
    else:
        url = Config.BASE_URL + "/orders?clientID=*****"

    headers = {
        "Content-Type": "application/json",
        "authorization": Config.ACCESS_TOKEN,
    }

    response = requests.get(url, headers=headers, json={"clientID": Config.XTS_CLIENT_ID}, timeout=10)
    
    # logger.debug(f"Response {response.text}")
    if response.status_code == 200 and response.json()["type"] == "success":
        response_json = response.json()
        broker_orders = response_json["result"]
        for broker_order in broker_orders:
            broker_order_id = broker_order["AppOrderID"]
            if broker_order_id not in orders:
                continue
            order_with_us = orders[broker_order_id]
            order_with_us.broker_order_id = broker_order_id
            if order_with_us.status not in [OrderStatus.OPEN, OrderStatus.WORKING]:
                continue
            order_status = broker_order["OrderStatus"]
            if order_status == "Filled":
                order_with_us.status = OrderStatus.FILLED
            elif order_status == "Rejected":
                order_with_us.status = OrderStatus.REJECTED
                order_with_us.error_code = 9017
                order_with_us.error_message = broker_order["CancelRejectReason"]
            elif order_status == "Cancelled":
                order_with_us.status = OrderStatus.CANCELLED
                order_with_us.error_code = 9017
                order_with_us.error_message = broker_order["CancelRejectReason"]
            order_with_us.last_update_time = datetime.strptime(
                broker_order["ExchangeTransactTime"], "%d-%m-%Y %H:%M:%S"
            )
            if (
                "OrderAverageTradedPrice" in broker_order
                and broker_order["OrderAverageTradedPrice"] != ""
            ):
                order_with_us.average_trade_price = float(
                    broker_order["OrderAverageTradedPrice"]
                )
            if (
                "CumulativeQuantity" in broker_order
                and broker_order["CumulativeQuantity"] != ""
            ):
                order_with_us.traded_quantity = int(broker_order["CumulativeQuantity"])

            logger.debug(
                {
                    "id": order_with_us.id,
                    "instrument_id": order_with_us.instrument_id,
                    "product_type": order_with_us.product_type.name,
                    "order_type": order_with_us.order_type.name,
                    "side": order_with_us.side.name,
                    "limit_price": order_with_us.limit_price,
                    "trigger_price": order_with_us.trigger_price,
                    "quantity": order_with_us.quantity,
                    "creation_time": order_with_us.creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "broker_order_id": order_with_us.broker_order_id,
                    "average_trade_price": order_with_us.average_trade_price,
                    "traded_quantity": order_with_us.traded_quantity,
                    "status": order_with_us.status.name,
                    "error_code": order_with_us.error_code,
                    "error_message": order_with_us.error_message,
                    "last_update_time": order_with_us.last_update_time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )
            instrument = get_instrument_by_token(order_with_us.instrument_id)
            logger.info(f"{instrument.trading_symbol} :: Status={order_with_us.status.name}, Side={order_with_us.side.name}, Traded-Qty={order_with_us.traded_quantity}, Traded-Price={order_with_us.average_trade_price}, Limit-Price={order_with_us.limit_price}")
    else:
        error_message = response.text
        logger.info(error_message)


def sync_position(position: Position):
    net_buy_qty = 0
    net_sell_qty = 0
    buy_prices = []
    buy_quantities = []
    sell_pricess = []
    sell_quantities = []
    modify_orders = []
    for order in position.orders:
        for child_order in list(order.child_orders.values()):
            if child_order.broker_order_id in orders:
                broker_order = orders[child_order.broker_order_id]
                child_order.traded_quantity = broker_order.traded_quantity
                child_order.average_trade_price = broker_order.average_trade_price
                if child_order.side == PositionType.BUY:
                    net_buy_qty += child_order.traded_quantity
                    buy_quantities.append(child_order.traded_quantity)
                    buy_prices.append(child_order.average_trade_price)
                else:
                    net_sell_qty += child_order.traded_quantity
                    sell_quantities.append(child_order.traded_quantity)
                    sell_pricess.append(child_order.average_trade_price)
                child_order.status = broker_order.status
                if child_order.status in [OrderStatus.REJECTED, OrderStatus.CANCELLED]:
                    logger.debug(f"{child_order.status} :: {child_order}")
                    position.status = PositionStatus.ERROR
                    child_order.error_code = broker_order.error_code
                    child_order.error_message = broker_order.error_message
                    raise BrokerError(
                        f"Order {child_order.broker_order_id} rejected with {child_order.error_message}"
                    )
                if child_order.status == OrderStatus.WORKING:
                    modify_orders.append(child_order.broker_order_id)
    
    if modify_orders:
        ltp = pricefeed.get_quote(position.instrument_id)
        for order in position.orders:
            for child_order in order.child_orders.values():
                if child_order.broker_order_id in modify_orders:
                    child_order.limit_price = ltp
                    modify_order(child_order.broker_order_id, child_order)

    if (
        net_buy_qty == position.net_buy_quantity
        and net_sell_qty == position.net_sell_quantity
    ):
        if buy_prices:
            position.buy_average_price = sum([buy_prices[i]*buy_quantities[i] for i in range(len(buy_prices))])/sum(buy_quantities)
        if sell_pricess:
            position.sell_average_price = sum([sell_pricess[i]*sell_quantities[i] for i in range(len(sell_pricess))])/sum(sell_quantities)
        logger.debug(f"{position.instrument_id}::Buy prices={buy_prices}, Buy quantities={buy_quantities}, Sell prices={sell_pricess}, Sell quantities={sell_quantities}")
        position.buy_value = position.buy_average_price * position.net_buy_quantity
        position.sell_value = position.sell_average_price * position.net_sell_quantity
        position.net_quantity = net_buy_qty - net_sell_qty
        position.status = PositionStatus.COMPLETE
    else:
        logger.debug(f"instrument_id={position.instrument_id}, position_net_buy_qty={position.net_buy_quantity}, net_buy_qty={net_buy_qty}, position_net_sell_qty={position.net_sell_quantity}, net_sell_qty={net_sell_qty}")

    if (position.net_buy_quantity) and (net_buy_qty == net_sell_qty):
        pnl_instrument = get_instrument_by_token(position.instrument_id)
        logger.debug(f"Instrument(strike={pnl_instrument.strike_price}, option_type={pnl_instrument.option_type.name}), instrument_id={position.instrument_id}, avg sell price={position.sell_average_price}, avg buy value={position.buy_average_price}, total qty={net_buy_qty}, pnl={round(position.sell_value - position.buy_value, 4)}")