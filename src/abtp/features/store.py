"""Feature snapshot storage adapters."""

from __future__ import annotations

from typing import Protocol

from abtp.features.schema import FeatureSnapshot
from abtp.repositories.intelligence import IntelligenceRepository


class FeatureSnapshotStore(Protocol):
    """Storage boundary for feature snapshots."""

    def save(self, snapshot: FeatureSnapshot) -> str:
        """Persist or retain a feature snapshot and return a stable reference."""


class RepositoryFeatureStore:
    """Map Stage 015 feature snapshots to the Stage 008 intelligence repository."""

    def __init__(self, repository: IntelligenceRepository) -> None:
        self._repository = repository

    def save(self, snapshot: FeatureSnapshot) -> str:
        return self._repository.add_feature_vector(snapshot.to_domain_feature_vector())


class InMemoryFeatureStore:
    """Deterministic feature store for tests and local pipeline composition."""

    def __init__(self) -> None:
        self._snapshots: dict[str, FeatureSnapshot] = {}
        self._next_id = 1

    def save(self, snapshot: FeatureSnapshot) -> str:
        if not snapshot.values:
            raise ValueError("cannot store an empty feature snapshot")
        snapshot_id = f"feature:{self._next_id}"
        self._next_id += 1
        self._snapshots[snapshot_id] = snapshot
        return snapshot_id

    def get(self, snapshot_id: str) -> FeatureSnapshot | None:
        return self._snapshots.get(snapshot_id)
