# ENTITY governance and Original Owner identity

## Designated Original Founder and Owner

ENTITY records the following governance identity:

- **Full name:** Abenaitwe Dickson
- **Country of birth:** Uganda
- **Designation:** Original Founder and Owner of ENTITY
- **Authority:** Highest governing Owner authority within ENTITY

These descriptors document the designation. A name, birthplace, nationality, public biography, or other discoverable fact is never an authentication factor, proof of account ownership, recovery secret, or basis for an OIDC subject binding.

ENTITY's complete division structure is the permanent 14-division register in [ENTITY_DIVISION_REGISTER.md](ENTITY_DIVISION_REGISTER.md). All divisions belong to one unified ecosystem.

## Identity is distinct from authority

Authentication proves that a request presents a token accepted from the configured OIDC issuer for a particular subject. It does not, by itself, prove that the subject belongs to the designated human Owner. The controlled identity-proofing and bootstrap process must separately establish that link using trustworthy, non-public evidence and independent review. The public descriptors above must not be used for that proof.

Authorization is a separate server-side decision. The service recognizes original Owner authority only when all of these agree:

1. The active account has the reserved Owner rank.
2. The token has been verified against the configured issuer and API audience.
3. The OIDC subject matches the deployment-pinned Owner subject.
4. The immutable Original Owner anchor links that issuer and subject to the exact account and internal UUID identity.
5. The privileged request has the required MFA; Owner-only and other sensitive operations require fresh step-up MFA.
6. The requested operation passes the normal resource, task, policy, independent-approval and audit checks.

A display name, birthplace claim, client role, rank claim in a token, or client-supplied policy context cannot create Owner authority. The OIDC provider is responsible for passwords, MFA enrollment and its own account recovery. ENTITY stores no Owner password or shared credential.

## Permanent authority safeguards

- Ordinary provisioning only permits ranks 1 through 6. Rank 0 can be established only through the controlled first-Owner bootstrap; a database uniqueness constraint permits at most one rank-0 account.
- The bootstrap creates a random immutable internal identity UUID and binds it to the exact Owner account, configured issuer and pinned OIDC subject. It records the independently authenticated review and the binding as separate events in the same HMAC-linked audit transaction.
- Application authorization denies a rank-0 account that lacks the correct anchor. Admin change handlers reject changes to the Owner account, and PostgreSQL triggers reject updates/deletion of the bound Owner account or anchor.
- The anchor cannot be changed by ordinary role assignment, suspension, policy or division membership changes. These mechanisms do not provide an Owner transfer path.
- Sensitive account, task and share changes continue to require Owner fresh MFA, a different active Rank 1 reviewer, a payload-bound approval and audit. Owner requests cannot approve themselves.
- No hardcoded Owner account, password, recovery code or universal credential is included.
- There is no succession or ownership-transfer endpoint. A future legitimate succession process must be explicit, strongly authenticated, independently reviewed, bound to an exact proposed change and written to the tamper-evident audit chain before it could be implemented.

The app-level and database-trigger safeguards protect against normal service operations and ordinary direct SQL changes. A database superuser or table owner can disable triggers or change deployment configuration; independent operational controls, runtime/migration role separation and external audit checkpoints are not yet configured. This limitation must be addressed and tested before production deployment. ENTITY cannot claim protection against a fully privileged infrastructure administrator.

## Bootstrap and recovery

Bootstrap is a guarded, operator-run two-identity setup ceremony, not an HTTP route. It requires an exact deployment-pinned Owner subject, a separately pinned reviewer subject, verified OIDC access tokens, and fresh MFA for both. The reviewer must independently confirm the identity-proofing and exact binding through the controlled deployment process; token presence alone does not verify the person's civil identity. It takes a PostgreSQL transaction lock, rejects replay, fails if accounts exist in an ambiguous state, writes the Owner anchor and reviewer provision atomically, and appends an audit event. The CLI reads tokens through a no-echo prompt; tokens are not command-line arguments. See [Owner recovery](ENTITY_OWNER_RECOVERY.md).

If the pinned Owner identity cannot be authenticated, ENTITY fails closed. Recovery must use the OIDC provider's independently verified process and retain the same issuer and subject. A changed subject is not silently rebound. ENTITY currently has no alternate-account takeover, break-glass bypass or succession implementation.

## Implementation status

The code and regression tests implement the immutable account/anchor binding, pinned OIDC subject checks, fresh-MFA bootstrap, independent initial reviewer, replay prevention, reserved Owner rank, role-change denial, and audit recording. They do not verify a live human identity against an OIDC account. No provider or staging environment has been provisioned; the out-of-band identity proofing ceremony and database operational controls remain deployment dependencies. This work is not production readiness evidence.
