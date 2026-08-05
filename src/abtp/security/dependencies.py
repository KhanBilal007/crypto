"""Dependency audit note contracts without network access."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DependencyRiskLevel(StrEnum):
    """Dependency audit risk levels."""

    OK = "ok"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class DependencyAuditNote:
    """Local dependency security note."""

    package: str
    version: str
    risk_level: DependencyRiskLevel
    reason: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.package, "package"),
            (self.version, "version"),
            (self.reason, "reason"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")


@dataclass(frozen=True, slots=True)
class DependencyAuditReport:
    """Deterministic dependency audit report."""

    notes: tuple[DependencyAuditNote, ...]

    @property
    def blocked(self) -> bool:
        return any(note.risk_level is DependencyRiskLevel.BLOCKED for note in self.notes)

    @property
    def requires_review(self) -> bool:
        return any(note.risk_level is DependencyRiskLevel.REVIEW for note in self.notes)

    def require_not_blocked(self) -> None:
        if self.blocked:
            blocked = ",".join(
                note.package
                for note in self.notes
                if note.risk_level is DependencyRiskLevel.BLOCKED
            )
            raise RuntimeError(f"blocked dependency audit findings: {blocked}")

    def as_dict(self) -> dict[str, object]:
        return {
            "blocked": self.blocked,
            "requires_review": self.requires_review,
            "notes": [
                {
                    "package": note.package,
                    "version": note.version,
                    "risk_level": note.risk_level.value,
                    "reason": note.reason,
                }
                for note in self.notes
            ],
        }


def build_dependency_audit_report(
    notes: tuple[DependencyAuditNote, ...],
) -> DependencyAuditReport:
    """Build a deterministic dependency audit report from local notes."""

    return DependencyAuditReport(notes=tuple(sorted(notes, key=lambda item: item.package)))
