# ENTITY authentication and authorization service

## Status

This is a security foundation for the ENTITY backend. It is not a production-ready identity platform and is not connected to the browser prototype. The Original Owner identity design is documented in [governance](../../docs/ENTITY_GOVERNANCE.md), [recovery](../../docs/ENTITY_OWNER_RECOVERY.md), and the [dashboard architecture](../../docs/ENTITY_OWNER_DASHBOARD.md).

| Area | Implemented | Regression coverage | Remaining work |
| --- | --- | --- | --- |
| OIDC bearer verification | Fixed issuer and audience, HTTPS JWKS, RS256/ES256 allowlist, expiry/issue-time/subject/JTI checks and bounded JWKS lookup | Signature, issuer, audience, expiration, subject, algorithm and audience-scoped session-digest tests | Validate claim mapping, key rotation and failure behavior against the chosen identity provider |
| Accounts and rank | Exact OIDC subject must be provisioned; one Owner rank is reserved; only the bound Owner can initiate account changes | Owner/MFA, non-owner mutation, account target and forged-change cases | Provider enrollment, production review and identity proofing for the human-to-OIDC link |
| Original Owner identity | Unique UUID anchor binds the pinned issuer/subject to one Rank 0 account; immutable triggers; no transfer route; bootstrap requires two pinned identities and fresh MFA | Exact subject binding, forged public descriptors, duplicate/replay bootstrap, Owner mutation, MFA, audit and policy-change cases | Live provider proofing, operator controls, runtime/migration role separation and recovery drill |
| Resource policy | Division, classification, risk and resource owner come from a server-side registry record; unknown resources deny | Client context rejection, critical-risk downgrade attempt, resource-owner scope, cross-division denial | Deploy and connect a dedicated trusted resource registry identity |
| Tasks, shares and access | Time-bounded, resource-scoped tasks; explicit read-only shares; revoked shares deny; regrant reactivates the grant | Expiry, scope, cross-division, revocation and regrant cases | Integrate checks into each authoritative product handler |
| Independent approval | High/critical-risk, highly restricted or execute/administer/revoke requests are bound to task, action, resource, owner, policy version, environment and requester; approvals expire and are consumed once | Forged, self, wrong-rank, stale-policy, revoked-approver and replay cases | Product-specific approval UX and execution integration |
| High-impact administration | Every account/task/share change is Owner-requested, freshly MFA-authenticated, approved by a different active Rank 1 reviewer, payload-bound, short-lived and one-time | Owner authority, second approver, affected-user, stale-MFA, forged and replay cases | No emergency override or succession process is implemented |
| Sessions | Only an issuer/audience/subject/JTI digest is stored; expiry and revocation are checked; suspending a user revokes sessions | Session collision and revocation tests | Idle timeout, cleanup, refresh-token flow and in-flight request cancellation |
| Audit | HMAC-linked records, serialized PostgreSQL append and Owner verification endpoint | Tampering and generated-ID correlation tests | External checkpoints/WORM retention, key IDs and tested key rotation; tail deletion alone is not detectable |
| Database | Versioned Alembic upgrade replaces bootstrap create_all; migration is additive and forward-only | GitHub Actions applies it to PostgreSQL before tests | Staging rehearsal, backup/restore drill, monitoring and operational rollback procedure |
| Protected operations | A point-of-use metadata read rechecks locked account, resource, task, membership and share state; consumes approval and audits before returning | Approval replay, cross-division denial, response redaction and audit outcomes | Domain content, health, financial and device-control handlers are not implemented |
| Staging validation | Provider-neutral OIDC/JWKS and API-token smoke checker | Discovery mismatch, algorithm/key compatibility, malformed-key and signing-use tests | No provider or staging URL is provisioned; no live check has run |

## Request flow

1. The browser or native app authenticates with the configured OIDC provider. Use Authorization Code with PKCE for a public client. The provider owns passwords, MFA enrollment, and account recovery.
2. The client sends the provider-issued access token to the API as Authorization: Bearer.
3. The service checks the token signature, fixed issuer/audience, expiry, issue time, subject and JTI; looks up the exact provisioned subject; enforces MFA for privileged ranks; and checks a revocable session record.
4. Clients send only a requested action, resource reference and optional task/approval references. The service loads division, classification, risk, owner and policy version from entity_resource_policies. Client-supplied authorization context is rejected. POST /v1/access/check returns a decision only; the implemented metadata handler is the only protected product read.
5. The policy checks active account, division membership, exact resource ownership, an active task or a read-only share. It denies unknown resources, mismatches, revoked grants and insufficient rank.
6. High/critical-risk or highly restricted access, plus execute/administer/revoke actions, requires recent MFA, an active scoped task, and a distinct eligible approver. Owner requests require an active Rank 1 reviewer; other requests require the Owner. Approval is bound to the exact server policy version and can be consumed once.
7. Administrative changes use a separate two-person flow: the Owner requests a canonical change with fresh MFA; a different active Rank 1 reviewer with fresh MFA approves or rejects it; then the Owner re-authenticates and executes that exact change once. Owner rank, suspension and recovery cannot be changed through these routes.

## Important enforcement boundary

POST /v1/access/check returns a policy decision and is not a data or operation handler. The service now includes a narrow reference product handler, GET /v1/resources/{resource_type}/{resource_id}/metadata. It locks and rechecks canonical resource policy, consumes any approval, audits the result and commits before returning metadata. Administrative account, task and share mutations likewise run through payload-bound two-person authorization. No resource-content, health, financial, device-control or other domain operation is implemented. Do not expose those sensitive capabilities until each domain handler loads canonical state, authorizes and consumes any approval, performs the operation, and audits it in one transaction.

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
$env:ENTITY_ORIGINAL_OWNER_SUBJECT = '<exact-owner-oidc-sub pinned by controlled setup>'
$env:ENTITY_ORIGINAL_OWNER_BOOTSTRAP_REVIEWER_SUBJECT = '<separately verified reviewer sub>'
python -m entity_auth.bootstrap_owner
uvicorn entity_auth.main:app --host 127.0.0.1 --port 8080
~~~

The one-time bootstrap applies migrations, then prompts without echo for short-lived Owner and independent-reviewer access tokens. It verifies both tokens with the configured OIDC verifier, requires exact deployment-pinned subjects and fresh MFA, and rejects an ambiguous database, duplicate or replay attempt. It creates or binds the exact active Rank 0 account, creates the separately verified Rank 1 reviewer when needed, writes the immutable UUID anchor, and records the binding in the HMAC audit chain in one transaction. It accepts no subject arguments and has no HTTP route. The Owner and reviewer must be identity-proofed through a controlled process; names and birthplaces are not proof. See the complete [bootstrap and recovery procedure](../../docs/ENTITY_OWNER_RECOVERY.md). Never include an actual password, API key, bearer token or audit key in source control, logs, CI configuration or issue text.

## Proposed Keycloak staging validation

Keycloak is proposed but not provisioned. Use the [staging setup checklist](../../docs/ENTITY_KEYCLOAK_STAGING.md) and run python -m entity_auth.staging after the issuer, API URL and protected staging tokens exist. No live validation has been performed.

## Integration plan for the browser prototype

See [ENTITY browser authentication integration](../../docs/ENTITY_AUTH_BROWSER_INTEGRATION.md). In short: keep the static XR prototype public and non-sensitive until there is a trusted application backend. Add OIDC Authorization Code + PKCE, an authenticated identity/session view, and then server-owned action handlers. The browser must not decide rank, resource ownership, division, classification, risk or approval eligibility.

## Known limitations and deployment blockers

- No OIDC provider or resource registry is provisioned. Keycloak is the proposed provider, not a configured integration.
- POST /v1/access/check returns a policy decision. The service now has a narrow protected metadata-read handler that rechecks locked policy, consumes approval and audits before returning canonical metadata. No resource-content, health, financial, device-control or other domain operation is implemented.
- CI uses generated RSA keys and mocked JWKS. Provider issuer, audience, MFA amr/auth_time semantics, key rotation and logout behavior remain unverified. A provider-neutral staging smoke checker is available in entity_auth.staging but has not been run because no staging issuer or API URL is provisioned.
- Staging and production require PostgreSQL sslmode=verify-full and a configured trusted resource-registry audience and subject allowlist.
- Session expiry follows the OIDC access-token expiry. There is no refresh flow, idle timeout, expired-session cleanup or cancellation of requests already in flight.
- The audit chain detects modifications and interior gaps when checked with the external HMAC key. It cannot detect deletion of the newest tail without an independent external checkpoint. Key rotation and WORM/external anchoring are not implemented.
- The Alembic revision is forward-only because dropping authorization/audit tables is destructive. Restore from a verified backup rather than downgrading. Production rollout still needs a staging rehearsal and restore validation.
- Rate limiting, alerting, security incident response, device trust, Owner recovery drills, delegated roles, a dashboard, registration/invitation workflows, and production threat modeling remain incomplete.
- The first-Owner bootstrap is implemented but has not been run against a provisioned provider. Founder-to-OIDC identity proofing is an operational ceremony, not an automated identity check. PostgreSQL protection triggers can be disabled by a sufficiently privileged database owner; runtime/migration role separation and independent controls remain to be deployed and tested.
- Recovery intentionally fails closed when the pinned issuer or subject is lost. There is no break-glass, subject rebinding, alternate Owner, succession, or ownership-transfer procedure implemented.

These limits mean the service must not be described or deployed as production-ready yet.
