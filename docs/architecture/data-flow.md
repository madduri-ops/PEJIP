# Data flow

How a role moves from a company job board to a ranked, explained entry in the
digest. Detail is in [design doc 0008](../design/0008-find-thin-slice.md).

```mermaid
flowchart LR
    boards[(Greenhouse and Lever boards)] -->|PoliteClient| fetch[Fetch]
    inbox[(S3 job-alert inbox)] -->|read, parse, delete| fetch
    fetch --> filter[Title + geography filter]
    filter -->|upsert by fingerprint| jobs[(jobs)]
    jobs -->|new or changed content| analyse[JOB_ANALYSIS]
    analyse -->|quotes grounded| match[EVIDENCE_MATCHING]
    profile[/profile.yaml evidence/] --> match
    match -->|evidence ids validated| analyses[(analyses)]
    analyses --> score[Fit, Confidence, Priority]
    jobs --> score
    config[/config/search.yaml/] --> score
    score --> explain[Cited explanation]
    connections[/LinkedIn export + decisions/] --> network[Matured connections]
    network -->|Priority boost| score
    network -->|Who you know| explain
    explain --> recs[(recommendations)]
    recs --> digest[/digest-*.md/]
    analyse -. spend .-> guard[AI cost guard] -.-> spend[(ai_spend)]
    match -. spend .-> guard
```

Connection data never leaves the machine; matching is deterministic. Only the
profile's headline, target seniority, career direction and evidence items leave the
machine, sent to the Anthropic API for matching (see
[docs/SECURITY.md](../SECURITY.md)).

## Data stores

| Store | Holds | Owner component | Retention |
|---|---|---|---|
| `jobs` | Posting fields, pay, content hash, first and last seen | store (via pipeline) | 90 days after last seen |
| `analyses` | AI analysis and matching output, provenance | analysis (via pipeline) | 90 days |
| `recommendations` | Scores, components, reasons, explanation | scoring (via pipeline) | 90 days |
| `runs` | Run status and per-source results | pipeline | 90 days |
| `profile.yaml` | Career profile (personal data, local file) | Babu | Babu's own file |
| LinkedIn export and decisions file | First-degree connections and Babu's network decisions (personal data, local files at `PEJIP_CONNECTIONS`, `PEJIP_NETWORK_DECISIONS`) | Babu | Babu's own files until the database stores imports (90 days after import) |
| `output/digest-*.md` | Digest per run | cli | Babu's own files |
| `ai_spend` (SQLite) | Per-call AI feature, model, tokens and cost; no personal data | AI cost guard | Kept; needed for monthly spend history |

Personal data, job postings and rankings are each kept for 90 days, using the
window in `pejip.retention` (see [0004: Data retention](../design/0004-data-retention.md)).
