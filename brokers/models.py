from typing import Dict
from commons.enums import BrokerResponseType


class Response:
    def __init__(
        self, type: BrokerResponseType, message: Dict[str, str], error_code: int
    ):
        self.type = type
        self.message = message
        self.error_code = error_code

    def json(self):
        return {"type": self.type, "data": self.message, "error_code": self.error_code}
