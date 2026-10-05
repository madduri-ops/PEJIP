"""AI cost guard: the one place Claude spend is checked against the monthly cap.

See docs/design/ai-cost-guard.md.
"""

from .guard import ALERT_PERCENTS, DEFAULT_CAP_USD, BudgetExceededError, CostGuard, Reservation
from .ledger import CapReachedError, Ledger, SpendLine, SpendRequest, SqliteLedger
from .metrics import CloudWatchSpendMetrics
from .pricing import PriceTable, TokenUsage, UnknownModelError

__all__ = [
    "ALERT_PERCENTS",
    "DEFAULT_CAP_USD",
    "BudgetExceededError",
    "CapReachedError",
    "CloudWatchSpendMetrics",
    "CostGuard",
    "Ledger",
    "PriceTable",
    "Reservation",
    "SpendLine",
    "SpendRequest",
    "SqliteLedger",
    "TokenUsage",
    "UnknownModelError",
]
