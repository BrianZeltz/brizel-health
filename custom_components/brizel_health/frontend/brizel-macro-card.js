import { BrizelCardUtils } from "./brizel-card-utils.js";

class BrizelMacroCard extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:brizel-macro-card", macro: "kcal" };
  }

  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._overview = null;
    this._resolvedProfileName = null;
    this._profileError = null;
    this._state = "loading";
    this._loading = false;
    this._errorMessage = "";
    this._lastLoadAt = 0;
    this._requestKey = "";
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config?.macro) {
      throw new Error("macro is required");
    }
    BrizelCardUtils.getMacroConfig(config.macro);
    this._config = {
      title: null,
      profile: null,
      profile_id: null,
      entity: null,
      ...config,
    };
    this._requestKey = "";
    this._overview = null;
    this._resolvedProfileName = null;
    this._profileError = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._maybeLoadOverview();
    this._render();
  }

  getCardSize() {
    return 4;
  }

  getGridOptions() {
    return {
      rows: 4,
      columns: 8,
      min_rows: 4,
      min_columns: 6,
    };
  }

  _usesExplicitEntityMode() {
    return Boolean(BrizelCardUtils.trimToNull(this._config?.entity));
  }

  async _maybeLoadOverview(force = false) {
    if (!this._config || !this._hass || this._loading || this._usesExplicitEntityMode()) {
      return;
    }

    const requestKey = BrizelCardUtils.buildProfileRequestKey(this._hass, this._config);
    const now = Date.now();

    if (
      !force &&
      requestKey === this._requestKey &&
      this._overview !== null &&
      now - this._lastLoadAt < 5000
    ) {
      return;
    }

    this._loading = true;
    this._state = "loading";
    this._profileError = null;
    this._errorMessage = "";
    this._render();

    try {
      const result = await BrizelCardUtils.loadDailyOverview(this._hass, this._config);
      this._overview = result.data;
      this._resolvedProfileName = result.profileDisplayName;
      this._requestKey = requestKey;
      this._lastLoadAt = now;
      this._profileError = result.error;

      if (result.state === "ready") {
        this._state = "ready";
      } else if (result.state === "no_data") {
        this._state = "no_data";
      } else if (result.state === "profile_error") {
        this._state = "profile_error";
      } else {
        this._state = "error";
        this._errorMessage = result.error?.detail || "Please check the Brizel Health integration.";
      }
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _renderProgressBar(data) {
    if (!data.scale) {
      return `<div class="progress-shell is-empty"><div class="progress-empty">Target range unavailable</div></div>`;
    }

    return `
      <div class="progress-shell">
        <div class="progress-track"></div>
        <div class="progress-range" style="left:${data.scale.minPct}%; width:${Math.max(
          data.scale.maxPct - data.scale.minPct,
          2
        )}%;"></div>
        ${
          data.scale.recommendedPct === null
            ? ""
            : `<div class="progress-recommended" style="left:${data.scale.recommendedPct}%"></div>`
        }
        ${
          data.scale.markerPct === null
            ? ""
            : `<div class="progress-marker" style="left:${data.scale.markerPct}%"></div>`
        }
        <div class="progress-labels">
          <span>${BrizelCardUtils.formatValue(data.targetMin, data.unit)}</span>
          <span>${BrizelCardUtils.formatValue(data.targetMax, data.unit)}</span>
        </div>
      </div>
    `;
  }

  _renderStateCard(message, detail = "") {
    return `
      <div class="display-text state-card">
        <div class="state-title">${BrizelCardUtils.escapeHtml(message)}</div>
        ${detail ? `<div class="state-detail">${BrizelCardUtils.escapeHtml(detail)}</div>` : ""}
      </div>
    `;
  }

  _render() {
    if (!this._config || !this.shadowRoot) {
      return;
    }

    const macroConfig = BrizelCardUtils.getMacroConfig(this._config.macro);
    const title = this._config.title || `${macroConfig.title} Detail`;
    const profileTitle =
      this._resolvedProfileName ||
      BrizelCardUtils.getConfiguredProfile(this._config) ||
      "Brizel Health";

    let data = null;
    let body = '<div class="display-text">Waiting for Home Assistant data.</div>';

    if (this._usesExplicitEntityMode() && this._hass) {
      data = BrizelCardUtils.getMacroDataFromEntity(this._hass, {
        entityId: this._config.entity,
        macro: this._config.macro,
      });
    } else if (!this._usesExplicitEntityMode()) {
      if (this._state === "loading") {
        body = this._renderStateCard("Loading...");
      } else if (this._state === "profile_error") {
        body = this._renderStateCard(
          this._profileError?.title || "No Brizel profile linked",
          this._profileError?.detail || "Brizel Health could not resolve a profile for this card."
        );
      } else if (this._state === "no_data") {
        body = this._renderStateCard(
          "No data yet today",
          "Once you log food, this card will show where you stand."
        );
      } else if (this._state === "error") {
        body = this._renderStateCard(
          "Couldn't load macro details",
          this._errorMessage || "Please check the Brizel Health integration."
        );
      } else if (this._overview) {
        data = BrizelCardUtils.getMacroDataFromOverview(this._overview, this._config.macro);
      }
    }

    if (data) {
      const meta = BrizelCardUtils.getStatusMeta(data.status);
      body = `
        <div class="hero">
          <div class="hero-value">${BrizelCardUtils.escapeHtml(
            BrizelCardUtils.formatValue(data.consumed, data.unit)
          )}</div>
          <div class="hero-range">Target ${BrizelCardUtils.escapeHtml(
            BrizelCardUtils.formatValue(data.targetMin, data.unit)
          )} - ${BrizelCardUtils.escapeHtml(
            BrizelCardUtils.formatValue(data.targetMax, data.unit)
          )}</div>
        </div>
        <p class="display-text">${BrizelCardUtils.escapeHtml(data.displayText)}</p>
        <div class="stats">
          <div class="stat"><div class="stat-label">Low</div><div class="stat-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetMin, data.unit))}</div></div>
          <div class="stat"><div class="stat-label">Recommended</div><div class="stat-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetRecommended, data.unit))}</div></div>
          <div class="stat"><div class="stat-label">High</div><div class="stat-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(data.targetMax, data.unit))}</div></div>
        </div>
        ${this._renderProgressBar(data)}
        ${
          this._usesExplicitEntityMode()
            ? `<div class="entity-id">${BrizelCardUtils.escapeHtml(this._config.entity)}</div>`
            : ""
        }
      `;

      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; }
          ha-card { border-radius: 24px; overflow: hidden; background: radial-gradient(circle at top right, rgba(255, 255, 255, 0.08), transparent 35%), linear-gradient(180deg, #101828 0%, #0f172a 100%); color: #e5edf7; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.18); }
          .card { padding: 22px; display: grid; gap: 18px; }
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
          .state-card { text-align: center; padding: 28px 12px; }
          .state-title { font-size: 1.15rem; font-weight: 800; margin-bottom: 10px; }
          .state-detail { color: #cbd5e1; font-size: 0.94rem; line-height: 1.45; max-width: 24rem; margin: 0 auto; }
          @media (min-width: 960px) { .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
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
            ${body}
          </div>
        </ha-card>
      `;
      return;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { border-radius: 24px; overflow: hidden; background: radial-gradient(circle at top right, rgba(255, 255, 255, 0.08), transparent 35%), linear-gradient(180deg, #101828 0%, #0f172a 100%); color: #e5edf7; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.18); }
        .card { padding: 22px; display: grid; gap: 18px; }
        .eyebrow { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
        .eyebrow-copy { display: grid; gap: 4px; }
        .eyebrow-label { color: #94a3b8; font-size: 0.77rem; letter-spacing: 0.08em; text-transform: uppercase; }
        .eyebrow-title { font-size: 1.25rem; font-weight: 700; line-height: 1.2; }
        .status-pill { padding: 8px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 700; color: ${BrizelCardUtils.getStatusMeta("unknown").color}; background: ${BrizelCardUtils.getStatusMeta("unknown").tint}; border: 1px solid rgba(148, 163, 184, 0.2); white-space: nowrap; }
        .display-text { color: #f8fafc; font-size: 0.96rem; line-height: 1.45; margin: 0; }
        .state-card { text-align: center; padding: 28px 12px; }
        .state-title { font-size: 1.15rem; font-weight: 800; margin-bottom: 10px; }
        .state-detail { color: #cbd5e1; font-size: 0.94rem; line-height: 1.45; max-width: 24rem; margin: 0 auto; }
      </style>
      <ha-card>
        <div class="card">
          <div class="eyebrow">
            <div class="eyebrow-copy">
              <div class="eyebrow-label">${BrizelCardUtils.escapeHtml(profileTitle)}</div>
              <div class="eyebrow-title">${BrizelCardUtils.escapeHtml(title)}</div>
            </div>
            <div class="status-pill">Unknown</div>
          </div>
          ${body}
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
  window.customCards.push({
    type: "brizel-macro-card",
    name: "Brizel Macro Card",
    description: "Shows one macro target status with progress and guidance.",
  });
}
