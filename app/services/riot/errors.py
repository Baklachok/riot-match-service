class RiotClientError(RuntimeError):
    """Base error for Riot API integration failures."""


class RiotConfigurationError(RiotClientError):
    """Raised when Riot client configuration is incomplete."""


class RiotApiError(RiotClientError):
    def __init__(
        self,
        status_code: int,
        message: str,
        retry_after: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.retry_after = retry_after
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.retry_after is None:
            return f"Riot API returned {self.status_code}: {self.message}"
        return (
            f"Riot API returned {self.status_code}: {self.message} "
            f"(retry after {self.retry_after}s)"
        )
