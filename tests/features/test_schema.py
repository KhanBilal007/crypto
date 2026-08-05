from __future__ import annotations

from decimal import Decimal

import pytest

from abtp.data import DataTrustLevel
from abtp.features import (
    FEATURE_SCHEMA_VERSION,
    FeatureDataType,
    FeatureDefinition,
    FeatureSchema,
    FeatureSourceKind,
    default_feature_schema,
)


def test_default_schema_has_stable_required_names() -> None:
    schema = default_feature_schema()

    assert schema.version == FEATURE_SCHEMA_VERSION
    assert schema.required_names == (
        "market.close",
        "market.return_1",
        "market.return_3",
        "market.volume_ratio",
        "indicator.sma.sma",
        "indicator.rsi.rsi",
        "indicator.atr.atr_pct",
        "data_quality.flag_count",
    )
    assert schema.get("market.close").data_type is FeatureDataType.DECIMAL


def test_schema_rejects_duplicates_unknowns_and_missing_required_values() -> None:
    definition = FeatureDefinition(
        name="x",
        data_type=FeatureDataType.DECIMAL,
        source_kind=FeatureSourceKind.CANDLES,
        source_name="x",
        required=True,
        description="x",
    )

    with pytest.raises(ValueError, match="duplicate feature"):
        FeatureSchema(version="test", definitions=(definition, definition))

    issues = FeatureSchema(version="test", definitions=(definition,)).validate_values(
        {"unknown": Decimal("1")}
    )

    assert tuple(issue.flag for issue in issues) == (
        "unknown_feature",
        "missing_required_feature",
    )
    assert all(issue.severity is DataTrustLevel.REJECTED for issue in issues)
