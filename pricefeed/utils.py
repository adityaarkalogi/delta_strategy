import pandas as pd
import requests
from typing import List
from datetime import datetime
from time import sleep
from dateutil.relativedelta import relativedelta
from commons.models import Instrument
from commons.utils import generate_trading_symbol
from commons.constants import FREEZE_QTY, INDICES, LOT_SIZE
from commons.enums import InstrumentType, OptionType, ExchangeType, Underlying
from data import Cache, instruments, underlying_instruments
import logging

logger = logging.getLogger(__name__)


def filter_master_data_by_index(
    master_data: dict, exchange: str, fno_name: str, underlying: str
):
    und_name = underlying
    if underlying == "NIFTY":
        und_name = "NIFTY 50"
    elif underlying == "BANKNIFTY":
        und_name = "NIFTY BANK"
    elif underlying == "FINNIFTY":
        und_name = "NIFTY FIN SERVICE"
    elif underlying == "MIDCPNIFTY":
        und_name = "NIFTY MID SELECT"
    elif underlying == "SENSEX50":
        und_name = "SENSEX"
    elif underlying == "CRUDEOIL":
        und_name = "MCXCRUDEX"
    elif underlying == "CRUDEOILM":
        und_name = "MCXCRUDEX"

    fno_data = master_data[
        (master_data["exchange"] == exchange) & (master_data["name"] == fno_name)
    ].copy()

    fno_data.loc[:, "expiry_int"] = (
        fno_data["expiry"].str.replace("-", "").astype(int) - 20000000
    )
    opt_expiries = fno_data[fno_data["segment"] == f"{exchange}-OPT"][
        "expiry_int"
    ].unique()
    fut_expiries = fno_data[fno_data["segment"] == f"{exchange}-FUT"][
        "expiry_int"
    ].unique()
    opt_expiries.sort()
    fut_expiries.sort()

    fno_data["expiry"] = pd.to_datetime(fno_data["expiry"], format="%Y-%m-%d")
    weekly_expiry = int(opt_expiries[0])
    next_weekly_expiry = int(opt_expiries[1])
    monthly_expiry = int(fut_expiries[0])
    if exchange in [ExchangeType.BFO.name, ExchangeType.MCX.name]:
        ## getting monthly expiry for BSE indexes
        today = datetime.now().date()
        weekly_expiry_date = datetime.strptime(str(weekly_expiry), "%y%m%d").date()
        if today.month != weekly_expiry_date.month:
            today += relativedelta(months=1)
        current_month_expiry = fno_data[(fno_data["expiry"].dt.month == today.month) & (fno_data["expiry"].dt.year == today.year)]
        monthly_expiry = int(current_month_expiry["expiry"].max().strftime('%y%m%d'))

    logger.info(f"{underlying}, {weekly_expiry}, {next_weekly_expiry}, {monthly_expiry}")

    fut_instrument = fno_data[
        (fno_data["segment"] == f"{exchange}-FUT")
        & (fno_data["expiry_int"] == monthly_expiry)
    ].iloc[0]

    if underlying in ["CRUDEOIL", "CRUDEOILM"]:
        cash_instrument = fut_instrument
    else:
        cash_instrument = master_data[
            (master_data["tradingsymbol"] == und_name)
            & (master_data["segment"] == "INDICES")
        ].iloc[0]

    underlying_instruments[cash_instrument["instrument_token"]] = Instrument(
        cash_instrument["instrument_token"],
        cash_instrument["exchange_token"],
        ExchangeType(exchange),
        Underlying(underlying),
        InstrumentType("INDICES"),
        datetime(1970, 1, 1),
        0,
        OptionType(cash_instrument["instrument_type"]),
        f"{underlying}",
    )

    Cache().push(f"{underlying}_WEEKLY", weekly_expiry)
    Cache().push(f"{underlying}_NEXTWEEKLY", next_weekly_expiry)
    Cache().push(f"{underlying}_MONTHLY", monthly_expiry)
    Cache().push(
        f"{underlying}_FUT",
        Instrument(
            fut_instrument["instrument_token"],
            fut_instrument["exchange_token"],
            ExchangeType(exchange),
            Underlying(underlying),
            InstrumentType("FUTIDX"),
            fut_instrument["expiry"],
            0,
            OptionType(fut_instrument["instrument_type"]),
            f"{underlying}_FUT",
        ),
    )
    Cache().push(
        fut_instrument["instrument_token"],
        Instrument(
            fut_instrument["instrument_token"],
            fut_instrument["exchange_token"],
            ExchangeType(exchange),
            Underlying(underlying),
            InstrumentType("FUTIDX"),
            fut_instrument["expiry"],
            0,
            OptionType(fut_instrument["instrument_type"]),
            f"{underlying}_FUT",
        ),
    )
    Cache().push(
        f"{underlying}",
        Instrument(
            cash_instrument["instrument_token"],
            cash_instrument["exchange_token"],
            ExchangeType(exchange),
            Underlying(underlying),
            InstrumentType("INDICES"),
            datetime(1970, 1, 1),
            0,
            OptionType(cash_instrument["instrument_type"]),
            f"{underlying}",
        ),
    )
    Cache().push(
        cash_instrument["instrument_token"],
        Instrument(
            cash_instrument["instrument_token"],
            cash_instrument["exchange_token"],
            ExchangeType(exchange),
            Underlying(underlying),
            InstrumentType("INDICES"),
            datetime(1970, 1, 1),
            0,
            OptionType(cash_instrument["instrument_type"]),
            f"{underlying}",
        ),
    )

    opt_data = fno_data[
        (fno_data["segment"] == f"{exchange}-OPT")
        & (fno_data["expiry_int"].isin([weekly_expiry, next_weekly_expiry, monthly_expiry]))
    ]

    lot_size = opt_data["lot_size"].unique()[0]
    LOT_SIZE[underlying] = int(lot_size)

    for _, row in opt_data.iterrows():
        generated_trading_symbol = generate_trading_symbol(
            row["exchange"],
            row["name"],
            "OPTIDX",
            row["expiry_int"],
            row["strike"],
            row["instrument_type"],
        )
        Cache().push(
            generated_trading_symbol,
            Instrument(
                row["instrument_token"],
                row["exchange_token"],
                ExchangeType(exchange),
                Underlying(underlying),
                InstrumentType("OPTIDX"),
                row["expiry"],
                row["strike"],
                OptionType(row["instrument_type"]),
                generated_trading_symbol,
                row["lot_size"],
            ),
        )
        Cache().push(
            row["instrument_token"],
            Instrument(
                row["instrument_token"],
                row["exchange_token"],
                ExchangeType(exchange),
                Underlying(underlying),
                InstrumentType("OPTIDX"),
                row["expiry"],
                row["strike"],
                OptionType(row["instrument_type"]),
                generated_trading_symbol,
                row["lot_size"],
            ),
        )
        instruments.append(
            Instrument(
                row["instrument_token"],
                row["exchange_token"],
                ExchangeType(exchange),
                Underlying(underlying),
                InstrumentType("OPTIDX"),
                row["expiry"],
                row["strike"],
                OptionType(row["instrument_type"]),
                generated_trading_symbol,
                row["lot_size"],
            )
        )
    instruments.append(
        Instrument(
            fut_instrument["instrument_token"],
            fut_instrument["exchange_token"],
            ExchangeType(exchange),
            Underlying(underlying),
            InstrumentType("FUTIDX"),
            fut_instrument["expiry"],
            0,
            OptionType(fut_instrument["instrument_type"]),
            f"{underlying}_FUT",
        )
    )
    instruments.append(
        Instrument(
            cash_instrument["instrument_token"],
            cash_instrument["exchange_token"],
            ExchangeType(exchange),
            Underlying(underlying),
            InstrumentType("INDICES"),
            datetime(1970, 1, 1),
            0,
            OptionType(cash_instrument["instrument_type"]),
            f"{underlying}",
        )
    )
    return instruments


def load_instruments():
    master_data = pd.read_csv("https://api.kite.trade/instruments")

    all_instruments: List[Instrument] = []
    for index, index_info in INDICES.items():
        instruments = filter_master_data_by_index(
            master_data=master_data,
            exchange=index_info[0],
            fno_name=index_info[1],
            underlying=index,
        )
        all_instruments += instruments

    logging.info(len(instruments))


def get_freeze_qty():
    base_urls = ["http://ctrade.jainam.in:3000", "https://developers.symphonyfintech.in"]
    for base_url in base_urls:
        try:
            url = base_url + "/apimarketdata/instruments/master"
            # if eval(Config.DEV_TESTING):
            #     url = "https://developers.symphonyfintech.in/apimarketdata/instruments/master"
            paylaod = {
                "exchangeSegmentList": [
                    "NSEFO",
                    "BSEFO"
                ]
            }
            resp = requests.post(url=url, json=paylaod)
            data = resp.json()["result"]
            lines = data.strip().split("\n")
            all_records = [line.split("|") for line in lines]
            final_records = all_records

            headers = [
                "ExchangeSegment", "ExchangeInstrumentID", "InstrumentType", "Name", 
                "Description", "Series", "NameWithSeries", "InstrumentID", 
                "PriceBand.High", "PriceBand.Low", "FreezeQty", "TickSize", "LotSize", 
                "Multiplier", "UnderlyingInstrumentId", "UnderlyingIndexName", 
                "ContractExpiration", "StrikePrice", "OptionType", "displayName", 
                "PriceNumerator", "PriceDenominator", "TradingSymbol"
            ]
            df = pd.DataFrame(final_records, columns=headers)
            df["ContractExpiration"] = pd.to_datetime(df["ContractExpiration"])
            df['expiry'] = df['ContractExpiration'].dt.strftime('%y%m%d').astype(int)

            for index in INDICES.keys():
                weekly_exp = Cache().pull(f"{index}_WEEKLY")
                next_weekly_exp = Cache().pull(f"{index}_NEXTWEEKLY")
                monthly_exp = Cache().pull(f"{index}_MONTHLY")
                index_df = df[(df["Name"] == index)]
                weekly_freeze_qty = index_df[index_df["expiry"]==weekly_exp]["FreezeQty"].iloc[0]
                next_weekly_freeze_qty = index_df[index_df["expiry"]==next_weekly_exp]["FreezeQty"].iloc[0]
                monthly_freeze_qty = index_df[index_df["expiry"]==monthly_exp]["FreezeQty"].iloc[0]
                if index not in FREEZE_QTY:
                    FREEZE_QTY[index] = {}
                FREEZE_QTY[index]["WEEKLY"]=int(weekly_freeze_qty)//LOT_SIZE[index]
                FREEZE_QTY[index]["NEXTWEEKLY"]=int(next_weekly_freeze_qty)//LOT_SIZE[index]
                FREEZE_QTY[index]["MONTHLY"]=int(monthly_freeze_qty)//LOT_SIZE[index]
            return
        except Exception as ex:
            logger.error(f"Error in url: {url}, {ex}", exc_info=True)
            continue
    raise ValueError(f"Error while fetching freeze quantities.")