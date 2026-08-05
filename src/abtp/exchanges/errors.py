"""Exchange adapter error hierarchy."""


class ExchangeAdapterError(Exception):
    """Base class for exchange adapter failures."""


class RateLimitExceededError(ExchangeAdapterError):
    """Raised when an adapter call exceeds the configured rate limit."""


class UnavailableExchangeError(ExchangeAdapterError):
    """Raised when an exchange adapter is unavailable."""


class InvalidSymbolError(ExchangeAdapterError):
    """Raised when a symbol is unknown or unsupported."""


class OrderRejectedError(ExchangeAdapterError):
    """Raised when an order intent is rejected by adapter validation."""


class StaleDataError(ExchangeAdapterError):
    """Raised when market data is too old for the requested operation."""


class UnsafeLiveOperationError(ExchangeAdapterError):
    """Raised when live operation controls are not satisfied."""


class UnsupportedOperationError(ExchangeAdapterError):
    """Raised for leverage, margin, futures, withdrawals, or other disabled operations."""
