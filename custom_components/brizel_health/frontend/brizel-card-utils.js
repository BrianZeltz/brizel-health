const STATUS_META = {
  under: { label: "Under", color: "#f59e0b", tint: "rgba(245, 158, 11, 0.14)" },
  within: { label: "Within", color: "#22c55e", tint: "rgba(34, 197, 94, 0.14)" },
  over: { label: "Over", color: "#ef4444", tint: "rgba(239, 68, 68, 0.14)" },
  unknown: { label: "Unknown", color: "#94a3b8", tint: "rgba(148, 163, 184, 0.14)" },
  unavailable: { label: "Unavailable", color: "#94a3b8", tint: "rgba(148, 163, 184, 0.14)" },
};

const MACROS = {
  kcal: { key: "kcal", title: "Kcal", icon: "mdi:fire", unit: "kcal" },
  protein: { key: "protein", title: "Protein", icon: "mdi:food-steak", unit: "g" },
  fat: { key: "fat", title: "Fat", icon: "mdi:oil", unit: "g" },
};
const PROFILE_REFRESH_EVENT = "brizel-health:profile-refresh";

const trimToNull = (value) => {
  const normalized = String(value ?? "").trim();
  return normalized ? normalized : null;
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const escapeHtml = (value) =>
  String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const titleize = (value) =>
  String(value ?? "")
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");

const toNumber = (value) => {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    value === "unknown" ||
    value === "unavailable"
  ) {
    return null;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const formatNumber = (value) => {
  const numeric = toNumber(value);
  if (numeric === null) {
    return "-";
  }
  if (Math.abs(numeric - Math.round(numeric)) < 0.0001) {
    return String(Math.round(numeric));
  }
  if (Math.abs(numeric * 10 - Math.round(numeric * 10)) < 0.0001) {
    return numeric.toFixed(1);
  }
  return numeric.toFixed(2);
};

const formatValue = (value, unit) => {
  const formatted = formatNumber(value);
  return formatted === "-" ? formatted : `${formatted} ${unit}`;
};

const formatMl = (value) => formatValue(value, "ml");

const getStatusMeta = (status) => STATUS_META[status] || STATUS_META.unknown;

const getMacroConfig = (macro) => {
  const config = MACROS[String(macro ?? "").toLowerCase()];
  if (!config) {
    throw new Error("Macro must be one of: kcal, protein, fat");
  }
  return config;
};

const getConfiguredProfile = (config) =>
  trimToNull(config?.profile) || trimToNull(config?.profile_id);

const getCurrentHaUserId = (hass) => trimToNull(hass?.user?.id);

const buildScale = ({ consumed, min, recommended, max }) => {
  if (min === null || max === null) {
    return null;
  }
  const upper = Math.max(max, recommended ?? 0, consumed ?? 0, 1);
  const paddedUpper = upper * 1.15;
  const toPercent = (value) => clamp((value / paddedUpper) * 100, 0, 100);
  return {
    minPct: toPercent(min),
    maxPct: toPercent(max),
    markerPct: consumed === null ? null : toPercent(consumed),
    recommendedPct: recommended === null ? null : toPercent(recommended),
  };
};

const getMacroDataFromOverview = (overview, macro) => {
  const macroConfig = getMacroConfig(macro);
  const raw = overview?.[macroConfig.key] ?? {};
  const consumed = toNumber(raw.consumed);
  const targetMin = toNumber(raw.target_min);
  const targetRecommended = toNumber(raw.target_recommended);
  const targetMax = toNumber(raw.target_max);
  const remainingToMin = toNumber(raw.remaining_to_min);
  const remainingToMax = toNumber(raw.remaining_to_max);
  const overAmount = toNumber(raw.over_amount);

  return {
    ...macroConfig,
    available: Boolean(Object.keys(raw).length),
    status: String(raw.status ?? "unknown").toLowerCase(),
    displayText: raw.display_text || "Target range is not available yet.",
    consumed,
    targetMin,
    targetRecommended,
    targetMax,
    remainingToMin,
    remainingToMax,
    overAmount,
    scale: buildScale({
      consumed,
      min: targetMin,
      recommended: targetRecommended,
      max: targetMax,
    }),
  };
};

const readEntity = (hass, entityId) => (entityId ? hass?.states?.[entityId] ?? null : null);

const getMacroDataFromEntity = (hass, { macro, entityId }) => {
  const macroConfig = getMacroConfig(macro);
  const stateObj = readEntity(hass, entityId);
  if (!stateObj) {
    return {
      ...macroConfig,
      entityId,
      available: false,
      status: "unavailable",
      displayText: "This sensor is not available yet.",
      consumed: null,
      targetMin: null,
      targetRecommended: null,
      targetMax: null,
      remainingToMin: null,
      remainingToMax: null,
      overAmount: null,
      scale: null,
    };
  }

  const attributes = stateObj.attributes ?? {};
  const consumed = toNumber(attributes.consumed);
  const targetMin = toNumber(attributes.target_min);
  const targetRecommended = toNumber(attributes.target_recommended);
  const targetMax = toNumber(attributes.target_max);
  const remainingToMin = toNumber(attributes.remaining_to_min);
  const remainingToMax = toNumber(attributes.remaining_to_max);
  const overAmount = toNumber(attributes.over_amount);

  return {
    ...macroConfig,
    entityId,
    available: stateObj.state !== "unavailable",
    status: String(stateObj.state ?? "unknown").toLowerCase(),
    displayText: attributes.display_text || "Target range is not available yet.",
    consumed,
    targetMin,
    targetRecommended,
    targetMax,
    remainingToMin,
    remainingToMax,
    overAmount,
    scale: buildScale({
      consumed,
      min: targetMin,
      recommended: targetRecommended,
      max: targetMax,
    }),
  };
};

const getHydrationDataFromEntities = (hass, config) => {
  const totalEntity = trimToNull(config?.total_entity);
  const drankEntity = trimToNull(config?.drank_entity);
  const foodEntity = trimToNull(config?.food_entity);
  const targetEntity = trimToNull(config?.target_entity);

  const totalState = readEntity(hass, totalEntity);
  const drankState = readEntity(hass, drankEntity);
  const foodState = readEntity(hass, foodEntity);
  const targetState = readEntity(hass, targetEntity);

  const total = toNumber(totalState?.state);
  const drank = toNumber(drankState?.state);
  const foodHydration = toNumber(foodState?.state);
  const target = toNumber(targetState?.state);
  const progress =
    total !== null && target !== null && target > 0
      ? Math.min((total / target) * 100, 100)
      : null;

  return {
    totalHydrationMl: total,
    drankMl: drank,
    foodHydrationMl: foodHydration,
    targetMl: target,
    progress,
    hasData: (total ?? 0) > 0 || (drank ?? 0) > 0 || (foodHydration ?? 0) > 0,
    goalConfigured: Boolean(targetEntity),
    goalAvailable: target !== null && target > 0,
    entityIds: {
      total: totalEntity,
      drank: drankEntity,
      food: foodEntity,
      target: targetEntity,
    },
  };
};

const normalizeServiceEnvelope = (response) => {
  const root = Array.isArray(response) ? response[0] : response;
  const candidate = root?.service_response || root?.response || root?.result || root;

  if (candidate && typeof candidate === "object" && !Array.isArray(candidate)) {
    return candidate;
  }

  if (Array.isArray(candidate) && candidate.length) {
    return candidate[0];
  }

  throw new Error("Could not parse Brizel Health service response.");
};

const callBrizelServiceWithResponse = async (hass, serviceName, data = {}) =>
  normalizeServiceEnvelope(
    await hass.callApi(
      "POST",
      `services/brizel_health/${serviceName}?return_response`,
      data
    )
  );

const classifyProfileErrorMessage = (message) => {
  if (message.includes("profile_id is required when no linked Home Assistant user is available")) {
    return "no_user";
  }
  if (message.includes("No Brizel Health profile is linked to the active Home Assistant user")) {
    return "no_link";
  }
  if (message.includes("No profile found for profile_id") || message.includes("A profile ID is required.")) {
    return "invalid_profile";
  }
  return "generic";
};

const buildProfileError = (kind, { explicitProfile = null, rawMessage = "" } = {}) => {
  if (kind === "no_user") {
    return {
      kind,
      title: "Home Assistant user unavailable",
      detail: "The currently signed-in Home Assistant user could not be determined.",
      rawMessage,
    };
  }
  if (kind === "no_link") {
    return {
      kind,
      title: "No Brizel profile linked",
      detail: "For your Home Assistant user, no Brizel Health profile is linked yet.",
      rawMessage,
    };
  }
  if (kind === "invalid_profile") {
    return {
      kind,
      title: "Invalid Brizel profile reference",
      detail: explicitProfile
        ? "The configured Brizel Health profile is invalid or no longer exists."
        : "The profile link is invalid or the Brizel Health profile no longer exists.",
      rawMessage,
    };
  }
  return {
    kind: "generic",
    title: "Couldn't load Brizel Health data",
    detail: rawMessage || "Please check the Brizel Health integration.",
    rawMessage,
  };
};

const normalizeServiceError = (error, { explicitProfile = null } = {}) => {
  const rawMessage = trimToNull(error?.message || error) || "Unknown error";
  const kind = classifyProfileErrorMessage(rawMessage);
  return buildProfileError(kind, { explicitProfile, rawMessage });
};

const buildProfileRequestKey = (hass, config) =>
  `${getConfiguredProfile(config) || ""}|${getCurrentHaUserId(hass) || ""}`;

const extractExpectedPayload = (response, responseKey) => {
  const candidate = normalizeServiceEnvelope(response);
  if (candidate && Object.prototype.hasOwnProperty.call(candidate, responseKey)) {
    return candidate;
  }
  throw new Error(`Could not parse Brizel Health ${responseKey} response.`);
};

const loadProfileScopedServiceData = async ({
  hass,
  config,
  serviceName,
  responseKey,
  hasData,
}) => {
  const explicitProfile = getConfiguredProfile(config);
  if (!explicitProfile && !getCurrentHaUserId(hass)) {
    return {
      state: "profile_error",
      error: buildProfileError("no_user"),
      data: null,
      profileId: null,
      profileDisplayName: null,
      date: null,
    };
  }

  try {
    const payload = explicitProfile ? { profile_id: explicitProfile } : {};
    const response = await hass.callApi(
      "POST",
      `services/brizel_health/${serviceName}?return_response`,
      payload
    );
    const parsed = extractExpectedPayload(response, responseKey);
    const data = parsed[responseKey];
    const resolvedProfileId = trimToNull(parsed.profile_id) || explicitProfile;
    const resolvedProfileName =
      trimToNull(parsed.profile_display_name) ||
      trimToNull(parsed.profile_name) ||
      resolvedProfileId;

    return {
      state: hasData(data) ? "ready" : "no_data",
      error: null,
      data,
      profileId: resolvedProfileId,
      profileDisplayName: resolvedProfileName,
      date: trimToNull(parsed.date),
    };
  } catch (error) {
    const normalizedError = normalizeServiceError(error, { explicitProfile });
    return {
      state: normalizedError.kind === "generic" ? "error" : "profile_error",
      error: normalizedError,
      data: null,
      profileId: null,
      profileDisplayName: null,
      date: null,
    };
  }
};

const loadDailyOverview = (hass, config) =>
  loadProfileScopedServiceData({
    hass,
    config,
    serviceName: "get_daily_overview",
    responseKey: "overview",
    hasData: (overview) => Boolean(overview?.has_data),
  });

const loadDailyHydrationReport = (hass, config) =>
  loadProfileScopedServiceData({
    hass,
    config,
    serviceName: "get_daily_hydration_report",
    responseKey: "hydration",
    hasData: (hydration) =>
      Number(hydration?.total_hydration_ml ?? 0) > 0 ||
      Number(hydration?.drank_ml ?? 0) > 0 ||
      Number(hydration?.food_hydration_ml ?? 0) > 0 ||
      (Array.isArray(hydration?.breakdown) && hydration.breakdown.length > 0),
  });

const searchExternalFoods = async (
  hass,
  { query, sourceName = null, profileId = null, limit = 10 }
) => {
  const payload = {
    query,
    limit,
  };
  if (trimToNull(sourceName)) {
    payload.source_name = trimToNull(sourceName);
  }
  if (trimToNull(profileId)) {
    payload.profile_id = trimToNull(profileId);
  }

  const parsed = await callBrizelServiceWithResponse(hass, "search_external_foods", payload);
  const sourceResults = Array.isArray(parsed.source_results) ? parsed.source_results : [];
  const results = Array.isArray(parsed.results)
    ? parsed.results.map((result) => ({
        ...result,
        source_name: trimToNull(result?.source_name),
      }))
    : sourceResults.flatMap((sourceResult) =>
        Array.isArray(sourceResult?.results)
          ? sourceResult.results.map((result) => ({
              ...result,
              source_name:
                trimToNull(result?.source_name) || trimToNull(sourceResult?.source_name),
            }))
          : []
      );

  return {
    status: trimToNull(parsed.status) || "failure",
    error: trimToNull(parsed.error),
    sourceResults,
    results,
  };
};

const getExternalFoodDetail = async (hass, { sourceName, sourceId }) => {
  const parsed = await callBrizelServiceWithResponse(hass, "get_external_food_detail", {
    source_name: sourceName,
    source_id: sourceId,
  });
  if (!parsed.food_detail || typeof parsed.food_detail !== "object") {
    throw new Error("Could not parse Brizel Health food detail response.");
  }
  return parsed.food_detail;
};

const logExternalFoodEntry = async (
  hass,
  config,
  { sourceName, sourceId, amount, unit = null, consumedAt = null }
) => {
  const payload = {
    source_name: sourceName,
    source_id: sourceId,
    amount,
  };
  const configuredProfile = getConfiguredProfile(config);
  if (configuredProfile) {
    payload.profile_id = configuredProfile;
  }
  if (trimToNull(unit)) {
    payload.unit = trimToNull(unit);
  }
  if (trimToNull(consumedAt)) {
    payload.consumed_at = trimToNull(consumedAt);
  }

  return callBrizelServiceWithResponse(hass, "log_external_food_entry", payload);
};

const emitProfileRefresh = (profileId) => {
  window.dispatchEvent(
    new CustomEvent(PROFILE_REFRESH_EVENT, {
      detail: {
        profileId: trimToNull(profileId),
        timestamp: Date.now(),
      },
    })
  );
};

const addProfileRefreshListener = (listener) => {
  const handler = (event) => {
    listener(event?.detail ?? {});
  };
  window.addEventListener(PROFILE_REFRESH_EVENT, handler);
  return () => window.removeEventListener(PROFILE_REFRESH_EVENT, handler);
};

const matchesProfileRefresh = ({ config, resolvedProfileId, detail }) => {
  const eventProfileId = trimToNull(detail?.profileId);
  const expectedProfileId = trimToNull(resolvedProfileId) || getConfiguredProfile(config);
  return Boolean(eventProfileId && expectedProfileId && eventProfileId === expectedProfileId);
};

const BrizelCardUtils =
  window.BrizelCardUtils ||
  (window.BrizelCardUtils = {
    addProfileRefreshListener,
    buildProfileRequestKey,
    callBrizelServiceWithResponse,
    clamp,
    emitProfileRefresh,
    escapeHtml,
    formatMl,
    formatNumber,
    formatValue,
    getExternalFoodDetail,
    getConfiguredProfile,
    getCurrentHaUserId,
    getHydrationDataFromEntities,
    getMacroConfig,
    getMacroDataFromEntity,
    getMacroDataFromOverview,
    getStatusMeta,
    loadDailyHydrationReport,
    loadDailyOverview,
    logExternalFoodEntry,
    matchesProfileRefresh,
    normalizeServiceError,
    readEntity,
    searchExternalFoods,
    titleize,
    toNumber,
    trimToNull,
  });

export { BrizelCardUtils };
