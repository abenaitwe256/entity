# ENTITY authentication and authorization service

## Status

This is a security foundation for the ENTITY backend. It is not a production-ready identity platform and is not connected to the browser prototype.

| Area | Implemented | Regression coverage | Remaining work |
| --- | --- | --- | --- |
| OIDC bearer verification | Fixed issuer and audience, HTTPS JWKS, RS256/ES256 allowlist, expiry/issue-time/subject/JTI checks and bounded JWKS lookup | Signature, issuer, audience, expiration, subject, algorithm and audience-scoped session-digest tests | Validate claim mapping, key rotation and failure behavior against the chosen identity provider |
| Accounts and rank | Exact OIDC subject must be provisioned; one Owner rank is reserved; only the Owner can initiate account changes | Owner/MFA, non-owner mutation, account target and forged-change cases | Owner recovery procedure, operational review and identity provider enrollment |
| Resource policy | Division, classification, risk and resource owner come from a server-side registry record; unknown resources deny | Client context rejection, critical-risk downgrade attempt, resource-owner scope, cross-division denial | Deploy and connect a dedicated trusted resource registry identity |
| Tasks, shares and access | Time-bounded, resource-scoped tasks; explicit read-only shares; revoked shares deny; regrant reactivates the grant | Expiry, scope, cross-division, revocation and regrant cases | Integrate checks into each authoritative product handler |
| Independent approval | High/critical-risk, highly restricted or execute/administer/revoke requests are bound to task, action, resource, owner, policy version, environment and requester; approvals expire and are consumed once | Forged, self, wrong-rank, stale-policy, revoked-approver and replay cases | Product-specific approval UX and execution integration |
| High-impact administration | Every account/task/share change is Owner-requested, freshly MFA-authenticated, approved by a different active Rank 1 reviewer, payload-bound, short-lived and one-time | Owner authority, second approver, affected-user, stale-MFA, forged and replay cases | Decide whether any operation needs multiple reviewers or an emergency process |
| Sessions | Only an issuer/audience/subject/JTI digest is stored; expiry and revocation are checked; suspending a user revokes sessions | Session collision and revocation tests | Idle timeout, cleanup, refresh-token flow and in-flight request cancellation |
| Audit | HMAC-linked records, serialized PostgreSQL append and Owner verification endpoint | Tampering and generated-ID correlation tests | External checkpoints/WORM retention, key IDs and tested key rotation; tail deletion alone is not detectable |
| Database | Versioned Alembic upgrade replaces bootstrap create_all; migration is additive and forward-only | GitHub Actions applies it to PostgreSQL before tests | Staging rehearsal, backup/restore drill, monitoring and operational rollback procedure |

## Request flow

1. The browser or native app authenticates with the configured OIDC provider. Use Authorization Code with PKCE for a public client. The provider owns passwords, MFA enrollment, and account recovery.
2. The client sends the provider-issued access token to the API as Authorization: Bearer.
3. The service checks the token signature, fixed issuer/audience, expiry, issue time, subject and JTI; looks up the exact provisioned subject; enforces MFA for privileged ranks; and checks a revocable session record.
4. The service accepts only an action, resource type/ID and optional task/approval references at POST /v1/access/check. It loads division, classification, risk, owner and policy version from entity_resource_policies. Client-supplied authorization context is rejected.
5. The policy checks active account, division membership, exact resource ownership, an active task or a read-only share. It denies unknown resources, mismatches, revoked grants and insufficient rank.
6. High/critical-risk or highly restricted access, plus execute/administer/revoke actions, requires recent MFA, an active scoped task, and a distinct eligible approver. Owner requests require an active Rank 1 reviewer; other requests require the Owner. Approval is bound to the exact server policy version and can be consumed once.
7. Administrative changes use a separate two-person flow: the Owner requests a canonical change with fresh MFA; a different active Rank 1 reviewer with fresh MFA approves or rejects it; then the Owner re-authenticates and executes that exact change once. Owner rank, suspension and recovery cannot be changed through these routes.

## Important enforcement boundary

POST /v1/access/check returns an authorization decision. It is not a protected data or operation handler. The current repository has no authoritative product backend that executes a read, mutation, device command, financial action or other protected effect in the same transaction as this decision. Do not expose sensitive data or operations by relying on this endpoint alone. Each future handler must load canonical resource state, invoke the policy, consume any approval, perform the protected operation, and write the audit event atomically.

The resource policy write endpoint is internal. It accepts tokens only for a configured audience and exact allow-listed OIDC subjects that are provisioned as active rank-6 service accounts. The service trusts this backend registry to report correct ownership, division, classification and risk. That registry has not yet been integrated with the browser prototype or deployed.

## Local setup

Use Python 3.11+, PostgreSQL and a dedicated OIDC application. Configure variables from .env.example without committing a filled file. For local development, generate a random audit HMAC key outside the repository. Production configuration requires PostgreSQL sslmode=verify-full and the dedicated resource registry identity.

~~~powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
$env:ENTITY_OIDC_ISSUER = 'https://your-idp.example/'
$env:ENTITY_OIDC_AUDIENCE = 'entity-api'
$env:ENTITY_OIDC_JWKS_URL = 'https://your-idp.example/.well-known/jwks.json'
$env:ENTITY_DATABASE_URL = 'postgresql+psycopg://entity@localhost:5432/entity'
$env:ENTITY_ENVIRONMENT = 'development'
$env:ENTITY_AUDIT_HMAC_KEY = '<load a private random value from a secret manager>'
python -m entity_auth.bootstrap_owner --owner-subject '<exact-owner-oidc-sub>' --initial-reviewer-subject '<different-reviewer-oidc-sub>'
uvicorn entity_auth.main:app --host 127.0.0.1 --port 8080
~~~

The bootstrap command applies Alembic migrations. On a new database it provisions the exact Owner subject as Rank 0 and a different reviewer subject as Rank 1, then records both in the HMAC audit chain. On an existing database it can add one initial active Rank 1 reviewer only when the named Owner is active and no active Rank 1 reviewer exists. This is a one-time deployment-operator trust ceremony because the two-person rule cannot approve its own first reviewer; after that, only an Owner-requested, independently approved change can add or alter accounts. Never include an actual password, API key, bearer token or audit key in source control, logs, CI configuration or issue text.

## Integration plan for the browser prototype

See [ENTITY browser authentication integration](../../docs/ENTITY_AUTH_BROWSER_INTEGRATION.md). In short: keep the static XR prototype public and non-sensitive until there is a trusted application backend. Add OIDC Authorization Code + PKCE, an authenticated identity/session view, and then server-owned action handlers. The browser must not decide rank, resource ownership, division, classification, risk or approval eligibility.

## Known limitations and deployment blockers

- The auth service and the XR browser prototype are not wired together. No OIDC provider or resource registry is configured in this repository.
- The access endpoint does not execute a protected operation atomically. Sensitive product features remain disabled until a trusted backend enforces each decision at the point of use.
- The CI OIDC tests use a generated RSA key and mocked JWKS client; the real provider's issuer, audience, MFA amr/auth_time semantics, key rotation and logout behavior are not verified.
- Production access requires a trusted resource-registry workload, verified PostgreSQL TLS, managed secrets, backups, monitoring and deployment-specific network controls.
- Session expiry follows the OIDC access-token expiry. There is no refresh flow, idle timeout, expired-session cleanup or cancellation of requests already in flight.
- The audit chain detects modifications and interior gaps when checked with the external HMAC key. It cannot detect deletion of the newest tail without an independent external checkpoint. Key rotation and WORM/external anchoring are not implemented.
- The Alembic revision is forward-only because dropping authorization/audit tables is destructive. Restore from a verified backup rather than downgrading. Production rollout still needs a staging rehearsal and restore validation.
- Rate limiting, alerting, security incident response, device trust, Owner recovery drills, delegated roles and production threat modeling remain incomplete.

These limits mean the service must not be described or deployed as production-ready yet.
