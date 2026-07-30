"""Deterministic parameter-space helpers for the strategy laboratory."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import product


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """One bounded strategy parameter definition."""

    name: str
    minimum: Decimal
    maximum: Decimal
    step: Decimal
    default: Decimal
    description: str = "strategy parameter"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("parameter name is required")
        if self.step <= Decimal("0"):
            raise ValueError("parameter step must be positive")
        if self.minimum > self.maximum:
            raise ValueError("parameter minimum cannot exceed maximum")
        if not self.minimum <= self.default <= self.maximum:
            raise ValueError("parameter default must be within bounds")

    def values(self) -> tuple[Decimal, ...]:
        """Return deterministic candidate values including the default."""

        values: list[Decimal] = []
        current = self.minimum
        while current <= self.maximum:
            values.append(current)
            current += self.step
        if self.default not in values:
            values.append(self.default)
        return tuple(sorted(set(values)))

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "minimum": str(self.minimum),
            "maximum": str(self.maximum),
            "step": str(self.step),
            "default": str(self.default),
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class ParameterCandidate:
    """One generated parameter configuration candidate."""

    strategy_key: str
    values: Mapping[str, Decimal]
    candidate_ref: str
    source_ref: str

    def __post_init__(self) -> None:
        if not self.strategy_key.strip():
            raise ValueError("strategy_key is required")
        if not self.values:
            raise ValueError("candidate values are required")
        if not self.candidate_ref.strip():
            raise ValueError("candidate_ref is required")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        object.__setattr__(self, "values", dict(self.values))

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "values": {key: str(value) for key, value in self.values.items()},
            "candidate_ref": self.candidate_ref,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class ParameterSearchSpace:
    """Bounded candidate generator for one strategy version."""

    strategy_key: str
    parameters: tuple[ParameterSpec, ...]
    max_candidates: int = 25
    source_ref: str = "lab:parameter_space"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_key.strip():
            raise ValueError("strategy_key is required")
        if not self.parameters:
            raise ValueError("at least one parameter spec is required")
        if self.max_candidates <= 0:
            raise ValueError("max_candidates must be positive")
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("parameter names must be unique")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def candidates(self) -> tuple[ParameterCandidate, ...]:
        """Generate deterministic candidates without applying them to a strategy."""

        names = tuple(parameter.name for parameter in self.parameters)
        value_sets = tuple(parameter.values() for parameter in self.parameters)
        candidates = [
            ParameterCandidate(
                strategy_key=self.strategy_key,
                values=dict(zip(names, values, strict=True)),
                candidate_ref=f"{self.strategy_key}:candidate:{index:03d}",
                source_ref=self.source_ref,
            )
            for index, values in enumerate(product(*value_sets))
        ]
        candidates.sort(
            key=lambda item: tuple((key, item.values[key]) for key in sorted(item.values))
        )
        return tuple(candidates[: self.max_candidates])

    @property
    def default_candidate(self) -> ParameterCandidate:
        """Return the configured default parameter candidate."""

        return ParameterCandidate(
            strategy_key=self.strategy_key,
            values={parameter.name: parameter.default for parameter in self.parameters},
            candidate_ref=f"{self.strategy_key}:candidate:default",
            source_ref=self.source_ref,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "parameters": [parameter.as_dict() for parameter in self.parameters],
            "max_candidates": self.max_candidates,
            "source_ref": self.source_ref,
            "metadata": dict(self.metadata),
        }


def generate_parameter_candidates(
    search_space: ParameterSearchSpace,
    *,
    include_default: bool = True,
) -> tuple[ParameterCandidate, ...]:
    """Generate stable parameter candidates for offline evaluation."""

    candidates = search_space.candidates()
    if not include_default:
        return candidates
    if any(candidate.values == search_space.default_candidate.values for candidate in candidates):
        return candidates
    return (search_space.default_candidate, *candidates[:-1])


def merge_candidate_overrides(
    candidate: ParameterCandidate,
    overrides: Mapping[str, Decimal],
) -> ParameterCandidate:
    """Return an overridden candidate for experiments without mutating the source."""

    merged = dict(candidate.values)
    merged.update(overrides)
    return ParameterCandidate(
        strategy_key=candidate.strategy_key,
        values=merged,
        candidate_ref=f"{candidate.candidate_ref}:override",
        source_ref=candidate.source_ref,
    )


def rank_candidate_results(
    candidates: Sequence[ParameterCandidate],
    scores: Mapping[str, Decimal],
) -> tuple[ParameterCandidate, ...]:
    """Rank candidates by supplied offline score, then by candidate ref."""

    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -scores.get(candidate.candidate_ref, Decimal("0")),
                candidate.candidate_ref,
            ),
        )
    )
