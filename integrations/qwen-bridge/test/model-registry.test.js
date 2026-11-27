import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const registry = JSON.parse(readFileSync(new URL("../model-registry.json", import.meta.url), "utf8"));

test("registry includes all planned ENTITY AI model families", () => {
  const ids = new Set(registry.models.map((model) => model.id));
  for (const id of [
    "qwen35-9b",
    "qwen3-14b",
    "gpt-oss-20b",
    "qwen3-coder-30b-a3b",
    "qwen3-vl-8b",
    "whisper-large-v3",
    "qwen3-asr-1.7b",
    "qwen3-tts-0.6b",
    "qwen3-embedding-0.6b",
    "qwen3-reranker-0.6b",
  ]) assert.ok(ids.has(id), `Missing registry model: ${id}`);
});

test("all candidate models fail closed until owner-approved and configured", () => {
  for (const model of registry.models) {
    assert.equal(model.state, "candidate");
    assert.equal(model.enabled, false);
    assert.equal(model.ownerApproved, false);
    assert.equal(model.providerEndpoint, null);
    assert.equal(model.revision, null);
  }
});

test("paid fallback is prohibited by default", () => {
  assert.equal(registry.policy.paidProvidersAllowed, false);
  assert.equal(registry.policy.automaticPaidFallback, false);
  assert.equal(registry.policy.ownerApprovalRequired, true);
});

test("ChatGPT integrations are documented but not falsely marked live", () => {
  assert.ok(registry.integrations.some((item) => item.id === "chatgpt-action"));
  assert.ok(registry.integrations.every((item) => item.enabled === false));
});
