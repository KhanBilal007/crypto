"""Deterministic parameter source metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from abtp.data import DataTrustLevel


class SourceKind(StrEnum):
    """Source categories for dependency parameters."""

    INTERNAL = "internal"
    EXCHANGE_ADAPTER = "exchange_adapter"
    REPOSITORY = "repository"
    DETERMINISTIC_STUB = "deterministic_stub"
    EXTERNAL_OPTIONAL = "external_optional"


@dataclass(frozen=True, slots=True)
class ParameterSource:
    """Metadata for a parameter source without provider calls."""

    key: str
    kind: SourceKind
    description: str
    trust_level: DataTrustLevel
    deterministic: bool
    live_allowed: bool

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("source key is required")
        if self.live_allowed and self.trust_level is not DataTrustLevel.TRUSTED:
            raise ValueError("live-allowed sources must be trusted")


def default_sources() -> tuple[ParameterSource, ...]:
    """Return source metadata stubs for the Stage 013 catalog."""

    return (
        ParameterSource(
            key="market_data_repository",
            kind=SourceKind.REPOSITORY,
            description="Validated candles, trades, and order books persisted by ABTP.",
            trust_level=DataTrustLevel.TRUSTED,
            deterministic=True,
            live_allowed=True,
        ),
        ParameterSource(
            key="sandbox_exchange_adapter",
            kind=SourceKind.EXCHANGE_ADAPTER,
            description="Deterministic sandbox adapter metadata and snapshots.",
            trust_level=DataTrustLevel.TRUSTED,
            deterministic=True,
            live_allowed=False,
        ),
        ParameterSource(
            key="data_quality_engine",
            kind=SourceKind.INTERNAL,
            description="Internal Stage 012 quality and trust status outputs.",
            trust_level=DataTrustLevel.TRUSTED,
            deterministic=True,
            live_allowed=True,
        ),
        ParameterSource(
            key="portfolio_repository",
            kind=SourceKind.REPOSITORY,
            description="Internal portfolio snapshot repository.",
            trust_level=DataTrustLevel.TRUSTED,
            deterministic=True,
            live_allowed=True,
        ),
        ParameterSource(
            key="external_derivatives_stub",
            kind=SourceKind.EXTERNAL_OPTIONAL,
            description="Optional derivatives metadata stub; no external calls in Stage 013.",
            trust_level=DataTrustLevel.DEGRADED,
            deterministic=True,
            live_allowed=False,
        ),
        ParameterSource(
            key="external_on_chain_stub",
            kind=SourceKind.EXTERNAL_OPTIONAL,
            description="Optional on-chain metadata stub; no external calls in Stage 013.",
            trust_level=DataTrustLevel.DEGRADED,
            deterministic=True,
            live_allowed=False,
        ),
        ParameterSource(
            key="external_macro_stub",
            kind=SourceKind.EXTERNAL_OPTIONAL,
            description="Optional macro metadata stub; no external calls in Stage 013.",
            trust_level=DataTrustLevel.DEGRADED,
            deterministic=True,
            live_allowed=False,
        ),
        ParameterSource(
            key="external_news_sentiment_stub",
            kind=SourceKind.EXTERNAL_OPTIONAL,
            description="Optional news/sentiment stub; no external calls in Stage 013.",
            trust_level=DataTrustLevel.DEGRADED,
            deterministic=True,
            live_allowed=False,
        ),
    )
