# ENTITY authenticated Owner dashboard architecture

## Scope and status

This document plans the authenticated Owner dashboard. No browser dashboard, registration workflow or new dashboard endpoint is implemented. The browser prototype does not authenticate and must not present sensitive controls as operational.

The dashboard is a client of authoritative backend handlers, never an authority source. It must not decide whether a user is the Owner, set roles, infer resource ownership, supply risk/classification, waive MFA, or approve its own actions.

## Identity and request boundary

1. The eventual application uses OIDC Authorization Code with PKCE. Prefer a same-origin backend-for-frontend with Secure, HttpOnly, SameSite cookies; otherwise keep short-lived access tokens in memory.
2. The API resolves the verified issuer/subject to the provisioned account and immutable Original Owner identity. Owner routes require the anchor and fresh MFA.
3. Backend handlers load canonical records from PostgreSQL or an authoritative product service, enforce policy and task scope, require any independent second approval, consume approvals once, perform the action and audit within a transaction.
4. The API returns only the minimum information authorized for that Owner. Exact-origin CORS, CSP, CSRF protections for cookie flows, rate limits and security monitoring are required before browser exposure.

## Planned dashboard capabilities

| Capability | Current server support | Dashboard status and required boundary |
|---|---|---|
| View registered users | No Owner-only user-list endpoint | Not exposed; add a paginated, audited Owner handler with field-level minimization. |
| Approve/reject registration requests | Registration-request workflow not implemented | Not exposed; implement explicit state transitions, fresh MFA, independent review where policy requires it, and audit. |
| Invite users | Invitation workflow not implemented | Not exposed; use single-use expiring invitations bound to the intended identity and role request. |
| Assign/revoke roles | Limited user provisioning, update and suspension routes exist behind Owner fresh MFA and independent Rank 1 approval | No dashboard UI; preserve exact payload binding, prohibit rank 0 assignment, self-approval and Owner modification. |
| Assign tasks and permissions | Existing task assignment/revocation routes use canonical payloads and independent approvals | No dashboard UI; constrain each task by division, resource, permissions and expiry. |
| Review security events and audit records | Audit-chain verification endpoint exists; general audit search/listing is not implemented | No dashboard UI; add a read-only, paginated, access-controlled view with external checkpoint status. |
| Manage independent approval requirements | Core risk/action approval rules are server-defined; no management endpoint | Not exposed; policy changes require explicit versioned proposals, independent approval and audit. |
| Review ENTITY EVOLVE upgrades | Upgrade proposal/execution backend not implemented | Not exposed; require Owner approval and independent review before any code or model change is deployed. |
| Monitor the 14 divisions and connected services | No division/service health inventory endpoint; `/healthz` is a basic service probe | Not exposed; build authenticated, source-backed status handlers and keep public health output non-sensitive. |

The limited administrative routes already present remain backend APIs with their own authorization. A dashboard must not be built around raw database access or a standalone `/v1/access/check` result. Do not expose the capabilities marked "not exposed" until each handler and its negative tests exist.

## Security acceptance tests before UI integration

For each operation, test unauthenticated access, non-Owner access, Owner with stale or absent MFA, forged Owner identity, wrong rank, cross-division/task/resource scope, changed payload after approval, self-approval, replay, expired/revoked session, revocation during execution, audit-write failure and concurrent changes. Confirm denied requests do not leak personal data or mutate domain state. Test the complete path against real staging OIDC claims and the authoritative data store before releasing a control.
