# Golden evaluation set

The quality bar for PEJIP rankings ([build policy](../docs/BUILD_POLICY.md) section 12,
[FIND spec](../docs/spec/FIND-build-specification.md) 9.42 and 17.31-17.34). Any change
to a prompt, model, ranking logic or scoring weights is scored against this set, and
CI fails when a metric drops below the committed [baseline](baseline.json). Design:
[docs/design/0003-golden-evaluation-set.md](../docs/design/0003-golden-evaluation-set.md).

## What is here

| Path | What it holds |
|---|---|
| `golden/manifest.toml` | Set version and the controlled vocabularies every label must use |
| `golden/profile.toml` | A **synthetic** executive profile the cases are labelled against (no real personal data) |
| `golden/cases/*.toml` | One labelled job posting per file: the posting, network context and expected results |
| `baseline.json` | The minimum each metric must reach; it only goes up |

Each case labels the expected Fit range, allowed Confidence and Priority levels, the
reason codes a good explanation must include, the concerns it must raise, the role
family and the inferred level. Ranges and sets are used instead of single values
where reasonable people (or models) could differ (spec 17.32).

The 24 cases cover every category in spec 9.42 and 17.31: excellent, good, borderline
and poor matches, misleading titles in both directions, too junior, hands-on,
sales-heavy, industry-specific, high-network low-fit, strong-fit no-network,
ambiguous and incomplete postings, career-direction conflict and a hard filter. The
four worked examples in spec 9.28 are G01, G02, G10 and G12.

## Metrics

All are rates from 0 to 1, higher is better.

| Metric | Passes a case when |
|---|---|
| `scored_rate` | The scorer returned a result instead of failing (failures count as unranked) |
| `fit_in_range` | Fit falls inside the labelled range |
| `confidence_match` | Confidence is one of the allowed levels |
| `priority_match` | Priority is one of the allowed levels (`EXCLUDED` for a hard filter) |
| `positive_reason_recall` | Share of expected positive reason codes the scorer gave |
| `concern_recall` | Share of expected concerns the scorer raised |
| `pairwise_order` | For every pair whose Fit ranges do not overlap, the higher one scored higher |
| `citation_validity` | The scorer cited at least one snippet and every snippet appears in the posting |
| `network_invariance` | On probe cases, swapping in a large network leaves Fit unchanged (spec 9.8) |

`citation_validity` and `network_invariance` start at 1.0 because the spec and policy
treat them as rules, not targets. The rest start at 0 and are raised the first time
the real scorer runs.

## Commands

```sh
export PYTHONPATH=src   # or install the project, see CONTRIBUTING.md

python -m pejip.evaluation validate                                # check the set is well formed
python -m pejip.evaluation run --scorer package.module:score       # fail below the baseline
python -m pejip.evaluation run --scorer package.module:score --report eval-report.json
python -m pejip.evaluation ratchet --scorer package.module:score   # raise the baseline (on main)
python -m pytest tests/unit/evaluation --cov=pejip.evaluation --cov-branch
```

A scorer is any callable that takes a `pejip.evaluation.scorer.EvalInput` (case id, posting,
network context, profile; never the labels) and returns a `pejip.evaluation.scorer.Prediction`.

## The ranking pipeline's scorer

`pejip.golden_eval` runs the FIND ranking pipeline as a scorer. The model's part
(job analysis and evidence matching) comes from a recording per case in
`recordings/<case id>.json`, so CI can score every change without calling the model:

```sh
python -m pejip.evaluation run --scorer pejip.golden_eval:replay_scorer
```

`live_scorer` calls the model instead (needs `ANTHROPIC_API_KEY`, a few dollars per
run). CI runs it on pull requests that change a prompt, the AI client, the analysis
code, `config/search.yaml`, the adapter or this set, and the "Evaluation set (live
model)" job uploads and prints what the model returned. To refresh the recordings,
run it with `PEJIP_EVAL_RECORD_DIR=eval/recordings`, or copy them from that job, and
commit them in the same PR. A recording is only used for the golden set version it
was made with, so bumping `golden_set_version` needs fresh recordings.

## Changing the set

- Bump `golden_set_version` in `manifest.toml` for any change to a case, a label or
  the profile, and add a line below.
- Add a case by copying a file in `golden/cases/`. Use invented companies and
  people only. The loader rejects unknown vocabulary, so add a new reason code or
  category to the manifest first.
- Relabelling a case to make a scorer pass needs a stated reason in the PR. The
  labels are the product owner's judgement, not the model's.

## Changelog

- **1.1.0** (2026-10-05): Babu's review. G17 (security operations) kept as is; G22
  (Chief of Staff to the CTO) raised to Fit 65-80, Priority HIGH or MEDIUM, as a
  worthwhile stepping stone.
- **1.0.0** (2026-10-05): first set, 24 synthetic cases drafted by Claude from the FIND
  spec. Labels await Babu's review.
