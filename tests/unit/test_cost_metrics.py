from decimal import Decimal
from typing import Any

from pejip.cost.metrics import (
    CALL_COST_METRIC,
    MONTH_TO_DATE_METRIC,
    NAMESPACE,
    CloudWatchSpendMetrics,
)


class FakeCloudWatch:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def put_metric_data(self, **kwargs: Any) -> None:
        self.requests.append(kwargs)


def test_publishes_month_to_date_and_per_call_cost() -> None:
    cloudwatch = FakeCloudWatch()
    CloudWatchSpendMetrics(cloudwatch, environment="prod").publish(
        month_to_date_usd=Decimal("51.25"),
        feature="ranking",
        model="claude-opus-5-5",
        call_usd=Decimal("0.03"),
    )
    [request] = cloudwatch.requests
    assert request["Namespace"] == NAMESPACE == "PEJIP"
    mtd, call = request["MetricData"]
    assert mtd == {
        "MetricName": MONTH_TO_DATE_METRIC,
        "Dimensions": [{"Name": "Environment", "Value": "prod"}],
        "Value": 51.25,
        "Unit": "None",
    }
    assert call["MetricName"] == CALL_COST_METRIC
    assert call["Value"] == 0.03
    assert {d["Name"]: d["Value"] for d in call["Dimensions"]} == {
        "Environment": "prod",
        "Feature": "ranking",
        "Model": "claude-opus-5-5",
    }
