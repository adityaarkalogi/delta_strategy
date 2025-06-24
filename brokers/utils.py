from copy import deepcopy
from datetime import datetime
from commons.models import Order
from data.models import Cache
import logging


logger = logging.getLogger(__name__)


def get_expiry_code(underlying_name: str, expiry: datetime) -> str:
    expiry = int(expiry.date().strftime("%y%m%d"))
    weekly_expiry = Cache().pull(f"{underlying_name}_WEEKLY")
    next_weekly_expiry = Cache().pull(f"{underlying_name}_NEXTWEEKLY")
    monthly_expiry = Cache().pull(f"{underlying_name}_MONTHLY")
    if underlying_name in ["NIFTY", "SENSEX"]:
        if expiry == monthly_expiry:
            return "CM"
        elif expiry == weekly_expiry:
            return "CW"
        elif expiry == next_weekly_expiry:
            return "W1"
    else:
        if expiry == weekly_expiry:
            return "CM"
        elif expiry == next_weekly_expiry:
            return "M1"


def slice_order(order: Order, lot_size: int, freeze_qty: int):
    complete_slices = int((order.quantity / lot_size) // freeze_qty)
    reamining_qty = int((order.quantity / lot_size) % freeze_qty)
    for i in range(complete_slices):
        child_order = deepcopy(order)
        child_order.id = i
        child_order.quantity = lot_size * freeze_qty
        order.child_orders[child_order.id] = child_order

    if reamining_qty:
        child_order = deepcopy(order)
        child_order.id = complete_slices
        child_order.quantity = reamining_qty * lot_size
        order.child_orders[child_order.id] = child_order
