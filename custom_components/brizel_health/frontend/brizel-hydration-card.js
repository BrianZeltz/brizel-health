import { BrizelCardUtils } from "./brizel-card-utils.js";

class BrizelHydrationCard extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:brizel-hydration-card" };
  }

  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._hydration = null;
    this._resolvedProfileId = null;
    this._resolvedProfileName = null;
    this._profileError = null;
    this._state = "loading";
    this._loading = false;
    this._errorMessage = "";
    this._lastLoadAt = 0;
    this._requestKey = "";
    this._profileRefreshUnsubscribe = null;
    this._profileLanguageChoice = "auto";
    this._languageProfileRequestKey = "";
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = {
      title: null,
      profile: null,
      profile_id: null,
      total_entity: null,
      drank_entity: null,
      food_entity: null,
      target_entity: null,
      ...config,
    };
    this._requestKey = "";
    this._hydration = null;
    this._resolvedProfileId = null;
    this._resolvedProfileName = null;
    this._profileError = null;
    this._profileLanguageChoice = "auto";
    this._languageProfileRequestKey = "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._maybeLoadConfiguredProfileLanguage();
    this._maybeLoadHydration();
    this._render();
  }

  connectedCallback() {
    if (!this._profileRefreshUnsubscribe) {
      this._profileRefreshUnsubscribe = BrizelCardUtils.addProfileRefreshListener((detail) => {
        if (
          BrizelCardUtils.matchesProfileRefresh({
            config: this._config,
            resolvedProfileId: this._resolvedProfileId,
            detail,
          })
        ) {
          this._maybeLoadHydration(true);
        }
      });
    }
  }

  disconnectedCallback() {
    if (this._profileRefreshUnsubscribe) {
      this._profileRefreshUnsubscribe();
      this._profileRefreshUnsubscribe = null;
    }
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

  _getLanguageContext() {
    return {
      hass: this._hass,
      preferredLanguage: this._profileLanguageChoice,
    };
  }

  _t(key, vars = {}) {
    return BrizelCardUtils.translateText(this._getLanguageContext(), key, vars);
  }

  _getCardTitle() {
    return BrizelCardUtils.trimToNull(this._config?.title) || this._t("hydrationCard.titleDefault");
  }

  async _loadProfileLanguagePreference(profileId) {
    const normalizedProfileId = BrizelCardUtils.trimToNull(profileId);
    if (!this._hass || !normalizedProfileId || this._languageProfileRequestKey === normalizedProfileId) {
      return;
    }
    this._languageProfileRequestKey = normalizedProfileId;
    try {
      const profile = await BrizelCardUtils.getProfile(this._hass, { profileId: normalizedProfileId });
      if (this._languageProfileRequestKey === normalizedProfileId) {
        this._profileLanguageChoice = profile?.preferred_language || "auto";
        this._render();
      }
    } catch (_error) {
      if (this._languageProfileRequestKey === normalizedProfileId) {
        this._profileLanguageChoice = "auto";
        this._render();
      }
    }
  }

  _maybeLoadConfiguredProfileLanguage() {
    const configuredProfileId = BrizelCardUtils.getConfiguredProfile(this._config);
    if (configuredProfileId) {
      void this._loadProfileLanguagePreference(configuredProfileId);
    }
  }

  _usesExplicitEntityMode() {
    return Boolean(
      BrizelCardUtils.trimToNull(this._config?.total_entity) ||
        BrizelCardUtils.trimToNull(this._config?.drank_entity) ||
        BrizelCardUtils.trimToNull(this._config?.food_entity)
    );
  }

  async _maybeLoadHydration(force = false) {
    if (!this._config || !this._hass || this._loading || this._usesExplicitEntityMode()) {
      return;
    }

    const requestKey = BrizelCardUtils.buildProfileRequestKey(this._hass, this._config);
    const now = Date.now();

    if (
      !force &&
      requestKey === this._requestKey &&
      this._hydration !== null &&
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
      const result = await BrizelCardUtils.loadDailyHydrationReport(this._hass, this._config);
      this._hydration = result.data;
      this._resolvedProfileId = result.profileId;
      this._resolvedProfileName = result.profileDisplayName;
      this._requestKey = requestKey;
      this._lastLoadAt = now;
      this._profileError = result.error;
      if (!BrizelCardUtils.getConfiguredProfile(this._config) && result.profileId) {
        void this._loadProfileLanguagePreference(result.profileId);
      }

      if (result.state === "ready") {
        this._state = "ready";
      } else if (result.state === "no_data") {
        this._state = "no_data";
      } else if (result.state === "profile_error") {
        this._state = "profile_error";
      } else {
        this._state = "error";
        this._errorMessage = result.error?.detail || this._t("profileError.genericDetail");
      }
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _buildHydrationViewModel() {
    if (this._usesExplicitEntityMode()) {
      return BrizelCardUtils.getHydrationDataFromEntities(this._hass, this._config);
    }

    const targetEntity = BrizelCardUtils.trimToNull(this._config?.target_entity);
    const targetState = BrizelCardUtils.readEntity(this._hass, targetEntity);
    const target = BrizelCardUtils.toNumber(targetState?.state);
    const total = BrizelCardUtils.toNumber(this._hydration?.total_hydration_ml);
    const drank = BrizelCardUtils.toNumber(this._hydration?.drank_ml);
    const foodHydration = BrizelCardUtils.toNumber(this._hydration?.food_hydration_ml);
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
      hasData:
        (total ?? 0) > 0 || (drank ?? 0) > 0 || (foodHydration ?? 0) > 0,
      goalConfigured: Boolean(targetEntity),
      goalAvailable: target !== null && target > 0,
      entityIds: {
        total: null,
        drank: null,
        food: null,
        target: targetEntity,
      },
    };
  }

  _renderStateCard(message, detail = "") {
    return `
      <div class="state-card">
        <div class="state-title">${BrizelCardUtils.escapeHtml(message)}</div>
        ${detail ? `<div class="state-detail">${BrizelCardUtils.escapeHtml(detail)}</div>` : ""}
      </div>
    `;
  }

  _render() {
    if (!this._config || !this.shadowRoot) {
      return;
    }

    const profileTitle = BrizelCardUtils.escapeHtml(
      this._resolvedProfileName ||
        BrizelCardUtils.getConfiguredProfile(this._config) ||
        this._t("app.title")
    );

    let body = `<div class="helper-text">${BrizelCardUtils.escapeHtml(
      this._t("hydrationCard.waitingEntity")
    )}</div>`;

    if (!this._usesExplicitEntityMode()) {
      if (this._state === "loading") {
        body = this._renderStateCard(this._t("hydrationCard.stateLoading"));
      } else if (this._state === "profile_error") {
        body = this._renderStateCard(
          this._profileError?.title || this._t("profileError.noLinkTitle"),
          this._profileError?.detail || this._t("profileError.noLinkDetail")
        );
      } else if (this._state === "no_data") {
        body = this._renderStateCard(
          this._t("hydrationCard.stateNoDataTitle"),
          this._t("hydrationCard.stateNoDataDetail")
        );
      } else if (this._state === "error") {
        body = this._renderStateCard(
          this._t("hydrationCard.stateErrorTitle"),
          this._errorMessage || this._t("profileError.genericDetail")
        );
      }
    }

    const model =
      this._hass &&
      (this._usesExplicitEntityMode() || this._state === "ready")
        ? this._buildHydrationViewModel()
        : null;

    if (model) {
      const helperText =
        model.totalHydrationMl !== null &&
        model.goalAvailable
          ? model.totalHydrationMl <= model.targetMl
            ? this._t("hydrationCard.helperLeft", {
                amount: BrizelCardUtils.formatMl(model.targetMl - model.totalHydrationMl),
              })
            : this._t("hydrationCard.helperAbove", {
                amount: BrizelCardUtils.formatMl(model.totalHydrationMl - model.targetMl),
              })
          : model.goalConfigured
          ? this._t("hydrationCard.helperEntityUnavailable")
          : this._t("hydrationCard.helperNoGoalConfigured");

      body = `
        <div class="content-grid">
          <div class="main-panel">
            <div class="hero">
              <div>
                <div class="hero-value">${BrizelCardUtils.escapeHtml(
                  BrizelCardUtils.formatMl(model.totalHydrationMl)
                )}</div>
                <div class="hero-copy">${BrizelCardUtils.escapeHtml(
                  this._t("hydrationCard.totalToday")
                )}</div>
              </div>
              <ha-icon class="drops" icon="mdi:water"></ha-icon>
            </div>
            <div class="progress-wrap">
              <div class="progress-track"><div class="progress-value" style="width:${
                model.progress === null ? 0 : model.progress
              }%"></div></div>
              <div class="progress-labels">
                <span>${BrizelCardUtils.escapeHtml(
                  BrizelCardUtils.formatMl(model.totalHydrationMl)
                )}</span>
                <span>${
                  model.goalAvailable
                    ? BrizelCardUtils.escapeHtml(BrizelCardUtils.formatMl(model.targetMl))
                    : model.goalConfigured
                    ? BrizelCardUtils.escapeHtml(this._t("hydrationCard.goalUnavailable"))
                    : BrizelCardUtils.escapeHtml(this._t("hydrationCard.noGoalConfigured"))
                }</span>
              </div>
            </div>
            <div class="helper-text">${BrizelCardUtils.escapeHtml(helperText)}</div>
          </div>
          <div class="side-panel">
            <div class="stat-grid">
              <div class="stat"><div class="stat-label">${BrizelCardUtils.escapeHtml(this._t("hydrationCard.drank"))}</div><div class="stat-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatMl(model.drankMl))}</div></div>
              <div class="stat"><div class="stat-label">${BrizelCardUtils.escapeHtml(this._t("hydrationCard.fromFood"))}</div><div class="stat-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatMl(model.foodHydrationMl))}</div></div>
            </div>
            ${
              this._usesExplicitEntityMode()
                ? `
                  <div class="entity-list">
                    ${BrizelCardUtils.escapeHtml(this._t("hydrationCard.entityTotal"))}: ${BrizelCardUtils.escapeHtml(model.entityIds.total)}<br>
                    ${BrizelCardUtils.escapeHtml(this._t("hydrationCard.entityDrank"))}: ${BrizelCardUtils.escapeHtml(model.entityIds.drank)}<br>
                    ${BrizelCardUtils.escapeHtml(this._t("hydrationCard.entityFood"))}: ${BrizelCardUtils.escapeHtml(model.entityIds.food)}
                    ${model.entityIds.target ? `<br>${BrizelCardUtils.escapeHtml(this._t("hydrationCard.entityTarget"))}: ${BrizelCardUtils.escapeHtml(model.entityIds.target)}` : ""}
                  </div>
                `
                : ""
            }
          </div>
        </div>
      `;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { border-radius: 28px; overflow: hidden; background: radial-gradient(circle at top right, rgba(56, 189, 248, 0.18), transparent 35%), linear-gradient(180deg, #082032 0%, #0f172a 100%); color: #eff6ff; box-shadow: 0 22px 46px rgba(8, 32, 50, 0.22); }
        .card { padding: 22px; display: grid; gap: 18px; }
        .header-label { color: #93c5fd; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem; margin-bottom: 6px; }
        .header-title { font-size: 1.45rem; font-weight: 800; }
        .content-grid { display: grid; gap: 16px; }
        .main-panel, .side-panel { display: grid; gap: 16px; align-content: start; }
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
        .state-card { padding: 36px 12px; text-align: center; min-height: 240px; align-content: center; }
        .state-title { font-size: 1.2rem; font-weight: 800; margin-bottom: 10px; }
        .state-detail { color: #dbeafe; font-size: 0.94rem; line-height: 1.45; max-width: 24rem; margin: 0 auto; }
        @media (min-width: 900px) {
          .content-grid { grid-template-columns: minmax(0, 1.35fr) minmax(16rem, 0.9fr); }
          .stat-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 480px) { .card { padding: 16px; } .hero { flex-direction: column; align-items: start; } .stat-grid { grid-template-columns: 1fr; } }
      </style>
      <ha-card>
        <div class="card">
          <div>
            <div class="header-label">${profileTitle}</div>
            <div class="header-title">${BrizelCardUtils.escapeHtml(this._getCardTitle())}</div>
          </div>
          ${body}
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
  window.customCards.push({
    type: "brizel-hydration-card",
    name: "Brizel Hydration Card",
    description: "Hydration overview with drank, food hydration, and optional goal progress.",
  });
}
