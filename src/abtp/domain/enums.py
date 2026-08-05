"""Core ABTP domain enumerations."""

from enum import StrEnum


class MarketType(StrEnum):
    """Market types known to ABTP."""

    SPOT = "spot"
    MARGIN = "margin"
    FUTURES = "futures"
    OPTIONS = "options"


class OrderSide(StrEnum):
    """Side of a proposed spot order."""

    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    """Order type vocabulary; execution semantics arrive in later stages."""

    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    """Lifecycle status for future execution modules."""

    CREATED = "created"
    RISK_REJECTED = "risk_rejected"
    RISK_APPROVED = "risk_approved"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELED = "canceled"
    FAILED = "failed"


class SignalDirection(StrEnum):
    """Directional output from an intelligence or strategy module."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class PredictionHorizon(StrEnum):
    """Prediction horizon vocabulary."""

    INTRADAY = "intraday"
    SWING = "swing"
    POSITION = "position"


class RiskDecisionStatus(StrEnum):
    """Final risk verdict for a proposed order path."""

    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"


class AuditEventType(StrEnum):
    """Audit event categories required for explainability."""

    MARKET_INPUT = "market_input"
    FEATURE_VECTOR = "feature_vector"
    PREDICTION = "prediction"
    SIGNAL = "signal"
    RISK_DECISION = "risk_decision"
    ORDER_INTENT = "order_intent"
    PORTFOLIO_SNAPSHOT = "portfolio_snapshot"
