"""Correlation estimates for portfolio allocation recommendations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from abtp.data import normalize_timestamp
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class CorrelationEstimate:
    """One pairwise asset-correlation estimate."""

    asset_a: str
    asset_b: str
    correlation: Decimal
    sample_count: int
    source_ref: str = "correlation:fixture"

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_a", self.asset_a.strip().upper())
        object.__setattr__(self, "asset_b", self.asset_b.strip().upper())
        if not self.asset_a or not self.asset_b:
            raise ValueError("correlation asset symbols are required")
        if self.asset_a == self.asset_b:
            raise ValueError("correlation assets must be different")
        if not Decimal("-1") <= self.correlation <= DECIMAL_ONE:
            raise ValueError("correlation must be between -1 and 1")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")

    @property
    def key(self) -> tuple[str, str]:
        left, right = sorted((self.asset_a, self.asset_b))
        return left, right

    def involves(self, symbol: str) -> bool:
        normalized = symbol.upper()
        return normalized in {self.asset_a, self.asset_b}

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "asset_a": self.asset_a,
            "asset_b": self.asset_b,
            "correlation": str(self.correlation),
            "sample_count": self.sample_count,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class CorrelationSnapshot:
    """Deterministic correlation matrix metadata."""

    generated_at: datetime
    estimates: tuple[CorrelationEstimate, ...]
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        seen: set[tuple[str, str]] = set()
        for estimate in self.estimates:
            if estimate.key in seen:
                raise ValueError(f"duplicate correlation estimate: {estimate.key}")
            seen.add(estimate.key)
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def estimate_for(self, asset_a: str, asset_b: str) -> CorrelationEstimate | None:
        left, right = sorted((asset_a.upper(), asset_b.upper()))
        key = (left, right)
        return next((estimate for estimate in self.estimates if estimate.key == key), None)

    def max_abs_correlation_for(self, symbol: str) -> Decimal:
        values = tuple(
            abs(estimate.correlation) for estimate in self.estimates if estimate.involves(symbol)
        )
        return max(values, default=DECIMAL_ZERO)

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "estimates": [estimate.as_dict() for estimate in self.estimates],
            "source_refs": dict(self.source_refs),
        }


def estimate_correlation(
    *,
    asset_a: str,
    asset_b: str,
    returns_a: Sequence[Decimal],
    returns_b: Sequence[Decimal],
    source_ref: str = "correlation:returns",
) -> CorrelationEstimate:
    """Estimate deterministic Pearson correlation for two aligned return series."""

    if len(returns_a) != len(returns_b):
        raise ValueError("return series must have the same length")
    if len(returns_a) < 2:
        return CorrelationEstimate(asset_a, asset_b, DECIMAL_ZERO, len(returns_a), source_ref)
    mean_a = _mean(tuple(returns_a))
    mean_b = _mean(tuple(returns_b))
    numerator = sum(
        (
            (left - mean_a) * (right - mean_b)
            for left, right in zip(returns_a, returns_b, strict=True)
        ),
        DECIMAL_ZERO,
    )
    variance_a = sum(((value - mean_a) ** 2 for value in returns_a), DECIMAL_ZERO)
    variance_b = sum(((value - mean_b) ** 2 for value in returns_b), DECIMAL_ZERO)
    if variance_a == DECIMAL_ZERO or variance_b == DECIMAL_ZERO:
        correlation = DECIMAL_ZERO
    else:
        correlation = numerator / (variance_a.sqrt() * variance_b.sqrt())
    if abs(correlation - DECIMAL_ONE) < Decimal("0.000000000000000000000001"):
        correlation = DECIMAL_ONE
    if abs(correlation + DECIMAL_ONE) < Decimal("0.000000000000000000000001"):
        correlation = Decimal("-1")
    return CorrelationEstimate(
        asset_a=asset_a,
        asset_b=asset_b,
        correlation=max(Decimal("-1"), min(DECIMAL_ONE, correlation)),
        sample_count=len(returns_a),
        source_ref=source_ref,
    )


def _mean(values: tuple[Decimal, ...]) -> Decimal:
    return sum(values, DECIMAL_ZERO) / Decimal(len(values))
