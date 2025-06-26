import datetime
import json
import uuid
from commons.enums import InstrumentType, Message, MessageType, OptionType, OrderType, PositionStatus, PositionType, StrategyStatus, SlTgType
from errors.system_defined import BrokerError
from pricefeed import get_quote
from commons.utils import get_current_time_int, calc_by_points, calc_by_percentage
from commons.models import Order, Position, Strategy, DummyStrategy
from config import Config
from data.models import Cache
from engine.utils import calculate_pnl, check_shift, get_instrument, get_instrument_by_price, get_instrument_by_token, get_required_margin, get_required_margin_for_position, get_atm
import logging
from brokers import fetch_orderbook, get_fund, place_order, sync_position
import user_com
from commons.constants import STRIKE_DIFF

logger = logging.getLogger(__name__)

def evaluate(strategy: DummyStrategy, ltp: float, underlying_expiry: int):
    if strategy.status == StrategyStatus.CREATED:
        if int(strategy.range_start_time) <= get_current_time_int() <= int(strategy.range_end_time):
            if strategy.underlying_high == None and strategy.underlying_low == None:
                strategy.underlying_high = ltp
                strategy.underlying_low = ltp
                
            if ltp > strategy.underlying_high:
                strategy.underlying_high = ltp

            elif ltp < strategy.underlying_low:
                strategy.underlying_low = ltp

        elif get_current_time_int() > int(strategy.range_end_time):
            logger.info("Strategy Range time is Ended")

            if (strategy.underlying_high is not None) and (strategy.underlying_low is not None):
                if ltp > strategy.underlying_high:
                    strike_price = get_atm(ltp, STRIKE_DIFF.get(f'{strategy.underlying.value}'))
                    instrument = get_instrument(
                        strategy.underlying,
                        InstrumentType.OPTIDX,
                        underlying_expiry,
                        strike_price,
                        OptionType.CE
                        )
                    
                    logger.info(f"High Break at ltp: {ltp} : High : {strategy.underlying_high} : instrument : {instrument}")
                
                    call_order = Order(
                        uuid.uuid4().hex,
                        strategy.id,
                        instrument.pricefeed_token,
                        Config.PRODUCT_TYPE,
                        Config.ORDER_TYPE,
                        PositionType.BUY,
                        0,
                        0,
                        strategy.lots * strategy.lots_size
                    )

                    strategy.position = Position(
                        call_order.id,
                        call_order.instrument_id
                    )

                    place_order(
                        call_order, 
                        strategy.lots_size, 
                        strategy.freeze_qty
                    )

                    strategy.position.net_buy_quantity = call_order.quantity
                    strategy.position.orders.append(call_order)

                    strategy.status = StrategyStatus.RUNNING

                    logger.info(f"Order Placed for CE {instrument.trading_symbol}")

                
                elif ltp < strategy.underlying_low:
                    strike_price = get_atm(ltp, STRIKE_DIFF.get(f'{strategy.underlying.value}'))
                    instrument = get_instrument(
                        strategy.underlying,
                        InstrumentType.OPTIDX,
                        underlying_expiry,
                        strike_price,
                        OptionType.PE
                        )
                    
                    logger.info(f"Low Break at ltp: {ltp} : Low  : {strategy.underlying_low} : instrument : {instrument}")

                    put_order = Order(
                        uuid.uuid4().hex,
                        strategy.id,
                        instrument.pricefeed_token,
                        Config.PRODUCT_TYPE,
                        Config.ORDER_TYPE,
                        PositionType.BUY,
                        0,
                        0,
                        strategy.lots * strategy.lots_size
                    )

                    strategy.position = Position(
                        put_order.id,
                        put_order.instrument_id
                    )

                    place_order(put_order, strategy.lots_size, strategy.freeze_qty)

                    strategy.position.net_sell_quantity = put_order.quantity
                    strategy.position.orders.append(put_order)

                    strategy.status = StrategyStatus.RUNNING

                    logger.info(f"Order Placed for PE {instrument.trading_symbol}")

        logger.info(f"High: {strategy.underlying_high} Low: {strategy.underlying_low} LTP : {ltp}") 

    elif strategy.status == StrategyStatus.RUNNING:

        if get_current_time_int() > int(strategy.range_end_time):
            if strategy.sl_tg_type is not None:
                if strategy.sl_tg_type  == SlTgType.POINTS:
                    if strategy.strategy_target is not None:
                        limit_value = calc_by_points(strategy.underlying_high, strategy.strategy_target)
                else:
                    ...


        if get_current_time_int() > int(strategy.strategy_end_time):
            logger.info(f"Current Time exceeded the Strategy End Time !")

            position_to_squareoff = strategy.position
            adjustment_qty = strategy.lots * strategy.lots_size # CURRENTLY NOT DEALING WITH NET QTY.

            ltp = get_quote(position_to_squareoff.instrument_id) # ORDER_TYPE = MARKET
            new_order = Order(
                uuid.uuid4().hex,
                strategy.id,
                position_to_squareoff.instrument_id,
                Config.PRODUCT_TYPE,
                Config.ORDER_TYPE,
                PositionType.SELL,
                ltp,
                0,
                adjustment_qty
            )
            place_order(new_order, strategy.lots_size, strategy.freeze_qty)
            position_to_squareoff.net_buy_quantity += adjustment_qty
            position_to_squareoff.orders.append(new_order)
            position_to_squareoff.status = PositionStatus.PENDING

            strategy.status = StrategyStatus.SQUARING_OFF

def sync_positions(strategy: DummyStrategy):
    fetch_orderbook()
    if strategy.status in [StrategyStatus.RUNNING, StrategyStatus.SQUARED_OFF]:
        if strategy.position:
            sync_position(strategy.position) 


def is_completed(strategy: DummyStrategy):
    return True