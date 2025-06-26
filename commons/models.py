from datetime import datetime
import time
from typing import List, Dict
from commons.constants import FREEZE_QTY
from commons.enums import (
    StrategyStatus,
    Underlying,
    InstrumentType,
    OptionType,
    ExchangeType,
    ProductType,
    OrderType,
    PositionType,
    OrderStatus,
    PositionStatus,
    ExpiryType
)

from commons.constants import (
    MARKET_END_TIME
)

class Singleton(object):
    _instance = None
    def __new__(class_, *args, **kwargs):
        if not isinstance(class_._instance, class_):
            class_._instance = object.__new__(class_, *args, **kwargs)
        return class_._instance


class Ohlc:
    def __init__(self, token: str, ltp: float):
        self.token = token
        self.ltp = ltp

    def __str__(self) -> str:
        return f"Ohlc(token: {self.token}, ltp: {self.ltp})"


class Instrument:
    def __init__(
        self,
        pricefeed_token: str,
        exchange_token: str,
        exchange: ExchangeType,
        underlying: Underlying,
        instrument_type: InstrumentType,
        expiry_date: datetime,
        strike_price: float,
        option_type: OptionType,
        trading_symbol: str,
        lot_size: int = 1,
    ):
        self.pricefeed_token = pricefeed_token
        self.exchange_token = exchange_token
        self.exchange = exchange
        self.underlying = underlying
        self.instrument_type = instrument_type
        self.expiry_date = expiry_date
        self.strike_price = strike_price
        self.option_type = option_type
        self.trading_symbol = trading_symbol
        self.lot_size = lot_size
        
    def __str__(self):
        return f"Instrument(pricefeed_token={self.pricefeed_token}, exchange_token={self.exchange_token}, exchange={self.exchange}, underlying={self.underlying}, instrument_type={self.instrument_type}, expiry_date={self.expiry_date}, strike_price={self.strike_price}, option_type={self.option_type}, trading_symbol={self.trading_symbol})"


class OrderConfig:
    def __init__(
        self,
        product_type: ProductType,
    ):
        self.product_type = product_type


class UserInstance:
    def __init__(self, id: str):
        self.id = id
        self.strategy = None


class Position:
    def __init__(self, initial_order_id: str, instrument_id: str):
        self.initial_order_id = initial_order_id
        self.instrument_id = instrument_id
        self.net_buy_quantity = 0
        self.buy_average_price = 0
        self.buy_value = 0
        self.net_sell_quantity = 0
        self.sell_average_price = 0
        self.sell_value = 0
        self.net_quantity = 0
        
        self.status = PositionStatus.PENDING
        self.ltp = None
        self.orders: List[Order] = []


class Order:
    def __init__(
        self,
        id: str,
        strategy_id: str,
        intstrument_id: str,
        product_type: ProductType,
        order_type: OrderType,
        side: PositionType,
        limit_price: float,
        trigger_price: float,
        quantity: int,
    ):
        self.id = id
        self.strategy_id = strategy_id
        self.instrument_id = intstrument_id
        self.product_type = product_type
        self.order_type = order_type
        self.side = side
        self.limit_price = limit_price
        self.trigger_price = trigger_price
        self.quantity = quantity
        self.creation_time = datetime.now()
        self.broker_order_id = None
        self.average_trade_price = 0.0
        self.traded_quantity = 0
        self.status = OrderStatus.CREATED
        self.error_code = 0
        self.error_message = None
        self.last_update_time = datetime.now()
        self.child_orders: Dict[str, Order] = {}
        
    def __str__(self):
        return f"Order(id={self.id}, strategy_id={self.strategy_id}, instrument_id={self.instrument_id}, product_type={self.product_type.name}, order_type={self.order_type.name}, side={self.side.name}, limit_price={self.limit_price}, trigger_price={self.trigger_price}, quantity={self.quantity}, creation_time={self.creation_time}, broker_order_id={self.broker_order_id}, average_trade_price={self.average_trade_price}, traded_quantity={self.traded_quantity}, status={self.status}, error_code={self.error_code}, error_message={self.error_message}, last_update_time={self.last_update_time}"

    def __repr__(self):
        return f"Order(id={self.id}, strategy_id={self.strategy_id}, instrument_id={self.instrument_id}, product_type={self.product_type.name}, order_type={self.order_type.name}, side={self.side.name}, limit_price={self.limit_price}, trigger_price={self.trigger_price}, quantity={self.quantity}, creation_time={self.creation_time}, broker_order_id={self.broker_order_id}, average_trade_price={self.average_trade_price}, traded_quantity={self.traded_quantity}, status={self.status}, error_code={self.error_code}, error_message={self.error_message}, last_update_time={self.last_update_time}"


class OrderUpdate:
    def __init__(
        self,
        broker_order_id: str,
        average_trade_price: float,
        traded_quantity: int,
        status: OrderStatus,
        last_update_time: str,
        error_code: int = 0,
        error_message: str = "",
    ):
        self.broker_order_id = broker_order_id
        self.average_trade_price = average_trade_price
        self.traded_quantity = traded_quantity
        self.status = status
        self.last_update_time = last_update_time
        self.error_code = error_code
        self.error_message = error_message

    def json(self):
        return {
            "broker_order_id": self.broker_order_id,
            "average_trade_price": self.average_trade_price,
            "traded_quantity": self.traded_quantity,
            "status": self.status,
            "last_update_time": self.last_update_time,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class Strategy:
    def __init__(
        self,
        fe_id:str,
        id: str,
        underlying: Underlying,
        expiry_type: ExpiryType,
        lots: int,
        lot_size: int,
        hedge_premium: float,
        hedge_comp_op: str,
        open_hedges: bool,
        call_strike: float,
        put_strike: float,
        sq_off_on_shift_after_same_strike: bool,
        strike_diff_percentage: float,
        shift_diff_multiplier: float,
        shift_delay: float,
        take_profit: float,
        stop_loss: float,
        sq_off_time: float,
        reduce_qty_percentage: float,
        no_shift_if_ltp_below_price: bool
    ):
        self.fe_id = fe_id
        self.id = id
        self.underlying = underlying
        self.expiry_type = expiry_type
        self.lots = lots
        self.lot_size = lot_size
        self.hedge_premium = hedge_premium
        self.hedge_comp_op = hedge_comp_op
        self.open_hedges = open_hedges
        self.call_strike = call_strike
        self.put_strike = put_strike
        self.sq_off_on_shift_after_same_strike = sq_off_on_shift_after_same_strike
        self.strike_diff_percentage = strike_diff_percentage
        self.shift_diff_multiplier = shift_diff_multiplier
        self.shift_delay = shift_delay
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.sq_off_time = sq_off_time
        self.reduce_qty_percentage = reduce_qty_percentage
        self.no_shift_if_ltp_below_price = no_shift_if_ltp_below_price

        self.reducing_qty = False
        self.shift_start_timestamp = None
        self.checking_shift_delay = False
        self.check_shift = True
        self.freeze_qty = FREEZE_QTY[self.underlying.name][self.expiry_type.name]
        self.call_position: Position = None
        self.put_position: Position = None
        self.call_hedge_position: Position = None
        self.put_hedge_position: Position = None
        self.archived_positions: List[Position] = []
        self.sq_off_triggerd = False

        self.ongoing_shift = False
        self.option_to_shift = None

        self.last_sync_time = time.time()
        self.status: StrategyStatus = StrategyStatus.CREATED
        self.message: str = None

    def __str__(self):
        return (
            f"Strategy(fe_id={self.fe_id}, id={self.id}, underlying={self.underlying}, expiry_type={self.expiry_type}, "
            f"lots={self.lots}, lot_size={self.lot_size}, hedge_premium={self.hedge_premium}, hedge_comp_op={self.hedge_comp_op}, "
            f"open_hedges={self.open_hedges}, call_strike={self.call_strike}, put_strike={self.put_strike}, no_shift_if_ltp_below_price={self.no_shift_if_ltp_below_price}, "
            f"sq_off_on_shift_after_same_strike={self.sq_off_on_shift_after_same_strike}, strike_diff_percentage={self.strike_diff_percentage}, shift_diff_multiplier={self.shift_diff_multiplier}, shift_delay={self.shift_delay}, take_profit={self.take_profit}, stop_loss={self.stop_loss}, "
            f"sq_off_time={self.sq_off_time}, reduce_qty_percentage={self.reduce_qty_percentage}, status={self.status}, message={self.message})"
        )

    def __repr__(self):
        return (
            f"Strategy(fe_id={self.fe_id}, id={self.id!r}, underlying={self.underlying!r}, expiry_type={self.expiry_type!r}, "
            f"lots={self.lots}, lot_size={self.lot_size}, hedge_premium={self.hedge_premium}, hedge_comp_op={self.hedge_comp_op}, "
            f"open_hedges={self.open_hedges}, call_strike={self.call_strike}, put_strike={self.put_strike}, no_shift_if_ltp_below_price={self.no_shift_if_ltp_below_price}, "
            f"sq_off_on_shift_after_same_strike={self.sq_off_on_shift_after_same_strike}, strike_diff_percentage={self.strike_diff_percentage}, shift_diff_multiplier={self.shift_diff_multiplier}, shift_delay={self.shift_delay}, take_profit={self.take_profit}, stop_loss={self.stop_loss}, "
            f"sq_off_time={self.sq_off_time}, reduce_qty_percentage={self.reduce_qty_percentage}, status={self.status!r}, message={self.message})"
        )


class DummyStrategy:
    def __init__(
        self,
        id: str,
        underlying: Underlying,
        expirytype: ExpiryType,
        range_start_time: str,
        range_end_time: str,
        strategy_end_time: str,
        lots: int,
        lots_size: int,
        strategy_target: str,
        strategy_stoploss: str,
        underlying_high: float = None,
        underlying_low: float = None,
        freeze_qty: int = None,
        # position: Position = None
   

    ):
        self.id = id
        self.underlying = underlying
        self.expirytype = expirytype
        self.range_start_time = range_start_time
        self.range_end_time = range_end_time
        self.strategy_end_time = strategy_end_time
        self.lots = lots
        self.lots_size = lots_size
        self.strategy_target = strategy_target
        self.strategy_stoploss = strategy_stoploss
        self.underlying_high = underlying_high
        self.underlying_low = underlying_low
        self.freeze_qty = freeze_qty
        self.position:Position = None 

        self.last_sync_time = time.time()
        self.status: StrategyStatus = StrategyStatus.CREATED
    

    def __str__(self):
        return (
        f"DummyStrategy(id={self.id}, underlying={self.underlying}, expiry_type={self.expirytype}), "
        f"lots={self.lots}, lots_size={self.lots_size}, freeze_qty={self.freeze_qty}"
        f"square_off(Strategy_end_time={self.strategy_end_time}, strategy_target={self.strategy_target}, strategy_stoploss={self.strategy_stoploss}"
        )

    
    def __repr__(self):
        return (
        f"DummyStrategy(id={self.id}, underlying={self.underlying}, expiry_type={self.expirytype}), "
        f"lots={self.lots}, lots_size={self.lots_size}, freeze_qty={self.freeze_qty}"
        f"square_off(Strategy_end_time={self.strategy_end_time}, strategy_target={self.strategy_target}, strategy_stoploss={self.strategy_stoploss}"
        )
