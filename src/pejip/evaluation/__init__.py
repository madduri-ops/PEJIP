"""Golden evaluation set and harness for PEJIP rankings.

Policy section 12 (AI quality) requires every change to a prompt, model, ranking
logic or scoring weights to be evaluated against a committed test set, failing when
results drop below a committed baseline. This package loads that set
(``eval/golden``), runs a scorer over it, scores the results and enforces the
baseline. See ``eval/README.md``.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
