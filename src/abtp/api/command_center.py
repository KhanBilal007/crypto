"""Framework-neutral API response for the paper command center."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from abtp.paper import PaperCommandRecommendation


@dataclass(frozen=True, slots=True)
class PaperCommandCenterResponse:
    """Dependency-free command-center API response contract."""

    recommendation: PaperCommandRecommendation
    generated_at: datetime

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "recommendation": self.recommendation.as_dict(),
            "audit_payload": self.recommendation.audit_payload(),
        }

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper command-center API cannot submit orders")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper command-center API cannot create order intents")

    def enable_live_trading(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper command-center API cannot enable live trading")


def build_paper_command_center_response(
    recommendation: PaperCommandRecommendation,
) -> PaperCommandCenterResponse:
    """Build the framework-neutral command-center API response."""

    return PaperCommandCenterResponse(
        recommendation=recommendation,
        generated_at=recommendation.generated_at,
    )
