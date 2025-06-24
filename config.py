import os
import json
from dotenv import load_dotenv
from commons.enums import ProductType, OrderType

load_dotenv(".env")

class Config:
    PRICEFEED_CLIENT_ID = os.environ.get("PRICEFEED_CLIENT_ID")
    PRICEFEED_CLIENT_PASSWORD = os.environ.get("PRICEFEED_CLIENT_PASSWORD")
    PRICEFEED_TOTP_SECRET = os.environ.get("PRICEFEED_TOTP_SECRET")
    PRICEFEED_API_KEY = os.environ.get("PRICEFEED_API_KEY")
    PRICEFEED_API_SECRET = os.environ.get("PRICEFEED_API_SECRET")
    PRICEFEED_ACCESS_TOKEN = os.environ.get("PRICEFEED_ACCESS_TOKEN")

    REDIS_HOST=os.environ.get("USER_COMM_HOST")
    REDIS_PORT=os.environ.get("USER_COMM_PORT")

    BASE_URL  = os.environ.get("BASE_URL")
    HOST_LOOKUP = os.environ.get("HOST_LOOKUP")
    API_KEY = os.environ.get("API_KEY")
    API_SECRET = os.environ.get("API_SECRET")
    ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
    IS_DEALER_API = eval(os.environ.get("IS_DEALER_API", "False"))
    XTS_CLIENT_ID = os.environ.get("XTS_CLIENT_ID")
    IS_PRO_ID = eval(os.environ.get("IS_PRO_ID", "False"))
    PRODUCT_TYPE = ProductType(os.environ.get("PRODUCT_TYPE"))
    ORDER_TYPE = OrderType(os.environ.get("ORDER_TYPE"))
    EXTERNAL_REQUEST_TIMEOUT = 10
    LOOKUP_KEY = "xts_api.lookup_key"


    BROKER = os.environ.get("BROKER")