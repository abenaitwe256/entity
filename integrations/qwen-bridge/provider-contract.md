# ENTITY AI provider contract

This contract applies to every model in `model-registry.json`. The registry is a catalogue of candidates, not proof that any endpoint is deployed or available.

## Required provider interface

Every provider adapter must implement the equivalent of:

- `health()`: report reachable/unavailable and timestamp without leaking secrets.
- `capabilities()`: declare supported modalities, tasks, context and output limits.
- `invoke(request, identityContext)`: accept a normalized task request and authenticated caller context.
- `estimateUsage(request)`: return a best-effort estimate before execution when supported.
- `normalizeResponse(response)`: return a provider-neutral response with model ID, pinned revision, output, usage and provider metadata.
- `close()`: release resources for local runtimes where relevant.

The adapter must not make authorization decisions. The ENTITY gateway and existing authorization service remain authoritative.

## Task families

| Task family | Candidate adapters |
|---|---|
| General reasoning / multimodal | Qwen3.5-9B |
| Text reasoning challenger | Qwen3-14B |
| Reasoning challenger | GPT-OSS-20B |
| Coding / repository analysis | Qwen3-Coder-30B-A3B-Instruct |
| Vision / OCR / video | Qwen3-VL-8B-Instruct; Qwen3.5-9B where sufficient |
| Speech recognition | Whisper Large V3; Qwen3-ASR-1.7B |
| Speech generation | Qwen3-TTS-12Hz-0.6B-Base, only for documented supported languages |
| Embeddings | Qwen3-Embedding-0.6B |
| Retrieval reranking | Qwen3-Reranker-0.6B |

## Routing policy

1. Resolve task and modality.
2. Filter to models whose state is `approved`, `enabled` is true, `ownerApproved` is true, immutable revision is pinned, and endpoint is configured.
3. Filter by user, division, task, resource and environment permissions.
4. Filter out paid endpoints unless the owner separately changes the budget policy.
5. Select among eligible models using evaluation score, latency, availability and task fit.
6. If no eligible model exists, return a truthful unavailable response or an explicitly configured mock in development. Never silently route to an unapproved or paid model.

The model cannot alter its own registry state, revision, provider, permissions or approvals.

## Modality-specific interfaces

- Text generation: normalized messages and bounded generation settings.
- Vision: user-authorized image references; do not forward private images to third parties without explicit data-handling approval.
- Speech recognition: audio input with declared language/task and retention controls.
- Speech generation: text input, documented voice/language constraints and output format.
- Embeddings: text input, fixed dimensions and versioned embedding model.
- Reranking: query plus bounded candidate documents with access filtering performed before reranking.

## ChatGPT integration

ChatGPT is an external client, not an ENTITY model provider. It should call a narrow ENTITY API Action or MCP tool through OAuth. The bridge exposes only explicitly documented operations. It must not expose arbitrary database access, file access, admin controls, secrets, model registry mutation or device actions.

## Deployment status

All registry entries begin as candidates and disabled. No provider endpoint, credential, immutable revision, language performance, hosting price or deployment status is assumed. Each adapter requires independent implementation, endpoint verification, benchmark tests and owner approval before activation.
