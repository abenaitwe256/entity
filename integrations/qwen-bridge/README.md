# ENTITY Qwen3.5-9B Bridge

This is a disabled-by-default Cloudflare Worker bridge intended to provide one restricted inference endpoint to both:

- ENTITY's authenticated backend; and
- a ChatGPT API Action when the user's ChatGPT workspace supports custom actions.

The bridge does not host model weights. It proxies to an OpenAI-compatible Qwen3.5-9B inference endpoint that must be separately supplied and explicitly approved.

## Current state

- Worker source and API contract: implemented as an isolated foundation.
- Default inference state: disabled.
- ENTITY authentication integration: depends on the identity/authorization service in PR #5/#6 being reviewed, merged and deployed.
- Resource policy: a trusted resource-registry service must register resource type `ai_model`, ID `qwen3.5-9b`, with the intended owner/division/classification/risk values.
- Qwen inference: not connected until an approved free or owner-approved local endpoint exists.
- ChatGPT connection: OpenAPI Action contract is provided, but it cannot be installed on every ChatGPT plan. Personal Free accounts cannot create/publish new GPTs, and custom MCP connections are currently limited to Business and Enterprise/Edu workspaces. See the official [GPT creation requirements](https://help.openai.com/en/articles/8554397-creating-with-chatgpt) and [custom MCP availability](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).

## Request flow

```text
ChatGPT API Action ─┐
                   ├─ HTTPS + ENTITY OIDC bearer token
ENTITY backend ────┘
                         |
                         v
                Cloudflare Worker
                         |
                1. /v1/auth/me
                2. /v1/access/check
                   action=read
                   resource_type=ai_model
                   resource_id=qwen3.5-9b
                         |
                         v
                OpenAI-compatible Qwen endpoint
                         |
                         v
                Text completion response
```

The browser must not call this worker directly with a long-lived service credential. ENTITY should call it from a trusted backend while forwarding the authenticated user's short-lived OIDC access token.

## Security behavior

- The worker requires a bearer token and validates it indirectly through the ENTITY auth service.
- The worker calls `GET /v1/auth/me` and requires an active, provisioned account.
- The worker calls `POST /v1/access/check` using a server-selected model resource. Client input cannot choose the resource ID or policy context.
- The auth service remains the authority for identity, session revocation, MFA, division/task/resource permissions and audit.
- The worker does not expose arbitrary tools, file access, memory, admin actions, or device controls to Qwen.
- Only `Qwen/Qwen3.5-9B` is accepted.
- Requests are plain text only in this first release; streaming and tool calls are disabled.
- Request bodies are limited to 256 KB, message count to 24, individual message content to 64 KB, and output to 2,048 tokens.
- No prompts, completions, bearer tokens or provider keys are logged by this worker.
- The Qwen provider key is a Worker secret, never a browser variable or committed file.
- Provider errors fail closed; no paid fallback exists.

## $0 controls

The latest Hugging Face Inference Providers pricing documentation states that Free users have no included monthly inference credits; additional use requires purchased credits. Therefore a Hugging Face token alone does not provide a $0 inference endpoint.

Do not enable this bridge against a paid endpoint. The operator must verify the endpoint's actual price and terms, then set both enablement flags manually. Local inference can be connected later through a secure HTTPS endpoint or private tunnel after hardware and runtime compatibility are verified. A local server bound to localhost is not reachable by a cloud Worker without a deliberate secure networking arrangement.

## Configure after dependencies are approved

Deploy the worker only after the ENTITY auth service is live and the Qwen endpoint is owner-approved.

Non-secret Worker variables:

- `ENTITY_AUTH_BASE_URL`: HTTPS base URL of the deployed ENTITY auth service.
- `QWEN_API_BASE_URL`: HTTPS OpenAI-compatible API base ending in `/v1`.
- `QWEN_RESOURCE_ID`: defaults to `qwen3.5-9b`.
- `QWEN_ENABLED`: must remain `false` until approval.
- `QWEN_FREE_PROVIDER_APPROVED`: must remain `false` until the owner verifies the provider is genuinely free or has explicitly approved a local endpoint.

Optional secret:

- `QWEN_API_KEY`: provider credential, stored with `wrangler secret`; never commit it.

Do not enable the worker by editing defaults in source. Use Cloudflare's secret/configuration interface and retain an auditable record of the owner's approval.

## ChatGPT setup

The OpenAPI Action schema is in `openapi.yaml`. Before importing it:

1. Deploy the Worker to an HTTPS URL.
2. Provision the OIDC provider and a dedicated OAuth client for the ChatGPT connector.
3. Replace the documented server, authorization and token URL placeholders with the actual verified endpoints.
4. Ensure the access token audience is accepted by the ENTITY auth service.
5. Configure the connector to request only the required identity scopes.
6. Test that an unprovisioned identity, revoked session and user without model permission are denied.
7. Do not publish the connector until security review is complete.

On the user's current personal Free ChatGPT account, custom GPT creation and custom MCP installation are not available. The API contract is ready for an eligible workspace/connector route, but this does not make Qwen callable from the current ChatGPT account automatically.

## ENTITY setup

ENTITY's backend calls the same `POST /v1/chat/completions` endpoint and forwards the current user's short-lived OIDC access token. Do not create a shared browser API key. Do not allow the model to perform tools or operations; the ENTITY tool gateway must separately validate and execute any future tool request.

## Local tests

From this directory, run:

```bash
node --test test/validation.test.js
```

These tests cover request validation only. They do not verify live authentication, the provider endpoint, ChatGPT OAuth, Cloudflare deployment or model quality.

## Current blockers

- PR #5 and PR #6 are still pending and must not be merged by this integration.
- The identity provider, production/staging auth service and resource registry are not provisioned.
- No Qwen inference endpoint is approved or configured.
- The ChatGPT account plan currently does not support creating a new custom GPT or adding a custom MCP server.
- No live end-to-end test has been performed.
