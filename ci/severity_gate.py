"""Severity gate for SAST, DAST and dependency audit reports (docs/BUILD_POLICY.md section 3).

The scanners run in report mode so every finding lands in the uploaded report; this
script is the gate. It prints every finding and exits 1 when any is high or critical.
Medium and low findings are reported only.
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, NamedTuple

BLOCKING = frozenset({"high", "critical"})


class Finding(NamedTuple):
    severity: str
    rule: str
    location: str


def bandit_findings(report: dict[str, Any]) -> list[Finding]:
    return [
        Finding(r["issue_severity"].lower(), r["test_id"], f"{r['filename']}:{r['line_number']}")
        for r in report["results"]
    ]


def grype_findings(report: dict[str, Any]) -> list[Finding]:
    return [
        Finding(
            m["vulnerability"]["severity"].lower(),
            m["vulnerability"]["id"],
            f"{m['artifact']['name']}=={m['artifact']['version']}",
        )
        for m in report["matches"]
    ]


# ZAP risk codes: 0 informational, 1 low, 2 medium, 3 high. ZAP has no critical.
ZAP_RISK = {"0": "informational", "1": "low", "2": "medium", "3": "high"}


def zap_findings(report: dict[str, Any]) -> list[Finding]:
    return [
        Finding(ZAP_RISK[alert["riskcode"]], f"{alert['pluginid']} {alert['name']}", site["@name"])
        for site in report["site"]
        for alert in site["alerts"]
    ]


PARSERS: dict[str, Callable[[dict[str, Any]], list[Finding]]] = {
    "bandit": bandit_findings,
    "grype": grype_findings,
    "zap": zap_findings,
}


def blocking(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity in BLOCKING]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=sorted(PARSERS))
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)

    findings = PARSERS[args.tool](json.loads(args.report.read_text(encoding="utf-8")))
    for finding in findings:
        print(f"{finding.severity:>13}  {finding.rule}  {finding.location}")
    blockers = blocking(findings)
    print(f"{args.tool}: {len(findings)} findings, {len(blockers)} high or critical.")
    if blockers:
        print(f"::error::{args.tool} found {len(blockers)} high or critical findings")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
