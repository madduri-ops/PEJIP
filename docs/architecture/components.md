# Components

_Status: first component landed. Add a section per component as it is introduced._

For each component, record:

- **Responsibility:** what it owns, in one or two sentences.
- **Interfaces:** the APIs, events or files it exposes and consumes.
- **Data:** the data it stores or reads.
- **Design doc:** link to its doc in [docs/design/](../design/).

```mermaid
flowchart TB
    alb[Load balancer / health gate] -- GET /healthz --> api[API: pejip.api]
```

## API (`pejip.api`)

- **Responsibility:** the HTTP surface of PEJIP. Today it serves only the health
  endpoint; feature endpoints are added here.
- **Interfaces:** `GET /healthz`; the OpenAPI document at `/openapi.json`. Run with
  `python -m pejip.api` (`PEJIP_HOST`, `PEJIP_PORT`).
- **Data:** none.
- **Design doc:** [0001: CI pipeline and health endpoint](../design/0001-ci-pipeline.md).

## Golden evaluation harness (`src/pejip/evaluation`)

- **Responsibility:** scores any ranking implementation against the labelled golden
  set and fails CI when a metric drops below the committed baseline.
- **Interfaces:** consumes a scorer callable (`EvalInput` in, `Prediction` out);
  exposes `python -m pejip.evaluation validate | run | ratchet`.
- **Data:** reads `eval/golden/` (synthetic cases and profile) and
  `eval/baseline.json`; writes an optional JSON report.
- **Design doc:** [0003: Golden evaluation set](../design/0003-golden-evaluation-set.md).
