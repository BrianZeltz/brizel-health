const BrizelCardUtils =
  window.BrizelCardUtils ||
  (window.BrizelCardUtils = (() => {
    const STATUS_META = {
      under: { label: "Under", color: "#f59e0b", tint: "rgba(245, 158, 11, 0.14)" },
      within: { label: "Within", color: "#22c55e", tint: "rgba(34, 197, 94, 0.14)" },
      over: { label: "Over", color: "#ef4444", tint: "rgba(239, 68, 68, 0.14)" },
      unknown: { label: "Unknown", color: "#94a3b8", tint: "rgba(148, 163, 184, 0.14)" },
      unavailable: { label: "Unavailable", color: "#94a3b8", tint: "rgba(148, 163, 184, 0.14)" },
    };

    const MACROS = {
      kcal: { key: "kcal", title: "Kcal", icon: "mdi:fire", unit: "kcal", entitySuffix: "kcal_target_status" },
      protein: { key: "protein", title: "Protein", icon: "mdi:food-steak", unit: "g", entitySuffix: "protein_target_status" },
      fat: { key: "fat", title: "Fat", icon: "mdi:oil", unit: "g", entitySuffix: "fat_target_status" },
    };

    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
    const slugify = (value) => String(value ?? "").trim().toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
    const titleize = (value) =>
      String(value ?? "").split(/[_\s-]+/).filter(Boolean).map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1)).join(" ");
    const escapeHtml = (value) =>
      String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

    const toNumber = (value) => {
      if (value === null || value === undefined || value === "" || value === "unknown" || value === "unavailable") {
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

    const getStatusMeta = (status) => STATUS_META[status] || STATUS_META.unknown;
    const defaultEntityId = (profile, suffix) => {
      const slug = slugify(profile);
      return slug ? `sensor.${slug}_${suffix}` : "";
    };

    const getMacroConfig = (macro) => {
      const config = MACROS[String(macro ?? "").toLowerCase()];
      if (!config) {
        throw new Error("Macro must be one of: kcal, protein, fat");
      }
      return config;
    };

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

    const readEntity = (hass, entityId) => (entityId ? hass?.states?.[entityId] ?? null : null);

    const getMacroData = (hass, { profile, macro, entity }) => {
      const macroConfig = getMacroConfig(macro);
      const entityId = entity || defaultEntityId(profile, macroConfig.entitySuffix);
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
        scale: buildScale({ consumed, min: targetMin, recommended: targetRecommended, max: targetMax }),
      };
    };

    return { escapeHtml, formatValue, getMacroConfig, getMacroData, getStatusMeta, titleize };
  })());

class BrizelMacroCard extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:brizel-macro-card", profile: "brian", macro: "kcal" };
  }

  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config?.profile) {
      throw new Error("profile is required");
    }
    if (!config?.macro) {
      throw new Error("macro is required");
    }
    BrizelCardUtils.getMacroConfig(config.macro);
    this._config = { title: null, entity: null, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  getGridOptions() {
    return {
      rows: 4,
      columns: 6,
      min_rows: 4,
      min_columns: 6,
    };
  }

  _renderProgressBar(data) {
    if (!data.scale) {
      return `<div class="progress-shell is-empty"><div class="progress-empty">Target range unavailable</div></div>`;
    }

    return `
      <div class="progress-shell">
        <div class="progress-track"></div>
        <div class="progress-range" style="left:${data.scale.minPct}%; width:${Math.max(data.scale.maxPct - data.scale.minPct, 2)}%;"></div>
        ${data.scale.recommendedPct === null ? "" : `<div class="progress-recommended" style="left:${data.scale.recommendedPct}%"></div>`}
        ${data.scale.markerPct === null ? "" : `<div class="progress-marker" style="left:${data.scale.markerPct}%"></div>`}
        <div class="progress-labels">
          <span>${BrizelCardUtils.formatValue(data.targetMin, data.unit)}</span>
          <span>${BrizelCardUtils.formatValue(data.targetMax, data.unit)}</span>
        </div>
      </div>
    `;
  }

  _render() {
    if (!this._config || !this.shadowRoot) {
      return;
    }

    const data = this._hass ? BrizelCardUtils.getMacroData(this._hass, this._config) : null;
    const macroConfig = BrizelCardUtils.getMacroConfig(this._config.macro);
    const title = this._config.title || `${macroConfig.title} Detail`;
    const profileTitle = BrizelCardUtils.titleize(this._config.profile);
    const meta = BrizelCardUtils.getStatusMeta(data?.status ?? "unknown");

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { border-radius: 24px; overflow: hidden; background: radial-gradient(circle at top right, rgba(255, 255, 255, 0.08), transparent 35%), linear-gradient(180deg, #101828 0%, #0f172a 100%); color: #e5edf7; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.18); }
        .card { padding: 20px; }
        .eyebrow { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
        .eyebrow-copy { display: grid; gap: 4px; }
        .eyebrow-label { color: #94a3b8; font-size: 0.77rem; letter-spacing: 0.08em; text-transform: uppercase; }
        .eyebrow-title { font-size: 1.25rem; font-weight: 700; line-height: 1.2; }
        .status-pill { padding: 8px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 700; color: ${meta.color}; background: ${meta.tint}; border: 1px solid color-mix(in srgb, ${meta.color} 40%, transparent); white-space: nowrap; }
        .hero { display: grid; gap: 8px; margin-bottom: 18px; }
        .hero-value { font-size: 2rem; font-weight: 800; line-height: 1; }
        .hero-range { color: #cbd5e1; font-size: 0.95rem; }
        .display-text { color: #f8fafc; font-size: 0.96rem; line-height: 1.45; margin: 0 0 18px; }
        .stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
        .stat { padding: 12px; border-radius: 18px; background: rgba(148, 163, 184, 0.08); border: 1px solid rgba(148, 163, 184, 0.12); }
        .stat-label { color: #94a3b8; font-size: 0.75rem; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.08em; }
        .stat-value { font-size: 1rem; font-weight: 700; color: #f8fafc; }
        .progress-shell { position: relative; margin-top: 14px; }
        .progress-track { height: 12px; border-radius: 999px; background: rgba(148, 163, 184, 0.15); }
        .progress-range { position: absolute; top: 0; height: 12px; border-radius: 999px; background: linear-gradient(90deg, #16a34a 0%, #22c55e 100%); }
        .progress-marker, .progress-recommended { position: absolute; top: -4px; width: 2px; height: 20px; border-radius: 999px; transform: translateX(-50%); }
        .progress-marker { background: #f8fafc; box-shadow: 0 0 0 4px rgba(248, 250, 252, 0.15); }
        .progress-recommended { background: rgba(248, 250, 252, 0.5); }
        .progress-labels { margin-top: 10px; display: flex; justify-content: space-between; gap: 12px; color: #94a3b8; font-size: 0.82rem; }
        .is-empty { padding: 14px 0 0; }
        .progress-empty { color: #94a3b8; font-size: 0.9rem; }
        .entity-id { margin-top: 16px; color: #64748b; font-size: 0.76rem; word-break: break-all; }
        @media (max-width: 480px) { .card { padding: 16px; } .stats { grid-template-columns: 1fr; } }
      </style>
      <ha-card>
        <div class="card">
          <div class="eyebrow">
            <div class="eyebrow-copy">
              <div class="eyebrow-label">${BrizelCardUtils.escapeHtml(profileTitle)}</div>
              <div class="eyebrow-title">${BrizelCardUtils.escapeHtml(title)}</div>
            </div>
            <div class="status-pill">${BrizelCardUtils.escapeHtml(meta.label)}</div>
          </div>
          ${
            !data
              ? `<div class="display-text">Waiting for Home Assistant data.</div>`
              : `
                <div class="hero">
                  <div class="hero-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.consumed, data.unit))}</div>
                  <div class="hero-range">Target ${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetMin, data.unit))} - ${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetMax, data.unit))}</div>
                </div>
                <p class="display-text">${BrizelCardUtils.escapeHtml(data.displayText)}</p>
                <div class="stats">
                  <div class="stat"><div class="stat-label">Low</div><div class="stat-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetMin, data.unit))}</div></div>
                  <div class="stat"><div class="stat-label">Recommended</div><div class="stat-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetRecommended, data.unit))}</div></div>
                  <div class="stat"><div class="stat-label">High</div><div class="stat-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetMax, data.unit))}</div></div>
                </div>
                ${this._renderProgressBar(data)}
                <div class="entity-id">${BrizelCardUtils.escapeHtml(data.entityId)}</div>
              `
          }
        </div>
      </ha-card>
    `;
  }
}

if (!customElements.get("brizel-macro-card")) {
  customElements.define("brizel-macro-card", BrizelMacroCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "brizel-macro-card")) {
  window.customCards.push({ type: "brizel-macro-card", name: "Brizel Macro Card", description: "Shows one macro target status with progress and guidance." });
}
