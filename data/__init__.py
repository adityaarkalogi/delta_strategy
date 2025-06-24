from typing import List, Dict
from commons.models import Instrument, Strategy
from data.models import Cache as  Cache

instruments: List[Instrument] = []
underlying_instruments: Dict[str, Instrument] = {}