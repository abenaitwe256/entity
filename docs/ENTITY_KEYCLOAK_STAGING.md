# Proposed Keycloak staging setup

## Status

Keycloak is the proposed OIDC provider for ENTITY; it has not been provisioned. There is no staging issuer, API URL, realm, registry workload identity, or staging credential available yet. No live provider or staging test has been performed.

The authentication service remains provider-neutral. Its current JWT verifier accepts RS256 or ES256, requires exact issuer and audience validation, and reads signing keys from the configured JWKS URL. The staging smoke check validates provider metadata and exercises real staging tokens without printing them.

## Keycloak configuration checklist

1. Provision a separate staging realm on a stable HTTPS hostname. Set ENTITY_OIDC_ISSUER to the exact issuer value in that realm's OpenID Provider Configuration document. Derive ENTITY_OIDC_JWKS_URL from its jwks_uri; do not guess either value. Keycloak documents the realm discovery document and certificate endpoint in its [OIDC endpoint guide](https://www.keycloak.org/securing-apps/oidc-layers) and [server administration guide](https://www.keycloak.org/docs/latest/server_admin/).
2. Configure the API signing algorithm to RS256 or ES256 and confirm the discovery document advertises an accepted algorithm. Confirm the JWKS contains the active public signing key and that the actual access token includes sub, exp, iat, and jti.
3. Configure the ENTITY API audience in the access token. Use a dedicated Audience protocol mapper and verify the resulting aud claim against ENTITY_OIDC_AUDIENCE. Keycloak documents the [Audience mapper](https://www.keycloak.org/docs/latest/server_admin/#_audience) and its access-token behavior.
4. Configure a separate browser client for Authorization Code with PKCE S256 and exact redirect URIs when browser integration begins. Do not enable implicit or direct password grants for the browser.
5. Require an actual second factor for the Owner and Rank 1 reviewers in the staging realm. Use an approved OTP or WebAuthn flow. Add or configure an AMR mapper only after inspecting the access token; set ENTITY_MFA_AMR_VALUES to the observed, trustworthy MFA method values. Confirm auth_time is present and that fresh step-up causes the service's Owner-only audit verification endpoint to accept the token. Keycloak documents [WebAuthn two-factor flows](https://www.keycloak.org/docs/latest/server_admin/) and the [AMR mapper](https://www.keycloak.org/admin-api/protocol-mappers). Do not treat a hard-coded AMR claim as proof of MFA.
6. Create a distinct confidential resource-registry client and service account. Use a short-lived client-credentials token with a separate resource-registry audience and a stable service-account subject. Prefer signed client authentication where supported; if a client secret is used, keep it in the deployment secret manager. Grant no broad realm-administration roles. Provision the same exact subject as an active Rank 6 service identity and set it in ENTITY_RESOURCE_REGISTRY_SUBJECTS. Keycloak documents [service accounts and client credentials](https://www.keycloak.org/docs/latest/server_admin/#_service_accounts).
7. Deploy the service with ENTITY_ENVIRONMENT=staging, PostgreSQL sslmode=verify-full, a private audit HMAC key, the exact issuer/audience/JWKS URL, and both registry settings. The application refuses staging startup configuration without verified PostgreSQL TLS or a trusted registry identity.
8. Provision the test Owner and independent Rank 1 reviewer through the guarded bootstrap. Use staging-only identities. Do not reuse production subjects or credentials.

## Staging smoke check

Install the service in its staging runtime, load its normal ENTITY configuration, then supply these values from the secret manager or protected deployment environment:

- ENTITY_STAGING_BASE_URL: HTTPS base URL of the deployed staging API.
- ENTITY_STAGING_OWNER_SUBJECT: exact provisioned staging Owner subject.
- ENTITY_STAGING_OWNER_TOKEN: short-lived staging Owner access token after fresh MFA.
- ENTITY_STAGING_REGISTRY_TOKEN: short-lived token for the allow-listed registry service account.

Run python -m entity_auth.staging from backend/auth-service. The checker compares issuer and JWKS metadata, requires an accepted asymmetric signing algorithm and usable public key, verifies Owner identity/rank/activity and recent-MFA enforcement, verifies the audit chain, and confirms that the registry token is accepted by the configured audience, subject allowlist, and active Rank 6 account. It never prints token values or response bodies and rejects HTTP redirects.

This is an operator-run staging check, not a GitHub Actions secret workflow. Run it only after the staging service, realm, and protected deployment secrets exist. The current repository has not run it against a live provider.

## Validation still required before production

- Exercise Authorization Code + PKCE with the actual browser client and verify exact issuer, audience, signature, expiry, iat, sub, jti, amr, and auth_time claims from real tokens.
- Rotate the realm signing key in staging and verify the service refreshes JWKS and handles old/new keys as intended.
- Confirm Owner and reviewer MFA enrollment and step-up expiry, not only token claim presence.
- Confirm the registry service account can publish canonical owner, division, classification, and risk values through the protected registry path; test forged owner/risk data and revoked registry identities.
- Rehearse database backup/restore, audit-key recovery, session revocation, migration upgrade, monitoring, and incident response.
- Keep product content, health, financial, device-control, and other consequential operations unavailable until their real backend handlers enforce authorization, consume approval, execute the operation, and audit in the same transaction.
