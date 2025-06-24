import logging
from queue import Queue
import time
from kiteconnect import KiteTicker
from commons.constants import MARKET_START_TIME
from commons.utils import get_current_time_int
from data import instruments, Cache
from commons.models import Ohlc, Instrument
from config import Config

logger = logging.getLogger(__name__)

price_dict = {}
option_chains = {}
oi_dict = {}
price_queue = Queue()
previous_oi = {}
last_heart_beat = time.time()
count = 0
all_connections: list[KiteTicker] = []


def connect():
    pricefeed_connection = KiteTicker(
        api_key=Config.PRICEFEED_API_KEY,
        access_token=Config.PRICEFEED_ACCESS_TOKEN,
        debug=False,
        root=None,
        reconnect=True,
        reconnect_max_tries=100,
        reconnect_max_delay=5,
        connect_timeout=10,
    )
    all_connections.append(pricefeed_connection)
    pricefeed_connection.on_connect = on_connect
    pricefeed_connection.on_ticks = on_ticks
    pricefeed_connection.on_close = on_close
    pricefeed_connection.on_error = or_error
    pricefeed_connection.on_reconnect = on_reconnect
    pricefeed_connection.connect(threaded=True)


def get_option_chain(underlying: str, expiry: str):
    return option_chains[underlying][expiry]


def get_quote(instrument_id: str):
    return price_dict.get(instrument_id)


def get_quote_from_stream():
    return price_queue.get()


def on_reconnect(_, attempts_count):
    logger.error(f"attempts: {attempts_count}")


def or_error(_, code, reason):
    logger.error(f"{code}:: {reason}")


def on_connect(pricefeed_connection: KiteTicker, _):
    logger.info("Feed connected successfully.")
    tokens_to_subscribe = [
        int(instrument.pricefeed_token) for instrument in instruments
    ]
    if len(instruments) > 0:
        pricefeed_connection.subscribe(tokens_to_subscribe)
        pricefeed_connection.set_mode(
            pricefeed_connection.MODE_FULL, tokens_to_subscribe
        )
        logger.info(f"Succesfully subscribed {len(tokens_to_subscribe)} tokens.")


def on_ticks(_, ticks: dict):
    global last_heart_beat, count
    for pkt in ticks:
        try:
            if "depth" in pkt:
                ask_price = pkt["depth"]["buy"][0]["price"]
                bid_price = pkt["depth"]["sell"][0]["price"]
                volume_traded = pkt["volume_traded"]
                open_interest = pkt["oi"]
            else:
                # for indices
                ask_price = 1
                bid_price = 1
                volume_traded = 1
                open_interest = 1

            if (ask_price != 0) and (bid_price != 0) and (volume_traded != 0):
                instrument_token = pkt["instrument_token"]
                ltp = pkt["last_price"]
                ohlc = Ohlc(instrument_token, ltp)
                price_dict[instrument_token] = ltp
                instrument: Instrument = Cache().pull(instrument_token)
                if instrument.underlying.name not in oi_dict:
                    oi_dict[instrument.underlying.name] = {}
                if (
                    instrument.expiry_date.strftime("%Y-%m-%d")
                    not in oi_dict[instrument.underlying.name]
                ):
                    oi_dict[instrument.underlying.name][
                        instrument.expiry_date.strftime("%Y-%m-%d")
                    ] = {}
                if (
                    instrument.option_type.name
                    not in oi_dict[instrument.underlying.name][
                        instrument.expiry_date.strftime("%Y-%m-%d")
                    ]
                ):
                    oi_dict[instrument.underlying.name][
                        instrument.expiry_date.strftime("%Y-%m-%d")][
                        instrument.option_type.name] = {}
                oi_dict[instrument.underlying.name][
                    instrument.expiry_date.strftime("%Y-%m-%d")][
                    instrument.option_type.name][instrument] = int(open_interest/instrument.lot_size)

                if instrument.underlying.name not in option_chains:
                    option_chains[instrument.underlying.name] = {}
                if (
                    instrument.expiry_date.strftime("%Y-%m-%d")
                    not in option_chains[instrument.underlying.name]
                ):
                    option_chains[instrument.underlying.name][
                        instrument.expiry_date.strftime("%Y-%m-%d")
                    ] = {}
                if (
                    instrument.option_type.name
                    not in option_chains[instrument.underlying.name][
                        instrument.expiry_date.strftime("%Y-%m-%d")
                    ]
                ):
                    option_chains[instrument.underlying.name][
                        instrument.expiry_date.strftime("%Y-%m-%d")
                    ][instrument.option_type.name] = {}

                option_chains[instrument.underlying.name][
                    instrument.expiry_date.strftime("%Y-%m-%d")
                ][instrument.option_type.name][instrument.strike_price] = ltp
                count += 1
                price_queue.put(ohlc)
        except Exception:
            logger.exception(f"Feed disconnected, {pkt}")


def heartbeat():
    global last_heart_beat, count
    while True:
        if get_current_time_int() <= MARKET_START_TIME:
            time.sleep(1)
            continue
        if time.time()-last_heart_beat>=10:
            if count == 0:
                logger.info(f"Trying to reconnect.")
                for prc_conn in all_connections:
                    prc_conn.close()
                all_connections.clear()
                connect()
            else:
                logger.debug(f"HEARTBEAT:: {count}")
                count = 0
            last_heart_beat = time.time()
        time.sleep(0.1)

def on_close(_, code, reason):
    logger.critical(f"Closed feed with code={code}, reason={reason}")
