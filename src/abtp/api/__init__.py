"""Framework-neutral API facades for future ABTP service layers."""

from abtp.api.paper import (
    PaperAPIError,
    PaperAPIRequestContext,
    PaperAPIRole,
    PaperControlState,
    PaperParameterHealth,
    PaperPermissionError,
    PaperPortfolioStatus,
    PaperStatusResponse,
    PaperTradingAPI,
    UnsafePaperActionError,
)
from abtp.api.predictions import PredictionAPI, prediction_response_to_json


def __getattr__(name: str) -> object:
    if name in {"PaperCommandCenterResponse", "build_paper_command_center_response"}:
        from abtp.api.command_center import (
            PaperCommandCenterResponse,
            build_paper_command_center_response,
        )

        values = {
            "PaperCommandCenterResponse": PaperCommandCenterResponse,
            "build_paper_command_center_response": build_paper_command_center_response,
        }
        return values[name]
    raise AttributeError(name)


__all__ = [
    "PaperAPIError",
    "PaperAPIRequestContext",
    "PaperAPIRole",
    "PaperCommandCenterResponse",
    "PaperControlState",
    "PaperParameterHealth",
    "PaperPermissionError",
    "PaperPortfolioStatus",
    "PaperStatusResponse",
    "PaperTradingAPI",
    "PredictionAPI",
    "UnsafePaperActionError",
    "build_paper_command_center_response",
    "prediction_response_to_json",
]
