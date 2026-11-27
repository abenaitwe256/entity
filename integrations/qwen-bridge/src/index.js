const MODEL_ID = "Qwen/Qwen3.5-9B";
const MAX_BODY_BYTES = 256 * 1024;
const MAX_MESSAGES = 24;
const MAX_OUTPUT_TOKENS = 2048;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function bearer(request) {
  const value = request.headers.get("authorization") || "";
  const match = /^Bearer\s+(.+)$/i.exec(value);
  return match ? match[1] : null;
}

function requiredHttpsBase(value, name) {
  if (!value) throw new Error(`${name} is not configured`);
  const parsed = new URL(value);
  if (parsed.protocol !== "https:") throw new Error(`${name} must use HTTPS`);
  return value.replace(/\/+$/, "");
}

async function authorizeRequest(request, env) {
  const token = bearer(request);
  if (!token) return { response: json({ error: { message: "Bearer token required" } }, 401) };

  let authBase;
  try {
    authBase = requiredHttpsBase(env.ENTITY_AUTH_BASE_URL, "ENTITY_AUTH_BASE_URL");
  } catch {
    return { response: json({ error: { message: "Identity service is not configured" } }, 503) };
  }

  const headers = { authorization: `Bearer ${token}`, accept: "application/json" };
  let identityResponse;
  try {
    identityResponse = await fetch(`${authBase}/v1/auth/me`, {
      method: "GET",
      headers,
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    return { response: json({ error: { message: "Identity service unavailable" } }, 503) };
  }
  if (!identityResponse.ok) {
    const status = identityResponse.status === 401 ? 401 : 403;
    return { response: json({ error: { message: "ENTITY identity verification failed" } }, status) };
  }

  const identity = await identityResponse.json().catch(() => null);
  if (!identity || identity.active !== true || typeof identity.subject !== "string") {
    return { response: json({ error: { message: "ENTITY account is not active" } }, 403) };
  }

  let policyResponse;
  try {
    policyResponse = await fetch(`${authBase}/v1/access/check`, {
      method: "POST",
      headers: { ...headers, "content-type": "application/json" },
      body: JSON.stringify({
        action: "read",
        resource_type: "ai_model",
        resource_id: env.QWEN_RESOURCE_ID || "qwen3.5-9b",
      }),
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    return { response: json({ error: { message: "ENTITY authorization service unavailable" } }, 503) };
  }
  if (!policyResponse.ok) {
    return { response: json({ error: { message: "ENTITY authorization check failed" } }, 403) };
  }
  const decision = await policyResponse.json().catch(() => null);
  if (!decision || decision.allowed !== true) {
    return { response: json({ error: { message: "Access to this AI model is not authorized" } }, 403) };
  }

  return { subject: identity.subject };
}

function validatePayload(payload, declaredLength) {
  if (declaredLength && Number(declaredLength) > MAX_BODY_BYTES) {
    return "Request body exceeds the 256 KB limit";
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return "A JSON object is required";
  }
  if (payload.model && payload.model !== MODEL_ID) {
    return `Only ${MODEL_ID} is enabled`;
  }
  if (!Array.isArray(payload.messages) || payload.messages.length < 1 || payload.messages.length > MAX_MESSAGES) {
    return `messages must contain between 1 and ${MAX_MESSAGES} entries`;
  }
  for (const message of payload.messages) {
    if (!message || !["system", "user", "assistant"].includes(message.role) || typeof message.content !== "string") {
      return "Only plain-text system, user, and assistant messages are supported";
    }
    if (message.content.length > 64000) return "A message exceeds the 64 KB character limit";
  }
  if (payload.tools || payload.tool_choice || payload.functions || payload.function_call) {
    return "Model tool execution is disabled";
  }
  if (payload.stream === true) return "Streaming is not enabled in the first bridge release";
  if (payload.max_tokens !== undefined &&
      (!Number.isInteger(payload.max_tokens) || payload.max_tokens < 1 || payload.max_tokens > MAX_OUTPUT_TOKENS)) {
    return `max_tokens must be an integer between 1 and ${MAX_OUTPUT_TOKENS}`;
  }
  return null;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/healthz") {
      return json({ status: "ok", component: "entity-qwen-bridge", inference: "configuration-dependent" });
    }
    if (request.method !== "POST" || url.pathname !== "/v1/chat/completions") {
      return json({ error: { message: "Not found" } }, 404);
    }

    if (env.QWEN_ENABLED !== "true" || env.QWEN_FREE_PROVIDER_APPROVED !== "true") {
      return json({ error: { message: "Qwen inference is disabled pending owner-approved free provider configuration" } }, 503);
    }

    const authorization = await authorizeRequest(request, env);
    if (authorization.response) return authorization.response;

    const raw = await request.text();
    if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
      return json({ error: { message: "Request body exceeds the 256 KB limit" } }, 413);
    }
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch {
      return json({ error: { message: "Invalid JSON" } }, 400);
    }
    const validationError = validatePayload(payload, request.headers.get("content-length"));
    if (validationError) return json({ error: { message: validationError } }, 400);

    let upstream;
    try {
      const base = requiredHttpsBase(env.QWEN_API_BASE_URL, "QWEN_API_BASE_URL");
      const headers = { "content-type": "application/json", accept: "application/json" };
      if (env.QWEN_API_KEY) headers.authorization = `Bearer ${env.QWEN_API_KEY}`;
      upstream = await fetch(`${base}/chat/completions`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          model: MODEL_ID,
          messages: payload.messages,
          max_tokens: Math.min(payload.max_tokens || 1024, MAX_OUTPUT_TOKENS),
          temperature: typeof payload.temperature === "number"
            ? Math.max(0, Math.min(2, payload.temperature))
            : 0.7,
          stream: false,
        }),
        signal: AbortSignal.timeout(60000),
      });
    } catch {
      return json({ error: { message: "Qwen provider is unavailable or not configured" } }, 503);
    }

    if (!upstream.ok) {
      return json({ error: { message: "Qwen provider returned an unsuccessful response" } }, 502);
    }
    const responseText = await upstream.text();
    if (responseText.length > 2 * 1024 * 1024) {
      return json({ error: { message: "Qwen provider response exceeded the response limit" } }, 502);
    }
    try {
      const result = JSON.parse(responseText);
      return json({
        id: result.id || crypto.randomUUID(),
        object: "chat.completion",
        created: result.created || Math.floor(Date.now() / 1000),
        model: MODEL_ID,
        choices: Array.isArray(result.choices) ? result.choices : [],
        usage: result.usage || null,
      });
    } catch {
      return json({ error: { message: "Qwen provider returned invalid JSON" } }, 502);
    }
  },
};

export { validatePayload };
