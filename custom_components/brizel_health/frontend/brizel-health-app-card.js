import { BrizelCardUtils } from "./brizel-card-utils.js";
import "./brizel-health-hero-card.js";
import "./brizel-nutrition-card.js";
import "./brizel-macro-card.js";
import "./brizel-hydration-card.js";
import "./brizel-food-logger-card.js";

class BrizelHealthAppCard extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:brizel-health-app-card" };
  }

  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._section = "home";
    this._navStack = [];
    this._overview = null;
    this._resolvedProfileId = null;
    this._resolvedProfileName = null;
    this._profileLanguageChoice = "auto";
    this._profileError = null;
    this._homeState = "loading";
    this._homeError = "";
    this._homeLoading = false;
    this._requestKey = "";
    this._lastLoadAt = 0;
    this._profileForm = null;
    this._bodyForm = null;
    this._profileSection = "preferences";
    this._profileState = "idle";
    this._profileErrorMessage = "";
    this._profileSaveStatus = "idle";
    this._profileSaveMessage = "";
    this._bodySaveStatus = "idle";
    this._bodySaveMessage = "";
    this._profileData = null;
    this._bodyProfile = null;
    this._bodyTargets = null;
    this._bodyGoal = null;
    this._bodyProgressSummary = null;
    this._bodyMeasurementTypes = [];
    this._bodyMeasurementHistory = [];
    this._bodyQuickWeightForm = null;
    this._bodyMeasurementForm = null;
    this._bodyGoalForm = null;
    this._bodyWeightSaveStatus = "idle";
    this._bodyWeightSaveMessage = "";
    this._bodyMeasurementSaveStatus = "idle";
    this._bodyMeasurementSaveMessage = "";
    this._bodyGoalSaveStatus = "idle";
    this._bodyGoalSaveMessage = "";
    this._historyState = "idle";
    this._historyError = "";
    this._historyEntries = [];
    this._historyDate = new Date().toISOString().slice(0, 10);
    this._waterStatus = "idle";
    this._waterMessage = "";
    this._pendingLoggerAction = null;
    this._profileRefreshUnsubscribe = null;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.addEventListener("click", (event) => this._handleClick(event));
    this.shadowRoot.addEventListener("input", (event) => this._handleInput(event));
  }

  setConfig(config) {
    this._config = {
      title: null,
      profile: null,
      profile_id: null,
      target_entity: null,
      initial_section: "home",
      logger_source_name: null,
      ...config,
    };
    this._section = BrizelCardUtils.trimToNull(this._config.initial_section) || "home";
    this._profileSection = this._section === "body" ? "body" : "preferences";
    this._requestKey = "";
    this._overview = null;
    this._resolvedProfileId = null;
    this._resolvedProfileName = null;
    this._profileLanguageChoice = "auto";
    this._profileError = null;
    this._profileData = null;
    this._bodyProfile = null;
    this._bodyTargets = null;
    this._bodyGoal = null;
    this._bodyProgressSummary = null;
    this._bodyMeasurementTypes = [];
    this._bodyMeasurementHistory = [];
    this._profileForm = null;
    this._bodyForm = null;
    this._bodyQuickWeightForm = null;
    this._bodyMeasurementForm = null;
    this._bodyGoalForm = null;
    this._historyEntries = [];
    this._historyState = "idle";
    this._homeState = "loading";
    this._bodyWeightSaveStatus = "idle";
    this._bodyWeightSaveMessage = "";
    this._bodyMeasurementSaveStatus = "idle";
    this._bodyMeasurementSaveMessage = "";
    this._bodyGoalSaveStatus = "idle";
    this._bodyGoalSaveMessage = "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    void this._maybeLoadHome();
    void this._maybeLoadActiveSection();
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
          void this._maybeLoadHome(true);
          void this._maybeLoadActiveSection(true);
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
    return 12;
  }

  getGridOptions() {
    return {
      rows: 12,
      columns: 12,
      min_rows: 8,
      min_columns: 8,
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

  _getReadableErrorMessage(error, fallback = "") {
    return BrizelCardUtils.getReadableErrorMessage(error, fallback) || "";
  }

  _getConfiguredProfile() {
    return BrizelCardUtils.getConfiguredProfile(this._config);
  }

  _baseChildConfig(extra = {}) {
    return {
      profile: this._config.profile,
      profile_id: this._config.profile_id,
      ...extra,
    };
  }

  _setProfileLanguageChoice(profile) {
    this._profileLanguageChoice = profile?.preferred_language || "auto";
  }

  _getAppTitle() {
    const configuredTitle = BrizelCardUtils.trimToNull(this._config?.title);
    if (configuredTitle) {
      return configuredTitle;
    }
    if (this._section === "nutrition") {
      return this._t("app.sectionNutrition");
    }
    if (this._section === "hydration") {
      return this._t("app.sectionHydration");
    }
    if (this._section === "body") {
      return this._t("app.sectionBody");
    }
    if (this._section === "logger") {
      return this._t("app.sectionLogger");
    }
    if (this._section === "history") {
      return this._t("app.sectionHistory");
    }
    if (this._section === "settings") {
      return this._t("app.sectionSettings");
    }
    return this._t("app.homeTitle");
  }

  async _ensureResolvedProfile() {
    if (this._resolvedProfileId) {
      return {
        profileId: this._resolvedProfileId,
        profileDisplayName: this._resolvedProfileName,
      };
    }
    const result = await BrizelCardUtils.loadDailyOverview(this._hass, this._config);
    this._profileError = result.error;
    if (result.profileId) {
      this._resolvedProfileId = result.profileId;
      this._resolvedProfileName = result.profileDisplayName;
    }
    return {
      profileId: result.profileId,
      profileDisplayName: result.profileDisplayName,
      state: result.state,
      error: result.error,
    };
  }

  async _maybeLoadHome(force = false) {
    if (!this._config || !this._hass || this._homeLoading) {
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

    this._homeLoading = true;
    this._homeState = "loading";
    this._homeError = "";
    if (this._section === "home") {
      this._render();
    }

    try {
      const result = await BrizelCardUtils.loadDailyOverview(this._hass, this._config);
      this._overview = result.data;
      this._resolvedProfileId = result.profileId;
      this._resolvedProfileName = result.profileDisplayName;
      this._profileError = result.error;
      this._requestKey = requestKey;
      this._lastLoadAt = now;
      this._homeState = result.state === "profile_error" ? "profile_error" : "ready";
      if (result.state === "error") {
        this._homeState = "error";
        this._homeError =
          result.error?.detail || this._t("profileError.genericDetail");
      }
      if (!this._getConfiguredProfile() && result.profileId) {
        try {
          const profile = await BrizelCardUtils.getProfile(this._hass, {
            profileId: result.profileId,
          });
          this._setProfileLanguageChoice(profile);
        } catch (_error) {
          this._profileLanguageChoice = "auto";
        }
      }
    } finally {
      this._homeLoading = false;
      if (this._section === "home") {
        this._render();
      }
    }
  }

  async _maybeLoadActiveSection(force = false) {
    if (!this._hass) {
      return;
    }
    if (this._section === "history") {
      await this._loadHistory(force);
      return;
    }
    if (this._section === "settings" || this._section === "body") {
      await this._loadProfileBundle(force);
    }
  }

  _syncProfileForms(profile, bodyProfile) {
    this._profileForm = {
      display_name: profile?.display_name || "",
      linked_ha_user_id: profile?.linked_ha_user_id || "",
      preferred_language: profile?.preferred_language || "auto",
      preferred_region: profile?.preferred_region || "",
      preferred_units: profile?.preferred_units || "",
    };
    this._bodyForm = {
      age_years:
        Number.isFinite(Number(bodyProfile?.age_years)) && Number(bodyProfile?.age_years) > 0
          ? String(bodyProfile.age_years)
          : "",
      sex: bodyProfile?.sex || "",
      height_cm:
        Number.isFinite(Number(bodyProfile?.height_cm)) && Number(bodyProfile?.height_cm) > 0
          ? String(bodyProfile.height_cm)
          : "",
      weight_kg:
        Number.isFinite(Number(bodyProfile?.weight_kg)) && Number(bodyProfile?.weight_kg) > 0
          ? String(bodyProfile.weight_kg)
          : "",
      activity_level: bodyProfile?.activity_level || "",
    };
  }

  _defaultLocalDateTimeValue() {
    const now = new Date();
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  }

  _syncBodyProgressForms(measurementTypes, goal) {
    const weightDefinition =
      measurementTypes.find((definition) => definition.key === "weight") || null;
    const defaultMeasurementType =
      measurementTypes.find((definition) => definition.key !== "weight")?.key || "";
    const measuredAt = this._defaultLocalDateTimeValue();

    this._bodyQuickWeightForm = {
      value: "",
      unit: weightDefinition?.display_unit || "kg",
      measured_at: measuredAt,
    };
    this._bodyMeasurementForm = {
      measurement_type: defaultMeasurementType,
      value: "",
      measured_at: measuredAt,
      note: "",
    };
    this._bodyGoalForm = {
      target_weight:
        Number.isFinite(Number(goal?.display_value)) && Number(goal?.display_value) > 0
          ? String(goal.display_value)
          : "",
      unit: weightDefinition?.display_unit || "kg",
    };
  }

  async _loadProfileBundle(force = false) {
    if (!this._hass) {
      return;
    }
    if (
      !force &&
      this._profileData &&
      this._bodyProfile &&
      this._bodyTargets &&
      this._bodyProgressSummary &&
      this._bodyMeasurementTypes.length
    ) {
      return;
    }

    const resolved = await this._ensureResolvedProfile();
    if (!resolved.profileId) {
      this._profileState = "profile_error";
      this._render();
      return;
    }

    this._profileState = "loading";
    this._profileErrorMessage = "";
    this._render();

    try {
      const [
        profile,
        bodyProfile,
        targets,
        measurementTypes,
        goal,
        progressSummary,
        measurementHistory,
      ] = await Promise.all([
        BrizelCardUtils.getProfile(this._hass, { profileId: resolved.profileId }),
        BrizelCardUtils.getBodyProfile(this._hass, { profileId: resolved.profileId }),
        BrizelCardUtils.getBodyTargets(this._hass, { profileId: resolved.profileId }),
        BrizelCardUtils.getBodyMeasurementTypes(this._hass, {
          profileId: resolved.profileId,
        }),
        BrizelCardUtils.getBodyGoal(this._hass, { profileId: resolved.profileId }),
        BrizelCardUtils.getBodyProgressSummary(this._hass, {
          profileId: resolved.profileId,
        }),
        BrizelCardUtils.getBodyMeasurementHistory(this._hass, {
          profileId: resolved.profileId,
          limit: 20,
        }),
      ]);
      this._profileData = profile;
      this._bodyProfile = bodyProfile;
      this._bodyTargets = targets;
      this._bodyMeasurementTypes = measurementTypes;
      this._bodyGoal = goal;
      this._bodyProgressSummary = progressSummary;
      this._bodyMeasurementHistory = measurementHistory;
      this._setProfileLanguageChoice(profile);
      this._syncProfileForms(profile, bodyProfile);
      this._syncBodyProgressForms(measurementTypes, goal);
      this._profileState = "ready";
    } catch (error) {
      this._profileState = "error";
      this._profileErrorMessage =
        this._getReadableErrorMessage(error, this._t("profile.loadErrorTitle"));
    }
    this._render();
  }

  async _loadHistory(force = false) {
    if (!this._hass) {
      return;
    }
    if (!force && this._historyState === "ready" && this._historyEntries.length) {
      return;
    }

    const resolved = await this._ensureResolvedProfile();
    if (!resolved.profileId) {
      this._historyState = "profile_error";
      this._render();
      return;
    }

    this._historyState = "loading";
    this._historyError = "";
    this._render();

    try {
      const entries = await BrizelCardUtils.getFoodEntriesForProfileDate(this._hass, {
        profileId: resolved.profileId,
        date: this._historyDate,
      });
      this._historyEntries = entries.sort((left, right) =>
        String(right.consumed_at || "").localeCompare(String(left.consumed_at || ""))
      );
      this._historyState = "ready";
    } catch (error) {
      this._historyEntries = [];
      this._historyState = "error";
      this._historyError = this._getReadableErrorMessage(error, this._t("history.errorTitle"));
    }
    this._render();
  }

  _navigate(section, { push = true, profileSection = null } = {}) {
    const nextSection = BrizelCardUtils.trimToNull(section) || "home";
    if (push && nextSection !== this._section) {
      this._navStack.push(this._section);
    }
    this._section = nextSection;
    if (profileSection) {
      this._profileSection = profileSection;
    } else if (nextSection === "body") {
      this._profileSection = "body";
    } else if (nextSection === "settings") {
      this._profileSection = "preferences";
    }
    this._render();
    void this._maybeLoadActiveSection();
  }

  _queueLoggerAction(action) {
    this._pendingLoggerAction = action;
    this._navigate("logger");
  }

  async _handleAddWater() {
    if (!this._hass) {
      return;
    }
    const resolved = await this._ensureResolvedProfile();
    if (!resolved.profileId) {
      this._waterStatus = "error";
      this._waterMessage = this._profileError?.detail || this._t("app.addWaterError");
      this._render();
      return;
    }
    this._waterStatus = "saving";
    this._waterMessage = "";
    this._render();
    try {
      await BrizelCardUtils.addWater(this._hass, {
        profileId: resolved.profileId,
        amountMl: 250,
      });
      BrizelCardUtils.emitProfileRefresh(resolved.profileId);
      this._waterStatus = "success";
      this._waterMessage = this._t("app.addWaterSuccess", {
        amount: BrizelCardUtils.formatMl(250),
      });
    } catch (error) {
      this._waterStatus = "error";
      this._waterMessage = this._getReadableErrorMessage(error, this._t("app.addWaterError"));
    }
    this._render();
  }

  async _handleRemoveWater() {
    if (!this._hass) {
      return;
    }
    const resolved = await this._ensureResolvedProfile();
    if (!resolved.profileId) {
      this._waterStatus = "error";
      this._waterMessage = this._profileError?.detail || this._t("app.removeWaterError");
      this._render();
      return;
    }
    this._waterStatus = "saving";
    this._waterMessage = "";
    this._render();
    try {
      await BrizelCardUtils.removeWater(this._hass, {
        profileId: resolved.profileId,
        amountMl: 250,
      });
      BrizelCardUtils.emitProfileRefresh(resolved.profileId);
      this._waterStatus = "success";
      this._waterMessage = this._t("app.removeWaterSuccess", {
        amount: BrizelCardUtils.formatMl(250),
      });
    } catch (error) {
      this._waterStatus = "error";
      this._waterMessage = this._getReadableErrorMessage(
        error,
        this._t("app.removeWaterError")
      );
    }
    this._render();
  }

  async _saveProfile() {
    if (!this._hass || !this._resolvedProfileId || !this._profileForm) {
      return;
    }
    this._profileSaveStatus = "saving";
    this._profileSaveMessage = "";
    this._render();
    try {
      const profile = await BrizelCardUtils.updateProfile(this._hass, {
        profileId: this._resolvedProfileId,
        displayName: this._profileForm.display_name,
        preferredLanguage: this._profileForm.preferred_language,
        preferredRegion: this._profileForm.preferred_region,
        preferredUnits: this._profileForm.preferred_units,
      });
      this._profileData = profile;
      this._setProfileLanguageChoice(profile);
      this._profileSaveStatus = "success";
      this._profileSaveMessage = this._t("profile.savedProfile");
    } catch (error) {
      this._profileSaveStatus = "error";
      this._profileSaveMessage = this._getReadableErrorMessage(error);
    }
    this._render();
  }

  async _saveBody() {
    if (!this._hass || !this._resolvedProfileId || !this._bodyForm) {
      return;
    }
    this._bodySaveStatus = "saving";
    this._bodySaveMessage = "";
    this._render();
    try {
      const bodyProfile = await BrizelCardUtils.updateBodyProfile(this._hass, {
        profileId: this._resolvedProfileId,
        ageYears: this._bodyForm.age_years,
        sex: this._bodyForm.sex,
        heightCm: this._bodyForm.height_cm,
        weightKg: this._bodyForm.weight_kg,
        activityLevel: this._bodyForm.activity_level,
      });
      this._bodyProfile = bodyProfile;
      this._bodyTargets = await BrizelCardUtils.getBodyTargets(this._hass, {
        profileId: this._resolvedProfileId,
      });
      this._bodyProgressSummary = await BrizelCardUtils.getBodyProgressSummary(this._hass, {
        profileId: this._resolvedProfileId,
      });
      this._bodySaveStatus = "success";
      this._bodySaveMessage = this._t("profile.savedBody");
      BrizelCardUtils.emitProfileRefresh(this._resolvedProfileId);
    } catch (error) {
      this._bodySaveStatus = "error";
      this._bodySaveMessage = this._getReadableErrorMessage(error);
    }
    this._render();
  }

  async _saveQuickWeight() {
    if (!this._hass || !this._resolvedProfileId || !this._bodyQuickWeightForm) {
      return;
    }
    this._bodyWeightSaveStatus = "saving";
    this._bodyWeightSaveMessage = "";
    this._render();
    try {
      await BrizelCardUtils.addBodyMeasurement(this._hass, {
        profileId: this._resolvedProfileId,
        measurementType: "weight",
        value: this._bodyQuickWeightForm.value,
        unit: this._bodyQuickWeightForm.unit,
        measuredAt: this._bodyQuickWeightForm.measured_at,
        source: "manual",
      });
      await this._loadProfileBundle(true);
      this._bodyWeightSaveStatus = "success";
      this._bodyWeightSaveMessage = this._t("body.savedWeight");
      BrizelCardUtils.emitProfileRefresh(this._resolvedProfileId);
    } catch (error) {
      this._bodyWeightSaveStatus = "error";
      this._bodyWeightSaveMessage = this._getReadableErrorMessage(
        error,
        this._t("body.saveWeightError")
      );
    }
    this._render();
  }

  async _saveMeasurement() {
    if (!this._hass || !this._resolvedProfileId || !this._bodyMeasurementForm) {
      return;
    }
    this._bodyMeasurementSaveStatus = "saving";
    this._bodyMeasurementSaveMessage = "";
    this._render();
    try {
      const definition = (this._bodyMeasurementTypes || []).find(
        (measurementType) => measurementType.key === this._bodyMeasurementForm.measurement_type
      );
      await BrizelCardUtils.addBodyMeasurement(this._hass, {
        profileId: this._resolvedProfileId,
        measurementType: this._bodyMeasurementForm.measurement_type,
        value: this._bodyMeasurementForm.value,
        unit: definition?.display_unit || null,
        measuredAt: this._bodyMeasurementForm.measured_at,
        note: this._bodyMeasurementForm.note,
        source: "manual",
      });
      await this._loadProfileBundle(true);
      this._bodyMeasurementSaveStatus = "success";
      this._bodyMeasurementSaveMessage = this._t("body.savedMeasurement");
      BrizelCardUtils.emitProfileRefresh(this._resolvedProfileId);
    } catch (error) {
      this._bodyMeasurementSaveStatus = "error";
      this._bodyMeasurementSaveMessage = this._getReadableErrorMessage(
        error,
        this._t("body.saveMeasurementError")
      );
    }
    this._render();
  }

  async _saveBodyGoal() {
    if (!this._hass || !this._resolvedProfileId || !this._bodyGoalForm) {
      return;
    }
    this._bodyGoalSaveStatus = "saving";
    this._bodyGoalSaveMessage = "";
    this._render();
    try {
      this._bodyGoal = await BrizelCardUtils.setBodyGoal(this._hass, {
        profileId: this._resolvedProfileId,
        targetWeight: this._bodyGoalForm.target_weight,
        unit: this._bodyGoalForm.unit,
      });
      await this._loadProfileBundle(true);
      this._bodyGoalSaveStatus = "success";
      this._bodyGoalSaveMessage = this._t("body.savedGoal");
      BrizelCardUtils.emitProfileRefresh(this._resolvedProfileId);
    } catch (error) {
      this._bodyGoalSaveStatus = "error";
      this._bodyGoalSaveMessage = this._getReadableErrorMessage(
        error,
        this._t("body.saveGoalError")
      );
    }
    this._render();
  }

  async _deleteBodyMeasurement(measurementId) {
    if (!this._hass || !measurementId) {
      return;
    }
    try {
      await BrizelCardUtils.deleteBodyMeasurement(this._hass, { measurementId });
      await this._loadProfileBundle(true);
      this._bodyMeasurementSaveStatus = "success";
      this._bodyMeasurementSaveMessage = this._t("body.deleted");
      if (this._resolvedProfileId) {
        BrizelCardUtils.emitProfileRefresh(this._resolvedProfileId);
      }
    } catch (error) {
      this._bodyMeasurementSaveStatus = "error";
      this._bodyMeasurementSaveMessage =
        this._getReadableErrorMessage(error, this._t("body.deleteUnavailable"));
    }
    this._render();
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
    const action = actionTarget.dataset.action;
    if (action === "navigate") {
      this._navigate(actionTarget.dataset.section, {
        profileSection: BrizelCardUtils.trimToNull(actionTarget.dataset.profileSection),
      });
      return;
    }
    if (action === "go-home") {
      this._navigate("home", { push: false });
      return;
    }
    if (action === "go-back") {
      const previous = this._navStack.pop() || "home";
      this._navigate(previous, { push: false });
      return;
    }
    if (action === "quick-add-food") {
      this._queueLoggerAction({ type: "open", mode: "search" });
      return;
    }
    if (action === "quick-barcode") {
      this._queueLoggerAction({ type: "open", mode: "barcode" });
      return;
    }
    if (action === "quick-history") {
      this._navigate("history");
      return;
    }
    if (action === "quick-settings") {
      this._navigate("settings", { profileSection: "preferences" });
      return;
    }
    if (action === "quick-water") {
      void this._handleAddWater();
      return;
    }
    if (action === "quick-remove-water") {
      void this._handleRemoveWater();
      return;
    }
    if (action === "profile-section") {
      this._profileSection = actionTarget.dataset.profileSection || "preferences";
      this._render();
      return;
    }
    if (action === "save-profile") {
      void this._saveProfile();
      return;
    }
    if (action === "save-body") {
      void this._saveBody();
      return;
    }
    if (action === "save-quick-weight") {
      void this._saveQuickWeight();
      return;
    }
    if (action === "save-body-measurement") {
      void this._saveMeasurement();
      return;
    }
    if (action === "save-body-goal") {
      void this._saveBodyGoal();
      return;
    }
    if (action === "refresh-history") {
      void this._loadHistory(true);
      return;
    }
    if (action === "reuse-entry") {
      this._queueLoggerAction({
        type: "reuse",
        foodId: actionTarget.dataset.foodId,
        grams: actionTarget.dataset.grams,
        mealType: actionTarget.dataset.mealType,
      });
      return;
    }
    if (action === "delete-entry") {
      const entryId = BrizelCardUtils.trimToNull(actionTarget.dataset.entryId);
      if (!entryId || !window.confirm(this._t("history.deleteConfirm"))) {
        return;
      }
      void this._deleteEntry(entryId);
      return;
    }
    if (action === "delete-body-measurement") {
      const measurementId = BrizelCardUtils.trimToNull(actionTarget.dataset.measurementId);
      if (!measurementId || !window.confirm(this._t("body.deleteConfirm"))) {
        return;
      }
      void this._deleteBodyMeasurement(measurementId);
    }
  }

  _handleInput(event) {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.dataset?.role) {
      return;
    }
    if (target.dataset.role.startsWith("profile-") && this._profileForm) {
      const field = target.dataset.role.replace("profile-", "");
      this._profileForm = {
        ...this._profileForm,
        [field]: target.value ?? "",
      };
      return;
    }
    if (target.dataset.role.startsWith("body-") && this._bodyForm) {
      const field = target.dataset.role.replace("body-", "");
      this._bodyForm = {
        ...this._bodyForm,
        [field]: target.value ?? "",
      };
      return;
    }
    if (target.dataset.role.startsWith("body-weight-") && this._bodyQuickWeightForm) {
      const field = target.dataset.role.replace("body-weight-", "");
      this._bodyQuickWeightForm = {
        ...this._bodyQuickWeightForm,
        [field]: target.value ?? "",
      };
      return;
    }
    if (
      target.dataset.role.startsWith("body-measurement-") &&
      this._bodyMeasurementForm
    ) {
      const field = target.dataset.role.replace("body-measurement-", "");
      this._bodyMeasurementForm = {
        ...this._bodyMeasurementForm,
        [field]: target.value ?? "",
      };
      return;
    }
    if (target.dataset.role.startsWith("body-goal-") && this._bodyGoalForm) {
      const field = target.dataset.role.replace("body-goal-", "");
      this._bodyGoalForm = {
        ...this._bodyGoalForm,
        [field]: target.value ?? "",
      };
      return;
    }
    if (target.dataset.role === "history-date") {
      this._historyDate = target.value || this._historyDate;
      void this._loadHistory(true);
    }
  }

  async _deleteEntry(foodEntryId) {
    if (!this._hass) {
      return;
    }
    try {
      await BrizelCardUtils.deleteFoodEntry(this._hass, { foodEntryId });
      if (this._resolvedProfileId) {
        BrizelCardUtils.emitProfileRefresh(this._resolvedProfileId);
      }
      this._waterStatus = "success";
      this._waterMessage = this._t("history.deleted");
      await this._loadHistory(true);
    } catch (error) {
      this._waterStatus = "error";
      this._waterMessage = this._getReadableErrorMessage(
        error,
        this._t("history.deleteUnavailable")
      );
      this._render();
    }
  }

  _formatFieldList(fields = []) {
    return fields
      .map((field) => {
        const key = `profile.field${field
          .split("_")
          .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
          .join("")}`;
        const translated = this._t(key);
        return translated === key ? BrizelCardUtils.titleize(field) : translated;
      })
      .join(", ");
  }

  _groupEntriesByMealType() {
    const ordered = ["breakfast", "lunch", "dinner", "snack", ""];
    return ordered
      .map((mealType) => ({
        mealType,
        label: mealType
          ? BrizelCardUtils.getMealTypeLabel(mealType, this._getLanguageContext())
          : this._t("history.mealSectionNone"),
        entries: this._historyEntries.filter((entry) => (entry.meal_type || "") === mealType),
      }))
      .filter((group) => group.entries.length > 0);
  }

  _renderHomeSection() {
    return `
      <section class="app-panel">
        <div class="section-header">
          <div>
            <div class="section-eyebrow">${BrizelCardUtils.escapeHtml(this._t("app.quickActions"))}</div>
            <div class="section-title">${BrizelCardUtils.escapeHtml(this._t("app.homeTitle"))}</div>
            <div class="section-copy">${BrizelCardUtils.escapeHtml(this._t("app.homeSubtitle"))}</div>
          </div>
        </div>
        <div class="quick-grid">
          <button class="quick-card" data-action="quick-add-food"><span>${BrizelCardUtils.escapeHtml(this._t("app.actionAddFood"))}</span></button>
          <button class="quick-card" data-action="quick-barcode"><span>${BrizelCardUtils.escapeHtml(this._t("app.actionBarcode"))}</span></button>
          <button class="quick-card" data-action="quick-water"><span>${BrizelCardUtils.escapeHtml(this._t("app.actionAddWater"))}</span></button>
          <button class="quick-card" data-action="quick-remove-water"><span>${BrizelCardUtils.escapeHtml(this._t("app.actionRemoveWater"))}</span></button>
          <button class="quick-card" data-action="quick-history"><span>${BrizelCardUtils.escapeHtml(this._t("app.actionHistory"))}</span></button>
          <button class="quick-card" data-action="quick-settings"><span>${BrizelCardUtils.escapeHtml(this._t("app.actionSettings"))}</span></button>
        </div>
        <div class="tile-grid">
          ${[
            ["nutrition", "tileNutritionTitle", "tileNutritionDetail"],
            ["hydration", "tileHydrationTitle", "tileHydrationDetail"],
            ["body", "tileBodyTitle", "tileBodyDetail"],
            ["logger", "tileLoggerTitle", "tileLoggerDetail"],
            ["history", "tileHistoryTitle", "tileHistoryDetail"],
            ["settings", "tileSettingsTitle", "tileSettingsDetail"],
          ]
            .map(
              ([section, titleKey, detailKey]) => `
                <button class="tile-card" data-action="navigate" data-section="${section}">
                  <div class="tile-title">${BrizelCardUtils.escapeHtml(this._t(`app.${titleKey}`))}</div>
                  <div class="tile-detail">${BrizelCardUtils.escapeHtml(this._t(`app.${detailKey}`))}</div>
                </button>
              `
            )
            .join("")}
        </div>
        <div class="embedded-card" data-embed="hero"></div>
      </section>
    `;
  }

  _renderHistorySection() {
    if (this._historyState === "loading") {
      return `<section class="app-panel"><div class="state-card">${BrizelCardUtils.escapeHtml(this._t("history.loading"))}</div></section>`;
    }
    if (this._historyState === "profile_error") {
      return `<section class="app-panel"><div class="state-card">${BrizelCardUtils.escapeHtml(this._profileError?.detail || this._t("profileError.noLinkDetail"))}</div></section>`;
    }
    if (this._historyState === "error") {
      return `<section class="app-panel"><div class="state-card">${BrizelCardUtils.escapeHtml(this._historyError || this._t("history.errorTitle"))}</div></section>`;
    }

    const groups = this._groupEntriesByMealType();
    return `
      <section class="app-panel">
        <div class="section-header">
          <div>
            <div class="section-eyebrow">${BrizelCardUtils.escapeHtml(this._t("common.history"))}</div>
            <div class="section-title">${BrizelCardUtils.escapeHtml(this._t("history.titleDefault"))}</div>
            <div class="section-copy">${BrizelCardUtils.escapeHtml(this._t("history.subtitle"))}</div>
          </div>
          <div class="toolbar">
            <label class="field inline-field">
              <span>${BrizelCardUtils.escapeHtml(this._t("history.dateLabel"))}</span>
              <input class="field-input" data-role="history-date" type="date" value="${BrizelCardUtils.escapeHtml(this._historyDate)}">
            </label>
            <button class="secondary-button" data-action="refresh-history">${BrizelCardUtils.escapeHtml(this._t("common.refresh"))}</button>
          </div>
        </div>
        ${
          groups.length
            ? groups
                .map(
                  (group) => `
                    <section class="entry-group">
                      <div class="entry-group-title">${BrizelCardUtils.escapeHtml(group.label)}</div>
                      <div class="entry-list">
                        ${group.entries
                          .map(
                            (entry) => `
                              <article class="entry-card">
                                <div>
                                  <div class="entry-name">${BrizelCardUtils.escapeHtml(entry.food_name)}</div>
                                  <div class="entry-meta">
                                    ${entry.food_brand ? `<span>${BrizelCardUtils.escapeHtml(entry.food_brand)}</span>` : ""}
                                    <span>${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(entry.grams, "g"))}</span>
                                    <span>${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(entry.kcal, "kcal"))}</span>
                                    <span>${BrizelCardUtils.escapeHtml(
                                      entry.consumed_at
                                        ? BrizelCardUtils.formatTime(entry.consumed_at, this._getLanguageContext())
                                        : this._t("history.timeUnknown")
                                    )}</span>
                                    <span>${BrizelCardUtils.escapeHtml(
                                      BrizelCardUtils.getEntrySourceLabel(entry.source, this._getLanguageContext())
                                    )}</span>
                                  </div>
                                </div>
                                <div class="entry-actions">
                                  <button class="secondary-button" data-action="reuse-entry" data-food-id="${BrizelCardUtils.escapeHtml(entry.food_id)}" data-grams="${BrizelCardUtils.escapeHtml(entry.grams)}" data-meal-type="${BrizelCardUtils.escapeHtml(entry.meal_type || "")}">${BrizelCardUtils.escapeHtml(this._t("history.reuseAction"))}</button>
                                  <button class="ghost-button" data-action="delete-entry" data-entry-id="${BrizelCardUtils.escapeHtml(entry.food_entry_id)}">${BrizelCardUtils.escapeHtml(this._t("history.deleteAction"))}</button>
                                </div>
                              </article>
                            `
                          )
                          .join("")}
                      </div>
                    </section>
                  `
                )
                .join("")
            : `<div class="state-card">${BrizelCardUtils.escapeHtml(this._t("history.emptyTitle"))}<div class="state-detail">${BrizelCardUtils.escapeHtml(this._t("history.emptyDetail"))}</div></div>`
        }
      </section>
    `;
  }

  _renderProfileSection() {
    if (this._profileState === "loading") {
      return `<section class="app-panel"><div class="state-card">${BrizelCardUtils.escapeHtml(this._t("common.loading"))}</div></section>`;
    }
    if (this._profileState === "profile_error") {
      return `<section class="app-panel"><div class="state-card">${BrizelCardUtils.escapeHtml(this._profileError?.detail || this._t("profileError.noLinkDetail"))}</div></section>`;
    }
    if (this._profileState === "error") {
      return `<section class="app-panel"><div class="state-card">${BrizelCardUtils.escapeHtml(this._profileErrorMessage || this._t("profile.loadErrorTitle"))}</div></section>`;
    }

    const profileForm = this._profileForm || {};
    const bodyForm = this._bodyForm || {};
    const languageOptions = BrizelCardUtils.getPreferredLanguageOptions(this._getLanguageContext());
    const regionOptions = BrizelCardUtils.getPreferredRegionOptions(this._getLanguageContext());
    const unitsOptions = BrizelCardUtils.getPreferredUnitsOptions(this._getLanguageContext());
    const sexOptions = BrizelCardUtils.getSexOptions(this._getLanguageContext());
    const activityOptions = BrizelCardUtils.getActivityLevelOptions(this._getLanguageContext());
    const targets = this._bodyTargets || {};
    const missingFields = Array.isArray(targets.missing_fields) ? targets.missing_fields : [];
    const unsupportedReasons = Array.isArray(targets.unsupported_reasons)
      ? targets.unsupported_reasons
      : [];

    return `
      <section class="app-panel">
        <div class="section-header">
          <div>
            <div class="section-eyebrow">${BrizelCardUtils.escapeHtml(this._t("app.sectionSettings"))}</div>
            <div class="section-title">${BrizelCardUtils.escapeHtml(this._t("profile.titleDefault"))}</div>
            <div class="section-copy">${BrizelCardUtils.escapeHtml(this._t("profile.subtitle"))}</div>
          </div>
        </div>
        <div class="subnav">
          ${[
            ["profile", "profile.sectionProfile"],
            ["preferences", "profile.sectionPreferences"],
            ["body", "profile.sectionBody"],
            ["targets", "profile.sectionTargets"],
          ]
            .map(
              ([section, key]) => `
                <button class="subnav-button ${this._profileSection === section ? "subnav-button-active" : ""}" data-action="profile-section" data-profile-section="${section}">
                  ${BrizelCardUtils.escapeHtml(this._t(key))}
                </button>
              `
            )
            .join("")}
        </div>
        <div class="settings-body">
          ${this._profileSection === "targets"
            ? this._renderTargetsView(targets, missingFields, unsupportedReasons)
            : this._profileSection === "body"
            ? this._renderBodyView(bodyForm, activityOptions, sexOptions)
            : this._renderProfileForm(profileForm, languageOptions, regionOptions, unitsOptions)}
        </div>
      </section>
    `;
  }

  _renderSelectOptions(options, selectedValue) {
    return options
      .map(
        (option) => `
          <option value="${BrizelCardUtils.escapeHtml(option.value)}" ${
            option.value === selectedValue ? "selected" : ""
          }>${BrizelCardUtils.escapeHtml(option.label)}</option>
        `
      )
      .join("");
  }

  _renderProfileForm(profileForm, languageOptions, regionOptions, unitsOptions) {
    return `
      <div class="form-grid">
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldDisplayName"))}</span><input class="field-input" data-role="profile-display_name" type="text" value="${BrizelCardUtils.escapeHtml(profileForm.display_name || "")}"></label>
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldLinkedHaUser"))}</span><div class="field-static">${BrizelCardUtils.escapeHtml(profileForm.linked_ha_user_id || this._t("common.notConfigured"))}</div></label>
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldProfileId"))}</span><div class="field-static">${BrizelCardUtils.escapeHtml(this._resolvedProfileId || "-")}</div></label>
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldLanguage"))}</span><select class="field-input" data-role="profile-preferred_language">${this._renderSelectOptions(languageOptions, profileForm.preferred_language || "auto")}</select></label>
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldRegion"))}</span><select class="field-input" data-role="profile-preferred_region">${this._renderSelectOptions(regionOptions, profileForm.preferred_region || "")}</select></label>
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldUnits"))}</span><select class="field-input" data-role="profile-preferred_units">${this._renderSelectOptions(unitsOptions, profileForm.preferred_units || "")}</select></label>
      </div>
      ${this._profileSaveMessage ? `<div class="feedback ${this._profileSaveStatus === "error" ? "feedback-error" : "feedback-success"}">${BrizelCardUtils.escapeHtml(this._profileSaveMessage)}</div>` : ""}
      <div class="actions"><button class="primary-button" data-action="save-profile">${BrizelCardUtils.escapeHtml(this._profileSaveStatus === "saving" ? this._t("profile.savingProfile") : this._t("profile.saveProfile"))}</button></div>
    `;
  }

  _renderBodyView(bodyForm, activityOptions, sexOptions) {
    return `
      <div class="form-grid">
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldAge"))}</span><input class="field-input" data-role="body-age_years" type="number" min="1" max="120" value="${BrizelCardUtils.escapeHtml(bodyForm.age_years || "")}"></label>
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldSex"))}</span><select class="field-input" data-role="body-sex">${this._renderSelectOptions(sexOptions, bodyForm.sex || "")}</select></label>
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldHeight"))}</span><input class="field-input" data-role="body-height_cm" type="number" min="50" max="250" step="0.1" value="${BrizelCardUtils.escapeHtml(bodyForm.height_cm || "")}"></label>
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldWeight"))}</span><input class="field-input" data-role="body-weight_kg" type="number" min="10" max="300" step="0.1" value="${BrizelCardUtils.escapeHtml(bodyForm.weight_kg || "")}"></label>
        <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("profile.fieldActivity"))}</span><select class="field-input" data-role="body-activity_level">${this._renderSelectOptions(activityOptions, bodyForm.activity_level || "")}</select></label>
      </div>
      <div class="hint-box">${BrizelCardUtils.escapeHtml(this._t("profile.bodyEmpty"))}</div>
      ${this._bodySaveMessage ? `<div class="feedback ${this._bodySaveStatus === "error" ? "feedback-error" : "feedback-success"}">${BrizelCardUtils.escapeHtml(this._bodySaveMessage)}</div>` : ""}
      <div class="actions"><button class="primary-button" data-action="save-body">${BrizelCardUtils.escapeHtml(this._bodySaveStatus === "saving" ? this._t("profile.savingBody") : this._t("profile.saveBody"))}</button></div>
    `;
  }

  _renderTargetsView(targets, missingFields, unsupportedReasons) {
    return `
      <div class="target-grid">
        <article class="target-card"><div class="target-label">${BrizelCardUtils.escapeHtml(this._t("profile.targetCalories"))}</div><div class="target-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(targets.target_daily_kcal, "kcal"))}</div></article>
        <article class="target-card"><div class="target-label">${BrizelCardUtils.escapeHtml(this._t("profile.targetProtein"))}</div><div class="target-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(targets.target_daily_protein, "g"))}</div></article>
        <article class="target-card"><div class="target-label">${BrizelCardUtils.escapeHtml(this._t("profile.targetFat"))}</div><div class="target-value">${BrizelCardUtils.escapeHtml(BrizelCardUtils.formatValue(targets.target_daily_fat, "g"))}</div></article>
      </div>
      <div class="hint-box">${BrizelCardUtils.escapeHtml(this._t("profile.targetsDerived"))}</div>
      ${missingFields.length ? `<div class="feedback feedback-neutral">${BrizelCardUtils.escapeHtml(this._t("profile.targetsMissingFields", { fields: this._formatFieldList(missingFields) }))}</div>` : ""}
      ${unsupportedReasons.length ? `<div class="feedback feedback-neutral">${BrizelCardUtils.escapeHtml(this._t("profile.targetsUnsupported", { reasons: unsupportedReasons.join(", ") }))}</div>` : ""}
      <div class="hint-box">${BrizelCardUtils.escapeHtml(this._t("profile.hydrationTargetNote"))}</div>
    `;
  }

  _getBodyMeasurementDefinition(measurementType) {
    return (this._bodyMeasurementTypes || []).find(
      (definition) => definition.key === measurementType
    );
  }

  _formatBodyMeasurementValue(value, unit, { signed = false } = {}) {
    if (!Number.isFinite(Number(value))) {
      return "–";
    }
    const numericValue = Number(value);
    const prefix = signed && numericValue > 0 ? "+" : "";
    return `${prefix}${BrizelCardUtils.formatNumber(numericValue)} ${unit}`.trim();
  }

  _renderBodySummaryCards(progressSummary, goal, weightUnit) {
    const lastMeasured = progressSummary?.latest_measured_at
      ? `${BrizelCardUtils.formatDate(
          progressSummary.latest_measured_at,
          this._getLanguageContext()
        )} · ${BrizelCardUtils.formatTime(
          progressSummary.latest_measured_at,
          this._getLanguageContext()
        )}`
      : "–";
    const goalText = Number.isFinite(Number(goal?.display_value))
      ? this._formatBodyMeasurementValue(goal.display_value, weightUnit)
      : this._t("body.goalUnset");

    return `
      <div class="target-grid">
        <article class="target-card"><div class="target-label">${BrizelCardUtils.escapeHtml(this._t("body.currentWeight"))}</div><div class="target-value">${BrizelCardUtils.escapeHtml(
          Number.isFinite(Number(progressSummary?.latest_value))
            ? this._formatBodyMeasurementValue(progressSummary.latest_value, weightUnit)
            : this._t("body.latestValueUnavailable")
        )}</div></article>
        <article class="target-card"><div class="target-label">${BrizelCardUtils.escapeHtml(this._t("body.targetWeight"))}</div><div class="target-value">${BrizelCardUtils.escapeHtml(goalText)}</div></article>
        <article class="target-card"><div class="target-label">${BrizelCardUtils.escapeHtml(this._t("body.distanceToGoal"))}</div><div class="target-value">${BrizelCardUtils.escapeHtml(
          Number.isFinite(Number(progressSummary?.distance_to_goal_value))
            ? this._formatBodyMeasurementValue(progressSummary.distance_to_goal_value, weightUnit, {
                signed: true,
              })
            : "–"
        )}</div></article>
        <article class="target-card"><div class="target-label">${BrizelCardUtils.escapeHtml(this._t("body.changeSincePrevious"))}</div><div class="target-value">${BrizelCardUtils.escapeHtml(
          Number.isFinite(Number(progressSummary?.change_since_previous_value))
            ? this._formatBodyMeasurementValue(progressSummary.change_since_previous_value, weightUnit, {
                signed: true,
              })
            : "–"
        )}</div></article>
        <article class="target-card"><div class="target-label">${BrizelCardUtils.escapeHtml(this._t("body.changeSinceStart"))}</div><div class="target-value">${BrizelCardUtils.escapeHtml(
          Number.isFinite(Number(progressSummary?.change_since_start_value))
            ? this._formatBodyMeasurementValue(progressSummary.change_since_start_value, weightUnit, {
                signed: true,
              })
            : "–"
        )}</div></article>
        <article class="target-card"><div class="target-label">${BrizelCardUtils.escapeHtml(this._t("body.trend7d"))}</div><div class="target-value">${BrizelCardUtils.escapeHtml(
          Number.isFinite(Number(progressSummary?.trend_7d_value))
            ? this._formatBodyMeasurementValue(progressSummary.trend_7d_value, weightUnit, {
                signed: true,
              })
            : "–"
        )}</div><div class="tile-detail">${BrizelCardUtils.escapeHtml(
          `${this._t("body.lastMeasured")}: ${lastMeasured}`
        )}</div></article>
      </div>
    `;
  }

  _renderBodyMeasurementHistory() {
    if (!this._bodyMeasurementHistory.length) {
      return `<div class="state-card">${BrizelCardUtils.escapeHtml(this._t("body.noMeasurementsTitle"))}<div class="state-detail">${BrizelCardUtils.escapeHtml(this._t("body.noMeasurementsDetail"))}</div></div>`;
    }

    return `
      <div class="entry-list">
        ${this._bodyMeasurementHistory
          .map((measurement) => {
            const measuredAt = measurement.measured_at
              ? `${BrizelCardUtils.formatDate(
                  measurement.measured_at,
                  this._getLanguageContext()
                )} · ${BrizelCardUtils.formatTime(
                  measurement.measured_at,
                  this._getLanguageContext()
                )}`
              : "–";
            return `
              <article class="entry-card">
                <div>
                  <div class="entry-name">${BrizelCardUtils.escapeHtml(
                    BrizelCardUtils.getBodyMeasurementTypeLabel(
                      measurement.measurement_type,
                      this._getLanguageContext()
                    )
                  )}</div>
                  <div class="entry-meta">
                    <span>${BrizelCardUtils.escapeHtml(
                      this._formatBodyMeasurementValue(
                        measurement.display_value,
                        measurement.display_unit
                      )
                    )}</span>
                    <span>${BrizelCardUtils.escapeHtml(measuredAt)}</span>
                    <span>${BrizelCardUtils.escapeHtml(
                      BrizelCardUtils.getBodyMeasurementSourceLabel(
                        measurement.source,
                        this._getLanguageContext()
                      )
                    )}</span>
                    ${measurement.note ? `<span>${BrizelCardUtils.escapeHtml(measurement.note)}</span>` : ""}
                  </div>
                </div>
                <div class="entry-actions">
                  <button class="ghost-button" data-action="delete-body-measurement" data-measurement-id="${BrizelCardUtils.escapeHtml(
                    measurement.measurement_id
                  )}">${BrizelCardUtils.escapeHtml(this._t("common.delete"))}</button>
                </div>
              </article>
            `;
          })
          .join("")}
      </div>
    `;
  }

  _renderBodySection() {
    if (this._profileState === "loading") {
      return `<section class="app-panel"><div class="state-card">${BrizelCardUtils.escapeHtml(this._t("common.loading"))}</div></section>`;
    }
    if (this._profileState === "profile_error") {
      return `<section class="app-panel"><div class="state-card">${BrizelCardUtils.escapeHtml(this._profileError?.detail || this._t("profileError.noLinkDetail"))}</div></section>`;
    }
    if (this._profileState === "error") {
      return `<section class="app-panel"><div class="state-card">${BrizelCardUtils.escapeHtml(this._profileErrorMessage || this._t("body.loadErrorTitle"))}</div></section>`;
    }

    const weightDefinition = this._getBodyMeasurementDefinition("weight");
    const weightUnit = weightDefinition?.display_unit || "kg";
    const measurementForm = this._bodyMeasurementForm || {};
    const quickWeightForm = this._bodyQuickWeightForm || { value: "", measured_at: "", unit: weightUnit };
    const goalForm = this._bodyGoalForm || { target_weight: "", unit: weightUnit };
    const measurementTypeOptions = BrizelCardUtils.getBodyMeasurementTypeOptions(
      this._bodyMeasurementTypes || [],
      this._getLanguageContext(),
      { includeWeight: false }
    );
    const selectedMeasurementType =
      measurementForm.measurement_type || measurementTypeOptions[0]?.value || "";
    const selectedMeasurementDefinition =
      this._getBodyMeasurementDefinition(selectedMeasurementType) ||
      measurementTypeOptions[0] ||
      null;
    const selectedUnit =
      selectedMeasurementDefinition?.display_unit ||
      measurementTypeOptions[0]?.display_unit ||
      "cm";

    return `
      <section class="app-panel">
        <div class="section-header">
          <div>
            <div class="section-eyebrow">${BrizelCardUtils.escapeHtml(this._t("app.sectionBody"))}</div>
            <div class="section-title">${BrizelCardUtils.escapeHtml(this._t("body.titleDefault"))}</div>
            <div class="section-copy">${BrizelCardUtils.escapeHtml(this._t("body.subtitle"))}</div>
          </div>
        </div>
        <div class="settings-body">
          <section class="target-card">
            <div class="section-eyebrow">${BrizelCardUtils.escapeHtml(this._t("body.overviewTitle"))}</div>
            <div class="section-copy">${BrizelCardUtils.escapeHtml(this._t("body.overviewDetail"))}</div>
            ${this._renderBodySummaryCards(this._bodyProgressSummary, this._bodyGoal, weightUnit)}
          </section>
          <div class="form-grid">
            <section class="app-panel">
              <div class="section-eyebrow">${BrizelCardUtils.escapeHtml(this._t("body.quickWeightTitle"))}</div>
              <div class="section-copy">${BrizelCardUtils.escapeHtml(this._t("body.quickWeightDetail"))}</div>
              <div class="form-grid">
                <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("body.fieldWeightValue"))}</span><input class="field-input" data-role="body-weight-value" type="number" step="0.1" value="${BrizelCardUtils.escapeHtml(quickWeightForm.value || "")}"></label>
                <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("common.unit"))}</span><div class="field-static">${BrizelCardUtils.escapeHtml(weightUnit)}</div></label>
                <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("body.fieldMeasuredAt"))}</span><input class="field-input" data-role="body-weight-measured_at" type="datetime-local" value="${BrizelCardUtils.escapeHtml(quickWeightForm.measured_at || "")}"></label>
              </div>
              ${this._bodyWeightSaveMessage ? `<div class="feedback ${this._bodyWeightSaveStatus === "error" ? "feedback-error" : "feedback-success"}">${BrizelCardUtils.escapeHtml(this._bodyWeightSaveMessage)}</div>` : ""}
              <div class="actions"><button class="primary-button" data-action="save-quick-weight">${BrizelCardUtils.escapeHtml(this._bodyWeightSaveStatus === "saving" ? this._t("body.savingWeight") : this._t("body.saveWeight"))}</button></div>
            </section>
            <section class="app-panel">
              <div class="section-eyebrow">${BrizelCardUtils.escapeHtml(this._t("body.goalTitle"))}</div>
              <div class="section-copy">${BrizelCardUtils.escapeHtml(this._t("body.goalDetail"))}</div>
              <div class="form-grid">
                <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("body.fieldTargetWeight"))}</span><input class="field-input" data-role="body-goal-target_weight" type="number" step="0.1" value="${BrizelCardUtils.escapeHtml(goalForm.target_weight || "")}"></label>
                <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("common.unit"))}</span><div class="field-static">${BrizelCardUtils.escapeHtml(weightUnit)}</div></label>
              </div>
              ${this._bodyGoalSaveMessage ? `<div class="feedback ${this._bodyGoalSaveStatus === "error" ? "feedback-error" : "feedback-success"}">${BrizelCardUtils.escapeHtml(this._bodyGoalSaveMessage)}</div>` : ""}
              <div class="actions"><button class="primary-button" data-action="save-body-goal">${BrizelCardUtils.escapeHtml(this._bodyGoalSaveStatus === "saving" ? this._t("body.savingGoal") : this._t("body.saveGoal"))}</button></div>
            </section>
          </div>
          <section class="app-panel">
            <div class="section-eyebrow">${BrizelCardUtils.escapeHtml(this._t("body.measurementFormTitle"))}</div>
            <div class="section-copy">${BrizelCardUtils.escapeHtml(this._t("body.measurementFormDetail"))}</div>
            <div class="form-grid">
              <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("body.fieldMeasurementType"))}</span><select class="field-input" data-role="body-measurement-measurement_type">${this._renderSelectOptions(
                measurementTypeOptions,
                selectedMeasurementType
              )}</select></label>
              <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("body.fieldMeasurementValue"))}</span><input class="field-input" data-role="body-measurement-value" type="number" step="0.1" value="${BrizelCardUtils.escapeHtml(measurementForm.value || "")}"></label>
              <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("common.unit"))}</span><div class="field-static">${BrizelCardUtils.escapeHtml(selectedUnit)}</div></label>
              <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("body.fieldMeasuredAt"))}</span><input class="field-input" data-role="body-measurement-measured_at" type="datetime-local" value="${BrizelCardUtils.escapeHtml(measurementForm.measured_at || "")}"></label>
              <label class="field"><span>${BrizelCardUtils.escapeHtml(this._t("body.fieldMeasurementNote"))}</span><input class="field-input" data-role="body-measurement-note" type="text" value="${BrizelCardUtils.escapeHtml(measurementForm.note || "")}"></label>
            </div>
            ${this._bodyMeasurementSaveMessage ? `<div class="feedback ${this._bodyMeasurementSaveStatus === "error" ? "feedback-error" : "feedback-success"}">${BrizelCardUtils.escapeHtml(this._bodyMeasurementSaveMessage)}</div>` : ""}
            <div class="actions"><button class="primary-button" data-action="save-body-measurement">${BrizelCardUtils.escapeHtml(this._bodyMeasurementSaveStatus === "saving" ? this._t("body.savingMeasurement") : this._t("body.saveMeasurement"))}</button></div>
          </section>
          <section class="app-panel">
            <div class="section-eyebrow">${BrizelCardUtils.escapeHtml(this._t("body.historyTitle"))}</div>
            <div class="section-copy">${BrizelCardUtils.escapeHtml(this._t("body.historyDetail"))}</div>
            ${this._renderBodyMeasurementHistory()}
          </section>
        </div>
      </section>
    `;
  }

  _renderSectionBody() {
    if (this._section === "home") return this._renderHomeSection();
    if (this._section === "nutrition") {
      return `<section class="embedded-grid"><div class="embedded-card" data-embed="hero"></div><div class="embedded-card" data-embed="nutrition"></div><div class="macro-grid"><div class="embedded-card" data-embed="macro-kcal"></div><div class="embedded-card" data-embed="macro-protein"></div><div class="embedded-card" data-embed="macro-fat"></div></div></section>`;
    }
    if (this._section === "hydration") {
      return `<section class="embedded-grid"><div class="quick-inline"><button class="primary-button" data-action="quick-water">${BrizelCardUtils.escapeHtml(this._t("app.actionAddWater"))}</button><button class="secondary-button" data-action="quick-remove-water">${BrizelCardUtils.escapeHtml(this._t("app.actionRemoveWater"))}</button></div><div class="embedded-card" data-embed="hydration"></div></section>`;
    }
    if (this._section === "logger") {
      return `<section class="embedded-grid"><div class="embedded-card" data-embed="logger"></div></section>`;
    }
    if (this._section === "history") return this._renderHistorySection();
    if (this._section === "body") return this._renderBodySection();
    if (this._section === "settings") return this._renderProfileSection();
    return this._renderHomeSection();
  }

  _syncEmbeddedCards() {
    if (!this.shadowRoot || !this._hass) return;
    const mounts = [
      ["hero", "brizel-health-hero-card", this._baseChildConfig({ title: this._t("hero.titleDefault") })],
      ["nutrition", "brizel-nutrition-card", this._baseChildConfig({ title: this._t("nutritionCard.titleDefault") })],
      ["hydration", "brizel-hydration-card", this._baseChildConfig({ title: this._t("hydrationCard.titleDefault"), target_entity: this._config.target_entity })],
      ["logger", "brizel-food-logger-card", this._baseChildConfig({ source_name: this._config.logger_source_name })],
      ["macro-kcal", "brizel-macro-card", this._baseChildConfig({ macro: "kcal" })],
      ["macro-protein", "brizel-macro-card", this._baseChildConfig({ macro: "protein" })],
      ["macro-fat", "brizel-macro-card", this._baseChildConfig({ macro: "fat" })],
    ];
    mounts.forEach(([embed, tagName, config]) => {
      const host = this.shadowRoot.querySelector(`[data-embed='${embed}']`);
      if (!host) return;
      let card = host.firstElementChild;
      if (!card || card.tagName.toLowerCase() !== tagName) {
        host.innerHTML = `<${tagName}></${tagName}>`;
        card = host.firstElementChild;
      }
      if (!card) return;

      const configKey = JSON.stringify(config);
      if (card.setConfig && card.__brizelConfigKey !== configKey) {
        card.setConfig(config);
        card.__brizelConfigKey = configKey;
      }
      card.hass = this._hass;
      if (embed === "logger" && this._pendingLoggerAction && typeof card?.openLoggerDialog === "function") {
        const action = this._pendingLoggerAction;
        this._pendingLoggerAction = null;
        window.requestAnimationFrame(() => {
          if (action.type === "open") {
            card.openLoggerDialog({ mode: action.mode });
          } else if (action.type === "reuse" && typeof card.openReuseFoodEntry === "function") {
            void card.openReuseFoodEntry(action);
          }
        });
      }
    });
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const profileLabel = this._resolvedProfileName || this._resolvedProfileId || this._t("common.linkedProfile");
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; } ha-card { border-radius: 30px; overflow:hidden; background: radial-gradient(circle at top left, rgba(34, 197, 94, 0.14), transparent 26%), radial-gradient(circle at top right, rgba(56, 189, 248, 0.14), transparent 32%), linear-gradient(180deg, #08111f 0%, #111827 100%); color:#f8fafc; box-shadow: 0 24px 50px rgba(15, 23, 42, 0.24); } .card { padding:22px; display:grid; gap:18px; } .topbar { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; } .brand-label { color:#94a3b8; text-transform:uppercase; letter-spacing:0.08em; font-size:0.78rem; margin-bottom:6px; } .brand-title { font-size:1.5rem; font-weight:800; line-height:1.1; } .profile-pill { padding:8px 12px; border-radius:999px; background:rgba(148,163,184,0.12); color:#dbeafe; font-size:0.82rem; font-weight:700; } .nav-row { display:flex; flex-wrap:wrap; gap:10px; } .nav-button, .subnav-button, .quick-card, .tile-card, .primary-button, .secondary-button, .ghost-button { font:inherit; border:none; cursor:pointer; } .nav-button, .subnav-button { padding:10px 14px; border-radius:999px; background:rgba(148,163,184,0.1); color:#e2e8f0; font-weight:700; } .nav-button-active, .subnav-button-active { background:rgba(34,197,94,0.16); color:#dcfce7; } .quick-grid, .tile-grid, .target-grid { display:grid; gap:12px; } .quick-grid { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); } .tile-grid { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); } .quick-card, .tile-card, .app-panel, .target-card { padding:16px; border-radius:22px; background:rgba(15,23,42,0.58); border:1px solid rgba(148,163,184,0.14); color:#f8fafc; text-align:left; } .quick-card span { font-weight:800; } .tile-title, .section-title { font-size:1.15rem; font-weight:800; margin-bottom:6px; } .tile-detail, .section-copy, .entry-meta, .hint-box, .state-detail { color:#cbd5e1; font-size:0.92rem; line-height:1.45; } .embedded-grid, .macro-grid, .entry-list, .settings-body { display:grid; gap:14px; } .macro-grid { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); } .section-header { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:16px; } .section-eyebrow, .entry-group-title, .target-label { color:#94a3b8; text-transform:uppercase; letter-spacing:0.08em; font-size:0.78rem; margin-bottom:6px; } .toolbar, .entry-actions, .actions, .quick-inline, .subnav { display:flex; gap:10px; flex-wrap:wrap; } .field { display:grid; gap:6px; color:#cbd5e1; } .field-input, .field-static { border-radius:16px; border:1px solid rgba(148,163,184,0.16); background:rgba(15,23,42,0.65); color:#f8fafc; padding:12px 14px; font:inherit; } .field-static { min-height: 48px; align-content:center; } .form-grid { display:grid; gap:14px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); } .feedback { padding:12px 14px; border-radius:16px; font-size:0.92rem; line-height:1.45; } .feedback-success { color:#dcfce7; background:rgba(34,197,94,0.14); border:1px solid rgba(34,197,94,0.24); } .feedback-error { color:#fee2e2; background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.22); } .feedback-neutral { color:#dbeafe; background:rgba(59,130,246,0.12); border:1px solid rgba(59,130,246,0.22); } .primary-button, .secondary-button, .ghost-button { border-radius:999px; padding:12px 18px; } .primary-button { background:linear-gradient(90deg, #22c55e 0%, #16a34a 100%); color:#06121f; font-weight:800; } .secondary-button { background:rgba(148,163,184,0.14); color:#f8fafc; font-weight:700; } .ghost-button { background:transparent; color:#cbd5e1; border:1px solid rgba(148,163,184,0.18); } .entry-card { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; padding:14px; border-radius:18px; background:rgba(2,6,23,0.34); border:1px solid rgba(148,163,184,0.12); } .entry-name, .target-value { font-size:1rem; font-weight:800; margin-bottom:6px; } .state-card { padding:24px 16px; border-radius:22px; background:rgba(15,23,42,0.58); border:1px solid rgba(148,163,184,0.14); text-align:center; } @media (max-width: 720px) { .card { padding:16px; } .topbar, .section-header, .entry-card { flex-direction:column; } }
      </style>
      <ha-card>
        <div class="card">
          <div class="topbar">
            <div>
              <div class="brand-label">${BrizelCardUtils.escapeHtml(this._t("app.title"))}</div>
              <div class="brand-title">${BrizelCardUtils.escapeHtml(this._getAppTitle())}</div>
            </div>
            <div class="profile-pill">${BrizelCardUtils.escapeHtml(profileLabel)}</div>
          </div>
          <div class="nav-row">
            <button class="nav-button ${this._section === "home" ? "nav-button-active" : ""}" data-action="go-home">${BrizelCardUtils.escapeHtml(this._t("common.home"))}</button>
            ${this._section !== "home" ? `<button class="nav-button" data-action="go-back">${BrizelCardUtils.escapeHtml(this._t("common.back"))}</button>` : ""}
            ${[
              ["nutrition", "app.sectionNutrition"],
              ["hydration", "app.sectionHydration"],
              ["body", "app.sectionBody"],
              ["logger", "app.sectionLogger"],
              ["history", "app.sectionHistory"],
              ["settings", "app.sectionSettings"],
            ]
              .map(
                ([section, key]) => `
                  <button class="nav-button ${this._section === section ? "nav-button-active" : ""}" data-action="navigate" data-section="${section}">
                    ${BrizelCardUtils.escapeHtml(this._t(key))}
                  </button>
                `
              )
              .join("")}
          </div>
          ${this._waterMessage ? `<div class="feedback ${this._waterStatus === "error" ? "feedback-error" : "feedback-success"}">${BrizelCardUtils.escapeHtml(this._waterMessage)}</div>` : ""}
          ${this._renderSectionBody()}
        </div>
      </ha-card>
    `;
    this._syncEmbeddedCards();
  }
}

if (!customElements.get("brizel-health-app-card")) {
  customElements.define("brizel-health-app-card", BrizelHealthAppCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "brizel-health-app-card")) {
  window.customCards.push({
    type: "brizel-health-app-card",
    name: "Brizel Health App Card",
    description:
      "App-style Brizel Health shell with Home, Nutrition, Hydration, Logger, History, and Settings sections.",
  });
}

export { BrizelHealthAppCard };
