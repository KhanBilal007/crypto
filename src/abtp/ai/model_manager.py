"""AI model manager orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from abtp.ai.model_registry import ModelRegistry
from abtp.ai.model_selection import (
    ActiveModelRecommendation,
    ModelSelectionInput,
    ModelSelectionPolicy,
    select_active_model,
)
from abtp.config import TradingMode
from abtp.domain.models import JsonValue


@dataclass(frozen=True, slots=True)
class ModelManagementRequest:
    """Input for one model-management review."""

    mode: TradingMode = TradingMode.PAPER
    generated_at: datetime | None = None
    manual_approval_for_live_change: bool = False
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class ModelManagementReport:
    """Auditable model-management report."""

    generated_at: datetime
    recommendation: ActiveModelRecommendation
    active_model_ref: str | None
    registry_model_count: int
    source_refs: Mapping[str, str]
    limitations: tuple[str, ...] = (
        "Model manager recommendations are advisory metadata decisions.",
        "The manager does not serve models, train models, create signals, or execute orders.",
        "Live active-model changes require manual approval and later live-stage gates.",
        "No profit is guaranteed by model selection.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "recommendation": self.recommendation.as_dict(),
            "active_model_ref": self.active_model_ref,
            "registry_model_count": self.registry_model_count,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        payload = self.recommendation.audit_payload()
        payload["active_model_ref"] = self.active_model_ref or "none"
        payload["registry_model_count"] = str(self.registry_model_count)
        return payload


class AIModelManager:
    """Select active model metadata without model serving or live swapping."""

    def __init__(
        self,
        registry: ModelRegistry,
        *,
        policy: ModelSelectionPolicy | None = None,
        active_model_ref: str | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy or ModelSelectionPolicy()
        self._active_model_ref = active_model_ref

    @property
    def active_model_ref(self) -> str | None:
        return self._active_model_ref

    @property
    def policy(self) -> ModelSelectionPolicy:
        return self._policy

    def review(self, request: ModelManagementRequest) -> ModelManagementReport:
        generated_at = request.generated_at or datetime.now(UTC)
        entries = self._registry.list(include_retired=True)
        candidates = tuple(
            ModelSelectionInput(
                entry=entry,
                latest_training=self._registry.latest_training(entry.model_ref),
                latest_evaluation=self._registry.latest_evaluation(entry.model_ref),
                current_active=entry.model_ref == self._active_model_ref,
                source_refs=entry.source_refs,
            )
            for entry in entries
        )
        recommendation = select_active_model(
            candidates,
            mode=request.mode,
            generated_at=generated_at,
            manual_approval_for_live_change=request.manual_approval_for_live_change,
            policy=self._policy,
            source_refs=request.source_refs,
        )
        return ModelManagementReport(
            generated_at=generated_at,
            recommendation=recommendation,
            active_model_ref=self._active_model_ref,
            registry_model_count=len(entries),
            source_refs=request.source_refs,
        )

    def apply_research_or_paper_recommendation(
        self,
        report: ModelManagementReport,
        *,
        mode: TradingMode,
    ) -> str | None:
        """Apply only non-live metadata selection in safe modes."""

        if mode is TradingMode.LIVE:
            raise ValueError("live active-model changes require manual live-stage approval")
        if not report.recommendation.recommended:
            return self._active_model_ref
        if not report.recommendation.can_apply_without_live_swap:
            return self._active_model_ref
        self._active_model_ref = report.recommendation.selected_model_ref
        return self._active_model_ref

    def predict(self, *_args: object, **_kwargs: object) -> None:
        """Reject prediction serving; prediction service owns model inference."""

        raise ValueError("AI model manager cannot serve predictions")

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        """Reject signal creation; strategies own signal generation."""

        raise ValueError("AI model manager cannot create strategy signals")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject order submission; model management has no execution authority."""

        raise ValueError("AI model manager cannot submit orders")
