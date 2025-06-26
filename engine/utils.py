from datetime import datetime
import json
import logging
import time
from typing import List, Tuple, Dict 
import uuid
import requests
from commons.constants import LOT_SIZE, STRATEGY_PATH, FREEZE_QTY
from commons.enums import (
    ExchangeType,
    ExpiryType,
    InstrumentType,
    LogType,
    MessageType,
    Underlying,
    OptionType
)
import uuid
from commons.models import Instrument, Ohlc, Strategy, DummyStrategy
from commons.utils import generate_trading_symbol, round_to, get_cache_data, get_underlying_expiry
from data.models import Cache
import pricefeed
from config import Config
from user_com import push_message
import user_com

logger = logging.getLogger(__name__)

def get_atm(ltp: float, strike_diff: int):
    return round_to(ltp, strike_diff)


def get_pricefeed_token(instrument_token):
    return Cache().pull(instrument_token).pricefeed_token


def get_instrument_by_token(instrument_token) -> Instrument:
    instrument_data = Cache().pull(instrument_token)
    return instrument_data


def get_instrument(
    underlying: Underlying,
    instrument_type: InstrumentType,
    expiry_int: int,
    strike_price: float,
    option_type: OptionType,
) -> Instrument:
    exchange = ExchangeType.NFO
    return Cache().pull(
        generate_trading_symbol(
            exchange.name,
            underlying.name,
            instrument_type.name,
            expiry_int,
            strike_price,
            option_type.name,
        )
    )


def get_instrument_by_price(
    underlying: Underlying,
    expiry_type: ExpiryType,
    option_type: OptionType,
    option_premium: float,
    option_comp_op: str,
) -> Instrument:
    expiry_int = Cache().pull(f"{underlying.name}_{expiry_type.name}")
    expiry = datetime.strptime(
        str(Cache().pull(f"{underlying.name}_{expiry_type.name}")),
        "%y%m%d",
    ).strftime("%Y-%m-%d")
    minimum_distance = float("inf")
    selected_hedge_strike = None
    if option_comp_op == "=":
        sorted_by_premium = dict(
            sorted(
                pricefeed.get_option_chain(underlying.name, expiry)[
                    option_type.name
                ].items(),
                key=lambda item: item[1],
                reverse=True,
            )
        )
        for strike, ltp in sorted_by_premium.items():
            if abs(ltp - option_premium) < minimum_distance:
                selected_hedge_strike = strike
                minimum_distance = abs(ltp - option_premium)
    elif option_comp_op == ">=":
        sorted_by_premium = dict(
            sorted(
                pricefeed.get_option_chain(underlying.name, expiry)[
                    option_type.name
                ].items(),
                key=lambda item: item[1],
                reverse=True,
            )
        )
        for strike, ltp in sorted_by_premium.items():
            if ltp >= option_premium:
                selected_hedge_strike = strike

    elif option_comp_op == "<=":
        sorted_by_premium = dict(
            sorted(
                pricefeed.get_option_chain(underlying.name, expiry)[
                    option_type.name
                ].items(),
                key=lambda item: item[1],
                reverse=True,
            )
        )
        for strike, ltp in sorted_by_premium.items():
            if ltp <= option_premium:
                selected_hedge_strike = strike
                break

    exchange = ExchangeType.NFO
    hedge_trading_symbol = generate_trading_symbol(
        exchange.name,
        underlying.name,
        InstrumentType.OPTIDX.name,
        expiry_int,
        selected_hedge_strike,
        option_type.name,
    )
    hedge_instrument: Instrument = Cache().pull(hedge_trading_symbol)
    # if not hedge_instrument:
    #     raise StrikeNotFound(f"Unable to get token for: {hedge_trading_symbol}")
    return hedge_instrument


def parse_strategy(strategy_json: dict) -> Strategy:
    open_hedges = True if strategy_json["hedge_premium"] else False
    strategy = Strategy(
        strategy_json["fe_id"],
        uuid.uuid4().hex,
        Underlying(strategy_json["underlying"]),
        ExpiryType(strategy_json["expiry_type"]),
        int(strategy_json["lots"]),
        LOT_SIZE[strategy_json["underlying"]],
        float(strategy_json.get("hedge_premium")) if open_hedges else 0,
        strategy_json.get("hedge_comp_op"),
        open_hedges,
        int(strategy_json["call_strike"]),
        int(strategy_json["put_strike"]),
        strategy_json["sq_off_on_shift_after_same_strike"],
        int(strategy_json["strike_diff_percentage"]),
        float(strategy_json["shift_diff_multiplier"]),
        float(strategy_json["shift_delay"]),
        int(strategy_json["take_profit"]),
        -1*float(strategy_json["stop_loss"]),
        float(strategy_json["sq_off_time"]),
        float(strategy_json["reduce_qty_precent"]),
        strategy_json['no_shift_if_ltp_below_price']
    )
    logger.info(strategy)
    return strategy


def get_strategy():
    with open(STRATEGY_PATH, "r") as file:
        strategy_json: Dict = json.load(file)
    return parse_strategy(strategy_json)


def check_shift(strategy: Strategy):
    shift_happend = False
    option_to_shift = None
    new_option = None
    strategy_update = ""
    if not strategy.check_shift:
        return shift_happend, option_to_shift, new_option, strategy_update
    call_ltp = pricefeed.get_quote(strategy.call_position.instrument_id)
    put_ltp = pricefeed.get_quote(strategy.put_position.instrument_id)
    call_instrument = get_instrument_by_token(strategy.call_position.instrument_id)
    put_instrument = get_instrument_by_token(strategy.put_position.instrument_id)
    
    if not call_ltp:
        logger.warning(f"Call: {call_instrument.trading_symbol} LTP is not available")
        return shift_happend, option_to_shift, new_option, strategy_update
    if not put_ltp:
        logger.warning(f"Put: {put_instrument.trading_symbol} LTP is not available")
        return shift_happend, option_to_shift, new_option, strategy_update
    
    if call_ltp <= put_ltp/strategy.shift_diff_multiplier:
        if strategy.no_shift_if_ltp_below_price:
            if strategy.put_position.sell_average_price > put_ltp:
                logger.debug(f'no shifting {strategy.put_position.sell_average_price} > {put_ltp}')
                return shift_happend, option_to_shift, new_option, strategy_update
        old_call_instrument = get_instrument_by_token(strategy.call_position.instrument_id)
        option_to_shift = OptionType.CE
        new_option_ltp = put_ltp - (put_ltp*strategy.strike_diff_percentage)/100
        new_option = get_instrument_by_price(
            strategy.underlying,
            strategy.expiry_type,
            option_to_shift,
            new_option_ltp,
            "<="
        )
        new_option_live_ltp = pricefeed.get_quote(new_option.pricefeed_token)
        logger.debug(f"call_ltp: {call_ltp}, put_ltp: {put_ltp}, new_option_ltp: {new_option_ltp}, new_option: {new_option.trading_symbol}")
        if old_call_instrument.strike_price != new_option.strike_price:
            shift_happend = True
    if put_ltp <= call_ltp/strategy.shift_diff_multiplier:
        if strategy.no_shift_if_ltp_below_price:
            if strategy.call_position.sell_average_price > call_ltp:
                logger.debug(f'no shifting {strategy.call_position.sell_average_price} > {call_ltp}')
                return shift_happend, option_to_shift, new_option, strategy_update
        old_put_instrument = get_instrument_by_token(strategy.put_position.instrument_id)
        option_to_shift = OptionType.PE
        new_option_ltp = call_ltp - (call_ltp*strategy.strike_diff_percentage)/100
        new_option = get_instrument_by_price(
            strategy.underlying,
            strategy.expiry_type,
            option_to_shift,
            new_option_ltp,
            "<="
        )
        new_option_live_ltp = pricefeed.get_quote(new_option.pricefeed_token)
        logger.debug(f"call_ltp: {call_ltp}, put_ltp: {put_ltp}, new_option_ltp: {new_option_ltp}, new_option: {new_option.trading_symbol}")
        if old_put_instrument.strike_price != new_option.strike_price:
            shift_happend = True
    
    if strategy.checking_shift_delay and not shift_happend:
        logger.info("Fake shift happened")
        message = {
            "type": MessageType.STRATEGY_UPDATE,
            "message": f"Fake shift happened."
        }
        user_com.push_message(strategy.fe_id, json.dumps(message))
        strategy.checking_shift_delay = False
        strategy.shift_start_timestamp = None
        shift_happend = False
    
    if not strategy.checking_shift_delay and shift_happend:
        logger.info("Shift delay started")
        message = {
            "type": MessageType.STRATEGY_UPDATE,
            "message": f"Shift delay started."
        }
        user_com.push_message(strategy.fe_id, json.dumps(message))
        strategy.shift_start_timestamp = time.time()
        strategy.checking_shift_delay = True
        shift_happend = False
    
    if strategy.checking_shift_delay:
        if time.time() - strategy.shift_start_timestamp >= strategy.shift_delay:
            strategy.checking_shift_delay = False
            strategy.shift_start_timestamp = None
            shift_happend = True
            if option_to_shift == OptionType.CE:
                log_msg = f"Call Option Shifted: Old CE(Strike={old_call_instrument.strike_price}, LTP={call_ltp}), New CE(Strike={new_option.strike_price}, LTP={new_option_live_ltp}) , Running PE(Strike={new_option.strike_price}, LTP={put_ltp})"
            else:
                log_msg = f"Put Option Shifted: Old PE(Strike={old_put_instrument.strike_price}, LTP={put_ltp}), New PE(Strike={new_option.strike_price}, LTP={new_option_live_ltp}), Running CE(Strike={new_option.strike_price}, LTP={call_ltp})"
            logger.debug(log_msg)
            strategy_update = {
                "type": MessageType.STRATEGY_UPDATE,
                "message": log_msg
            }
        else:
            shift_happend = False

    return shift_happend, option_to_shift, new_option, strategy_update


def calculate_pnl(strategy: DummyStrategy):
    pnl = 0
    positions = {}
    position_count = 0
 
    position = strategy.position
    instrument = get_instrument_by_token(position.instrument_id)

    if position.net_sell_quantity > position.net_buy_quantity:
        realized_pnl = position.net_buy_quantity * (
            position.sell_average_price - position.buy_average_price
        )
        ohlc = Ohlc(
            position.instrument_id,
            pricefeed.get_quote(position.instrument_id),
        )
        if not ohlc.ltp:
            ohlc.ltp = position.sell_average_price
        position.ltp = ohlc.ltp
        unrialized_pnl = (
            position.net_sell_quantity - position.net_buy_quantity
        ) * (position.sell_average_price - ohlc.ltp)
        pnl += realized_pnl + unrialized_pnl
    elif position.net_sell_quantity <= position.net_buy_quantity:
        realized_pnl = position.net_sell_quantity * (
            position.sell_average_price - position.buy_average_price
        )
        ohlc = Ohlc(
            position.instrument_id,
            pricefeed.get_quote(position.instrument_id),
        )
        if not ohlc.ltp:
            ohlc.ltp = position.sell_average_price
        position.ltp = ohlc.ltp
        unrialized_pnl = (
            position.net_buy_quantity - position.net_sell_quantity
        ) * (ohlc.ltp - position.buy_average_price)
        pnl += realized_pnl + unrialized_pnl
    logger.debug(
        f"Call Position Pnl: Buy qty={position.net_buy_quantity}, Avg buy price={position.buy_average_price}, Sell qty={position.net_sell_quantity}, Avg sell price={position.sell_average_price}, Ltp={ohlc.ltp}, Realized={realized_pnl}, Unrealized={unrialized_pnl}"
    )
    positions[position_count] = {
        "symbol": instrument.trading_symbol,
        "avg_buy_price": position.buy_average_price,
        "buy_qty": position.net_buy_quantity,
        "avg_sell_price": position.sell_average_price,
        "sell_qty": position.net_sell_quantity,
        "pnl": realized_pnl + unrialized_pnl,
        "ltp": ohlc.ltp
    }
    position_count += 1
    return round(pnl, 4)


def get_required_margin_for_position(instrument: Instrument):
    positions = []
    positions.append(
        {
            "contract": f"{instrument.underlying.name}-{instrument.expiry_date.strftime("%d%b%y").upper()}",
            "exchange": instrument.exchange.name,
            "product": "OPTION",
            "qty": instrument.lot_size,
            "strikePrice": instrument.strike_price,
            "tradeType": "SELL",
            "optionType": "PUT",
        }
    )
    url = "https://margin-calc-arom-prod.angelbroking.com/margin-calculator/SPAN"
    headers = {
        "authority": "margin-calc-arom-prod.angelbroking.com",
        "origin": "https://www.angelone.in",
        "referer": "https://www.angelone.in/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
        "content-type": "application/json",
        "path": "/margin-calculator/SPAN",
    }
    payload = {"position": positions}
    resp = requests.post(url, headers=headers, json=payload)
    logger.debug(resp.text)
    resp_margin = resp.json()['margin']
    required_margin = resp_margin['netPremium'] if resp_margin['totalMargin'] == 0 else resp_margin['totalMargin']
    logger.info(f"required_margin: {required_margin}")
    return float(required_margin)


def get_required_margin(
        call_hedge_instrument: Instrument, 
        put_hedge_instrument: Instrument, 
        call_instrument: Instrument, 
        put_instrument: Instrument
    ):
    positions = []
    if call_hedge_instrument:
        positions.append(
            {
                "contract": f"{call_hedge_instrument.underlying.name}-{call_hedge_instrument.expiry_date.strftime("%d%b%y").upper()}",
                "exchange": call_hedge_instrument.exchange.name,
                "product": "OPTION",
                "qty": call_hedge_instrument.lot_size,
                "strikePrice": call_hedge_instrument.strike_price,
                "tradeType": "BUY",
                "optionType": "CALL",
            }
        )
    if put_hedge_instrument:
        positions.append(
            {
                "contract": f"{put_hedge_instrument.underlying.name}-{put_hedge_instrument.expiry_date.strftime("%d%b%y").upper()}",
                "exchange": put_hedge_instrument.exchange.name,
                "product": "OPTION",
                "qty": put_hedge_instrument.lot_size,
                "strikePrice": put_hedge_instrument.strike_price,
                "tradeType": "BUY",
                "optionType": "PUT",
            }
        )
    positions.append(
        {
            "contract": f"{call_instrument.underlying.name}-{call_instrument.expiry_date.strftime("%d%b%y").upper()}",
            "exchange": call_instrument.exchange.name,
            "product": "OPTION",
            "qty": call_instrument.lot_size,
            "strikePrice": call_instrument.strike_price,
            "tradeType": "SELL",
            "optionType": "CALL",
        }
    )
    positions.append(
        {
            "contract": f"{put_instrument.underlying.name}-{put_instrument.expiry_date.strftime("%d%b%y").upper()}",
            "exchange": put_instrument.exchange.name,
            "product": "OPTION",
            "qty": put_instrument.lot_size,
            "strikePrice": put_instrument.strike_price,
            "tradeType": "SELL",
            "optionType": "PUT",
        }
    )
    url = "https://margin-calc-arom-prod.angelbroking.com/margin-calculator/SPAN"
    headers = {
        "authority": "margin-calc-arom-prod.angelbroking.com",
        "origin": "https://www.angelone.in",
        "referer": "https://www.angelone.in/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
        "content-type": "application/json",
        "path": "/margin-calculator/SPAN",
    }
    payload = {"position": positions}
    resp = requests.post(url, headers=headers, json=payload)
    logger.debug(resp.content)
    resp_margin = resp.json()['margin']
    required_margin = resp_margin['netPremium'] if resp_margin['totalMargin'] == 0 else resp_margin['totalMargin']
    logger.info(f"required_margin: {required_margin}")
    return float(required_margin)



def new_parse_strategy(strategy_json: Dict) -> DummyStrategy:
    underlying = Underlying(strategy_json['UNDERLYING'])
    expirytype = ExpiryType(strategy_json['EXPIRY_TYPE'])

    underlying_cache_data = get_cache_data(underlying)

    pricefeed_token = underlying_cache_data.pricefeed_token

    underlying_expiry = get_underlying_expiry(
            underlying,
            expirytype
            )
        

    strategy = DummyStrategy(
        strategy_json['ID'],
        Underlying(strategy_json['UNDERLYING']),
        ExpiryType(strategy_json['EXPIRY_TYPE']),
        strategy_json['RANGE_START_TIME'],  
        strategy_json['RANGE_END_TIME'],
        strategy_json['STRATEGY_END_TIME'],
        strategy_json['LOTS'],
        strategy_json['LOTS_SIZE'],
        strategy_json.get('STRATEGY_TARGET'," "),
        strategy_json.get('STRATEGY_STOPLOSS', " "),
        strategy_json.get('SL_TG_TYPE', None),
        underlying_high=None,
        underlying_low=None,
        pricefeed_token=pricefeed_token,
        underlying_expiry=underlying_expiry,
        freeze_qty= FREEZE_QTY[strategy_json['UNDERLYING']][strategy_json['EXPIRY_TYPE']]
    )

    # logger.info(strategy)
    return strategy
