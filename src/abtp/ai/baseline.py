"""Conservative baseline prediction model for research and backtesting."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from abtp.ai.datasets import DatasetRow, DirectionLabel
from abtp.ai.metrics import evaluate_directional_predictions
from abtp.data import DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain import Prediction
from abtp.domain.enums import PredictionHorizon
from abtp.features import FeatureSnapshot

BASELINE_MODEL_NAME = "conservative_baseline"
BASELINE_MODEL_VERSION = "stage-017.v1"


@dataclass(frozen=True, slots=True)
class BaselineModelConfig:
    """Configuration for the deterministic baseline model."""

    label_horizon_steps: int
    probability_nudge: Decimal = Decimal("0.05")
    max_confidence: Decimal = Decimal("0.40")

    def __post_init__(self) -> None:
        if self.label_horizon_steps <= 0:
            raise ValueError("label_horizon_steps must be positive")
        if not Decimal("0") <= self.probability_nudge <= Decimal("0.20"):
            raise ValueError("probability_nudge must be between 0 and 0.20")
        if not Decimal("0") <= self.max_confidence <= Decimal("1"):
            raise ValueError("max_confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class BaselineModelMetadata:
    """Auditable metadata for a fitted baseline model."""

    model_name: str
    version: str
    feature_schema_version: str
    trained_at: datetime
    training_start: datetime
    training_end: datetime
    label_horizon_steps: int
    metrics: Mapping[str, Decimal]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BaselinePrediction:
    """Research/backtest prediction output with no trading authority."""

    pair_symbol: str
    generated_at: datetime
    model_metadata: BaselineModelMetadata
    features_ref: str
    probability_up: Decimal
    probability_down: Decimal
    confidence: Decimal
    expected_return: Decimal
    expected_volatility: Decimal
    quality: DataQualityStatus
    actionable: bool
    rationale: str

    @property
    def predicted_direction(self) -> DirectionLabel:
        if self.probability_up > self.probability_down:
            return DirectionLabel.UP
        if self.probability_down > self.probability_up:
            return DirectionLabel.DOWN
        return DirectionLabel.FLAT

    def to_domain_prediction(self, snapshot: FeatureSnapshot) -> Prediction:
        """Convert to the Stage 007 prediction contract for repository storage."""

        return Prediction(
            pair=snapshot.pair,
            generated_at=self.generated_at,
            horizon=PredictionHorizon.INTRADAY,
            expected_return=self.expected_return,
            confidence=self.confidence,
            model_version=self.model_metadata.version,
            features_ref=self.features_ref,
            rationale=self.rationale,
        )


@dataclass(frozen=True, slots=True)
class ConservativeBaselineModel:
    """A dependency-free prior model for research and backtesting smoke tests."""

    metadata: BaselineModelMetadata
    probability_up_prior: Decimal
    mean_future_return: Decimal
    mean_future_volatility: Decimal
    config: BaselineModelConfig

    @classmethod
    def fit(
        cls,
        rows: Sequence[DatasetRow],
        *,
        trained_at: datetime,
        config: BaselineModelConfig,
        validation_rows: Sequence[DatasetRow] = (),
    ) -> ConservativeBaselineModel:
        training_rows = tuple(row for row in rows if row.actionable)
        if not training_rows:
            raise ValueError("baseline model requires at least one actionable training row")
        up_count = sum(1 for row in training_rows if row.label.direction is DirectionLabel.UP)
        probability_up = Decimal(up_count) / Decimal(len(training_rows))
        mean_return = _mean(tuple(row.label.future_return for row in training_rows))
        mean_volatility = _mean(tuple(row.label.future_volatility for row in training_rows))
        model = cls(
            metadata=BaselineModelMetadata(
                model_name=BASELINE_MODEL_NAME,
                version=BASELINE_MODEL_VERSION,
                feature_schema_version=training_rows[0].features.schema_version,
                trained_at=normalize_timestamp(trained_at),
                training_start=training_rows[0].features.generated_at,
                training_end=training_rows[-1].features.generated_at,
                label_horizon_steps=config.label_horizon_steps,
                metrics={},
                limitations=(
                    "research/backtesting only",
                    "baseline uses training-set priors and simple momentum nudges",
                    "output is probability/confidence only and cannot create orders",
                    "not a profitability claim",
                ),
            ),
            probability_up_prior=probability_up,
            mean_future_return=mean_return,
            mean_future_volatility=mean_volatility,
            config=config,
        )
        metrics = model.evaluate(validation_rows or training_rows)
        return cls(
            metadata=BaselineModelMetadata(
                model_name=model.metadata.model_name,
                version=model.metadata.version,
                feature_schema_version=model.metadata.feature_schema_version,
                trained_at=model.metadata.trained_at,
                training_start=model.metadata.training_start,
                training_end=model.metadata.training_end,
                label_horizon_steps=model.metadata.label_horizon_steps,
                metrics=metrics,
                limitations=model.metadata.limitations,
            ),
            probability_up_prior=model.probability_up_prior,
            mean_future_return=model.mean_future_return,
            mean_future_volatility=model.mean_future_volatility,
            config=model.config,
        )

    def predict(self, snapshot: FeatureSnapshot) -> BaselinePrediction:
        generated_at = normalize_timestamp(snapshot.generated_at)
        probability_up = self._probability_for(snapshot)
        probability_down = Decimal("1") - probability_up
        confidence = min(
            abs(probability_up - Decimal("0.5")) * Decimal("2"),
            self.config.max_confidence,
        )
        actionable = (
            snapshot.is_live_eligible and snapshot.generated_at >= self.metadata.training_end
        )
        quality = (
            snapshot.quality if snapshot.is_live_eligible else _non_actionable_quality(snapshot)
        )
        return BaselinePrediction(
            pair_symbol=snapshot.pair.symbol,
            generated_at=generated_at,
            model_metadata=self.metadata,
            features_ref=snapshot.inputs_ref,
            probability_up=probability_up,
            probability_down=probability_down,
            confidence=confidence,
            expected_return=self.mean_future_return,
            expected_volatility=self.mean_future_volatility,
            quality=quality,
            actionable=actionable and quality.is_trusted,
            rationale=(
                "Conservative baseline prior with a small current-return nudge; "
                "research/backtesting only."
            ),
        )

    def evaluate(self, rows: Sequence[DatasetRow]) -> Mapping[str, Decimal]:
        evaluation_rows = tuple(row for row in rows if row.actionable)
        if not evaluation_rows:
            return {
                "accuracy": Decimal("0"),
                "precision_up": Decimal("0"),
                "recall_up": Decimal("0"),
                "directional_hit_rate": Decimal("0"),
                "return_mae": Decimal("0"),
                "volatility_mae": Decimal("0"),
                "calibration_error": Decimal("0"),
            }
        predictions = tuple(self.predict(row.features) for row in evaluation_rows)
        return evaluate_directional_predictions(
            evaluation_rows,
            predicted_directions=tuple(
                prediction.predicted_direction for prediction in predictions
            ),
            predicted_probabilities_up=tuple(
                prediction.probability_up for prediction in predictions
            ),
            predicted_returns=tuple(prediction.expected_return for prediction in predictions),
            predicted_volatility=tuple(
                prediction.expected_volatility for prediction in predictions
            ),
        )

    def _probability_for(self, snapshot: FeatureSnapshot) -> Decimal:
        probability = self.probability_up_prior
        current_return = snapshot.values.get("market.return_1", Decimal("0"))
        if current_return > Decimal("0"):
            probability += self.config.probability_nudge
        elif current_return < Decimal("0"):
            probability -= self.config.probability_nudge
        return min(Decimal("0.95"), max(Decimal("0.05"), probability))


def _mean(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def _non_actionable_quality(snapshot: FeatureSnapshot) -> DataQualityStatus:
    if snapshot.quality.is_trusted:
        return DataQualityStatus(
            trust_level=DataTrustLevel.DEGRADED,
            issues=snapshot.quality.issues,
            source_ref=f"baseline:{snapshot.quality.source_ref}",
            checked_at=snapshot.generated_at,
        )
    return snapshot.quality
