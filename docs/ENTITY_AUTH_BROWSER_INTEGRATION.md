# ENTITY browser authentication integration plan

## Current state

The checked-in XR experience is a static browser prototype. It renders local scenes and controls but has no sign-in, account, session or server-authoritative data flow. The separate Python auth service is not connected to it. The auth service now has one narrow protected metadata-reference read backed by its trusted resource-policy record; it does not expose product content, device controls or other domain operations. Keep the prototype's current public, non-sensitive behavior until an authoritative backend exists.

## Owner identity and dashboard boundary

The future Owner dashboard must use the server-resolved immutable Owner identity and fresh MFA. The browser cannot establish the Owner from a name or birthplace, write Owner rank, change the Owner anchor, or decide an approval. Review [the dashboard architecture](ENTITY_OWNER_DASHBOARD.md), [governance](ENTITY_GOVERNANCE.md), and [Owner recovery](ENTITY_OWNER_RECOVERY.md). No dashboard UI or broad user-list/registration API is implemented; preserve that boundary until each server handler is authorized and tested.

## Target request path

~~~text
Browser XR
  ├─ OIDC provider: Authorization Code + PKCE
  ├─ ENTITY application backend: session and protected product handlers
  │    ├─ verifies the provider token or a backend session
  │    ├─ loads canonical resource ownership/division/classification/risk
  │    ├─ calls ENTITY authorization policy
  │    ├─ consumes a required independent approval
  │    ├─ performs the protected operation
  │    └─ writes the audit event in the same transaction
  └─ browser receives only the result it is allowed to display
~~~

Do not let the browser send authoritative rank, division, resource owner, classification, risk, task permission or approver identity. It may send a resource reference and the user's requested action; the trusted backend resolves the rest.

## Delivery phases

1. **Provider and deployment decisions.** Select the OIDC provider, register separate browser/API clients, define exact issuer/audience and MFA claim mapping, configure MFA and step-up for Owner/privileged accounts, create a dedicated resource-registry workload identity, and deploy PostgreSQL with verified TLS. Keep secrets in a managed secret store.
2. **Authentication shell.** Add sign-in/sign-out and an account view to the browser. Use Authorization Code + PKCE. Prefer a same-origin backend-for-frontend (BFF) with Secure, HttpOnly, SameSite cookies; if the browser calls the API directly, keep short-lived access tokens in memory and never localStorage/sessionStorage. Add exact-origin CORS, CSP, CSRF protection for cookie-based flows and clear login/session error states.
3. **Identity and session UI.** Read /v1/auth/me for the server-resolved subject, rank, divisions and expiry. Add a list/revoke session view using the authenticated session endpoints. Sign-out revokes the ENTITY session and separately redirects to provider logout when supported; explain that local API revocation does not by itself sign out the provider.
4. **Resource registry integration.** Build trusted backend adapters that publish each resource's stable ID, owner, division, classification and risk to the internal registry endpoint. The adapter uses the allow-listed service identity. The browser never calls this endpoint.
5. **Authoritative product handlers.** The current metadata-reference handler is a narrow example only. For each product action (read/share/edit/delete/execute/device control), implement a backend handler that loads the product resource from its authoritative store, calls policy with the requested operation and scoped task/approval IDs, consumes approvals and performs the operation as one secure unit. Do not use a standalone browser call to /v1/access/check as the gate.
6. **Approval experience.** Show the requester an immutable summary of the server-canonical action and resource. Provide pending approvals only to eligible Owner/Rank 1 reviewers, require fresh provider MFA to decide, prohibit self-approval, and show expiry/rejection/revocation. For irreversible administration, require the independent Rank 1 approval and a fresh Owner execution.
7. **Rollout and verification.** Test denied and allowed flows, stale/replayed approval, revoked sessions/grants, rank changes, cross-division references, resource policy version changes, token expiry, provider key rotation and browser XSS/CSRF. Start with a non-production environment, review logs and alerts, then gate features by server capability. Do not enable sensitive product operations until the handler-level enforcement and recovery procedures pass review.

## Browser security requirements

- Treat the browser as untrusted. Any UI role badge or disabled button is presentation only.
- Keep provider secrets and audit HMAC keys out of browser bundles, repository files, and build-time variables.
- Never log Authorization headers, JWTs, PKCE verifier/challenge secrets, cookies, or full identity claims.
- Do not cache sensitive API responses in service-worker or shared browser caches.
- Use short-lived tokens, explicit logout and visible session expiry. Avoid silent token handling until provider behavior is reviewed.
- Require re-authentication and an independent reviewer for Owner high-impact changes; no front-end Owner mode bypass.
- Enforce authorization again on every backend read and write, including WebSocket messages and future multi-user synchronization events.

## Acceptance checks

- The browser can authenticate and display server-derived identity without holding a long-lived credential.
- Tampering with request fields cannot change server-derived policy context.
- A cross-division or unknown-resource request is denied server-side.
- A revoked session, revoked grant, changed resource policy or consumed approval denies the next protected handler call.
- A high-impact Owner change needs an independent Rank 1 approval and fresh Owner MFA at execution.
- All denied/approved/consumed actions are auditable without recording token or secret values.
