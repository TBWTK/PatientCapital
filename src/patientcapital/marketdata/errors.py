"""Typed failures from external market-data providers."""


class MarketDataError(RuntimeError):
    """A provider did not return trustworthy facts; no fallback is allowed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")
