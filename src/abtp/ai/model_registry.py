"""Metadata registry contracts for AI model versions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.ai.baseline import BaselineModelMetadata
from abtp.data import DataQualityStatus, DataTrustLevel, normalize_timestamp


class ModelLifecycleStatus(StrEnum):
    """Lifecycle state for a registered model version."""

    REGISTERED = "registered"
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DEGRADED = "degraded"
    RETIRED = "retired"
    REJECTED = "rejected"


class ModelApprovalStatus(StrEnum):
    """Manual approval level for model use."""

    UNAPPROVED = "unapproved"
    RESEARCH_APPROVED = "research_approved"
    PAPER_APPROVED = "paper_approved"
    LIVE_APPROVED = "live_approved"


@dataclass(frozen=True, slots=True)
class ModelRegistryEntry:
    """Registry metadata for one model version."""

    model_name: str
    version: str
    feature_schema_version: str
    model_family: str
    label_horizon_steps: int
    status: ModelLifecycleStatus = ModelLifecycleStatus.CANDIDATE
    approval_status: ModelApprovalStatus = ModelApprovalStatus.UNAPPROVED
    created_at: datetime = field(default_factory=lambda: normalize_timestamp(datetime.now()))
    limitations: tuple[str, ...] = ("metadata-only model registry entry",)
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name is required")
        if not self.version.strip():
            raise ValueError("model version is required")
        if not self.feature_schema_version.strip():
            raise ValueError("feature_schema_version is required")
        if not self.model_family.strip():
            raise ValueError("model_family is required")
        if self.label_horizon_steps <= 0:
            raise ValueError("label_horizon_steps must be positive")
        if not self.limitations:
            raise ValueError("model limitations are required")
        object.__setattr__(self, "created_at", normalize_timestamp(self.created_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def model_ref(self) -> str:
        return f"{self.model_name}:{self.version}"

    @property
    def selectable(self) -> bool:
        return self.status not in {ModelLifecycleStatus.RETIRED, ModelLifecycleStatus.REJECTED}

    def with_status(
        self,
        status: ModelLifecycleStatus,
        *,
        approval_status: ModelApprovalStatus | None = None,
    ) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_name=self.model_name,
            version=self.version,
            feature_schema_version=self.feature_schema_version,
            model_family=self.model_family,
            label_horizon_steps=self.label_horizon_steps,
            status=status,
            approval_status=approval_status or self.approval_status,
            created_at=self.created_at,
            limitations=self.limitations,
            source_refs=self.source_refs,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "model_ref": self.model_ref,
            "feature_schema_version": self.feature_schema_version,
            "model_family": self.model_family,
            "label_horizon_steps": self.label_horizon_steps,
            "status": self.status.value,
            "approval_status": self.approval_status.value,
            "created_at": self.created_at.isoformat(),
            "limitations": list(self.limitations),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class ModelTrainingRecord:
    """Auditable training-history metadata without model artifacts or secrets."""

    model_name: str
    version: str
    trained_at: datetime
    training_start: datetime
    training_end: datetime
    feature_schema_version: str
    label_horizon_steps: int
    sample_count: int
    metrics: Mapping[str, Decimal]
    limitations: tuple[str, ...]
    source_ref: str = "model_training:metadata"

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name is required")
        if not self.version.strip():
            raise ValueError("model version is required")
        if self.training_end < self.training_start:
            raise ValueError("training_end cannot be before training_start")
        if not self.feature_schema_version.strip():
            raise ValueError("feature_schema_version is required")
        if self.label_horizon_steps <= 0:
            raise ValueError("label_horizon_steps must be positive")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")
        if not self.limitations:
            raise ValueError("training limitations are required")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        object.__setattr__(self, "trained_at", normalize_timestamp(self.trained_at))
        object.__setattr__(self, "training_start", normalize_timestamp(self.training_start))
        object.__setattr__(self, "training_end", normalize_timestamp(self.training_end))
        object.__setattr__(self, "metrics", dict(self.metrics))

    @property
    def model_ref(self) -> str:
        return f"{self.model_name}:{self.version}"

    def as_dict(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "model_ref": self.model_ref,
            "trained_at": self.trained_at.isoformat(),
            "training_start": self.training_start.isoformat(),
            "training_end": self.training_end.isoformat(),
            "feature_schema_version": self.feature_schema_version,
            "label_horizon_steps": self.label_horizon_steps,
            "sample_count": self.sample_count,
            "metrics": {key: str(value) for key, value in self.metrics.items()},
            "limitations": list(self.limitations),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class ModelEvaluationSnapshot:
    """Evaluation metrics for one model version and dataset/split."""

    model_name: str
    version: str
    evaluated_at: datetime
    dataset_ref: str
    split_name: str
    metrics: Mapping[str, Decimal]
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name is required")
        if not self.version.strip():
            raise ValueError("model version is required")
        if not self.dataset_ref.strip():
            raise ValueError("dataset_ref is required")
        if not self.split_name.strip():
            raise ValueError("split_name is required")
        if not self.metrics:
            raise ValueError("evaluation metrics are required")
        object.__setattr__(self, "evaluated_at", normalize_timestamp(self.evaluated_at))
        object.__setattr__(self, "metrics", dict(self.metrics))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def model_ref(self) -> str:
        return f"{self.model_name}:{self.version}"

    def as_dict(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "model_ref": self.model_ref,
            "evaluated_at": self.evaluated_at.isoformat(),
            "dataset_ref": self.dataset_ref,
            "split_name": self.split_name,
            "metrics": {key: str(value) for key, value in self.metrics.items()},
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
        }


class ModelRegistry:
    """In-memory model metadata registry keyed by model name and version."""

    def __init__(self, entries: Sequence[ModelRegistryEntry] = ()) -> None:
        self._entries: dict[str, ModelRegistryEntry] = {}
        self._training: dict[str, list[ModelTrainingRecord]] = {}
        self._evaluations: dict[str, list[ModelEvaluationSnapshot]] = {}
        for entry in entries:
            self.register(entry)

    def register(self, entry: ModelRegistryEntry) -> None:
        if entry.model_ref in self._entries:
            raise ValueError(f"model already registered: {entry.model_ref}")
        self._entries[entry.model_ref] = entry

    def upsert(self, entry: ModelRegistryEntry) -> None:
        self._entries[entry.model_ref] = entry

    def get(self, model_name: str, version: str) -> ModelRegistryEntry:
        model_ref = f"{model_name}:{version}"
        try:
            return self._entries[model_ref]
        except KeyError as exc:
            raise KeyError(f"unknown model: {model_ref}") from exc

    def list(
        self,
        *,
        model_name: str | None = None,
        model_family: str | None = None,
        status: ModelLifecycleStatus | None = None,
        feature_schema_version: str | None = None,
        include_retired: bool = True,
    ) -> tuple[ModelRegistryEntry, ...]:
        entries = tuple(self._entries[key] for key in sorted(self._entries))
        if model_name is not None:
            entries = tuple(entry for entry in entries if entry.model_name == model_name)
        if model_family is not None:
            entries = tuple(entry for entry in entries if entry.model_family == model_family)
        if status is not None:
            entries = tuple(entry for entry in entries if entry.status is status)
        if feature_schema_version is not None:
            entries = tuple(
                entry for entry in entries if entry.feature_schema_version == feature_schema_version
            )
        if not include_retired:
            entries = tuple(entry for entry in entries if entry.selectable)
        return entries

    def record_training(self, record: ModelTrainingRecord) -> None:
        self.get(record.model_name, record.version)
        self._training.setdefault(record.model_ref, []).append(record)

    def record_evaluation(self, snapshot: ModelEvaluationSnapshot) -> None:
        self.get(snapshot.model_name, snapshot.version)
        self._evaluations.setdefault(snapshot.model_ref, []).append(snapshot)

    def training_history(self, model_ref: str) -> tuple[ModelTrainingRecord, ...]:
        return tuple(sorted(self._training.get(model_ref, ()), key=lambda item: item.trained_at))

    def latest_training(self, model_ref: str) -> ModelTrainingRecord | None:
        history = self.training_history(model_ref)
        return history[-1] if history else None

    def evaluations(self, model_ref: str) -> tuple[ModelEvaluationSnapshot, ...]:
        return tuple(
            sorted(self._evaluations.get(model_ref, ()), key=lambda item: item.evaluated_at)
        )

    def latest_evaluation(self, model_ref: str) -> ModelEvaluationSnapshot | None:
        snapshots = self.evaluations(model_ref)
        return snapshots[-1] if snapshots else None

    def mark_retired(self, model_name: str, version: str) -> ModelRegistryEntry:
        entry = self.get(model_name, version).with_status(ModelLifecycleStatus.RETIRED)
        self.upsert(entry)
        return entry

    def audit_payload(self) -> dict[str, str]:
        return {
            "model_count": str(len(self._entries)),
            "registered_models": "|".join(sorted(self._entries)),
            "retired_models": "|".join(
                entry.model_ref for entry in self.list(status=ModelLifecycleStatus.RETIRED)
            ),
        }


def registry_entry_from_baseline_metadata(
    metadata: BaselineModelMetadata,
    *,
    model_family: str = "baseline",
    status: ModelLifecycleStatus = ModelLifecycleStatus.CANDIDATE,
    approval_status: ModelApprovalStatus = ModelApprovalStatus.RESEARCH_APPROVED,
    source_refs: Mapping[str, str] | None = None,
) -> ModelRegistryEntry:
    """Create a registry entry from Stage 017 baseline metadata."""

    return ModelRegistryEntry(
        model_name=metadata.model_name,
        version=metadata.version,
        feature_schema_version=metadata.feature_schema_version,
        model_family=model_family,
        label_horizon_steps=metadata.label_horizon_steps,
        status=status,
        approval_status=approval_status,
        created_at=metadata.trained_at,
        limitations=metadata.limitations,
        source_refs=source_refs or {"baseline_metadata": metadata.version},
    )


def training_record_from_baseline_metadata(
    metadata: BaselineModelMetadata,
    *,
    sample_count: int,
    source_ref: str = "baseline:metadata",
) -> ModelTrainingRecord:
    """Create a training-history record from Stage 017 baseline metadata."""

    return ModelTrainingRecord(
        model_name=metadata.model_name,
        version=metadata.version,
        trained_at=metadata.trained_at,
        training_start=metadata.training_start,
        training_end=metadata.training_end,
        feature_schema_version=metadata.feature_schema_version,
        label_horizon_steps=metadata.label_horizon_steps,
        sample_count=sample_count,
        metrics=metadata.metrics,
        limitations=metadata.limitations,
        source_ref=source_ref,
    )


def trusted_model_evaluation(
    *,
    model_name: str,
    version: str,
    evaluated_at: datetime,
    dataset_ref: str,
    split_name: str,
    metrics: Mapping[str, Decimal],
) -> ModelEvaluationSnapshot:
    """Build a trusted deterministic evaluation fixture/metadata snapshot."""

    return ModelEvaluationSnapshot(
        model_name=model_name,
        version=version,
        evaluated_at=evaluated_at,
        dataset_ref=dataset_ref,
        split_name=split_name,
        metrics=metrics,
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=f"model_evaluation:{model_name}:{version}",
            checked_at=normalize_timestamp(evaluated_at),
        ),
    )
