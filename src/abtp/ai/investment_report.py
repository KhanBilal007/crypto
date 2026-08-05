"""Explainable advisory AI investment report generator."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class InvestmentReportSectionType(StrEnum):
    """Required sections for the institutional-style investment report."""

    WHY_BUY = "why_buy"
    WHY_SELL = "why_sell"
    WHY_HOLD = "why_hold"
    MARKET_CYCLE = "market_cycle"
    MACRO_ANALYSIS = "macro_analysis"
    ONCHAIN = "onchain"
    FUNDAMENTALS = "fundamentals"
    AI_VOTES = "ai_votes"
    RISK = "risk"
    EXPECTED_RETURN = "expected_return"
    EXPECTED_HOLDING = "expected_holding"
    PORTFOLIO_IMPACT = "portfolio_impact"


class InvestmentReportStance(StrEnum):
    """Advisory stance of one report section."""

    SUPPORTIVE = "supportive"
    OPPOSING = "opposing"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class InvestmentReportRecommendation(StrEnum):
    """Advisory report conclusion with no trading authority."""

    BUY_REVIEW = "buy_review"
    SELL_REVIEW = "sell_review"
    HOLD_REVIEW = "hold_review"
    NO_DECISION = "no_decision"


REQUIRED_SECTION_TYPES: frozenset[InvestmentReportSectionType] = frozenset(
    InvestmentReportSectionType
)


@dataclass(frozen=True, slots=True)
class InvestmentReportPolicy:
    """Conservative thresholds for Stage 063 report conclusions."""

    minimum_confidence: Decimal = Decimal("0.45")
    minimum_directional_edge: Decimal = Decimal("0.10")
    max_rejected_sections: int = 0
    require_all_sections: bool = True
    policy_version: str = "stage-063.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("minimum_confidence", self.minimum_confidence),
            ("minimum_directional_edge", self.minimum_directional_edge),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_rejected_sections < 0:
            raise ValueError("max_rejected_sections cannot be negative")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class InvestmentReportSection:
    """One explainable report section from supplied advisory evidence."""

    section_type: InvestmentReportSectionType
    title: str
    summary: str
    stance: InvestmentReportStance
    confidence: Decimal
    quality: DataQualityStatus
    evidence_points: tuple[str, ...]
    source_refs: Mapping[str, str] = field(default_factory=dict)
    weight: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        object.__setattr__(self, "section_type", InvestmentReportSectionType(self.section_type))
        object.__setattr__(self, "stance", InvestmentReportStance(self.stance))
        if not self.title.strip():
            raise ValueError("report section title is required")
        if not self.summary.strip():
            raise ValueError("report section summary is required")
        if not DECIMAL_ZERO <= self.confidence <= DECIMAL_ONE:
            raise ValueError("report section confidence must be between 0 and 1")
        if self.weight <= DECIMAL_ZERO:
            raise ValueError("report section weight must be positive")
        if not self.evidence_points:
            raise ValueError("report section evidence points are required")
        object.__setattr__(self, "evidence_points", tuple(self.evidence_points))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def weighted_confidence(self) -> Decimal:
        if not self.quality.is_trusted:
            return DECIMAL_ZERO
        return self.confidence * self.weight

    def as_dict(self) -> dict[str, object]:
        return {
            "section_type": self.section_type.value,
            "title": self.title,
            "summary": self.summary,
            "stance": self.stance.value,
            "confidence": str(self.confidence),
            "weight": str(self.weight),
            "weighted_confidence": str(self.weighted_confidence),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "evidence_points": list(self.evidence_points),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class InvestmentReportInput:
    """Inputs for one institutional-style investment report."""

    asset_symbol: str
    generated_at: datetime
    sections: Sequence[InvestmentReportSection]
    expected_return_pct: Decimal | None = None
    expected_holding_period: str | None = None
    report_id: str | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        asset = self.asset_symbol.strip().upper()
        if not asset:
            raise ValueError("asset_symbol is required")
        normalized_sections = tuple(self.sections)
        if not normalized_sections:
            raise ValueError("investment report requires sections")
        seen: set[InvestmentReportSectionType] = set()
        for section in normalized_sections:
            if section.section_type in seen:
                raise ValueError(f"duplicate report section: {section.section_type.value}")
            seen.add(section.section_type)
        if self.expected_holding_period is not None and not self.expected_holding_period.strip():
            raise ValueError("expected_holding_period cannot be blank")
        object.__setattr__(self, "asset_symbol", asset)
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "sections", normalized_sections)
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class InvestmentReportScorecard:
    """Directional scorecard behind the report conclusion."""

    supportive_score: Decimal
    opposing_score: Decimal
    neutral_score: Decimal
    included_weight: Decimal
    directional_edge: Decimal
    confidence: Decimal

    def __post_init__(self) -> None:
        for name, value in (
            ("supportive_score", self.supportive_score),
            ("opposing_score", self.opposing_score),
            ("neutral_score", self.neutral_score),
            ("included_weight", self.included_weight),
            ("confidence", self.confidence),
        ):
            if value < DECIMAL_ZERO:
                raise ValueError(f"{name} cannot be negative")
        if not DECIMAL_ZERO <= self.confidence <= DECIMAL_ONE:
            raise ValueError("scorecard confidence must be between 0 and 1")

    def as_dict(self) -> dict[str, str]:
        return {
            "supportive_score": str(self.supportive_score),
            "opposing_score": str(self.opposing_score),
            "neutral_score": str(self.neutral_score),
            "included_weight": str(self.included_weight),
            "directional_edge": str(self.directional_edge),
            "confidence": str(self.confidence),
        }


@dataclass(frozen=True, slots=True)
class AIInvestmentReport:
    """Structured institutional-style report with no trading authority."""

    report_id: str
    asset_symbol: str
    generated_at: datetime
    recommendation: InvestmentReportRecommendation
    scorecard: InvestmentReportScorecard
    sections: tuple[InvestmentReportSection, ...]
    why_buy: tuple[str, ...]
    why_sell: tuple[str, ...]
    why_hold: tuple[str, ...]
    expected_return_pct: Decimal | None
    expected_holding_period: str | None
    portfolio_impact_summary: str
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "AI investment reports are advisory research context only.",
        "Reports cannot create signals, risk decisions, order intents, or execution.",
        "Reports cannot approve live trading or bypass the Risk Management Engine.",
        "Report generation uses supplied evidence only and does not call providers.",
        "No profit is guaranteed by an investment report.",
    )

    def __post_init__(self) -> None:
        if not self.report_id.strip():
            raise ValueError("report_id is required")
        if not self.asset_symbol.strip():
            raise ValueError("asset_symbol is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(
            self,
            "recommendation",
            InvestmentReportRecommendation(self.recommendation),
        )
        object.__setattr__(self, "sections", tuple(self.sections))
        if not self.sections:
            raise ValueError("investment report requires sections")
        if not self.reasons:
            raise ValueError("investment report requires reasons")
        if not self.portfolio_impact_summary.strip():
            raise ValueError("portfolio_impact_summary is required")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("investment report limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def actionable_context(self) -> bool:
        return self.recommendation is not InvestmentReportRecommendation.NO_DECISION

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("AI investment report cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("AI investment report cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("AI investment report cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("AI investment report cannot submit orders")

    def as_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "asset_symbol": self.asset_symbol,
            "generated_at": self.generated_at.isoformat(),
            "recommendation": self.recommendation.value,
            "scorecard": self.scorecard.as_dict(),
            "sections": [section.as_dict() for section in self.sections],
            "why_buy": list(self.why_buy),
            "why_sell": list(self.why_sell),
            "why_hold": list(self.why_hold),
            "expected_return_pct": (
                str(self.expected_return_pct) if self.expected_return_pct is not None else None
            ),
            "expected_holding_period": self.expected_holding_period,
            "portfolio_impact_summary": self.portfolio_impact_summary,
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "report_id": self.report_id,
            "asset_symbol": self.asset_symbol,
            "recommendation": self.recommendation.value,
            "confidence": str(self.scorecard.confidence),
            "directional_edge": str(self.scorecard.directional_edge),
            "expected_return_pct": (
                str(self.expected_return_pct) if self.expected_return_pct is not None else None
            ),
            "expected_holding_period": self.expected_holding_period,
            "quality": self.quality.trust_level.value,
            "rejection_reasons": "|".join(self.rejection_reasons),
            "policy_version": self.policy_version,
        }

    def render_markdown(self) -> str:
        """Render a deterministic human-readable report."""

        lines = [
            f"# Institutional Investment Report: {self.asset_symbol}",
            "",
            f"- Recommendation: {self.recommendation.value}",
            f"- Confidence: {self.scorecard.confidence}",
            f"- Quality: {self.quality.trust_level.value}",
            f"- Expected return: {_optional_decimal(self.expected_return_pct)}",
            f"- Expected holding: {self.expected_holding_period or 'not supplied'}",
            "",
            "## Why Buy",
            *_bullet_lines(self.why_buy),
            "",
            "## Why Sell",
            *_bullet_lines(self.why_sell),
            "",
            "## Why Hold",
            *_bullet_lines(self.why_hold),
            "",
            "## Evidence Sections",
        ]
        for section in self.sections:
            lines.extend(
                (
                    f"### {section.title}",
                    f"- Stance: {section.stance.value}",
                    f"- Confidence: {section.confidence}",
                    f"- Quality: {section.quality.trust_level.value}",
                    f"- Summary: {section.summary}",
                    *_bullet_lines(section.evidence_points),
                    "",
                )
            )
        if self.rejection_reasons:
            lines.extend(("## Rejection Reasons", *_bullet_lines(self.rejection_reasons), ""))
        lines.extend(("## Limitations", *_bullet_lines(self.limitations)))
        return "\n".join(lines)


def generate_investment_report(
    report_input: InvestmentReportInput,
    *,
    policy: InvestmentReportPolicy | None = None,
) -> AIInvestmentReport:
    """Generate a deterministic advisory report from supplied evidence sections."""

    active_policy = policy or InvestmentReportPolicy()
    issues = _issues(report_input, active_policy)
    quality = _quality(report_input, issues, checked_at=report_input.generated_at)
    scorecard = _scorecard(report_input.sections)
    rejection_reasons = _rejection_reasons(report_input, active_policy, scorecard, quality)
    recommendation = _recommendation(scorecard, rejection_reasons, active_policy)
    reasons = _reasons(report_input, scorecard, recommendation, rejection_reasons)
    default_report_id = (
        f"investment-report-{report_input.asset_symbol.lower()}-{report_input.generated_at.date()}"
    )
    return AIInvestmentReport(
        report_id=report_input.report_id or default_report_id,
        asset_symbol=report_input.asset_symbol,
        generated_at=report_input.generated_at,
        recommendation=recommendation,
        scorecard=scorecard,
        sections=tuple(report_input.sections),
        why_buy=_points_for(report_input.sections, InvestmentReportSectionType.WHY_BUY),
        why_sell=_points_for(report_input.sections, InvestmentReportSectionType.WHY_SELL),
        why_hold=_points_for(report_input.sections, InvestmentReportSectionType.WHY_HOLD),
        expected_return_pct=report_input.expected_return_pct,
        expected_holding_period=report_input.expected_holding_period,
        portfolio_impact_summary=_section_summary(
            report_input.sections, InvestmentReportSectionType.PORTFOLIO_IMPACT
        ),
        reasons=reasons,
        rejection_reasons=tuple(rejection_reasons),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=report_input.source_refs,
    )


def section_from_mapping(
    *,
    section_type: InvestmentReportSectionType,
    title: str,
    summary: str,
    stance: InvestmentReportStance,
    confidence: Decimal,
    quality: DataQualityStatus,
    evidence: Mapping[str, JsonValue],
    source_refs: Mapping[str, str] | None = None,
    weight: Decimal = Decimal("1"),
) -> InvestmentReportSection:
    """Build a section from provider-neutral structured evidence."""

    if not evidence:
        raise ValueError("section evidence mapping cannot be empty")
    points = tuple(f"{key}: {value}" for key, value in sorted(evidence.items()))
    return InvestmentReportSection(
        section_type=section_type,
        title=title,
        summary=summary,
        stance=stance,
        confidence=confidence,
        quality=quality,
        evidence_points=points,
        source_refs=source_refs or {},
        weight=weight,
    )


def _issues(
    report_input: InvestmentReportInput,
    policy: InvestmentReportPolicy,
) -> list[DataQualityIssue]:
    issues = [issue for section in report_input.sections for issue in section.quality.issues]
    if report_input.stale:
        issues.append(
            DataQualityIssue(
                flag="stale_investment_report_input",
                severity=DataTrustLevel.REJECTED,
                reason="investment report input is stale",
            )
        )
    if policy.require_all_sections:
        present = {section.section_type for section in report_input.sections}
        missing = sorted(section.value for section in REQUIRED_SECTION_TYPES - present)
        if missing:
            issues.append(
                DataQualityIssue(
                    flag="missing_report_sections",
                    severity=DataTrustLevel.REJECTED,
                    reason=f"missing required report sections: {', '.join(missing)}",
                )
            )
    rejected_count = sum(1 for section in report_input.sections if section.quality.is_rejected)
    if rejected_count > policy.max_rejected_sections:
        issues.append(
            DataQualityIssue(
                flag="rejected_report_sections",
                severity=DataTrustLevel.REJECTED,
                reason=f"{rejected_count} report sections are rejected",
            )
        )
    degraded_count = sum(1 for section in report_input.sections if section.quality.is_degraded)
    if degraded_count:
        issues.append(
            DataQualityIssue(
                flag="degraded_report_sections",
                severity=DataTrustLevel.DEGRADED,
                reason=f"{degraded_count} report sections are degraded",
            )
        )
    return issues


def _quality(
    report_input: InvestmentReportInput,
    issues: Sequence[DataQualityIssue],
    *,
    checked_at: datetime,
) -> DataQualityStatus:
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif any(issue.severity is DataTrustLevel.DEGRADED for issue in issues):
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref=f"ai_investment_report:{report_input.asset_symbol}",
        checked_at=normalize_timestamp(checked_at),
    )


def _scorecard(sections: Sequence[InvestmentReportSection]) -> InvestmentReportScorecard:
    supportive = DECIMAL_ZERO
    opposing = DECIMAL_ZERO
    neutral = DECIMAL_ZERO
    included_weight = DECIMAL_ZERO
    for section in sections:
        score = section.weighted_confidence
        if score == DECIMAL_ZERO:
            continue
        included_weight += section.weight
        if section.stance is InvestmentReportStance.SUPPORTIVE:
            supportive += score
        elif section.stance is InvestmentReportStance.OPPOSING:
            opposing += score
        else:
            neutral += score
    total_score = supportive + opposing + neutral
    confidence = (
        (max(supportive, opposing, neutral) / total_score).quantize(SCORE_QUANT)
        if total_score > DECIMAL_ZERO
        else DECIMAL_ZERO
    )
    return InvestmentReportScorecard(
        supportive_score=supportive.quantize(SCORE_QUANT),
        opposing_score=opposing.quantize(SCORE_QUANT),
        neutral_score=neutral.quantize(SCORE_QUANT),
        included_weight=included_weight.quantize(SCORE_QUANT),
        directional_edge=(supportive - opposing).quantize(SCORE_QUANT),
        confidence=confidence,
    )


def _rejection_reasons(
    report_input: InvestmentReportInput,
    policy: InvestmentReportPolicy,
    scorecard: InvestmentReportScorecard,
    quality: DataQualityStatus,
) -> list[str]:
    reasons: list[str] = []
    if not quality.is_trusted:
        reasons.append(f"report quality is {quality.trust_level.value}")
    if scorecard.confidence < policy.minimum_confidence:
        reasons.append("report confidence is below threshold")
    if abs(scorecard.directional_edge) < policy.minimum_directional_edge:
        reasons.append("directional edge is below threshold")
    if report_input.expected_return_pct is None:
        reasons.append("expected return is not supplied")
    if not report_input.expected_holding_period:
        reasons.append("expected holding period is not supplied")
    return reasons


def _recommendation(
    scorecard: InvestmentReportScorecard,
    rejection_reasons: Sequence[str],
    policy: InvestmentReportPolicy,
) -> InvestmentReportRecommendation:
    if rejection_reasons:
        return InvestmentReportRecommendation.NO_DECISION
    if scorecard.directional_edge >= policy.minimum_directional_edge:
        return InvestmentReportRecommendation.BUY_REVIEW
    if scorecard.directional_edge <= -policy.minimum_directional_edge:
        return InvestmentReportRecommendation.SELL_REVIEW
    return InvestmentReportRecommendation.HOLD_REVIEW


def _reasons(
    report_input: InvestmentReportInput,
    scorecard: InvestmentReportScorecard,
    recommendation: InvestmentReportRecommendation,
    rejection_reasons: Sequence[str],
) -> tuple[str, ...]:
    reasons = [
        f"{report_input.asset_symbol} report generated from {len(report_input.sections)} sections",
        f"recommendation={recommendation.value}",
        f"confidence={scorecard.confidence}",
        f"directional_edge={scorecard.directional_edge}",
    ]
    if rejection_reasons:
        reasons.append("report is non-actionable advisory context because safety checks failed")
    return tuple(reasons)


def _points_for(
    sections: Sequence[InvestmentReportSection],
    section_type: InvestmentReportSectionType,
) -> tuple[str, ...]:
    for section in sections:
        if section.section_type is section_type:
            return section.evidence_points
    return ("section not supplied",)


def _section_summary(
    sections: Sequence[InvestmentReportSection],
    section_type: InvestmentReportSectionType,
) -> str:
    for section in sections:
        if section.section_type is section_type:
            return section.summary
    return "section not supplied"


def _optional_decimal(value: Decimal | None) -> str:
    return str(value) if value is not None else "not supplied"


def _bullet_lines(values: Sequence[str]) -> list[str]:
    return [f"- {value}" for value in values] if values else ["- none"]
