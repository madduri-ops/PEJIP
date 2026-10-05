# Data flow

How a role moves from a company job board to a ranked, explained entry in the
digest. Detail is in [design doc 0003](../design/0003-find-thin-slice.md).

```mermaid
flowchart LR
    boards[(Greenhouse and Lever boards)] -->|PoliteClient| fetch[Fetch]
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
    explain --> recs[(recommendations)]
    recs --> digest[/digest-*.md/]
    analyse -. spend .-> usage[(ai_usage)]
    match -. spend .-> usage
```

Only the profile's headline, target seniority, career direction and evidence items
leave the machine, sent to the Anthropic API for matching (see
[docs/SECURITY.md](../SECURITY.md)).

## Data stores

| Store | Holds | Owner component | Retention |
|---|---|---|---|
| `jobs` | Posting fields, pay, content hash, first and last seen | store (via pipeline) | 90 days after last seen |
| `analyses` | AI analysis and matching output, provenance | analysis (via pipeline) | 90 days |
| `recommendations` | Scores, components, reasons, explanation | scoring (via pipeline) | 90 days |
| `ai_usage` | Tokens and cost per call by feature and model | ai.client | 90 days |
| `runs` | Run status and per-source results | pipeline | 90 days |
| `profile.yaml` | Career profile (personal data, local file) | Babu | Babu's own file |
| `output/digest-*.md` | Digest per run | cli | Babu's own files |
