# 0006: Releases and rollback

_Status: implemented. Last updated: 2026-10-05._

## Purpose

Build policy section 15 asks for semantic version tags, a changelog, and a rollback
to the previous release that is one documented command, is exercised in CI, and
runs automatically when the post-deploy health gate fails. This feature supplies the
version and changelog rules, the release workflow, the rollback target selection and
the CI rollback drill, and defines the interface the deploy workflow plugs into.

## Scope

In scope:

- `CHANGELOG.md` and its structure check.
- `ci/release.py`: version, changelog and tag checks, cutting a release, release
  notes, and choosing the rollback target.
- `.github/workflows/release.yml`: run on `main`, tags the release and publishes its
  GitHub Release.
- `ci/rollback_drill.py` and the **Rollback drill** CI job.
- `.github/workflows/rollback.yml`: the one-command production rollback.

Out of scope here, and where it lands:

- The automatic rollback when the post-deploy health gate fails: inside the Deploy
  workflow (ECS circuit breaker with rollback, then putting the service back on the
  previous task definition if any later step fails).
- Building and pushing images, the ECS rollout and its health gate: the Deploy
  workflow ([ADR-0005](../adr/0005-app-hosting-and-continuous-deploy.md)), which `rollback.yml` calls.
- Database migrations: none exist yet. When the first one lands, the drill is
  extended to run the previous release against the database migrated by the
  current build (see [Non-functional considerations](#non-functional-considerations)).

## Design

### Versions and the changelog

- Versions are `MAJOR.MINOR.PATCH` without pre-release suffixes. The version lives in
  one place, `pyproject.toml`; the app reads it from package metadata
  (`pejip.__version__`) and reports it on `GET /healthz`.
- `CHANGELOG.md` starts with `## Unreleased`, followed by releases newest first as
  `## X.Y.Z - YYYY-MM-DD`, each listing at least one change. The newest release is the
  version in `pyproject.toml`, so the two can't drift.
- `python -m ci.release check` enforces this. It runs as the `release-check`
  pre-commit hook, so it runs locally and in the **Pre-commit hooks** CI job on every
  change, docs-only ones included.

### Cutting a release

```mermaid
sequenceDiagram
    participant D as Developer
    participant M as main
    participant R as Release workflow
    D->>D: python -m ci.release prepare X.Y.Z
    D->>M: PR (changelog section + version bump), all gates green, squash merge
    D->>R: gh workflow run release.yml (on main)
    R->>R: ci.release version (changelog valid, version = newest section)
    R->>R: vX.Y.Z does not exist yet
    R->>R: notes X.Y.Z from CHANGELOG.md
    R->>M: tag vX.Y.Z on main's head
    R-->>D: GitHub Release vX.Y.Z
```

`prepare` refuses a version that is not newer than the current one and an empty
Unreleased section. The release workflow runs only on `main`, so only gated code is
released, and refuses a version that is already tagged. It creates the tag itself
rather than reacting to a pushed tag, for two reasons: the deploy role trusts only
`refs/heads/main`, so a later step that adds the `vX.Y.Z` tag to the release's ECR
image can run in the same job; and no one needs push rights for tags.

### Rollback

Continuous deploy ships every main commit that changes the image (the Deploy
workflow's push paths: `src/`, `pyproject.toml`, `Dockerfile`, `.dockerignore`,
`deploy.yml`), tagging the image in ECR with that commit's full SHA. So:

- a commit's **image commit** is the last commit at or before it that touched those
  paths (`python -m ci.release image-commit SHA`); and
- the live image is the image commit of `main`'s head.

The rollback target is the release named by the operator, or else the newest
release whose image commit is not the live one. Comparing image commits means a
docs-only commit after a release doesn't count as a new build, so the default is
always a release that changes what runs.
`python -m ci.release rollback-target --by-image [--version X.Y.Z] --head SHA` prints
the target's `version` and image commit `sha` in `GITHUB_OUTPUT` form.

The one documented command is the Rollback workflow, `workflow_dispatch` on `main`:

```sh
gh workflow run rollback.yml                     # the release before the live one
gh workflow run rollback.yml -f version=0.1.0    # a named release
```

```mermaid
sequenceDiagram
    participant O as Operator
    participant R as Rollback workflow
    participant D as Deploy workflow
    participant E as ECS pejip-prod
    O->>R: gh workflow run rollback.yml [-f version]
    R->>R: rollback-target --by-image (release, image SHA)
    R->>D: workflow_call image_tag = image SHA
    D->>D: image exists in ECR? (else fail)
    D->>E: new task definition revision, roll service
    D->>D: health gate: /healthz ok and version = release
    D-->>E: on failure, back to the previous revision
    D-->>O: email result
```

- `rollback.yml` must not use the Deploy workflow's own concurrency group
  (`deploy-refs/heads/main`), or it would wait on the deploy it calls; it uses
  `rollback`. It grants the called workflow `id-token: write` for the main-only
  deploy role.
- The next merge to `main` that changes the image deploys again, so a rollback holds
  until the fix merges.
- **Keeping release images:** the ECR lifecycle policy keeps the last 100 images
  tagged `v*` and the last 10 of the rest. The Release workflow's **Tag the release
  image** job (once `DEPLOY_ENABLED` is on) finds the release's image commit, waits
  for a deploy of it still in flight, and adds the `vX.Y.Z` tag by re-putting the same
  manifest, so the digest is unchanged and the image outlives the 10-image window.
  Releases cut before deploys were enabled (v0.1.0) have no image to roll back to.

### Rollback drill

The **Rollback drill** CI job runs on every app change, after **System tests**:

1. Picks the rollback target for this commit with `rollback-target --fallback-parent`.
   Until the first release is tagged there is none, so the commit before this one
   stands in.
2. Builds the target's wheel from its commit in a separate worktree and installs it,
   and installs this build's wheel from the System tests job, each in its own venv.
3. `python -m ci.rollback_drill` serves this build until `/healthz` is healthy, swaps
   it for the target and checks it is healthy and reports the target's version, then
   rolls forward to this build and checks it again.

A failure in any step fails the job, which is a required check.

## Interfaces

- `python -m ci.release check | version | prepare X.Y.Z | check-tag vX.Y.Z | notes X.Y.Z |
  image-commit SHA | rollback-target [--version X.Y.Z] [--head SHA]
  [--fallback-parent | --by-image]`; exit code 1 and
  a `::error::` annotation on any broken rule.
- `python -m ci.rollback_drill --current PY --previous PY --previous-version X.Y.Z
  [--port 8000] [--timeout 30]`.
- Tags `vMAJOR.MINOR.PATCH`, annotated or lightweight; other tags are ignored.
- `GET /healthz` returns `{"status": "ok", "version": "X.Y.Z"}` (existing).

## Data model

No stored data. `CHANGELOG.md`, the `pyproject.toml` version and git tags are the
release record.

## Non-functional considerations

- **Reliability:** rollback is exercised on every app change, not only when needed.
  Once the app has a database, each migration must work with the previous release
  (policy section 15), and the drill is extended to apply this build's migrations to
  a scratch database before starting the previous release on it.
- **Security:** the release workflow is the only job with `contents: write`, runs only
  on `main` and refuses a version that is already released. The release tooling runs git with
  fixed arguments and no shell.
- **Tests:** `tests/unit/test_release.py` covers every rule; the integration tests run
  rollback target selection against a real git repository and the drill against real
  app processes, including a build that exits, one that never gets healthy and one
  that ignores terminate.

## Alternatives considered

- Release automation tools (release-please, semantic-release): they need commit
  message conventions and more third-party code in the release path; a small script
  with tests is enough for one app.
- Retagging release images in ECR at release time: needs the deploy role in the
  release workflow. Resolving the image by commit SHA avoids that.
- Rolling back by reverting the commit: slower (a full CI run) and doesn't help when
  the previous release is the one that must run now.

## Open questions

None.
