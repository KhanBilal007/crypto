from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair
from abtp.features import FeatureSnapshot, InMemoryFeatureStore

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def snapshot() -> FeatureSnapshot:
    return FeatureSnapshot(
        pair=pair(),
        generated_at=NOW,
        schema_version="stage-015.v1",
        values={"market.close": Decimal("100")},
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref="features:stage-015.v1",
            checked_at=NOW,
        ),
        lookback_start=NOW - timedelta(minutes=1),
        lookback_end=NOW,
        source_refs={"candles": "candles:fixture"},
    )


def test_in_memory_store_keeps_snapshot_and_domain_mapping() -> None:
    store = InMemoryFeatureStore()
    saved = snapshot()

    snapshot_id = store.save(saved)
    domain_vector = saved.to_domain_feature_vector()

    assert store.get(snapshot_id) == saved
    assert domain_vector.feature_version == "stage-015.v1"
    assert domain_vector.inputs_ref.startswith("features:stage-015.v1:")


def test_empty_snapshot_cannot_be_stored_or_mapped_to_domain_vector() -> None:
    empty = FeatureSnapshot(
        pair=pair(),
        generated_at=NOW,
        schema_version="stage-015.v1",
        values={},
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.REJECTED,
            issues=(),
            source_ref="features:stage-015.v1",
            checked_at=NOW,
        ),
        lookback_start=NOW,
        lookback_end=NOW,
        source_refs={},
    )
    store = InMemoryFeatureStore()

    with pytest.raises(ValueError, match="empty feature snapshot"):
        store.save(empty)
    with pytest.raises(ValueError, match="empty feature vector"):
        empty.to_domain_feature_vector()
