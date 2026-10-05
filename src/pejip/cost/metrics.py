"""Publishes AI spend to CloudWatch, where the Terraform alarms in
infra/ai_cost.tf email Babu at 50% of the cap and every 10% after."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

NAMESPACE = "PEJIP"
MONTH_TO_DATE_METRIC = "AISpendMonthToDateUSD"
CALL_COST_METRIC = "AICallCostUSD"


class CloudWatchSpendMetrics:
    """Sends spend to CloudWatch through a boto3 ``cloudwatch`` client.

    The client is passed in so this package doesn't depend on boto3. The caller's
    role needs ``cloudwatch:PutMetricData`` limited to the ``PEJIP`` namespace.
    """

    def __init__(self, cloudwatch: Any, *, environment: str = "prod") -> None:
        self._cloudwatch = cloudwatch
        self._environment = environment

    def publish(
        self,
        *,
        month_to_date_usd: Decimal,
        feature: str,
        model: str,
        call_usd: Decimal,
    ) -> None:
        env = {"Name": "Environment", "Value": self._environment}
        self._cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": MONTH_TO_DATE_METRIC,
                    "Dimensions": [env],
                    "Value": float(month_to_date_usd),
                    "Unit": "None",
                },
                {
                    "MetricName": CALL_COST_METRIC,
                    "Dimensions": [
                        env,
                        {"Name": "Feature", "Value": feature},
                        {"Name": "Model", "Value": model},
                    ],
                    "Value": float(call_usd),
                    "Unit": "None",
                },
            ],
        )
