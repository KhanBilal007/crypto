"""Strategy laboratory catalogue and registration contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from abtp.data import normalize_timestamp


class StrategyCatalogueStatus(StrEnum):
    """Lifecycle status for laboratory strategy entries."""

    BENCHMARK = "benchmark"
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DISABLED = "disabled"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class StrategyCatalogueEntry:
    """Metadata for one strategy version in the laboratory catalogue."""

    key: str
    name: str
    version: str
    family: str
    status: StrategyCatalogueStatus = StrategyCatalogueStatus.CANDIDATE
    regime_suitability: tuple[str, ...] = ("unknown",)
    description: str = "laboratory strategy entry"
    parameter_space_ref: str | None = None
    validation_ref: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("strategy key is required")
        if not self.name.strip():
            raise ValueError("strategy name is required")
        if not self.version.strip():
            raise ValueError("strategy version is required")
        if not self.family.strip():
            raise ValueError("strategy family is required")
        if not self.regime_suitability:
            raise ValueError("at least one regime suitability label is required")
        if any(not regime.strip() for regime in self.regime_suitability):
            raise ValueError("regime labels cannot be blank")
        object.__setattr__(self, "created_at", normalize_timestamp(self.created_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def enabled_for_lab(self) -> bool:
        """Whether the entry can be benchmarked as a candidate."""

        return self.status not in {
            StrategyCatalogueStatus.DISABLED,
            StrategyCatalogueStatus.RETIRED,
        }

    def supports_regime(self, regime_label: str) -> bool:
        """Return whether the strategy declares suitability for a regime."""

        return regime_label in self.regime_suitability

    def with_status(
        self,
        status: StrategyCatalogueStatus,
        *,
        validation_ref: str | None = None,
    ) -> StrategyCatalogueEntry:
        """Return a copy with updated advisory laboratory status."""

        return StrategyCatalogueEntry(
            key=self.key,
            name=self.name,
            version=self.version,
            family=self.family,
            status=status,
            regime_suitability=self.regime_suitability,
            description=self.description,
            parameter_space_ref=self.parameter_space_ref,
            validation_ref=validation_ref if validation_ref is not None else self.validation_ref,
            created_at=self.created_at,
            source_refs=self.source_refs,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "family": self.family,
            "status": self.status.value,
            "regime_suitability": list(self.regime_suitability),
            "description": self.description,
            "parameter_space_ref": self.parameter_space_ref,
            "validation_ref": self.validation_ref,
            "created_at": self.created_at.isoformat(),
            "source_refs": dict(self.source_refs),
        }


class StrategyLaboratoryRegistry:
    """In-memory deterministic catalogue for many strategy versions."""

    def __init__(self, entries: Sequence[StrategyCatalogueEntry] = ()) -> None:
        self._entries: dict[str, StrategyCatalogueEntry] = {}
        for entry in entries:
            self.register(entry)

    def register(self, entry: StrategyCatalogueEntry) -> None:
        """Register one strategy entry by unique key."""

        if entry.key in self._entries:
            raise ValueError(f"strategy catalogue entry already registered: {entry.key}")
        self._entries[entry.key] = entry

    def upsert(self, entry: StrategyCatalogueEntry) -> None:
        """Insert or replace one strategy entry by key."""

        self._entries[entry.key] = entry

    def get(self, key: str) -> StrategyCatalogueEntry:
        """Return one entry or raise a clear lookup error."""

        try:
            return self._entries[key]
        except KeyError as exc:
            raise KeyError(f"unknown strategy catalogue entry: {key}") from exc

    def list(
        self,
        *,
        family: str | None = None,
        status: StrategyCatalogueStatus | None = None,
        regime_label: str | None = None,
        version: str | None = None,
        include_disabled: bool = True,
    ) -> tuple[StrategyCatalogueEntry, ...]:
        """Return stable filtered catalogue entries."""

        entries = tuple(self._entries[key] for key in sorted(self._entries))
        if family is not None:
            entries = tuple(entry for entry in entries if entry.family == family)
        if status is not None:
            entries = tuple(entry for entry in entries if entry.status is status)
        if regime_label is not None:
            entries = tuple(entry for entry in entries if entry.supports_regime(regime_label))
        if version is not None:
            entries = tuple(entry for entry in entries if entry.version == version)
        if not include_disabled:
            entries = tuple(entry for entry in entries if entry.enabled_for_lab)
        return entries

    def mark_status(
        self,
        key: str,
        status: StrategyCatalogueStatus,
        *,
        validation_ref: str | None = None,
    ) -> StrategyCatalogueEntry:
        """Update catalogue status without touching strategy implementation code."""

        updated = self.get(key).with_status(status, validation_ref=validation_ref)
        self.upsert(updated)
        return updated

    def audit_payload(self) -> dict[str, str]:
        """Return compact catalogue state for append-only audit records."""

        return {
            "entry_count": str(len(self._entries)),
            "entries": "|".join(self._entries),
            "disabled_or_retired": "|".join(
                entry.key for entry in self.list() if not entry.enabled_for_lab
            ),
        }
