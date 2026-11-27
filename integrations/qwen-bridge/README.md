# ENTITY Qwen and multi-model AI bridge

This integration folder contains the first disabled-by-default foundation for connecting ENTITY and eligible ChatGPT clients to a common AI gateway.

## Scope: all identified model capabilities

The candidate registry in `model-registry.json` covers all models selected for ENTITY AI Foundation v1:

| Capability | Model candidate |
|---|---|
| General multimodal intelligence | Qwen3.5-9B |
| Text reasoning | Qwen3-14B |
| Reasoning challenger | GPT-OSS-20B |
| Coding and repository analysis | Qwen3-Coder-30B-A3B-Instruct |
| Vision, OCR and video | Qwen3-VL-8B-Instruct |
| Speech recognition | Whisper Large V3 |
| Alternative speech recognition | Qwen3-ASR-1.7B |
| Speech generation | Qwen3-TTS-12Hz-0.6B-Base |
| Embeddings and semantic retrieval | Qwen3-Embedding-0.6B |
| Retrieval reranking | Qwen3-Reranker-0.6B |

The registry also records ChatGPT Action and MCP as external client integration options. ChatGPT is not a model provider; it is an authorized client of ENTITY's narrow API.

**Important:** registering a candidate does not mean its weights are hosted, its API is configured, or it is currently accessible. All ten model candidates are disabled, unapproved and have no configured endpoint or pinned revision. This is deliberate fail-closed behavior.

## Architecture

- `src/index.js`: Cloudflare Worker bridge with restricted text completion endpoint.
- `model-registry.json`: versioned catalogue of candidate models and integration options.
- `provider-contract.md`: common adapter contract and routing policy for text, vision, speech, embedding and reranking providers.
- `openapi.yaml`: ChatGPT Action contract for the narrow Qwen text endpoint.
- `test/`: request validation and registry policy tests.

All model adapters must use the same provider-neutral contract. The application must not bind directly to a vendor-specific SDK.

## Provider routing and authority

The gateway may select only models that are:
- owner-approved;
- explicitly enabled;
- pinned to an immutable revision;
- configured with a verified endpoint;
- evaluated for the task and modality;
- permitted by the authenticated user's division, task, resource and environment permissions.

Adaptive routing can choose between already-approved models. It cannot approve or activate candidates, change the registry, alter security policy or enable paid inference. No eligible model means a truthful unavailable response, not an unapproved or paid fallback.

The model is not an authorization engine. All tool execution must be handled by a separate ENTITY policy-enforcing tool gateway.

## Qwen bridge

The Worker exposes `POST /v1/chat/completions`, pins requests to `Qwen/Qwen3.5-9B`, accepts plain-text messages only, disables model tool execution and streaming, and enforces bounded request/output sizes.

The Worker checks:
1. `GET /v1/auth/me` at the ENTITY identity service.
2. `POST /v1/access/check` for the server-selected `ai_model/qwen3.5-9b` resource.

It does not expose ENTITY files, memory, administration, device controls or secrets.

## Current state and blockers

- Code and registry foundation: committed on the draft PR branch.
- Qwen inference: disabled; no endpoint configured.
- Other model adapters: contract and registry defined; individual adapters/endpoints not yet implemented or tested.
- ChatGPT Action: OpenAPI contract prepared; OAuth URLs and deployed Worker URL are placeholders.
- ChatGPT MCP: future integration option, not implemented in this PR.
- ENTITY identity service: runtime dependency on PR #5/#6 being reviewed, approved, merged and deployed.
- Model resource registry: must register the Qwen resource with correct policy.
- Local inference: not enabled until compatible hardware/runtime are verified and owner approves.
- Free hosting: must be verified per provider. No Hugging Face free inference quota is assumed.
- Production use: prohibited until staged integration and security tests pass.

The pending PRs #5 and #6 must remain untouched and unmerged by this work.

## $0 budget

Do not enable billing, paid inference endpoints, GPU rentals, subscriptions or paid fallback. A model's open license does not make its hosted inference free. Use a verified no-cost endpoint, an owner-approved local endpoint, or a mock in development. If none is available, return a clear unavailable status.

## Tests

From this directory:

```bash
npm test
```

The tests validate request shape, fail-closed registry defaults and integration metadata. They do not verify live inference, OIDC, authorization, ChatGPT OAuth, Cloudflare deployment or model quality.

## ChatGPT availability

The OpenAPI contract can be imported into a supported custom GPT Action setup after the Worker and OAuth client are deployed and reviewed. Custom connector availability depends on ChatGPT plan/workspace features. The API contract itself does not create a live connection.

## Release gates

1. Review PR #5/#6 and validate identity/auth service in staging.
2. Register the Qwen resource and confirm permission enforcement.
3. Select and verify a genuinely free or approved local Qwen inference endpoint.
4. Deploy the Worker with inference disabled; configure secrets securely.
5. Run auth, revocation, denied-access, provider outage and prompt-injection tests.
6. Activate Qwen only after explicit owner approval.
7. Implement and evaluate specialist adapters one at a time.
8. Configure the ChatGPT Action/MCP route only after OAuth and plan eligibility are confirmed.
