"""Self-learning analysis exports.

Stage 035 produces advisory learning recommendations from completed trade
records. It does not modify trading rules, create signals, create order intents,
or bypass risk controls.
"""

from abtp.learning.analyzer import (
    FeatureImportanceObservation,
    LearningAnalysis,
    LearningRecommendation,
    OutcomeLabel,
    PatternSummary,
    StrategyLearningRank,
    TradeLearningRecord,
    TradeOutcomeAnalysis,
    analyze_trade_outcomes,
    build_learning_analysis,
    feature_importance_observations,
    regime_performance,
    strategy_rankings,
    win_loss_patterns,
)
from abtp.learning.calibration import (
    ConfidenceBucket,
    ConfidenceCalibrationReport,
    ConfidenceCalibrationSuggestion,
    calibrate_confidence,
)
from abtp.learning.reports import LearningReport, build_monthly_learning_report
from abtp.learning.trade_intelligence import (
    AIPredictionAccuracy,
    CommonTradeMistake,
    HoldingTimeInsight,
    TradeImprovementSuggestion,
    TradeImprovementType,
    TradeIntelligenceReport,
    TradeMistakeType,
    build_trade_intelligence_report,
)

__all__ = [
    "AIPredictionAccuracy",
    "CommonTradeMistake",
    "ConfidenceBucket",
    "ConfidenceCalibrationReport",
    "ConfidenceCalibrationSuggestion",
    "FeatureImportanceObservation",
    "HoldingTimeInsight",
    "LearningAnalysis",
    "LearningRecommendation",
    "LearningReport",
    "OutcomeLabel",
    "PatternSummary",
    "TradeImprovementSuggestion",
    "TradeImprovementType",
    "TradeIntelligenceReport",
    "StrategyLearningRank",
    "TradeLearningRecord",
    "TradeMistakeType",
    "TradeOutcomeAnalysis",
    "analyze_trade_outcomes",
    "build_learning_analysis",
    "build_monthly_learning_report",
    "build_trade_intelligence_report",
    "calibrate_confidence",
    "feature_importance_observations",
    "regime_performance",
    "strategy_rankings",
    "win_loss_patterns",
]
