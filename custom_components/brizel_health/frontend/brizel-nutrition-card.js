import { BrizelCardUtils } from "./brizel-card-utils.js";

class BrizelNutritionCard extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:brizel-nutrition-card" };
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
    this._config = {
      title: "Nutrition Overview",
      profile: null,
      profile_id: null,
      kcal_entity: null,
      protein_entity: null,
      fat_entity: null,
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
    return 5;
  }

  getGridOptions() {
    return {
      rows: 5,
      columns: 12,
      min_rows: 5,
      min_columns: 6,
    };
  }

  _usesExplicitEntityMode() {
    return Boolean(
      BrizelCardUtils.trimToNull(this._config?.kcal_entity) ||
        BrizelCardUtils.trimToNull(this._config?.protein_entity) ||
        BrizelCardUtils.trimToNull(this._config?.fat_entity)
    );
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

  _renderBar(data) {
    if (!data.scale) {
      return `<div class="bar-empty">Target range unavailable</div>`;
    }

    return `
      <div class="bar">
        <div class="bar-track"></div>
        <div class="bar-range" style="left:${data.scale.minPct}%; width:${Math.max(
          data.scale.maxPct - data.scale.minPct,
          2
        )}%;"></div>
        ${
          data.scale.recommendedPct === null
            ? ""
            : `<div class="bar-recommended" style="left:${data.scale.recommendedPct}%"></div>`
        }
        ${
          data.scale.markerPct === null
            ? ""
            : `<div class="bar-marker" style="left:${data.scale.markerPct}%"></div>`
        }
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
            <div class="macro-consumed">${BrizelCardUtils.escapeHtml(
              BrizelCardUtils.formatValue(data.consumed, data.unit)
            )}</div>
          </div>
          <div class="status-pill" style="color:${meta.color}; background:${meta.tint}; border-color: color-mix(in srgb, ${meta.color} 35%, transparent);">${BrizelCardUtils.escapeHtml(meta.label)}</div>
        </div>
        <div class="macro-range">${BrizelCardUtils.escapeHtml(
          BrizelCardUtils.formatValue(data.targetMin, data.unit)
        )} - ${BrizelCardUtils.escapeHtml(
          BrizelCardUtils.formatValue(data.targetMax, data.unit)
        )}</div>
        ${this._renderBar(data)}
        <div class="macro-text">${BrizelCardUtils.escapeHtml(data.displayText)}</div>
      </section>
    `;
  }

  _renderStateCard(message, detail = "") {
    return `
      <section class="macro-block empty-state">
        <div class="empty-title">${BrizelCardUtils.escapeHtml(message)}</div>
        ${detail ? `<div class="empty-detail">${BrizelCardUtils.escapeHtml(detail)}</div>` : ""}
      </section>
    `;
  }

  _render() {
    if (!this._config || !this.shadowRoot) {
      return;
    }

    const explicitEntityMode = this._usesExplicitEntityMode();
    const profileTitle = BrizelCardUtils.escapeHtml(
      this._resolvedProfileName ||
        BrizelCardUtils.getConfiguredProfile(this._config) ||
        "Brizel Health"
    );
    let gridClass = "macro-grid is-state";

    let content = '<div class="macro-block"><div class="macro-text">Waiting for Home Assistant data.</div></div>';
    if (explicitEntityMode && this._hass) {
      const cards = [
        BrizelCardUtils.getMacroDataFromEntity(this._hass, {
          entityId: this._config.kcal_entity,
          macro: "kcal",
        }),
        BrizelCardUtils.getMacroDataFromEntity(this._hass, {
          entityId: this._config.protein_entity,
          macro: "protein",
        }),
        BrizelCardUtils.getMacroDataFromEntity(this._hass, {
          entityId: this._config.fat_entity,
          macro: "fat",
        }),
      ];
      gridClass = "macro-grid is-cards";
      content = cards.map((card) => this._renderMacroBlock(card)).join("");
    } else if (!explicitEntityMode) {
      if (this._state === "loading") {
        content = this._renderStateCard("Loading...");
      } else if (this._state === "profile_error") {
        content = this._renderStateCard(
          this._profileError?.title || "No Brizel profile linked",
          this._profileError?.detail || "Brizel Health could not resolve a profile for this card."
        );
      } else if (this._state === "no_data") {
        content = this._renderStateCard(
          "No data yet today",
          "Once you log food, this card will show where you stand."
        );
      } else if (this._state === "error") {
        content = this._renderStateCard(
          "Couldn't load nutrition overview",
          this._errorMessage || "Please check the Brizel Health integration."
        );
      } else if (this._overview) {
        const cards = ["kcal", "protein", "fat"].map((macro) =>
          BrizelCardUtils.getMacroDataFromOverview(this._overview, macro)
        );
        gridClass = "macro-grid is-cards";
        content = cards.map((card) => this._renderMacroBlock(card)).join("");
      }
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { border-radius: 28px; overflow: hidden; background: radial-gradient(circle at top left, rgba(34, 197, 94, 0.12), transparent 30%), radial-gradient(circle at top right, rgba(59, 130, 246, 0.16), transparent 34%), linear-gradient(180deg, #08111f 0%, #0f172a 100%); color: #eff6ff; box-shadow: 0 22px 46px rgba(15, 23, 42, 0.22); }
        .card { padding: 22px; display: grid; gap: 18px; }
        .header { display: flex; align-items: end; justify-content: space-between; gap: 12px; }
        .header-label { color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem; margin-bottom: 6px; }
        .header-title { font-size: 1.45rem; font-weight: 800; line-height: 1.15; }
        .header-subtitle { color: #cbd5e1; font-size: 0.92rem; max-width: 22rem; text-align: right; }
        .macro-grid { display: grid; gap: 14px; }
        .macro-block { padding: 18px; border-radius: 22px; background: rgba(15, 23, 42, 0.62); border: 1px solid rgba(148, 163, 184, 0.14); backdrop-filter: blur(8px); }
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
        .empty-state { text-align: center; min-height: 240px; align-content: center; }
        .empty-title { font-size: 1.2rem; font-weight: 800; margin-bottom: 10px; }
        .empty-detail { color: #cbd5e1; font-size: 0.94rem; line-height: 1.45; max-width: 24rem; margin: 0 auto; }
        .macro-grid.is-state .macro-block { grid-column: 1 / -1; }
        @media (min-width: 960px) { .macro-grid.is-cards { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
        @media (max-width: 480px) { .card { padding: 16px; } .header { align-items: start; flex-direction: column; } .header-subtitle { text-align: left; } }
      </style>
      <ha-card>
        <div class="card">
          <div class="header">
            <div>
              <div class="header-label">${profileTitle}</div>
              <div class="header-title">${BrizelCardUtils.escapeHtml(this._config.title)}</div>
            </div>
            <div class="header-subtitle">See where you are, and what you can still do today.</div>
          </div>
          <div class="${gridClass}">
            ${content}
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
  window.customCards.push({
    type: "brizel-nutrition-card",
    name: "Brizel Nutrition Card",
    description: "Overview card for kcal, protein, and fat target status.",
  });
}
