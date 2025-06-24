class SystemDefinedError(Exception):
    def __init__(self, code: int, message="System defined"):
        self.code = code
        self.message = message
        super().__init__(message)


class LoginExpiredError(SystemDefinedError):
    def __init__(self, message: str = "Login expired"):
        self.code = 9001
        self.message = message
        super().__init__(self.code, message)
        

class NotSupportedError(SystemDefinedError):
    def __init__(self, message: str = "Not supported"):
        self.code = 9016
        self.message = message
        super().__init__(self.code, message)

class BrokerError(SystemDefinedError):
    def __init__(self, message: str = "Error in broker"):
        self.code = 9081
        self.message = message
        super().__init__(self.code, message)

class UnknownError(SystemDefinedError):
    def __init__(self, message: str = "Something went wrong"):
        self.code = 9090
        self.message = message
        super().__init__(self.code, message)
