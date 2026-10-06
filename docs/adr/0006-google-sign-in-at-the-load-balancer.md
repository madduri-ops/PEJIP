# ADR-0006: Require Google sign-in at the load balancer, with an allow-list check in the app

**Status:** Accepted (2026-10-05)

## Context

`https://job-search.zephyr-mcg.com` is public ([ADR-0005](0005-app-hosting-and-continuous-deploy.md)).
PEJIP is a personal tool for one person, and the career data it will hold is
private (build policy section 10), so nobody but Babu may use it. Babu asked for
"Sign in with Google", accepting only their own Google account.

Google lets any Google account sign in to an OAuth client, so Google alone cannot
limit access to one person. The repository is public, so no client secret or
personal address may be committed. The post-deploy health gate polls `/healthz`
from GitHub and must keep working.

## Decision

- **Sign-in at the edge:** the ALB's HTTPS listener runs an `authenticate-oidc`
  action against Google (issuer `https://accounts.google.com`, scope
  `openid email`) before forwarding. Sessions last 12 hours
  (`sign_in_session_seconds`). The callback is
  `https://job-search.zephyr-mcg.com/oauth2/idpresponse`, handled by the ALB.
- **Health path stays open:** a listener rule forwards `/healthz` without sign-in.
  (2026-10-06: a second rule does the same for the signed-out page and its
  stylesheet, so Sign out does not sign Babu straight back in; design 0009.)
- **One account, checked in the app:** the ALB passes the signed-in user's claims
  in `x-amzn-oidc-data`, an ES256 JWT it signs. `pejip.auth` verifies the signature
  with the ALB's public key for the token's `kid`, requires the `signer` to be
  PEJIP's own ALB ARN and the token to be unexpired, and admits only a
  Google-verified email equal to `PEJIP_AUTH_ALLOWED_EMAIL` (since
  [ADR-0010](0010-one-deployment-separate-accounts.md), an email in the account
  registry `PEJIP_AUTH_ACCOUNTS`). Others get 401 (no or
  bad token) or 403 (another account). Without these settings every route but
  `/healthz` answers 503: the app fails closed.
- **Secrets stay out of the repo:** the OAuth client ID and secret live in SSM
  Parameter Store (`/pejip/google-oauth/*`, SecureString with `alias/pejip`),
  created by Babu and read by Terraform. The allowed address is the sensitive
  variable `sign_in_email` (defaults to `alert_email`), passed at apply time.
- **Belt and braces at Google:** the OAuth consent screen stays in Testing with
  Babu as the only test user, so Google itself refuses other accounts too.
- **CI exercises the real check:** `ci/alb_token.py` signs tokens with a
  throwaway key the way the ALB does. Unit, integration and system tests and DAST
  run the app with sign-in on and that key; ZAP sends a signed token on every
  request.

## Consequences

- No user table, passwords or session code in the app; the ALB handles the
  sign-in flow and cookies.
- The app trusts `x-amzn-oidc-data` only from PEJIP's ALB (signer check), and
  tasks only accept traffic from the ALB's security group.
- The ALB's security group now allows outbound HTTPS so it can reach Google's
  token and user info endpoints.
- Terraform state holds the client secret (as it holds every listener setting);
  state is in the encrypted `pejip-tfstate-*` bucket. The plan role may read the
  two SSM parameters, which adds nothing it could not already read from state.
- Adding a second person means changing the app's single-address setting to a
  list; deferred until needed.
- There is no sign-out button yet; the ALB session cookie expires after 12 hours.

## Alternatives considered

- **Sign-in in the app (OAuth library and sessions):** more code to secure and
  test, and the app would need its own session store. Rejected.
- **ALB only, no app check:** any Google account could get in. Rejected.
- **Amazon Cognito with Google as a federated IdP:** an extra service and cost
  for one user, with the same need for an allow-list. Rejected.
- **Restricting by IP:** Babu's address changes and VPNs are common. Rejected.
