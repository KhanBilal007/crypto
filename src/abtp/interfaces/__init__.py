"""Protocol interfaces for future ABTP modules."""

from abtp.interfaces.ai import PredictionEngine
from abtp.interfaces.data import MarketDataProvider
from abtp.interfaces.execution import OrderExecutionGateway
from abtp.interfaces.portfolio import PortfolioRepository
from abtp.interfaces.risk import RiskManagementEngine
from abtp.interfaces.strategy import StrategyEngine

__all__ = [
    "MarketDataProvider",
    "OrderExecutionGateway",
    "PortfolioRepository",
    "PredictionEngine",
    "RiskManagementEngine",
    "StrategyEngine",
]
