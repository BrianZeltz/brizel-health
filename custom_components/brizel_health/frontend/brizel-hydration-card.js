const BrizelHydrationUtils =
  window.BrizelHydrationUtils ||
  (window.BrizelHydrationUtils = (() => {
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

    const formatMl = (value) => {
      const formatted = formatNumber(value);
      return formatted === "-" ? formatted : `${formatted} ml`;
    };

    const defaultEntityId = (profile, suffix) => {
      const slug = slugify(profile);
      return slug ? `sensor.${slug}_${suffix}` : "";
    };

    const readEntity = (hass, entityId) => (entityId ? hass?.states?.[entityId] ?? null : null);

    return { defaultEntityId, escapeHtml, formatMl, readEntity, titleize, toNumber };
  })());

class BrizelHydrationCard extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:brizel-hydration-card", profile: "brian" };
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
    this._config = { title: "Hydration", ...config };
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

  _render() {
    if (!this._config || !this.shadowRoot) {
      return;
    }

    const profileTitle = BrizelHydrationUtils.titleize(this._config.profile);
    const totalEntity = this._config.total_entity || BrizelHydrationUtils.defaultEntityId(this._config.profile, "total_hydration_today");
    const drankEntity = this._config.drank_entity || BrizelHydrationUtils.defaultEntityId(this._config.profile, "drank_today");
    const foodEntity = this._config.food_entity || BrizelHydrationUtils.defaultEntityId(this._config.profile, "food_hydration_today");
    const targetEntity = this._config.target_entity || null;

    const totalState = BrizelHydrationUtils.readEntity(this._hass, totalEntity);
    const drankState = BrizelHydrationUtils.readEntity(this._hass, drankEntity);
    const foodState = BrizelHydrationUtils.readEntity(this._hass, foodEntity);
    const targetState = BrizelHydrationUtils.readEntity(this._hass, targetEntity);

    const total = BrizelHydrationUtils.toNumber(totalState?.state);
    const drank = BrizelHydrationUtils.toNumber(drankState?.state);
    const foodHydration = BrizelHydrationUtils.toNumber(foodState?.state);
    const target = BrizelHydrationUtils.toNumber(targetState?.state);
    const progress = total !== null && target !== null && target > 0 ? Math.min((total / target) * 100, 100) : null;

    const helperText =
      total !== null && target !== null && target > 0
        ? total <= target
          ? `${BrizelHydrationUtils.formatMl(target - total)} left to your target`
          : `${BrizelHydrationUtils.formatMl(total - target)} above your target`
        : "Add a target entity later if you want a hydration goal bar.";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { border-radius: 28px; overflow: hidden; background: radial-gradient(circle at top right, rgba(56, 189, 248, 0.18), transparent 35%), linear-gradient(180deg, #082032 0%, #0f172a 100%); color: #eff6ff; box-shadow: 0 22px 46px rgba(8, 32, 50, 0.22); }
        .card { padding: 20px; display: grid; gap: 16px; }
        .header-label { color: #93c5fd; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem; margin-bottom: 6px; }
        .header-title { font-size: 1.45rem; font-weight: 800; }
        .hero { display: flex; align-items: end; justify-content: space-between; gap: 12px; }
        .hero-value { font-size: 2.2rem; font-weight: 800; line-height: 1; }
        .hero-copy { color: #cbd5e1; font-size: 0.94rem; line-height: 1.4; }
        .drops { color: #7dd3fc; }
        .progress-wrap { display: grid; gap: 10px; }
        .progress-track { height: 14px; border-radius: 999px; background: rgba(147, 197, 253, 0.16); overflow: hidden; }
        .progress-value { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #38bdf8 0%, #0ea5e9 100%); }
        .progress-labels { display: flex; justify-content: space-between; gap: 12px; color: #cbd5e1; font-size: 0.88rem; }
        .helper-text { color: #dbeafe; font-size: 0.93rem; line-height: 1.4; }
        .stat-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
        .stat { padding: 14px; border-radius: 18px; background: rgba(147, 197, 253, 0.08); border: 1px solid rgba(147, 197, 253, 0.14); }
        .stat-label { color: #93c5fd; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.74rem; margin-bottom: 6px; }
        .stat-value { font-size: 1rem; font-weight: 700; color: #f8fafc; }
        .entity-list { color: #7dd3fc; font-size: 0.75rem; line-height: 1.4; word-break: break-all; }
        @media (max-width: 480px) { .card { padding: 16px; } .hero { flex-direction: column; align-items: start; } .stat-grid { grid-template-columns: 1fr; } }
      </style>
      <ha-card>
        <div class="card">
          <div>
            <div class="header-label">${BrizelHydrationUtils.escapeHtml(profileTitle)}</div>
            <div class="header-title">${BrizelHydrationUtils.escapeHtml(this._config.title)}</div>
          </div>
          <div class="hero">
            <div>
              <div class="hero-value">${BrizelHydrationUtils.escapeHtml(BrizelHydrationUtils.formatMl(total))}</div>
              <div class="hero-copy">Total hydration today</div>
            </div>
            <ha-icon class="drops" icon="mdi:water"></ha-icon>
          </div>
          <div class="progress-wrap">
            <div class="progress-track"><div class="progress-value" style="width:${progress === null ? 0 : progress}%"></div></div>
            <div class="progress-labels">
              <span>${BrizelHydrationUtils.escapeHtml(BrizelHydrationUtils.formatMl(total))}</span>
              <span>${target === null ? "No target" : BrizelHydrationUtils.escapeHtml(BrizelHydrationUtils.formatMl(target))}</span>
            </div>
          </div>
          <div class="helper-text">${BrizelHydrationUtils.escapeHtml(helperText)}</div>
          <div class="stat-grid">
            <div class="stat"><div class="stat-label">Drank</div><div class="stat-value">${BrizelHydrationUtils.escapeHtml(BrizelHydrationUtils.formatMl(drank))}</div></div>
            <div class="stat"><div class="stat-label">From Food</div><div class="stat-value">${BrizelHydrationUtils.escapeHtml(BrizelHydrationUtils.formatMl(foodHydration))}</div></div>
          </div>
          <div class="entity-list">
            total: ${BrizelHydrationUtils.escapeHtml(totalEntity)}<br>
            drank: ${BrizelHydrationUtils.escapeHtml(drankEntity)}<br>
            food: ${BrizelHydrationUtils.escapeHtml(foodEntity)}
            ${targetEntity ? `<br>target: ${BrizelHydrationUtils.escapeHtml(targetEntity)}` : ""}
          </div>
        </div>
      </ha-card>
    `;
  }
}

if (!customElements.get("brizel-hydration-card")) {
  customElements.define("brizel-hydration-card", BrizelHydrationCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "brizel-hydration-card")) {
  window.customCards.push({ type: "brizel-hydration-card", name: "Brizel Hydration Card", description: "Hydration overview with drank, food hydration, and optional goal progress." });
}
