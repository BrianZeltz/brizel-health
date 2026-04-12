import { BrizelCardUtils } from "./brizel-card-utils.js";

class BrizelHealthHeroCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: "custom:brizel-health-hero-card",
    };
  }

  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._overview = null;
    this._resolvedProfileId = null;
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
      title: "Today",
      profile: null,
      profile_id: null,
      ...config,
    };
    this._requestKey = "";
    this._overview = null;
    this._resolvedProfileId = null;
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

  async _maybeLoadOverview(force = false) {
    if (!this._config || !this._hass || this._loading) {
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
    this._errorMessage = "";
    this._profileError = null;
    this._render();

    try {
      const result = await BrizelCardUtils.loadDailyOverview(this._hass, this._config);

      this._overview = result.data;
      this._resolvedProfileId = result.profileId;
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

  _formatNumber(value) {
    return BrizelCardUtils.formatNumber(value);
  }

  _formatValue(value, unit) {
    return BrizelCardUtils.formatValue(value, unit);
  }

  _statusMeta(status) {
    const meta = BrizelCardUtils.getStatusMeta(status);
    return {
      label: meta.label,
      color:
        status === "under"
          ? "#94a3b8"
          : status === "within"
          ? "#22c55e"
          : status === "over"
          ? "#475569"
          : meta.color,
      accent:
        status === "under"
          ? "#64748b"
          : status === "within"
          ? "#16a34a"
          : status === "over"
          ? "#334155"
          : "#64748b",
    };
  }

  _calculateHeroScale(kcal) {
    const consumed = BrizelCardUtils.toNumber(kcal?.consumed);
    const targetMin = BrizelCardUtils.toNumber(kcal?.target_min);
    const targetRecommended = BrizelCardUtils.toNumber(kcal?.target_recommended);
    const targetMax = BrizelCardUtils.toNumber(kcal?.target_max);

    if (
      consumed === null ||
      targetMin === null ||
      targetRecommended === null ||
      targetMax === null ||
      targetMin <= 0 ||
      targetMax <= 0 ||
      targetMax < targetMin
    ) {
      return null;
    }

    const targetRange = Math.max(targetMax - targetMin, 1);
    const scaleUpper = targetMax + Math.max(targetRange, targetMax * 0.15, 1);
    const toProgress = (value) =>
      BrizelCardUtils.clamp((Math.max(value, 0) / scaleUpper) * 100, 0, 100);

    const minProgress = toProgress(targetMin);
    const maxProgress = toProgress(targetMax);
    const recommendedProgress = toProgress(targetRecommended);
    const markerProgress = toProgress(consumed);

    return {
      markerProgress,
      consumedProgress: markerProgress,
      minProgress,
      maxProgress,
      targetWidth: Math.max(maxProgress - minProgress, 2),
      recommendedProgress,
      markerPoint: this._progressToPoint(markerProgress),
    };
  }

  _progressToPoint(progress) {
    const centerX = 110;
    const centerY = 110;
    const radius = 92;
    const clamped = Math.max(0, Math.min(progress, 100));
    const angle = Math.PI - Math.PI * (clamped / 100);

    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY - radius * Math.sin(angle),
    };
  }

  _renderStateCard(message, detail = "") {
    return `
      <div class="empty-state">
        <div class="empty-title">${BrizelCardUtils.escapeHtml(message)}</div>
        ${detail ? `<div class="empty-detail">${BrizelCardUtils.escapeHtml(detail)}</div>` : ""}
      </div>
    `;
  }

  _renderMiniMacro(label, macro) {
    const status = this._statusMeta(macro?.status);
    return `
      <div class="mini-macro">
        <div class="mini-label">${BrizelCardUtils.escapeHtml(label)}</div>
        <div class="mini-status" style="color:${status.color}">
          ${BrizelCardUtils.escapeHtml(status.label)}
        </div>
      </div>
    `;
  }

  _renderHeroContent() {
    const kcal = this._overview?.kcal;
    const protein = this._overview?.protein;
    const fat = this._overview?.fat;
    const scale = this._calculateHeroScale(kcal);
    const status = this._statusMeta(kcal?.status);
    const profileLabel =
      this._resolvedProfileName ||
      this._resolvedProfileId ||
      BrizelCardUtils.getConfiguredProfile(this._config) ||
      "Profile";

    return `
      <div class="hero-top">
        <div>
          <div class="hero-label">Today</div>
          <div class="hero-title">${BrizelCardUtils.escapeHtml(
            this._config.title || "Today"
          )}</div>
        </div>
        <div class="profile-pill">${BrizelCardUtils.escapeHtml(profileLabel)}</div>
      </div>

      <div class="hero-focus">
        <div class="status-pill" style="color:${status.color}; background:${status.color}1a;">
          ${BrizelCardUtils.escapeHtml(status.label)}
        </div>
        <div class="kcal-value">${BrizelCardUtils.escapeHtml(
          this._formatValue(kcal?.consumed, "kcal")
        )}</div>
        <div class="kcal-range">
          Range ${BrizelCardUtils.escapeHtml(this._formatValue(kcal?.target_min, "kcal"))}
          -
          ${BrizelCardUtils.escapeHtml(this._formatValue(kcal?.target_max, "kcal"))}
        </div>
        <div class="display-text">${BrizelCardUtils.escapeHtml(
          kcal?.display_text || "Target range is not available yet."
        )}</div>
      </div>

      <div class="hero-visual">
        ${
          scale
            ? `
              <svg viewBox="0 0 220 140" class="gauge" role="img" aria-label="Kcal progress">
                <path class="gauge-base" d="M 18 110 A 92 92 0 0 1 202 110" pathLength="100"></path>
                <path class="gauge-target" d="M 18 110 A 92 92 0 0 1 202 110" pathLength="100" style="stroke-dasharray:${scale.targetWidth} 100; stroke-dashoffset:-${scale.minProgress};"></path>
                <path class="gauge-progress gauge-progress-${BrizelCardUtils.escapeHtml(
                  kcal?.status || "unknown"
                )}" d="M 18 110 A 92 92 0 0 1 202 110" pathLength="100" style="stroke-dasharray:${scale.consumedProgress} 100;"></path>
                <path class="gauge-recommended" d="M 18 110 A 92 92 0 0 1 202 110" pathLength="100" style="stroke-dasharray:1.5 100; stroke-dashoffset:-${scale.recommendedProgress};"></path>
                <circle class="gauge-marker" cx="${scale.markerPoint.x}" cy="${scale.markerPoint.y}" r="6"></circle>
              </svg>
              <div class="gauge-labels">
                <span class="gauge-label gauge-label-start" style="left:0%;">0</span>
                <span class="gauge-label" style="left:${scale.minProgress}%;">Low ${BrizelCardUtils.escapeHtml(this._formatNumber(kcal?.target_min))}</span>
                <span class="gauge-label gauge-label-end" style="left:${scale.maxProgress}%;">High ${BrizelCardUtils.escapeHtml(this._formatNumber(kcal?.target_max))}</span>
              </div>
            `
            : `
              <div class="empty-visual">Target range unavailable</div>
            `
        }
      </div>

      <div class="macro-strip">
        ${this._renderMiniMacro("Protein", protein)}
        ${this._renderMiniMacro("Fat", fat)}
      </div>
    `;
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }

    const content =
      this._state === "loading"
        ? this._renderStateCard("Loading...")
        : this._state === "profile_error"
        ? this._renderStateCard(
            this._profileError?.title || "No Brizel profile linked",
            this._profileError?.detail || "Brizel Health could not resolve a profile for this card."
          )
        : this._state === "no_data"
        ? this._renderStateCard(
            "No data yet today",
            "Once you log food, this card will show where you stand."
          )
        : this._state === "error"
        ? this._renderStateCard(
            "Couldn't load today's overview",
            this._errorMessage || "Please check the Brizel Health integration."
          )
        : this._renderHeroContent();

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        ha-card {
          border-radius: 30px;
          overflow: hidden;
          background:
            radial-gradient(circle at top left, rgba(16, 185, 129, 0.18), transparent 26%),
            radial-gradient(circle at top right, rgba(59, 130, 246, 0.18), transparent 30%),
            linear-gradient(180deg, #08111f 0%, #111827 100%);
          color: #f8fafc;
          box-shadow: 0 24px 50px rgba(15, 23, 42, 0.24);
        }

        .card {
          padding: 22px;
          display: grid;
          gap: 18px;
        }

        .hero-top {
          display: flex;
          align-items: start;
          justify-content: space-between;
          gap: 12px;
        }

        .hero-label {
          color: #94a3b8;
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          margin-bottom: 6px;
        }

        .hero-title {
          font-size: 1.65rem;
          font-weight: 800;
          line-height: 1.1;
        }

        .profile-pill {
          padding: 8px 12px;
          border-radius: 999px;
          background: rgba(148, 163, 184, 0.12);
          color: #dbeafe;
          font-size: 0.82rem;
          font-weight: 700;
          white-space: nowrap;
        }

        .hero-focus {
          display: grid;
          gap: 10px;
        }

        .status-pill {
          width: fit-content;
          padding: 8px 12px;
          border-radius: 999px;
          font-size: 0.82rem;
          font-weight: 700;
        }

        .kcal-value {
          font-size: 2.5rem;
          font-weight: 900;
          line-height: 1;
        }

        .kcal-range {
          color: #cbd5e1;
          font-size: 0.95rem;
        }

        .display-text {
          color: #f8fafc;
          font-size: 1.02rem;
          line-height: 1.45;
          padding: 14px 16px;
          border-radius: 18px;
          background: rgba(15, 23, 42, 0.5);
          border: 1px solid rgba(148, 163, 184, 0.12);
        }

        .hero-visual {
          display: grid;
          gap: 8px;
        }

        .gauge {
          width: 100%;
          height: auto;
          overflow: visible;
        }

        .gauge-base,
        .gauge-target,
        .gauge-progress,
        .gauge-recommended {
          fill: none;
          stroke-linecap: round;
        }

        .gauge-base {
          stroke: rgba(148, 163, 184, 0.18);
          stroke-width: 16;
        }

        .gauge-target {
          stroke: rgba(34, 197, 94, 0.24);
          stroke-width: 16;
        }

        .gauge-progress {
          stroke-width: 16;
        }

        .gauge-progress-under {
          stroke: #94a3b8;
        }

        .gauge-progress-within {
          stroke: #22c55e;
        }

        .gauge-progress-over {
          stroke: #475569;
        }

        .gauge-progress-unknown {
          stroke: #94a3b8;
        }

        .gauge-recommended {
          stroke: rgba(248, 250, 252, 0.6);
          stroke-width: 4;
        }

        .gauge-marker {
          fill: #f8fafc;
          stroke: rgba(15, 23, 42, 0.4);
          stroke-width: 3;
        }

        .gauge-labels {
          position: relative;
          min-height: 1.35rem;
          color: #94a3b8;
          font-size: 0.84rem;
        }

        .gauge-label {
          position: absolute;
          top: 0;
          transform: translateX(-50%);
          white-space: nowrap;
        }

        .gauge-label-start {
          transform: none;
        }

        .gauge-label-end {
          transform: translateX(-100%);
        }

        .empty-visual {
          color: #94a3b8;
          font-size: 0.92rem;
        }

        .macro-strip {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
        }

        .mini-macro {
          padding: 14px;
          border-radius: 18px;
          background: rgba(148, 163, 184, 0.08);
          border: 1px solid rgba(148, 163, 184, 0.12);
        }

        .mini-label {
          color: #94a3b8;
          font-size: 0.76rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          margin-bottom: 6px;
        }

        .mini-status {
          font-size: 1rem;
          font-weight: 800;
        }

        .empty-state {
          padding: 36px 18px;
          display: grid;
          gap: 10px;
          text-align: center;
          min-height: 260px;
          align-content: center;
        }

        .empty-title {
          font-size: 1.35rem;
          font-weight: 800;
        }

        .empty-detail {
          color: #cbd5e1;
          font-size: 0.96rem;
          line-height: 1.45;
          max-width: 24rem;
          margin: 0 auto;
        }

        @media (max-width: 480px) {
          .card {
            padding: 18px;
          }

          .hero-top {
            flex-direction: column;
          }

          .kcal-value {
            font-size: 2.15rem;
          }
        }
      </style>
      <ha-card>
        <div class="card">
          ${content}
        </div>
      </ha-card>
    `;
  }
}

if (!customElements.get("brizel-health-hero-card")) {
  customElements.define("brizel-health-hero-card", BrizelHealthHeroCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "brizel-health-hero-card")) {
  window.customCards.push({
    type: "brizel-health-hero-card",
    name: "Brizel Health Hero Card",
    description:
      "Hero card for today's kcal guidance with automatic HA-user profile resolution.",
  });
}
