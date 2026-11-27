import test from "node:test";
import assert from "node:assert/strict";
import { validatePayload } from "../src/index.js";

test("accepts a bounded plain-text conversation", () => {
  assert.equal(validatePayload({
    model: "Qwen/Qwen3.5-9B",
    messages: [{ role: "user", content: "Hello ENTITY" }],
    max_tokens: 128,
  }), null);
});

test("rejects a different model", () => {
  assert.match(validatePayload({
    model: "some-other-model",
    messages: [{ role: "user", content: "Hello" }],
  }), /Only Qwen/);
});

test("rejects tool execution requests", () => {
  assert.match(validatePayload({
    messages: [{ role: "user", content: "Run this tool" }],
    tools: [{ type: "function" }],
  }), /tool execution is disabled/);
});

test("rejects non-text messages", () => {
  assert.match(validatePayload({
    messages: [{ role: "user", content: [{ type: "text", text: "Hello" }] }],
  }), /plain-text/);
});

test("rejects oversized output requests", () => {
  assert.match(validatePayload({
    messages: [{ role: "user", content: "Hello" }],
    max_tokens: 999999,
  }), /max_tokens/);
});

test("rejects streaming until it is explicitly implemented", () => {
  assert.match(validatePayload({
    messages: [{ role: "user", content: "Hello" }],
    stream: true,
  }), /Streaming is not enabled/);
});
