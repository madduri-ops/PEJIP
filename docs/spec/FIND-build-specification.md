<!-- Converted from "Product and Engineering Build Specification — FIND.docx" (v1.0, 2026-10-04). This Markdown file is now the source of truth; edit it here. -->

# Product + Engineering Build Specification — FIND

Version: 1.0 Date: October 4, 2026 Status: Coding-ready Phase 1 specification

> Primary product question: “What are the best new opportunities for me right now, why do they fit, and where do I already have an advantage?”

## 1. Product Vision

Build a personal AI-powered Executive Job Intelligence Platform that continuously discovers relevant senior-leadership opportunities, determines which opportunities deserve attention, and clearly explains why.

The system should behave less like a traditional job board and more like a personal job-market intelligence analyst.

The product roadmap is:

- Phase 1 — FIND Discover, understand, score, prioritize, explain, monitor and learn.
- Phase 2 — PURSUE Tailor, network, apply and manage selected opportunities.
- Phase 3 — WIN & ANTICIPATE Prepare for interviews, learn from outcomes and identify opportunities before or as they emerge.
- This document defines Phase 1 only.

## 2. Phase 1 Product Boundary

Phase 1 performs:

```text
Discover → Verify → Normalize → Deduplicate → Enrich → Match → Score → Explain → Prioritize → Monitor → Learn
```

Phase 1 does not:

- automatically apply for jobs;
- send LinkedIn messages;
- email recruiters;
- rewrite or submit resumes;
- generate and submit cover letters;
- make career decisions for the user;
- conduct interview preparation.

Those belong primarily to Phase 2 and Phase 3.

## 3. Job Discovery Scope and Search Taxonomy

The job-discovery engine must not depend on a small, hard-coded list of job titles.

Phase 1 will maintain a configurable Job Search Taxonomy that defines the types of opportunities the platform should discover. The taxonomy must be editable without changing application code.

The taxonomy is used primarily for candidate discovery. Final relevance is determined later by the matching engine using responsibilities, seniority, organizational scope, career direction, company context, and the Master Career Profile.

### 3.1 Role Families

The initial role families are:

- Technology Operations
- Product Operations
- Engineering Operations
- Business / Technology Operations
- Enterprise Transformation
- Technology Transformation
- Digital Transformation
- Transformation Management Office / Value Management Office
- Technical Program Management
- Program / Portfolio Leadership
- Strategic Programs
- Platform Operations
- Developer Platforms / Developer Productivity
- Engineering Productivity
- Cloud / Enterprise Technology
- AI / ML Transformation and Operations
- AI Governance / Enablement
- Security / Risk / Governance-adjacent Technology Leadership

Additional role families can be added later through configuration.

### 3.2 Search Title Taxonomy

Each role family contains multiple potential job titles.

The initial title taxonomy should include, but not be limited to:

#### Vice President

- VP Technology Operations
- VP Product Operations
- VP Engineering Operations
- VP Business Operations
- VP Strategy & Operations
- VP Enterprise Transformation
- VP Technology Transformation
- VP Digital Transformation
- VP Transformation
- VP Program Management
- VP Technical Program Management
- VP Portfolio Management
- VP Strategic Programs
- VP Platform Operations
- VP Developer Productivity
- VP Engineering Productivity
- VP Cloud Operations
- VP Enterprise Technology
- VP Technology Strategy
- VP AI Transformation
- VP AI Operations

#### Head-of Roles

- Head of Technology Operations
- Head of Product Operations
- Head of Engineering Operations
- Head of Business Operations
- Head of Enterprise Transformation
- Head of Technology Transformation
- Head of Transformation
- Head of Technical Program Management
- Head of Program Management
- Head of Portfolio Management
- Head of Strategic Programs
- Head of Platform Operations
- Head of Developer Productivity
- Head of Engineering Productivity
- Head of Enterprise Technology
- Head of Technology Strategy
- Head of AI Transformation
- Head of AI Operations

#### Senior Director

- Senior Director Technology Operations
- Senior Director Product Operations
- Senior Director Engineering Operations
- Senior Director Business Operations
- Senior Director Enterprise Transformation
- Senior Director Technology Transformation
- Senior Director Digital Transformation
- Senior Director Transformation
- Senior Director Technical Program Management
- Senior Director Program Management
- Senior Director Portfolio Management
- Senior Director Strategic Programs
- Senior Director Platform Operations
- Senior Director Developer Productivity
- Senior Director Engineering Productivity
- Senior Director Enterprise Technology
- Senior Director Technology Strategy
- Senior Director AI Transformation

The taxonomy must support additional seniority/title patterns discovered during actual searches.

### 3.3 Title Variations and Synonyms

The discovery engine must account for title variations.

For example:

Vice President may appear as:

- VP
- V.P.
- Vice President

Senior Director may appear as:

- Senior Director
- Sr. Director
- Sr Director

The system should normalize these variations to common internal title concepts.

### 3.4 Semantic Discovery

Exact title matching alone is insufficient.

The system should also discover opportunities whose titles are unfamiliar but whose responsibilities strongly correspond to one of the configured role families.

For example:

- Executive Director, Technology Strategy & Execution may be highly relevant even though that exact title wasn't configured.

Similarly:

Global Head of Strategic Technology Programs could represent the same career direction as a VP Technology Operations or Head of Transformation opportunity.

The search engine should therefore combine:

- Configured titles + title synonyms + role-family concepts + semantic discovery to generate candidate opportunities.

### 3.5 Discovery Keywords

In addition to titles, searches may use capability and responsibility terms to broaden discovery.

Initial categories include:

#### Transformation

- enterprise transformation
- technology transformation
- digital transformation
- business transformation
- operating model transformation
- strategic transformation
- modernization
- transformation office
- Transformation Management Office
- TMO
- Value Management Office
- VMO

#### Technology / Product Operations

- technology operations
- product operations
- engineering operations
- strategic operations
- business operations
- operational excellence
- operating model
- organizational effectiveness
- execution excellence

#### Program / Portfolio

- technical program management
- TPM
- program management
- portfolio management
- portfolio governance
- strategic programs
- enterprise programs
- PMO
- enterprise PMO
- roadmap governance
- portfolio optimization

#### Platforms / Developer Productivity

- platform engineering
- platform operations
- developer platform
- developer productivity
- developer experience
- DevEx
- engineering productivity
- engineering enablement
- internal developer platform
- DevOps
- DevSecOps
- CI/CD
- software delivery

#### Cloud / Enterprise Technology

- cloud transformation
- cloud modernization
- enterprise technology
- infrastructure transformation
- technology modernization
- cloud governance
- AWS
- Azure
- GCP
- hybrid cloud

#### AI

- AI transformation
- AI strategy
- AI operations
- AI platform
- AI governance
- AI enablement
- enterprise AI
- generative AI
- GenAI
- agentic AI
- AI adoption
- responsible AI
- MLOps

#### Security / Governance

- cybersecurity transformation
- security governance
- cyber risk
- technology risk
- information security governance
- privacy
- data privacy
- GRC
- risk management
- compliance transformation
- ISO 27001
- SOC 2

These keywords should help discover candidate opportunities. Their presence alone does not establish a strong match.

### 3.6 Scope and Seniority Signals

The engine should also recognize language indicating genuine executive or senior-leadership scope.

Examples include:

- executive leadership
- executive stakeholders
- C-suite
- board
- enterprise-wide
- global
- cross-functional leadership
- organizational leadership
- strategic planning
- budget ownership
- portfolio ownership
- manage managers
- build organizations
- transformation roadmap
- executive communication
- global portfolio
- multi-business-unit
- large-scale transformation
- enterprise-scale
- matrixed organization
- distributed teams
- M&A
- acquisition integration

These signals help the later matching engine determine whether the actual scope corresponds to the user's target level.

### 3.7 Negative Discovery Signals

The taxonomy should also maintain potential negative-fit signals.

Examples include:

- quota carrying
- sales quota
- account executive
- sales pipeline ownership
- commission
- primarily hands-on coding
- individual contributor
- field sales
- direct sales

These terms should not automatically eliminate an opportunity unless a configured hard filter applies.

Instead, they trigger additional negative-fit analysis.

### 3.8 Search Taxonomy Configuration

The taxonomy must be data-driven rather than hard-coded.

Conceptually:

```text
SearchTerm {
    id
    term
    category
    role_family
    term_type
    synonyms[]
    seniority_context?
    discovery_weight?
    enabled
}
```

term_type may include:

- TITLE
- TITLE_SYNONYM
- CAPABILITY
- RESPONSIBILITY
- SCOPE_SIGNAL
- NEGATIVE_SIGNAL

Administrators/users should be able to:

- add terms;
- remove terms;
- enable/disable terms;
- assign role families;
- add title variations;
- adjust discovery importance.

### 3.9 Search Query Generation

The platform should generate multiple targeted searches rather than constructing one enormous Boolean query.

Conceptually:

```text
Role Family
      +
Title / Title Variation
      +
Relevant Capability Terms
      +
Geographic Scope
      +
Work Model
      =
Search Query
```

Different external sources may require different query-generation strategies.

The adapter for each source is responsible for translating the internal taxonomy into the most appropriate query format for that source.

### 3.10 Opportunity Clustering

Search results should ultimately be grouped by underlying career direction rather than exact title.

For example:

- Technology / Transformation Leadership

VP Technology Operations

Head of Enterprise Transformation

VP Product Operations

Senior Director Strategic Programs

Executive Director Technology Strategy & Execution

Global Head of Technology Programs

This protects the discovery engine from becoming overly dependent on title conventions.

## 4. Geographic Search Scope

Geography must be fully configurable and must not be hard-coded into application logic.

Phase 1 will initially seed the system with:

- San Francisco Bay Area
- United States Remote

However, additional geographic scopes must be addable later without software changes.

Examples might include:

- Sacramento
- Seattle
- Austin
- Los Angeles
- New York
- another U.S. region
- another country

### 4.1 Geographic Scope Model

Conceptually:

```text
GeographicScope {
    geographic_scope_id
    name
    scope_type
    country?
    state_or_region?
    locations[]
    center_point?
    radius_miles?
    allowed_work_models[]
    relocation_allowed
    commute_preference?
    enabled
    priority?
}
```

Possible scope_type values include:

- METRO
- CITY
- REGION
- STATE
- COUNTRY
- RADIUS
- REMOTE

### 4.2 Initial Bay Area Scope

The initial Bay Area geographic scope should support opportunities in reasonable employment centers throughout:

- San Francisco
- Peninsula
- South Bay / Silicon Valley
- East Bay
- other locations reasonably considered part of the Bay Area employment market

The implementation should not depend solely on a literal job-location value of "San Francisco Bay Area".

Jobs may instead list individual cities such as:

- San Francisco
- South San Francisco
- Burlingame
- San Mateo
- Redwood City
- Palo Alto
- Mountain View
- Sunnyvale
- Santa Clara
- San Jose
- Cupertino
- Fremont
- Newark
- Milpitas
- Hayward
- Oakland
- Pleasanton
- San Ramon

The geographic configuration should therefore support a collection of cities/locations and, where appropriate, radius-based interpretation.

### 4.3 U.S. Remote Scope

Remote jobs should be treated as a separate geographic scope.

The system must distinguish:

- fully remote anywhere in the United States;
- remote with geographic restrictions;
- remote with required proximity to an office;
- hybrid;
- primarily on-site;
- remote with substantial travel.

A job containing the word "remote" should not automatically be assumed to satisfy the U.S. Remote scope.

### 4.4 Work Model

Work model should be represented independently from geographic location.

Supported values should include:

- REMOTE
- HYBRID
- ONSITE
- FLEXIBLE
- UNKNOWN

This allows scenarios such as:

- Geography: Bay Area
- Work Model: Hybrid

or:

- Geography: United States
- Work Model: Remote

### 4.5 Geographic Scope Expansion

The user must be able to add a new geographic search scope through configuration.

For example:

- Name: Seattle Metro

Type: METRO

Locations:

- Seattle
- Bellevue
- Redmond

Work Models:

- Hybrid
- Onsite
- Remote

Enabled:

- Yes

Once enabled, the scheduler should automatically execute appropriate job searches against that geography during subsequent discovery runs.

No code deployment should be required.

### 4.6 Geographic Scope and Search Taxonomy Independence

The job-search taxonomy and geographic scopes must remain separate.

For example:

- 40 Job / Role Search Patterns

```text
             ×
3 Geographic Scopes
             =
Search Plan
```

This allows the same role taxonomy to be reused across different markets.

The system should therefore be able to execute:

- VP Technology Operations × Bay Area

VP Technology Operations × U.S. Remote

Head of Transformation × Bay Area

Head of Transformation × U.S. Remote

and later:

- VP Technology Operations × Seattle

Head of Transformation × Seattle

without modifying the underlying role taxonomy.

### 4.7 Geographic Hard Filters vs. Preferences

Each geographic scope can define whether geography represents a hard requirement or preference.

Examples:

- Hard requirement

> U.S.-based employment only.

Preference

> Bay Area preferred, but U.S. remote is acceptable.

Preference

> Hybrid within reasonable commuting distance preferred.

The ranking engine should therefore distinguish:

- geographically eligible;
- geographically preferred;
- geographically acceptable;
- geographically undesirable;
- geographically ineligible.

### 4.8 Geographic Search Configuration

The product UI should eventually provide a Search Scope Settings area where the user can:

- add a geographic scope;
- edit a scope;
- enable/disable a scope;
- specify cities/regions;
- configure radius;
- select permitted work models;
- specify relocation preference;
- set scope priority.

This configuration becomes input to the scheduled search planner.

The search planner therefore operates from two independently configurable dimensions:

- WHAT jobs should we search for? — Job Search Taxonomy and
- WHERE should we search for them? — Geographic Scopes
- Those two configuration models become the foundation for all Phase 1 job discovery.

## 5. Search Operating Model

The Phase 1 discovery engine operates continuously over time rather than treating every search as an independent job-board query.

The system must maintain persistent knowledge of:

- jobs previously discovered;
- companies previously discovered;
- employer posting dates;
- first-seen and last-seen timestamps;
- previous versions of job postings;
- source observations;
- expired or removed opportunities;
- user feedback;
- watched jobs and companies.

This persistent state allows the system to determine not simply what jobs exist, but:

> What is new?
>
> What changed?
>
> What disappeared?
>
> What has already been evaluated?
>
> What deserves attention now?

The Search Operating Model consists of four primary search modes:

- Initial Market Baseline
- Incremental Discovery
- Reconciliation and Verification
- Targeted / On-Demand Search

### 5.1 Initial Market Baseline

The Initial Market Baseline runs when the system is first established or when a major search configuration change requires rebuilding part of the market view.

Its purpose is to establish the current opportunity universe.

The baseline should search across:

- all enabled Job Search Taxonomy role families;
- all enabled title patterns;
- all enabled geographic scopes;
- configured job-discovery sources;
- target-company career sites;
- relevant company and market intelligence sources.

The baseline should attempt to identify currently active relevant jobs regardless of whether they were posted today, yesterday, or earlier.

For every discovered job, capture when available:

- company;
- title;
- normalized title;
- location;
- work model;
- compensation;
- employer posting date;
- requisition ID;
- source;
- canonical application URL;
- job description;
- first-seen timestamp.

The critical distinction is:

- Employer Posted Date = when the employer/source says the job was posted.
- First-Seen Date = when our platform first discovered it.

A job discovered during the baseline must not automatically be presented as:

> “New job today.”

Instead, it should be classified as an existing market opportunity discovered during baseline unless reliable posting information establishes that it is genuinely new.

The output of the baseline becomes the starting market inventory against which subsequent searches are compared.

### 5.2 Incremental Discovery

After the Initial Market Baseline completes, the platform switches to Incremental Discovery as its normal operating mode.

Incremental Discovery asks:

> “What has appeared since we last searched?”

Rather than repeatedly processing the entire market from scratch, the system focuses primarily on:

- newly posted jobs;
- newly discovered jobs;
- jobs at watched companies;
- relevant jobs discovered through newly available sources;
- previously unseen title variations;
- opportunities matching newly learned preferences.

Each discovered opportunity is compared against persistent job history.

The system classifies the result as one of:

- NEW_POSTING

NEWLY_DISCOVERED_EXISTING_POSTING

PREVIOUSLY_SEEN

MATERIALLY_CHANGED

**REPOSTED**

EXPIRED_OR_REMOVED

**UNRESOLVED**

#### NEW_POSTING

Evidence indicates the employer recently posted the opportunity and the system has not previously seen it.

#### NEWLY_DISCOVERED_EXISTING_POSTING

The platform has not seen the opportunity before, but available evidence indicates that the job existed before the current search cycle.

This distinction prevents late discovery from being confused with a genuinely new posting.

#### PREVIOUSLY_SEEN

The job already exists in the platform and no material change has occurred.

#### MATERIALLY_CHANGED

A previously known posting changed in a meaningful way.

Examples:

- compensation changed;
- responsibilities changed;
- qualifications changed;
- location changed;
- remote/hybrid status changed;
- reporting relationship changed;
- scope changed.

#### REPOSTED

A job appears to be a new posting of a previously observed opportunity.

The new posting should be retained while preserving lineage to the previous posting when evidence supports the relationship.

#### EXPIRED_OR_REMOVED

A previously active job can no longer be confirmed as active.

#### UNRESOLVED

The system does not yet have enough evidence to determine the posting state confidently.

### 5.3 Reconciliation and Verification

Incremental search alone is insufficient because job sources do not always update simultaneously.

A company might publish a job at 8:00 AM while:

- an aggregator indexes it hours later;
- another job source indexes it the following day;
- an employer ATS changes the URL;
- a posting temporarily disappears from one source.

Therefore, the platform maintains a rolling reconciliation window, initially approximately 72 hours.

During reconciliation, the system revisits recent observations to determine whether:

- newly discovered jobs can be verified on the employer site;
- duplicate postings represent the same requisition;
- posting dates can be resolved;
- jobs remain active;
- source information changed;
- canonical URLs became available;
- previously ambiguous jobs can now be classified.

The reconciliation process should prefer the employer's own career site or ATS as the canonical record whenever available.

Reconciliation prevents the platform from treating indexing delays as genuinely new opportunities.

### 5.4 Targeted / On-Demand Search

The user should not have to wait for the next scheduled search.

Phase 1 should support an on-demand search using the same discovery infrastructure.

Examples:

> “Search Seattle now.”
>
> “I just added VP AI Transformation. Search for it now.”
>
> “Show me everything relevant at ServiceNow.”
>
> “Search for Head of Transformation roles in the Bay Area.”
>
> “I changed my geographic scope. Refresh the market.”

An on-demand search may target:

- one role family;
- one or more titles;
- one geographic scope;
- one company;
- a company group;
- a newly added taxonomy term;
- the complete configured market.

Results enter the same canonical job inventory and follow the same:

```text
Normalization → Deduplication → Verification → Matching → Scoring → Explanation
```

pipeline.

There should not be a separate data model for manually requested searches.

### 5.5 Search Planning

Before executing a search, the platform creates a Search Plan.

The Search Plan combines:

- Enabled Role Families

```text
×
```

Enabled Search Titles / Concepts

```text
×
```

Enabled Geographic Scopes

```text
×
```

Applicable Sources

The system should optimize this plan rather than blindly issuing every possible combination.

For example, if:

- 40 title patterns exist;
- 2 geographic scopes exist;
- 6 discovery sources exist;

the application should not automatically assume that 480 independent searches are necessary.

Each source adapter should determine the most efficient query strategy supported by that source.

The Search Plan records what the system intended to search so that coverage can later be measured.

### 5.6 Search Run

Every execution creates a SearchRun.

Conceptually:

```text
SearchRun {
    run_id
    run_type
    started_at
    completed_at
    search_plan_version
    taxonomy_version
    geographic_scope_version
    expected_sources[]
    completed_sources[]
    failed_sources[]
    observations_found
    new_jobs
    changed_jobs
    expired_jobs
    status
}
```

Possible run_type values:

**BASELINE**

**INCREMENTAL**

**RECONCILIATION**

ON_DEMAND

Possible status values:

**RUNNING**

**SUCCESS**

**PARTIAL**

**FAILED**

### 5.7 Search Coverage

A successful scheduler invocation does not necessarily mean the market was searched successfully.

The system must track Search Coverage.

For example:

- 7:00 AM Search

Company Career Sites      SUCCESS

Job Source A              SUCCESS

Job Source B              FAILED

Company Intelligence      SUCCESS

Overall Run               PARTIAL

If a source fails, the platform must never interpret that failure as:

> “No new jobs found.”

Instead:

> “Search results may be incomplete because one source failed.”

### 5.8 Search Freshness

For every active opportunity, maintain:

- employer_posted_at first_seen_at last_seen_at last_verified_at last_changed_at

These timestamps answer different questions.

Employer Posted At

When did the employer apparently publish the job?

First Seen At

When did our platform first discover it?

Last Seen At

When did any source most recently report it?

Last Verified At

When did we most recently confirm the canonical posting?

Last Changed At

When did we detect a material change?

This distinction is essential for determining urgency.

### 5.9 Search History

The system must retain enough history to answer:

> “Did we already see this?”
>
> “When did we first see it?”
>
> “Which source found it first?”
>
> “Has the job changed?”
>
> “Was this previously recommended?”
>
> “Did I reject or watch it before?”
>
> “Did this company post a similar role previously?”

This history becomes increasingly valuable in Phase 2 and Phase 3.

### 5.10 Search Operating Principle

The fundamental operating model is therefore:

```text
INITIAL BASELINE
       ↓
Establish Market Inventory
       ↓
INCREMENTAL DISCOVERY
       ↓
Identify New / Changed Opportunities
       ↓
RECONCILIATION
       ↓
Verify / Deduplicate / Resolve
       ↓
Persistent Market History
       ↓
Next Incremental Search
```

At any point:

```text
USER REQUEST
      ↓
ON-DEMAND SEARCH
      ↓
Same Processing Pipeline
      ↓
Persistent Market History
```

The system therefore evolves from a simple job-search application into a persistent career-market intelligence system that understands what it has seen before and recognizes meaningful changes over time.

## 6. Search Schedule and Cadence

Section 5 defines how the search system operates. This section defines when searches execute, what each scheduled cycle is responsible for, and how scheduling failures and overlapping runs are handled.

Phase 1 must support scheduled discovery as a configurable service rather than embedding fixed times directly in application code.

The initial operating cadence is:

- Morning Search — 7:00 AM Pacific
- Midday Search — 12:00 PM Pacific
- Evening Search — 5:00 PM Pacific

These are initial configuration values, not permanent product constraints.

### 6.1 Initial Baseline Schedule

The Initial Market Baseline is not part of the normal three-times-per-day schedule.

It runs:

- during initial system setup;
- when explicitly requested by the user;
- when a major search configuration change requires rebuilding a significant portion of the market inventory.

Examples of changes that may justify a new or partial baseline include:

- adding a major new geographic scope;
- adding a large new role family;
- enabling a major new discovery source;
- substantially changing the target opportunity strategy.

A configuration change should not automatically trigger a complete market rebuild when a smaller targeted search is sufficient.

For example, adding Seattle should normally trigger a baseline for Seattle rather than rebuilding the Bay Area inventory.

### 6.2 Normal Daily Schedule

After the initial baseline, the platform enters normal scheduled operation.

Default Phase 1 schedule:

- 07:00 Pacific   Morning Incremental Search

12:00 Pacific   Midday Incremental Search

17:00 Pacific   Evening Incremental Search

Each scheduled cycle searches all enabled combinations that are appropriate for incremental discovery.

The schedule should be stored as configuration.

Conceptually:

```text
SearchSchedule {
    schedule_id
    name
    run_type
    local_time
    timezone
    enabled
    geographic_scope_ids[]
    role_family_ids[]
    notification_policy_id?
    created_at
    updated_at
}
```

### 6.3 Time Zone Handling

Schedules must always include an explicit time zone.

Initial configuration:

- Timezone: America/Los_Angeles

The system should store timestamps internally in UTC while retaining the configured scheduling time zone.

This prevents daylight-saving changes from causing the intended 7:00 AM Pacific search to drift.

The UI should display scheduled times in the user's configured local time zone.

### 6.4 Scheduled Run Lifecycle

At each scheduled time, the scheduler creates a new SearchRun.

The scheduler itself should not perform job discovery.

Its responsibility is to initiate the run.

Conceptually:

```text
Scheduler
    ↓
Create SearchRun
    ↓
Create Search Plan
    ↓
Dispatch Source Tasks
    ↓
Collect Observations
    ↓
Normalize
    ↓
Deduplicate
    ↓
Verify
    ↓
Detect Changes
    ↓
Analyze Relevant Jobs
    ↓
Calculate Fit
    ↓
Calculate Confidence
    ↓
Calculate Application Priority
    ↓
Generate Explanations
    ↓
Evaluate Notifications
    ↓
Close SearchRun
```

This separation allows discovery and analysis work to run asynchronously.

### 6.5 Morning Search

The Morning Search should perform the broadest normal incremental scan.

Its objectives are to identify:

- jobs posted overnight;
- jobs indexed overnight;
- changes since the previous evening run;
- jobs discovered through target-company monitoring;
- relevant company signals;
- unresolved observations from the previous day.

The morning run should generally have the largest reconciliation overlap because approximately fourteen hours have passed since the 5:00 PM search.

### 6.6 Midday Search

The Midday Search focuses primarily on opportunities appearing during the first part of the business day.

It should detect:

- newly posted jobs;
- newly indexed jobs;
- changes to known postings;
- new target-company opportunities;
- relevant company/hiring signals.

The midday run compares its results against persistent history rather than against only the morning result set.

### 6.7 Evening Search

The Evening Search captures opportunities appearing during the second half of the business day.

It should also establish the final normal discovery checkpoint before the overnight period.

The evening run should:

- discover new postings;
- detect changed postings;
- update active-job status;
- process unresolved observations where possible;
- prepare persistent state for the next morning run.

### 6.8 Search Windows and Overlap

Scheduled searches must not use strict non-overlapping windows such as:

```text
Morning: 5 PM yesterday → 7 AM today

Midday: 7 AM → noon

Evening: noon → 5 PM
```

That approach risks missing jobs because external sources may index postings late.

Instead, searches should intentionally overlap.

For example, a noon run may query a sufficiently broad recent-posting window rather than only jobs posted after exactly 7:00 AM.

Deduplication and persistent first-seen history prevent overlapping searches from creating duplicate opportunities.

The operating principle is:

> Prefer harmless overlap over missed opportunities.

### 6.9 Reconciliation Window

Maintain a rolling reconciliation period initially configured to approximately:

- 72 hours

This value must be configurable.

During that period, the system may revisit recently discovered or unresolved jobs to:

- locate the employer posting;
- resolve duplicate records;
- confirm posting dates;
- detect changes;
- verify active status;
- determine whether a job is genuinely new or merely newly indexed.

Reconciliation may occur as part of the three scheduled runs rather than requiring a separate user-visible run every time.

### 6.10 Source-Specific Cadence

Not every source needs to be queried identically three times per day.

The scheduler should support source-specific cadence.

For example:

- Job Discovery Sources
- 3 × daily

Target Company Career Monitoring

3 × daily

Company / Market Intelligence

1–3 × daily depending on source

Connection Import

User initiated

Canonical Verification

Triggered by discovery + reconciliation

Expired Job Verification

Periodic

This avoids unnecessary processing while preserving useful freshness.

The precise cadence for each source can be tuned after source-performance data becomes available.

### 6.11 Target Company Monitoring

Companies in the Target Company Universe may receive dedicated monitoring.

High-interest companies can be assigned a higher monitoring priority than companies discovered incidentally.

Conceptually:

- Company Monitoring Priority

**HIGH**

**NORMAL**

**LOW**

Monitoring priority may influence:

- career-site search frequency;
- company-signal collection;
- verification priority;
- reconciliation priority.

It must not directly inflate Job Fit.

### 6.12 On-Demand Search

The user may initiate a search outside the scheduled cadence.

Examples:

> Search now.
>
> Search Seattle now.
>
> Refresh AI Transformation jobs.
>
> Check this company now.

An on-demand search creates its own SearchRun with:

- run_type = ON_DEMAND

It enters the same processing pipeline as scheduled discovery.

An on-demand search must not reset the scheduled cadence.

For example, an 11:15 AM manual search does not cancel the normal noon search unless the scheduler's overlap-control logic determines that running the same plan again would be wasteful.

### 6.13 Overlapping Run Protection

The scheduler must prevent accidental duplicate execution.

Before starting a scheduled run, check whether an equivalent Search Plan is already:

**QUEUED**

or

**RUNNING**

If so, the scheduler may:

- skip the duplicate;
- merge compatible work;
- defer the new run.

The action should be recorded.

Two runs targeting different scopes should be allowed to execute concurrently when system capacity permits.

For example:

- Seattle On-Demand Search

and

Bay Area Scheduled Search

may run simultaneously.

### 6.14 Idempotency

All scheduled discovery operations must be idempotent.

If a task is retried, the system must not create:

- duplicate jobs;
- duplicate job versions;
- duplicate source observations;
- duplicate notifications.

Use stable identifiers, fingerprints and database constraints where appropriate.

This is particularly important because retries are expected in distributed job-processing systems.

### 6.15 Retry Policy

Transient source failures should automatically retry.

Initial policy can use bounded exponential backoff.

Conceptually:

```text
Attempt 1
    ↓ failure
Short Delay
    ↓
Attempt 2
    ↓ failure
Longer Delay
    ↓
Attempt 3
```

The exact retry counts and intervals should be configurable by adapter/source.

Permanent failures such as authorization problems or incompatible responses should not retry indefinitely.

### 6.16 Partial Runs

A scheduled run can complete even when one source fails.

Example:

- 7:00 AM Search

Employer Sources       SUCCESS

Discovery Source A     SUCCESS

Discovery Source B     FAILED

Company Intelligence   SUCCESS

Run Status              PARTIAL

The successfully discovered jobs should still be processed.

The entire run should not be discarded because one source failed.

The dashboard must make the incomplete coverage visible.

### 6.17 Failed Runs

A run should be marked FAILED when the system cannot perform enough of the planned work to produce a meaningful result.

Failure information should include:

- failed component;
- error category;
- retry attempts;
- affected source/scope;
- start/end timestamps.

Operational errors should be recorded separately from job-market results.

### 6.18 Run Completion

A run should not be marked complete simply because discovery finished.

Completion means required downstream processing has reached a defined terminal state.

For example:

- Discovery              COMPLETE

Normalization          COMPLETE

Deduplication          COMPLETE

Verification           COMPLETE / DEFERRED

Matching               COMPLETE

Scoring                COMPLETE

Notification Evaluation COMPLETE

Some noncritical enrichment may remain asynchronous.

The implementation should clearly define which stages are required before SearchRun.status becomes SUCCESS or PARTIAL.

### 6.19 Immediate Opportunity Alerts

The system searches three times per day, but the user should not necessarily have to wait for a digest after a highly relevant opportunity is discovered.

A newly discovered job may qualify for immediate notification when configurable criteria are met.

Example:

```text
New Job
   +
Fit ≥ configured threshold
   +
Priority ≥ configured threshold
   +
Confidence != LOW
   =
Immediate Alert Candidate
```

The exact thresholds will be tuned using the Golden Evaluation Set and user feedback.

The alert should state why the opportunity deserves immediate attention.

### 6.20 Notification Deduplication

Repeated discovery of the same opportunity must not repeatedly notify the user.

Maintain notification history by:

- job_id job_version_id notification_type reason sent_at

A new notification may be appropriate when a material change occurs, such as:

- compensation added;
- location changed;
- job reposted;
- significant JD change;
- Priority materially increased.

### 6.21 Configurable Schedule Settings

The Phase 1 UI should eventually allow the user to configure:

- enabled/disabled scheduled searches;
- run times;
- time zone;
- geographic scopes included;
- role families included;
- reconciliation window;
- immediate-alert behavior;
- notification quiet hours.

The initial UI does not need to expose every advanced scheduler parameter.

Operational parameters such as retry intervals may remain system-level configuration.

### 6.22 Schedule Changes

Changing the schedule should not affect historical search data.

For example, changing:

- 07:00 / 12:00 / 17:00

to:

- 06:00 / 11:00 / 16:00

changes future execution only.

Existing SearchRuns and first-seen timestamps remain unchanged.

### 6.23 Search Cadence Observability

The dashboard should show the latest run status.

Example:

**LAST SEARCH**

Today, 7:00 AM Pacific

**SUCCESS**

**NEXT SEARCH**

Today, 12:00 PM Pacific

**NEW OPPORTUNITIES**

8

**HIGH PRIORITY**

2

**CHANGED**

3

If the last run was partial:

**LAST SEARCH**

Today, 7:00 AM Pacific

**PARTIAL**

1 discovery source failed.

Results may be incomplete.

This prevents the user from assuming that silence means no opportunities exist.

### 6.24 Search Cadence History

Retain historical execution information so the system can answer:

- Did the morning search run?
- Which sources succeeded?
- Which source discovered a particular job?
- Which run first discovered it?
- How long after employer posting did we find it?
- How frequently is a source failing?
- Which search period produces the strongest opportunities?

This history will also help optimize search cadence later.

### 6.25 Initial Phase 1 Scheduling Configuration

The initial implementation should start with:

Time Zone:

- America/Los_Angeles

Scheduled Incremental Searches:

- 07:00
- 12:00
- 17:00

Reconciliation Window:

- 72 hours

Baseline:

- On initial setup or explicit/targeted rebuild

On-Demand Search:

- Enabled

Automatic Retry:

- Enabled

Partial Run Processing:

- Enabled

Immediate High-Priority Alerts:

- Enabled

Schedule Configuration:

- Editable

These are initial configuration values rather than permanent assumptions.

### 6.26 Implementation Principle

The scheduling system should answer four separate questions:

- WHAT should we search?
- Defined by the Job Search Taxonomy.
- WHERE should we search?
- Defined by Geographic Scopes.
- HOW should we search?
- Defined by the Search Operating Model and source adapters.
- WHEN should we search?
- Defined by the Search Schedule and Cadence.
- Keeping these concerns separate is a fundamental Phase 1 architecture principle.

## 7. Discovery and Intelligence Sources

Phase 1 uses four distinct source classes. Each source class has a different purpose in the discovery and intelligence pipeline.

The four source classes are:

- Company Career Sites / Applicant Tracking Systems
- Job Sites / Aggregators
- Professional / Social Sources
- Company and Market Intelligence Sources

The overall source strategy is:

```text
Discover broadly → Verify at the company → Enrich with company and market intelligence → Overlay network intelligence → Analyze → Score → Prioritize
```

### 7.1 Source Class 1 — Company Career Sites / ATS

Company career sites and employer Applicant Tracking Systems should be treated as the preferred canonical source of truth for job openings whenever available.

Examples include an employer's own careers site or its public ATS-hosted job pages.

These sources are used to confirm that an opportunity actually exists and remains open.

Capture when available:

- Company
- Job title
- Requisition ID
- Full job description
- Location
- Work model
- Compensation
- Employer posting date
- Employment type
- Application URL
- Job status
- Canonical job URL

When a job is discovered through another source, the system should attempt to locate the corresponding employer posting.

If found, the employer posting becomes the preferred canonical record while the original discovery source remains attached as provenance.

### 7.2 Source Class 2 — Job Sites / Aggregators

Job sites and aggregators provide the broad discovery layer.

Their primary purpose is coverage.

They help identify opportunities that:

- have not yet been discovered through company monitoring;
- come from companies not currently on the Target Company Universe;
- use unexpected job titles;
- appear in geographic or functional searches;
- may reveal new companies worth monitoring.

The platform may search multiple appropriate job-discovery sources.

A listing discovered through an aggregator should not automatically become the canonical job record.

The system should attempt to verify it against the employer's career site.

If the same requisition appears through several sources, the user should normally see one opportunity, with all relevant source observations retained behind it.

### 7.3 Source Class 3 — Professional / Social Sources

Professional and social sources provide job-discovery, company, hiring, and network intelligence.

This source class serves several different purposes.

#### Job Discovery

Publicly available job postings or job announcements may identify relevant opportunities.

Where possible, those opportunities should subsequently be verified against the employer's career site.

#### Hiring and Organizational Signals

Professional sources may reveal signals such as:

- hiring announcements;
- team expansion;
- technology-organization growth;
- executive appointments;
- transformation initiatives;
- AI initiatives;
- platform investments;
- organizational changes.

These signals may increase the relevance of a company for continued monitoring.

#### Network Intelligence

Phase 1 also uses the user's imported LinkedIn first-degree Connections data package.

The LinkedIn connection import is used to identify:

- first-degree connections at a hiring company;
- connection titles;
- potentially relevant functional relationships;
- possible relationship advantages.

Network information affects Application Priority, but it must not inflate the underlying Fit Score.

Phase 1 must not depend on credential-based LinkedIn scraping.

The network integration should use a replaceable adapter so an approved official API integration could be introduced later without redesigning the matching system.

### 7.4 Source Class 4 — Company and Market Intelligence

Company and market intelligence helps answer a different question:

> Why should we be watching this company?

Sources may include:

- company newsrooms;
- company press releases;
- public regulatory filings;
- acquisition announcements;
- funding announcements;
- reputable business news;
- reputable technology news;
- publicly announced AI initiatives;
- transformation programs;
- major technology investments;
- leadership appointments.

Relevant company signals may include:

- new CIO or CTO;
- significant AI investment;
- cloud modernization;
- platform transformation;
- acquisitions;
- rapid technology-organization growth;
- enterprise transformation;
- security or regulatory transformation;
- new operating-model initiatives.

A company may therefore remain important even when no appropriate job is currently open.

The system should be capable of representing:

> No suitable opening currently, but this company remains worth monitoring.

### 7.5 Source Roles

The four source classes should not be treated as interchangeable.

Their primary roles are:

| Source Class | Primary Purpose |
|---|---|
| Company Career Sites / ATS | Verification and canonical job record |
| Job Sites / Aggregators | Broad job discovery |
| Professional / Social | Job, hiring, organizational and network intelligence |
| Company / Market Intelligence | Company relevance and strategic signals |

A source may contribute information outside its primary role, but the system should preserve where each piece of information originated.

### 7.6 Source Provenance

Every externally obtained observation must retain provenance.

Conceptually:

```text
SourceObservation {
    source_id
    source_class
    source_name
    source_url_or_reference
    retrieved_at
    source_posted_at?
    first_seen_at
    last_seen_at
    content_hash
    confidence
    fetch_status
}
```

This allows the system to answer:

- Where did this information come from?
- When did we retrieve it?
- Which source found the job first?
- Has the information changed?
- Was the job independently verified?
- Which source should be treated as canonical?

### 7.7 Canonicalization Policy

When multiple sources describe the same opportunity, the system should create one canonical Job entity.

The preferred hierarchy is generally:

```text
Employer Career Site / ATS
↓
Other verified job source
↓
Aggregator discovery record
```

The original discovery record must still be preserved.

For example:

```text
LinkedIn / Aggregator
       ↓
Job Discovered
       ↓
Employer Career Site Located
       ↓
Canonical Job Record
       ↓
Original Source Retained as Provenance
```

This prevents duplicate opportunities while preserving discovery history.

### 7.8 Source Confidence

Information quality varies by source and by field.

For example:

- An employer career page may provide high confidence that a job exists.
- An aggregator may provide useful discovery information but an outdated posting date.
- A news article may provide strong evidence that a company announced an acquisition but no evidence that a particular job exists.

Confidence should therefore be associated with the specific observation and its purpose, rather than assigning one universal trust score to an entire source.

### 7.9 Source Performance

The platform should measure how effectively each source contributes to the search.

Track metrics such as:

- search success rate;
- source failures;
- jobs discovered;
- unique jobs discovered;
- jobs first discovered by source;
- high-Fit jobs discovered;
- high-Priority jobs discovered;
- duplicate rate;
- canonical verification rate;
- discovery latency;
- user-interest rate.

Over time, the system should be able to answer:

> Which sources consistently find valuable opportunities first?

This allows search resources to be concentrated on the most productive sources.

### 7.10 Source Health

Every scheduled search run should record the health of each expected source.

Example:

- Company Career Sources     SUCCESS
- Job Discovery Source A     SUCCESS
- Job Discovery Source B     FAILED
- Professional Signals       SUCCESS
- Company Intelligence       SUCCESS

Overall Search Run         PARTIAL

A source failure must never be interpreted as:

> No jobs found.

Instead, the system must explicitly report that search coverage was incomplete.

### 7.11 Source Architecture Principle

External sources will change over time.

Therefore, each source integration must be implemented behind an adapter interface.

Conceptually:

- JobDiscoveryAdapter
- CompanyCareerAdapter
- ProfessionalSignalAdapter
- CompanyIntelligenceAdapter
- NetworkDataAdapter

This allows sources to be:

- added;
- replaced;
- disabled;
- upgraded;
- authenticated differently;
- migrated to an official API later

without redesigning the core job intelligence system.

### 7.12 Source Strategy Summary

The Phase 1 source strategy is:

- Job Sites / Aggregators
- Find opportunities broadly.

```text
↓
Company Career Sites / ATS
```

Verify opportunities and establish canonical records.

```text
↓
Professional / Social Sources
```

Add hiring, organizational and network context.

```text
↓
Company / Market Intelligence
```

Explain why companies may deserve continued attention.

```text
↓
Career Profile + Network Intelligence
```

Evaluate personal relevance.

```text
↓
Fit + Confidence + Application Priority
```

Determine what deserves the user's attention.

## 8. User, Career Profile and Network Data

Phase 1 requires a structured representation of the user's professional background, career objectives, search preferences, and professional network.

These data sets serve different purposes and must remain logically separated:

- User Profile — basic account and application preferences.
- Master Career Profile — professional history, accomplishments, capabilities, leadership scope, and career direction.
- Search Preferences — what the user wants in the next opportunity.
- Network Data — imported first-degree professional connections.
- Profile Evidence — traceable evidence supporting job-match conclusions.

The system must never invent professional experience, qualifications, accomplishments, or leadership scope in order to improve a job match.

### 8.1 User Profile

The UserProfile contains basic account-level configuration.

Conceptually:

```text
UserProfile {
    user_id
    preferred_name?
    timezone
    default_currency
    notification_preferences
    created_at
    updated_at
}
```

Career information should not be unnecessarily mixed into the basic user record.

Changing a target role, geographic preference, or compensation expectation should update the appropriate career/search configuration rather than changing the user's identity record.

### 8.2 Master Career Profile

The Master Career Profile is the authoritative structured representation of the user's professional background.

It contains substantially more information than a traditional resume.

A resume is primarily a presentation document.

The Master Career Profile is a career intelligence data model used for matching, scoring, explanation, and later Phase 2 and Phase 3 capabilities.

Conceptually:

```text
CareerProfile {
    career_profile_id
    user_id
    executive_summary?
    experiences[]
    achievements[]
    leadership_capabilities[]
    functional_capabilities[]
    technical_capabilities[]
    industries[]
    domains[]
    transformation_experience[]
    platform_experience[]
    cloud_experience[]
    security_governance_experience[]
    privacy_experience[]
    ai_experience[]
    ma_experience[]
    organization_scope[]
    financial_scope[]
    career_direction[]
    version
    created_at
    updated_at
}
```

The Master Career Profile should be extensible so additional career information can be incorporated later without redesigning the data model.

### 8.3 Employment Experience

Each significant professional experience should be represented structurally.

Conceptually:

```text
Experience {
    experience_id
    career_profile_id
    company
    title
    start_date?
    end_date?
    organization_scope?
    team_scope?
    geographic_scope?
    responsibilities[]
    achievements[]
    technologies[]
    capabilities[]
    domains[]
    evidence_source?
}
```

The matching engine must understand both:

> What role did the user hold?

and:

> What did the user actually do in that role?

Job titles alone are insufficient evidence of capability or leadership scope.

### 8.4 Career Achievements

Important accomplishments should be stored as individual structured evidence objects rather than existing only as text inside a resume.

Conceptually:

```text
Achievement {
    achievement_id
    experience_id?
    description
    category
    quantified_impact?
    scale?
    technologies[]
    capabilities[]
    evidence_source?
    confidence
}
```

Achievement categories may include:

- enterprise transformation;
- technology transformation;
- platform modernization;
- developer productivity;
- cloud transformation;
- AI / ML;
- cybersecurity;
- privacy;
- governance;
- portfolio management;
- program management;
- M&A;
- vendor management;
- financial management;
- organizational leadership;
- operational efficiency.

Where a quantified result is known, the actual metric should be preserved.

The system must not manufacture numerical impact.

### 8.5 Leadership and Organizational Scope

Executive-job matching requires explicit representation of leadership scale.

Capture when known:

- organization size;
- direct reports;
- indirect reports;
- manager-of-managers responsibility;
- geographic responsibility;
- global responsibility;
- budget responsibility;
- vendor spend;
- portfolio size;
- executive stakeholder exposure;
- board exposure;
- cross-functional authority;
- transformation scope;
- business-unit scope;
- decision-making authority.

Unknown information should remain unknown.

The system must never infer a specific team size, budget, reporting relationship, or organizational scale without supporting evidence.

### 8.6 Capability Model

Career capabilities should be organized into categories rather than maintained as one flat keyword list.

Initial categories include:

#### Executive Leadership

- organizational leadership;
- executive stakeholder management;
- strategic planning;
- operating-model design;
- transformation leadership;
- change management;
- cross-functional leadership.

#### Technology / Product Operations

- technology operations;
- product operations;
- engineering operations;
- operating cadence;
- organizational effectiveness;
- operational excellence.

#### Program / Portfolio

- technical program management;
- enterprise program management;
- portfolio management;
- portfolio governance;
- PMO;
- TMO;
- roadmap governance;
- prioritization;
- executive reporting.

#### Platforms / Engineering

- platform strategy;
- platform operations;
- developer platforms;
- developer productivity;
- engineering productivity;
- engineering enablement;
- CI/CD;
- DevOps;
- DevSecOps.

#### Cloud / Enterprise Technology

- AWS;
- GCP;
- Azure where applicable;
- cloud transformation;
- cloud governance;
- infrastructure modernization;
- enterprise technology.

#### Security / Risk / Privacy

- cybersecurity governance;
- enterprise risk;
- security transformation;
- ISO 27001;
- SOC 2;
- privacy;
- identity;
- compliance;
- AI governance.

#### AI / ML

- AI strategy;
- AI governance;
- AI transformation;
- AI adoption;
- AI platforms;
- MLOps where applicable;
- agentic AI where applicable.

#### Corporate / Business

- M&A;
- due diligence;
- transition service agreements;
- vendor management;
- financial management;
- business transformation.

Every capability used as evidence in job matching must be supported by actual Career Profile information.

### 8.7 Career Direction

The system must distinguish between:

- Historical Capability and
- Desired Career Direction
- This is critical because a person may have extensive experience in an area without wanting their next role centered on that function.

The matching system should therefore separately evaluate:

> Can the user perform this job?

and:

> Does this opportunity move the user toward the career direction they want?

Career Direction should be an explicit component of the Master Career Profile and an explicit component of Fit scoring.

### 8.8 Search Preferences

Search Preferences define what the user wants the system to look for now.

They should remain separate from historical career facts.

Conceptually:

```text
SearchPreferences {
    user_id
    target_role_family_ids[]
    geographic_scope_ids[]
    allowed_work_models[]
    compensation_preferences
    industry_preferences[]
    company_preferences[]
    travel_preferences?
    relocation_preferences?
    hard_filters[]
    soft_preferences[]
    enabled
    version
}
```

Search Preferences should be editable without rewriting the Master Career Profile.

### 8.9 Compensation Preferences

Where configured, compensation preferences may include:

- minimum acceptable base compensation;
- preferred base range;
- bonus expectations;
- equity expectations;
- total compensation expectations.

Job postings frequently contain incomplete compensation information.

If compensation is unavailable, the system should return:

- Compensation Fit: UNKNOWN

It should not penalize or reward an opportunity based on invented compensation assumptions.

### 8.10 Hard Filters vs. Preferences

Search Preferences must distinguish between explicit hard requirements and preferences.

Example:

Hard Filter:

- U.S.-based employment only

versus:

Preference:

- Bay Area hybrid preferred

or:

Preference:

- Enterprise technology environment preferred

Only explicit configuration should create a hard exclusion.

Learned preferences must not silently become hard filters.

### 8.11 Profile Evidence

Career claims used during matching should be traceable to evidence.

Conceptually:

```text
ProfileEvidence {
    evidence_id
    career_profile_id
    evidence_type
    source_reference?
    experience_id?
    achievement_id?
    text
    confidence
}
```

Possible evidence sources include:

- master resume;
- previous resumes;
- structured user input;
- professional-profile information supplied by the user;
- verified career-history information;
- user-approved profile updates.

The objective is traceability.

### 8.12 Evidence-Based Matching

When the matching engine says:

> Strong enterprise transformation experience

it must be able to identify the Career Profile evidence supporting that conclusion.

Conceptually:

```text
JOB REQUIREMENT
       ↓
MATCHED CAPABILITY
       ↓
CAREER EVIDENCE
       ↓
MATCH REASON
```

For example:

Job Requirement:

- Lead enterprise-wide technology transformation

Matched Capability:

- Enterprise Transformation

Career Evidence:

- Specific transformation leadership experience from the Master Career Profile

Result:

- Strong positive match

This prevents unsupported AI-generated conclusions.

### 8.13 Missing Career Information

The system must distinguish between:

**NO EVIDENCE OF EXPERIENCE**

and:

**INSUFFICIENT INFORMATION**

For example, if a job requires responsibility for a $500M budget and the Career Profile confirms financial-management experience but does not specify a comparable budget amount, the system should report:

> The Career Profile contains relevant financial-management experience, but available evidence does not establish comparable budget scale.

It should not automatically conclude that the user lacks the experience.

Missing information should also influence Recommendation Confidence.

### 8.14 Career Profile Versioning

The Master Career Profile must be versioned.

For example:

- CareerProfile v12
- CareerProfile v13
- CareerProfile v14

Every job analysis should record the Career Profile version used to generate it.

This makes a historical recommendation reproducible.

When the Career Profile changes materially, relevant active opportunities may be rescored.

### 8.15 Search Preference Versioning

Search Preferences should be versioned independently from Career Profile information.

Changes such as:

- adding target roles;
- removing role families;
- changing geographic scopes;
- changing work-model preferences;
- changing compensation requirements;
- adding hard filters

should create a new Search Preferences version.

Historical SearchRuns must retain the configuration version used at execution time.

### 8.16 Network Data Source

Phase 1 assumes the user periodically provides a LinkedIn Connections data export/package.

The application must not require the user's LinkedIn username or password.

The Phase 1 network workflow is:

```text
LinkedIn Connections Export
        ↓
Upload
        ↓
Parse
        ↓
Validate
        ↓
Preview
        ↓
Normalize Companies
        ↓
Resolve Ambiguities
        ↓
Commit Import
        ↓
Match Connections to Companies
        ↓
Recalculate Application Priority
```

The network architecture should use a replaceable adapter so another authorized network-data source could be introduced later without redesigning the matching engine.

### 8.17 Connection Import

The application should provide an:

- Import LinkedIn Connections function.

Before committing the import, show:

- records parsed;
- valid records;
- rejected records;
- duplicate records;
- company mappings;
- ambiguous company mappings;
- parsing errors.

Ambiguous employer mappings should be reviewable before commit.

### 8.18 Connection Model

Conceptually:

```text
Connection {
    connection_id
    user_id
    first_name
    last_name
    profile_url?
    company_raw?
    company_id?
    position_raw?
    connected_on?
    relationship_strength?
    import_batch_id
    imported_at
}
```

Raw imported company and position values should be preserved even after normalization.

### 8.19 Connection Import Batch

Every import should be recorded.

Conceptually:

```text
ConnectionImportBatch {
    import_batch_id
    user_id
    imported_at
    source_type
    source_file_hash?
    records_parsed
    records_accepted
    records_rejected
    ambiguous_company_count
    status
}
```

The user interface should display:

> LinkedIn connections last refreshed: [date]

This makes it clear that the network information represents a snapshot.

### 8.20 Network Snapshot Limitation

Imported LinkedIn connection information is not a live synchronization.

If a connection changes employers after an import, the platform may continue showing the previous employer until another import occurs.

Therefore, every imported connection must retain its import timestamp.

The application should not present snapshot employment information as guaranteed real-time information.

### 8.21 Company Normalization for Connections

Network matching depends on accurate company identity.

Imported employer values may contain variations such as:

- Company X
- Company X Inc.
- Company X Cloud
- Company X Technologies

The platform therefore maintains:

- Company
- CompanyAlias

Company resolution should use:

- deterministic alias matching;
- normalized exact matching;
- high-confidence fuzzy matching;
- manual review for ambiguous cases.

The system must never silently associate an ambiguous connection with the wrong company.

### 8.22 Network Matching

Once a connection's company has been normalized, connections can be associated with jobs at that company.

Conceptually:

```text
JOB
 ↓
COMPANY
 ↓
NORMALIZED COMPANY ID
 ↓
CONNECTIONS
```

The Job Detail page can then display:

Network:

- 4 first-degree connections

and identify the relevant connections.

### 8.23 Relationship Strength

Connection count alone is insufficient.

One former close colleague who knows the user's work may be more useful than several weak professional acquaintances.

The data model should therefore support:

- relationship_strength

Initial values:

**STRONG**

**MEDIUM**

**WEAK**

**UNKNOWN**

The LinkedIn import should not automatically infer relationship strength.

Unless the user provides this information, it remains:

**UNKNOWN**

### 8.24 Connection Relevance

Relationship strength and opportunity relevance are different concepts.

A connection may be especially relevant because the person is:

- in the hiring organization;
- an executive at the company;
- in the relevant technology organization;
- in recruiting or talent;
- a former colleague familiar with the user's work;
- otherwise positioned to provide useful context.

Phase 1 may calculate Network Relevance using known factual information.

It must not invent reporting relationships or organizational influence.

### 8.25 Network Strength

Application Priority may eventually use a composite network signal.

Conceptually:

- Network Strength =

```text
  Connection Presence
+ Relationship Strength
+ Opportunity Relevance
```

The precise weighting should be tuned later.

The critical rule is:

> Network Strength must never be included in Job Fit Score.

Network affects Application Priority, not whether the user is qualified for the job.

### 8.26 Network Examples

#### Strong Fit, No Connections

Fit: 94

Network: 0 connections

This remains an excellent career match.

#### Strong Fit, Strong Network

Fit: 94

Network: 4 relevant connections

Fit remains 94.

Application Priority may increase.

#### Weak Fit, Strong Network

Fit: 58

Network: 12 connections

The job remains a weak career match.

The network must not push the opportunity into the highest recommendation category merely because many connections work there.

### 8.27 Network Privacy and Security

Professional network information must be treated as personal data.

Requirements include:

- encryption in transit;
- encryption at rest;
- access restricted to the owning user;
- no unnecessary connection information in logs;
- ability to delete imported network information;
- audit trail for imports and deletions;
- configurable retention of raw import files.

Phase 1 does not automatically contact connections.

### 8.28 Profile Update Workflow

The user should be able to correct or enhance the Master Career Profile.

Conceptually:

```text
Current Career Profile
        ↓
Proposed Update
        ↓
Validation
        ↓
User Confirmation where appropriate
        ↓
New Career Profile Version
        ↓
Recalculate Affected Matches
```

AI may identify potentially missing career information and suggest that it be added.

It must not silently create significant career facts.

### 8.29 Separation of Career Truth, Explicit Preference and Learned Preference

The platform must keep three concepts separate.

#### Career Truth

What the user has actually done.

Examples:

- employment history;
- accomplishments;
- leadership scope;
- capabilities;
- technologies;
- industries.

#### Explicit Preference

What the user explicitly says they want.

Examples:

- target roles;
- geography;
- work model;
- compensation;
- preferred industries;
- exclusions.

#### Learned Preference

Patterns derived from user feedback.

Examples:

- repeatedly rejecting roles with insufficient leadership scope;
- consistently selecting transformation-heavy roles;
- preferring certain company characteristics.

Learned preferences may influence ranking.

They must never rewrite Career Truth or silently create hard filters.

### 8.30 Phase 1 Data Ownership Principle

The Master Career Profile should become a durable platform asset rather than something built specifically for one search.

In Phase 1:

```text
Career Profile
      ↓
Job Matching
```

In Phase 2:

```text
Career Profile
      ↓
Resume Tailoring
```

Networking Strategy

Application Strategy

In Phase 3:

```text
Career Profile
      ↓
Interview Preparation
```

Career-Market Analytics

Opportunity Anticipation

This prevents the system from repeatedly reconstructing the user's career history for every new capability.

### 8.31 Section 8 Implementation Principle

Section 8 establishes four fundamental rules:

> The Master Career Profile defines what the user has actually done.
>
> Search Preferences define what the user wants next.
>
> Network Data identifies relationship advantages.
>
> Feedback helps the system learn how to rank opportunities more effectively.

These data sets interact during recommendation generation but remain independently stored, traceable, and versioned.

The fundamental relationship is:

**JOB REQUIREMENTS**

```text
        ↕
MASTER CAREER PROFILE
        ↓
       FIT
```

**FIT**

```text
 + FRESHNESS
 + NETWORK
 + COMPENSATION
 + LOCATION
 + USER PREFERENCES
        ↓
APPLICATION PRIORITY
```

This separation allows the platform to answer two distinctly different questions:

> Why is this a strong career match?

and:

> Why should I pay attention to this opportunity right now?

## 9. Matching, Scoring and Explainability

The Matching, Scoring and Explainability Engine determines how relevant each discovered opportunity is to the user and why it deserves—or does not deserve—attention.

The engine produces three separate primary outputs:

- Fit Score — How well does this job match the user's demonstrated experience, leadership scope, capabilities, and desired career direction?
- Recommendation Confidence — How confident is the system in the Fit assessment?
- Application Priority — How much attention should the user give this opportunity right now?

These outputs must remain separate.

```text
JOB
 ↓
JOB REQUIREMENTS + RESPONSIBILITIES + SCOPE
 ↓
MASTER CAREER PROFILE
 ↓
FIT SCORE
 +
RECOMMENDATION CONFIDENCE
```

**FIT**

```text
 + FRESHNESS
 + NETWORK
 + COMPENSATION
 + LOCATION / WORK MODEL
 + USER PREFERENCES
 + OPPORTUNITY CONTEXT
 ↓
APPLICATION PRIORITY
```

A strong network must never make a weak career match appear to be a strong Fit.

Incomplete information should normally reduce Confidence rather than automatically reducing Fit.

### 9.1 Structured Job Analysis

Before calculating any score, the system converts the job description into a structured representation.

```text
JobAnalysis {
    job_id
    normalized_title
    inferred_role_family
    inferred_seniority
    inferred_scope
    primary_responsibilities[]
    required_capabilities[]
    preferred_capabilities[]
    leadership_requirements[]
    technical_requirements[]
    domain_requirements[]
    industry_requirements[]
    transformation_requirements[]
    platform_requirements[]
    cloud_requirements[]
    ai_requirements[]
    security_governance_requirements[]
    compensation_information?
    work_model?
    travel_requirement?
    positive_scope_signals[]
    negative_signals[]
    ambiguities[]
    missing_information[]
    analysis_confidence
}
```

The matching engine evaluates the substance of the job rather than relying primarily on title or keyword similarity.

### 9.2 Requirement Classification

Job requirements should be classified before matching.

Initial classifications:

**REQUIRED**

**PREFERRED**

**CONTEXTUAL**

**INFERRED**

**UNKNOWN**

Requirements should also be assigned an importance level:

**CORE**

**IMPORTANT**

**SUPPORTING**

**MINOR**

If a job repeatedly emphasizes enterprise transformation, organizational leadership, and portfolio governance, those requirements should carry more importance than a technology mentioned once in a long list.

The system must not assume that every keyword in a job description has equal importance.

### 9.3 Requirement-to-Evidence Matching

Each significant job requirement is compared with evidence in the Master Career Profile.

```text
JOB REQUIREMENT
      ↓
CAREER CAPABILITY
      ↓
SUPPORTING EXPERIENCE
      ↓
SUPPORTING ACHIEVEMENT
      ↓
EVIDENCE STRENGTH
      ↓
MATCH ASSESSMENT
```

Conceptually:

```text
RequirementMatch {
    requirement_id
    requirement_text
    importance
    matched_capability_ids[]
    evidence_ids[]
    match_strength
    evidence_strength
    gap_type?
    explanation
}
```

This relationship provides the foundation for scoring and explainability.

### 9.4 Match Strength

Each significant requirement may be classified as:

- STRONG_MATCH
- GOOD_MATCH
- PARTIAL_MATCH
- WEAK_MATCH
- NO_MATCH
**UNKNOWN**

UNKNOWN is materially different from NO_MATCH.

If a role requires a specific budget responsibility but the Career Profile does not contain enough information to determine comparable budget scope, the result should normally be UNKNOWN, not NO_MATCH.

### 9.5 Fit Score

The Fit Score answers:

> How well does this opportunity match the user's demonstrated experience, leadership scope, capabilities, and desired career direction?

Initial scale:

- 0–100

Fit should be calculated from structured components rather than generated directly by an LLM.

Conceptually:

- Fit Score =

```text
  Role / Responsibility Fit
+ Seniority / Scope Fit
+ Capability Fit
+ Leadership Fit
+ Career Direction Fit
+ Domain / Industry Fit
```

Exact weights must be configurable and tuned using the Golden Evaluation Set and actual user feedback.

### 9.6 Initial Fit Components

#### Role / Responsibility Fit

Does the actual work resemble responsibilities the user has successfully performed?

#### Seniority / Scope Fit

Does the organizational scope align with the user's demonstrated leadership level?

#### Capability Fit

Does the Career Profile contain evidence supporting the major capabilities required by the role?

#### Leadership Fit

Does the opportunity require the executive, organizational, cross-functional, or transformation leadership demonstrated by the user?

#### Career Direction Fit

Does the opportunity move the user toward the desired next career direction?

#### Domain / Industry Fit

Does the opportunity require specialized functional, domain, or industry experience, and how important is that requirement?

These components should remain individually available for debugging, testing, and explanation even if the user interface presents a simplified overall Fit Score.

### 9.7 Configurable Fit Weighting

Fit weights must not be permanently embedded in application code.

```text
FitScoringModel {
    model_version
    role_responsibility_weight
    seniority_scope_weight
    capability_weight
    leadership_weight
    career_direction_weight
    domain_industry_weight
    effective_at
}
```

An initial illustrative configuration could be:

- Role / Responsibility       25%
- Seniority / Scope           20%
- Capability                  20%
- Leadership                  15%
- Career Direction            15%
- Domain / Industry            5%

These are starting parameters, not finalized scoring policy.

They should be tuned against the Golden Evaluation Set and real user feedback.

### 9.8 Fit Must Exclude Network and Urgency

The following must not increase Job Fit:

- number of connections at the company;
- relationship strength;
- recruiter connections;
- referral availability;
- posting freshness;
- application timing;
- urgency.

Example:

- Opportunity A

Career Match: Excellent

Connections: 0

Fit: 94

Opportunity B

Career Match: Excellent

Connections: 6

Fit: 94

Network and timing may affect Application Priority.

They do not affect Fit.

### 9.9 Seniority and Role-Scope Inference

Job titles are unreliable indicators of actual organizational level.

The system should infer role scope from the complete job description.

Signals may include:

- reporting relationship;
- team size;
- manager-of-managers responsibility;
- budget ownership;
- portfolio ownership;
- enterprise-wide responsibility;
- global responsibility;
- executive stakeholder exposure;
- board interaction;
- organizational-design responsibility;
- decision authority;
- strategic-planning responsibility;
- cross-functional scope.

The system should therefore be capable of recognizing that a Senior Director role may have greater actual scope than some VP roles, or that a VP title may represent a relatively narrow function.

Actual scope is more important than title prestige.

### 9.10 Scope Classification

Conceptually:

```text
RoleScope {
    people_scope?
    manager_of_managers?
    geographic_scope?
    financial_scope?
    portfolio_scope?
    decision_scope?
    executive_exposure?
    organizational_scope?
    inferred_level
    confidence
}
```

Possible inferred levels:

**EXECUTIVE**

VP_EQUIVALENT

SENIOR_DIRECTOR_EQUIVALENT

DIRECTOR_EQUIVALENT

INDIVIDUAL_CONTRIBUTOR

**UNKNOWN**

These classifications support analysis and do not replace the employer's actual title.

### 9.11 Career Direction Fit

Historical experience alone should not determine Fit.

The system must explicitly evaluate whether the opportunity advances the user's desired career direction.

A user may have substantial historical experience in a function but no longer want that function to dominate the next role.

A role may therefore have:

- Historical Capability Fit: HIGH
- Career Direction Fit: LOW

The matching engine should ask two different questions:

> Can the user perform this job?

and:

> Does the user want their career to move in this direction?

Career Direction Fit should influence the overall Fit Score.

### 9.12 Career Direction Protection

Career Direction Fit prevents the recommendation engine from repeatedly surfacing roles simply because the user performed similar work historically.

The system should distinguish:

**CAN DO**

from:

**WANTS TO DO NEXT**

This prevents historically relevant roles from unintentionally pulling the user's career backward or sideways.

### 9.13 Negative-Fit Detection

The system should actively identify characteristics that make an otherwise keyword-compatible opportunity unattractive.

Examples include:

- quota-carrying responsibility;
- sales-pipeline ownership;
- primarily hands-on coding;
- individual-contributor structure;
- insufficient leadership scope;
- materially excessive travel;
- compensation materially below requirements;
- incompatible relocation requirements;
- unsupported specialized domain requirements;
- responsibilities substantially outside desired career direction.

Conceptually:

```text
NegativeSignal {
    type
    evidence
    severity
    confidence
    hard_filter_triggered
}
```

### 9.14 Hard Exclusions vs. Negative Signals

Not every concern eliminates a job.

A negative signal may:

- Reduce Fit
- Reduce Priority
- Generate a Concern
- Trigger a Hard Filter
- Have No Scoring Effect

depending on configuration.

For example, required relocation may trigger a hard exclusion when relocation is explicitly disallowed.

A 20% travel requirement may instead appear as a concern when travel is undesirable but acceptable.

Only explicitly configured hard requirements should automatically eliminate an opportunity.

### 9.15 Gap Analysis

The system should identify meaningful gaps for each relevant opportunity.

Gap categories may include:

- CAPABILITY_GAP
- LEADERSHIP_SCOPE_GAP
- INDUSTRY_GAP
- DOMAIN_GAP
- TECHNICAL_DEPTH_GAP
- CERTIFICATION_GAP
- CAREER_DIRECTION_CONCERN
- COMPENSATION_CONCERN
- LOCATION_CONCERN
- MISSING_INFORMATION

Gaps should be prioritized according to their importance to the role.

The system should avoid overwhelming the user with trivial keyword differences.

### 9.16 Missing Information vs. Genuine Gap

The distinction between missing information and an actual capability gap must be explicit.

Example job requirement:

- Managed $300M+ technology portfolio

Career Profile:

- Substantial technology portfolio leadership, but exact portfolio value is not recorded.

Correct classification:

- MISSING_INFORMATION

Incorrect classification:

- PORTFOLIO_SCOPE_GAP

Important missing information should reduce Recommendation Confidence.

It should not automatically reduce Fit as though missing data proves missing experience.

### 9.17 Recommendation Confidence

Recommendation Confidence answers:

> How confident is the system that the Fit assessment is reliable?

Initial user-facing levels:

**HIGH**

**MEDIUM**

**LOW**

Confidence remains separate from Fit.

Example:

- Fit: 91
- Confidence: HIGH

means the available evidence strongly supports the assessment.

Fit: 91

Confidence: LOW

means the opportunity appears promising, but important information is incomplete or ambiguous.

### 9.18 Confidence Factors

Recommendation Confidence may consider:

- completeness of the job description;
- clarity of responsibilities;
- clarity of organizational scope;
- strength of Career Profile evidence;
- amount of missing Career Profile information;
- canonical job verification;
- source confidence;
- compensation completeness;
- work-model clarity;
- ambiguity in role classification.

Conceptually:

```text
RecommendationConfidence {
    job_id
    level
    internal_score?
    positive_factors[]
    uncertainty_factors[]
    model_version
}
```

The application may maintain a numeric internal confidence score while presenting only High, Medium, or Low to the user.

### 9.19 Application Priority

Application Priority answers:

> How much attention should the user give this opportunity right now?

Application Priority is not another Fit Score.

Conceptually:

- Application Priority =

```text
  Fit
+ Freshness / Timing
+ Network Strength
+ Compensation Fit
+ Location / Work-Model Fit
+ Explicit User Preferences
+ Opportunity Context
```

Recommendation Confidence may constrain Priority when the available evidence is unusually weak.

### 9.20 Application Priority Levels

Initial user-facing categories:

**IMMEDIATE**

**HIGH**

**MEDIUM**

**LOW**

#### IMMEDIATE

Strong match with a compelling reason to act quickly.

#### HIGH

Strong opportunity deserving prompt review.

#### MEDIUM

Potentially worthwhile but with meaningful concerns, uncertainty, or lower urgency.

#### LOW

Currently unlikely to justify significant attention.

Thresholds should remain configurable.

### 9.21 Freshness and Timing

Application Priority should consider both:

- employer_posted_at

and:

- first_seen_at

A strong opportunity posted six hours ago may deserve more immediate attention than an otherwise equivalent opportunity open for several weeks.

However, older opportunities should not automatically be discarded.

Freshness is an urgency signal, not a qualification signal.

### 9.22 Network Contribution to Priority

Network information affects Application Priority only.

Possible signals include:

- number of first-degree connections;
- relationship strength;
- connection relevance;
- former close colleagues;
- relevant executives;
- people in the likely hiring organization;
- recruiting or talent connections.

Conceptually:

```text
NetworkPrioritySignal {
    connection_count
    strong_relationship_count
    relevant_connection_count
    network_strength
    explanation
}
```

The system must not infer relationship strength where it is unknown.

### 9.23 Compensation Fit

Where compensation information exists, compare it against configured preferences.

Possible results:

**STRONG**

**ACCEPTABLE**

BELOW_PREFERENCE

BELOW_MINIMUM

**UNKNOWN**

BELOW_MINIMUM may trigger a hard exclusion if the user explicitly configures minimum compensation as a hard requirement.

If compensation is unavailable:

- Compensation Fit: UNKNOWN

The system must not invent compensation.

### 9.24 Location and Work-Model Fit

Evaluate:

- geographic eligibility;
- preferred geography;
- commute implications where configured;
- remote eligibility;
- hybrid requirements;
- onsite requirements;
- relocation requirements;
- travel requirements.

Possible results:

**PREFERRED**

**ACCEPTABLE**

**UNDESIRABLE**

**INELIGIBLE**

**UNKNOWN**

Location and Work-Model Fit affect Application Priority unless an explicit hard filter makes the opportunity ineligible.

### 9.25 User Preference Signal

Explicit and learned user preferences may influence Application Priority and ranking, but they must not alter the underlying Fit Score.

Fit represents the evidence-based career match between the opportunity and the user’s Career Evidence. It must remain independent of whether the user personally prefers or dislikes a particular company, industry, location, work model, compensation range, or other opportunity characteristic.

Explicit user preferences may affect:

- Application Priority;
- ranking among otherwise relevant opportunities;
- notification eligibility or urgency;
- explanations such as Why Now;
- eligibility when the user has explicitly configured a hard filter.

Learned preferences derived from feedback may also influence Application Priority and ranking. However, learned preferences must never:

- increase or decrease Fit;
- silently become hard exclusions;
- override explicit user preferences or search configuration;
- convert an unknown preference into a negative signal;
- permanently suppress discovery without explicit user authorization.

For example, repeatedly rejecting opportunities in one industry may cause similar opportunities to receive lower Application Priority. It must not reduce their Fit Score when the user's Career Evidence strongly matches the role, and the system must not permanently stop discovering that industry unless the user explicitly changes the search configuration.

The governing principle is:

- Fit answers: “How well does this opportunity match my career evidence?”
- Preference answers: “Given what I want, how much attention should I give this opportunity?”
- These questions must remain separate.

### 9.26 Opportunity Context

Application Priority may incorporate factual company or hiring context discovered through Section 7 sources.

Examples include:

- technology expansion;
- announced transformation initiatives;
- AI investment;
- acquisitions;
- new technology leadership;
- organizational expansion.

These signals may help explain why an opportunity is timely.

The system must not speculate about undisclosed hiring motives.

### 9.27 Priority Calculation

Application Priority should be calculated by deterministic application logic using configurable inputs.

Conceptually:

```text
PriorityModel {
    model_version
    fit_weight
    freshness_weight
    network_weight
    compensation_weight
    location_weight
    user_preference_weight
    opportunity_context_weight
    thresholds
}
```

AI may interpret job information and generate structured signals.

AI should not independently determine the final Priority outside the scoring framework.

### 9.28 Fit and Priority Examples

#### Example A — Excellent Match, Fresh, Strong Network

Fit: 94

Confidence: HIGH

Posted: 5 hours ago

Network: 4 relevant connections

Compensation: Strong

Location: Preferred

Priority: IMMEDIATE

Fit is driven by career evidence.

Freshness, network, compensation, and location increase Priority.

#### Example B — Excellent Match, No Network

Fit: 94

Confidence: HIGH

Posted: 5 hours ago

Network: 0 connections

Compensation: Strong

Location: Preferred

Priority: HIGH

The absence of a network does not reduce Fit.

#### Example C — Weak Match, Strong Network

Fit: 57

Confidence: HIGH

Network: 12 connections

Priority: LOW

Connections must not transform a weak career match into a top recommendation.

#### Example D — Strong Apparent Match, Incomplete Information

Fit: 90

Confidence: LOW

Priority: MEDIUM

The system surfaces the opportunity but clearly explains what information is missing.

### 9.29 Explainability Requirement

Every recommendation must explain its result.

The user should never receive only:

- 87% Match

Instead:

- Fit: 87
- Confidence: HIGH

Why it fits:

- + Strong enterprise transformation alignment
- + Significant platform leadership experience
- + Executive stakeholder management
- + Portfolio governance experience

Concerns:

- - Role prefers deep healthcare experience
- - Limited direct evidence for that industry requirement

Why it matters now:

- + Posted today
- + Preferred Bay Area location

Network:

- + 3 first-degree connections at the company

### 9.30 Reason Codes

The system should generate structured reason codes in addition to natural-language explanations.

Examples:

- STRONG_TRANSFORMATION_MATCH
- STRONG_PLATFORM_MATCH
- EXECUTIVE_SCOPE_MATCH
- PORTFOLIO_LEADERSHIP_MATCH
- AI_TRANSFORMATION_MATCH

CAREER_DIRECTION_MATCH

INDUSTRY_GAP

TECHNICAL_DEPTH_GAP

SCOPE_CONCERN

COMPENSATION_CONCERN

LOCATION_CONCERN

FRESH_POSTING

STRONG_NETWORK

RELEVANT_CONNECTION

Reason codes enable:

- consistent explanations;
- analytics;
- testing;
- feedback learning;
- model evaluation;
- future personalization.

### 9.31 Score Contribution Records

For debugging and auditability, retain the contribution of each scoring component.

```text
ScoreContribution {
    job_analysis_id
    score_type
    component
    raw_value
    normalized_value
    weight
    weighted_value
    evidence_ids[]
    reason_codes[]
    scoring_model_version
}
```

This allows the platform to answer:

> Why did this job receive a Fit Score of 91 instead of 78?

without asking AI to reconstruct the scoring rationale afterward.

### 9.32 Explanation Generation

Natural-language explanations should be generated from structured analysis.

```text
STRUCTURED JOB ANALYSIS
        ↓
REQUIREMENT MATCHES
        ↓
CAREER EVIDENCE
        ↓
SCORE CONTRIBUTIONS
        ↓
REASON CODES
        ↓
NATURAL-LANGUAGE EXPLANATION
```

AI explains an already-grounded decision.

It must not invent reasoning after the score has been calculated.

### 9.33 Explanation Contract

Every recommended opportunity should answer four questions:

#### Why does it fit?

Identify the strongest evidence-backed career matches.

#### What concerns should I know about?

Identify meaningful gaps, uncertainties, and negative signals.

#### Why should I pay attention now?

Explain timing, freshness, compensation, location, company context, and other Priority factors.

#### Who do I know?

Show relevant network information separately.

This structure should remain consistent across opportunities.

### 9.34 Primary Opportunity Summary

The primary opportunity summary should use a compact structure such as:

- Fit: 91
- Confidence: HIGH
- Priority: HIGH
- Posted: 6h ago
- Network: 3 connections

followed by:

- Why it fits
- Concerns
- Why act now
- Who you know

The user should be able to understand the recommendation quickly and then expand into supporting evidence.

### 9.35 Evidence Drill-Down

Where practical, the interface should allow the user to inspect why a specific match was made.

Example:

Strong Match:

- Enterprise Transformation

Job Evidence:

- "Lead enterprise-wide technology modernization..."

Career Evidence:

- [Relevant Master Career Profile achievement]

Assessment:

- STRONG_MATCH

This provides transparency and helps identify errors in either job interpretation or Career Profile information.

### 9.36 User Correction

The user should be able to correct inaccurate assessments.

Examples:

- This is actually a strong capability of mine.

This requirement is not important to me.

The system inferred the role level incorrectly.

This is not the career direction I want.

The company mapping is wrong.

Corrections should update the appropriate underlying data rather than simply changing the displayed score.

### 9.37 Feedback and Scoring

User feedback should not immediately rewrite the scoring model after a single action.

Feedback should be stored as evidence for later preference learning.

Examples:

**INTERESTED**

NOT_INTERESTED

GREAT_MATCH

WRONG_LEVEL

WRONG_FUNCTION

WRONG_INDUSTRY

COMPENSATION_TOO_LOW

LOCATION_NOT_DESIRABLE

TOO_HANDS_ON

ALREADY_APPLIED

The feedback architecture is handled separately from the core scoring model.

### 9.38 Scoring Model Versioning

Every recommendation must record the scoring configuration that generated it.

```text
JobRecommendation {
    job_id
    career_profile_version
    search_preference_version
    fit_model_version
    priority_model_version
    fit_score
    recommendation_confidence
    application_priority
    generated_at
}
```

This makes historical recommendations reproducible.

### 9.39 Rescoring

An opportunity may need to be rescored when:

- Career Profile changes materially;
- Search Preferences change;
- relationship information changes;
- compensation becomes available;
- the job description changes materially;
- location or work model changes;
- scoring-model configuration changes.

Rescored opportunities should retain historical recommendation versions rather than silently overwriting all prior analysis.

### 9.40 AI Responsibilities

AI is appropriate for:

- interpreting job descriptions;
- extracting responsibilities;
- identifying capabilities;
- inferring role scope;
- semantic matching;
- identifying potential gaps;
- generating structured reason codes;
- producing evidence-backed explanations.

AI must not:

- invent career experience;
- invent compensation;
- invent organizational scope;
- invent relationship strength;
- fabricate missing job requirements;
- silently create hard filters;
- independently override deterministic scoring rules.

### 9.41 Deterministic Application Responsibilities

Application logic should own:

- hard-filter enforcement;
- weighted-score calculations;
- threshold evaluation;
- Fit computation from structured components;
- Priority calculation;
- notification thresholds;
- version tracking;
- persistence;
- auditability.

The architecture is therefore:

**AI**

```text
Interprets and structures evidence

        +

APPLICATION LOGIC
Calculates and enforces rules

        =

EXPLAINABLE RECOMMENDATION
```

### 9.42 Golden Evaluation Set

Before Fit and Priority scoring are considered production-ready, create a manually reviewed Golden Evaluation Set.

It should contain representative opportunities including:

- obvious excellent matches;
- good but imperfect matches;
- title matches with poor actual scope;
- unexpected-title strong matches;
- roles that are too junior;
- roles that are too hands-on;
- sales-heavy roles;
- industry-specific roles;
- high-network but low-Fit roles;
- strong-Fit roles with no network;
- ambiguous job descriptions.

For each opportunity, manually establish expected ranges or classifications for:

- Fit
- Confidence
- Priority
- Primary Positive Reasons
- Primary Concerns

Automated evaluation should compare system results against this set whenever matching or scoring logic changes.

### 9.43 Scoring Quality Metrics

Track metrics including:

- percentage of high-Fit jobs marked Interested;
- percentage of low-Fit jobs rejected;
- false-positive recommendation rate;
- missed-opportunity rate from manual review;
- score stability after repeated analysis;
- explanation/evidence consistency;
- scope-inference accuracy;
- career-direction classification accuracy.

The objective is not merely mathematical consistency.

The objective is:

> Does the system reliably surface opportunities the user considers genuinely worth reviewing?

### 9.44 Phase 1 Matching Principle

The Phase 1 matching system must preserve a strict separation between three questions:

**FIT**

"Is this a strong career match?"

**CONFIDENCE**

"How sure are we?"

**PRIORITY**

"How much attention should I give it right now?"

The final recommendation flow is:

```text
JOB
 ↓
STRUCTURED JOB ANALYSIS
 ↓
REQUIREMENT-TO-EVIDENCE MATCHING
 ↓
ROLE / SCOPE INFERENCE
 ↓
CAREER DIRECTION ANALYSIS
 ↓
NEGATIVE-FIT / GAP ANALYSIS
 ↓
FIT SCORE
 ↓
RECOMMENDATION CONFIDENCE
 ↓
TIMING + NETWORK + COMPENSATION
+ LOCATION + PREFERENCES + CONTEXT
 ↓
APPLICATION PRIORITY
 ↓
REASON CODES
 ↓
EVIDENCE-BACKED EXPLANATION
```

Every recommendation must therefore be traceable from the job requirement to Career Profile evidence, from that evidence to scoring components, and from those components to the final Fit, Confidence, and Application Priority.

## 10. User Feedback, Watch State and Learning

Section 10 defines how the system captures the user's reaction to opportunities and uses those reactions to improve future prioritization without allowing isolated feedback to distort the underlying Career Profile or Fit model.

The system must distinguish among:

- explicit user feedback;
- workflow state;
- watch state;
- learned preferences;
- Career Profile facts;
- explicit Search Preferences.

These are related but must remain separate.

### 10.1 Feedback Objectives

Feedback serves four purposes:

- Record what the user thinks about an opportunity.
- Explain why the user accepted or rejected the recommendation.
- Improve future ranking and prioritization.
- Identify systematic errors in matching, role classification, company interpretation, or Career Profile data.

Feedback must therefore capture more information than a simple thumbs-up or thumbs-down.

### 10.2 Opportunity Feedback Actions

Initial feedback actions should include:

**INTERESTED**

GREAT_MATCH

NOT_INTERESTED

**WATCH**

ALREADY_APPLIED

**ARCHIVE**

Where appropriate, an action should allow or require a reason.

### 10.3 Feedback Reason Codes

Initial reason codes should include:

- WRONG_LEVEL
- WRONG_FUNCTION
- WRONG_CAREER_DIRECTION
- WRONG_INDUSTRY
- WRONG_COMPANY_TYPE

TOO_HANDS_ON

TOO_TECHNICAL

TOO_NARROW

INSUFFICIENT_LEADERSHIP_SCOPE

SALES_HEAVY

COMPENSATION_TOO_LOW

LOCATION_NOT_DESIRABLE

WORK_MODEL_NOT_DESIRABLE

TRAVEL_TOO_HIGH

RELOCATION_REQUIRED

GOOD_TRANSFORMATION_SCOPE

GOOD_EXECUTIVE_SCOPE

GOOD_PLATFORM_SCOPE

GOOD_AI_SCOPE

GOOD_COMPANY

GOOD_COMPENSATION

GOOD_LOCATION

**OTHER**

Reason codes should be configurable and extensible.

### 10.4 Feedback Record

Conceptually:

```text
OpportunityFeedback {
    feedback_id
    user_id
    job_id
    action
    reason_codes[]
    comment?
    recommendation_version_id
    fit_score_at_feedback
    priority_at_feedback
    created_at
}
```

The recommendation version should be retained so the system knows exactly what the user saw when providing feedback.

### 10.5 Explicit Feedback vs. Learned Preference

The system must distinguish:

**EXPLICIT USER PREFERENCE**

from:

**LEARNED PREFERENCE**

An explicit preference is something the user intentionally configures.

Example:

- I do not want roles requiring relocation.

A learned preference is inferred from repeated behavior.

Example:

- User frequently rejects highly hands-on engineering leadership roles.

Learned preferences may influence ranking.

They must not silently become hard filters.

### 10.6 Feedback Learning Guardrail

A single feedback event must not materially rewrite the recommendation model.

For example:

- NOT_INTERESTED
- Reason: WRONG_INDUSTRY

on one healthcare opportunity must not cause the application to conclude:

- Never show healthcare companies again.

Preference learning should require repeated, consistent evidence.

### 10.7 Learned Preference Model

Conceptually:

```text
LearnedPreference {
    preference_id
    dimension
    value
    direction
    strength
    supporting_feedback_ids[]
    first_observed_at
    last_observed_at
    confidence
    active
}
```

Possible dimensions include:

- ROLE_FAMILY
- ROLE_SCOPE
**INDUSTRY**

COMPANY_TYPE

WORK_MODEL

**LOCATION**

**TRAVEL**

**COMPENSATION**

CAREER_DIRECTION

TECHNICAL_DEPTH

LEADERSHIP_SCOPE

### 10.8 Learned Preference Strength

Initial strength levels:

**WEAK**

**MODERATE**

**STRONG**

A preference becomes stronger only when supported by repeated behavior.

The system should also allow learned preferences to weaken over time when subsequent feedback contradicts them.

### 10.9 Feedback Must Not Rewrite Career Truth

User preference feedback must not alter factual Career Profile information.

For example:

- NOT_INTERESTED
- Reason: TOO_HANDS_ON

does not mean the user lacks technical experience.

It means the user does not currently prefer that type of role.

The system must preserve the distinction:

**CAREER PROFILE**

What the user has done

**SEARCH PREFERENCES**

What the user explicitly wants

**LEARNED PREFERENCES**

What behavior suggests the user tends to prefer

**FEEDBACK**

What the user thought about a particular opportunity

### 10.10 Feedback and Fit

Feedback must not directly alter the Fit Score of the job that received the feedback.

If the system calculates:

- Fit: 92

and the user selects:

- NOT_INTERESTED
- Reason: WRONG_CAREER_DIRECTION
- the historical Fit remains 92.

The feedback may indicate that the user's Career Direction preferences need refinement. Such preference refinement may affect future Application Priority, ranking, notification eligibility or urgency, and recommendation explanations, but it must not increase or decrease the underlying Fit Score.

Fit represents the evidence-based career match between an opportunity and the user's Career Evidence. Preference feedback represents what the user wants or does not want. These must remain separate.

A future Fit Score may change only when information relevant to the career match changes, such as:

- the user's underlying Career Evidence;
- the job's requirements, responsibilities, or scope;
- correction of inaccurate or incomplete evidence;
- resolution of previously unknown or ambiguous information; or
- an explicitly versioned change to the Fit Model itself.

Learned or explicit preferences must not be treated as Career Evidence and must not indirectly modify Fit.

The governing principle is:

- Feedback may change what the system prioritizes.
- Feedback must not rewrite what the user's career evidence demonstrates.

### 10.11 Feedback and Application Priority

Learned preferences may influence future Application Priority.

For example, repeated rejection of roles with heavy travel may gradually lower Priority for similar opportunities.

This effect must be:

- explainable;
- reversible;
- versioned;
- bounded.

The system should be able to explain:

> Priority was reduced because similar high-travel opportunities have repeatedly been marked Not Interested.

### 10.12 Recommendation Error Feedback

Some feedback indicates a system error rather than a preference.

Examples:

- ROLE_LEVEL_INCORRECT
- COMPANY_MAPPING_INCORRECT
- LOCATION_INCORRECT
- WORK_MODEL_INCORRECT
- JOB_ALREADY_CLOSED
- DUPLICATE_JOB
- MATCH_REASON_INCORRECT
- CAREER_EVIDENCE_INCORRECT

These should trigger correction workflows rather than preference learning.

### 10.13 Watch State

The system needs a state between Interested and Not Interested.

That state is:

**WATCH**

Watch means:

> This opportunity or company is potentially interesting, but I am not ready to pursue it yet.

### 10.14 Watch Targets

The user should be able to watch:

**JOB**

**COMPANY**

Future versions may support additional watch targets.

### 10.15 Watched Job Behavior

For a watched job, monitor:

- job status;
- description changes;
- compensation changes;
- location changes;
- work-model changes;
- reposting;
- closing or removal;
- relevant company developments.

Material changes may trigger a notification.

### 10.16 Watched Company Behavior

A watched company should receive elevated monitoring for:

- newly posted matching jobs;
- relevant leadership changes;
- transformation initiatives;
- AI initiatives;
- acquisitions;
- organizational expansion;
- other relevant company signals.

Watching a company does not increase the Fit Score of its jobs.

It affects monitoring and potentially Application Priority.

### 10.17 Watch Record

Conceptually:

```text
WatchItem {
    watch_id
    user_id
    target_type
    target_id
    reason?
    monitoring_priority
    created_at
    updated_at
    active
}
```

### 10.18 Opportunity Clusters

The system should recognize that different job titles may represent the same underlying career direction.

Example cluster:

- Enterprise Transformation Leadership

VP Technology Transformation

VP Enterprise Transformation

Head of Transformation

Senior Director Strategic Transformation

Executive Director Technology Strategy & Execution

Another cluster:

- Technology / Product Operations Leadership

VP Technology Operations

VP Product Operations

Head of Engineering Operations

VP Strategy & Operations

Senior Director Technology Operations

### 10.19 Opportunity Cluster Model

Conceptually:

```text
OpportunityCluster {
    cluster_id
    name
    role_family_ids[]
    title_patterns[]
    capability_patterns[]
    description
    enabled
}
```

Jobs may belong to more than one cluster when appropriate.

### 10.20 Cluster Learning

Feedback should be analyzed at both the individual-job level and cluster level.

If the user repeatedly marks jobs within one cluster as:

- GREAT_MATCH

the system may learn that the cluster deserves greater discovery or Priority emphasis.

If the user repeatedly rejects another cluster for the same reason, ranking may adjust accordingly.

The system must still avoid converting learned behavior into an invisible hard filter.

### 10.21 Feedback Analytics

The system should track:

- Interested rate;
- Great Match rate;
- Not Interested rate;
- most common rejection reasons;
- most common positive reasons;
- acceptance rate by role family;
- acceptance rate by Opportunity Cluster;
- acceptance rate by company type;
- acceptance rate by Fit range;
- acceptance rate by Priority level;
- recommendation-error rate.

These metrics help tune the matching system.

### 10.22 Feedback Re-Evaluation

When significant preference patterns emerge, the system may re-evaluate active opportunities.

Example:

Repeated Feedback:

- INSUFFICIENT_LEADERSHIP_SCOPE

Learned Preference:

- Strong preference for enterprise-level leadership scope

Action:

- Recalculate Priority for active opportunities

Historical scores and recommendations must remain available.

### 10.23 User Control Over Learned Preferences

The application should provide a simple view such as:

- What the system has learned about your preferences

Examples:

Strong preference:

- Enterprise transformation leadership

Moderate preference:

- Large organizational scope

Possible preference:

- AI transformation roles

Avoid tendency:

- Highly hands-on engineering roles

The user should be able to:

**CONFIRM**

**CORRECT**

**DISMISS**

**RESET**

a learned preference.

### 10.24 Phase 1 Feedback Principle

The learning loop is:

```text
DISCOVER
 ↓
ANALYZE
 ↓
FIT + CONFIDENCE + PRIORITY
 ↓
USER REVIEW
 ↓
FEEDBACK
 ↓
LEARNED PREFERENCE
 ↓
FUTURE PRIORITIZATION
```

The core guardrail is:

> Learn from behavior without confusing preference with career capability or silently eliminating opportunities.

## 11. Notifications and Executive Digest

Section 11 defines how the system communicates important opportunities and changes without overwhelming the user.

The notification system should answer:

> What requires my attention now?

The executive digest should answer:

> What changed since I last looked?

### 11.1 Notification Types

Phase 1 should support three primary delivery modes:

**IMMEDIATE ALERT**

**SCHEDULED DIGEST**

**IN-APP UPDATE**

Not every new job should generate an immediate notification.

### 11.2 Immediate Alerts

Immediate alerts are reserved for unusually actionable opportunities.

Initial eligibility may require:

**NEW OR MATERIALLY CHANGED JOB**

**AND**

FIT >= configured threshold

**AND**

APPLICATION PRIORITY >= configured threshold

**AND**

CONFIDENCE != LOW

Thresholds must remain configurable.

### 11.3 Immediate Alert Reasons

Examples include:

- Strong match posted recently

Strong match at watched company

Strong match with relevant network

High-priority job materially changed

Watched opportunity materially changed

Previously ambiguous opportunity now verified

The notification should explain why it was sent.

### 11.4 Immediate Alert Content

A compact alert might contain:

- VP Technology Transformation
- Company Name

Fit: 94

Confidence: HIGH

Priority: IMMEDIATE

Posted: 4h ago

Network: 3 relevant connections

Why now:

- Strong career match + fresh posting + relevant network

The user should be able to open the full opportunity analysis directly.

### 11.5 Notification Deduplication

The same opportunity must not repeatedly notify the user without a meaningful reason.

Conceptually:

```text
NotificationRecord {
    notification_id
    job_id
    job_version_id
    notification_type
    reason_codes[]
    sent_at
}
```

Before sending an alert, check whether an equivalent alert has already been sent for that job version and reason.

### 11.6 Re-Alert Conditions

A previously alerted opportunity may generate another alert only when something materially changes.

Examples:

- COMPENSATION_CHANGED
- LOCATION_CHANGED
- WORK_MODEL_CHANGED
- ROLE_SCOPE_CHANGED
- MATERIAL_JD_CHANGE
- JOB_REPOSTED
- PRIORITY_INCREASED
- NETWORK_ADVANTAGE_ADDED
- WATCHED_JOB_CHANGED

Minor formatting changes should not generate new notifications.

### 11.7 Notification Quiet Hours

The user should be able to configure quiet hours.

Conceptually:

```text
NotificationPolicy {
    immediate_alerts_enabled
    quiet_hours_start
    quiet_hours_end
    timezone
    minimum_fit
    minimum_priority
    minimum_confidence
    digest_enabled
}
```

During quiet hours, non-critical alerts should be queued for the next permitted delivery window.

### 11.8 Scheduled Executive Digest

The Executive Digest summarizes relevant changes from scheduled search runs.

The digest should not simply list every discovered job.

It should prioritize what deserves attention.

### 11.9 Digest Structure

Recommended structure:

**EXECUTIVE JOB INTELLIGENCE DIGEST**

1. Requires Your Attention

2. New Strong Matches

3. Watched Opportunities Changed

4. Companies Worth Watching

5. Other New Opportunities

6. Search Coverage / Health

### 11.10 Requires Your Attention

This section contains the most actionable opportunities.

Example:

- 3 opportunities require attention

1. VP Technology Transformation — Company A

```text
Fit 94 | High Confidence | Immediate Priority
Posted 4h ago | 3 relevant connections
```

2. Head of Product Operations — Company B

```text
Fit 92 | High Confidence | High Priority
Posted today
```

3. VP Strategic Programs — Company C

```text
Fit 90 | High Confidence | High Priority
Compensation updated
```

### 11.11 New Strong Matches

Show opportunities discovered since the previous digest that exceed configured Fit and Confidence thresholds.

Each should include:

- Company
- Title
- Fit
- Confidence
- Priority
- Posted / First Seen
- Location / Work Model
- Network Count
- Primary Match Reason

### 11.12 Watched Opportunity Changes

Summarize changes to watched jobs or companies.

Examples:

- Compensation range added

Job changed from Hybrid to Remote

Watched company posted a matching role

Job description materially changed

Watched role was reposted

Watched job appears closed

### 11.13 Companies Worth Watching

The digest may include companies with relevant strategic signals even when no suitable job currently exists.

Example:

- Company X

No matching opening currently.

Why watch:

- + Announced enterprise AI initiative
- + New technology leadership
- + Expanding Bay Area organization

These observations should be evidence-backed and sourced through the Section 7 intelligence pipeline.

### 11.14 Other New Opportunities

Lower-priority opportunities may appear in a secondary section rather than generating individual alerts.

This preserves discovery coverage without overwhelming the primary executive view.

### 11.15 Search Health in Digest

The digest should clearly disclose incomplete coverage.

Example:

- Search Coverage: PARTIAL

Company career sites: Complete

Job discovery sources: Complete

Professional signals: Partial

Company intelligence: Complete

A source failure must never be represented as:

- No jobs found.

when the source was not successfully searched.

### 11.16 Digest Timing

The initial scheduled searches are:

- 07:00 Pacific
- 12:00 Pacific
- 17:00 Pacific

Digest delivery does not necessarily need to occur after every search run.

Search cadence and notification cadence should remain separately configurable.

An initial implementation may support:

- Morning Digest
- Evening Digest
- Immediate High-Priority Alerts

while still performing all three scheduled searches.

### 11.17 In-App Executive View

The application home screen should function as a continuously updated executive digest.

It should answer:

- WHAT'S NEW?

WHAT CHANGED?

WHAT REQUIRES MY ATTENTION?

WHAT AM I WATCHING?

DID ALL SEARCHES RUN SUCCESSFULLY?

### 11.18 Home-Screen Summary

Example:

Since your last review:

12 new opportunities

3 high-priority matches

1 immediate opportunity

2 watched jobs changed

4 companies worth monitoring

Last Search: 12:00 PM

Status: SUCCESS

Next Search: 5:00 PM

If the search was partial:

- Last Search: 12:00 PM
- Status: PARTIAL

1 source failed.

Results may be incomplete.

### 11.19 Notification Preferences

The user should be able to configure:

- immediate alerts on/off;
- minimum Fit threshold;
- minimum Priority threshold;
- minimum Confidence;
- watched-job alerts;
- watched-company alerts;
- digest frequency;
- quiet hours;
- notification channels;
- whether lower-priority opportunities appear only in-app.

### 11.20 Notification Channels

The architecture should support replaceable notification adapters.

Conceptually:

- NotificationAdapter

Potential channels include:

- IN_APP
**EMAIL**

**PUSH**

Additional channels may be added later without changing recommendation logic.

### 11.21 Notification Evaluation Pipeline

Conceptually:

```text
SEARCH RUN COMPLETES
 ↓
NEW / CHANGED OPPORTUNITIES
 ↓
FIT + CONFIDENCE + PRIORITY
 ↓
WATCH STATE
 ↓
USER NOTIFICATION POLICY
 ↓
DEDUPLICATION CHECK
 ↓
QUIET-HOURS CHECK
 ↓
IMMEDIATE ALERT / DIGEST / IN-APP ONLY
```

### 11.22 Notification Failure Handling

Notification delivery failures must not affect the underlying recommendation or search data.

Track:

```text
NotificationDelivery {
    notification_id
    channel
    attempted_at
    delivered_at?
    status
    error?
    retry_count
}
```

Delivery may use bounded retries.

### 11.23 Notification Analytics

Track:

- immediate alerts generated;
- alerts opened;
- opportunities marked Interested from alerts;
- alerts dismissed;
- digest opens;
- opportunities reviewed from digest;
- duplicate alerts prevented;
- notifications suppressed by quiet hours;
- notification failures.

These metrics can help tune notification thresholds.

### 11.24 Notification Guardrails

The system must avoid:

- notifying on every discovered job;
- repeated alerts for the same unchanged opportunity;
- treating source failure as no opportunities;
- waking the user for low-priority changes;
- allowing network strength alone to trigger a high-priority alert;
- generating an urgent alert from a Low-Confidence recommendation without another explicit reason.

### 11.25 Phase 1 Notification Principle

The notification hierarchy should be:

**IMMEDIATE**

Only unusually actionable opportunities

**DIGEST**

Important new and changed information

**IN-APP**

Complete opportunity inventory

The goal is not maximum notification volume.

The goal is:

> Surface the right opportunity at the right time while preserving trust and minimizing noise.

## 12. User Experience, Screens and Executive Workflow

The Phase 1 user experience should be designed as an executive decision-support system, not as a traditional job board.

The primary interface must quickly answer:

- What is new?

What changed?

What deserves my attention?

Why is this opportunity relevant?

What am I watching?

Who do I know?

Did the searches run successfully?

The user should not need to browse hundreds of jobs to understand the market.

The application should organize discovered information into a prioritized executive workflow.

### 12.1 Phase 1 Navigation

The initial application navigation should include:

- Home
- Opportunities
- Companies
- Watchlist
- Connections
- Search Health
- Settings

The Home screen serves as the primary executive dashboard.

### 12.2 Home — Executive Dashboard

The Home screen answers:

> What requires my attention right now?

Recommended top-level structure:

**EXECUTIVE JOB INTELLIGENCE**

Since Your Last Review

12 New Opportunities

3 High Priority

1 Immediate

2 Watched Opportunities Changed

4 Companies Worth Watching

Last Search: 12:00 PM

Status: SUCCESS

Next Search: 5:00 PM

The dashboard should prioritize actionable information rather than total job volume.

### 12.3 Requires Your Attention

The first dashboard section should contain opportunities requiring immediate or high-priority review.

Example:

**REQUIRES YOUR ATTENTION**

VP Technology Transformation

Company A

Fit: 94

Confidence: HIGH

Priority: IMMEDIATE

Posted: 4h ago

Network: 3 relevant connections

Why it fits:

- Enterprise transformation + technology operations leadership

Why now:

- Fresh posting + strong network

Only a limited number of highly relevant opportunities should appear here.

### 12.4 New Strong Matches

The next section should show strong opportunities discovered since the user's previous review.

Each card should display enough information for rapid triage:

- Company
- Title

Fit

Confidence

Priority

Posted / First Seen

Location

Work Model

Compensation

Network

Primary Match Reason

Primary Concern

The user should not need to open every job to understand why it was recommended.

### 12.5 Opportunity Card

The standard opportunity card should use a consistent hierarchy.

Example:

- VP Technology Operations
- Company Name

Fit: 92 | Confidence: HIGH | Priority: HIGH

San Francisco, CA | Hybrid

320K + Bonus + Equity

Posted: 7h ago

First Seen: 5h ago

Network: 4 connections

Why it fits:

- Strong technology operations and enterprise transformation alignment

Concern:

- Role requires significant financial-services experience

Primary actions:

**VIEW DETAILS**

**INTERESTED**

**WATCH**

**NOT INTERESTED**

**ALREADY APPLIED**

### 12.6 Opportunity Detail Screen

The Opportunity Detail screen should provide the complete decision context for one job.

Recommended structure:

- 1. Opportunity Summary
- 2. Fit Analysis
- 3. Concerns and Gaps
- 4. Why Act Now
- 5. Network
- 6. Company Intelligence
- 7. Job Description
- 8. Source and Verification
- 9. History / Changes
- 10. User Actions

### 12.7 Opportunity Summary

The top of the page should show:

- Title
- Company
- Location
- Work Model

Fit

Confidence

Priority

Employer Posted Date

First-Seen Date

Compensation

Current Job Status

Canonical Source

Example:

- VP Enterprise Transformation
- Company Name

Fit: 94

Confidence: HIGH

Priority: IMMEDIATE

Posted: Today

First Seen: 8:07 AM

San Jose, CA

Hybrid

340K + Bonus + Equity

### 12.8 Fit Analysis

The Fit section should explain the overall score and its major components.

Example:

- FIT: 94

Role / Responsibility       96

Seniority / Scope           94

Capability                  95

Leadership                  96

Career Direction            93

Domain / Industry           82

Below the summary:

**WHY IT FITS**

+ Enterprise transformation leadership

+ Technology operations experience

+ Large-scale portfolio governance

+ Executive stakeholder management

+ Global organizational leadership

Where practical, each reason should support evidence drill-down.

### 12.9 Concerns and Gaps

Concerns must appear prominently rather than being hidden below positive recommendations.

Example:

**CONCERNS**

Industry Experience

Role strongly prefers financial-services experience.

Assessment:

- PARTIAL_MATCH

Evidence:

- Strong regulated-environment experience, but limited direct financial-services evidence.

The UI must distinguish:

**REAL GAP**

**MISSING INFORMATION**

**UNKNOWN**

**PREFERENCE CONCERN**

**HARD-FILTER CONFLICT**

### 12.10 Why Act Now

Application Priority factors should be shown separately from Fit.

Example:

**WHY ACT NOW**

+ Posted 6 hours ago

+ High Fit

+ Preferred Bay Area location

+ Compensation within preferred range

+ 3 relevant first-degree connections

+ Company recently announced technology transformation initiative

This prevents urgency or network factors from being confused with career qualification.

### 12.11 Network Section

Show relevant connections separately.

Example:

**WHO YOU KNOW**

4 first-degree connections

2 Technology Organization

1 Executive Leadership

1 Talent / Recruiting

Where relationship strength is known:

- Strong Relationship: 1
- Medium Relationship: 1
- Unknown: 2

Unknown relationship strength must remain explicitly unknown.

Phase 1 should provide network intelligence.

Outreach workflows belong to Phase 2.

### 12.12 Company Intelligence

The Opportunity Detail page should include a compact company context section.

Example:

**COMPANY INTELLIGENCE**

Company:

- Company Name

Industry:

- Enterprise Software

Stage / Size:

- Public / Large Enterprise

Relevant Signals:

- + Enterprise AI investment
- + Technology modernization program
- + Recent acquisition
- + New technology leadership

Why It Matters:

- The company's current initiatives appear relevant to the capabilities represented in the Master Career Profile.

All material intelligence should retain provenance.

### 12.13 Job Source and Verification

The user should be able to understand where the job came from.

Example:

**SOURCE**

Discovered:

- LinkedIn Jobs

Canonical Verification:

- Company Careers Site

Requisition:

- R123456

Employer Posted:

- October 4, 2026

First Seen:

- October 4, 2026 — 8:07 AM

Last Verified:

- October 4, 2026 — 12:03 PM

Status:

**ACTIVE**

### 12.14 Job History and Changes

The Opportunity Detail screen should show meaningful changes.

Example:

**JOB HISTORY**

Oct 4 — First discovered

Oct 4 — Verified on employer careers site

Oct 5 — Compensation range added

Oct 7 — Work model changed from Onsite to Hybrid

Oct 12 — Reposted

Only meaningful changes should be emphasized.

### 12.15 Opportunities Screen

The Opportunities screen contains the complete active opportunity inventory.

Default ordering should prioritize:

- Application Priority then Fit then Freshness

rather than simply sorting by posting date.

### 12.16 Opportunity Filters

Initial filters should include:

- Priority
- Fit Range
- Confidence
- Role Family
- Opportunity Cluster
- Company
- Industry
- Location
- Geographic Scope
- Work Model
- Compensation
- Posting Age
- Network Presence
- Watch State
- Feedback State
- Job Status

Filters should help exploration without replacing the recommendation engine.

### 12.17 Opportunity Views

Useful saved views may include:

- Requires Attention
- New Since Last Review
- High Fit
- Immediate Priority
- Watched
- Strong Network
- Remote
- Bay Area
- Recently Changed
- Already Applied
- Archived

### 12.18 Companies Screen

The Companies screen represents the Target Company Universe.

It should answer:

> Which companies are strategically relevant to my career, whether or not they have a matching opening today?

Possible company states:

**MATCHING JOBS AVAILABLE**

**WATCHING**

**STRATEGICALLY RELEVANT**

**NO CURRENT MATCH**

**LOW RELEVANCE**

### 12.19 Company Card

Example:

- Company Name

Technology / AI Infrastructure

Monitoring Priority: HIGH

Matching Jobs: 2

High-Priority Jobs: 1

Connections: 7

Relevant Signals:

- + AI expansion
- + Platform modernization
- + New technology leadership

### 12.20 Company Detail Screen

Recommended sections:

- Company Overview
- Current Matching Opportunities
- Relevant Company Signals
- Network
- Opportunity History
- Monitoring Status
- Sources

The user should be able to select:

**WATCH COMPANY**

from this screen.

### 12.21 No Current Opening State

A company should remain useful even when no matching role exists.

Example:

- Company Name

No suitable opening currently.

Why this company remains relevant:

+ Significant AI investment

+ Enterprise transformation underway

+ Bay Area technology organization

+ 5 first-degree connections

Monitoring Status:

**WATCHING**

This supports the longer-term Phase 3 vision without requiring Phase 3 functionality yet.

### 12.22 Watchlist Screen

The Watchlist consolidates watched:

- Jobs
- Companies
- Role Families

The default view should emphasize changes.

Example:

**WATCHLIST**

2 Watched Jobs Changed

1 Watched Company Posted a Matching Role

3 Watched Companies Have New Signals

### 12.23 Connections Screen

The Connections screen provides the local network intelligence imported through the Network Data Adapter.

Top-level summary:

- LinkedIn Connections

Last Refreshed:

- September 28, 2026

Total Imported:

- 2,486

Companies Represented:

- 614

Connections at Active Target Companies:

- 137

Values above are illustrative only.

### 12.24 Import LinkedIn Connections

The Connections screen should include:

**IMPORT LINKEDIN CONNECTIONS**

Workflow:

```text
Upload
 ↓
Parse
 ↓
Validate
 ↓
Preview
 ↓
Normalize Companies
 ↓
Resolve Ambiguities
 ↓
Commit Import
 ↓
Recalculate Network Signals
 ↓
Recalculate Application Priority
```

### 12.25 Import Preview

Before committing an import, show:

- Valid Connections
- Duplicate Connections
- New Connections
- Updated Connections
- Unresolved Companies
- Rejected Records

The user should be able to resolve important company ambiguities before final import.

### 12.26 Connection Search

The user should be able to search connections by:

- Name
- Company
- Position
- Normalized Company
- Relationship Strength

This screen is primarily for validating and understanding network data in Phase 1.

Full outreach management belongs to Phase 2.

### 12.27 Search Health Screen

Search Health provides operational transparency.

Its primary purpose is to answer:

> Did the system actually search what it was supposed to search?

This is important because:

**NO JOBS FOUND**

is materially different from:

**SEARCH SOURCE FAILED**

### 12.28 Search Health Summary

Example:

**SEARCH HEALTH**

Last Scheduled Run:

- 12:00 PM

Status:

**PARTIAL**

New Opportunities:

- 7

Changed Opportunities:

- 3

Expired:

- 2

Expected Sources:

- 14

Successful:

- 13

Failed:

- 1

Next Search:

- 5:00 PM

### 12.29 Search Run History

Show recent runs:

- 07:00 AM   SUCCESS
- 12:00 PM   PARTIAL
- 05:00 PM   SUCCESS

Selecting a run should display:

- Run Type
- Start Time
- Completion Time
- Search Plan Version
- Taxonomy Version
- Geographic Scope Version

Expected Sources

Successful Sources

Failed Sources

New Jobs

Changed Jobs

Expired Jobs

Unresolved Jobs

### 12.30 Source Health

Each source or adapter should have visible operational state.

Example:

- Company Career Sites       HEALTHY
- Job Discovery Source A     HEALTHY
- Job Discovery Source B     DEGRADED
- Professional Signals       HEALTHY
- Company Intelligence       HEALTHY
- Network Data               USER REFRESH REQUIRED

Possible states:

**HEALTHY**

**DEGRADED**

**FAILED**

**DISABLED**

NOT_CONFIGURED

USER_ACTION_REQUIRED

### 12.31 Source Failure Detail

For failed sources, display enough information to understand the impact.

Example:

Source:

- Job Discovery Source B

Status:

**FAILED**

Last Successful Search:

- Yesterday 5:00 PM

Current Run:

- 12:00 PM

Impact:

- Results from this source may be incomplete.

Retry:

- Scheduled

Do not expose unnecessary low-level infrastructure errors in the primary executive interface.

Detailed diagnostics may be available in an administrative or developer view.

### 12.32 Search Coverage

Search Health should also show whether configured search scopes were covered.

Example:

**SEARCH COVERAGE**

Bay Area                    COMPLETE

United States Remote        COMPLETE

Technology Operations       COMPLETE

Product Operations          COMPLETE

Enterprise Transformation   COMPLETE

AI Transformation           PARTIAL

This is more useful than merely showing whether a background process ran.

### 12.33 Search Now

The UI should support an explicit:

**SEARCH NOW**

action.

Optional targeted search choices may include:

- Search Everything

Search a Geographic Scope

Search a Role Family

Search a Company

Search New Configuration Only

The resulting run should use the ON_DEMAND SearchRun type defined in Section 5.

### 12.34 Active Search State

While an on-demand search is running, the UI should show truthful status such as:

**SEARCH IN PROGRESS**

Sources Completed: 8 / 14

New Opportunities: 3

The application must not report completion until required downstream processing has reached its defined terminal state.

### 12.35 Settings Screen

Settings should initially contain:

- Career Profile

Search Taxonomy

Geographic Scopes

Search Preferences

Compensation Preferences

Search Schedule

Notification Preferences

LinkedIn Connection Import

Learned Preferences

Source Configuration

Privacy / Data

Settings should expose user-configurable policy without requiring code changes.

### 12.36 Search Taxonomy Settings

The user should be able to inspect and modify:

- Role Families
- Titles
- Title Variations
- Capability Terms
- Scope Signals
- Negative Signals
- Enabled / Disabled Terms

Changes should create a new taxonomy version.

### 12.37 Geographic Scope Settings

The user should be able to:

- Add Scope
- Edit Scope
- Enable / Disable Scope
- Set Work Models
- Set Relocation Preference
- Set Priority

Example:

- San Francisco Bay Area       ENABLED
- United States Remote         ENABLED
- Seattle Metro                DISABLED

### 12.38 Search Schedule Settings

Display:

- Morning Search     7:00 AM
- Midday Search     12:00 PM
- Evening Search     5:00 PM

Timezone:

- America/Los_Angeles

Reconciliation Window:

- 72 Hours

The user should be able to modify the schedule without altering historical SearchRun data.

### 12.39 Learned Preferences Screen

The application should expose what it believes it has learned.

Example:

**WHAT THE SYSTEM HAS LEARNED**

Strong Preference

Enterprise transformation leadership

Moderate Preference

Large organizational scope

Possible Preference

AI transformation

Avoid Tendency

Highly hands-on engineering roles

Available actions:

**CONFIRM**

**CORRECT**

**DISMISS**

**RESET**

The system should never hide significant learned ranking behavior from the user.

### 12.40 Recommendation Transparency

Any screen displaying Fit or Priority should provide access to the explanation behind the value.

The UI should never create an unexplained:

- 94% MATCH

without allowing the user to understand:

- What matched
- What did not match
- What evidence was used
- What remains unknown
- What affected Priority

### 12.41 Unknown Data Presentation

Unknown information must be displayed as unknown.

Examples:

- Compensation: Not Published

Relationship Strength: Unknown

Reporting Structure: Not Specified

Travel: Not Specified

The UI must not replace missing information with AI-generated assumptions.

### 12.42 Source Provenance

Important factual information should allow source inspection where practical.

Examples:

```text
Job Description
→ Employer Careers Site

Compensation
→ Employer Posting

Company AI Initiative
→ Company Announcement

Connection
→ LinkedIn Connections Import
```

This increases trust and simplifies debugging.

### 12.43 Responsive Information Hierarchy

The interface should optimize for rapid executive review.

The order should generally be:

```text
DECISION
 ↓
REASON
 ↓
EVIDENCE
 ↓
DETAIL
```

not:

```text
RAW DATA
 ↓
MORE RAW DATA
 ↓
USER FIGURES OUT WHAT MATTERS
```

### 12.44 Phase 1 Workflow

The primary user workflow should be:

```text
OPEN HOME
 ↓
REVIEW WHAT REQUIRES ATTENTION
 ↓
OPEN STRONG OPPORTUNITY
 ↓
UNDERSTAND FIT + CONCERNS + WHY NOW
 ↓
REVIEW NETWORK
 ↓
```

SELECT:

**INTERESTED**

**WATCH**

**NOT INTERESTED**

```text
ALREADY APPLIED

 ↓
SYSTEM RECORDS FEEDBACK
 ↓
RETURN TO PRIORITIZED OPPORTUNITIES
```

This workflow should take minutes rather than requiring extended job-board browsing.

### 12.45 Interested State

Selecting:

**INTERESTED**

in Phase 1 records the user's intent and elevates the opportunity into the future pursuit workflow.

Phase 1 does not automatically:

- Apply
- Modify Resume
- Contact Connections
- Send Messages
- Submit Forms

Those actions belong to Phase 2.

### 12.46 Already Applied State

Selecting:

**ALREADY APPLIED**

should remove the opportunity from normal discovery recommendations while retaining it in history.

This state becomes an input to the Phase 2 application pipeline.

### 12.47 Archived Opportunities

Archived opportunities remain historically searchable.

Archive must not mean delete.

The system should retain:

- Job Record
- Job Versions
- Recommendation History
- Feedback
- Source History
- Relevant User Actions

subject to retention policy.

### 12.48 Empty States

Empty states should distinguish among different conditions.

Correct examples:

- No new high-priority opportunities since your last review.

No matching jobs currently found at this watched company.

Search results may be incomplete because two sources failed.

Incorrect:

- No jobs available.

when the system does not actually know that.

### 12.49 Error States

Errors should explain:

- What failed
- Whether results are incomplete
- Whether existing data remains available
- Whether retry is automatic
- Whether user action is required

Operational failure should not erase previously discovered opportunities.

### 12.50 Phase 1 UX Guardrails

The interface must not:

- behave like an undifferentiated job feed;
- rank primarily by title keyword similarity;
- hide material concerns;
- mix network strength into Fit;
- present missing data as fact;
- imply complete market coverage after a partial search;
- send the user through unnecessary screens to understand a recommendation;
- silently learn permanent exclusions;
- perform Phase 2 actions without explicit future implementation and user control.

### 12.51 Phase 1 UX Principle

The Phase 1 interface should follow this hierarchy:

**HOME**

"What needs my attention?"

**OPPORTUNITY**

"Why does this fit?"

**CONFIDENCE**

"How sure are we?"

**PRIORITY**

"Why now?"

**NETWORK**

"Who do I know?"

**COMPANY**

"Why is this company relevant?"

**WATCH**

"What changed?"

**SEARCH HEALTH**

"Did the system actually look?"

**SETTINGS**

"What should the system search for and how should it behave?"

The product should feel less like a job board and more like a personal executive career-intelligence console.

## 13. Company Intelligence and Core Data Model

Section 13 defines the canonical data model that supports company intelligence, job discovery, source provenance, job history, matching, scoring, network intelligence, feedback, watch state, and notifications.

The data model must preserve enough history and provenance to answer:

- What companies are relevant?
- What jobs currently exist?
- Where was each job discovered?
- Has the employer verified the job?
- When was it first seen?
- What changed?
- Has the job disappeared or been reposted?
- Why was the opportunity recommended?
- What information supported the recommendation?
- What did the user do with it?
- Can the system reproduce the recommendation later?

The canonical database must represent entities, observations, versions, analysis, and user state separately.

### 13.1 Core Data Domains

Phase 1 data is organized into the following domains:

**USER AND CAREER**

```text
User
MasterCareerProfile
CareerExperience
CareerAchievement
CareerCapability
SearchPreference
GeographicScope
```

**COMPANY INTELLIGENCE**

```text
Company
CompanyAlias
CompanySignal
CompanyMonitoringState
```

**JOB INTELLIGENCE**

```text
Job
JobVersion
JobSourceObservation
JobChange
JobAnalysis
```

**SEARCH OPERATIONS**

```text
SearchRun
SearchPlan
SourceExecution
SourceObservation
```

**MATCHING**

```text
RequirementMatch
ScoreContribution
JobRecommendation
RecommendationExplanation
```

**NETWORK**

```text
Connection
ConnectionImportBatch
CompanyConnectionMatch
```

**USER LEARNING**

```text
OpportunityFeedback
LearnedPreference
WatchItem
OpportunityCluster
```

**DELIVERY**

```text
NotificationRecord
NotificationDelivery
```

These domains should use stable identifiers and explicit relationships rather than duplicating data across features.

### 13.2 Company as a Canonical Entity

A company must exist independently from jobs discovered at that company.

Conceptually:

```text
Company {
    company_id
    canonical_name
    normalized_name
    website_domain?
    industry?
    company_type?
    ownership_type?
    headquarters_location?
    bay_area_presence?
    employee_size_range?
    stage?
    description?
    monitoring_priority
    first_seen_at
    last_updated_at
    active
}
```

The Company record represents the canonical organization used throughout the application.

### 13.3 Company Aliases

Companies may appear under multiple names.

Examples:

- Google
- Google LLC
- Alphabet
- Alphabet Inc.

Meta

Meta Platforms

Meta Platforms, Inc.

The system must maintain aliases separately.

```text
CompanyAlias {
    company_alias_id
    company_id
    alias
    normalized_alias
    source?
    confidence
    verified
}
```

Aliases support:

- job deduplication;
- connection matching;
- company intelligence;
- employer-site verification;
- source normalization.

### 13.4 Company Resolution

When an incoming source references a company, the system should attempt:

```text
EXACT CANONICAL MATCH
        ↓
EXACT ALIAS MATCH
        ↓
DOMAIN MATCH
        ↓
NORMALIZED NAME MATCH
        ↓
FUZZY / SEMANTIC MATCH
        ↓
MANUAL REVIEW
```

Automatic fuzzy matches should require an appropriate confidence threshold.

Low-confidence mappings must not silently merge companies.

### 13.5 Company Monitoring Priority

Companies may have monitoring priorities such as:

**HIGH**

**NORMAL**

**LOW**

Monitoring priority may affect:

- career-site search frequency;
- intelligence collection frequency;
- reconciliation priority;
- watched-company processing.

Monitoring priority must not affect Job Fit.

### 13.6 Company Intelligence

Company Intelligence provides factual context explaining why a company may be relevant to the user's career.

Relevant intelligence may include:

- enterprise transformation;
- technology modernization;
- AI investment;
- platform investment;
- cloud modernization;
- acquisitions;
- funding;
- expansion;
- new technology leadership;
- security or regulatory transformation;
- organizational changes;
- technology operating-model changes.

The system should store individual signals rather than one opaque AI-generated company assessment.

### 13.7 Company Signal Model

Conceptually:

```text
CompanySignal {
    company_signal_id
    company_id
    signal_type
    headline?
    summary
    event_date?
    discovered_at
    source_observation_id
    relevance_score?
    confidence
    active
}
```

Possible signal types:

- AI_INITIATIVE
- TECHNOLOGY_TRANSFORMATION
- DIGITAL_TRANSFORMATION
- CLOUD_MODERNIZATION
- PLATFORM_INVESTMENT

**ACQUISITION**

**FUNDING**

**EXPANSION**

NEW_CIO

NEW_CTO

NEW_CISO

NEW_TECHNOLOGY_LEADERSHIP

ORGANIZATIONAL_CHANGE

TECHNOLOGY_HIRING_EXPANSION

SECURITY_TRANSFORMATION

REGULATORY_CHANGE

**OTHER**

Signal types should remain extensible.

### 13.8 Company Signal Provenance

Every Company Signal must retain source provenance.

The system must be able to answer:

- What is the signal?

When did the event occur?

When did we discover it?

Where did the information come from?

How confident are we?

Why is it relevant?

AI-generated summaries must remain linked to the underlying source observation.

### 13.9 Company Intelligence Snapshot

The UI may generate a current company snapshot from canonical data.

Example:

**COMPANY INTELLIGENCE**

Company:

- Example Corp

Industry:

- Enterprise Software

Relevant Signals:

- + Enterprise AI initiative
- + Cloud modernization program
- + New CTO
- + Bay Area technology expansion

Matching Jobs:

- 2

High-Priority Jobs:

- 1

Connections:

- 6

Monitoring Priority:

**HIGH**

This snapshot is a presentation layer.

The underlying signals remain independently stored.

### 13.10 Company Without Current Jobs

A company may remain relevant even when no matching opportunity currently exists.

The system must support:

- Company Relevance: HIGH
- Current Matching Jobs: 0
- Monitoring Status: ACTIVE

This allows the platform to maintain a living Target Company Universe rather than creating companies only when jobs appear.

### 13.11 Canonical Job Entity

A Job represents one logical employment opportunity.

Conceptually:

```text
Job {
    job_id
    company_id
    canonical_title
    normalized_title
    role_family_id?
    opportunity_cluster_ids[]
    canonical_url?
    employer_requisition_id?
    current_status
    employer_posted_at?
    first_seen_at
    last_seen_at
    last_verified_at?
    last_changed_at?
    current_job_version_id?
    created_at
    updated_at
}
```

The Job entity should remain stable while details about the posting change over time.

### 13.12 Job Identity

The system should attempt to identify the same logical job across multiple sources.

Useful identity signals include:

- Company
- Employer Requisition ID
- Canonical Employer URL
- Normalized Title
- Location
- Job Description Fingerprint
- ATS Identifier
- Source Posting Identifier

Employer requisition ID and canonical employer URL should receive strong preference when available.

### 13.13 Job Version

Job content must be versioned.

```text
JobVersion {
    job_version_id
    job_id
    title
    description
    locations[]
    work_model?
    compensation_min?
    compensation_max?
    compensation_currency?
    compensation_period?
    bonus_information?
    equity_information?
    employment_type?
    travel_requirement?
    role_scope_data?
    content_fingerprint
    effective_from
    effective_to?
    created_at
}
```

A new JobVersion should be created only for meaningful changes.

### 13.14 Meaningful Job Changes

Changes that may create a new JobVersion include:

- TITLE_CHANGED
- DESCRIPTION_MATERIALLY_CHANGED

COMPENSATION_CHANGED

LOCATION_CHANGED

WORK_MODEL_CHANGED

ROLE_SCOPE_CHANGED

TRAVEL_REQUIREMENT_CHANGED

EMPLOYMENT_TYPE_CHANGED

Formatting, punctuation, tracking parameters, and insignificant wording changes should not create unnecessary versions.

### 13.15 Job Source Observation

A source observation records what a particular source reported about a job at a particular time.

```text
JobSourceObservation {
    job_source_observation_id
    job_id?
    source_id
    source_job_id?
    source_url?
    observed_company_name
    observed_title
    observed_location?
    observed_posted_at?
    raw_content_reference?
    content_fingerprint?
    discovered_at
    observed_at
    source_confidence
    canonical_candidate
}
```

Source observations must not be overwritten merely because a canonical record exists.

They provide discovery and provenance history.

### 13.16 Discovery Source vs. Canonical Source

The system must distinguish:

**DISCOVERY SOURCE**

from:

**CANONICAL SOURCE**

Example:

Discovered:

- Job Aggregator

Verified:

- Employer Careers Site

Both observations should remain stored.

This allows the system to measure which source discovered an opportunity first while still treating the employer posting as authoritative.

### 13.17 Canonical Source Hierarchy

Initial hierarchy:

- 1. Employer Career Site / Employer ATS
- 2. Other Verified Employer-Controlled Source
- 3. Professional Job Platform
- 4. Job Aggregator
- 5. Other Discovery Source

This hierarchy may vary by data field.

For example, an employer career site may be canonical for job status while another source may provide useful discovery timing.

### 13.18 Source Observation

The generic SourceObservation entity supports provenance beyond job postings.

Conceptually:

```text
SourceObservation {
    source_observation_id
    source_id
    observation_type
    external_id?
    source_url?
    retrieved_at
    published_at?
    content_reference?
    content_fingerprint?
    confidence
    metadata
}
```

Possible observation types:

- JOB_POSTING
- COMPANY_NEWS
- PRESS_RELEASE
- REGULATORY_FILING
- PROFESSIONAL_SIGNAL
- HIRING_SIGNAL
- LEADERSHIP_CHANGE
**OTHER**

### 13.19 Source Entity

Each external source should have a canonical configuration.

```text
Source {
    source_id
    name
    source_class
    adapter_type
    canonical_authority_level?
    enabled
    created_at
    updated_at
}
```

Source classes correspond to Section 7:

- COMPANY_CAREER
- JOB_DISCOVERY
- PROFESSIONAL_SOCIAL
- COMPANY_MARKET_INTELLIGENCE

Network data is not modeled as a fifth external source class. User-provided professional network data, including LinkedIn first-degree connection exports, is represented separately as Network Intelligence through `ConnectionImportBatch` and related connection entities. Network Intelligence may contribute to Application Priority, “Why Now” explanations, and outreach context, but it must never alter the underlying Job Fit Score.

### 13.20 Job State Model

Each Job must have an explicit lifecycle state.

Initial states:

**ACTIVE**

**EXPIRED**

**REMOVED**

**CLOSED**

**UNRESOLVED**

**UNKNOWN**

Discovery classification remains separate from lifecycle status.

For example:

Discovery Classification:

- NEW_POSTING

Job Status:

**ACTIVE**

### 13.21 Discovery Classification

When a job is encountered during a SearchRun, classify the observation as:

- NEW_POSTING
- NEWLY_DISCOVERED_EXISTING_POSTING
- PREVIOUSLY_SEEN
- MATERIALLY_CHANGED
**REPOSTED**

EXPIRED_OR_REMOVED

**UNRESOLVED**

These classifications were defined in Section 5 and should be persisted where operationally useful.

### 13.22 New Posting

NEW_POSTING means the available evidence indicates the opportunity was recently posted and the application has not previously seen it.

This should generally require reasonable alignment between:

- employer_posted_at

and:

- first_seen_at

The system should avoid claiming that a job is newly posted when it merely discovered an older posting for the first time.

### 13.23 Newly Discovered Existing Posting

Use:

- NEWLY_DISCOVERED_EXISTING_POSTING

when the system first encounters a job that appears to have existed before the current discovery window.

Example:

Employer Posted:

- September 27

First Seen:

- October 4

This distinction is important for urgency and search-quality measurement.

### 13.24 Reposted Jobs

A job may be classified as:

**REPOSTED**

when a previously removed, closed, or aged posting appears again with sufficient evidence that the employer has renewed the opportunity.

The system should avoid creating a completely unrelated new Job merely because the same role was reposted.

Where identity is uncertain, the system may create a new Job linked through a relationship such as:

- possible_repost_of_job_id

rather than forcing an incorrect merge.

### 13.25 Expiration and Removal

A job should not become expired based solely on one temporary source failure.

Expiration may consider:

- canonical employer posting removed;
- explicit closed status;
- repeated verification failure;
- ATS status;
- source-specific expiration evidence.

The system should preserve the last known state and verification history.

### 13.26 Job Change Record

Meaningful changes should be recorded explicitly.

```text
JobChange {
    job_change_id
    job_id
    previous_job_version_id
    new_job_version_id
    change_types[]
    detected_at
    source_observation_ids[]
    material
}
```

This record supports:

- user-visible job history;
- watched-job alerts;
- re-scoring;
- notification decisions.

### 13.27 SearchRun Relationship

All discovery activity should be traceable to a SearchRun.

```text
SearchRun
    ↓
SearchPlan
    ↓
SourceExecution
    ↓
SourceObservation
    ↓
Job / Company Resolution
```

A job may be observed by multiple SearchRuns and multiple sources.

The canonical Job should not be duplicated for each run.

### 13.28 SearchPlan

Conceptually:

```text
SearchPlan {
    search_plan_id
    search_run_id
    taxonomy_version
    geographic_scope_version
    role_family_ids[]
    geographic_scope_ids[]
    source_ids[]
    generated_at
}
```

The SearchPlan represents intended coverage for that run.

### 13.29 Source Execution

Each planned source execution should be independently tracked.

```text
SourceExecution {
    source_execution_id
    search_run_id
    source_id
    scope_reference?
    started_at
    completed_at?
    status
    retry_count
    observations_created
    error_category?
    error_reference?
}
```

Possible states:

**QUEUED**

**RUNNING**

**SUCCESS**

**PARTIAL**

**FAILED**

**SKIPPED**

This supports the Search Health interface defined in Section 12.

### 13.30 Job Analysis Entity

Structured AI interpretation of a JobVersion must be persisted separately from the raw JobVersion.

```text
JobAnalysis {
    job_analysis_id
    job_id
    job_version_id
    analysis_model_version
    inferred_role_family
    inferred_seniority
    inferred_scope
    primary_responsibilities[]
    required_capabilities[]
    preferred_capabilities[]
    leadership_requirements[]
    technical_requirements[]
    domain_requirements[]
    positive_scope_signals[]
    negative_signals[]
    ambiguities[]
    missing_information[]
    analysis_confidence
    created_at
}
```

A new JobVersion may trigger a new JobAnalysis.

### 13.31 Requirement Entity

Important extracted requirements should have stable structured records.

```text
JobRequirement {
    job_requirement_id
    job_analysis_id
    requirement_type
    requirement_text
    importance
    requirement_status
    evidence_reference?
    created_at
}
```

Possible requirement statuses:

**REQUIRED**

**PREFERRED**

**CONTEXTUAL**

**INFERRED**

**UNKNOWN**

### 13.32 Requirement Match

The relationship between Job Requirements and Career Profile evidence must be persisted.

```text
RequirementMatch {
    requirement_match_id
    job_requirement_id
    career_profile_version
    matched_capability_ids[]
    career_evidence_ids[]
    match_strength
    evidence_strength
    gap_type?
    explanation
}
```

This is the core traceability relationship used by Section 9.

### 13.33 Recommendation Entity

A recommendation is a versioned evaluation of one Job against a specific version of the user's career and preferences.

```text
JobRecommendation {
    recommendation_id
    job_id
    job_version_id
    job_analysis_id
    career_profile_version
    search_preference_version
    fit_model_version
    priority_model_version
    fit_score
    confidence_level
    application_priority
    generated_at
}
```

A new recommendation should be generated when material inputs change.

### 13.34 Recommendation Reason

Structured reasons should be persisted separately from natural-language explanation.

```text
RecommendationReason {
    recommendation_reason_id
    recommendation_id
    reason_code
    reason_type
    score_component?
    evidence_ids[]
    display_order
}
```

Possible reason types:

**POSITIVE**

**CONCERN**

**UNKNOWN**

**PRIORITY**

**NETWORK**

### 13.35 Recommendation Explanation

Natural-language explanation should be treated as generated presentation content.

```text
RecommendationExplanation {
    explanation_id
    recommendation_id
    explanation_version
    why_it_fits
    concerns
    why_now
    network_summary
    generated_at
}
```

Structured evidence and reason codes remain the authoritative explanation basis.

### 13.36 Network Relationships

Connections should resolve to canonical companies.

```text
Connection
    ↓
Company Resolution
    ↓
Company
    ↓
Job
```

This allows network information to be reused across all jobs at the company.

### 13.37 Company Connection Match

Conceptually:

```text
CompanyConnectionMatch {
    company_connection_match_id
    connection_id
    company_id
    match_method
    confidence
    verified
}
```

Possible match methods:

**EXACT**

**ALIAS**

**DOMAIN**

**NORMALIZED**

**FUZZY**

**MANUAL**

### 13.38 User State Must Remain Separate from Job State

The employer's job state and the user's relationship with the job are different concepts.

Example:

Job Status:

**ACTIVE**

User State:

**WATCH**

or:

Job Status:

**ACTIVE**

User State:

- ALREADY_APPLIED

Do not overload the Job entity with user-specific workflow state.

### 13.39 User Opportunity State

Conceptually:

```text
UserOpportunityState {
    user_id
    job_id
    state
    first_reviewed_at?
    last_reviewed_at?
    updated_at
}
```

Possible initial states:

**UNREVIEWED**

**INTERESTED**

**WATCH**

NOT_INTERESTED

ALREADY_APPLIED

**ARCHIVED**

Feedback records remain separate so the system retains why the state changed.

### 13.40 Temporal Data Requirements

The system should preserve important timestamps rather than relying on one generic updated timestamp.

For Jobs:

- employer_posted_at first_seen_at last_seen_at last_verified_at last_changed_at

For Company Signals:

- event_date published_at discovered_at

For Sources:

- retrieved_at

For Recommendations:

- generated_at

These distinctions are required for freshness, urgency, provenance, reconciliation, and auditability.

### 13.41 Time Storage

Persist timestamps in UTC where practical.

Also retain the configured timezone needed for user-facing scheduling and display.

The Phase 1 default user timezone is configured as:

- America/Los_Angeles

Timezone configuration must not be hard-coded into the data model.

### 13.42 Stable Identifiers

Canonical entities should use application-generated stable identifiers.

Examples:

- company_id job_id connection_id search_run_id recommendation_id

External identifiers such as employer requisition numbers should be stored as attributes or source identifiers rather than used as the sole internal primary key.

### 13.43 Idempotency and Uniqueness

Database constraints and application logic should prevent duplicate records during retries.

Important uniqueness candidates include:

- Source + External Source ID

Company + Employer Requisition ID

Job + Content Fingerprint

SearchRun + Planned Source Execution

Recommendation + Input Version Combination

Notification + Job Version + Notification Type + Reason

Exact database constraints should be finalized during implementation based on source behavior.

### 13.44 Content Fingerprints

Fingerprints should support:

- duplicate detection;
- change detection;
- idempotent processing.

Potential fingerprint inputs include:

- Normalized Company
- Normalized Title
- Normalized Location
- Employer Requisition
- Normalized Job Description

Raw HTML, tracking parameters, formatting, and irrelevant page elements should not cause false job changes.

### 13.45 Raw vs. Normalized Data

Where useful, retain both:

**RAW SOURCE VALUE**

and:

**NORMALIZED CANONICAL VALUE**

Example:

Observed Company:

- Meta Platforms, Inc.

Canonical Company:

- Meta

This supports debugging and future normalization improvements.

### 13.46 Provenance Principle

Material facts should be traceable to their origin.

Conceptually:

```text
FACT
 ↓
SOURCE OBSERVATION
 ↓
SOURCE
 ↓
RETRIEVAL TIME
```

AI-generated interpretations should add another layer:

```text
SOURCE FACT
 ↓
STRUCTURED INTERPRETATION
 ↓
MODEL VERSION
 ↓
GENERATED ANALYSIS
```

The application should never discard the distinction between sourced fact and AI interpretation.

### 13.47 Data Retention

Phase 1 should preserve enough historical data to support:

- deduplication;
- repost detection;
- change detection;
- recommendation reproduction;
- feedback learning;
- search-quality analysis;
- Phase 2 application workflows;
- Phase 3 market intelligence.

Expired jobs should therefore not automatically be deleted.

### 13.48 Soft Deletion

Where practical, important business entities should use soft deletion or inactive states rather than destructive deletion.

Examples:

- Company.active = false
- WatchItem.active = false
- LearnedPreference.active = false

User-requested privacy deletion is separate and must follow the applicable data-deletion policy.

### 13.49 Data Model Boundaries

The canonical data model must keep the following distinctions explicit:

**COMPANY**

is not

**COMPANY SIGNAL**

**JOB**

is not

**JOB VERSION**

**JOB**

is not

**SOURCE OBSERVATION**

**JOB STATUS**

is not

**USER OPPORTUNITY STATE**

**CAREER PROFILE**

is not

**SEARCH PREFERENCE**

**SEARCH PREFERENCE**

is not

**LEARNED PREFERENCE**

**FIT**

is not

**PRIORITY**

**SOURCE FACT**

is not

**AI INTERPRETATION**

These boundaries prevent major implementation and explainability problems later.

### 13.50 Phase 1 Canonical Relationship Model

At a high level:

**USER**

```text
├── MASTER CAREER PROFILE
├── SEARCH PREFERENCES
├── GEOGRAPHIC SCOPES
├── CONNECTIONS
├── FEEDBACK
├── WATCH ITEMS
└── LEARNED PREFERENCES
```

**COMPANY**

```text
├── COMPANY ALIASES
├── COMPANY SIGNALS
├── CONNECTIONS
└── JOBS
```

**JOB**

```text
├── JOB VERSIONS
├── SOURCE OBSERVATIONS
├── JOB CHANGES
├── JOB ANALYSES
├── REQUIREMENTS
├── REQUIREMENT MATCHES
├── RECOMMENDATIONS
├── FEEDBACK
└── WATCH STATE
```

**SEARCH RUN**

```text
├── SEARCH PLAN
├── SOURCE EXECUTIONS
└── SOURCE OBSERVATIONS
```

**RECOMMENDATION**

```text
├── FIT
├── CONFIDENCE
├── PRIORITY
├── SCORE CONTRIBUTIONS
├── REASON CODES
└── EXPLANATION
```

### 13.51 Phase 1 Data Principle

The system should follow this progression:

```text
OBSERVE
 ↓
PRESERVE SOURCE EVIDENCE
 ↓
NORMALIZE
 ↓
RESOLVE CANONICAL ENTITY
 ↓
VERSION
 ↓
ANALYZE
 ↓
MATCH
 ↓
SCORE
 ↓
EXPLAIN
 ↓
LEARN FROM USER RESPONSE
```

The canonical database should make every important recommendation reproducible and every important factual assertion traceable.

The fundamental data principle is:

> Never sacrifice provenance, history, or entity identity for implementation convenience.

A Job is a persistent entity.

A JobVersion represents what changed.

A SourceObservation represents what a source reported.

A JobAnalysis represents what AI interpreted.

A JobRecommendation represents how that opportunity matched the user at a particular point in time.

Keeping those concepts separate provides the foundation required for reliable discovery, explainability, learning, and future Phase 2 and Phase 3 capabilities.

#### Replacement Mapping to the Old Document

New Section 13 — Company Intelligence and Core Data Model replaces and consolidates:

- Old Section 36 — Company Intelligence
- Old Section 37 — Core Data Model
- Old Section 38 — Source Observation
- Old Section 39 — Job State Model

After inserting the new Section 13:

- DELETE OLD SECTIONS 36–39

Several concepts from those sections now also connect directly to earlier rewritten sections:

```text
Company discovery and monitoring
→ Section 12 and Section 13

Source strategy and provenance
→ Section 7 and Section 13

SearchRun behavior
→ Section 5, Section 6 and Section 13

Career and network data
→ Section 8 and Section 13

Matching and recommendation records
→ Section 9 and Section 13

Feedback and watch state
→ Section 10 and Section 13

Notifications
→ Section 11 and Section 13

Search Health
→ Section 12 and Section 13
```

The next replacement section should be:

**SECTION 14**

System Architecture and Processing Pipelines

Primarily replaces:

- OLD SECTIONS 40–48

## 14. System Architecture and Processing Pipelines

Section 14 defines the technical architecture that implements the Phase 1 product behavior specified in Sections 1–13.

The architecture must support:

- scheduled and on-demand job discovery;
- multiple replaceable discovery sources;
- company career-site verification;
- company and market intelligence;
- persistent job and company history;
- normalization and deduplication;
- job-change detection;
- AI-assisted job interpretation;
- evidence-based career matching;
- deterministic Fit and Priority scoring;
- network intelligence;
- feedback and watch state;
- notifications;
- explainability;
- retries, idempotency, and partial failure;
- observability and auditability.

The architecture should favor a modular monolith with asynchronous workers for Phase 1, rather than prematurely introducing a large microservices environment.

The system must nevertheless maintain clear internal service boundaries so components can be separated later if scale or operational requirements justify it.

### 14.1 Architectural Principles

Phase 1 should follow these principles:

**MODULAR**

Clear boundaries between discovery, normalization, analysis, matching, scoring, and delivery.

**ASYNCHRONOUS**

Long-running searches and AI processing do not block interactive application requests.

**IDEMPOTENT**

Retries do not create duplicate jobs, versions, recommendations, or notifications.

**TRACEABLE**

Important outputs can be traced to source evidence, model versions, and application rules.

**CONFIGURABLE**

Search taxonomy, geography, scoring, scheduling, thresholds, and source behavior are not hard-coded.

**RESILIENT**

Failure of one source does not invalidate successful results from other sources.

**REPLACEABLE**

External sources and AI providers are accessed through adapter interfaces.

**SECURE**

Credentials and sensitive user data are isolated and protected.

**EXPLAINABLE**

AI interpretation is separated from deterministic business decisions.

### 14.2 High-Level Architecture

```text
                       ┌─────────────────────┐
                        │     WEB CLIENT      │
                        │ Executive Career UI │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │   APPLICATION API   │
                        └──────────┬──────────┘
                                   │
             ┌─────────────────────┼─────────────────────┐
             │                     │                     │
             ▼                     ▼                     ▼
     ┌──────────────┐     ┌────────────────┐    ┌────────────────┐
     │ Configuration│     │ Opportunity /  │    │ User / Career  │
     │   Services   │     │ Company Service│    │ Profile Service│
     └──────────────┘     └────────────────┘    └────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │ SEARCH ORCHESTRATOR │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │ TASK QUEUE / WORKERS│
                        └──────────┬──────────┘
                                   │
        ┌──────────────────────────┼───────────────────────────┐
        │                          │                           │
        ▼                          ▼                           ▼
┌────────────────┐      ┌────────────────────┐      ┌──────────────────┐
```

│ Job Discovery  │      │ Company Career /   │      │ Company / Market │

│    Adapters    │      │    ATS Adapters    │      │ Intelligence     │

```text
└────────────────┘      └────────────────────┘      └──────────────────┘
        │                          │                           │
        └──────────────────────────┼───────────────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │ INGESTION PIPELINE  │
                        └──────────┬──────────┘
                                   ▼
                  ┌──────────────────────────────┐
                  │ Normalize / Resolve / Dedupe │
                  └───────────────┬──────────────┘
                                  ▼
                       ┌──────────────────────┐
                       │ CANONICAL DATA STORE │
                       └──────────┬───────────┘
                                  │
                                  ▼
                        ┌─────────────────────┐
                        │ AI ANALYSIS LAYER   │
                        └──────────┬──────────┘
                                   ▼
                      ┌────────────────────────┐
                      │ MATCHING + SCORING     │
                      │ Deterministic Rules    │
                      └────────────┬───────────┘
                                   ▼
                  ┌──────────────────────────────┐
                  │ Explanation / Notification   │
                  │ Feedback / Watch Processing  │
                  └──────────────────────────────┘
```

### 14.3 Phase 1 Deployment Model

The recommended initial deployment is:

- Web Application
- Application API
- Background Worker Pool
- Scheduler
- Relational Database
- Object / Document Storage
- Queue
- Cache
- AI Provider Adapter
- External Source Adapters
- Notification Adapters

These may initially run within a small number of deployable services.

A reasonable Phase 1 structure is:

- career-intelligence-web

career-intelligence-api

career-intelligence-worker

career-intelligence-scheduler

The API and worker may share the same application codebase while executing different process roles.

### 14.4 Recommended Initial Technology Stack

The initial stack should optimize for development speed, maintainability, strong typing, asynchronous processing, and future extensibility.

Recommended baseline:

- Frontend
- Next.js / React
- TypeScript

Backend

Python

FastAPI

Database

PostgreSQL

Background Processing

Celery or equivalent worker framework

Queue / Broker

Redis initially or managed queue equivalent

Cache

Redis

Object Storage

S3-compatible object storage

AI Integration

Provider-independent AI adapter

Authentication

Managed identity / authentication provider

Infrastructure

Containerized deployment

Infrastructure as Code

Observability

Structured logging

Metrics

Tracing

Error monitoring

Specific managed cloud services may be selected during implementation.

The architecture should not depend on one cloud provider unless intentionally chosen.

### 14.5 Why PostgreSQL Is the Canonical Store

The Phase 1 domain contains strongly related entities:

- Company
- Job
- JobVersion
- SourceObservation
- SearchRun
- JobAnalysis
- Recommendation
- Connection
- Feedback
- WatchItem

These relationships benefit from:

- referential integrity;
- transactions;
- uniqueness constraints;
- version relationships;
- queryability;
- auditability.

PostgreSQL should therefore serve as the canonical operational datastore.

Vector search or specialized search infrastructure may be added later but should not replace canonical relational data.

### 14.6 Object Storage

Large or source-native artifacts should not necessarily be stored directly in relational tables.

Object storage may contain:

- Raw job-source payloads
- HTML snapshots where permitted
- Imported LinkedIn connection files
- Large source documents
- AI processing artifacts where required

Database records should retain references and metadata.

Retention must follow applicable source and privacy requirements.

### 14.7 Search and Semantic Retrieval

Phase 1 may initially use PostgreSQL full-text capabilities and structured filtering.

Semantic matching may use embeddings where useful for:

- job-to-career capability similarity;
- title normalization;
- opportunity clustering;
- company-name assistance;
- semantic discovery.

Embeddings must remain supporting signals.

They must not replace evidence-based matching or deterministic scoring.

### 14.8 Internal Service Boundaries

The application should maintain logical modules such as:

- UserService
- CareerProfileService
- SearchConfigurationService

SearchOrchestrator

SourceAdapterRegistry

IngestionService

CompanyResolutionService

JobNormalizationService

JobDeduplicationService

JobVerificationService

JobChangeDetectionService

CompanyIntelligenceService

JobAnalysisService

CareerMatchingService

FitScoringService

PriorityScoringService

ExplanationService

NetworkService

FeedbackService

WatchService

LearningService

NotificationService

SearchHealthService

These are logical boundaries.

They do not require independent microservices in Phase 1.

### 14.9 Adapter Architecture

External dependencies must be isolated behind adapters.

Core interfaces include:

- JobDiscoveryAdapter

CompanyCareerAdapter

ProfessionalSignalAdapter

CompanyIntelligenceAdapter

NetworkDataAdapter

AIProviderAdapter

NotificationAdapter

The application should interact with these interfaces rather than directly embedding provider-specific logic into business services.

### 14.10 JobDiscoveryAdapter

Conceptual contract:

```text
JobDiscoveryAdapter {
    search(search_request)
        -> JobDiscoveryResult
    fetch(job_reference)
        -> SourceJobObservation?
    health()
        -> AdapterHealth
}
```

The adapter translates the application's Search Plan into source-specific queries.

It returns observations rather than canonical Jobs.

### 14.11 CompanyCareerAdapter

The CompanyCareerAdapter verifies opportunities against employer-controlled sources.

Conceptually:

```text
CompanyCareerAdapter {
    discover_company_jobs(company, search_context)
        -> SourceJobObservation[]
    verify_job(job_candidate)
        -> JobVerificationResult
    health()
        -> AdapterHealth
}
```

Where practical, employer career sites or ATS systems become the canonical source for:

- active status;
- canonical job description;
- requisition identifier;
- employer location;
- published compensation;
- application URL.

### 14.12 ProfessionalSignalAdapter

This interface supports professional/social intelligence without coupling the application to credential-based scraping.

```text
ProfessionalSignalAdapter {
    discover_job_signals(search_context)
    discover_company_signals(company_context)
    health()
}
```

Phase 1 implementation must respect the access method supported by each source.

### 14.13 NetworkDataAdapter

Phase 1 assumes the primary network source is a user-provided LinkedIn Connections export.

```text
NetworkDataAdapter {
    parse_import(file)
    validate(records)
    normalize(records)
    create_import_preview(records)
    commit_import(records)
}
```

The interface must remain replaceable so a future approved API integration can use the same downstream network model.

### 14.14 CompanyIntelligenceAdapter

Conceptually:

```text
CompanyIntelligenceAdapter {
    discover_signals(company)
    verify_signal(signal_candidate)
    health()
}
```

Outputs become SourceObservations and, after processing, CompanySignals.

### 14.15 AIProviderAdapter

AI access must be abstracted.

```text
AIProviderAdapter {
    analyze_job(job_version, analysis_schema)
    match_requirements(job_analysis, career_profile)
    classify_company_signal(source_observation)
    generate_explanation(structured_recommendation)
}
```

Provider-specific prompt formats, response formats, retry logic, and model identifiers remain inside the AI integration layer.

### 14.16 NotificationAdapter

Conceptually:

```text
NotificationAdapter {
    send(notification)
    delivery_status(notification_reference)
}
```

Initial implementations may include:

- IN_APP
**EMAIL**

**PUSH**

Recommendation logic must not depend on the delivery channel.

### 14.17 Search Orchestrator

The Search Orchestrator coordinates SearchRuns.

Responsibilities include:

- Create SearchRun

Load active configuration

Generate SearchPlan

Determine source tasks

Prevent redundant overlapping work

Dispatch asynchronous tasks

Track completion

Determine SUCCESS / PARTIAL / FAILED

Trigger downstream processing

Close SearchRun

The orchestrator should not contain source-specific search logic.

That belongs inside adapters.

### 14.18 Scheduler

The scheduler initiates configured SearchRuns.

Initial configuration:

- 07:00 America/Los_Angeles
- 12:00 America/Los_Angeles
- 17:00 America/Los_Angeles

The scheduler should create work.

It should not execute the entire search pipeline synchronously.

### 14.19 Search Plan Generation

A Search Plan derives from:

- Enabled Role Families

```text
×
```

Search Taxonomy

```text
×
```

Enabled Geographic Scopes

```text
×
```

Applicable Sources

```text
×
```

Company Monitoring Rules

This is a conceptual combination.

The planner should optimize source requests rather than blindly execute every Cartesian combination.

### 14.20 Task Queue

Long-running operations should be asynchronous.

Example task categories:

- SOURCE_SEARCH
- JOB_FETCH
- JOB_VERIFY
- COMPANY_RESOLVE
- JOB_NORMALIZE
- JOB_DEDUPE
- JOB_CHANGE_DETECT

COMPANY_SIGNAL_DISCOVERY

JOB_ANALYSIS

REQUIREMENT_MATCHING

FIT_SCORING

PRIORITY_SCORING

EXPLANATION_GENERATION

NOTIFICATION_EVALUATION

NOTIFICATION_DELIVERY

**RECONCILIATION**

Workers should be able to process tasks independently where dependencies permit.

### 14.21 Pipeline Dependency Model

A job should move through explicit processing stages.

```text
DISCOVERED
 ↓
NORMALIZED
 ↓
RESOLVED
 ↓
DEDUPLICATED
 ↓
VERIFIED / VERIFICATION_DEFERRED
 ↓
VERSIONED
 ↓
ANALYZED
 ↓
MATCHED
 ↓
SCORED
 ↓
EXPLAINED
 ↓
NOTIFICATION_EVALUATED
```

The system should know which stage has completed rather than relying on one generic "processed" flag.

### 14.22 Baseline Pipeline

The initial baseline establishes the known opportunity universe.

```text
CREATE BASELINE SEARCH RUN
        ↓
GENERATE FULL SEARCH PLAN
        ↓
DISCOVER TARGET COMPANIES
        ↓
SEARCH ENABLED JOB SOURCES
        ↓
SEARCH COMPANY CAREER SITES
        ↓
COLLECT SOURCE OBSERVATIONS
        ↓
NORMALIZE COMPANIES
        ↓
NORMALIZE JOBS
        ↓
DEDUPLICATE
        ↓
VERIFY CANONICAL POSTINGS
        ↓
CREATE JOB + JOB VERSION
        ↓
ANALYZE JOB
        ↓
MATCH TO CAREER PROFILE
        ↓
CALCULATE FIT
        ↓
CALCULATE CONFIDENCE
        ↓
CALCULATE PRIORITY
        ↓
GENERATE EXPLANATION
        ↓
STORE BASELINE INVENTORY
```

Baseline jobs must not automatically be treated as newly posted merely because the system first saw them during the baseline.

### 14.23 Incremental Pipeline

Normal scheduled runs focus on new and changed information.

```text
CREATE INCREMENTAL SEARCH RUN
        ↓
LOAD LAST KNOWN STATE
        ↓
EXECUTE SEARCH PLAN
        ↓
COLLECT OBSERVATIONS
        ↓
COMPARE WITH HISTORY
        ↓
CLASSIFY
```

NEW_POSTING

NEWLY_DISCOVERED_EXISTING_POSTING

PREVIOUSLY_SEEN

MATERIALLY_CHANGED

**REPOSTED**

EXPIRED_OR_REMOVED

```text
UNRESOLVED

        ↓
PROCESS NEW / CHANGED ITEMS
        ↓
VERIFY
        ↓
VERSION
        ↓
ANALYZE / RE-ANALYZE
        ↓
MATCH / RE-MATCH
        ↓
SCORE / RE-SCORE
        ↓
NOTIFICATION EVALUATION
        ↓
UPDATE EXECUTIVE VIEW
```

Previously seen unchanged jobs should not require expensive repeated AI analysis.

### 14.24 Reconciliation Pipeline

The reconciliation process revisits recent or uncertain observations.

Initial reconciliation window:

**72 HOURS**

configurable.

Pipeline:

```text
SELECT RECENT / UNRESOLVED JOBS
        ↓
RECHECK CANONICAL SOURCE
        ↓
RECHECK SOURCE OBSERVATIONS
        ↓
RESOLVE POSTING DATE
        ↓
RESOLVE DUPLICATES
        ↓
VERIFY ACTIVE STATUS
        ↓
DETECT MATERIAL CHANGE
        ↓
UPDATE CLASSIFICATION
        ↓
RE-SCORE IF NECESSARY
```

Reconciliation prevents late source indexing from being mistaken for genuinely new postings.

### 14.25 On-Demand Pipeline

An on-demand search uses the same canonical processing path.

```text
USER REQUEST
 ↓
CREATE ON_DEMAND SEARCH RUN
 ↓
TARGETED SEARCH PLAN
 ↓
STANDARD DISCOVERY PIPELINE
 ↓
STANDARD CANONICAL STORE
 ↓
STANDARD MATCHING + SCORING
```

On-demand search must not create a parallel or temporary job universe.

### 14.26 Job Normalization Pipeline

Incoming observations should be normalized before canonical matching.

Normalize:

- Company Name
- Title
- Location
- Work Model
- Compensation
- Employment Type
- Posting Date
- Requisition ID
- Application URL
- Job Description

Preserve the original source values.

### 14.27 Company Resolution Pipeline

```text
OBSERVED COMPANY
 ↓
EXACT CANONICAL MATCH
 ↓
ALIAS MATCH
 ↓
DOMAIN MATCH
 ↓
NORMALIZED MATCH
 ↓
FUZZY / SEMANTIC ASSISTANCE
 ↓
MANUAL REVIEW IF REQUIRED
```

Low-confidence company matches must not be silently committed.

### 14.28 Job Deduplication Pipeline

Deduplication should consider:

- Employer Requisition ID
- Canonical Employer URL
- Company
- Normalized Title
- Location
- ATS Identifier
- Description Fingerprint
- Source Posting Identifier

The output should be:

**NEW CANONICAL JOB**

or

**EXISTING CANONICAL JOB + NEW SOURCE OBSERVATION**

### 14.29 Canonical Verification Pipeline

For a job discovered elsewhere:

```text
DISCOVERY OBSERVATION
 ↓
IDENTIFY EMPLOYER
 ↓
LOCATE EMPLOYER CAREER / ATS RECORD
 ↓
COMPARE IDENTITY SIGNALS
 ↓
VERIFY
 ↓
SET CANONICAL SOURCE
```

Possible verification outcomes:

**VERIFIED**

PROBABLY_VERIFIED

NOT_FOUND

**CONFLICT**

**DEFERRED**

NOT_FOUND should not automatically mean the job is closed.

### 14.30 Change Detection Pipeline

When a known job is observed again:

```text
NEW OBSERVATION
 ↓
NORMALIZE CONTENT
 ↓
CALCULATE FINGERPRINT
 ↓
COMPARE WITH CURRENT JOB VERSION
 ↓
NO MATERIAL CHANGE
        OR
CREATE NEW JOB VERSION
 ↓
CREATE JOB CHANGE RECORD
 ↓
TRIGGER RE-ANALYSIS IF REQUIRED
```

Materiality rules should be configurable.

### 14.31 Re-Analysis Rules

Not every change requires complete AI re-analysis.

Examples:

```text
Compensation Change
→ Recalculate Priority

Location / Work Model Change
→ Recalculate Priority
→ Possibly re-evaluate eligibility

Material Responsibility Change
→ Re-run Job Analysis
→ Re-match
→ Recalculate Fit and Priority

Formatting Change
→ No re-analysis
```

This reduces unnecessary cost and processing.

### 14.32 AI Analysis Pipeline

AI should transform unstructured source content into structured analysis.

```text
JOB VERSION
 ↓
AI ANALYSIS REQUEST
 ↓
SCHEMA-VALIDATED RESPONSE
 ↓
JOB ANALYSIS
 ↓
JOB REQUIREMENTS
 ↓
VALIDATION
 ↓
PERSIST
```

AI outputs must conform to an explicit schema.

Free-form prose should not be the authoritative analysis representation.

### 14.33 AI Job Analysis Contract

The AI analysis contract should request structured fields including:

- Normalized Role Family

Inferred Seniority

Inferred Scope

Primary Responsibilities

Required Capabilities

Preferred Capabilities

Leadership Requirements

Technical Requirements

Domain Requirements

Industry Requirements

Transformation Requirements

Platform Requirements

Cloud Requirements

AI Requirements

Security / Governance Requirements

Positive Scope Signals

Negative Signals

Ambiguities

Missing Information

Analysis Confidence

Every extracted requirement should be grounded in the supplied job content.

### 14.34 Requirement Matching Pipeline

```text
JOB REQUIREMENTS
        +
MASTER CAREER PROFILE
        ↓
AI-ASSISTED EVIDENCE MATCHING
        ↓
REQUIREMENT MATCHES
        ↓
VALIDATION
        ↓
DETERMINISTIC FIT ENGINE
```

The AI identifies plausible evidence relationships.

The application owns the scoring mathematics.

### 14.35 Deterministic Scoring Boundary

The AI must not simply return:

- Fit = 94

as the authoritative result.

Instead:

```text
AI
→ Structured Job Requirements
→ Requirement-to-Evidence Matches
→ Scope Interpretation
→ Gap Classification

APPLICATION LOGIC
→ Component Scores
→ Fit Score
→ Confidence Rules
→ Priority Score / Priority Band
```

This boundary is fundamental to explainability.

### 14.36 Fit Calculation Pipeline

```text
REQUIREMENT MATCHES
 ↓
ROLE / RESPONSIBILITY COMPONENT
 ↓
SENIORITY / SCOPE COMPONENT
 ↓
CAPABILITY COMPONENT
 ↓
LEADERSHIP COMPONENT
 ↓
CAREER DIRECTION COMPONENT
 ↓
DOMAIN / INDUSTRY COMPONENT
 ↓
CONFIGURED WEIGHTS
 ↓
FIT SCORE
```

The exact model version must be stored with the recommendation.

### 14.37 Confidence Pipeline

Confidence evaluates information quality rather than desirability.

Inputs may include:

- Job Description Completeness
- Role Scope Clarity
- Career Evidence Completeness
- Missing Information
- Canonical Verification
- Source Confidence
- Compensation Clarity
- Work-Model Clarity
- Role Ambiguity

Output:

**HIGH**

**MEDIUM**

**LOW**

### 14.38 Priority Pipeline

```text
FIT
 +
FRESHNESS
 +
NETWORK
 +
COMPENSATION
 +
LOCATION / WORK MODEL
 +
EXPLICIT USER PREFERENCES
 +
LEARNED PREFERENCES
 +
OPPORTUNITY CONTEXT
 ↓
APPLICATION PRIORITY
```

Output:

**IMMEDIATE**

**HIGH**

**MEDIUM**

**LOW**

Network must enter here, not in Fit.

### 14.39 Explanation Pipeline

```text
JOB ANALYSIS
 +
REQUIREMENT MATCHES
 +
CAREER EVIDENCE
 +
SCORE CONTRIBUTIONS
 +
REASON CODES
 +
PRIORITY FACTORS
 ↓
AI EXPLANATION GENERATION
 ↓
VALIDATION
 ↓
RECOMMENDATION EXPLANATION
```

The explanation should answer:

- Why does it fit?

What are the concerns?

Why should I pay attention now?

Who do I know?

The AI explains structured evidence.

It must not invent additional reasons.

### 14.40 AI Guardrails

All AI operations must follow these rules:

#### Evidence Grounding

Only use:

- Provided Job Content
- Provided Career Profile
- Provided Company Intelligence
- Provided Network Data
- Provided Configuration

#### No Fabrication

Never invent:

- Career Experience
- Achievements
- Budget Responsibility
- Team Size
- Compensation
- Certifications
- Industry Experience
- Relationship Strength
- Job Requirements
- Company Facts

#### Unknown Means Unknown

When evidence is insufficient:

**UNKNOWN**

or:

- MISSING_INFORMATION

must be used.

#### Structured Output

Machine-consumed AI operations should use validated structured schemas.

#### Model Versioning

Persist:

- Provider
- Model
- Prompt / Instruction Version
- Schema Version
- Generated At

where required for reproducibility.

### 14.41 Prompt Architecture

Prompts should be task-specific rather than using one enormous general-purpose prompt.

Recommended prompt families:

- JOB_ANALYSIS

REQUIREMENT_EVIDENCE_MATCHING

ROLE_SCOPE_INFERENCE

COMPANY_SIGNAL_CLASSIFICATION

EXPLANATION_GENERATION

Each prompt should have:

- Prompt ID
- Prompt Version
- Input Schema
- Output Schema
- Validation Rules

### 14.42 Prompt Guardrail Example

A Job Analysis prompt should conceptually instruct:

- Analyze only the supplied job posting.

Do not infer experience about the candidate.

Do not invent requirements not supported by the posting.

Distinguish explicit requirements from inferred context.

Return UNKNOWN when the posting does not provide sufficient information.

Return output matching the required schema.

A Career Matching prompt should conceptually instruct:

- Use only evidence contained in the supplied
- Master Career Profile.

Do not assume that missing profile information means the user lacks the experience.

Distinguish NO_MATCH from UNKNOWN.

For every positive match, identify supporting career evidence.

### 14.43 Schema Validation

AI responses must be validated before persistence.

Validation should check:

- Valid JSON / Structured Response

Required Fields Present

Allowed Enum Values

Valid References

Reasonable Numeric Ranges

Evidence References Exist

Invalid outputs should not flow directly into scoring.

### 14.44 AI Retry Behavior

Transient AI failures may be retried.

Retries should be:

- Bounded
- Idempotent
- Observable

Repeated schema failures should result in:

- AI_ANALYSIS_FAILED

or an equivalent processing state rather than silently accepting malformed output.

### 14.45 Failure Isolation

Failure of one processing component should not unnecessarily invalidate other successful work.

Example:

- 13 of 14 discovery sources succeed.

1 source fails.

Result:

- SearchRun = PARTIAL

The 13 successful source results continue through normalization, matching, scoring, and storage.

The system must not discard valid results because one source failed.

### 14.46 Retry Strategy

Use bounded exponential backoff for transient failures.

Examples:

- Network Timeout
- Rate Limit
- Temporary Provider Failure
- Temporary Database Contention

Permanent failures should not retry indefinitely.

Examples:

- Invalid Credentials
- Unsupported API
- Invalid Configuration
- Permission Denied

Retry policy should be configurable by adapter or task type.

### 14.47 Dead-Letter / Failed Task Handling

Tasks that exceed retry limits should move into an inspectable failed state.

Store:

- Task Type
- Entity Reference
- SearchRun
- Failure Category
- Attempt Count
- Last Error
- First Failure Time
- Last Failure Time

Failed work should be retryable after the underlying problem is corrected.

### 14.48 Idempotency

Every retryable pipeline operation should be designed for safe repetition.

Examples:

- Running the same source search twice must not create duplicate source observations.

Processing the same job observation twice must not create duplicate Jobs.

Analyzing the same JobVersion twice must not create uncontrolled duplicate analyses.

Sending the same notification task twice must not send duplicate alerts.

Stable identifiers, fingerprints, and database uniqueness constraints should enforce this wherever practical.

### 14.49 Concurrency Control

The system must protect against simultaneous workers modifying the same canonical entity incorrectly.

Potential techniques include:

- Database Transactions
- Unique Constraints
- Optimistic Locking
- Row-Level Locking
- Idempotency Keys

Implementation should use the simplest mechanism appropriate to each operation.

### 14.50 Overlapping Search Runs

Before starting equivalent work, the orchestrator should check for:

**QUEUED**

**RUNNING**

SearchRuns with substantially equivalent Search Plans.

The system may:

**MERGE**

**SKIP**

**DEFER**

redundant work.

Different scopes may run concurrently.

### 14.51 SearchRun Completion

A SearchRun is not complete merely because source discovery finished.

Required processing stages should reach a terminal state.

At minimum:

- Source Discovery
- Normalization
- Resolution
- Deduplication
- Verification or Explicit Deferral
- Change Detection
- Required Matching
- Required Scoring
- Notification Evaluation

Some non-critical enrichment may continue asynchronously after the SearchRun is considered operationally complete.

The distinction between critical and non-critical enrichment must be explicit.

### 14.52 SearchRun Status

Possible top-level statuses:

**RUNNING**

**SUCCESS**

**PARTIAL**

**FAILED**

#### SUCCESS

Required planned work completed successfully.

#### PARTIAL

Meaningful results were produced, but one or more planned components failed or remain incomplete.

#### FAILED

Insufficient planned work completed to produce a meaningful run.

### 14.53 Event-Driven Processing

Phase 1 may use internal events to decouple pipeline stages.

Examples:

- JobObserved
- JobCreated
- JobChanged
- JobVerified

CompanySignalCreated

JobAnalyzed

RecommendationGenerated

FeedbackRecorded

WatchItemChanged

HighPriorityOpportunityDetected

These events may initially be implemented using the existing queue infrastructure rather than a dedicated enterprise event platform.

### 14.54 Example Event Flow

```text
JobObserved
 ↓
NormalizeJob
 ↓
ResolveCompany
 ↓
ResolveJobIdentity
 ↓
JobCreated
 ↓
VerifyJob
 ↓
AnalyzeJob
 ↓
MatchCareerProfile
 ↓
GenerateRecommendation
 ↓
EvaluateNotification
```

The architecture should permit reprocessing from a known stage.

### 14.55 Network Import Pipeline

```text
USER UPLOADS LINKEDIN CONNECTION EXPORT
 ↓
STORE IMPORT FILE SECURELY
 ↓
PARSE
 ↓
VALIDATE
 ↓
DETECT DUPLICATES
 ↓
NORMALIZE COMPANY NAMES
 ↓
RESOLVE COMPANIES
 ↓
GENERATE IMPORT PREVIEW
 ↓
USER CONFIRMS
 ↓
COMMIT
 ↓
CREATE / UPDATE CONNECTIONS
 ↓
MATCH CONNECTIONS TO COMPANIES
 ↓
RECALCULATE NETWORK SIGNALS
 ↓
RECALCULATE APPLICATION PRIORITY
```

Network import must not cause Fit recalculation unless another Fit input changed.

### 14.56 Feedback Processing Pipeline

```text
USER FEEDBACK
 ↓
STORE FEEDBACK EVENT
 ↓
UPDATE USER OPPORTUNITY STATE
 ↓
CLASSIFY
```

**WORKFLOW ACTION**

**PREFERENCE SIGNAL**

```text
SYSTEM CORRECTION

 ↓
UPDATE LEARNING EVIDENCE
 ↓
RECALCULATE LEARNED PREFERENCE IF WARRANTED
 ↓
RE-SCORE RELEVANT ACTIVE OPPORTUNITIES IF REQUIRED
```

One isolated feedback event should not create a strong learned preference.

### 14.57 Watch Processing Pipeline

```text
WATCH ITEM
 ↓
REGISTER MONITORING TARGET
 ↓
INCREASE MONITORING ATTENTION
 ↓
FUTURE SEARCH / RECONCILIATION
 ↓
DETECT MATERIAL CHANGE
 ↓
RE-SCORE IF REQUIRED
 ↓
NOTIFICATION EVALUATION
```

Watching an opportunity or company must not artificially increase Job Fit.

### 14.58 Notification Pipeline

```text
RECOMMENDATION / MATERIAL CHANGE
 ↓
LOAD NOTIFICATION POLICY
 ↓
CHECK FIT / PRIORITY / CONFIDENCE
 ↓
CHECK WATCH STATE
 ↓
CHECK PREVIOUS NOTIFICATIONS
 ↓
CHECK QUIET HOURS
 ↓
CREATE NOTIFICATION
 ↓
DELIVER THROUGH ADAPTER
 ↓
STORE DELIVERY RESULT
```

Notification evaluation must be idempotent.

### 14.59 Security Architecture Boundary

Detailed security requirements are defined in Section 16.

At the architectural level:

```text
Secrets
→ Secret Manager

User Authentication
→ Managed Authentication Layer

Database
→ Private / Restricted Access

Object Storage
→ Private by Default

External Credentials
→ Server-Side Only

AI Provider Calls
→ Controlled Integration Layer

Imported Network Data
→ User-Scoped Access

Application Authorization
→ Server-Side Enforcement
```

Client applications must never receive external-source credentials or AI-provider secrets.

### 14.60 Observability Architecture

Every important asynchronous operation should carry correlation identifiers such as:

- request_id search_run_id source_execution_id job_id job_version_id analysis_id recommendation_id

Structured logs should allow an engineer to trace:

```text
SearchRun
 ↓
Source Request
 ↓
Observation
 ↓
Canonical Job
 ↓
Analysis
 ↓
Recommendation
 ↓
Notification
```

Detailed observability requirements are defined in Section 16.

### 14.61 Cost Control

Potentially expensive operations include:

- External Searches
- AI Analysis
- Embedding Generation
- Company Intelligence Collection
- Repeated Verification

Cost controls should include:

- avoid re-analyzing unchanged JobVersions;
- cache appropriate source responses;
- batch processing where supported;
- use fingerprints before expensive analysis;
- prioritize relevant jobs before deep enrichment where appropriate;
- monitor AI usage by operation;
- monitor source usage and value.

Cost optimization must not compromise discovery quality or explainability.

### 14.62 Source Performance Optimization

The architecture should measure:

- Which source discovered a job first?

Which sources produce duplicates?

Which sources produce high-Fit opportunities?

Which sources frequently fail?

Which sources have long indexing delays?

Which sources rarely add unique value?

These metrics can later influence Search Plan generation.

The system should not permanently remove a source solely because of one poor run.

### 14.63 Configuration Architecture

Configuration should be versioned.

Important configurable domains include:

- Search Taxonomy
- Geographic Scopes
- Search Schedule
- Source Configuration

Fit Model

Priority Model

Notification Policy

Reconciliation Window

Retry Policies

Historical recommendations and SearchRuns should retain the relevant configuration versions.

### 14.64 Configuration Change Impact

Configuration changes should affect future processing unless an explicit reprocessing action occurs.

Examples:

```text
Add Seattle
→ Baseline Seattle
→ Future scheduled searches include Seattle

Change Fit Model
→ New recommendations use new version
→ Existing recommendations remain historically reproducible

Change Notification Threshold
→ Future notification evaluations use new policy
```

### 14.65 Manual Review Queue

Some ambiguity cannot safely be resolved automatically.

Phase 1 should support a small manual-review mechanism for cases such as:

- Ambiguous Company Mapping
- Potential Duplicate Job
- Conflicting Canonical Sources
- Uncertain Repost
- Connection Company Ambiguity

The application should not require manual review for routine processing.

Manual review is the fallback for low-confidence entity decisions that could materially corrupt canonical data.

### 14.66 Phase 1 Scalability Principle

The system is initially a personal application, but architecture should avoid assumptions that make later multi-user support impossible.

Therefore:

- User-Owned Data should include user_id where appropriate.

Canonical Public Company / Job Data may later be shared across users.

User Recommendations must remain user-specific.

Connections must remain user-specific.

Feedback must remain user-specific.

Preferences must remain user-specific.

Do not introduce unnecessary multi-tenant complexity into the initial implementation, but preserve clean ownership boundaries.

### 14.67 Phase 1 Processing Contract

For every discovered opportunity, the platform should ultimately be able to reconstruct:

**WHERE IT CAME FROM**

**WHEN IT WAS DISCOVERED**

**WHETHER IT WAS VERIFIED**

**WHAT CHANGED**

**HOW AI INTERPRETED IT**

**WHICH CAREER EVIDENCE MATCHED**

**HOW FIT WAS CALCULATED**

**HOW CONFIDENT THE SYSTEM WAS**

**WHY PRIORITY WAS ASSIGNED**

**WHAT EXPLANATION WAS SHOWN**

**WHAT THE USER DID**

**WHETHER A NOTIFICATION WAS SENT**

This is the core engineering contract for Phase 1.

### 14.68 Architecture Principle

The complete processing model is:

```text
SEARCH CONFIGURATION
        ↓
SEARCH ORCHESTRATION
        ↓
SOURCE ADAPTERS
        ↓
SOURCE OBSERVATIONS
        ↓
NORMALIZATION
        ↓
ENTITY RESOLUTION
        ↓
DEDUPLICATION
        ↓
CANONICAL VERIFICATION
        ↓
VERSIONING / CHANGE DETECTION
        ↓
AI STRUCTURED ANALYSIS
        ↓
CAREER EVIDENCE MATCHING
        ↓
DETERMINISTIC FIT
        ↓
RECOMMENDATION CONFIDENCE
        ↓
DETERMINISTIC PRIORITY
        ↓
EVIDENCE-BACKED EXPLANATION
        ↓
NOTIFICATION EVALUATION
        ↓
EXECUTIVE USER EXPERIENCE
        ↓
USER FEEDBACK
        ↓
CONTROLLED LEARNING
```

The fundamental architectural separation is:

**EXTERNAL SOURCES**

provide observations

**AI**

interprets unstructured information

**CANONICAL DATA MODEL**

preserves facts and history

**APPLICATION LOGIC**

makes deterministic scoring decisions

**USER INTERFACE**

presents decisions and evidence

**USER FEEDBACK**

improves future prioritization

This separation provides the foundation for a system that is reliable, explainable, maintainable, and extensible into Phase 2 and Phase 3.

## 15. APIs and Integration Contracts

Section 15 defines the application APIs and integration contracts required to expose the Phase 1 capabilities defined in Sections 1–14.

The API layer must support the executive user experience while preserving the architectural boundaries established in Section 14.

The API should expose canonical application data, not raw provider-specific structures.

External source integrations should remain behind adapters and should not leak their implementation details into the frontend.

### 15.1 API Design Principles

Phase 1 APIs should follow these principles:

**RESOURCE ORIENTED**

Expose stable application resources such as jobs, companies, recommendations, connections, and SearchRuns.

**VERSIONED**

Breaking API changes require explicit version management.

**USER SCOPED**

Career profiles, preferences, network data, feedback, watch state, and recommendations are user-specific.

**ASYNCHRONOUS WHERE REQUIRED**

Long-running searches, imports, and reprocessing operations return task or SearchRun references rather than blocking.

**IDEMPOTENT**

Retryable write operations should avoid duplicate effects.

**TRACEABLE**

Important responses should expose stable identifiers needed for debugging and auditability.

**CANONICAL**

Provider-specific source formats remain behind adapters.

**EXPLAINABLE**

Recommendation APIs expose evidence, reason codes, confidence, and Priority factors rather than only scores.

### 15.2 API Versioning

Initial API namespace:

- /api/v1

Example:

- GET /api/v1/opportunities

API versioning is separate from:

- Career Profile Version
- Search Preference Version
- Fit Model Version
- Priority Model Version
- Prompt Version
- Job Version
- Recommendation Version

### 15.3 Authentication and Authorization

All user-specific endpoints require authentication.

Authorization must be enforced server-side.

The API must ensure that one user's:

- Career Profile
- Connections
- Feedback
- Watch Items
- Learned Preferences
- Recommendations
- Notification Preferences

cannot be accessed by another user.

External provider credentials must never be exposed through client-facing APIs.

### 15.4 Primary API Domains

Phase 1 APIs should be grouped into:

- Dashboard

Opportunities

Companies

Career Profile

Search Configuration

Search Runs

Connections

Feedback

Watchlist

Learned Preferences

Notifications

Search Health

### 15.5 Dashboard API

Primary endpoint:

- GET /api/v1/dashboard

Purpose:

- Provide the information required for the executive Home screen without requiring numerous independent frontend requests.

Conceptual response:

```text
{
  "since_last_review": {
    "new_opportunities": 12,
    "high_priority": 3,
    "immediate": 1,
    "watched_changes": 2,
    "companies_worth_watching": 4
  },
  "requires_attention": [],
  "new_strong_matches": [],
  "watched_changes": [],
  "company_signals": [],
  "search_health": {
    "last_run_at": "2026-10-04T19:00:00Z",
    "last_run_status": "SUCCESS",
    "next_run_at": "2026-10-05T00:00:00Z"
  }
}
```

Times above are illustrative.

The server should return UTC timestamps and allow the client to display them in the user's configured timezone.

### 15.6 Opportunity List API

GET /api/v1/opportunities

Supported query parameters may include:

- priority fit_min fit_max confidence

role_family opportunity_cluster

company_id industry

geographic_scope location work_model

compensation_min

posted_after first_seen_after

network_present

watch_state user_state job_status

changed_since

sort page page_size

Default sorting should align with the Phase 1 executive workflow:

- Application Priority then Fit then Freshness

### 15.7 Opportunity List Response

Each result should contain enough information for the standard Opportunity Card.

Conceptually:

```text
{
  "job_id": "job_123",
  "company": {
    "company_id": "company_456",
    "name": "Example Corp"
  },
  "title": "VP Technology Transformation",
  "location": "San Francisco, CA",
  "work_model": "HYBRID",
  "fit_score": 94,
  "confidence": "HIGH",
  "application_priority": "IMMEDIATE",
  "employer_posted_at": "2026-10-04T14:00:00Z",
  "first_seen_at": "2026-10-04T15:07:00Z",
  "compensation": {
    "minimum": 275000,
    "maximum": 340000,
    "currency": "USD",
    "period": "YEAR"
  },
  "network": {
    "connection_count": 3,
    "relevant_connection_count": 2
  },
  "primary_match_reason": "Strong enterprise transformation leadership alignment",
  "primary_concern": "Financial-services experience preferred",
  "user_state": "UNREVIEWED",
  "watched": false
}
```

Values are illustrative only.

### 15.8 Opportunity Detail API

GET /api/v1/opportunities/{job_id}

This is the primary API contract for the Opportunity Detail screen.

The response should include:

- Canonical Job
- Current Job Version
- Company
- Recommendation
- Fit Components
- Confidence
- Priority Factors
- Requirement Matches
- Concerns
- Network
- Company Intelligence
- Source Verification
- Job History
- User State
- Watch State

### 15.9 Opportunity Detail Response

Conceptual response:

```text
{
  "job": {
    "job_id": "job_123",
    "title": "VP Enterprise Transformation",
    "normalized_title": "VP Enterprise Transformation",
    "role_family": "ENTERPRISE_TRANSFORMATION",
    "location": "San Jose, CA",
    "work_model": "HYBRID",
    "status": "ACTIVE",
    "employer_posted_at": "2026-10-04T14:00:00Z",
    "first_seen_at": "2026-10-04T15:07:00Z",
    "last_verified_at": "2026-10-04T19:03:00Z",
    "canonical_url": "canonical-employer-job-reference"
  },
  "company": {
    "company_id": "company_456",
    "name": "Example Corp",
    "industry": "Enterprise Software"
  },
  "recommendation": {
    "recommendation_id": "rec_789",
    "fit_score": 94,
    "confidence": "HIGH",
    "application_priority": "IMMEDIATE",
    "fit_components": {
      "role_responsibility": 96,
      "seniority_scope": 94,
      "capability": 95,
      "leadership": 96,
      "career_direction": 93,
      "domain_industry": 82
    },
    "why_it_fits": [
      "Enterprise transformation leadership",
      "Technology operations experience",
      "Portfolio governance",
      "Executive stakeholder management"
    ],
    "concerns": [
      {
        "type": "INDUSTRY_GAP",
        "assessment": "PARTIAL_MATCH",
        "summary": "Role prefers direct financial-services experience."
      }
    ],
    "why_now": [
      "Recently posted",
      "Preferred geographic scope",
      "Compensation aligns with configured preferences",
      "Relevant first-degree connections"
    ]
  },
  "network": {
    "connection_count": 3,
    "relevant_connection_count": 2,
    "connections": []
  },
  "company_intelligence": {
    "signals": []
  },
  "source": {
    "discovered_via": "JOB_DISCOVERY_SOURCE",
    "canonical_source": "EMPLOYER_CAREER_SITE",
    "verification_status": "VERIFIED"
  },
  "user_state": "UNREVIEWED",
  "watched": false
}
```

All values and names above are illustrative.

### 15.10 Fit Evidence API

The UI should be able to drill into a Fit component or Requirement Match.

GET /api/v1/opportunities/{job_id}/evidence

Optional filtering:

- requirement_id score_component reason_code

Conceptual response:

```text
{
  "requirement": {
    "requirement_id": "req_101",
    "text": "Lead enterprise-wide technology transformation",
    "importance": "CORE"
  },
  "assessment": {
    "match_strength": "STRONG_MATCH",
    "evidence_strength": "STRONG"
  },
  "career_evidence": [
    {
      "evidence_id": "career_achievement_55",
      "summary": "Led large-scale enterprise technology transformation."
    }
  ],
  "reason_codes": [
    "STRONG_TRANSFORMATION_MATCH",
    "EXECUTIVE_SCOPE_MATCH"
  ]
}
```

The API should not expose hidden AI reasoning or chain-of-thought.

It should expose the structured evidence and reasons actually used by the system.

### 15.11 Job History API

GET /api/v1/opportunities/{job_id}/history

Response may include:

- First Discovered
- Canonical Verification
- Material Job Versions
- Compensation Changes
- Location Changes
- Work-Model Changes
- Reposts
- Status Changes
- Recommendation Changes

Example:

```text
{
  "job_id": "job_123",
  "events": [
    {
      "type": "FIRST_DISCOVERED",
      "occurred_at": "2026-10-04T15:07:00Z"
    },
    {
      "type": "CANONICAL_VERIFIED",
      "occurred_at": "2026-10-04T15:11:00Z"
    },
    {
      "type": "COMPENSATION_CHANGED",
      "occurred_at": "2026-10-05T18:20:00Z"
    }
  ]
}
```

### 15.12 Company List API

GET /api/v1/companies

Possible filters:

- monitoring_priority industry has_matching_jobs has_high_priority_jobs network_present watched signal_type geographic_presence

The API should support the Target Company Universe rather than only companies with currently active jobs.

### 15.13 Company Detail API

GET /api/v1/companies/{company_id}

Response should include:

- Company Overview

Monitoring Priority

Matching Opportunities

Relevant Company Signals

Network Summary

Watch State

Opportunity History

Source Provenance

Conceptually:

```text
{
  "company": {
    "company_id": "company_456",
    "name": "Example Corp",
    "industry": "Enterprise Software",
    "monitoring_priority": "HIGH"
  },
  "opportunities": {
    "active_matching_jobs": 2,
    "high_priority_jobs": 1
  },
  "network": {
    "connection_count": 6
  },
  "signals": [],
  "watched": true
}
```

### 15.14 Company Signal API

GET /api/v1/companies/{company_id}/signals

Each signal should expose:

- Signal Type
- Summary
- Event Date
- Discovery Date
- Confidence
- Source Reference

Company intelligence must remain evidence-backed.

### 15.15 Career Profile API

GET /api/v1/career-profile

PUT /api/v1/career-profile

Updates should create a new Career Profile version when materially changed.

The update response should indicate whether active recommendations require rescoring.

Conceptually:

```text
{
  "career_profile_version": 7,
  "material_change": true,
  "rescore_required": true
}
```

### 15.16 Career Profile Evidence API

GET /api/v1/career-profile/evidence

Optional filters:

- capability experience achievement domain leadership_scope

This endpoint supports evidence inspection and profile correction.

### 15.17 Search Taxonomy API

GET    /api/v1/search-taxonomy

POST   /api/v1/search-taxonomy/terms

PATCH  /api/v1/search-taxonomy/terms/{term_id}

DELETE /api/v1/search-taxonomy/terms/{term_id}

Deleting a taxonomy term should normally mean disabling or retiring it rather than destroying historical configuration data.

Changes should create a new taxonomy version.

### 15.18 Geographic Scope API

GET    /api/v1/geographic-scopes

POST   /api/v1/geographic-scopes

PATCH  /api/v1/geographic-scopes/{scope_id}

DELETE /api/v1/geographic-scopes/{scope_id}

The API must support adding future locations without code changes.

### 15.19 Search Preference API

GET /api/v1/search-preferences

PUT /api/v1/search-preferences

Search Preference updates should create a versioned configuration.

The response should identify potential processing effects:

```text
{
  "search_preference_version": 12,
  "baseline_required": false,
  "targeted_baseline_recommended": true,
  "rescore_required": true
}
```

### 15.20 Search Schedule API

GET /api/v1/search-schedules

PUT /api/v1/search-schedules

Schedule configuration should include:

- Enabled
- Run Type
- Local Time
- Timezone
- Applicable Geographic Scopes
- Applicable Role Families

The API must preserve explicit timezone configuration.

### 15.21 Start Search API

POST /api/v1/search-runs

Example request:

```text
{
  "run_type": "ON_DEMAND",
  "scope": {
    "geographic_scope_ids": ["geo_seattle"],
    "role_family_ids": ["AI_TRANSFORMATION"]
  }
}
```

Response:

```text
{
  "search_run_id": "run_123",
  "status": "RUNNING"
}
```

The API should return promptly.

Search processing continues asynchronously.

### 15.22 SearchRun API

GET /api/v1/search-runs/{search_run_id}

Conceptual response:

```text
{
  "search_run_id": "run_123",
  "run_type": "ON_DEMAND",
  "status": "RUNNING",
  "started_at": "2026-10-04T18:15:00Z",
  "completed_at": null,
  "sources": {
    "expected": 14,
    "completed": 8,
    "failed": 0
  },
  "results": {
    "new_opportunities": 3,
    "changed_opportunities": 1,
    "expired_opportunities": 0
  }
}
```

### 15.23 SearchRun History API

GET /api/v1/search-runs

Possible filters:

- run_type status started_after started_before

This supports the Search Health screen.

### 15.24 Search Health API

GET /api/v1/search-health

Response should include:

- Last Scheduled Run
- Last Run Status
- Next Scheduled Run

Expected Sources

Healthy Sources

Degraded Sources

Failed Sources

Geographic Coverage

Role-Family Coverage

Recent Failures

A partial search must be represented explicitly.

### 15.25 Source Health API

GET /api/v1/search-health/sources

Each source should report:

- Source
- Status
- Last Successful Execution
- Last Attempt
- Failure Category
- Retry State
- User Action Required

Do not expose credentials, secrets, or unnecessary internal error detail.

### 15.26 Connections Import API

Network import is asynchronous and should use a staged workflow.

Start:

- POST /api/v1/connections/imports

The uploaded file should be stored securely and associated with an import batch.

Response:

```text
{
  "import_batch_id": "import_123",
  "status": "PROCESSING"
}
```

### 15.27 Connections Import Preview API

GET /api/v1/connections/imports/{import_batch_id}

Response should include:

- Valid Records
- Duplicate Records
- New Connections
- Updated Connections
- Unresolved Companies
- Rejected Records

The import should not be committed until required validation and user confirmation are complete.

### 15.28 Commit Connections Import

POST /api/v1/connections/imports/{import_batch_id}/commit

After commit:

- Update Connections
- Resolve Company Matches
- Update Network Signals
- Recalculate Application Priority Where Required

Fit must not change merely because network data changed.

### 15.29 Connections API

GET /api/v1/connections

Possible filters:

- name company_id position relationship_strength

Relationship strength must remain UNKNOWN unless explicitly known.

### 15.30 Opportunity Feedback API

POST /api/v1/opportunities/{job_id}/feedback

Example:

```text
{
  "action": "NOT_INTERESTED",
  "reason_codes": [
    "WRONG_CAREER_DIRECTION",
    "TOO_HANDS_ON"
  ],
  "comment": "Role is more engineering execution than the leadership direction I want."
}
```

The system should record the Recommendation version shown when feedback was provided.

### 15.31 Opportunity State API

PATCH /api/v1/opportunities/{job_id}/state

Possible states:

**UNREVIEWED**

**INTERESTED**

**WATCH**

NOT_INTERESTED

ALREADY_APPLIED

**ARCHIVED**

State changes and feedback events should remain separate internally.

### 15.32 Watchlist API

Create:

- POST /api/v1/watchlist

Example:

```text
{
  "target_type": "COMPANY",
  "target_id": "company_456",
  "monitoring_priority": "HIGH"
}
```

List:

- GET /api/v1/watchlist

Update:

- PATCH /api/v1/watchlist/{watch_id}

Remove:

- DELETE /api/v1/watchlist/{watch_id}

Removal should normally deactivate the WatchItem rather than destroy its history.

### 15.33 Learned Preferences API

GET /api/v1/learned-preferences

The user should be able to act on a learned preference:

- POST /api/v1/learned-preferences/{preference_id}/confirm

POST /api/v1/learned-preferences/{preference_id}/dismiss

POST /api/v1/learned-preferences/{preference_id}/reset

Corrections may require a dedicated update endpoint.

The API must preserve whether a preference is:

**LEARNED**

EXPLICITLY_CONFIRMED

**DISMISSED**

### 15.34 Notification Preference API

GET /api/v1/notification-preferences

PUT /api/v1/notification-preferences

Configuration may include:

- Immediate Alerts Enabled
- Minimum Fit
- Minimum Priority
- Minimum Confidence

Watched Job Alerts

Watched Company Alerts

Digest Frequency

Quiet Hours

Timezone

Notification Channels

### 15.35 Notifications API

GET /api/v1/notifications

Possible filters:

- unread notification_type job_id company_id created_after

Actions:

- POST /api/v1/notifications/{notification_id}/read

Notification records must retain the reason the notification was generated.

### 15.36 Executive Digest API

GET /api/v1/digests/latest

Optional historical endpoint:

- GET /api/v1/digests

Digest content should follow Section 11:

- Requires Your Attention
- New Strong Matches
- Watched Changes
- Companies Worth Watching
- Other New Opportunities
- Search Health

The digest API should expose structured sections rather than one opaque generated document.

### 15.37 Async Operation Contract

Long-running operations should return an operation reference.

Examples:

- Search
- Connection Import
- Large Rescore
- Targeted Baseline
- Reconciliation

Conceptual response:

```text
{
  "operation_id": "operation_123",
  "operation_type": "TARGETED_BASELINE",
  "status": "QUEUED"
}
```

Status endpoint:

- GET /api/v1/operations/{operation_id}

Possible states:

**QUEUED**

**RUNNING**

**SUCCESS**

**PARTIAL**

**FAILED**

**CANCELLED**

### 15.38 Idempotency Contract

Write APIs that may be retried should support an idempotency mechanism where appropriate.

Example header:

- Idempotency-Key

Useful operations include:

- Start Search
- Commit Connection Import
- Record Feedback
- Create Watch Item
- Trigger Rescore

Repeated requests with the same idempotency key should not create duplicate effects.

### 15.39 Pagination Contract

Large collection endpoints should use consistent pagination.

Example:

- page_size cursor

Response:

```text
{
  "items": [],
  "next_cursor": "cursor_value",
  "has_more": true
}
```

Cursor-based pagination is preferred for frequently changing opportunity inventories.

### 15.40 Sorting Contract

Sorting should use documented stable fields.

Example:

- sort=priority_desc sort=fit_desc sort=posted_desc sort=first_seen_desc sort=changed_desc

Default Opportunity ordering:

```text
Priority
→ Fit
→ Freshness
```

### 15.41 Error Contract

APIs should return structured errors.

Conceptually:

```text
{
  "error": {
    "code": "SEARCH_SOURCE_UNAVAILABLE",
    "message": "One configured search source is currently unavailable.",
    "retryable": true,
    "request_id": "request_123"
  }
}
```

Do not expose:

- Credentials
- Secrets
- Internal Tokens
- Raw Provider Authentication Errors
- Sensitive Infrastructure Detail

### 15.42 Partial Success Contract

Partial success must be represented explicitly.

Example:

```text
{
  "status": "PARTIAL",
  "results_available": true,
  "coverage": {
    "expected_sources": 14,
    "successful_sources": 13,
    "failed_sources": 1
  }
}
```

The frontend must not translate this into:

- No new jobs.

### 15.43 Provenance Contract

Important externally sourced facts should include provenance references where useful.

Conceptually:

```text
{
  "value": "Hybrid",
  "source": {
    "source_type": "EMPLOYER_CAREER_SITE",
    "observed_at": "2026-10-04T19:03:00Z"
  }
}
```

Not every list response needs full provenance.

Detailed views should make it accessible.

### 15.44 Confidence Contract

Confidence values should use a stable enum:

**HIGH**

**MEDIUM**

**LOW**

The API should not overload Confidence to mean Fit or Priority.

Example:

```text
{
  "fit_score": 91,
  "confidence": "LOW",
  "application_priority": "MEDIUM"
}
```

is valid.

### 15.45 Unknown-Value Contract

Unknown values must be represented as unknown.

For example:

```text
{
  "compensation": null,
  "compensation_status": "NOT_PUBLISHED"
}
```

or:

```text
{
  "relationship_strength": "UNKNOWN"
}
```

Do not manufacture default values for missing facts.

### 15.46 Score Version Contract

Detailed Recommendation responses should include relevant versions.

```text
{
  "recommendation_metadata": {
    "career_profile_version": 7,
    "search_preference_version": 12,
    "fit_model_version": "fit_v3",
    "priority_model_version": "priority_v2",
    "generated_at": "2026-10-04T19:04:00Z"
  }
}
```

This supports auditability and reproducibility.

### 15.47 API Rescoring Behavior

When inputs change, APIs should not silently rewrite historical Recommendation records.

Instead:

**OLD RECOMMENDATION**

remains historical

**NEW RECOMMENDATION**

is created using current inputs

The Opportunity Detail API normally returns the current Recommendation while allowing historical versions to be retrieved where required.

### 15.48 Recommendation History API

GET /api/v1/opportunities/{job_id}/recommendations

This may expose:

- Recommendation Version
- Fit
- Confidence
- Priority
- Generated At
- Input Versions
- Reason for Recalculation

Useful reasons include:

- JOB_CHANGED
- CAREER_PROFILE_CHANGED
- PREFERENCES_CHANGED
- NETWORK_CHANGED
- SCORING_MODEL_CHANGED
- COMPENSATION_ADDED
- LOCATION_CHANGED

### 15.49 Integration Boundary

External integrations should never be called directly by the browser for core discovery processing.

Correct:

```text
WEB CLIENT
 ↓
APPLICATION API
 ↓
APPLICATION SERVICE
 ↓
ADAPTER
 ↓
EXTERNAL PROVIDER
```

Avoid:

```text
WEB CLIENT
 ↓
EXTERNAL JOB PROVIDER
```

for protected or controlled integrations.

This protects credentials and preserves normalization, provenance, and observability.

### 15.50 Adapter Result Contract

External adapters should return normalized application-level observation structures.

Conceptually:

```text
SourceJobObservation {
    source
    external_job_id?
    source_url?
    observed_company_name
    observed_title
    observed_location?
    observed_posted_at?
    description?
    compensation?
    requisition_id?
    retrieved_at
    raw_payload_reference?
}
```

Adapters must not create canonical Jobs directly.

Canonical entity creation belongs to the ingestion and resolution pipeline.

### 15.51 AI Integration Contract

Application services should send structured requests to the AI layer.

Example conceptual input:

```text
JobAnalysisRequest {
    job_version_id
    job_content
    analysis_schema_version
    prompt_version
}
```

Output:

```text
JobAnalysisResult {
    structured_analysis
    model
    model_version
    prompt_version
    schema_version
    generated_at
}
```

AI-provider-specific response structures must remain inside the AI adapter.

### 15.52 AI Failure Contract

If AI analysis fails:

- Do not invent analysis.

Do not assign arbitrary Fit.

Do not silently treat the job as a poor match.

Instead, the job may temporarily expose:

- Analysis Status: FAILED
- Fit: NOT_AVAILABLE
- Confidence: NOT_AVAILABLE
- Priority: PENDING

Retry according to Section 14 failure rules.

### 15.53 Frontend Contract for Recommendation State

The frontend should support Recommendation states such as:

- PENDING_ANALYSIS
**ANALYZED**

**RECOMMENDED**

ANALYSIS_FAILED

RESCORE_PENDING

The UI must not display stale or incomplete scores as though they were current without appropriate status.

### 15.54 Search Coverage Contract

SearchRun responses should expose both execution and coverage.

Example:

```text
{
  "status": "PARTIAL",
  "execution": {
    "expected_sources": 14,
    "completed_sources": 13,
    "failed_sources": 1
  },
  "coverage": {
    "geographic_scopes": {
      "bay_area": "COMPLETE",
      "us_remote": "COMPLETE"
    },
    "role_families": {
      "technology_operations": "COMPLETE",
      "ai_transformation": "PARTIAL"
    }
  }
}
```

This supports the Search Health requirements from Section 12.

### 15.55 API Performance Expectations

Interactive read endpoints should be optimized for executive UI responsiveness.

The Dashboard and Opportunity List APIs should use precomputed Recommendation data rather than performing AI matching during each page request.

Expensive operations belong in asynchronous pipelines.

The interactive API should primarily retrieve already processed canonical results.

### 15.56 Caching

Appropriate read-heavy responses may be cached.

Potential candidates:

- Dashboard Summary
- Company Summary
- Search Configuration
- Search Health Summary
- Opportunity Lists

Cache invalidation should occur when underlying Recommendation, SearchRun, feedback, or watch-state data materially changes.

Canonical database state remains authoritative.

### 15.57 Auditability

Important write operations should retain:

- User
- Operation
- Entity
- Timestamp
- Previous State where appropriate
- New State
- Request / Correlation ID

Examples:

- Career Profile Update
- Search Preference Update
- Taxonomy Change
- Geographic Scope Change
- Feedback
- Watch State Change
- Notification Policy Change
- Manual Company Resolution

Detailed security audit requirements are defined in Section 16.

### 15.58 API Documentation

The backend should generate or maintain machine-readable API documentation.

For a FastAPI implementation, OpenAPI should be generated from the application contracts.

API schemas should be treated as part of the engineering specification and validated in automated tests.

### 15.59 Phase 1 API Principle

The API architecture should preserve the complete decision chain:

```text
SOURCE
 ↓
OBSERVATION
 ↓
CANONICAL JOB
 ↓
JOB VERSION
 ↓
JOB ANALYSIS
 ↓
REQUIREMENT MATCH
 ↓
FIT
 ↓
CONFIDENCE
 ↓
PRIORITY
 ↓
EXPLANATION
 ↓
USER ACTION
```

The frontend should consume the result of this chain without needing to reconstruct the business logic itself.

The core API principle is:

> The server owns canonical data, scoring rules, provenance, and workflow state; the client presents those decisions and sends explicit user actions back to the server.

### 15.60 Phase 1 Minimum API Surface

The minimum coding-ready Phase 1 API surface is:

**DASHBOARD**

GET /api/v1/dashboard

**OPPORTUNITIES**

GET   /api/v1/opportunities

GET   /api/v1/opportunities/{job_id}

GET   /api/v1/opportunities/{job_id}/evidence

GET   /api/v1/opportunities/{job_id}/history

POST  /api/v1/opportunities/{job_id}/feedback

PATCH /api/v1/opportunities/{job_id}/state

**COMPANIES**

GET /api/v1/companies

GET /api/v1/companies/{company_id}

GET /api/v1/companies/{company_id}/signals

**CAREER PROFILE**

GET /api/v1/career-profile

PUT /api/v1/career-profile

**SEARCH CONFIGURATION**

GET /api/v1/search-taxonomy

GET /api/v1/geographic-scopes

GET /api/v1/search-preferences

GET /api/v1/search-schedules

**SEARCH**

POST /api/v1/search-runs

GET  /api/v1/search-runs

GET  /api/v1/search-runs/{search_run_id}

**SEARCH HEALTH**

GET /api/v1/search-health

GET /api/v1/search-health/sources

**CONNECTIONS**

POST /api/v1/connections/imports

GET  /api/v1/connections/imports/{import_batch_id}

POST /api/v1/connections/imports/{import_batch_id}/commit

GET  /api/v1/connections

**WATCHLIST**

GET    /api/v1/watchlist

POST   /api/v1/watchlist

PATCH  /api/v1/watchlist/{watch_id}

DELETE /api/v1/watchlist/{watch_id}

**LEARNED PREFERENCES**

GET  /api/v1/learned-preferences

POST /api/v1/learned-preferences/{preference_id}/confirm

POST /api/v1/learned-preferences/{preference_id}/dismiss

**NOTIFICATIONS**

GET /api/v1/notifications

GET /api/v1/notification-preferences

PUT /api/v1/notification-preferences

**DIGEST**

GET /api/v1/digests/latest

Additional administrative or engineering endpoints may be added during implementation without changing the Phase 1 product contract.

## 16. Security, Privacy and Observability

Section 16 defines the security, privacy, auditability, and operational-observability requirements for the Phase 1 Executive Job Intelligence Platform.

The platform processes several categories of information that require deliberate protection:

- Master Career Profile data;
- employment history and achievements;
- compensation preferences;
- job-search preferences;
- imported professional-network data;
- user feedback and learned preferences;
- authentication information;
- external-source credentials;
- AI requests and responses;
- application activity and audit records.

The platform must also provide enough operational visibility to determine whether searches, source integrations, AI processing, matching, scoring, and notifications are functioning correctly.

The core principle is:

> Protect personal and credential data while making system behavior, failures, data lineage, and recommendation processing observable and auditable.

### 16.1 Security Objectives

Phase 1 security should protect:

**CONFIDENTIALITY**

Only authorized users and services can access protected data.

**INTEGRITY**

Career data, recommendations, configurations, and source observations cannot be altered without authorization.

**AVAILABILITY**

Failure of individual integrations or processing components should not make the entire application unusable.

**TRACEABILITY**

Important user and system actions can be reconstructed.

**DATA MINIMIZATION**

Collect and retain only information required for the product.

**SEPARATION OF DUTIES**

External credentials, AI access, application logic, and client access remain appropriately separated.

### 16.2 Data Classification

Phase 1 should classify application data according to sensitivity.

Suggested initial categories:

**PUBLIC**

Public job postings

Public company information

Public market intelligence

**INTERNAL**

Search configuration

Scoring-model configuration

Operational metrics

Non-sensitive system metadata

**CONFIDENTIAL USER DATA**

Master Career Profile

Search preferences

Compensation preferences

Feedback

Learned preferences

Watch state

Recommendation history

**RESTRICTED**

Imported connection data

Authentication data

Access tokens

External provider credentials

Secrets

Sensitive audit/security information

The exact classification terminology may be aligned with the hosting environment or future organizational security framework.

### 16.3 Authentication

User authentication should use a managed authentication solution rather than custom password storage where practical.

Authentication capabilities should support:

- Secure Sign-In
- Session Management
- Password / Credential Protection
- Account Recovery
- MFA Capability
- Session Revocation

Phase 1 may initially have one primary user, but authentication should not be omitted merely because the application is personal.

### 16.4 Authorization

Authorization must be enforced server-side.

User-scoped resources include:

- Career Profile
- Search Preferences
- Geographic Preferences
- Connections
- Feedback
- Watch Items
- Learned Preferences
- Recommendations
- Notification Preferences

The client must never be treated as the authorization boundary.

### 16.5 Future Multi-User Boundary

Although Phase 1 may begin as a personal application, user ownership should be explicit where appropriate.

Conceptually:

**PUBLIC / CANONICAL DATA**

Company

Public Job

Public Company Signal

```text
versus
```

**USER-SPECIFIC DATA**

Career Profile

Connections

Recommendation

Feedback

Watch State

Preferences

Notifications

This prevents future multi-user support from requiring a complete security-model redesign.

### 16.6 Secrets Management

Secrets must not be:

- stored in frontend code;
- committed to source control;
- embedded in application configuration files distributed with the application;
- exposed through logs;
- returned through APIs.

Secrets include:

- AI Provider Credentials
- Job Source API Credentials
- Email / Notification Credentials
- Database Credentials
- Authentication Secrets
- Encryption Keys
- OAuth Client Secrets

Use a managed secrets system or equivalent secure runtime-secret mechanism.

### 16.7 Secret Rotation

The architecture should permit credential rotation without application redesign.

Where supported:

- Credential Version
- Created At
- Rotated At
- Expires At
- Provider

should be operationally trackable.

Secrets themselves should not appear in application audit records.

### 16.8 External Source Credentials

External source credentials must remain server-side.

Correct:

```text
CLIENT
 ↓
APPLICATION API
 ↓
SOURCE ADAPTER
 ↓
EXTERNAL PROVIDER
```

Incorrect:

```text
CLIENT
 ↓
EXTERNAL PROVIDER USING EMBEDDED SECRET
```

Each adapter should receive only the credentials required for that integration.

### 16.9 LinkedIn / Network Data Security

Phase 1 assumes a user-provided LinkedIn Connections export rather than username/password collection.

The application must not request or store the user's LinkedIn password.

Network-import files should be treated as Restricted data.

Processing flow:

```text
USER UPLOAD
 ↓
SECURE TEMPORARY STORAGE
 ↓
VALIDATE
 ↓
PARSE
 ↓
NORMALIZE
 ↓
IMPORT
 ↓
APPLY RETENTION POLICY TO ORIGINAL FILE
```

The normalized connection records should contain only fields required for the product.

### 16.10 Network Data Minimization

If the imported export contains information that Phase 1 does not require, the system should avoid unnecessarily persisting it.

Required fields may include:

- First Name
- Last Name
- Public Profile URL
- Current Company
- Current Position
- Connection Date
- Email only if present and actually required

The system should not expand the dataset merely because additional information is technically available.

### 16.11 Career Profile Privacy

The Master Career Profile may contain substantially more information than a public resume.

It should therefore be treated as Confidential User Data.

Access should be limited to:

- Authorized User
- Application Services Requiring It
- Approved AI Processing Required for Matching

The complete Career Profile should not be sent to external systems unless necessary for the specific operation.

### 16.12 AI Data Minimization

AI requests should contain the minimum context necessary for the task.

For example:

**JOB ANALYSIS**

Needs job content.

Does not require the user's connection list.

**REQUIREMENT MATCHING**

Needs relevant Career Profile evidence.

Does not require notification history.

**EXPLANATION GENERATION**

Needs structured recommendation evidence.

Does not require raw source credentials.

This reduces unnecessary exposure and simplifies privacy controls.

### 16.13 AI Provider Security Boundary

All AI calls should pass through the controlled AI integration layer defined in Section 14.

The application should retain operational metadata such as:

- Provider
- Model
- Operation Type
- Prompt Version
- Schema Version
- Request Time
- Response Time
- Status
- Token / Usage Metadata where available

Sensitive prompt or response content should not automatically be copied into general-purpose logs.

### 16.14 AI Logging

Operational logs should prefer metadata over full content.

Preferred:

- JobAnalysis job_id=job_123
- job_version_id=version_4
- model=model_x status=SUCCESS
- duration_ms=1840

Avoid routinely logging:

- Full Career Profile
- Full Connection List
- Full AI Prompt
- Full AI Response
- Authentication Data
- Secrets

Detailed content should be retained only where required for explicit debugging, evaluation, or reproducibility and protected appropriately.

### 16.15 Encryption

Sensitive data should be encrypted:

**IN TRANSIT**

**TLS / HTTPS**

**AT REST**

Database and object-storage encryption

Highly sensitive secrets should additionally use the designated secrets-management system rather than ordinary database fields.

### 16.16 Object Storage Security

Object storage containing:

- connection imports;
- raw source payloads;
- source documents;
- processing artifacts;

should be private by default.

Access should occur through authorized server-side mechanisms.

Public object URLs should not be used for Restricted user data.

### 16.17 Database Security

The production database should:

- not be publicly exposed unnecessarily;
- use encrypted connections;
- use least-privilege application credentials;
- separate administrative access from application access;
- support backup and recovery;
- log relevant administrative activity where practical.

Application services should not connect using unrestricted superuser credentials.

### 16.18 Least Privilege

Each system component should receive only the access it needs.

Examples:

**WEB CLIENT**

No database credentials.

**APPLICATION API**

Application-level database access.

**WORKER**

Required queue, database, storage, AI, and source access.

**SCHEDULER**

Ability to create scheduled work, not unrestricted administrative access.

**SOURCE ADAPTER**

Only credentials required for that source.

### 16.19 Input Validation

All external inputs must be validated.

This includes:

- API Payloads
- Uploaded Files
- Source Adapter Responses
- AI Structured Responses
- Search Configuration
- URLs
- Identifiers
- Notification Content

Validation should occur before data enters canonical processing.

### 16.20 File Upload Security

Connection-import and other future file uploads should validate:

- File Type
- File Size
- Expected Structure
- Encoding
- Malformed Content

Uploaded files should receive server-generated storage identifiers rather than trusting user-supplied paths or filenames.

### 16.21 Data Retention

Retention rules should distinguish among:

- Canonical Job History
- Source Observations
- Career Profile Versions
- Recommendation History
- Feedback
- Network Imports
- Normalized Connections
- Audit Logs
- Operational Logs
- AI Metadata

Historical job and recommendation data has legitimate product value because it supports:

- deduplication;
- repost detection;
- scoring analysis;
- user-learning analysis;
- future application history.

Raw imported files may require a shorter retention period than normalized application data.

Retention periods should be configurable.

### 16.22 User Data Deletion

The architecture should support deletion of user-specific data where required.

Deletion should consider:

- Career Profile
- Preferences
- Connections
- Feedback
- Watch Items
- Learned Preferences
- Recommendations
- Notifications
- Uploaded Network Files

Public canonical job and company data need not necessarily be deleted merely because one user's account data is removed.

The implementation must preserve the distinction between public canonical data and user-owned data.

### 16.23 Backup and Recovery

Critical persistent data should be backed up.

Recovery objectives should be appropriate for a personal Phase 1 application but should still protect against accidental loss.

At minimum, recovery planning should cover:

- PostgreSQL Database
- Configuration
- User Career Profile
- Connections
- Feedback
- Recommendations
- Watch State

Infrastructure configuration should be reproducible through Infrastructure as Code where practical.

### 16.24 Audit Logging

Security and business-critical actions should generate audit records.

Examples include:

- Authentication Events
- Career Profile Changes
- Search Preference Changes
- Taxonomy Changes
- Geographic Scope Changes
- Schedule Changes
- Notification Policy Changes
- Connection Imports
- Manual Company Resolution
- Manual Job Resolution
- Feedback
- Learned Preference Confirmation / Dismissal
- Watch State Changes
- Administrative Configuration Changes

### 16.25 Audit Event Model

Conceptually:

```text
AuditEvent {
    audit_event_id
    actor_type
    actor_id?
    action
    entity_type
    entity_id?
    occurred_at
    request_id?
    correlation_id?
    previous_state_reference?
    new_state_reference?
    result
    metadata
}
```

Sensitive values and secrets should be excluded or redacted.

### 16.26 Audit Immutability

Audit records should not be casually editable through ordinary application workflows.

Corrections should generally create additional events rather than silently rewriting audit history.

### 16.27 Observability Objectives

Operational observability must answer:

- Did the scheduled search run?

Which sources were searched?

Which sources failed?

How long did the run take?

How many jobs were discovered?

How many were actually new?

How many changed?

How many required AI analysis?

Did AI analysis succeed?

Were recommendations generated?

Were notifications evaluated?

Were alerts delivered?

What is failing repeatedly?

Where is processing delayed?

### 16.28 Three Observability Layers

Phase 1 should maintain:

**LOGS**

Detailed structured events.

**METRICS**

Aggregated operational measurements.

**TRACES / CORRELATION**

Ability to follow work across pipeline stages.

A lightweight implementation is acceptable initially, but all three concepts should be represented.

### 16.29 Structured Logging

Logs should use structured fields rather than relying primarily on free-form text.

Common fields may include:

- timestamp level environment

request_id correlation_id

user_id where appropriate

search_run_id source_execution_id

company_id job_id job_version_id

analysis_id recommendation_id

operation status

duration_ms error_category

Sensitive user data should not be included merely for convenience.

### 16.30 Correlation IDs

Long-running workflows must retain identifiers that allow the complete processing chain to be reconstructed.

Example:

- SearchRun

```text
  search_run_id=run_123

        ↓

SourceExecution
  source_execution_id=source_456

        ↓

SourceObservation
  observation_id=obs_789

        ↓

Job
  job_id=job_321

        ↓

JobAnalysis
  analysis_id=analysis_654

        ↓

Recommendation
  recommendation_id=rec_987

        ↓

Notification
  notification_id=notification_111
```

This traceability is essential for debugging incorrect recommendations or missing opportunities.

### 16.31 Search Metrics

Track at least:

- Search Runs Started
- Search Runs Completed

SUCCESS Count

PARTIAL Count

FAILED Count

Run Duration

Expected Sources

Successful Sources

Failed Sources

Observations Collected

New Jobs

Newly Discovered Existing Jobs

Changed Jobs

Reposted Jobs

Expired Jobs

Unresolved Jobs

Metrics should be available by:

- Run Type
- Source
- Role Family
- Geographic Scope
- Time Period

where useful.

### 16.32 Source Metrics

For each source, track:

- Availability
- Success Rate
- Failure Rate
- Latency

Observations Returned

Unique Jobs Discovered

Duplicate Jobs

Canonical Verification Rate

Average Discovery Delay

High-Fit Opportunities Discovered

High-Priority Opportunities Discovered

This allows the system to evaluate source usefulness rather than simply source volume.

### 16.33 AI Metrics

Track AI operations separately by task.

Examples:

- Job Analyses Requested
- Job Analyses Successful
- Job Analyses Failed

Requirement Matching Calls

Company Signal Classifications

Explanation Generations

Schema Validation Failures

Retries

Average Latency

Token / Usage Volume where available

Estimated Cost where available

Metrics should also include model and prompt versions so regressions can be identified.

### 16.34 Matching and Recommendation Metrics

Track:

- Recommendations Generated

Fit Distribution

Confidence Distribution

Priority Distribution

High-Fit Count

Low-Confidence High-Fit Count

Rescore Count

Recommendations by Role Family

Recommendations by Opportunity Cluster

Interested Rate

Great Match Rate

Not Interested Rate

These metrics bridge operational monitoring and recommendation-quality evaluation.

Detailed quality testing remains in Section 17.

### 16.35 Queue and Worker Metrics

Track:

- Queue Depth
- Oldest Queued Task Age

Tasks Started

Tasks Completed

Tasks Failed

Retry Count

Dead-Letter / Exhausted Tasks

Worker Availability

Task Duration by Type

A growing queue may indicate a system problem even when individual components appear healthy.

### 16.36 Notification Metrics

Track:

- Notifications Evaluated

Immediate Alerts Generated

Immediate Alerts Suppressed

Duplicate Alerts Prevented

Alerts Delayed by Quiet Hours

Delivery Attempts

Delivery Success

Delivery Failure

Digest Generation Success

These metrics support both operational reliability and notification-quality tuning.

### 16.37 Search Freshness Metrics

Because timing is important to executive job search, the platform should measure discovery latency.

Useful metric:

- Discovery Delay =
- first_seen_at - employer_posted_at

where employer_posted_at is reliably known.

Track distributions such as:

- Median Discovery Delay
- 90th Percentile Discovery Delay

Discovery Delay by Source

Discovery Delay by Search Time

This helps determine whether the three-search-per-day cadence and source strategy are working effectively.

### 16.38 Data Quality Metrics

Monitor:

- Unresolved Companies

Ambiguous Company Matches

Potential Duplicate Jobs

Jobs Missing Posting Date

Jobs Missing Canonical Verification

Jobs Missing Location

Jobs Missing Work Model

Jobs Missing Compensation

Failed Job Analysis

Low-Confidence Recommendations

Not all missing information represents system failure.

The metrics identify where uncertainty exists.

### 16.39 Search Coverage Metrics

For every SearchRun, measure intended versus completed coverage.

Conceptually:

**EXPECTED COVERAGE**

```text
Role Families
Geographic Scopes
Sources
Target Companies

      versus
```

**COMPLETED COVERAGE**

This supports the Search Health screen and prevents a failed search component from being misinterpreted as an empty market.

### 16.40 Health Checks

Services should expose operational health checks where appropriate.

Examples:

- Application API
- Database Connectivity
- Queue Connectivity
- Worker Availability
- Cache Connectivity
- Object Storage Connectivity

External providers should have separate integration-health status rather than making the entire application unhealthy because one provider is unavailable.

### 16.41 Source Health States

Source health should use stable states:

**HEALTHY**

**DEGRADED**

**FAILED**

**DISABLED**

NOT_CONFIGURED

USER_ACTION_REQUIRED

The Search Health interface defined in Section 12 should consume these states.

### 16.42 Alerting

Operational alerts should focus on actionable system problems.

Initial examples:

- Scheduled Search Did Not Start

Scheduled Search Failed

Repeated PARTIAL SearchRuns

Critical Source Failing Repeatedly

Queue Backlog Above Threshold

AI Failure Rate Above Threshold

Database Unavailable

Worker Pool Unavailable

Notification Delivery Repeatedly Failing

Connection Import Failed

Alert thresholds should be configurable.

### 16.43 Avoid Alert Fatigue

Operational alerting should distinguish:

**INFORMATIONAL**

**WARNING**

**CRITICAL**

A single transient source failure should generally not generate the same severity as complete search-system failure.

Repeated or sustained failures may escalate.

### 16.44 Search Health vs. System Health

These concepts must remain separate.

Example:

**SYSTEM HEALTH**

Application API: HEALTHY

Database: HEALTHY

Workers: HEALTHY

**SEARCH HEALTH**

Last Run: PARTIAL

1 Job Source Failed

The application itself may be healthy while search coverage is incomplete.

Conversely, the last search may have succeeded while a current infrastructure problem exists.

### 16.45 Business Observability

Operational telemetry should also answer product-level questions.

Examples:

- How many genuinely relevant opportunities are being discovered?

Which role families produce the strongest matches?

Which geographic scopes produce useful opportunities?

Which sources discover strong opportunities earliest?

How often does the user reject supposedly high-Fit opportunities?

Which concerns appear most frequently?

How many opportunities are watched versus pursued?

This data helps tune the system without relying on intuition alone.

### 16.46 Privacy-Preserving Analytics

Product analytics should avoid unnecessary exposure of personal content.

Prefer:

- Fit Band = 90–100
- Priority = HIGH
- Feedback = INTERESTED
- Role Family = TECHNOLOGY_OPERATIONS

over copying full Career Profile evidence or full job descriptions into analytics systems.

### 16.47 Environment Separation

Development, testing, and production environments should be separated.

Production user data should not automatically be copied into development environments.

Where realistic data is required for testing, use sanitized or synthetic datasets.

### 16.48 Testing and Debug Data

Debugging tools must not become an uncontrolled path for exposing:

- Career Profile Data
- Connections
- Credentials
- Secrets
- Full AI Prompts
- Authentication Tokens

Administrative debugging access should be limited and auditable.

### 16.49 Dependency and Vulnerability Management

Application dependencies and container images should be maintained through routine vulnerability and dependency management.

The implementation should support:

- Dependency Inventory
- Automated Vulnerability Scanning
- Security Updates
- Container Image Scanning where applicable

Critical security updates should not depend on normal product-feature release timing.

### 16.50 Secure Development Requirements

Phase 1 development should include:

- source-control protection;
- secret scanning;
- dependency scanning;
- code review;
- automated tests;
- protected production configuration;
- controlled deployment access.

Security controls should remain proportionate to a personal Phase 1 application while avoiding shortcuts that create difficult remediation later.

### 16.51 Incident Evidence

Operational and security logs should preserve enough information to investigate:

- Unauthorized Access Attempt

Unexpected Data Change

Credential Failure

Suspicious Import

Unexpected AI Processing

Source Integration Failure

Notification Misdelivery

Configuration Change

Log retention should balance investigation value with privacy and storage requirements.

### 16.52 Recommendation Auditability

For any important recommendation, the platform should be able to reconstruct:

- Job Version

Source Evidence

Job Analysis Version

Career Profile Version

Search Preference Version

Fit Model Version

Priority Model Version

Requirement Matches

Score Contributions

Reason Codes

Recommendation Confidence

Generated Explanation

User Feedback

Notification History

This is both an explainability requirement and an observability requirement.

### 16.53 Operational Dashboard

An engineering/admin operational view should eventually show:

**SEARCH**

Last Run

Next Run

Run Success Rate

Partial / Failed Runs

**SOURCES**

Healthy

Degraded

Failed

**PROCESSING**

Queue Depth

Failed Tasks

AI Failures

**DATA QUALITY**

Unresolved Companies

Potential Duplicates

Low-Confidence Analyses

**NOTIFICATIONS**

Delivery Success

Failures

**COST**

AI Usage

Source Usage

Infrastructure Indicators

This operational dashboard is distinct from the user's Executive Job Intelligence dashboard.

### 16.54 Security Events vs. Product Events

The application should distinguish:

**SECURITY EVENT**

Authentication failure

Unauthorized access attempt

Secret-access anomaly

**OPERATIONAL EVENT**

Search source timeout

Worker failure

Queue backlog

**PRODUCT EVENT**

Opportunity marked Interested

Company added to Watchlist

Search preference changed

These event types may have different retention, alerting, and access requirements.

### 16.55 Privacy and Observability Balance

Observability must not become a mechanism for duplicating sensitive user data throughout the infrastructure.

The design principle is:

**LOG IDENTIFIERS AND STATES**

**NOT UNNECESSARY CONTENT**

For example:

Preferred:

- recommendation_id=rec_123
- fit=94
- confidence=HIGH
- priority=IMMEDIATE

Avoid:

- complete career history copied into application log

### 16.56 Phase 1 Security Baseline

Before Phase 1 is considered production-ready, the minimum security baseline should include:

- Authentication enabled

Server-side authorization

**TLS / HTTPS**

Encrypted persistent storage

Secrets management

No credentials in source control

Private connection-import storage

Input validation

User-data ownership controls

Audit logging for material configuration changes

Backup / recovery capability

Dependency and secret scanning

Production / development separation

### 16.57 Phase 1 Observability Baseline

Before Phase 1 is considered production-ready, the minimum observability baseline should include:

- Structured application logs

Request / correlation IDs

SearchRun tracking

SourceExecution tracking

Source health

Queue / worker health

AI operation success / failure metrics

Recommendation-generation metrics

Notification-delivery metrics

Search coverage reporting

Operational failure alerts

Search Health UI support

### 16.58 Security and Observability Principle

The platform should be able to answer two different sets of questions.

#### Security and Privacy

Who can access the data?

What data is being stored?

Where are credentials stored?

What information is sent externally?

Can sensitive actions be audited?

Can user-owned data be deleted?

Are secrets and personal data protected?

#### Observability

Did the system run?

What did it search?

What succeeded?

What failed?

What was discovered?

How was the job processed?

Was the recommendation generated?

Was the user notified?

Can the complete processing chain be reconstructed?

The final operating principle is:

> Sensitive information should be protected by default, while system behavior should be observable by design.

Security must not depend on obscurity.

Observability must not depend on exposing sensitive content.

## 17. Testing, Evaluation and Acceptance Criteria

Section 17 defines how Phase 1 will be verified before production use and how recommendation quality will be measured after implementation.

Testing must cover more than whether the application runs. The platform must demonstrate that it can:

- discover relevant opportunities;
- avoid duplicate opportunities;
- distinguish newly posted jobs from newly discovered older jobs;
- preserve source provenance;
- detect meaningful job changes;
- interpret job scope accurately;
- match jobs against actual career evidence;
- calculate Fit consistently;
- keep Fit separate from network and urgency;
- calculate Application Priority correctly;
- represent uncertainty honestly;
- explain recommendations from evidence;
- survive partial source failures;
- learn from feedback without overreacting;
- protect user data;
- deliver useful alerts without excessive noise.

The testing strategy therefore combines:

**UNIT TESTING**

**INTEGRATION TESTING**

**PIPELINE TESTING**

**CONTRACT TESTING**

**AI EVALUATION**

**GOLDEN-SET EVALUATION**

**DATA-QUALITY TESTING**

**SECURITY TESTING**

**PERFORMANCE TESTING**

**USER ACCEPTANCE TESTING**

**PRODUCTION MONITORING**

The central quality principle is:

> A technically functioning system is not successful unless its recommendations are accurate, explainable, timely, and useful.

### 17.1 Test Pyramid

Phase 1 should use several layers of testing.

```text
 USER ACCEPTANCE
       ▲
GOLDEN-SET EVALUATION
       ▲
  END-TO-END TESTS
       ▲
 INTEGRATION TESTS
       ▲
  CONTRACT TESTS
       ▲
    UNIT TESTS
```

Most deterministic business logic should be covered by fast automated unit tests.

External integrations and AI behavior require additional evaluation layers.

### 17.2 Unit Testing

Unit tests should cover deterministic application logic independently from external providers.

Primary areas include:

- Search Plan Generation

Taxonomy Expansion

Geographic Scope Evaluation

Company Name Normalization

Company Resolution Rules

Title Normalization

Job Identity

Job Deduplication

Content Fingerprinting

Job Change Detection

Discovery Classification

Fit Component Calculation

Fit Weighting

Recommendation Confidence Rules

Application Priority Calculation

Hard Filters

Negative Signals

Learned Preference Rules

Watch State

Notification Eligibility

Notification Deduplication

SearchRun Status

Retry Classification

Idempotency Logic

### 17.3 Deterministic Scoring Tests

The Fit engine must have explicit test fixtures.

Example:

- Role / Responsibility = 96
- Seniority / Scope = 94
- Capability = 95
- Leadership = 96
- Career Direction = 93
- Domain / Industry = 82

Given a specific Fit Model version, the same inputs must always produce the same Fit result.

Tests should verify:

- Correct weighting

Correct rounding

Missing-component handling

Unknown-value handling

Hard-filter interaction

Model-version selection

AI variability must not alter deterministic scoring mathematics.

### 17.4 Fit Independence Tests

Critical invariant:

**NETWORK STRENGTH**

**MUST NOT CHANGE**

**FIT SCORE**

Test example:

- Job A

Career Match:

- 94

Connections:

- 0

Expected Fit:

- 94

Then:

- Same Job
- Same Career Profile

Connections:

- 12

Expected Fit:

- 94

Application Priority may change.

Fit must not.

### 17.5 Freshness Independence Tests

Similarly:

**JOB AGE**

**MUST NOT CHANGE**

**CAREER FIT**

A job posted one hour ago and the same job posted ten days ago should have the same Fit when job content and Career Profile evidence are identical.

Freshness may change Application Priority.

### 17.6 Compensation Independence Tests

Compensation should not alter whether the user is professionally qualified for the role.

Example:

- Fit = 92

```text
Compensation = Strong
→ Fit remains 92

Compensation = Below Preference
→ Fit remains 92
→ Priority may decrease
```

### 17.7 Integration Testing

Integration tests should verify interactions among application modules.

Important flows include:

```text
Source Observation
→ Normalization
→ Company Resolution
→ Job Resolution

Job Version
→ AI Analysis
→ Requirement Matching
→ Fit
→ Confidence
→ Priority

Recommendation
→ Notification Evaluation
→ Delivery Record

Feedback
→ Learned Preference
→ Priority Recalculation

Connection Import
→ Company Resolution
→ Network Match
→ Priority Recalculation
```

### 17.8 Source Adapter Contract Tests

Every source adapter should pass a common contract suite.

Verify that each adapter:

- Accepts Search Requests

Returns Source Observations

Preserves Source Identifiers

Preserves Retrieval Timestamp

Handles Empty Results

Handles Pagination

Handles Rate Limits

Handles Temporary Failure

Handles Permanent Failure

Reports Health

Does Not Create Canonical Jobs Directly

Provider-specific tests may be added beyond the common contract.

### 17.9 Canonical Verification Tests

Test scenarios should include:

```text
Aggregator Job
→ Matching Employer Posting
→ VERIFIED

Aggregator Job
→ Employer Posting Not Found
→ NOT_FOUND

Multiple Similar Employer Jobs
→ Ambiguous
→ DEFERRED / MANUAL REVIEW

Employer Posting Removed
→ Repeated Verification
→ Correct Lifecycle Handling
```

One failed verification attempt must not automatically mark a job expired.

### 17.10 Deduplication Tests

Deduplication is a critical Phase 1 capability.

Test cases should include:

- Same Job
- Same Employer
- Different Aggregators

Same Job

Different Tracking URLs

Same Requisition

Different Title Formatting

Same Title

Different Locations

Same Company

Same Title

Different Requisition IDs

Reposted Role

Similar Role

Different Organization

Different Jobs

Nearly Identical Descriptions

The system must minimize both:

**FALSE DUPLICATES**

Two distinct jobs incorrectly merged

and

**DUPLICATE LEAKAGE**

One job shown multiple times

### 17.11 Job Change Detection Tests

Test changes such as:

```text
Formatting Only
→ No Material Change

Tracking URL Change
→ No Material Change

Minor Punctuation
→ No Material Change

Compensation Change
→ Material Change

Location Change
→ Material Change

Remote → Hybrid
→ Material Change

Leadership Scope Added
→ Material Change

Major Responsibility Change
→ Material Change
```

The expected JobVersion behavior should be explicit for each fixture.

### 17.12 Discovery Classification Tests

The application must correctly distinguish:

- NEW_POSTING

NEWLY_DISCOVERED_EXISTING_POSTING

PREVIOUSLY_SEEN

MATERIALLY_CHANGED

**REPOSTED**

EXPIRED_OR_REMOVED

**UNRESOLVED**

Example:

Employer Posted:

- October 4

First Seen:

- October 4

No Prior Job Record

Expected:

- NEW_POSTING

Versus:

Employer Posted:

- September 20

First Seen:

- October 4

No Prior Job Record

Expected:

- NEWLY_DISCOVERED_EXISTING_POSTING

This distinction is critical for urgency.

### 17.13 SearchRun Tests

Test:

```text
All Sources Succeed
→ SUCCESS

13 of 14 Sources Succeed
→ PARTIAL

One Source Fails but Useful Results Exist
→ PARTIAL

Most Required Discovery Work Cannot Run
→ FAILED

Equivalent Search Already Running
→ Merge / Skip / Defer according to policy
```

The system must never report:

**NO NEW JOBS**

when the actual condition is:

**SEARCH COVERAGE INCOMPLETE**

### 17.14 Retry and Idempotency Tests

The same task should be safely repeatable.

Test repeated execution of:

- Source Search

Source Observation Processing

Job Creation

Job Version Creation

Job Analysis

Recommendation Generation

Feedback Submission

Watch Creation

Connection Import Commit

Notification Evaluation

Notification Delivery Request

Retries must not produce uncontrolled duplicates.

### 17.15 Baseline Pipeline Test

End-to-end baseline test:

```text
Create Baseline SearchRun
        ↓
Generate Search Plan
        ↓
Execute Mock Sources
        ↓
Create Source Observations
        ↓
Normalize
        ↓
Resolve Companies
        ↓
Deduplicate Jobs
        ↓
Verify Canonical Sources
        ↓
Create Jobs / JobVersions
        ↓
Analyze
        ↓
Match
        ↓
Score
        ↓
Explain
        ↓
Populate Dashboard
```

Verify that baseline opportunities are not automatically labeled as newly posted merely because they were first discovered during baseline initialization.

### 17.16 Incremental Pipeline Test

Test a second SearchRun against the baseline.

Expected behavior:

```text
Unchanged Jobs
→ PREVIOUSLY_SEEN

New Jobs
→ NEW_POSTING or NEWLY_DISCOVERED_EXISTING_POSTING

Changed Jobs
→ MATERIALLY_CHANGED

Missing / Closed Jobs
→ Appropriate Verification Process

Reposts
→ REPOSTED where supported
```

Only jobs requiring new analysis should incur expensive reprocessing.

### 17.17 Reconciliation Test

Simulate delayed indexing.

Example:

Employer Posted:

- Monday

Aggregator First Shows Job:

- Wednesday

Application First Sees Job:

- Wednesday

Expected:

- NEWLY_DISCOVERED_EXISTING_POSTING

rather than automatically:

- NEW_POSTING

Reconciliation should correct earlier uncertain classifications when stronger evidence appears.

### 17.18 Connection Import Tests

Test:

- Valid LinkedIn Export

Malformed File

Missing Columns

Duplicate Connections

Same Person Re-imported

Company Alias Match

Ambiguous Company Match

Unknown Company

Connection Changed Company

Relationship Strength Missing

Relationship strength must remain:

**UNKNOWN**

unless explicitly provided or entered by the user.

### 17.19 Network Scoring Tests

Verify:

```text
0 Connections
→ No network priority boost

1 Relevant Strong Connection
→ Appropriate network priority signal

10 Weak / Irrelevant Connections
→ Must not automatically outweigh one highly relevant connection

Network Change
→ Priority may change
→ Fit must remain unchanged
```

### 17.20 Feedback Tests

Test each feedback action:

**INTERESTED**

GREAT_MATCH

NOT_INTERESTED

**WATCH**

ALREADY_APPLIED

**ARCHIVE**

Verify that:

- the action is stored;
- reason codes are preserved;
- the Recommendation version is preserved;
- user opportunity state changes correctly where applicable;
- historical Recommendation records remain intact.

### 17.21 Learning Guardrail Tests

One isolated feedback event must not create a strong learned preference.

Example:

- One NOT_INTERESTED

Reason:

- WRONG_INDUSTRY

Expected:

- No immediate hard exclusion of that industry.

Repeated consistent feedback may create:

```text
WEAK
→ MODERATE
→ STRONG
```

learned preference evidence according to configured rules.

Learned preferences must remain:

- Explainable
- Reversible
- Versioned
- User-correctable

### 17.22 Watch State Tests

Test:

- Watch Job

Watch Company

Watch Role Family

Material Change to Watched Job

New Job at Watched Company

No Change to Watched Item

Watching an entity may affect monitoring and notification behavior.

It must not artificially increase Fit.

### 17.23 Notification Tests

Test immediate-alert eligibility across combinations of:

- Fit
- Priority
- Confidence
- Freshness
- Watch State
- Quiet Hours
- Previous Notification
- Material Change

Examples:

- High Fit
- Immediate Priority
- High Confidence

```text
New Job
→ Alert Candidate

High Fit
```

Immediate Priority

```text
Low Confidence
→ No Immediate Alert under initial policy

Previously Alerted
No Material Change
→ No Duplicate Alert
```

### 17.24 Notification Re-Alert Tests

Verify re-alert behavior for:

- Material Compensation Change

Location Change

Work-Model Change

Repost

Major JD Change

Priority Increase

Relevant Network Change

Watched Opportunity Change

Minor formatting changes must not trigger repeated alerts.

### 17.25 API Contract Tests

Section 15 API contracts should be validated automatically.

Tests should verify:

- Authentication Required

Authorization Enforced

Required Fields

Enum Validation

Pagination

Filtering

Sorting

Unknown Values

Partial Status

Error Contract

Idempotency

Version Metadata

OpenAPI schemas should be checked for unintended breaking changes.

### 17.26 Security Testing

Before production use, verify at minimum:

- Authentication

Authorization

User Data Isolation

Secret Handling

**TLS**

Private Object Storage

Input Validation

File Upload Validation

No Secrets in Logs

No Secrets in Frontend Bundles

No Secrets in Source Control

Dependency Scanning

Secret Scanning

Testing should also verify that imported network files cannot be retrieved without authorization.

### 17.27 Privacy Testing

Verify that AI requests contain only the data required for the operation.

Examples:

```text
Job Analysis
→ No connection list required

Company Signal Classification
→ No Career Profile required

Requirement Matching
→ Career evidence required
→ Source credentials not required
```

Logs and analytics should be checked for unnecessary personal content.

### 17.28 Performance Testing

Phase 1 is a personal application, so extreme-scale load testing is unnecessary.

Performance testing should focus on responsiveness and pipeline completion.

Test:

- Dashboard Load

Opportunity List

Opportunity Detail

SearchRun Creation

Large Baseline Processing

Connection Import

Batch Job Analysis

Recommendation Generation

Search Health

Interactive pages should use precomputed recommendation data rather than waiting for live AI analysis.

### 17.29 Queue and Worker Testing

Test:

- Worker Restart

Queue Backlog

Task Retry

Task Timeout

Poison / Repeatedly Failing Task

Dead-Letter Handling

Multiple Workers Processing Concurrently

The application should recover without corrupting canonical state.

### 17.30 AI Evaluation Strategy

Traditional pass/fail unit tests are insufficient for AI interpretation.

AI evaluation should test:

- Requirement Extraction

Role Family Classification

Seniority Inference

Role Scope Inference

Negative-Signal Detection

Gap Classification

Requirement-to-Evidence Matching

Unknown Handling

Company Signal Classification

Explanation Grounding

Evaluation should use curated examples with expected outcomes.

### 17.31 Golden Evaluation Set

The canonical Golden Evaluation Set is defined in Section 9.

Section 17 defines how it is used.

The Golden Set should contain representative roles including:

- Excellent Matches

Good Matches

Borderline Matches

Poor Matches

Misleading Titles

Strong Title / Weak Scope

Weak Title / Strong Scope

Sales-Heavy Roles

Hands-On Engineering Roles

Transformation Roles

Product Operations Roles

Technology Operations Roles

TPM / Portfolio Roles

Platform / Developer Productivity Roles

AI Transformation Roles

Security / Governance-Adjacent Roles

Industry-Specific Roles

Ambiguous Job Descriptions

The set should include opportunities that are intentionally difficult to classify.

### 17.32 Golden Set Expected Labels

Each Golden Set item should contain human-reviewed expectations such as:

- Expected Role Family

Expected Seniority Range

Expected Scope

Expected Positive Signals

Expected Negative Signals

Expected Core Requirements

Expected Career Evidence

Expected Gaps

Expected Fit Range

Expected Confidence

Expected Priority Behavior

Expected Explanation Themes

Not every item requires one exact Fit number.

For AI-dependent interpretation, acceptable ranges may be more appropriate.

### 17.33 Golden Set Regression Testing

Run the Golden Set when changing:

- AI Model

Prompt

Analysis Schema

Fit Model

Priority Model

Career Profile

Taxonomy

Requirement Matching Logic

Role-Scope Logic

Compare results against the approved baseline.

A model or prompt upgrade must not be accepted merely because it is newer.

### 17.34 Golden Set Versioning

Track:

- Golden Set Version

Job Fixture Version

Career Profile Version

Expected Result Version

AI Model Version

Prompt Version

Fit Model Version

Priority Model Version

This allows evaluation results to be reproduced.

### 17.35 AI Hallucination Tests

Include adversarial fixtures where the job description does not provide information about:

- Team Size

Budget

Reporting Line

Compensation

Industry Requirement

Travel

Board Exposure

Technical Depth

Expected behavior:

**UNKNOWN**

or:

- MISSING_INFORMATION

The AI must not invent the missing information.

### 17.36 Career Evidence Hallucination Tests

If the Career Profile does not contain evidence of a specific experience, the system must not invent it.

Important distinction:

**NO EVIDENCE FOUND**

does not automatically mean:

**USER DEFINITELY LACKS EXPERIENCE**

The correct classification may be:

**INSUFFICIENT INFORMATION**

### 17.37 Explanation Grounding Tests

Every positive explanation should be traceable to:

```text
Job Requirement
+
Career Evidence
```

Every concern should be traceable to:

```text
Job Requirement
+
Gap / Unknown / Preference
```

Every "Why Now" reason should be traceable to:

- Freshness
- Network
- Compensation
- Location
- Watch State
- Company Context or another valid Priority factor

The explanation generator must not introduce unsupported reasons.

### 17.38 Recommendation Quality Metrics

Evaluation should measure more than model accuracy.

Important quality metrics include:

- Precision of High-Fit Recommendations

Recall of Known Strong Opportunities

False High-Fit Rate

False Low-Fit Rate

Duplicate Opportunity Rate

Incorrect Seniority Rate

Incorrect Role-Family Rate

Unsupported Explanation Rate

Unknown-vs-Gap Error Rate

Immediate Alert Precision

### 17.39 Discovery Quality Metrics

Measure:

- Relevant Opportunities Found

Relevant Opportunities Missed

Unique Opportunities by Source

Time to Discovery

Canonical Verification Rate

Duplicate Rate

Late Discovery Rate

A discovery engine that produces thousands of irrelevant jobs is not successful merely because coverage is high.

### 17.40 User Feedback as Evaluation Data

User feedback becomes an additional real-world quality signal.

Examples:

```text
GREAT_MATCH
→ Positive evidence about ranking quality

NOT_INTERESTED + WRONG_FUNCTION
→ Possible classification / preference issue

NOT_INTERESTED + WRONG_LEVEL
→ Possible scope inference issue

NOT_INTERESTED + TOO_HANDS_ON
→ Possible negative-fit issue

INTERESTED
→ Positive recommendation signal
```

Feedback should supplement, not replace, controlled evaluation.

### 17.41 False-Positive Review

High-Fit jobs rejected by the user should periodically be reviewed.

Ask:

- Was Fit wrong?

Was Career Direction wrong?

Was Role Scope inferred incorrectly?

Was an explicit preference missing?

Was a learned preference missing?

Was Priority wrong while Fit was actually correct?

This distinction prevents the system from "fixing" the wrong component.

### 17.42 False-Negative Review

If the user identifies a strong opportunity that the system ranked poorly or missed entirely, determine:

- Discovery Failure?

Taxonomy Failure?

Source Coverage Failure?

Deduplication Error?

Role-Family Classification Error?

Career Evidence Missing?

Fit Model Error?

Priority Model Error?

This is one of the most valuable evaluation workflows for Phase 1.

### 17.43 Search Coverage Acceptance

For each scheduled run, the application must know:

- What it intended to search

What it actually searched

What failed

Acceptance requirement:

> The system must never represent incomplete source execution as complete market coverage.

### 17.44 Provenance Acceptance

For every recommended opportunity, the system must be able to identify:

- Discovery Source

Canonical Source where available

First-Seen Timestamp

Current Job Version

Job Analysis

Career Evidence Used

Recommendation Version

A recommendation without reconstructable provenance fails Phase 1 acceptance.

### 17.45 Fit Acceptance

Fit must satisfy all of the following:

- Derived from Career Match

Evidence Backed

Independent of Network Strength

Independent of Job Freshness

Independent of Notification Urgency

Independent of User Relationship Count

Versioned

Reproducible

### 17.46 Confidence Acceptance

Recommendation Confidence must:

- Remain separate from Fit

Reflect evidence / information quality

Decrease appropriately when important information is missing

Never be used as a disguised Fit score

The system must support valid states such as:

- Fit: 92
- Confidence: LOW

### 17.47 Priority Acceptance

Application Priority must:

- Start from career relevance

Incorporate timing

Incorporate network advantage

Incorporate compensation

Incorporate location / work model

Incorporate explicit preferences

Use learned preferences only within defined guardrails

Remain explainable

A weak-fit job must not become a top recommendation solely because the user has many connections there.

### 17.48 Unknown-Data Acceptance

The application must visibly distinguish:

**KNOWN NEGATIVE**

**UNKNOWN**

**MISSING INFORMATION**

**NOT APPLICABLE**

Missing compensation must not become zero compensation.

Unknown relationship strength must not become weak relationship strength.

Missing industry evidence must not automatically become lack of industry experience.

### 17.49 Notification Acceptance

Immediate notifications should be:

- Rare Enough to Matter

Strongly Relevant

Timely

Explainable

Deduplicated

A successful notification system is not one that sends the largest number of alerts.

### 17.50 Search Health Acceptance

The Search Health screen must correctly distinguish:

**SUCCESSFUL SEARCH + NO NEW JOBS**

from

**PARTIAL SEARCH**

from

**FAILED SEARCH**

This is a critical trust requirement.

### 17.51 Network Acceptance

Phase 1 network functionality is acceptable when the user can:

- Import LinkedIn Connections Export

Preview Import

Resolve / Identify Import Problems

Commit Import

See Last Refresh Date

See Connections by Company

See Relevant Connections on Opportunities

Use Network as a Priority Signal

Network data must not alter Fit.

### 17.52 Feedback and Learning Acceptance

The user must be able to:

- Mark Interested

Mark Great Match

Mark Not Interested

Select Reasons

Watch

Archive

Mark Already Applied

Inspect Learned Preferences

Confirm Learned Preferences

Correct / Dismiss Learned Preferences

Reset Learned Preferences

One isolated feedback action must not silently create a permanent hard filter.

### 17.53 Security Acceptance

Before production use:

- Authentication must be enabled.

Authorization must be server-side.

Secrets must not exist in frontend code.

Secrets must not exist in source control.

Sensitive storage must be private.

Connection imports must be protected.

Production data must be separated from development.

Material user/configuration actions must be auditable.

### 17.54 Operational Acceptance

The application must expose enough operational information to determine:

- Last Search

Next Search

Search Status

Source Status

Coverage

Queue / Processing Failure

AI Failure

Notification Failure

A failed background process must not remain invisible indefinitely.

### 17.55 End-to-End Acceptance Scenario

Before Phase 1 release, complete at least one controlled end-to-end scenario:

- 1. Configure Career Profile.

2. Configure Search Taxonomy.

3. Configure Bay Area and U.S. Remote scopes.

4. Run Initial Baseline.

5. Verify multiple sources execute.

6. Confirm duplicate postings consolidate.

7. Confirm employer posting becomes canonical where available.

8. Confirm Job Analysis extracts responsibilities and scope.

9. Confirm career evidence is matched.

10. Confirm Fit is calculated deterministically.

11. Confirm Confidence is calculated separately.

12. Import LinkedIn Connections.

13. Confirm network affects Priority but not Fit.

14. Confirm explanation cites valid reasons.

15. Mark opportunities Interested / Not Interested / Watch.

16. Confirm feedback is retained.

17. Run Incremental Search.

18. Confirm only new / changed opportunities receive appropriate processing.

19. Simulate one source failure.

20. Confirm SearchRun becomes PARTIAL and successful results remain available.

21. Introduce a material job change.

22. Confirm new JobVersion and re-evaluation.

23. Trigger an eligible high-priority alert.

24. Confirm notification deduplication.

25. Verify Search Health reflects actual coverage.

The scenario should be repeatable in a controlled test environment.

### 17.56 User Acceptance Review

Before calling Phase 1 complete, the user should review a representative sample of recommendations.

For each sample:

- Would I expect the system to find this?

Is the inferred role level correct?

Does the Fit feel directionally correct?

Does the explanation use my actual experience?

Are the concerns legitimate?

Is the Priority sensible?

Does "Why Now" make sense?

Are the connections relevant?

Would I want to see this opportunity?

The objective is not to force every recommendation to match a predetermined number.

The objective is to validate that the system behaves consistently with the intended decision model.

### 17.57 Phase 1 Quality Gate

Phase 1 should not be considered complete merely because all features exist.

Release requires satisfactory results across four dimensions:

**FUNCTIONAL CORRECTNESS**

Does the workflow work?

**DATA CORRECTNESS**

Are jobs, companies, history, and provenance accurate?

**RECOMMENDATION QUALITY**

Are Fit, Confidence, Priority, and explanations useful?

**OPERATIONAL RELIABILITY**

Can the system run repeatedly without silent failure?

### 17.58 Critical Acceptance Criteria

Phase 1 must satisfy these critical criteria:

- 1. Baseline search establishes a persistent opportunity inventory.

2. Scheduled incremental searches execute three times per day using configurable schedules.

3. Search taxonomy and geographic scopes are configurable without code changes.

4. Jobs from multiple sources are normalized and deduplicated.

5. Employer career sources are used for canonical verification where available.

6. Employer Posted Date and First-Seen Date remain distinct.

7. New, newly discovered, changed, reposted, expired, and unresolved jobs are distinguishable.

8. Material job changes create version history.

9. Master Career Profile evidence is traceable.

10. AI does not fabricate candidate experience.

11. Fit is evidence-based and deterministic.

12. Network strength does not affect Fit.

13. Freshness does not affect Fit.

14. Recommendation Confidence remains separate from Fit.

15. Application Priority remains separate from Fit.

16. Missing information is represented as unknown rather than invented.

17. LinkedIn connection import works without storing LinkedIn credentials.

18. Network information can affect Priority.

19. Feedback reasons are retained.

20. Learned preferences are controlled, explainable, and reversible.

21. Watch state works for jobs and companies.

22. Immediate notifications are deduplicated.

23. Partial source failures remain visible.

24. Successful results survive partial source failures.

25. Search Health accurately represents actual coverage.

26. Recommendations retain source and model provenance.

27. Historical recommendations remain reproducible.

28. Sensitive user and network data are protected.

29. Critical background failures are observable.

30. The Golden Evaluation Set passes the agreed release thresholds.

### 17.59 Definition of Test Completion

Testing is complete for a Phase 1 release candidate when:

- Critical unit tests pass.

Integration tests pass.

API contract tests pass.

End-to-end baseline and incremental tests pass.

Security baseline tests pass.

Golden Evaluation Set meets approved thresholds.

No unresolved critical recommendation-quality defect remains.

No unresolved critical data-integrity defect remains.

No unresolved critical security defect remains.

Search Health accurately reflects known failures.

User acceptance review is satisfactory.

Minor defects may remain only when explicitly documented and judged not to compromise the core Phase 1 decision-support workflow.

### 17.60 Continuous Evaluation After Release

Evaluation does not stop at deployment.

Production usage should continue to measure:

- Strong opportunities missed

Weak opportunities over-ranked

High-Fit rejection patterns

Search-source performance

Discovery latency

Duplicate leakage

Role-scope errors

Explanation errors

Notification usefulness

Learned-preference accuracy

These findings should feed future model, prompt, taxonomy, source, and scoring improvements.

### 17.61 Final Testing Principle

The Phase 1 platform is fundamentally a recommendation system built on top of a search and intelligence pipeline.

Therefore:

**SEARCH QUALITY**

determines what the system sees.

**DATA QUALITY**

determines what the system knows.

**AI ANALYSIS QUALITY**

determines how the system interprets.

**SCORING QUALITY**

determines how the system ranks.

**EXPLANATION QUALITY**

determines whether the user can trust the result.

**OPERATIONAL QUALITY**

determines whether the system works every day.

The final testing principle is:

> Test the complete decision chain, not merely the software components.

A job-search platform that runs reliably but misses the right opportunities has failed.

A recommendation engine that finds the right job but cannot explain why has failed.

A high-quality matcher that silently stops searching one important source has failed.

Phase 1 is successful only when discovery, evidence, matching, prioritization, explainability, and operational reliability work together.

## 18. Implementation Plan and Phase 1 Definition of Done

Section 18 converts the architecture, data model, intelligence model, APIs, security requirements, and acceptance criteria defined in Sections 1–17 into an executable Phase 1 delivery plan.

The implementation strategy is intentionally incremental.

The objective is not to build every capability independently and connect them at the end.

The objective is to establish the complete decision pipeline early:

```text
DISCOVER
   ↓
NORMALIZE
   ↓
RESOLVE
   ↓
VERIFY
   ↓
ANALYZE
   ↓
MATCH
   ↓
SCORE
   ↓
EXPLAIN
   ↓
PRIORITIZE
   ↓
PRESENT
   ↓
LEARN
```

Then strengthen each part through successive implementation increments.

The central implementation principle is:

> Build a thin, working end-to-end decision pipeline first, then progressively improve coverage, intelligence, reliability, and automation.

### 18.1 Phase 1 Delivery Objective

Phase 1 is complete when the application can repeatedly discover relevant opportunities, determine how well they match the user's actual career evidence, prioritize them using contextual signals, explain its reasoning, learn cautiously from feedback, and operate reliably without requiring continuous manual intervention.

Phase 1 must support:

- Persistent Career Profile
- Configurable Search Taxonomy
- Configurable Geographic Scope
- Multiple Discovery Sources
- Scheduled Searches
- Persistent Opportunity Inventory
- Canonical Job Resolution
- Job Deduplication
- Job Version History
- AI Job Analysis
- Requirement-to-Evidence Matching
- Deterministic Fit
- Recommendation Confidence
- Application Priority
- LinkedIn Connection Import
- Network Context
- Opportunity Dashboard
- Opportunity Detail
- Feedback
- Watch State
- Learned Preferences
- Notifications
- Search Health
- Operational Observability
- Security / Privacy Controls
- Golden-Set Evaluation

Phase 1 is not merely a prototype demonstrating AI analysis.

It is a usable personal decision-support application.

### 18.2 Implementation Strategy

Implementation should proceed through vertical slices rather than isolated technical layers.

Avoid:

```text
Build Entire Database
        ↓
Build Entire Backend
        ↓
Build Entire AI Layer
        ↓
Build Entire Frontend
        ↓
Integrate Everything
```

Prefer:

**MINIMUM VERTICAL SLICE**

```text
Discovery → Job → Analysis → Fit → Dashboard

        ↓

EXPAND DISCOVERY
Multiple Sources → Deduplication → Verification

        ↓

EXPAND INTELLIGENCE
Evidence Matching → Confidence → Explanations

        ↓

EXPAND DECISION SUPPORT
Priority → Network → Feedback → Watch

        ↓

EXPAND OPERATIONS
Scheduling → Notifications → Health → Monitoring

        ↓

HARDEN
Testing → Security → Evaluation → Acceptance
```

This exposes architecture problems early.

### 18.3 Implementation Stages

Phase 1 should be implemented through the following major stages:

**STAGE 0**

Foundation and Configuration

**STAGE 1**

Career Intelligence Foundation

**STAGE 2**

Discovery Foundation

**STAGE 3**

Canonical Opportunity Inventory

**STAGE 4**

Job Intelligence

**STAGE 5**

Fit and Recommendation Engine

**STAGE 6**

User Experience

**STAGE 7**

Network Intelligence

**STAGE 8**

Feedback, Learning and Watch State

**STAGE 9**

Scheduling and Notifications

**STAGE 10**

Search Health and Operations

**STAGE 11**

Security and Production Hardening

**STAGE 12**

Evaluation, Acceptance and Release

These are implementation stages rather than rigid calendar sprints.

Several may overlap once their dependencies are stable.

### 18.4 Stage 0 — Foundation and Configuration

Establish the application foundation before implementing significant product behavior.

Deliver:

- Repository Structure
- Application Configuration
- Environment Configuration
- Database
- Migration Framework
- Backend Service
- Frontend Application
- Worker Framework
- Queue
- Object Storage
- Authentication Foundation
- Logging
- Error Handling
- Local Development Environment
- Test Framework
- CI Pipeline

Create explicit environments:

**LOCAL**

**TEST**

**PRODUCTION**

A separate staging environment may be introduced if operational complexity justifies it.

Production data must never become the default development dataset.

### 18.5 Configuration-First Design

Important operating assumptions must be configurable rather than buried in application code.

Configuration should include:

- Search Schedule
- Search Taxonomy
- Role Families
- Title Variants
- Geographic Scopes
- Remote Policy
- Source Enablement
- Source Limits
- Fit Model Version
- Fit Weights
- Priority Model Version
- Priority Weights
- Confidence Rules
- Notification Thresholds
- Quiet Hours
- Learning Thresholds
- Verification Rules
- Retry Rules
- AI Model Selection
- Prompt Versions

Configuration may initially be managed through:

```text
Database-backed settings
+
Version-controlled defaults
```

A full administrative UI is not required for every configuration in Phase 1.

### 18.6 Stage 1 — Career Intelligence Foundation

Implement the Master Career Profile defined earlier in this specification.

The Career Profile should contain structured evidence for:

- Roles
- Employers
- Responsibilities
- Leadership Scope
- Programs
- Products
- Platforms
- Transformation Work
- Technical Domains
- Operational Domains
- Security / Governance Experience
- Industry Exposure
- Business Outcomes
- Scale
- Team Scope
- Financial Scope
- Geographic Scope
- Skills
- Capabilities
- Career Direction
- Preferences
- Constraints

Career evidence should retain provenance.

Example:

- CareerEvidence

```text
├── evidence_id
├── evidence_type
```

├── normalized_capability

```text
├── statement
├── employer
├── role
├── start_date
├── end_date
├── source
├── confidence
└── status
```

The application must distinguish:

**EVIDENCE EXISTS**

from

**NO EVIDENCE FOUND**

It must not interpret missing evidence as definitive lack of experience.

### 18.7 Career Profile Bootstrap

Phase 1 may bootstrap the Career Profile from:

- Resume
- LinkedIn Export / Profile Data supplied by user
- Structured Career Notes
- Manually Entered Evidence
- Previously Curated Career History

AI may assist with extraction.

AI-generated career evidence must be reviewable.

The application must not silently invent:

- Team Size
- Budget Ownership
- Revenue Responsibility
- Technologies
- Industries
- Certifications
- Management Scope
- Executive Reporting Relationships

when those facts are absent.

### 18.8 Career Profile Versioning

The Career Profile must be versioned.

A recommendation should be reconstructable against the Career Profile version used when it was generated.

Store:

- CareerProfileVersion
- CreatedAt
- SourceChanges
- EvidenceChanges
- PreferenceChanges

Future Career Profile improvements should not silently rewrite historical recommendations.

### 18.9 Stage 2 — Discovery Foundation

Implement the search orchestration model defined earlier.

Start with a small number of high-value sources rather than every planned source simultaneously.

The first discovery implementation should prove:

- SearchRun Creation
- Search Plan Generation
- Source Execution
- Source Observation Capture
- Retrieval Timestamp
- Provider Identifier Preservation
- Basic Pagination
- Failure Capture

Every discovery result initially becomes a:

- SourceObservation

not automatically a canonical Job.

### 18.10 Search Taxonomy Implementation

Implement the configurable taxonomy before broad source expansion.

The taxonomy should support:

- Role Families
- Canonical Titles
- Title Variants
- Adjacent Titles
- Positive Keywords
- Negative Keywords
- Seniority Indicators
- Capability Terms
- Industry Terms

Example role families may include:

- Technology Operations
- Product Operations
- Transformation
- Technical Program Management
- Portfolio / PMO
- Platform Leadership
- Developer Productivity
- AI Transformation
- Security / Governance Adjacent
- Enterprise Technology

The taxonomy must evolve independently of application deployment.

### 18.11 Geographic Scope Implementation

Implement geographic search scopes as structured configuration.

Examples:

- BAY_AREA
- US_REMOTE

A scope should support:

- Cities
- Regions
- States
- Remote Eligibility
- Hybrid Rules
- Radius where supported
- Exclusions

The application must not assume that:

- Remote

automatically means:

- Remote from anywhere in the United States.

### 18.12 Initial Baseline Search

The first full search establishes the persistent opportunity inventory.

This is:

**BASELINE SEARCH**

Its purpose is to determine:

**WHAT EXISTS NOW**

not:

**WHAT WAS POSTED TODAY**

Therefore:

```text
First Seen Today
≠
Posted Today
```

Baseline opportunities must preserve both:

- Employer Posted Date
- First-Seen Date

where available.

### 18.13 Stage 3 — Canonical Opportunity Inventory

Once source observations exist, implement:

- Normalization
- Company Resolution
- Job Identity
- Deduplication
- Canonical Verification
- Job Creation
- JobVersion Creation
- Lifecycle State

The canonical inventory becomes the durable representation of market opportunities.

### 18.14 Company Resolution

Create canonical Company records.

Resolve source-specific names such as:

- Google LLC
- Google
- Google Cloud
**GOOGLE**

against the appropriate canonical company representation.

Company resolution should support:

- Exact Match
- Normalized Match
- Alias Match
- Domain Match
- Manual Resolution
- Unresolved State

Do not silently merge genuinely distinct subsidiaries when that distinction matters.

### 18.15 Job Identity and Deduplication

Implement deterministic identifiers where reliable provider IDs or employer requisition IDs exist.

Then supplement with similarity logic using:

- Company
- Title
- Location
- Requisition
- Canonical URL
- Description Fingerprint
- Posting Dates

Deduplication must support:

```text
One Canonical Job
        ↑
Multiple Source Observations
```

Source provenance must remain intact after consolidation.

### 18.16 Canonical Employer Verification

Where possible:

```text
Aggregator Discovery
        ↓
Employer Career Site Verification
        ↓
Canonical Employer Posting
```

The employer source should generally become the canonical representation when sufficiently verified.

Store:

- Canonical URL
- Verification Status
- Verification Timestamp
- Verification Evidence

Failure to locate the employer posting once must not automatically expire the opportunity.

### 18.17 Job Versioning

Material changes must create a new JobVersion.

Examples:

- Compensation
- Location
- Work Model
- Responsibilities
- Leadership Scope
- Requirements
- Travel
- Employment Type

Non-material changes should not create unnecessary versions.

Examples:

- Tracking Parameters
- Whitespace
- Formatting
- Minor Punctuation

Historical versions must remain available.

### 18.18 First Coding Milestone

The first major coding milestone should occur before sophisticated recommendation functionality.

The milestone is:

> A real search produces persistent canonical opportunities visible in the application.

Minimum workflow:

- 1. Create SearchRun.
- 2. Generate SearchRequests.
- 3. Execute at least one real discovery adapter.
- 4. Store SourceObservations.
- 5. Normalize observations.
- 6. Resolve Company.
- 7. Deduplicate Jobs.
- 8. Create Job and JobVersion.
- 9. Display opportunities.
- 10. Display source provenance.

At this milestone, advanced AI scoring is optional.

This milestone validates the foundation on which the rest of Phase 1 depends.

### 18.19 Stage 4 — Job Intelligence

Once canonical JobVersions are stable, implement AI-assisted Job Analysis.

The analysis should produce structured interpretation rather than unstructured commentary.

Extract or infer, with appropriate uncertainty:

- Role Family
- Seniority
- Organizational Scope
- Primary Responsibilities
- Core Requirements
- Preferred Requirements
- Leadership Expectations
- Technical Depth
- Operational Scope
- Transformation Scope
- Industry Requirements
- Positive Signals
- Negative Signals
- Compensation
- Location / Work Model
- Travel
- Ambiguities
- Missing Information

Store the model and prompt versions used.

### 18.20 Structured AI Output

AI analysis should return validated structured data.

Example:

- JobAnalysis

```text
├── role_family
├── seniority
├── scope
```

├── responsibilities[]

```text
├── requirements[]
```

├── positive_signals[]

├── negative_signals[]

```text
├── compensation
├── work_model
├── unknowns[]
```

├── confidence_by_field

```text
├── model_version
└── prompt_version
```

Invalid structured responses should be retried or quarantined.

They must not silently enter the recommendation pipeline.

### 18.21 Requirement-to-Evidence Matching

Implement explicit matching between:

**JOB REQUIREMENT**

```text
↕
```

**CAREER EVIDENCE**

For each meaningful requirement, classify:

- STRONG_MATCH
**MATCH**

PARTIAL_MATCH

POSSIBLE_MATCH

NO_EVIDENCE_FOUND

KNOWN_GAP

**UNKNOWN**

NOT_APPLICABLE

The matching layer is the foundation for explainable Fit.

### 18.22 Stage 5 — Fit and Recommendation Engine

Implement the Fit Model only after Career Evidence and Job Analysis structures are stable enough to support it.

Fit should use the components defined earlier, such as:

- Role / Responsibility Match
- Seniority / Scope Match
- Capability Match
- Leadership Match
- Career Direction Match
- Domain / Industry Match

Fit must be:

- Evidence-Based
- Deterministic
- Versioned
- Reproducible
- Explainable

### 18.23 Fit Isolation

The implementation must enforce:

```text
FIT
=
CAREER MATCH
```

Fit must not depend on:

- Number of Connections
- Relationship Strength
- Posting Freshness
- Application Urgency
- Notification Eligibility
- Compensation Preference
- Search Source
- Watch State

Those signals belong elsewhere.

### 18.24 Recommendation Confidence

Implement Recommendation Confidence independently from Fit.

Confidence reflects the quality and completeness of the information used to reach the recommendation.

Examples:

**HIGH FIT + HIGH CONFIDENCE**

Strong evidence and complete JD

**HIGH FIT + LOW CONFIDENCE**

Strong apparent match but incomplete scope information

**LOW FIT + HIGH CONFIDENCE**

Clear mismatch supported by strong evidence

Valid state:

Fit:

- 92

Confidence:

**LOW**

### 18.25 Application Priority

Implement Application Priority after Fit is stable.

Priority answers:

- HOW MUCH ATTENTION SHOULD THIS OPPORTUNITY RECEIVE NOW?

Priority may incorporate:

- Fit
- Freshness
- Network Advantage
- Compensation
- Location / Work Model
- Explicit Preferences
- Watch State
- Company Context
- Learned Preferences

Priority must remain explainable.

### 18.26 Recommendation Explanation

Generate structured explanations from stored evidence.

Each Recommendation should answer:

- Why It Fits
- What Matches
- What May Be Missing
- What Concerns Exist
- Why Now
- What Changed

Every explanation must be grounded.

The system must never manufacture a compelling narrative merely to justify a score.

### 18.27 Stage 6 — User Experience

Build the primary user workflow around decisions rather than raw search results.

The primary surfaces should include:

- Dashboard
- Opportunity List
- Opportunity Detail
- Search Health
- Network
- Feedback / Preferences
- Settings

### 18.28 Dashboard

The Dashboard should answer quickly:

- What should I look at?
- What is new?
- What changed?
- What deserves immediate attention?
- What am I watching?
- Did the latest search complete successfully?

Suggested sections:

- Immediate Attention
- Strong New Matches
- Recently Changed
- Watched Opportunities
- Recently Discovered
- Search Health Summary

### 18.29 Opportunity List

Support:

- Filtering
- Sorting
- Search
- Fit
- Confidence
- Priority
- Freshness
- Company
- Role Family
- Location
- Work Model
- Watch State
- Application State

The list should use precomputed recommendation data.

Opening the list must not trigger AI processing.

### 18.30 Opportunity Detail

The detail experience should expose:

- Job Summary
- Fit
- Confidence
- Priority
- Why It Fits
- Evidence Matches
- Concerns / Gaps
- Why Now
- Compensation
- Location / Work Model
- Relevant Connections
- Source Provenance
- Job History
- Feedback Controls
- Watch Controls
- Application State

The user should be able to understand why the recommendation exists.

### 18.31 Stage 7 — Network Intelligence

Implement LinkedIn connection import without storing LinkedIn credentials.

Phase 1 should support user-supplied export files.

Flow:

```text
Upload
   ↓
Validate
   ↓
Preview
   ↓
Normalize
   ↓
Resolve Companies
   ↓
Identify Ambiguities
   ↓
Commit
```

Store import provenance and refresh date.

### 18.32 Network Matching

Resolve connections against canonical companies.

Display relevant connections on opportunities.

Network signals may affect:

- Application Priority
- Why Now
- Outreach Suggestions

They must not affect:

- Fit

Unknown relationship strength must remain:

**UNKNOWN**

unless the user explicitly provides or confirms it.

### 18.33 Stage 8 — Feedback, Learning and Watch State

Implement explicit feedback before sophisticated automated learning.

Support:

**INTERESTED**

GREAT_MATCH

NOT_INTERESTED

**WATCH**

ALREADY_APPLIED

**ARCHIVE**

For negative feedback, capture reason codes where useful.

Examples:

- WRONG_FUNCTION
- WRONG_LEVEL
- TOO_HANDS_ON
- WRONG_INDUSTRY
**COMPENSATION**

**LOCATION**

**COMPANY**

ROLE_SCOPE

**OTHER**

### 18.34 Learned Preferences

Learning should begin conservatively.

Pattern:

```text
Repeated Feedback
        ↓
Candidate Preference
        ↓
Weak Evidence
        ↓
Moderate Evidence
        ↓
Strong Evidence
        ↓
User Confirmation where appropriate
```

Learned preferences must be:

- Visible
- Explainable
- Versioned
- Correctable
- Dismissible
- Resettable

A single rejection must not silently create a permanent exclusion.

### 18.35 Watch State

Allow the user to watch:

- Jobs
- Companies

Future expansion may support:

- Role Families
- Search Patterns

Watch state should increase monitoring sensitivity.

It must not increase career Fit.

### 18.36 Stage 9 — Scheduling and Notifications

After the baseline and incremental pipelines are reliable, enable scheduled execution.

Phase 1 target:

**THREE SEARCH RUNS PER DAY**

The exact schedule must be configurable.

Do not hard-code the times into pipeline logic.

### 18.37 Incremental Search

After baseline initialization:

```text
Scheduled Search
        ↓
Compare Against Inventory
        ↓
Classify
```

Possible results:

- NEW_POSTING
- NEWLY_DISCOVERED_EXISTING_POSTING
- PREVIOUSLY_SEEN
- MATERIALLY_CHANGED
**REPOSTED**

EXPIRED_OR_REMOVED

**UNRESOLVED**

Only affected opportunities should receive unnecessary expensive reprocessing avoided.

### 18.38 Notification Engine

Notifications should be generated from recommendation state, not directly from raw discovery events.

Pipeline:

```text
Opportunity Change
        ↓
Recommendation Recalculation
        ↓
Notification Eligibility
        ↓
Deduplication
        ↓
Quiet-Hour Evaluation
        ↓
Delivery
```

Immediate alerts should be reserved for genuinely high-value events.

### 18.39 Notification Channels

Phase 1 should implement at least one dependable notification channel.

Possible channels include:

- Email
- Push
- In-App

The architecture should permit additional channels without changing recommendation logic.

Notification delivery state must be persisted.

### 18.40 Stage 10 — Search Health and Operations

Search Health is a product capability, not merely an engineering dashboard.

The user must be able to determine:

- Last Search
- Next Search
- Search Status
- Sources Attempted
- Sources Successful
- Sources Failed
- Coverage
- Jobs Found
- New Jobs
- Changed Jobs
- Processing Status

The system must distinguish:

**SUCCESS + ZERO NEW JOBS**

from:

**PARTIAL SEARCH**

and:

**FAILED SEARCH**

### 18.41 Operational Workers

Background workers should handle:

- Search Execution
- Observation Processing
- Canonical Verification
- Job Analysis
- Requirement Matching
- Recommendation Generation
- Network Resolution
- Notification Evaluation
- Notification Delivery
- Reconciliation
- Lifecycle Verification

All tasks should support appropriate:

- Retry
- Idempotency
- Timeout
- Failure Recording

### 18.42 Failure Isolation

One failing source must not invalidate successful results from other sources.

Example:

- 14 Sources Planned
- 13 Successful
- 1 Failed

Expected:

SearchRun:

**PARTIAL**

Successful Results:

**PRESERVED**

Failed Source:

**VISIBLE**

Retry:

**ELIGIBLE**

The system must never convert this into:

**NO NEW JOBS**

without exposing incomplete coverage.

### 18.43 Stage 11 — Security and Production Hardening

Before production use, complete the security baseline defined in Section 16.

At minimum:

- Authentication Enabled
- Server-Side Authorization
**TLS**

Secret Management

Private Storage

User Data Isolation

Input Validation

Upload Validation

Dependency Scanning

Secret Scanning

Audit Events

Production / Development Separation

Backup Strategy

Recovery Procedure

LinkedIn connection exports require particular protection because they contain personal network information.

### 18.44 Privacy-by-Design Verification

Review every AI operation for minimum necessary data.

Examples:

- Job Classification

Needs:

- Job Content

Does Not Need:

- Connection Data

Requirement Matching

Needs:

- Job Requirements
- Relevant Career Evidence

Does Not Need:

- Source Credentials

Company Signal Classification

Needs:

- Company / Signal Data

Does Not Need:

- Full Career History

Data minimization should be implemented rather than merely documented.

### 18.45 Stage 12 — Evaluation, Acceptance and Release

Run the Section 17 test strategy against the release candidate.

Required evaluation includes:

- Unit Tests
- Integration Tests
- API Contract Tests
- Pipeline Tests
- Security Tests
- Golden Evaluation Set
- Baseline Search Test
- Incremental Search Test
- Partial-Failure Test
- Network Test
- Feedback Test
- Notification Test
- User Acceptance Review

A release candidate failing critical decision-quality criteria must not be accepted merely because its software tests pass.

### 18.46 Golden Set Release Gate

Run the Golden Evaluation Set against the complete release candidate.

Capture:

- Golden Set Version
- Career Profile Version
- AI Model Version
- Prompt Version
- Fit Model Version
- Priority Model Version
- Results
- Regression Comparison

Material regressions require investigation before release.

### 18.47 Implementation Dependency Chain

The major dependency chain is:

```text
FOUNDATION
    ↓
CAREER PROFILE
    ↓
DISCOVERY
    ↓
CANONICAL INVENTORY
    ↓
JOB ANALYSIS
    ↓
EVIDENCE MATCHING
    ↓
FIT
    ↓
CONFIDENCE
    ↓
PRIORITY
    ↓
EXPLANATIONS
    ↓
USER EXPERIENCE
```

Parallel capabilities can then attach:

**NETWORK**

```text
───────────────→ PRIORITY
```

**FEEDBACK**

```text
───────────────→ LEARNING
```

**WATCH**

```text
───────────────→ MONITORING
```

**SCHEDULING**

```text
───────────────→ DISCOVERY
```

**OPERATIONS**

```text
───────────────→ ALL PIPELINES
```

**SECURITY**

```text
───────────────→ ALL COMPONENTS
```

### 18.48 Recommended Build Order

A practical coding order is:

- 1. Repository / environments
- 2. Database / migrations
- 3. Core domain models
- 4. Career Profile
- 5. Search taxonomy
- 6. SearchRun
- 7. First source adapter
- 8. SourceObservation
- 9. Company resolution
- 10. Job normalization
- 11. Job deduplication
- 12. Job / JobVersion
- 13. Basic opportunity UI
- 14. Employer verification
- 15. Job Analysis
- 16. Requirement extraction
- 17. Career Evidence matching
- 18. Fit
- 19. Confidence
- 20. Recommendation
- 21. Explanation
- 22. Priority
- 23. Dashboard
- 24. Opportunity detail
- 25. Additional sources
- 26. LinkedIn connection import
- 27. Network matching
- 28. Feedback
- 29. Watch state
- 30. Learned preferences
- 31. Scheduler
- 32. Incremental search
- 33. Notification engine
- 34. Search Health
- 35. Operational monitoring
- 36. Security hardening
- 37. Golden Set regression
- 38. End-to-end acceptance
- 39. Production deployment

This order may be adjusted where parallel development is practical, but dependency integrity should be preserved.

### 18.49 Implementation Checkpoints

Use explicit checkpoints rather than waiting until the end to determine whether the architecture works.

**CHECKPOINT 1**

Can one real source create persistent opportunities?

**CHECKPOINT 2**

Can multiple sources resolve to one canonical Job?

**CHECKPOINT 3**

Can a JobVersion be interpreted into structured Job Analysis?

**CHECKPOINT 4**

Can job requirements be matched to actual Career Evidence?

**CHECKPOINT 5**

Can deterministic Fit be reproduced?

**CHECKPOINT 6**

Can the user understand why an opportunity received its Fit?

**CHECKPOINT 7**

Can network context alter Priority without altering Fit?

**CHECKPOINT 8**

Can feedback be captured without uncontrolled learning?

**CHECKPOINT 9**

Can scheduled incremental searches distinguish new from merely newly discovered jobs?

**CHECKPOINT 10**

Can the system survive a partial source failure transparently?

**CHECKPOINT 11**

Can an important new opportunity trigger one appropriate alert?

**CHECKPOINT 12**

Can the complete Section 17 acceptance scenario pass?

### 18.50 Phase 1 Scope Discipline

Phase 1 should resist features that do not materially improve:

- Discovery
- Matching
- Prioritization
- Decision Quality
- Reliability
- Trust

Potential later-phase capabilities should not delay Phase 1 unless required for the core decision workflow.

Examples of capabilities that may be deferred include:

- Automated Job Application Submission
- Automated LinkedIn Messaging
- Autonomous Recruiter Outreach
- Complex CRM Functionality
- Interview Coaching Suite
- Resume Generation per Opportunity
- Cover-Letter Automation
- Multi-User Collaboration
- Recruiter Marketplace
- Enterprise Administration
- Large-Scale Analytics

Interfaces may anticipate future expansion without implementing it prematurely.

### 18.51 Phase 1 Definition of Done

Phase 1 is DONE only when the following capabilities operate together as one reliable system.

#### Discovery

```text
✓ Configurable role taxonomy exists.
✓ Bay Area search scope exists.
✓ U.S. Remote search scope exists.
✓ Multiple discovery sources operate.
✓ Baseline search establishes persistent inventory.
✓ Incremental searches operate automatically.
✓ Scheduled searches run three times per day.
✓ Schedule is configurable.
✓ Search provenance is retained.
```

#### Opportunity Data

```text
✓ Companies are normalized.
✓ Jobs are normalized.
✓ Duplicate postings are consolidated.
✓ Employer postings are canonical where verifiable.
✓ Employer Posted Date and First-Seen Date remain distinct.
✓ Job lifecycle state is maintained.
✓ Material changes create JobVersions.
✓ Historical versions remain available.
```

#### Career Intelligence

```text
✓ Master Career Profile exists.
✓ Career evidence is structured.
✓ Career evidence has provenance.
✓ Career Profile is versioned.
✓ Missing career evidence is not treated automatically as a known gap.
```

#### Job Intelligence

```text
✓ Job Analysis is structured.
✓ Role family is identified.
✓ Seniority / scope is interpreted.
✓ Responsibilities are extracted.
✓ Requirements are extracted.
✓ Positive signals are identified.
✓ Negative signals are identified.
✓ Unknown information remains unknown.
✓ AI model and prompt provenance are stored.
```

#### Matching and Scoring

```text
✓ Requirements map to Career Evidence.
✓ Fit is deterministic.
✓ Fit is evidence-backed.
✓ Fit is versioned.
✓ Network does not affect Fit.
✓ Freshness does not affect Fit.
✓ Confidence is separate from Fit.
✓ Priority is separate from Fit.
✓ Priority can incorporate contextual signals.
✓ Recommendations are explainable.
```

#### Network

```text
✓ LinkedIn connection export can be imported.
✓ Import can be previewed.
✓ Duplicate connections are handled.
✓ Connections resolve to companies.
✓ Ambiguous matches can remain unresolved.
✓ Relevant connections appear on opportunities.
✓ Network can influence Priority.
✓ Network cannot influence Fit.
✓ Relationship strength remains unknown unless known.
```

#### User Decision Workflow

```text
✓ Dashboard identifies important opportunities.
✓ Opportunity list supports useful filtering and sorting.
✓ Opportunity detail explains the recommendation.
✓ User can mark Interested.
✓ User can mark Great Match.
✓ User can mark Not Interested.
✓ User can provide rejection reasons.
✓ User can Watch.
✓ User can Archive.
✓ User can mark Already Applied.
```

#### Learning

```text
✓ Feedback history is preserved.
✓ Learned preferences are controlled.
✓ Learned preferences are explainable.
✓ Learned preferences are reversible.
✓ User can correct learned preferences.
✓ One isolated action cannot create an uncontrolled permanent rule.
```

#### Notifications

```text
✓ Notification eligibility is calculated.
✓ Immediate alerts are limited to appropriate opportunities.
✓ Quiet hours are supported.
✓ Duplicate alerts are prevented.
✓ Material changes may trigger appropriate re-alerts.
✓ Delivery status is retained.
```

#### Operations

```text
✓ Search Health exists.
✓ Last Search is visible.
✓ Next Search is visible.
✓ Source execution state is visible.
✓ Partial searches are distinguishable.
✓ Failed searches are distinguishable.
✓ Background failures are observable.
✓ Retries are controlled.
✓ Critical processing is idempotent.
```

#### Security and Privacy

```text
✓ Authentication is enabled.
✓ Authorization is enforced server-side.
✓ Secrets are protected.
✓ Sensitive storage is private.
✓ Network files are protected.
✓ Production data is separated from development.
✓ Critical actions are auditable.
✓ AI requests follow data-minimization principles.
```

#### Evaluation

```text
✓ Critical unit tests pass.
✓ Integration tests pass.
✓ API contract tests pass.
✓ Baseline pipeline test passes.
✓ Incremental pipeline test passes.
✓ Partial-failure scenario passes.
✓ Golden Evaluation Set meets approved thresholds.
✓ User acceptance review is satisfactory.
```

### 18.52 Phase 1 Non-Negotiable Invariants

The following invariants must hold at release:

```text
FIT
≠
PRIORITY

FIT
≠
CONFIDENCE

FIRST SEEN
≠
POSTED DATE

DISCOVERED
≠
VERIFIED

NO EVIDENCE FOUND
≠
KNOWN GAP

UNKNOWN
≠
NEGATIVE

SOURCE OBSERVATION
≠
CANONICAL JOB

ONE FAILED SOURCE
≠
FAILED ENTIRE SEARCH

PARTIAL SEARCH
≠
NO NEW JOBS

WATCHING
≠
HIGHER FIT

NETWORK STRENGTH
≠
CAREER MATCH
```

These are architectural constraints, not presentation preferences.

### 18.53 Release Blockers

Phase 1 should not be released when any of the following remains unresolved:

- Critical Security Defect
- Critical Data-Integrity Defect
- Critical Recommendation-Quality Defect
- Uncontrolled Duplicate Creation
- Unreliable Fit Reproduction
- Unsupported AI Career Claims
- Silent Search Failure
- Incorrect Search Health Reporting
- Network Affecting Fit
- Unknown Values Converted to Negative Values
- Historical Recommendation Provenance Missing
- Notification Duplication Severe Enough to Reduce Trust
- Golden Set Materially Below Agreed Threshold

### 18.54 Production Readiness Review

Before deployment, conduct one final production-readiness review covering:

- Application
- Database
- Migrations
- Workers
- Queue
- Scheduler
- AI Providers
- Source Adapters
- Authentication
- Authorization
- Secrets
- Storage
- Logging
- Metrics
- Alerts
- Backups
- Recovery
- Notification Channel
- Search Health
- Golden Set

Verify production configuration independently from development configuration.

### 18.55 Initial Production Baseline

The first production execution should be treated as a controlled baseline initialization.

Sequence:

```text
Deploy
   ↓
Verify Configuration
   ↓
Verify Career Profile
   ↓
Verify Search Taxonomy
   ↓
Verify Geographic Scope
   ↓
Verify Enabled Sources
   ↓
Run Baseline
   ↓
Review Search Health
   ↓
Review Deduplication
   ↓
Review Representative Recommendations
   ↓
Approve Scheduled Incremental Searches
```

Do not enable aggressive notifications before baseline quality has been reviewed.

### 18.56 Early Production Observation Period

During initial production use, monitor closely:

- Source Reliability
- Discovery Coverage
- Duplicate Leakage
- False Deduplication
- AI Extraction Errors
- Fit Distribution
- High-Fit False Positives
- Strong Opportunities Missed
- Confidence Calibration
- Priority Behavior
- Notification Frequency
- Feedback Patterns
- Worker Failures
- Processing Latency

Early feedback should be used to calibrate the system without destabilizing the underlying decision model.

### 18.57 Phase 1 Success

Phase 1 succeeds when the user can open the application and confidently answer:

- What strong opportunities exist?

What is genuinely new?

What changed?

Which opportunities best match my background?

Why does the system believe they match?

Where does my experience support the requirements?

Where are the gaps or unknowns?

Which opportunities deserve attention now?

Do I know anyone relevant at the company?

Did today's searches actually complete?

Can I trust that important failures are visible?

If the application cannot answer these questions reliably, Phase 1 is not complete.

### 18.58 Data Assets Created by Phase 1

Phase 1 intentionally creates durable data assets that become valuable in later phases.

These include:

- Career Profile History
- Career Evidence Graph
- SearchRun History
- Source Performance History
- Company Inventory
- Opportunity History
- Job Version History
- Requirement Corpus
- Requirement-to-Evidence Matches
- Recommendation History
- Fit History
- Priority History
- Network-to-Company Mapping
- Feedback History
- Watch History
- Learned Preference History
- Notification History
- Golden Evaluation Set
- Evaluation History

These datasets should be retained with appropriate privacy controls.

### 18.59 Later-Phase Opportunities

The Phase 1 data foundation can support future capabilities such as:

- Resume Tailoring
- Application Strategy
- Recruiter Outreach
- Connection Outreach
- Interview Preparation
- Career-Gap Analysis
- Skill Development Recommendations
- Company Intelligence
- Market Trend Analysis
- Compensation Intelligence
- Career Trajectory Modeling
- Application Outcome Learning
- Interview Outcome Learning
- Offer Comparison
- Long-Term Career Planning

These should build on Phase 1 rather than require rebuilding its core data model.

### 18.60 Avoid Premature Automation

Later phases may introduce more agentic behavior.

Phase 1 should establish trustworthy intelligence before autonomous action.

Progression:

**PHASE 1**

Discover

Analyze

Recommend

Explain

```text
Notify

        ↓

LATER PHASES
```

Prepare

Draft

Coordinate

Act with Approval

Potentially Automate Selected Actions

The system should earn automation through demonstrated accuracy and user trust.

### 18.61 Documentation Required at Phase 1 Completion

The repository should contain sufficient documentation to operate and extend the application.

At minimum:

- Architecture Overview
- Local Setup
- Environment Configuration
- Database Migration Procedure
- Search Adapter Contract
- AI Analysis Contract
- Fit Model
- Priority Model
- Career Profile Schema
- Notification Rules
- Deployment Procedure
- Operational Runbook
- Failure Recovery
- Security Notes
- Golden Set Procedure

The specification itself remains the primary product and architecture reference.

### 18.62 Final Phase 1 Delivery Principle

The implementation must preserve the distinction between:

**WHAT EXISTS**

Discovery

**WHAT THE JOB ACTUALLY REQUIRES**

Job Intelligence

**WHAT THE USER HAS ACTUALLY DONE**

Career Evidence

**HOW WELL THEY MATCH**

Fit

**HOW CERTAIN THE SYSTEM IS**

Confidence

**HOW MUCH ATTENTION THE JOB DESERVES NOW**

Priority

**WHY THE SYSTEM RECOMMENDS IT**

Explanation

**WHAT THE USER THINKS**

Feedback

**WHAT THE SYSTEM LEARNS**

Preferences

Collapsing these concepts into one AI-generated score would undermine the architecture established throughout this specification.

The final implementation principle is:

> Build the smallest complete system that can repeatedly make trustworthy career-opportunity decisions, then improve it from evidence.

Phase 1 does not need to automate the entire job-search process.

It needs to make the most important part of that process dramatically better:

**FIND THE RIGHT OPPORTUNITIES**

**UNDERSTAND THEM CORRECTLY**

**MATCH THEM TO REAL EXPERIENCE**

**PRIORITIZE THEM INTELLIGENTLY**

**EXPLAIN THE REASONING**

**AND NEVER HIDE WHEN THE SYSTEM IS UNCERTAIN OR INCOMPLETE**

## Final Phase 1 Product Statement

Phase 1 — FIND is an AI-powered executive job-intelligence system that continuously discovers opportunities from company career sites, job-search sources, professional/social signals, and company/market intelligence; verifies and deduplicates those opportunities; evaluates them against a structured career profile; incorporates imported first-degree LinkedIn connections as a prioritization signal; and presents new and changing opportunities with separate Fit, Confidence, and Application Priority assessments and evidence-backed explanations.

After the initial market baseline, the platform runs three incremental searches per day, maintains a persistent company and opportunity history, learns from structured user feedback, monitors the health and effectiveness of its information sources, and surfaces the opportunities that deserve attention without automatically applying or contacting anyone.

Phase 1 ends at informed human decision-making. Phase 2 begins when the user decides to pursue an opportunity.
