class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 409, *, retry_after=None):
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(message)
