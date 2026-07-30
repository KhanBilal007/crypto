"""Limited automation exports."""

from abtp.automation.circuit_breakers import (
    AutomationHealthSnapshot,
    CircuitBreakerConfig,
    CircuitBreakerDecision,
    evaluate_circuit_breakers,
)
from abtp.automation.controller import (
    AutomationController,
    AutomationControlState,
    AutomationDecision,
    AutomationEvidence,
    AutomationMode,
    AutomationPolicy,
)

__all__ = [
    "AutomationControlState",
    "AutomationController",
    "AutomationDecision",
    "AutomationEvidence",
    "AutomationHealthSnapshot",
    "AutomationMode",
    "AutomationPolicy",
    "CircuitBreakerConfig",
    "CircuitBreakerDecision",
    "evaluate_circuit_breakers",
]
