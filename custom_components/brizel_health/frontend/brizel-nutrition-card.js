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
      kcal: { key: "kcal", title: "Kcal", unit: "kcal", entitySuffix: "kcal_target_status" },
      protein: { key: "protein", title: "Protein", unit: "g", entitySuffix: "protein_target_status" },
      fat: { key: "fat", title: "Fat", unit: "g", entitySuffix: "fat_target_status" },
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
      const macroConfig = MACROS[String(macro ?? "").toLowerCase()];
      if (!macroConfig) {
        throw new Error("Macro must be one of: kcal, protein, fat");
      }
      const entityId = entity || defaultEntityId(profile, macroConfig.entitySuffix);
      const stateObj = readEntity(hass, entityId);
      if (!stateObj) {
        return { ...macroConfig, entityId, status: "unavailable", displayText: "This sensor is not available yet.", consumed: null, targetMin: null, targetRecommended: null, targetMax: null, scale: null };
      }

      const attributes = stateObj.attributes ?? {};
      const consumed = toNumber(attributes.consumed);
      const targetMin = toNumber(attributes.target_min);
      const targetRecommended = toNumber(attributes.target_recommended);
      const targetMax = toNumber(attributes.target_max);

      return {
        ...macroConfig,
        entityId,
        status: String(stateObj.state ?? "unknown").toLowerCase(),
        displayText: attributes.display_text || "Target range is not available yet.",
        consumed,
        targetMin,
        targetRecommended,
        targetMax,
        scale: buildScale({ consumed, min: targetMin, recommended: targetRecommended, max: targetMax }),
      };
    };

    return { escapeHtml, formatValue, getMacroData, getStatusMeta, titleize };
  })());

class BrizelNutritionCard extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:brizel-nutrition-card", profile: "brian" };
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
    this._config = { title: "Nutrition Overview", ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return {
      rows: 5,
      columns: 6,
      min_rows: 5,
      min_columns: 6,
    };
  }

  _renderBar(data) {
    if (!data.scale) {
      return `<div class="bar-empty">Target range unavailable</div>`;
    }

    return `
      <div class="bar">
        <div class="bar-track"></div>
        <div class="bar-range" style="left:${data.scale.minPct}%; width:${Math.max(data.scale.maxPct - data.scale.minPct, 2)}%;"></div>
        ${data.scale.recommendedPct === null ? "" : `<div class="bar-recommended" style="left:${data.scale.recommendedPct}%"></div>`}
        ${data.scale.markerPct === null ? "" : `<div class="bar-marker" style="left:${data.scale.markerPct}%"></div>`}
      </div>
    `;
  }

  _renderMacroBlock(data) {
    const meta = BrizelCardUtils.getStatusMeta(data.status);
    return `
      <section class="macro-block">
        <div class="macro-head">
          <div>
            <div class="macro-title">${BrizelCardUtils.escapeHtml(data.title)}</div>
            <div class="macro-consumed">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.consumed, data.unit))}</div>
          </div>
          <div class="status-pill" style="color:${meta.color}; background:${meta.tint}; border-color: color-mix(in srgb, ${meta.color} 35%, transparent);">${BrizelCardUtils.escapeHtml(meta.label)}</div>
        </div>
        <div class="macro-range">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetMin, data.unit))} - ${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetMax, data.unit))}</div>
        ${this._renderBar(data)}
        <div class="macro-text">${BrizelCardUtils.escapeHtml(data.displayText)}</div>
      </section>
    `;
  }

  _render() {
    if (!this._config || !this.shadowRoot) {
      return;
    }

    const profileTitle = BrizelCardUtils.titleize(this._config.profile);
    const cards = this._hass
      ? [
          BrizelCardUtils.getMacroData(this._hass, { profile: this._config.profile, macro: "kcal", entity: this._config.kcal_entity }),
          BrizelCardUtils.getMacroData(this._hass, { profile: this._config.profile, macro: "protein", entity: this._config.protein_entity }),
          BrizelCardUtils.getMacroData(this._hass, { profile: this._config.profile, macro: "fat", entity: this._config.fat_entity }),
        ]
      : [];

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { border-radius: 28px; overflow: hidden; background: radial-gradient(circle at top left, rgba(34, 197, 94, 0.12), transparent 30%), radial-gradient(circle at top right, rgba(59, 130, 246, 0.16), transparent 34%), linear-gradient(180deg, #08111f 0%, #0f172a 100%); color: #eff6ff; box-shadow: 0 22px 46px rgba(15, 23, 42, 0.22); }
        .card { padding: 20px; display: grid; gap: 16px; }
        .header { display: flex; align-items: end; justify-content: space-between; gap: 12px; }
        .header-label { color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem; margin-bottom: 6px; }
        .header-title { font-size: 1.45rem; font-weight: 800; line-height: 1.15; }
        .header-subtitle { color: #cbd5e1; font-size: 0.92rem; max-width: 18rem; text-align: right; }
        .macro-grid { display: grid; gap: 14px; }
        .macro-block { padding: 16px; border-radius: 22px; background: rgba(15, 23, 42, 0.62); border: 1px solid rgba(148, 163, 184, 0.14); backdrop-filter: blur(8px); }
        .macro-head { display: flex; align-items: start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
        .macro-title { color: #cbd5e1; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
        .macro-consumed { font-size: 1.45rem; font-weight: 800; color: #f8fafc; }
        .status-pill { padding: 8px 12px; border-radius: 999px; border: 1px solid transparent; font-size: 0.78rem; font-weight: 700; white-space: nowrap; }
        .macro-range { color: #94a3b8; font-size: 0.9rem; margin-bottom: 12px; }
        .bar { position: relative; height: 12px; margin-bottom: 12px; }
        .bar-track { height: 12px; border-radius: 999px; background: rgba(148, 163, 184, 0.14); }
        .bar-range { position: absolute; top: 0; height: 12px; border-radius: 999px; background: linear-gradient(90deg, #16a34a 0%, #22c55e 100%); }
        .bar-marker, .bar-recommended { position: absolute; top: -4px; width: 2px; height: 20px; border-radius: 999px; transform: translateX(-50%); }
        .bar-marker { background: #f8fafc; box-shadow: 0 0 0 4px rgba(248, 250, 252, 0.14); }
        .bar-recommended { background: rgba(248, 250, 252, 0.45); }
        .bar-empty { color: #94a3b8; font-size: 0.9rem; margin-bottom: 12px; }
        .macro-text { color: #e2e8f0; font-size: 0.93rem; line-height: 1.45; }
        @media (max-width: 480px) { .card { padding: 16px; } .header { align-items: start; flex-direction: column; } .header-subtitle { text-align: left; } }
      </style>
      <ha-card>
        <div class="card">
          <div class="header">
            <div>
              <div class="header-label">${BrizelCardUtils.escapeHtml(profileTitle)}</div>
              <div class="header-title">${BrizelCardUtils.escapeHtml(this._config.title)}</div>
            </div>
            <div class="header-subtitle">See where you are, and what you can still do today.</div>
          </div>
          <div class="macro-grid">
            ${cards.length ? cards.map((card) => this._renderMacroBlock(card)).join("") : '<div class="macro-block"><div class="macro-text">Waiting for Home Assistant data.</div></div>'}
          </div>
        </div>
      </ha-card>
    `;
  }
}

if (!customElements.get("brizel-nutrition-card")) {
  customElements.define("brizel-nutrition-card", BrizelNutritionCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "brizel-nutrition-card")) {
  window.customCards.push({ type: "brizel-nutrition-card", name: "Brizel Nutrition Card", description: "Overview card for kcal, protein, and fat target status." });
}
