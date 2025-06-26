import enum


class ExchangeType(enum.Enum):
    NFO = "NFO"
    BFO = "BFO"
    MCX = "MCX"
    

class Underlying(enum.Enum):
    NIFTY = "NIFTY"
    BANKNIFTY = "BANKNIFTY"


class InstrumentType(enum.Enum):
    OPTIDX = "OPTIDX"
    FUTIDX = "FUTIDX"
    INDICES = "INDICES"


class ExpiryType(enum.Enum):
    WEEKLY = "WEEKLY"
    NEXTWEEKLY = "NEXTWEEKLY"
    MONTHLY = "MONTHLY"


class OptionType(enum.Enum):
    CE = "CE"
    PE = "PE"
    FUT = "FUT"
    EQ = "EQ"


class ShiftDirection(enum.Enum):
    CENTER = "CENTER"
    UP = "UP"
    DOWN = "DOWN"


class DecrType(enum.Enum):
    LOTS = "LOTS"
    PERCENTAGE = "PERCENTAGE"


class PnlType(enum.Enum):
    POINTS = "POINTS"
    PERCENTAGE = "PERCENTAGE"


class OrderType(enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class ProductType(enum.Enum):
    NRML = "NRML"
    MIS = "MIS"


class PositionType(enum.Enum):
    BUY = 1
    SELL = -1


class PositionStatus:
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    
    
class StrategyStatus(enum.Enum):
    CREATED = "CREATED"
    HEDGE_SELECTED = "HEDGE_SELECTED"
    RUNNING = "RUNNING"
    PAUSE = "PAUSE"
    SQUARING_OFF = "SQUARING_OFF"
    SQUARED_OFF = "SQUARED_OFF"
    STOPPING = "STOPPED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class OrderStatus(enum.Enum):
    CREATED = "CREATED"
    SENT = "SENT"
    WORKING = "WORKING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class BrokerType(enum.Enum):
    DUMMY = "DUMMY"
    XTS = "XTS"


class BrokerResponseType(enum.Enum):
    PLACEORDER = "PLACEORDER"
    MODIFYORDER = "MODIFYORDER"
    CANCELORDER = "CANCELORDER"
    GETORDERDETAILS = "GETORDERDETAILS"


class UserMessageType(enum.Enum):
    CONNECT = "CONNECT"
    START = "START"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    UPDATE = "UPDATE"
    STOP = "STOP"


class LogType(enum.Enum):
    RUNNING = "RUNNING"
    ARCHIVED = "ARCHIVED" 
    POSITIONS = "POSITIONS"
    PNL = "PNL"
    STRATEGYUPDATE = "STRATEGYUPDATE"
    LTPUPDATE = "LTPUPDATE"
    ORDERUPDATE = "ORDERUPDATE"
    FUNDUPDATE = "FUNDUPDATE"
    BACKFILL = "BACKFILL"
    SYNTHUPDATE = "SYNTHUPDATE"
    STRADDLEUPDATE = "STRADDLEUPDATE"


class SlTgType(enum.Enum):
    POINTS = 'POINTS'
    PERCENTAGE = 'PERCENTAGE'

class MessageType:
    STRATEGY_UPDATE = "STRATEGY_UPDATE" 
    OPENED = "OPENED"
    CONNECT = "CONNECT"
    RUNNING = "RUNNING"
    STARTED = "STARTED"
    END = "END"
    ERROR = "ERROR"
    LTP = "LTP"
    PNL = "PNL"


class Message:
    MANUAL_SQUARED_OFF = "Manual Square Off"
    CHECK_STRATEGY_PARAMETERS = "Check Strategy Parameters"
    SQUARE_OFF_TIME_EXPIRED = "Square Off Time Expired"
    TAREGT_HIT = "Strategy Profit Achieved"
    STOP_LOSS_TRIGGERED = "Strategy Stop Loss Triggered"
    SQUARE_OFF_TIME_REACHED = "Square Off Time Reached"
    BOTH_STRIKES_SAME_AND_SHIFT_HAPPENED = "Equal Strikes Detected and Shift Happend"
    STRATEGY_ERROR = "Strategy Error. Contact Developer"
