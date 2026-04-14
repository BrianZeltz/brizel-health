import { BrizelCardUtils } from "./brizel-card-utils.js";

class BrizelFoodLoggerCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: "custom:brizel-food-logger-card",
    };
  }

  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._dialogOpen = false;
    this._step = "search";
    this._searchQuery = "";
    this._searchStatus = "idle";
    this._searchResults = [];
    this._searchError = "";
    this._recentFoods = [];
    this._recentStatus = "idle";
    this._recentRequestId = 0;
    this._searchDebounceHandle = null;
    this._searchRequestId = 0;
    this._selectedResult = null;
    this._detail = null;
    this._detailStatus = "idle";
    this._detailError = "";
    this._detailRequestId = 0;
    this._amountInput = "100";
    this._selectedUnit = "g";
    this._timeOverrideEnabled = false;
    this._consumedAtInput = "";
    this._saveStatus = "idle";
    this._saveError = "";
    this._successMessage = "";
    this._successTimeoutHandle = null;
    this._pendingFocusRole = null;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.addEventListener("pointerdown", (event) => {
      if (this._dialogOpen) {
        event.stopPropagation();
      }
    });
    this.shadowRoot.addEventListener("click", (event) => {
      if (this._dialogOpen) {
        event.stopPropagation();
      }
    });
    this.shadowRoot.addEventListener("input", (event) => this._handleInput(event));
    this.shadowRoot.addEventListener("change", (event) => this._handleChange(event));
  }

  setConfig(config) {
    this._config = {
      title: "Food Log",
      action_label: "Food hinzufuegen",
      source_name: null,
      profile: null,
      profile_id: null,
      search_placeholder: "Search food or brand",
      min_query_length: 3,
      debounce_ms: 320,
      limit: 8,
      recent_limit: 6,
      ...config,
    };
    this._config.min_query_length = Math.max(
      1,
      Number(this._config.min_query_length) || 2
    );
    this._config.debounce_ms = Math.max(150, Number(this._config.debounce_ms) || 320);
    this._config.limit = Math.max(1, Number(this._config.limit) || 8);
    this._config.recent_limit = Math.max(1, Number(this._config.recent_limit) || 6);
    this._resetDialogState({ closeDialog: true });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  disconnectedCallback() {
    this._clearSearchDebounce();
    this._clearSuccessTimeout();
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return {
      rows: 3,
      columns: 8,
      min_rows: 3,
      min_columns: 4,
    };
  }

  _clearSearchDebounce() {
    if (this._searchDebounceHandle !== null) {
      window.clearTimeout(this._searchDebounceHandle);
      this._searchDebounceHandle = null;
    }
  }

  _clearSuccessTimeout() {
    if (this._successTimeoutHandle !== null) {
      window.clearTimeout(this._successTimeoutHandle);
      this._successTimeoutHandle = null;
    }
  }

  _resetDialogState({ closeDialog = false } = {}) {
    this._clearSearchDebounce();
    this._dialogOpen = !closeDialog;
    this._step = "search";
    this._searchQuery = "";
    this._searchStatus = "idle";
    this._searchResults = [];
    this._searchError = "";
    this._recentFoods = [];
    this._recentStatus = "idle";
    this._selectedResult = null;
    this._detail = null;
    this._detailStatus = "idle";
    this._detailError = "";
    this._amountInput = "100";
    this._selectedUnit = "g";
    this._timeOverrideEnabled = false;
    this._consumedAtInput = "";
    this._saveStatus = "idle";
    this._saveError = "";
    this._pendingFocusRole = closeDialog ? null : "search-input";
  }

  _openDialog() {
    this._resetDialogState();
    this._render();
    void this._loadRecentFoods();
  }

  _closeDialog() {
    this._resetDialogState({ closeDialog: true });
    this._render();
  }

  _setSuccessMessage(message) {
    this._clearSuccessTimeout();
    this._successMessage = message;
    this._successTimeoutHandle = window.setTimeout(() => {
      this._successMessage = "";
      this._successTimeoutHandle = null;
      this._render();
    }, 4000);
  }

  _getSourceName() {
    return BrizelCardUtils.trimToNull(this._config?.source_name);
  }

  _getSourceLabel() {
    return this._getSourceName() ? BrizelCardUtils.titleize(this._getSourceName()) : "Enabled sources";
  }

  _getNowLocalDateTimeValue() {
    const now = new Date();
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  }

  _toIsoDateTime(localValue) {
    const normalized = BrizelCardUtils.trimToNull(localValue);
    if (!normalized) {
      return null;
    }
    const parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) {
      throw new Error("Please provide a valid date and time.");
    }
    return parsed.toISOString();
  }

  _normalizeHumanError(error, fallbackMessage) {
    const normalized = BrizelCardUtils.normalizeServiceError(error, {
      explicitProfile: BrizelCardUtils.getConfiguredProfile(this._config),
    });
    if (normalized.kind !== "generic") {
      return normalized.detail;
    }
    return BrizelCardUtils.trimToNull(error?.message || error) || fallbackMessage;
  }

  _handleAction(action, actionTarget = null) {
    if (action === "open-dialog") {
      window.requestAnimationFrame(() => this._openDialog());
      return;
    }
    if (action === "close-dialog") {
      this._closeDialog();
      return;
    }
    if (action === "back-to-search") {
      this._step = "search";
      this._detailStatus = "idle";
      this._detailError = "";
      this._saveStatus = "idle";
      this._saveError = "";
      this._pendingFocusRole = "search-input";
      this._render();
      return;
    }
    if (action === "toggle-time") {
      this._timeOverrideEnabled = !this._timeOverrideEnabled;
      if (this._timeOverrideEnabled && !BrizelCardUtils.trimToNull(this._consumedAtInput)) {
        this._consumedAtInput = this._getNowLocalDateTimeValue();
      }
      this._render();
      return;
    }
    if (action === "submit-log") {
      void this._saveFoodEntry();
      return;
    }
    if (action === "use-recent") {
      const recentName = BrizelCardUtils.trimToNull(actionTarget.dataset.name);
      if (!recentName) {
        return;
      }
      this._searchQuery = recentName;
      this._searchStatus = "idle";
      this._searchResults = [];
      this._searchError = "";
      this._pendingFocusRole = "search-input";
      this._render();
      void this._performSearch(recentName);
      return;
    }
    if (action === "select-result") {
      const index = Number(actionTarget.dataset.index);
      if (!Number.isInteger(index) || index < 0 || index >= this._searchResults.length) {
        return;
      }
      void this._loadDetailForResult(this._searchResults[index]);
    }
  }

  _handleClick(event) {
    const actionTarget = event
      .composedPath()
      .find((node) => node instanceof HTMLElement && node.dataset?.action);
    if (!actionTarget) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    this._handleAction(actionTarget.dataset.action, actionTarget);
  }

  _handleInput(event) {
    const inputTarget = event.target;
    if (!(inputTarget instanceof HTMLElement) || !inputTarget.dataset?.role) {
      return;
    }

    const role = inputTarget.dataset.role;
    if (role === "search-input") {
      this._searchQuery = inputTarget.value ?? "";
      if (this._searchStatus === "error") {
        this._searchError = "";
      }
      this._queueSearch();
      return;
    }
    if (role === "amount-input") {
      this._amountInput = inputTarget.value ?? "";
      if (this._saveStatus === "error") {
        this._saveStatus = "idle";
        this._saveError = "";
        this._render();
      }
      return;
    }
    if (role === "consumed-at-input") {
      this._consumedAtInput = inputTarget.value ?? "";
    }
  }

  _handleChange(event) {
    const inputTarget = event.target;
    if (!(inputTarget instanceof HTMLElement) || !inputTarget.dataset?.role) {
      return;
    }

    if (inputTarget.dataset.role === "unit-select") {
      this._selectedUnit = BrizelCardUtils.trimToNull(inputTarget.value) || "g";
    }
  }

  _queueSearch() {
    this._clearSearchDebounce();
    const normalizedQuery = BrizelCardUtils.trimToNull(this._searchQuery) || "";
    if (normalizedQuery.length < this._config.min_query_length) {
      const shouldRender =
        this._searchStatus !== "idle" ||
        this._searchResults.length > 0 ||
        Boolean(this._searchError);
      this._searchStatus = "idle";
      this._searchResults = [];
      this._searchError = "";
      if (shouldRender) {
        this._render();
      }
      return;
    }

    this._searchDebounceHandle = window.setTimeout(() => {
      this._searchDebounceHandle = null;
      void this._performSearch(normalizedQuery);
    }, this._config.debounce_ms);
  }

  async _performSearch(query) {
    if (!this._hass) {
      return;
    }

    const requestId = ++this._searchRequestId;
    this._searchStatus = "loading";
    this._searchError = "";
    this._render();

    try {
      const response = await BrizelCardUtils.searchExternalFoods(this._hass, {
        query,
        sourceName: this._getSourceName(),
        profileId: BrizelCardUtils.getConfiguredProfile(this._config),
        limit: this._config.limit,
      });

      if (requestId !== this._searchRequestId) {
        return;
      }

      if (response.results.length > 0) {
        this._searchResults = response.results;
        this._searchStatus = "ready";
      } else if (response.status === "empty") {
        this._searchResults = [];
        this._searchStatus = "empty";
      } else {
        this._searchResults = [];
        this._searchStatus = "error";
        this._searchError =
          BrizelCardUtils.trimToNull(response.error) ||
          "The food search is temporarily unavailable.";
      }
    } catch (error) {
      if (requestId !== this._searchRequestId) {
        return;
      }
      this._searchResults = [];
      this._searchStatus = "error";
      this._searchError =
        BrizelCardUtils.trimToNull(error?.message || error) ||
        "The food search is temporarily unavailable.";
    }

    this._render();
  }

  async _loadRecentFoods() {
    if (!this._hass) {
      return;
    }

    const requestId = ++this._recentRequestId;
    this._recentStatus = "loading";
    this._render();

    try {
      const response = await BrizelCardUtils.getRecentFoods(this._hass, {
        profileId: BrizelCardUtils.getConfiguredProfile(this._config),
        limit: this._config.recent_limit,
      });

      if (requestId !== this._recentRequestId) {
        return;
      }

      this._recentFoods = response.foods;
      this._recentStatus = response.foods.length ? "ready" : "empty";
    } catch (_error) {
      if (requestId !== this._recentRequestId) {
        return;
      }
      this._recentFoods = [];
      this._recentStatus = "unavailable";
    }

    this._render();
  }

  async _loadDetailForResult(result) {
    if (!this._hass) {
      return;
    }

    this._selectedResult = result;
    this._detail = null;
    this._detailStatus = "loading";
    this._detailError = "";
    this._saveStatus = "idle";
    this._saveError = "";
    this._step = "detail";
    this._render();

    const requestId = ++this._detailRequestId;

    try {
      const detail = await BrizelCardUtils.getExternalFoodDetail(this._hass, {
        sourceName: result.source_name,
        sourceId: result.source_id,
      });

      if (requestId !== this._detailRequestId) {
        return;
      }

      this._detail = detail;
      this._detailStatus = "ready";
      this._selectedUnit =
        BrizelCardUtils.trimToNull(detail.default_unit) ||
        BrizelCardUtils.trimToNull(detail.allowed_units?.[0]) ||
        "g";
      this._pendingFocusRole = "amount-input";
    } catch (error) {
      if (requestId !== this._detailRequestId) {
        return;
      }
      this._detailStatus = "error";
      this._detailError =
        BrizelCardUtils.trimToNull(error?.message || error) ||
        "The selected food could not be loaded right now.";
    }

    this._render();
  }

  async _saveFoodEntry() {
    if (!this._hass || !this._detail) {
      return;
    }

    const amount = Number(this._amountInput);
    if (!Number.isFinite(amount)) {
      this._saveStatus = "error";
      this._saveError = "Please enter a valid amount.";
      this._render();
      return;
    }
    if (amount <= 0) {
      this._saveStatus = "error";
      this._saveError = "Please enter an amount greater than zero.";
      this._render();
      return;
    }

    let consumedAt = null;
    if (this._timeOverrideEnabled) {
      try {
        consumedAt = this._toIsoDateTime(this._consumedAtInput);
      } catch (error) {
        this._saveStatus = "error";
        this._saveError = this._normalizeHumanError(error, "Please provide a valid date and time.");
        this._render();
        return;
      }
    }

    this._saveStatus = "saving";
    this._saveError = "";
    this._render();

    try {
      const response = await BrizelCardUtils.logExternalFoodEntry(this._hass, this._config, {
        sourceName: this._detail.source_name,
        sourceId: this._detail.source_id,
        amount,
        unit: this._selectedUnit,
        consumedAt,
      });

      const foodName =
        BrizelCardUtils.trimToNull(response?.food?.name) ||
        BrizelCardUtils.trimToNull(this._detail.name) ||
        "Food";
      BrizelCardUtils.emitProfileRefresh(response?.profile_id);
      this._setSuccessMessage(
        `${foodName} was added to today (${BrizelCardUtils.formatValue(
          amount,
          this._selectedUnit
        )}).`
      );
      this._closeDialog();
    } catch (error) {
      this._saveStatus = "error";
      this._saveError = this._normalizeHumanError(
        error,
        "The food entry could not be saved right now."
      );
      this._render();
    }
  }

  _renderSearchState() {
    const normalizedQuery = BrizelCardUtils.trimToNull(this._searchQuery) || "";
    if (!normalizedQuery) {
      if (this._recentStatus === "loading") {
        return `
          <div class="state-panel">
            <div class="spinner"></div>
            <div class="state-title">Loading recent foods...</div>
          </div>
        `;
      }

      if (this._recentFoods.length) {
        return `
          <div class="recent-block">
            <div class="recent-header">
              <div class="state-title">Recent foods</div>
              <div class="state-detail">Start with something you've logged before, or type to search.</div>
            </div>
            <div class="results-list" role="list">
              ${this._recentFoods
                .map(
                  (food) => `
                    <button class="result-item" type="button" data-action="use-recent" data-name="${BrizelCardUtils.escapeHtml(
                      food.name
                    )}">
                      <div class="result-main">
                        <div class="result-name">${BrizelCardUtils.escapeHtml(food.name)}</div>
                        <div class="result-meta">
                          ${
                            food.brand
                              ? `<span>${BrizelCardUtils.escapeHtml(food.brand)}</span>`
                              : ""
                          }
                          <span>Recent</span>
                        </div>
                      </div>
                      <div class="result-side">
                        <div class="result-kcal">${
                          food.kcal_per_100g === null || food.kcal_per_100g === undefined
                            ? "-"
                            : BrizelCardUtils.escapeHtml(
                                `${BrizelCardUtils.formatNumber(food.kcal_per_100g)} kcal`
                              )
                        }</div>
                        <div class="result-basis">per 100 g</div>
                      </div>
                    </button>
                  `
                )
                .join("")}
            </div>
          </div>
        `;
      }

      return `
        <div class="state-panel">
          <div class="state-title">Start typing to search for a food</div>
          <div class="state-detail">
            Search across enabled food sources and pick the food you want to log.
          </div>
        </div>
      `;
    }

    if (normalizedQuery.length < this._config.min_query_length) {
      return `
        <div class="state-panel">
          <div class="state-title">Keep typing to search</div>
          <div class="state-detail">
            Enter at least ${BrizelCardUtils.escapeHtml(this._config.min_query_length)} characters to search for a food.
          </div>
        </div>
      `;
    }

    if (this._searchStatus === "loading") {
      return `
        <div class="state-panel">
          <div class="spinner"></div>
          <div class="state-title">Searching...</div>
        </div>
      `;
    }

    if (this._searchStatus === "error") {
      return `
        <div class="state-panel state-panel-error">
          <div class="state-title">Couldn't search foods</div>
          <div class="state-detail">${BrizelCardUtils.escapeHtml(this._searchError)}</div>
        </div>
      `;
    }

    if (this._searchStatus === "empty") {
      return `
        <div class="state-panel">
          <div class="state-title">No matching foods found</div>
          <div class="state-detail">
            Try another spelling, a brand name, or a more general food term.
          </div>
        </div>
      `;
    }

    return "";
  }

  _renderSearchResults() {
    if (this._searchStatus !== "ready" || !this._searchResults.length) {
      return this._renderSearchState();
    }

    return `
      <div class="results-list" role="list">
        ${this._searchResults
          .map(
            (result, index) => `
              <button class="result-item" type="button" data-action="select-result" data-index="${index}">
                <div class="result-main">
                  <div class="result-name">${BrizelCardUtils.escapeHtml(result.name)}</div>
                  <div class="result-meta">
                    ${
                      result.brand
                        ? `<span>${BrizelCardUtils.escapeHtml(result.brand)}</span>`
                        : ""
                    }
                    <span>${BrizelCardUtils.escapeHtml(
                      BrizelCardUtils.titleize(result.source_name || this._getSourceLabel())
                    )}</span>
                  </div>
                </div>
                <div class="result-side">
                  <div class="result-kcal">${
                    result.kcal_per_100g === null || result.kcal_per_100g === undefined
                      ? "-"
                      : BrizelCardUtils.escapeHtml(
                          `${BrizelCardUtils.formatNumber(result.kcal_per_100g)} kcal`
                        )
                  }</div>
                  <div class="result-basis">per 100 g</div>
                </div>
              </button>
            `
          )
          .join("")}
      </div>
    `;
  }

  _renderDetailView() {
    if (this._detailStatus === "loading") {
      return `
        <div class="detail-state">
          <div class="spinner"></div>
          <div class="state-title">Loading food details...</div>
        </div>
      `;
    }

    if (this._detailStatus === "error" || !this._detail) {
      return `
        <div class="detail-state state-panel-error">
          <div class="state-title">Couldn't load this food</div>
          <div class="state-detail">${BrizelCardUtils.escapeHtml(
            this._detailError || "The selected food could not be loaded right now."
          )}</div>
        </div>
      `;
    }

    const allowedUnits = Array.isArray(this._detail.allowed_units)
      ? this._detail.allowed_units
      : ["g"];
    const selectedUnit = BrizelCardUtils.trimToNull(this._selectedUnit) || "g";

    return `
      <div class="detail-view">
        <div class="detail-header">
          <div>
            <div class="detail-name">${BrizelCardUtils.escapeHtml(this._detail.name)}</div>
            <div class="detail-meta">
              ${
                this._detail.brand
                  ? `<span>${BrizelCardUtils.escapeHtml(this._detail.brand)}</span>`
                  : ""
              }
              <span>${BrizelCardUtils.escapeHtml(
                BrizelCardUtils.titleize(this._detail.source_name)
              )}</span>
            </div>
          </div>
          <div class="basis-pill">${BrizelCardUtils.escapeHtml(
            `${BrizelCardUtils.formatNumber(this._detail.basis_amount)} ${this._detail.basis_unit}`
          )}</div>
        </div>

        <div class="macro-grid">
          <div class="macro-stat">
            <div class="macro-label">Kcal</div>
            <div class="macro-value">${BrizelCardUtils.escapeHtml(
              BrizelCardUtils.formatValue(this._detail.kcal_per_100g, "kcal")
            )}</div>
          </div>
          <div class="macro-stat">
            <div class="macro-label">Protein</div>
            <div class="macro-value">${BrizelCardUtils.escapeHtml(
              BrizelCardUtils.formatValue(this._detail.protein_per_100g, "g")
            )}</div>
          </div>
          <div class="macro-stat">
            <div class="macro-label">Carbs</div>
            <div class="macro-value">${BrizelCardUtils.escapeHtml(
              BrizelCardUtils.formatValue(this._detail.carbs_per_100g, "g")
            )}</div>
          </div>
          <div class="macro-stat">
            <div class="macro-label">Fat</div>
            <div class="macro-value">${BrizelCardUtils.escapeHtml(
              BrizelCardUtils.formatValue(this._detail.fat_per_100g, "g")
            )}</div>
          </div>
        </div>

        <div class="form-grid">
          <label class="field">
            <span class="field-label">Amount</span>
            <input
              class="field-input"
              data-role="amount-input"
              type="number"
              inputmode="decimal"
              min="0.1"
              step="0.1"
              value="${BrizelCardUtils.escapeHtml(this._amountInput)}"
            >
          </label>
          <label class="field">
            <span class="field-label">Unit</span>
            ${
              allowedUnits.length > 1
                ? `
                  <select class="field-input field-select" data-role="unit-select">
                    ${allowedUnits
                      .map(
                        (unit) => `
                          <option value="${BrizelCardUtils.escapeHtml(unit)}" ${
                            unit === selectedUnit ? "selected" : ""
                          }>${BrizelCardUtils.escapeHtml(unit)}</option>
                        `
                      )
                      .join("")}
                  </select>
                `
                : `
                  <div class="field-static">${BrizelCardUtils.escapeHtml(selectedUnit)}</div>
                `
            }
          </label>
        </div>

        <div class="time-row">
          <button type="button" class="inline-link" data-action="toggle-time">
            ${this._timeOverrideEnabled ? "Use current time instead" : "Change time"}
          </button>
          <span class="time-copy">Defaults to now if you keep this closed.</span>
        </div>

        ${
          this._timeOverrideEnabled
            ? `
              <label class="field">
                <span class="field-label">Consumed at</span>
                <input
                  class="field-input"
                  data-role="consumed-at-input"
                  type="datetime-local"
                  value="${BrizelCardUtils.escapeHtml(this._consumedAtInput)}"
                >
              </label>
            `
            : ""
        }

        ${
          this._saveStatus === "error"
            ? `
              <div class="feedback feedback-error">
                ${BrizelCardUtils.escapeHtml(this._saveError)}
              </div>
            `
            : ""
        }

        <div class="dialog-actions">
          <button type="button" class="secondary-button" data-action="back-to-search">Back</button>
          <button type="button" class="ghost-button" data-action="close-dialog">Cancel</button>
          <button
            type="button"
            class="primary-button"
            data-action="submit-log"
            ${this._saveStatus === "saving" ? "disabled" : ""}
          >
            ${this._saveStatus === "saving" ? "Saving..." : "Add to today"}
          </button>
        </div>
      </div>
    `;
  }

  _renderDialog() {
    if (!this._dialogOpen) {
      return "";
    }

    const dialogBody =
      this._step === "detail"
        ? this._renderDetailView()
        : `
            <div class="search-view">
              <label class="search-shell">
                <ha-icon icon="mdi:magnify"></ha-icon>
                <input
                  class="search-input"
                  data-role="search-input"
                  type="search"
                  placeholder="${BrizelCardUtils.escapeHtml(this._config.search_placeholder)}"
                  value="${BrizelCardUtils.escapeHtml(this._searchQuery)}"
                >
              </label>
              ${this._renderSearchResults()}
              <div class="dialog-actions">
                <button type="button" class="ghost-button" data-action="close-dialog">Close</button>
              </div>
            </div>
          `;

    const dialogTitle =
      this._step === "detail" ? "Confirm food entry" : "Search food";
    const dialogSubtitle =
      this._step === "detail"
        ? "Review the food and choose how much you consumed."
        : `Source: ${this._getSourceLabel()}`;

    return `
      <div class="dialog-backdrop" data-action="close-dialog"></div>
      <div class="dialog-layer" role="dialog" aria-modal="true" aria-label="${BrizelCardUtils.escapeHtml(
        dialogTitle
      )}">
        <div class="dialog-panel">
          <div class="dialog-header">
            <div>
              <div class="dialog-eyebrow">${BrizelCardUtils.escapeHtml(dialogSubtitle)}</div>
              <div class="dialog-title">${BrizelCardUtils.escapeHtml(dialogTitle)}</div>
            </div>
            <button class="icon-button" type="button" data-action="close-dialog" aria-label="Close dialog">
              <ha-icon icon="mdi:close"></ha-icon>
            </button>
          </div>
          ${dialogBody}
        </div>
      </div>
    `;
  }

  _applyPendingFocus() {
    if (!this._pendingFocusRole) {
      return;
    }

    const selector = `[data-role="${this._pendingFocusRole}"]`;
    const target = this.shadowRoot?.querySelector(selector);
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const role = this._pendingFocusRole;
    this._pendingFocusRole = null;
    window.setTimeout(() => {
      target.focus();
      if (role === "search-input" || role === "amount-input") {
        target.select?.();
      }
    }, 0);
  }

  _bindActionHandlers() {
    if (!this.shadowRoot) {
      return;
    }

    this.shadowRoot.querySelectorAll("[data-action]").forEach((element) => {
      if (!(element instanceof HTMLElement)) {
        return;
      }

      element.onclick = (event) => {
        event.preventDefault();
        event.stopPropagation();
        this._handleAction(element.dataset.action, element);
      };
    });
  }

  _captureFocusState() {
    if (!this.shadowRoot) {
      return null;
    }

    const activeElement = this.shadowRoot.activeElement;
    if (!(activeElement instanceof HTMLElement) || !activeElement.dataset?.role) {
      return null;
    }

    const state = {
      role: activeElement.dataset.role,
      value: typeof activeElement.value === "string" ? activeElement.value : null,
      selectionStart:
        typeof activeElement.selectionStart === "number"
          ? activeElement.selectionStart
          : null,
      selectionEnd:
        typeof activeElement.selectionEnd === "number" ? activeElement.selectionEnd : null,
    };
    return state;
  }

  _restoreFocusState(focusState) {
    if (!focusState || !this.shadowRoot || this._pendingFocusRole) {
      return;
    }

    const target = this.shadowRoot.querySelector(`[data-role="${focusState.role}"]`);
    if (!(target instanceof HTMLElement)) {
      return;
    }

    window.setTimeout(() => {
      target.focus({ preventScroll: true });
      if (
        typeof focusState.selectionStart === "number" &&
        typeof focusState.selectionEnd === "number" &&
        typeof target.setSelectionRange === "function"
      ) {
        target.setSelectionRange(focusState.selectionStart, focusState.selectionEnd);
      } else if (focusState.role === "search-input" && typeof target.select === "function") {
        target.select();
      }
    }, 0);
  }

  _render() {
    if (!this._config || !this.shadowRoot) {
      return;
    }

    const focusState = this._captureFocusState();
    const profileMode = BrizelCardUtils.getConfiguredProfile(this._config)
      ? "Manual profile override"
      : "Uses your linked Brizel profile";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { border-radius: 28px; overflow: hidden; background: radial-gradient(circle at top left, rgba(34, 197, 94, 0.12), transparent 28%), radial-gradient(circle at top right, rgba(56, 189, 248, 0.16), transparent 34%), linear-gradient(180deg, #08111f 0%, #0f172a 100%); color: #eff6ff; box-shadow: 0 20px 44px rgba(15, 23, 42, 0.22); }
        .card { padding: 22px; display: grid; gap: 18px; }
        .eyebrow { color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem; }
        .title-row { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
        .title { font-size: 1.45rem; font-weight: 800; line-height: 1.15; }
        .source-pill, .basis-pill { padding: 8px 12px; border-radius: 999px; background: rgba(148, 163, 184, 0.12); color: #dbeafe; font-size: 0.78rem; font-weight: 700; white-space: nowrap; }
        .copy { color: #dbeafe; font-size: 0.96rem; line-height: 1.5; }
        .helper-text { color: #94a3b8; font-size: 0.9rem; line-height: 1.45; }
        .actions, .dialog-actions { display: flex; gap: 10px; flex-wrap: wrap; }
        .actions { justify-content: flex-start; }
        .dialog-actions { justify-content: flex-end; }
        .success-banner, .feedback { padding: 12px 14px; border-radius: 16px; font-size: 0.92rem; line-height: 1.45; }
        .success-banner { color: #dcfce7; background: rgba(34, 197, 94, 0.14); border: 1px solid rgba(34, 197, 94, 0.24); }
        .feedback-error { color: #fee2e2; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.22); }
        .primary-button, .secondary-button, .ghost-button, .icon-button, .result-item, .inline-link { font: inherit; }
        .primary-button, .secondary-button, .ghost-button { border: none; border-radius: 999px; padding: 12px 18px; cursor: pointer; transition: transform 160ms ease, opacity 160ms ease; }
        .primary-button { background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%); color: #06121f; font-weight: 800; }
        .primary-button:disabled { cursor: default; opacity: 0.65; }
        .secondary-button { background: rgba(148, 163, 184, 0.14); color: #f8fafc; font-weight: 700; }
        .ghost-button { background: transparent; color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.18); font-weight: 700; }
        .dialog-backdrop { position: fixed; inset: 0; background: rgba(2, 6, 23, 0.72); z-index: 999; }
        .dialog-layer { position: fixed; inset: 0; display: grid; place-items: center; padding: 18px; z-index: 1000; }
        .dialog-panel { width: min(100%, 760px); max-height: min(88vh, 860px); overflow: auto; border-radius: 28px; background: radial-gradient(circle at top left, rgba(34, 197, 94, 0.1), transparent 28%), linear-gradient(180deg, #0b1220 0%, #111827 100%); color: #eff6ff; border: 1px solid rgba(148, 163, 184, 0.18); box-shadow: 0 26px 70px rgba(2, 6, 23, 0.45); }
        .dialog-header { padding: 22px 22px 0; display: flex; align-items: start; justify-content: space-between; gap: 12px; }
        .dialog-eyebrow { color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
        .dialog-title { font-size: 1.45rem; font-weight: 800; line-height: 1.15; }
        .icon-button { display: inline-grid; place-items: center; width: 40px; height: 40px; border-radius: 999px; border: 1px solid rgba(148, 163, 184, 0.16); background: rgba(148, 163, 184, 0.08); color: #eff6ff; cursor: pointer; }
        .search-view, .detail-view { padding: 20px 22px 22px; display: grid; gap: 16px; }
        .search-shell { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: 10px; padding: 12px 14px; border-radius: 18px; background: rgba(148, 163, 184, 0.08); border: 1px solid rgba(148, 163, 184, 0.14); }
        .search-input, .field-input, .field-select { width: 100%; border: none; outline: none; background: transparent; color: #f8fafc; font: inherit; }
        .search-input::placeholder { color: #94a3b8; }
        .state-panel, .detail-state { min-height: 220px; display: grid; place-content: center; gap: 10px; text-align: center; padding: 18px; border-radius: 22px; background: rgba(15, 23, 42, 0.42); border: 1px solid rgba(148, 163, 184, 0.12); }
        .state-panel-error { border-color: rgba(239, 68, 68, 0.18); }
        .state-title { font-size: 1.1rem; font-weight: 800; }
        .state-detail { color: #cbd5e1; font-size: 0.94rem; line-height: 1.45; max-width: 30rem; }
        .spinner { width: 28px; height: 28px; border-radius: 999px; border: 3px solid rgba(148, 163, 184, 0.2); border-top-color: #22c55e; margin: 0 auto; animation: spin 900ms linear infinite; }
        .recent-block { display: grid; gap: 12px; }
        .recent-header { display: grid; gap: 6px; }
        .results-list { display: grid; gap: 10px; max-height: min(48vh, 420px); overflow: auto; }
        .result-item { width: 100%; display: flex; align-items: start; justify-content: space-between; gap: 12px; text-align: left; padding: 14px 16px; border-radius: 18px; border: 1px solid rgba(148, 163, 184, 0.12); background: rgba(15, 23, 42, 0.55); color: #eff6ff; cursor: pointer; }
        .result-name { font-size: 1rem; font-weight: 700; line-height: 1.3; margin-bottom: 6px; }
        .result-meta { display: flex; flex-wrap: wrap; gap: 8px; color: #94a3b8; font-size: 0.82rem; }
        .result-side { text-align: right; min-width: 88px; }
        .result-kcal { font-size: 0.94rem; font-weight: 700; }
        .result-basis { color: #94a3b8; font-size: 0.78rem; margin-top: 6px; }
        .detail-header { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
        .detail-name { font-size: 1.3rem; font-weight: 800; line-height: 1.2; }
        .detail-meta { display: flex; flex-wrap: wrap; gap: 8px; color: #94a3b8; font-size: 0.84rem; margin-top: 8px; }
        .macro-grid, .form-grid { display: grid; gap: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .macro-stat { padding: 14px; border-radius: 18px; background: rgba(148, 163, 184, 0.08); border: 1px solid rgba(148, 163, 184, 0.12); }
        .macro-label { color: #94a3b8; font-size: 0.76rem; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; }
        .macro-value { font-size: 1rem; font-weight: 700; }
        .field { display: grid; gap: 8px; }
        .field-label { color: #cbd5e1; font-size: 0.84rem; font-weight: 700; }
        .field-input, .field-static { padding: 12px 14px; border-radius: 16px; background: rgba(15, 23, 42, 0.62); border: 1px solid rgba(148, 163, 184, 0.14); min-height: 48px; box-sizing: border-box; }
        .field-static { display: flex; align-items: center; color: #f8fafc; }
        .time-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; }
        .inline-link { padding: 0; border: none; background: transparent; color: #7dd3fc; cursor: pointer; font-weight: 700; }
        .time-copy { color: #94a3b8; font-size: 0.86rem; }
        .result-item:hover, .primary-button:hover, .secondary-button:hover, .ghost-button:hover, .icon-button:hover, .inline-link:hover { transform: translateY(-1px); }
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 720px) { .dialog-layer { padding: 0; } .dialog-panel { width: 100%; max-height: 100vh; min-height: 100vh; border-radius: 0; } }
        @media (max-width: 600px) { .card, .dialog-header, .search-view, .detail-view { padding-left: 16px; padding-right: 16px; } .title-row, .detail-header, .result-item { flex-direction: column; } .macro-grid, .form-grid { grid-template-columns: 1fr; } .result-side { min-width: 0; text-align: left; } .dialog-actions { justify-content: stretch; } .dialog-actions > * { flex: 1 1 auto; } }
      </style>
      <ha-card>
        <div class="card">
          <div class="eyebrow">${BrizelCardUtils.escapeHtml(profileMode)}</div>
          <div class="title-row">
            <div class="title">${BrizelCardUtils.escapeHtml(this._config.title)}</div>
            <div class="source-pill">${BrizelCardUtils.escapeHtml(this._getSourceLabel())}</div>
          </div>
          <div class="copy">Search a food, choose the amount you consumed, and save it to today.</div>
          <div class="helper-text">v1 uses the existing Brizel Health food flow and stores the entry for your linked profile.</div>
          ${
            this._successMessage
              ? `<div class="success-banner">${BrizelCardUtils.escapeHtml(
                  this._successMessage
                )}</div>`
              : ""
          }
          <div class="actions">
            <button class="primary-button" type="button" data-action="open-dialog">
              ${BrizelCardUtils.escapeHtml(this._config.action_label)}
            </button>
          </div>
        </div>
      </ha-card>
      ${this._renderDialog()}
    `;

    this._bindActionHandlers();
    this._restoreFocusState(focusState);
    this._applyPendingFocus();
  }
}

if (!customElements.get("brizel-food-logger-card")) {
  customElements.define("brizel-food-logger-card", BrizelFoodLoggerCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "brizel-food-logger-card")) {
  window.customCards.push({
    type: "brizel-food-logger-card",
    name: "Brizel Food Logger Card",
    description:
      "Search an external food source, confirm the amount, and save a food entry for today.",
  });
}
