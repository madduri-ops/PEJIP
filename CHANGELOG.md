# Changelog

All notable user-visible changes. Versions follow [semantic versioning](https://semver.org/);
releases are tagged `vMAJOR.MINOR.PATCH` (build policy section 15).

## Unreleased

### Added

- First end-to-end FIND slice as the `pejip` command line tool: fetches roles from
  configured Greenhouse and Lever company boards, filters them by the search
  taxonomy and geography, analyses each with Claude, scores Fit, Confidence and
  Priority with deterministic rules, and writes a Markdown digest that explains
  every ranking with cited evidence.
- `pejip purge`, `pejip export` and `pejip delete-all` for retention, export and
  deletion of stored data.
- The ranking pipeline is scored against the golden evaluation set in CI, from
  recorded model output on every change and live when prompts or AI code change.
