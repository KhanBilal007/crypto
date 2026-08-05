from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.ai import (
    DatasetSplitName,
    DirectionLabel,
    build_feature_dataset,
    dataset_with_splits,
    split_time_ordered,
)
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair
from abtp.features import FeatureSnapshot

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def snapshot(index: int, close: str, *, trusted: bool = True) -> FeatureSnapshot:
    generated_at = NOW + timedelta(minutes=index)
    issues = (
        ()
        if trusted
        else (
            DataQualityIssue(
                flag="degraded_fixture",
                severity=DataTrustLevel.DEGRADED,
                reason="fixture degradation",
            ),
        )
    )
    return FeatureSnapshot(
        pair=pair(),
        generated_at=generated_at,
        schema_version="stage-015.v1",
        values={
            "market.close": Decimal(close),
            "market.return_1": Decimal("0.01"),
            "data_quality.flag_count": Decimal(len(issues)),
        },
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED if trusted else DataTrustLevel.DEGRADED,
            issues=issues,
            source_ref=f"features:{index}",
            checked_at=generated_at,
        ),
        lookback_start=generated_at - timedelta(minutes=3),
        lookback_end=generated_at,
        source_refs={"candles": f"candles:{index}"},
    )


def snapshots() -> tuple[FeatureSnapshot, ...]:
    return tuple(
        snapshot(index, close)
        for index, close in enumerate(("100", "101", "103", "106", "110", "115"))
    )


def test_dataset_labels_use_future_windows_without_leaking_into_features() -> None:
    dataset = build_feature_dataset(
        snapshots(),
        built_at=NOW + timedelta(hours=1),
        label_horizon_steps=2,
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
    )

    first = dataset.rows[0]

    assert len(dataset.rows) == 4
    assert first.features.generated_at == NOW
    assert first.label.label_start == NOW + timedelta(minutes=1)
    assert first.label.label_end == NOW + timedelta(minutes=2)
    assert first.label.future_return == Decimal("0.03")
    assert first.label.net_future_return == Decimal("0.0285")
    assert first.label.direction is DirectionLabel.UP
    assert first.features.values["market.close"] == Decimal("100")


def test_non_actionable_snapshots_are_excluded_unless_requested() -> None:
    items = (*snapshots()[:2], snapshot(2, "103", trusted=False), *snapshots()[3:])

    excluded = build_feature_dataset(
        items,
        built_at=NOW + timedelta(hours=1),
        label_horizon_steps=1,
    )
    included = build_feature_dataset(
        items,
        built_at=NOW + timedelta(hours=1),
        label_horizon_steps=1,
        include_non_actionable=True,
    )

    assert len(excluded.rows) == 4
    assert len(included.rows) == 5
    assert any(not row.actionable for row in included.rows)


def test_time_ordered_splits_preserve_integrity() -> None:
    dataset = build_feature_dataset(
        snapshots(),
        built_at=NOW + timedelta(hours=1),
        label_horizon_steps=1,
    )
    split_dataset = dataset_with_splits(
        dataset,
        train_ratio=Decimal("0.60"),
        validation_ratio=Decimal("0.20"),
    )
    partitions = split_time_ordered(
        dataset.rows,
        train_ratio=Decimal("0.60"),
        validation_ratio=Decimal("0.20"),
    )

    assert len(partitions.train) == 3
    assert len(partitions.validation) == 1
    assert len(partitions.test) == 1
    assert (
        partitions.train[-1].features.generated_at < partitions.validation[0].features.generated_at
    )
    assert (
        partitions.validation[-1].features.generated_at < partitions.test[0].features.generated_at
    )
    assert tuple(row.split for row in split_dataset.rows) == (
        DatasetSplitName.TRAIN,
        DatasetSplitName.TRAIN,
        DatasetSplitName.TRAIN,
        DatasetSplitName.VALIDATION,
        DatasetSplitName.TEST,
    )


def test_dataset_validation_rejects_invalid_horizon_and_missing_close() -> None:
    with pytest.raises(ValueError, match="label_horizon_steps"):
        build_feature_dataset(snapshots(), built_at=NOW, label_horizon_steps=0)

    bad = snapshot(0, "100")
    object.__setattr__(bad, "values", {"market.return_1": Decimal("0")})
    with pytest.raises(ValueError, match="market.close"):
        build_feature_dataset((bad, snapshot(1, "101")), built_at=NOW, label_horizon_steps=1)
