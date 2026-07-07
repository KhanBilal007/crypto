from __future__ import annotations

from dataclasses import dataclass

from config import settings
from src.models import Token


@dataclass
class RiskResult:
    score: float
    passed: bool
    reasons: list[str]


class RiskEngine:
    def score_token(self, token: Token, whale_confirmations: int) -> RiskResult:
        score = 100.0
        reasons: list[str] = []

        if token.liquidity_usd < settings.MIN_LIQUIDITY_USD:
            score -= 30
            reasons.append("Low liquidity")
        if token.top_holder_percent > settings.MAX_TOP_HOLDER_PERCENT:
            score -= 25
            reasons.append("Top holder concentration high")
        if token.top_10_holder_percent > settings.MAX_TOP_10_HOLDER_PERCENT:
            score -= 20
            reasons.append("Top 10 holder concentration high")
        if settings.REQUIRE_MINT_AUTHORITY_DISABLED and not token.mint_revoked:
            score -= 20
            reasons.append("Mint authority active")
        if settings.REQUIRE_FREEZE_AUTHORITY_DISABLED and not token.freeze_revoked:
            score -= 20
            reasons.append("Freeze authority active")
        if token.token_age_minutes < settings.MIN_TOKEN_AGE_MINUTES:
            score -= 20
            reasons.append("Token too new")
        if token.token_age_minutes < 60 and whale_confirmations <= 1:
            score -= 20
            reasons.append("Very new token with weak confirmation")
        if token.holder_count < 200:
            score -= 10
            reasons.append("Low holder count")

        score = max(0.0, score)
        return RiskResult(score=score, passed=score >= settings.MIN_TOKEN_RISK_SCORE, reasons=reasons)
