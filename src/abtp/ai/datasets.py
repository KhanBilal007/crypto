"""Dataset construction utilities for research and backtesting."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.context import ContextBatch
from abtp.data import DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.features import FeatureSnapshot


class DirectionLabel(StrEnum):
    """Directional label vocabulary for future returns."""

    DOWN = "down"
    FLAT = "flat"
    UP = "up"


class DatasetSplitName(StrEnum):
    """Time-ordered dataset split names."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class ReturnLabel:
    """Future-window labels generated without using future values as features."""

    direction: DirectionLabel
    future_return: Decimal
    future_volatility: Decimal
    label_start: datetime
    label_end: datetime
    horizon_steps: int
    fee_bps: Decimal
    slippage_bps: Decimal

    @property
    def net_future_return(self) -> Decimal:
        return self.future_return - (self.fee_bps + self.slippage_bps) / Decimal("10000")


@dataclass(frozen=True, slots=True)
class DatasetRow:
    """One feature snapshot paired with its future-window label."""

    features: FeatureSnapshot
    label: ReturnLabel
    actionable: bool
    split: DatasetSplitName | None = None


@dataclass(frozen=True, slots=True)
class DatasetMetadata:
    """Trace metadata for a deterministic dataset build."""

    schema_version: str
    built_at: datetime
    feature_names: tuple[str, ...]
    label_horizon_steps: int
    fee_bps: Decimal
    slippage_bps: Decimal
    training_start: datetime | None
    training_end: datetime | None
    source_refs: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FeatureDataset:
    """A research/backtest feature dataset."""

    rows: tuple[DatasetRow, ...]
    metadata: DatasetMetadata

    def by_split(self, split: DatasetSplitName) -> tuple[DatasetRow, ...]:
        return tuple(row for row in self.rows if row.split is split)


@dataclass(frozen=True, slots=True)
class DatasetPartitions:
    """Time-ordered train/validation/test partitions."""

    train: tuple[DatasetRow, ...]
    validation: tuple[DatasetRow, ...]
    test: tuple[DatasetRow, ...]

    @property
    def rows(self) -> tuple[DatasetRow, ...]:
        return (*self.train, *self.validation, *self.test)


def build_feature_dataset(
    snapshots: Sequence[FeatureSnapshot],
    *,
    built_at: datetime,
    label_horizon_steps: int,
    fee_bps: Decimal = Decimal("0"),
    slippage_bps: Decimal = Decimal("0"),
    flat_threshold: Decimal = Decimal("0"),
    include_non_actionable: bool = False,
    context_batches: Sequence[ContextBatch] = (),
) -> FeatureDataset:
    """Build labels from future windows while keeping feature inputs current/past only."""

    if label_horizon_steps <= 0:
        raise ValueError("label_horizon_steps must be positive")
    if fee_bps < Decimal("0") or slippage_bps < Decimal("0"):
        raise ValueError("fee_bps and slippage_bps must be non-negative")
    ordered = tuple(sorted(snapshots, key=lambda snapshot: snapshot.generated_at))
    rows: list[DatasetRow] = []
    for index, snapshot in enumerate(ordered):
        if not include_non_actionable and not snapshot.is_live_eligible:
            continue
        label_index = index + label_horizon_steps
        if label_index >= len(ordered):
            continue
        future_window = ordered[index + 1 : label_index + 1]
        label = _label_for(
            snapshot,
            future_window,
            label_horizon_steps=label_horizon_steps,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            flat_threshold=flat_threshold,
        )
        rows.append(
            DatasetRow(features=snapshot, label=label, actionable=snapshot.is_live_eligible)
        )
    metadata = _metadata(
        rows=tuple(rows),
        ordered=ordered,
        built_at=normalize_timestamp(built_at),
        label_horizon_steps=label_horizon_steps,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        context_batches=context_batches,
    )
    return FeatureDataset(rows=tuple(rows), metadata=metadata)


def split_time_ordered(
    rows: Sequence[DatasetRow],
    *,
    train_ratio: Decimal = Decimal("0.60"),
    validation_ratio: Decimal = Decimal("0.20"),
) -> DatasetPartitions:
    """Split rows in timestamp order without shuffling or overlap."""

    if not Decimal("0") < train_ratio < Decimal("1"):
        raise ValueError("train_ratio must be between 0 and 1")
    if not Decimal("0") <= validation_ratio < Decimal("1"):
        raise ValueError("validation_ratio must be between 0 and 1")
    if train_ratio + validation_ratio >= Decimal("1"):
        raise ValueError("train_ratio + validation_ratio must be less than 1")
    ordered = tuple(sorted(rows, key=lambda row: row.features.generated_at))
    train_end = int(Decimal(len(ordered)) * train_ratio)
    validation_end = train_end + int(Decimal(len(ordered)) * validation_ratio)
    return DatasetPartitions(
        train=_with_split(ordered[:train_end], DatasetSplitName.TRAIN),
        validation=_with_split(ordered[train_end:validation_end], DatasetSplitName.VALIDATION),
        test=_with_split(ordered[validation_end:], DatasetSplitName.TEST),
    )


def dataset_with_splits(
    dataset: FeatureDataset,
    *,
    train_ratio: Decimal = Decimal("0.60"),
    validation_ratio: Decimal = Decimal("0.20"),
) -> FeatureDataset:
    """Return the same dataset metadata with rows assigned to time-ordered splits."""

    partitions = split_time_ordered(
        dataset.rows,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
    )
    return FeatureDataset(rows=partitions.rows, metadata=dataset.metadata)


def _label_for(
    snapshot: FeatureSnapshot,
    future_window: Sequence[FeatureSnapshot],
    *,
    label_horizon_steps: int,
    fee_bps: Decimal,
    slippage_bps: Decimal,
    flat_threshold: Decimal,
) -> ReturnLabel:
    if not future_window:
        raise ValueError("future_window is required")
    current_close = snapshot.values.get("market.close")
    future_close = future_window[-1].values.get("market.close")
    if current_close is None or future_close is None:
        raise ValueError("market.close is required for label generation")
    if future_window[0].generated_at <= snapshot.generated_at:
        raise ValueError("label window must start after feature generated_at")
    future_return = future_close / current_close - Decimal("1")
    returns = _window_returns((snapshot, *future_window))
    volatility = _mean_absolute(returns)
    return ReturnLabel(
        direction=_direction(future_return, flat_threshold),
        future_return=future_return,
        future_volatility=volatility,
        label_start=future_window[0].generated_at,
        label_end=future_window[-1].generated_at,
        horizon_steps=label_horizon_steps,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )


def _window_returns(window: Sequence[FeatureSnapshot]) -> tuple[Decimal, ...]:
    returns: list[Decimal] = []
    previous_close = window[0].values["market.close"]
    for snapshot in window[1:]:
        close = snapshot.values["market.close"]
        returns.append(close / previous_close - Decimal("1"))
        previous_close = close
    return tuple(returns)


def _mean_absolute(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum((abs(value) for value in values), Decimal("0")) / Decimal(len(values))


def _direction(value: Decimal, flat_threshold: Decimal) -> DirectionLabel:
    if value > flat_threshold:
        return DirectionLabel.UP
    if value < -flat_threshold:
        return DirectionLabel.DOWN
    return DirectionLabel.FLAT


def _with_split(
    rows: Sequence[DatasetRow],
    split: DatasetSplitName,
) -> tuple[DatasetRow, ...]:
    return tuple(
        DatasetRow(
            features=row.features,
            label=row.label,
            actionable=row.actionable,
            split=split,
        )
        for row in rows
    )


def _metadata(
    *,
    rows: tuple[DatasetRow, ...],
    ordered: tuple[FeatureSnapshot, ...],
    built_at: datetime,
    label_horizon_steps: int,
    fee_bps: Decimal,
    slippage_bps: Decimal,
    context_batches: Sequence[ContextBatch],
) -> DatasetMetadata:
    feature_names = tuple(sorted(ordered[0].values)) if ordered else ()
    source_refs = tuple(batch.quality.source_ref for batch in context_batches)
    return DatasetMetadata(
        schema_version=ordered[0].schema_version if ordered else "unknown",
        built_at=built_at,
        feature_names=feature_names,
        label_horizon_steps=label_horizon_steps,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        training_start=rows[0].features.generated_at if rows else None,
        training_end=rows[-1].features.generated_at if rows else None,
        source_refs=source_refs,
        limitations=(
            "research/backtesting only",
            "labels use future windows and must not be used as live features",
            "low-quality feature snapshots are excluded unless explicitly included",
        ),
    )


def quality_for_dataset_rows(
    rows: Sequence[DatasetRow], *, checked_at: datetime
) -> DataQualityStatus:
    """Aggregate row actionability into a simple dataset quality status."""

    issues = tuple(
        issue for row in rows for issue in row.features.quality.issues if not row.actionable
    )
    if issues:
        trust_level = (
            DataTrustLevel.REJECTED
            if any(issue.severity is DataTrustLevel.REJECTED for issue in issues)
            else DataTrustLevel.DEGRADED
        )
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=issues,
        source_ref="ai_dataset",
        checked_at=normalize_timestamp(checked_at),
    )
