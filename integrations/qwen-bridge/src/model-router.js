export function eligibleModels(registry, { role, modality, adapterIds = [] }) {
  if (!registry || !Array.isArray(registry.models)) return [];
  const availableAdapters = new Set(adapterIds);
  return registry.models.filter((model) =>
    model.role === role &&
    model.modalities.includes(modality) &&
    model.state === "approved" &&
    model.enabled === true &&
    model.ownerApproved === true &&
    typeof model.revision === "string" && model.revision.length > 0 &&
    typeof model.providerEndpoint === "string" && model.providerEndpoint.startsWith("https://") &&
    availableAdapters.has(model.id)
  );
}

export function selectApprovedModel(registry, request) {
  const eligible = eligibleModels(registry, request);
  if (eligible.length === 0) {
    return {
      status: "unavailable",
      reason: "No owner-approved, enabled, revision-pinned model has a configured provider adapter for this task.",
      model: null,
    };
  }

  eligible.sort((a, b) => (b.evaluationScore ?? -1) - (a.evaluationScore ?? -1));
  return { status: "selected", reason: "Selected from owner-approved eligible models.", model: eligible[0] };
}
