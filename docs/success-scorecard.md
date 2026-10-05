# Success scorecard

_Status: draft, awaiting Babu's review. Last updated: 2026-10-05._

How PEJIP measures whether it is working. The README's
[How we measure success](../README.md#how-we-measure-success) section summarises this
page; the detailed acceptance tests behind the product metrics are in sections 17 and
18 of the [FIND specification](spec/FIND-build-specification.md).

## North star

**Three referral-backed interviews per month.**

A referral-backed interview is an interview for a role that PEJIP surfaced, where a
matured connection recommended the candidate.

A **matured connection** is a first-degree LinkedIn connection who currently works at
the hiring company in a position comparable to, or more senior than, the open role.
The match uses the imported connections snapshot (spec section 8). It can be
stale, so every match shows the import date.

A **referral-ready role** is a high-Fit role at a company where the candidate has at
least one matured connection. Network data raises Priority only. It never changes
the Fit score (spec section 13), so a weak-fit role stays weak however well connected
the candidate is.

## The funnel

Each month the north star is fed by this chain. The ratios between steps are
assumptions until real data replaces them.

| Step | Monthly target | Assumed conversion |
| --- | --- | --- |
| Referral-ready roles surfaced | 15 to 20 | |
| Referrals asked for | 12 | about 70% of referral-ready roles |
| Referrals made | 6 | about 50% of asks |
| Referral-backed interviews | **3** | about 50% of referrals |

The candidate records the asks, referrals and interviews in the app, because PEJIP
never contacts anyone itself.

## Three vectors, five analytical approaches

Every metric belongs to one vector. The five approaches form a ladder, not a grid to
fill: each metric starts at the lowest rung and climbs only when there is enough data
for the next rung to be honest. With a single user and a few interviews a month,
prediction from outcome data alone is not meaningful, so the predictive rung is used
where volume exists (roles, searches, CI runs, AI spend).

| Rung | Question | Meaning in PEJIP |
| --- | --- | --- |
| Descriptive | What happened? | The funnel counts and each metric's monthly value. |
| Diagnostic | Why did it happen? | Where the funnel leaked, for example roles with no matured connection, or false high-Fit. |
| Predictive | What is likely to happen? | Whether this month is on track for 3 interviews, AI spend run-rate, and source coverage trend. |
| Prescriptive | What should we do? | A short weekly list, for example "ask this connection about this role". |
| Cognitive / AI | Does the system learn? | The candidate's feedback recalibrates ranking and connection matching, checked by the golden evaluation set before it ships. |

## Metrics

At most twelve metrics, so the scorecard stays readable. "Rung" is the highest
approach each metric supports today or in Phase 1.

### Business value

| Metric | Definition | Target | Rung |
| --- | --- | --- | --- |
| Referral-backed interviews | Interviews per month that came through a matured connection for a PEJIP-surfaced role. | 3 per month | Descriptive, then predictive |
| Referral conversion | Asks to referrals, and referrals to interviews. | Measured, then set | Diagnostic |
| Interested rate | Share of high-Fit roles the candidate marks Interested (README real-world signal). | Rising | Diagnostic |

### Product maturity

| Metric | Definition | Target | Rung |
| --- | --- | --- | --- |
| Referral-ready roles | High-Fit roles with a matured connection, per month. | 15 to 20 | Predictive |
| Warm-path precision | Share of matured-connection matches the candidate confirms are real and willing to refer. | 80% or more | Cognitive |
| High-Fit precision | Share of high-Fit roles the candidate agrees are strong (spec 17.30). | Golden-set baseline | Cognitive |
| Missed strong roles | Strong roles the candidate found elsewhere that PEJIP missed. | Falling | Diagnostic |

### Engineering

| Metric | Definition | Target | Rung |
| --- | --- | --- | --- |
| Search success rate | Share of scheduled searches that complete across every source. | 95% or more | Predictive |
| Data freshness | Age of the newest job data and of the connections import. | Jobs under 24 hours, connections under 30 days | Prescriptive |
| Cost per referral-backed interview | Month-to-date AI spend from the cost guard divided by referral-backed interviews. | Inside the $100 monthly cap | Predictive |
| Delivery health | CI gate pass rate on main, deploys, and change failure rate. | All gates green | Descriptive |

## Phase 2 additions

Phase 2 (PURSUE) adds a tailored first-draft resume for each referral-ready role,
built from the candidate's past resumes. Those resumes are private career data under
policy section 10. When Phase 2 starts, add these metrics:

- **Interview lift:** interview rate for tailored applications compared with untailored
  ones (business value).
- **Edit distance:** how much the candidate edits each draft before sending it; falling
  edits mean the system is learning (product maturity).
- **Unsupported claims:** claims in a draft that do not trace to a real past resume;
  the target is zero (AI quality, policy section 12).

## Review cadence

The scorecard is reviewed weekly from the home-screen summary, and monthly against the
north star. A target changes only with Babu's agreement, recorded in this file.

## Open questions

- How the app decides that a connection's position is "comparable or more senior":
  a seniority ladder from titles (for example VP, SVP, C-level), with the candidate
  confirming ambiguous cases.
- Where the candidate records asks, referrals and interviews (the Watchlist or the
  Opportunity page).
