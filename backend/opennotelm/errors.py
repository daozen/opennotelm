class AppError(Exception):
    """Safe error intended for users; never includes provider response bodies."""

    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(code)
