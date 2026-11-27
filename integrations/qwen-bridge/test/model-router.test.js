import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { eligibleModels, selectApprovedModel } from "../src/model-router.js";

const registry = JSON.parse(readFileSync(new URL("../model-registry.json", import.meta.url), "utf8"));

test("does not route to any candidate model by default", () => {
  const result = selectApprovedModel(registry, {
    role: "general-multimodal",
    modality: "text",
    adapterIds: ["qwen35-9b"],
  });
  assert.equal(result.status, "unavailable");
  assert.equal(result.model, null);
});

test("routes only to approved, enabled, pinned, configured model with adapter", () => {
  const copy = structuredClone(registry);
  const model = copy.models.find((item) => item.id === "qwen35-9b");
  Object.assign(model, {
    state: "approved",
    enabled: true,
    ownerApproved: true,
    revision: "immutable-test-sha",
    providerEndpoint: "https://inference.example.test/v1",
    evaluationScore: 0.91,
  });
  const result = selectApprovedModel(copy, {
    role: "general-multimodal",
    modality: "text",
    adapterIds: ["qwen35-9b"],
  });
  assert.equal(result.status, "selected");
  assert.equal(result.model.id, "qwen35-9b");
});

test("does not route when an adapter is missing or endpoint is not HTTPS", () => {
  const copy = structuredClone(registry);
  const model = copy.models.find((item) => item.id === "qwen35-9b");
  Object.assign(model, {
    state: "approved",
    enabled: true,
    ownerApproved: true,
    revision: "immutable-test-sha",
    providerEndpoint: "http://insecure.example.test/v1",
  });
  assert.equal(eligibleModels(copy, {
    role: "general-multimodal",
    modality: "text",
    adapterIds: ["qwen35-9b"],
  }).length, 0);
});
