# Data flow

_Status: skeleton. Update whenever a source, store or pipeline step changes._

Describe how a role moves through the system, from discovery to a ranked,
explained recommendation, and where each piece of data is stored.

```mermaid
flowchart LR
    %% Replace with the real pipeline as it lands.
    discover[Discover roles] --> enrich[Enrich] --> rank[Rank] --> explain[Explain] --> notify[Surface to Babu]
```

## Data stores

| Store | Holds | Owner component | Retention |
|---|---|---|---|
| `ai_spend` (SQLite) | Per-call AI feature, model, tokens and cost; no personal data | AI cost guard | Kept; needed for monthly spend history |

Personal data, job postings and rankings are each kept for 90 days, using the
window in `pejip.retention` (see [0004: Data retention](../design/0004-data-retention.md)).
