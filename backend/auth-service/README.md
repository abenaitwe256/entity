# ENTITY identity and authorization service

This is the first backend foundation called for in the product blueprint. It is a small API service, separate from the current browser XR prototype. It must be deployed and reviewed before product features rely on it.

## What is implemented

- OIDC bearer-token verification against a configured HTTPS issuer and JWKS endpoint. The identity provider owns sign-in, password storage, MFA enrollment, and account recovery; this service never receives a password or issues a login token.
- Server-side account provisioning. An identity is denied by default until the Owner provisions its exact OIDC `sub`.
- Rank, division membership, explicit resource shares, time-bounded task assignments, risk checks, and separate approval records in the authorization decision.
- Privileged-account MFA checks and fresh MFA (`auth_time`) checks for approve, execute, administer, and revoke actions.
- API-token session tracking and revocation. Only a SHA-256 digest of the token's OIDC `jti` is stored; the bearer value is never stored. Suspending an account immediately blocks future requests, including still-valid JWTs.
- HMAC-linked audit event chain with an Owner verification endpoint. Keep the HMAC key in a secret manager separate from the database.

No sensitive device, health, financial, or real-world operation endpoint is exposed by this initial service. `POST /v1/access/check` is the policy interface that future backend capabilities must call server-side; a client-side check is never an authorization boundary.

## Request flow

1. The Android/web client authenticates with the configured OIDC provider using Authorization Code + PKCE. Configure provider MFA for Owner and privileged accounts, and enable recent-authentication policy for step-up.
2. The client sends the provider-issued access token as `Authorization: Bearer …` to this API.
3. The API validates signature, issuer, audience, expiry, issue time, and required subject/JWT ID against cached provider JWKS. It then looks up the subject in PostgreSQL, checks suspension/MFA and the token's revocable API session.
4. Protected backend handlers call the authorization policy with the action, division, resource, classification, task, and risk context. Decisions are deny-by-default and are audit-recorded.
5. High/critical execution and approval requests need an independent Owner approval. Delegated administrator approvals are not enabled yet; the requester cannot approve their own request.

The provider's own login session, trusted-device policy, and account recovery remain the provider's responsibility. Revoking an ENTITY API session blocks that access token immediately; it does not claim to sign the user out of the identity provider. Configure recovery so the Owner regains the same stable OIDC `sub`; this service has no secret backdoor that can transfer root authority.

## Local setup

Use Python 3.11+, PostgreSQL, and the provider's OIDC discovery/JWKS values. Set the variables from `.env.example` in your shell or secret store; do not commit a filled `.env`.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:ENTITY_OIDC_ISSUER = 'https://your-idp.example/'
$env:ENTITY_OIDC_AUDIENCE = 'entity-api'
$env:ENTITY_OIDC_JWKS_URL = 'https://your-idp.example/.well-known/jwks.json'
$env:ENTITY_DATABASE_URL = 'postgresql+psycopg://entity@localhost:5432/entity'
$env:ENTITY_ENVIRONMENT = 'development'
$env:ENTITY_AUDIT_HMAC_KEY = '<secret from a password manager or secret manager>'
python -m entity_auth.bootstrap_owner --owner-subject '<exact-owner-oidc-sub>'
uvicorn entity_auth.main:app --host 127.0.0.1 --port 8080
```

Only the one-time bootstrap command creates Rank 0, and it refuses to run when any user already exists. After startup, the Owner can provision ranks 1–6 through `POST /v1/admin/users`. The Owner identity cannot be created through an API request.

## Initial limits

- This is an implementation start, not a claim that the blueprint's access-control requirements are fully complete or production-certified.
- Provider-specific MFA claim mapping and exact `iss`/`aud`/JWKS behavior must be verified against the selected OIDC provider before deployment. The default accepted `amr` values are configurable.
- Database schema evolution, rate limiting, alerting, secret rotation, formal recovery drills, device trust, delegated administrator scopes, independent audit checkpoints/WORM retention, and an Owner console remain to be built. The current HMAC chain detects edits and interior deletions, but cannot detect deletion of the newest tail without an external checkpoint. Until device trust is integrated, sessions are API-token sessions and do not prove a trusted device.
- `create_all` is used only by the one-time bootstrap. Production upgrades need reviewed migrations and backups.
- The service intentionally requires PostgreSQL; SQLite is not suitable for concurrent security decisions, session revocation, or the serialized audit chain.

## Blueprint mapping

This implements the first slice of the blueprint's requirement for secure authentication, privileged MFA, server-side RBAC + task/resource ABAC, deny-by-default checks, revocable sessions, independent approvals, and auditable grants/decisions. It does not yet implement delegated authority or all account-recovery operations.
