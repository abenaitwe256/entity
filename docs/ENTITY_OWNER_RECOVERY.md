# ENTITY Original Owner bootstrap and recovery

## Status

The service contains a one-time Owner bootstrap command and immutable binding checks. No OIDC provider, deployment staging URL, real Owner account or recovery drill has been provisioned or validated. This document defines the safe operating procedure; it does not claim a live identity-provider integration.

## Before first bootstrap

1. Provision the approved OIDC realm and API client over HTTPS. Confirm the exact issuer, audience, JWKS endpoint and trusted MFA claim behavior from actual provider documentation and staging tokens.
2. Independently verify the intended human Owner using an approved, private identity-proofing process. The governance record's name and country of birth are not authentication or recovery evidence.
3. Through a controlled deployment approval, pin the exact OIDC subject in `ENTITY_ORIGINAL_OWNER_SUBJECT`. Pin a separately identity-verified reviewer in `ENTITY_ORIGINAL_OWNER_BOOTSTRAP_REVIEWER_SUBJECT`. Protect both deployment settings; never place access tokens or secret values in source control.
4. Enroll the Owner and independent reviewer in the provider's strong MFA method. Obtain short-lived access tokens that prove the exact API audience, issuer, subject, and fresh MFA step-up.
5. Start from a new database. If accounts already exist, the bootstrap refuses ambiguous state; stop and perform a documented operator review instead of deleting or editing accounts to force success.

## Run the controlled bootstrap

From the auth-service deployment environment, after loading its normal settings from the secret manager:

```sh
python -m entity_auth.bootstrap_owner
```

The command applies the forward-only migrations, prompts without echo for the Owner and reviewer tokens, validates both through the configured OIDC verifier, checks the pinned subjects and fresh MFA, and commits the initial Owner identity and reviewer in one transaction. The database advisory lock serializes concurrent attempts. A unique anchor key and immutable triggers prevent replay, reassignment, account demotion or deletion through normal SQL paths. The Owner anchor is tied to a generated UUID and the configured issuer/subject. A successful bootstrap writes `identity.original_owner_bound` to the HMAC-linked audit trail.

Do not paste a token into shell arguments, CI logs, issues, chat, or this repository. The prompt keeps tokens out of command-line history and ordinary terminal echo, but operators must still use a protected host and short-lived tokens. A deployment must separately control who can run the process and read database or secret-manager credentials.

## Recovery after loss of an authenticator

1. Use only the configured identity provider's documented, independently verified account-recovery procedure. ENTITY does not recover an OIDC password or MFA device.
2. Re-authenticate to the same issuer with the exact existing Owner subject and freshly enrolled MFA. Then review the Owner identity in `/v1/auth/me`, revoke no-longer-needed ENTITY API sessions, and verify the audit chain.
3. If the issuer or subject has changed, stop. The service intentionally denies the new identity; do not edit `ENTITY_ORIGINAL_OWNER_SUBJECT`, create another rank-0 user, modify the immutable anchor, use the public founder details, or ask an administrator to impersonate the Owner.
4. Preserve the database, deployment settings, audit HMAC key and provider evidence. Restore only from verified backups under a two-person operational review. Changes to trust configuration need a separately documented, Owner-authorized and independently reviewed deployment change.

There is no implemented subject-rebinding, break-glass login, alternate Owner, or succession process. If the same verified subject cannot be recovered, the system remains locked against Owner-only operations until a future explicit succession design has been reviewed and implemented. Do not bypass the immutable trigger.

## Operations that still need validation

- Prove the provider emits trustworthy MFA and `auth_time` claims after a real step-up.
- Exercise token expiry, session revocation and recovery from a revoked/compromised authenticator in staging.
- Rehearse database backup/restore, audit HMAC key recovery, migration upgrade, monitoring and operator identity-proofing.
- Separate runtime database privileges from the migration/table-owner role and test that the runtime role cannot disable the Owner protection triggers.
- Establish external audit checkpoints or WORM retention to detect deletion of the newest audit-chain tail.
