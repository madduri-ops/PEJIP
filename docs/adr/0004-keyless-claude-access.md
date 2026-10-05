# ADR-0007: Keyless Claude access through Workload Identity Federation

**Status:** Accepted (2026-10-05)

## Context

The build policy (section 5) says cloud access uses OIDC and no long-lived keys. The
first Claude caller, the live golden-set evaluation in CI, was set up with an
`ANTHROPIC_API_KEY` repository secret: a static key in the Default workspace that
expires around 2027-01-03 and has to be rotated by hand. The app on ECS will call
Claude too, and would need the same kind of key in AWS.

The Claude API now supports Workload Identity Federation: a workload presents a
short-lived token from an identity provider it already has, and Anthropic returns a
short-lived Claude token bound to a service account. GitHub Actions issues OIDC
tokens to jobs, and AWS STS issues web identity tokens to IAM roles
(`sts:GetWebIdentityToken`, outbound identity federation).

## Decision

- No Claude API key exists in GitHub, AWS or the repository. CI and the app
  authenticate with Workload Identity Federation only.
- **Identity sources:** GitHub Actions OIDC for CI jobs; AWS STS web identity tokens
  for the ECS task role. EKS-style projected tokens are not used (PEJIP runs on ECS).
- **Anthropic resources** (created by Babu in the Claude Console, Settings >
  Workload identity): one service account per workload (`pejip-ci`, `pejip-app`),
  one issuer per provider, and one rule per workload. Rules use the narrowest match
  available (GitHub: this repository and owner ID, pull request events only; AWS: the
  exact ECS task role ARN), audience `https://api.anthropic.com`, scope `workspace:developer`
  and a 10-minute token lifetime.
- **Code:** `pejip.claude_auth` builds the arguments for the SDK's
  `WorkloadIdentityCredentials`, picking the source from `PEJIP_CLAUDE_IDENTITY`. A
  workload that federates refuses to start if `ANTHROPIC_API_KEY` or
  `ANTHROPIC_AUTH_TOKEN` is also set, because the SDK would silently prefer the key.
- **AWS:** Terraform turns on outbound web identity federation for the account and
  defines `pejip-claude-federation`, a policy that only allows tokens for Anthropic,
  signed RS256, lasting at most 15 minutes. It is attached to the ECS task role.
- The non-secret IDs (organization, rule, service account) are GitHub repository
  variables and ECS task environment variables, not secrets.

## Consequences

- No key to rotate or leak; the January 2027 expiry stops mattering once the old key
  is deleted.
- Outbound web identity federation is an account-wide switch in the account PEJIP
  shares with KRI. It grants nothing on its own (a principal still needs
  `sts:GetWebIdentityToken`), it changes no KRI resource, and Terraform protects it
  from being switched off by a destroy.
- Federated tokens carry the workload's identity, so the Console's authentication
  history shows which workload called Claude.
- Each identity token is accepted once, so token providers fetch a fresh one on every
  refresh instead of re-reading a file.
- Developers on their own machine use `ant auth login` or a personal key; that path
  is unchanged because `PEJIP_CLAUDE_IDENTITY` is unset there.
