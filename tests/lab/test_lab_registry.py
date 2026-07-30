from __future__ import annotations

from datetime import UTC, datetime

import pytest

from abtp.lab import (
    StrategyCatalogueEntry,
    StrategyCatalogueStatus,
    StrategyLaboratoryRegistry,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_strategy_laboratory_registry_filters_deterministically() -> None:
    registry = StrategyLaboratoryRegistry(
        (
            _entry("trend-v1", family="trend", regime_suitability=("trend_up",)),
            _entry("range-v1", family="range", regime_suitability=("range_bound",)),
            _entry("old-v1", status=StrategyCatalogueStatus.RETIRED),
        )
    )

    assert [entry.key for entry in registry.list(include_disabled=False)] == [
        "range-v1",
        "trend-v1",
    ]
    assert [entry.key for entry in registry.list(family="trend", include_disabled=False)] == [
        "trend-v1"
    ]
    assert [entry.key for entry in registry.list(regime_label="range_bound")] == ["range-v1"]
    assert registry.get("trend-v1").version == "1.0"


def test_duplicate_strategy_key_is_rejected() -> None:
    registry = StrategyLaboratoryRegistry((_entry("trend-v1"),))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(_entry("trend-v1"))


def test_mark_status_preserves_auditable_catalogue_state() -> None:
    registry = StrategyLaboratoryRegistry((_entry("trend-v1"),))

    updated = registry.mark_status(
        "trend-v1",
        StrategyCatalogueStatus.DISABLED,
        validation_ref="walk_forward:trend-v1",
    )

    assert updated.status is StrategyCatalogueStatus.DISABLED
    assert updated.validation_ref == "walk_forward:trend-v1"
    assert registry.audit_payload()["disabled_or_retired"] == "trend-v1"


def _entry(
    key: str,
    *,
    family: str = "trend",
    status: StrategyCatalogueStatus = StrategyCatalogueStatus.CANDIDATE,
    regime_suitability: tuple[str, ...] = ("trend_up",),
) -> StrategyCatalogueEntry:
    return StrategyCatalogueEntry(
        key=key,
        name=key,
        version="1.0",
        family=family,
        status=status,
        regime_suitability=regime_suitability,
        created_at=NOW,
        source_refs={"strategy": f"fixture:{key}"},
    )
