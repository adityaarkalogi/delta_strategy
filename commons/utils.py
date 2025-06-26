
from datetime import date, datetime
import logging
from time import time
from time import sleep
import pytz
import data

from commons.constants import HOLIDAYS
from commons.models import Singleton

logger = logging.getLogger(__name__)


def retry(n, frequency):
    """
    n: retry count.
    frequency: after which time it retry on exception.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            retry_attempt = n
            exeption = None
            while retry_attempt:
                try:
                    func(*args, **kwargs)
                    return
                except Exception as ex:
                    retry_attempt -= 1
                    sleep(frequency)
                    exeption = ex
            raise exeption

        return wrapper

    return decorator


def timer(func):
    def wrapper(*args, **kwargs):
        st = time()
        func(*args, **kwargs)
        logger.info(f"TIme taken to execute {func.__name__} is {time() - st}")

    return wrapper


def generate_trading_symbol(
    exchange: str,
    underlying: str,
    instrument_type: str,
    expiry_date: int,
    strike_price: float,
    option_type: str,
):
    return "-".join(
        [
            exchange,
            underlying,
            instrument_type,
            str(expiry_date),
            "{:.1f}".format(strike_price),
            option_type,
        ]
    )


def round_to(n, precision):
    correction = 0.5 if n >= 0 else -0.5
    return int(n / (precision) + correction) * precision


def get_current_time_int(): 
    return int(datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H%M%S"))


def is_holiday(trading_day: date):
    if trading_day.weekday() > 4:
        return True
    if int(trading_day.strftime("%y%m%d"))in HOLIDAYS:
        return True
    return False


class OrderId(Singleton):
    order_id = 0

    def generate_orderid(self):
        self.order_id += 1
        return self.order_id


def get_cache_data(underlying: str):
    return data.Cache().pull(underlying)



def get_underlying_expiry(underlying: str, expiry_type: str):
    return data.Cache().pull(f"{underlying}_{expiry_type}")


def calc_by_points(underlying_value: float, strategy_value: float) -> float:
    value = underlying_value + strategy_value
    return value



def calc_by_percentage(underlying_value:float) -> float:
    ...