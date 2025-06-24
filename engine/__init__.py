import json
from typing import Dict
from commons.constants import (
    MARKET_END_TIME,
    MARKET_START_TIME, 
    VERSION
)
from commons.enums import LogType, Message, MessageType, StrategyStatus
from commons.models import Ohlc, Strategy, DummyStrategy
from commons.utils import (
    get_current_time_int,
    get_cache_data,
    get_underlying_expiry
)
import data
from engine.utils import calculate_pnl, parse_strategy, new_parse_strategy
from engine import evaluator
from errors.system_defined import BrokerError
import pricefeed
from pricefeed.utils import (
    load_instruments, 
)
import brokers.zerodha
import brokers.xts
from config import Config
import logging
import time
import user_com
import threading



logger = logging.getLogger()


def setup():
    logger.info(VERSION)
    logger.info(f"BROKER: {Config.BROKER}")
    brokers.zerodha.login()
    brokers.xts.login()
    load_instruments()
    logger.info("Waiting for market to start...")
    while get_current_time_int() <= MARKET_START_TIME - 1500:
        time.sleep(0.5)
        continue
    pricefeed.connect()
    threading.Thread(target=pricefeed.heartbeat, daemon=True).start()

def run():
    current_strategy = None
    fe_id_map: Dict[str, DummyStrategy] = {}

    while True:
        user_raw_data = user_com.get_data()
        if user_raw_data:
            # logger.info(user_raw_data)
            if fe_id_map.get('1') is None:
                strategy = new_parse_strategy(user_raw_data)
                fe_id_map["1"] = strategy
                current_strategy = strategy
            
            if current_strategy is None:
                continue

            if get_current_time_int() >= int(current_strategy.strategy_end_time):
                logger.info(f"Strategy Square off time already passed")
                fe_id_map["1"] = None
                current_strategy = None
                continue    
        
        if get_current_time_int()<= MARKET_START_TIME:
            time.sleep(0.5)
            continue
        
        if get_current_time_int()>= MARKET_END_TIME + 15:
            logger.info(f"Market is closed !")
            return
        
        underlying_ohlc: Ohlc = pricefeed.get_quote_from_stream()
        underlying_cache_data = get_cache_data(current_strategy.underlying.value)

        pricefeed_token = underlying_cache_data.pricefeed_token

        underlying_expiry = get_underlying_expiry(
            current_strategy.underlying.value,
            current_strategy.expirytype.value
            )
        
        for _, strategy_obj in fe_id_map.items():

            if strategy_obj is None:
                continue

            try:
                if strategy_obj and underlying_ohlc.token == pricefeed_token:
                    evaluator.evaluate(strategy_obj, underlying_ohlc.ltp, underlying_expiry)
                
                if time.time() - strategy_obj.last_sync_time >=1:
                    evaluator.sync_positions(strategy_obj)
                    strategy_obj.last_sync_time = time.time()

            except Exception as e:
                logger.error(f"Error : {e}")