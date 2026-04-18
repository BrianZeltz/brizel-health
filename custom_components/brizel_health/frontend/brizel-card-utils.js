const PROFILE_REFRESH_EVENT = "brizel-health:profile-refresh";
const UI_LANGUAGE_AUTO = "auto";
const UI_LANGUAGE_DE = "de";
const UI_LANGUAGE_EN = "en";

const trimToNull = (value) => {
  const normalized = String(value ?? "").trim();
  return normalized ? normalized : null;
};

const UI_STRINGS = {
  en: {
    status: {
      under: "Under",
      within: "Within",
      over: "Over",
      unknown: "Unknown",
      unavailable: "Unavailable",
    },
    macro: {
      kcal: "Kcal",
      protein: "Protein",
      fat: "Fat",
    },
    mealType: {
      none: "No meal type",
      breakfast: "Breakfast",
      lunch: "Lunch",
      dinner: "Dinner",
      snack: "Snack",
    },
    common: {
      targetRangeUnavailable: "Target range is not available yet.",
      sensorUnavailable: "This sensor is not available yet.",
      enabledSources: "Enabled sources",
      recentFood: "Recent food",
      foodFallback: "Food",
    },
    profileError: {
      noUserTitle: "Home Assistant user unavailable",
      noUserDetail:
        "The currently signed-in Home Assistant user could not be determined.",
      noLinkTitle: "No Brizel profile linked",
      noLinkDetail:
        "For your Home Assistant user, no Brizel Health profile is linked yet.",
      invalidProfileTitle: "Invalid Brizel profile reference",
      invalidProfileConfiguredDetail:
        "The configured Brizel Health profile is invalid or no longer exists.",
      invalidProfileLinkedDetail:
        "The profile link is invalid or the Brizel Health profile no longer exists.",
      genericTitle: "Couldn't load Brizel Health data",
      genericDetail: "Please check the Brizel Health integration.",
    },
    logger: {
      cardTitle: "Food Log",
      actionLabel: "Add food",
      searchPlaceholder: "Search food or brand",
      profileModeManual: "Manual profile override",
      profileModeLinked: "Uses your linked Brizel profile",
      cardCopy:
        "Search a food or enter a barcode, choose the amount you consumed, and save it to today.",
      helperCopy:
        "Recents, barcode lookup, and the existing Brizel Health save flow all stay tied to your linked profile.",
      sourcePrefix: "Source: {source}",
      barcodeSourcePrefix: "Barcode lookup via {source}",
      detailTitle: "Confirm food entry",
      detailSubtitle: "Review the food and choose how much you consumed.",
      searchTitle: "Search food",
      barcodeTitle: "Lookup barcode",
      closeDialog: "Close dialog",
      close: "Close",
      cancel: "Cancel",
      back: "Back",
      save: "Add to today",
      saving: "Saving...",
      searchMode: "Search",
      barcodeMode: "Barcode",
      foodLookupMode: "Food lookup mode",
      searchUnavailable: "The food search is temporarily unavailable.",
      detailUnavailable: "The selected food could not be loaded right now.",
      barcodeUnavailable: "This barcode could not be looked up right now.",
      saveUnavailable: "The food entry could not be saved right now.",
      invalidAmount: "Please enter a valid amount.",
      amountGreaterThanZero: "Please enter an amount greater than zero.",
      invalidDateTime: "Please provide a valid date and time.",
      barcodeRequired: "Please enter a barcode.",
      successAdded: "{foodName} was added to today ({amount}).",
      recentFoods: "Recent foods",
      recentHeader:
        "Start with something you've logged before, or type to search.",
      recentBadge: "Recent",
      recentUsed: "Used {count}x",
      recentLastAmount: "Last: {amount} g",
      detailLoading: "Loading food details...",
      detailErrorTitle: "Couldn't load this food",
      carbsLabel: "Carbs",
      fieldAmount: "Amount",
      fieldUnit: "Unit",
      fieldMeal: "Meal",
      fieldConsumedAt: "Consumed at",
      changeTime: "Change time",
      useCurrentTime: "Use current time instead",
      timeDefaultsToNow: "Defaults to now if you keep this closed.",
      barcodeEnterTitle: "Enter a barcode",
      barcodeEnterDetail:
        "Type a barcode to look up a packaged food and continue with the normal logging flow.",
      barcodeEnterHint:
        "Use 8 to 14 digits. Brizel Health will look across barcode-capable sources.",
      barcodeLoading: "Looking up barcode...",
      barcodeErrorTitle: "Couldn't look up this barcode",
      barcodeEmptyTitle: "No product found for this barcode",
      barcodeEmptyDetail:
        "Check the digits and try again, or switch back to the text search.",
      recentLoading: "Loading recent foods...",
      searchIdleTitle: "Start typing to search for a food",
      searchIdleDetail:
        "Search across enabled food sources and pick the food you want to log.",
      searchMinLengthTitle: "Keep typing to search",
      searchMinLengthDetail:
        "Enter at least {count} characters to search for a food.",
      searchLoading: "Searching...",
      searchErrorTitle: "Couldn't search foods",
      searchEmptyTitle: "No matching foods found",
      searchEmptyDetail:
        "Try another spelling, a brand name, or a more general food term.",
      basisPer100g: "per 100 g",
    },
  },
  de: {
    status: {
      under: "Unter",
      within: "Im Zielbereich",
      over: "Darüber",
      unknown: "Unbekannt",
      unavailable: "Nicht verfügbar",
    },
    macro: {
      kcal: "Kalorien",
      protein: "Protein",
      fat: "Fett",
    },
    mealType: {
      none: "Keine Mahlzeit",
      breakfast: "Frühstück",
      lunch: "Mittagessen",
      dinner: "Abendessen",
      snack: "Snack",
    },
    common: {
      targetRangeUnavailable: "Der Zielbereich ist noch nicht verfügbar.",
      sensorUnavailable: "Dieser Sensor ist noch nicht verfügbar.",
      enabledSources: "Aktive Quellen",
      recentFood: "Zuletzt verwendet",
      foodFallback: "Lebensmittel",
    },
    profileError: {
      noUserTitle: "Home-Assistant-Nutzer nicht verfügbar",
      noUserDetail:
        "Der aktuell angemeldete Home-Assistant-Nutzer konnte nicht bestimmt werden.",
      noLinkTitle: "Kein Brizel-Profil verknüpft",
      noLinkDetail:
        "Für deinen Home-Assistant-Nutzer ist noch kein Brizel-Health-Profil verknüpft.",
      invalidProfileTitle: "Ungültige Brizel-Profilreferenz",
      invalidProfileConfiguredDetail:
        "Das konfigurierte Brizel-Health-Profil ist ungültig oder existiert nicht mehr.",
      invalidProfileLinkedDetail:
        "Die Profilverknüpfung ist ungültig oder das Brizel-Health-Profil existiert nicht mehr.",
      genericTitle: "Brizel-Health-Daten konnten nicht geladen werden",
      genericDetail: "Bitte prüfe die Brizel-Health-Integration.",
    },
    logger: {
      cardTitle: "Lebensmittel-Logger",
      actionLabel: "Lebensmittel hinzufügen",
      searchPlaceholder: "Lebensmittel oder Marke suchen",
      profileModeManual: "Manuelle Profilauswahl",
      profileModeLinked: "Verwendet dein verknüpftes Brizel-Profil",
      cardCopy:
        "Suche nach einem Lebensmittel oder gib einen Barcode ein, wähle die verzehrte Menge und speichere den Eintrag für heute.",
      helperCopy:
        "Zuletzt verwendete Lebensmittel, Barcode-Suche und das bestehende Speichern in Brizel Health bleiben an dein verknüpftes Profil gebunden.",
      sourcePrefix: "Quelle: {source}",
      barcodeSourcePrefix: "Barcode-Suche über {source}",
      detailTitle: "Eintrag bestätigen",
      detailSubtitle:
        "Prüfe das Lebensmittel und wähle aus, wie viel du verzehrt hast.",
      searchTitle: "Lebensmittel suchen",
      barcodeTitle: "Barcode nachschlagen",
      closeDialog: "Dialog schließen",
      close: "Schließen",
      cancel: "Abbrechen",
      back: "Zurück",
      save: "Zu heute hinzufügen",
      saving: "Speichern...",
      searchMode: "Suche",
      barcodeMode: "Barcode",
      foodLookupMode: "Suchmodus",
      searchUnavailable: "Die Lebensmittelsuche ist gerade vorübergehend nicht verfügbar.",
      detailUnavailable:
        "Das ausgewählte Lebensmittel konnte gerade nicht geladen werden.",
      barcodeUnavailable:
        "Dieser Barcode konnte gerade nicht nachgeschlagen werden.",
      saveUnavailable: "Der Eintrag konnte gerade nicht gespeichert werden.",
      invalidAmount: "Bitte gib eine gültige Menge ein.",
      amountGreaterThanZero:
        "Bitte gib eine Menge größer als null ein.",
      invalidDateTime: "Bitte gib ein gültiges Datum und eine gültige Uhrzeit ein.",
      barcodeRequired: "Bitte gib einen Barcode ein.",
      successAdded: "{foodName} wurde zu heute hinzugefügt ({amount}).",
      recentFoods: "Zuletzt verwendete Lebensmittel",
      recentHeader:
        "Starte mit etwas, das du schon einmal erfasst hast, oder tippe zum Suchen.",
      recentBadge: "Zuletzt verwendet",
      recentUsed: "{count}x verwendet",
      recentLastAmount: "Zuletzt: {amount} g",
      detailLoading: "Lebensmittel-Details werden geladen...",
      detailErrorTitle: "Dieses Lebensmittel konnte nicht geladen werden",
      carbsLabel: "Kohlenhydrate",
      fieldAmount: "Menge",
      fieldUnit: "Einheit",
      fieldMeal: "Mahlzeit",
      fieldConsumedAt: "Verzehrt um",
      changeTime: "Zeit ändern",
      useCurrentTime: "Stattdessen aktuelle Zeit verwenden",
      timeDefaultsToNow: "Standard ist jetzt, wenn du diesen Bereich geschlossen lässt.",
      barcodeEnterTitle: "Barcode eingeben",
      barcodeEnterDetail:
        "Gib einen Barcode ein, um ein verpacktes Produkt zu suchen und dann im normalen Erfassungsablauf weiterzumachen.",
      barcodeEnterHint:
        "Verwende 8 bis 14 Ziffern. Brizel Health sucht über barcodefähige Quellen hinweg.",
      barcodeLoading: "Barcode wird gesucht...",
      barcodeErrorTitle: "Dieser Barcode konnte nicht nachgeschlagen werden",
      barcodeEmptyTitle: "Kein Produkt für diesen Barcode gefunden",
      barcodeEmptyDetail:
        "Prüfe die Ziffern und versuche es erneut oder wechsle zur Textsuche.",
      recentLoading: "Zuletzt verwendete Lebensmittel werden geladen...",
      searchIdleTitle: "Tippe, um nach einem Lebensmittel zu suchen",
      searchIdleDetail:
        "Suche über aktive Lebensmittelquellen hinweg und wähle das Lebensmittel aus, das du erfassen möchtest.",
      searchMinLengthTitle: "Tippe weiter, um zu suchen",
      searchMinLengthDetail:
        "Gib mindestens {count} Zeichen ein, um nach einem Lebensmittel zu suchen.",
      searchLoading: "Suche läuft...",
      searchErrorTitle: "Lebensmittel konnten nicht gesucht werden",
      searchEmptyTitle: "Keine passenden Lebensmittel gefunden",
      searchEmptyDetail:
        "Versuche eine andere Schreibweise, eine Marke oder einen allgemeineren Lebensmittelbegriff.",
      basisPer100g: "pro 100 g",
    },
  },
};

UI_STRINGS.en.entrySource = {
  manual: "Manual",
  barcode: "Barcode",
  photo_ai: "Photo AI",
  unknown: "Unknown",
};

Object.assign(UI_STRINGS.en.common, {
  automatic: "Automatic",
  home: "Home",
  back: "Back",
  today: "Today",
  saveChanges: "Save changes",
  saving: "Saving...",
  refresh: "Refresh",
  retry: "Retry",
  reuse: "Use again",
  delete: "Delete",
  deleting: "Deleting...",
  linkedProfile: "Linked profile",
  notConfigured: "Not configured",
  readOnly: "Read only",
  historyEntry: "History entry",
  sourcePrefix: "Source: {source}",
  date: "Date",
  time: "Time",
  amount: "Amount",
  unit: "Unit",
  loading: "Loading...",
  body: "Body",
  nutrition: "Nutrition",
  hydration: "Hydration",
  foodLogger: "Food Logger",
  history: "History",
  settings: "Settings",
});

UI_STRINGS.en.app = {
  title: "Brizel Health",
  homeTitle: "Brizel Home",
  homeSubtitle:
    "Keep your daily health view close and jump quickly into the areas you use most.",
  quickActions: "Quick actions",
  sections: "Sections",
  actionAddFood: "Add food",
  actionBarcode: "Open barcode",
  actionAddWater: "Add water",
  actionRemoveWater: "Remove water",
  actionHistory: "Open history",
  actionSettings: "Open settings",
  addWaterSuccess: "Added {amount} water to today.",
  addWaterError: "Water could not be added right now.",
  removeWaterSuccess: "Removed {amount} water from today.",
  removeWaterError: "Water could not be removed right now.",
  tileNutritionTitle: "Nutrition",
  tileNutritionDetail: "Calories, macros, and daily guidance.",
  tileHydrationTitle: "Hydration",
  tileHydrationDetail: "Hydration progress and quick water actions.",
  tileBodyTitle: "Body",
  tileBodyDetail: "Weight, activity, and body data for target calculations.",
  tileLoggerTitle: "Food Logger",
  tileLoggerDetail: "Search, barcode lookup, recents, and confirm flow.",
  tileHistoryTitle: "History",
  tileHistoryDetail: "Today's entries with meal context and reuse.",
  tileSettingsTitle: "Profile & Settings",
  tileSettingsDetail: "Language, region, units, and profile preferences.",
  sectionNutrition: "Nutrition",
  sectionHydration: "Hydration",
  sectionBody: "Body",
  sectionLogger: "Food Logger",
  sectionHistory: "History",
  sectionSettings: "Profile & Settings",
};

UI_STRINGS.en.hero = {
  titleDefault: "Today",
  labelToday: "Today",
  profileFallback: "Profile",
  rangeLabel: "Range",
  stateLoading: "Loading...",
  stateNoDataTitle: "No data yet today",
  stateNoDataDetail: "Once you log food, this card will show where you stand.",
  stateErrorTitle: "Couldn't load today's overview",
  lowLabel: "Low",
  recommendedLabel: "Recommended",
  highLabel: "High",
  gaugeAriaLabel: "Kcal progress",
};

UI_STRINGS.en.nutritionCard = {
  titleDefault: "Nutrition Overview",
  subtitle: "See where you are, and what you can still do today.",
  waitingEntity: "Waiting for Home Assistant data.",
  stateLoading: "Loading...",
  stateNoDataTitle: "No data yet today",
  stateNoDataDetail: "Once you log food, this card will show where you stand.",
  stateErrorTitle: "Couldn't load nutrition overview",
};

UI_STRINGS.en.hydrationCard = {
  titleDefault: "Hydration",
  waitingEntity: "Waiting for Home Assistant data.",
  stateLoading: "Loading...",
  stateNoDataTitle: "No data yet today",
  stateNoDataDetail:
    "Once you log water or food, this card will show today's hydration.",
  stateErrorTitle: "Couldn't load hydration",
  totalToday: "Total hydration today",
  helperLeft: "{amount} left to your target",
  helperAbove: "{amount} above your target",
  helperEntityUnavailable:
    "The configured hydration goal entity is unavailable right now.",
  helperNoGoalConfigured:
    "No hydration goal is configured for this card. Brizel Health does not yet provide its own built-in hydration target.",
  goalUnavailable: "Goal unavailable",
  noGoalConfigured: "No goal configured",
  drank: "Drank",
  fromFood: "From food",
  entityTotal: "Total",
  entityDrank: "Drank",
  entityFood: "From food",
  entityTarget: "Target",
};

UI_STRINGS.en.macroCard = {
  titleSuffix: "Detail",
  waitingEntity: "Waiting for Home Assistant data.",
  targetLabel: "Target",
  stateLoading: "Loading...",
  stateNoDataTitle: "No data yet today",
  stateNoDataDetail: "Once you log food, this card will show where you stand.",
  stateErrorTitle: "Couldn't load macro details",
  lowLabel: "Low",
  recommendedLabel: "Recommended",
  highLabel: "High",
  unknownStatus: "Unknown",
  targetRangeUnavailable: "Target range unavailable",
};

UI_STRINGS.en.macroStatus = {
  underRange: "Still {min}–{max} {unit} to reach your target range",
  withinRangeKcal: "In range, {amount} left",
  withinRangeMacro: "In range, {amount} {macro} left",
  overTargetKcal: "{amount} above your target range",
  overTargetMacro: "{amount} {macro} above your target range",
};

UI_STRINGS.de.entrySource = {
  manual: "Manuell",
  barcode: "Barcode",
  photo_ai: "Foto-KI",
  unknown: "Unbekannt",
};

Object.assign(UI_STRINGS.de.common, {
  automatic: "Automatisch",
  home: "Start",
  back: "Zurück",
  today: "Heute",
  saveChanges: "Änderungen speichern",
  saving: "Speichern...",
  refresh: "Aktualisieren",
  retry: "Erneut versuchen",
  reuse: "Erneut verwenden",
  delete: "Löschen",
  deleting: "Wird gelöscht...",
  linkedProfile: "Verknüpftes Profil",
  notConfigured: "Nicht konfiguriert",
  readOnly: "Schreibgeschützt",
  historyEntry: "Verlaufseintrag",
  sourcePrefix: "Quelle: {source}",
  date: "Datum",
  time: "Uhrzeit",
  amount: "Menge",
  unit: "Einheit",
  loading: "Laden...",
  body: "Körper",
  nutrition: "Ernährung",
  hydration: "Hydration",
  foodLogger: "Lebensmittel-Logger",
  history: "Verlauf",
  settings: "Einstellungen",
});

UI_STRINGS.de.app = {
  title: "Brizel Health",
  homeTitle: "Brizel Startseite",
  homeSubtitle:
    "Halte deinen täglichen Gesundheitsüberblick griffbereit und springe schnell in die Bereiche, die du am meisten nutzt.",
  quickActions: "Schnellaktionen",
  sections: "Bereiche",
  actionAddFood: "Lebensmittel hinzufügen",
  actionBarcode: "Barcode öffnen",
  actionAddWater: "Wasser hinzufügen",
  actionRemoveWater: "Wasser entfernen",
  actionHistory: "Verlauf öffnen",
  actionSettings: "Einstellungen öffnen",
  addWaterSuccess: "{amount} Wasser wurde zu heute hinzugefügt.",
  addWaterError: "Wasser konnte gerade nicht hinzugefügt werden.",
  removeWaterSuccess: "{amount} Wasser wurde von heute entfernt.",
  removeWaterError: "Wasser konnte gerade nicht entfernt werden.",
  tileNutritionTitle: "Ernährung",
  tileNutritionDetail: "Kalorien, Makros und tägliche Orientierung.",
  tileHydrationTitle: "Hydration",
  tileHydrationDetail: "Hydrationsfortschritt und schnelle Wasseraktionen.",
  tileBodyTitle: "Körper",
  tileBodyDetail: "Gewicht, Aktivität und Körperdaten für die Zielberechnung.",
  tileLoggerTitle: "Lebensmittel-Logger",
  tileLoggerDetail: "Suche, Barcode, zuletzt verwendete Lebensmittel und Bestätigung.",
  tileHistoryTitle: "Verlauf",
  tileHistoryDetail: "Heutige Einträge mit Mahlzeitenkontext und Wiederverwendung.",
  tileSettingsTitle: "Profil & Einstellungen",
  tileSettingsDetail: "Sprache, Region, Einheiten und Profilpräferenzen.",
  sectionNutrition: "Ernährung",
  sectionHydration: "Hydration",
  sectionBody: "Körper",
  sectionLogger: "Lebensmittel-Logger",
  sectionHistory: "Verlauf",
  sectionSettings: "Profil & Einstellungen",
};

UI_STRINGS.de.hero = {
  titleDefault: "Heute",
  labelToday: "Heute",
  profileFallback: "Profil",
  rangeLabel: "Zielbereich",
  stateLoading: "Laden...",
  stateNoDataTitle: "Heute noch keine Daten",
  stateNoDataDetail:
    "Sobald du Lebensmittel erfasst, zeigt dir diese Karte, wo du gerade stehst.",
  stateErrorTitle: "Der heutige Überblick konnte nicht geladen werden",
  lowLabel: "Niedrig",
  recommendedLabel: "Empfohlen",
  highLabel: "Hoch",
  gaugeAriaLabel: "Kalorienfortschritt",
};

UI_STRINGS.de.nutritionCard = {
  titleDefault: "Ernährungsübersicht",
  subtitle: "Sieh, wo du stehst und was heute noch möglich ist.",
  waitingEntity: "Warte auf Home-Assistant-Daten.",
  stateLoading: "Laden...",
  stateNoDataTitle: "Heute noch keine Daten",
  stateNoDataDetail:
    "Sobald du Lebensmittel erfasst, zeigt dir diese Karte, wo du gerade stehst.",
  stateErrorTitle: "Die Ernährungsübersicht konnte nicht geladen werden",
};

UI_STRINGS.de.hydrationCard = {
  titleDefault: "Hydration",
  waitingEntity: "Warte auf Home-Assistant-Daten.",
  stateLoading: "Laden...",
  stateNoDataTitle: "Heute noch keine Daten",
  stateNoDataDetail:
    "Sobald du Wasser oder Lebensmittel erfasst, zeigt diese Karte die heutige Hydration.",
  stateErrorTitle: "Hydration konnte nicht geladen werden",
  totalToday: "Gesamte Hydration heute",
  helperLeft: "{amount} bis zu deinem Ziel",
  helperAbove: "{amount} über deinem Ziel",
  helperEntityUnavailable:
    "Die konfigurierte Hydrationsziel-Entity ist gerade nicht verfügbar.",
  helperNoGoalConfigured:
    "Für diese Karte ist kein Hydrationsziel konfiguriert. Brizel Health bringt aktuell noch kein eigenes eingebautes Hydrationsziel mit.",
  goalUnavailable: "Ziel nicht verfügbar",
  noGoalConfigured: "Kein Ziel konfiguriert",
  drank: "Getrunken",
  fromFood: "Aus Lebensmitteln",
  entityTotal: "Gesamt",
  entityDrank: "Getrunken",
  entityFood: "Aus Lebensmitteln",
  entityTarget: "Ziel",
};

UI_STRINGS.de.macroCard = {
  titleSuffix: "im Detail",
  waitingEntity: "Warte auf Home-Assistant-Daten.",
  targetLabel: "Ziel",
  stateLoading: "Laden...",
  stateNoDataTitle: "Heute noch keine Daten",
  stateNoDataDetail:
    "Sobald du Lebensmittel erfasst, zeigt dir diese Karte, wo du gerade stehst.",
  stateErrorTitle: "Makro-Details konnten nicht geladen werden",
  lowLabel: "Niedrig",
  recommendedLabel: "Empfohlen",
  highLabel: "Hoch",
  unknownStatus: "Unbekannt",
  targetRangeUnavailable: "Zielbereich nicht verfügbar",
};

UI_STRINGS.de.macroStatus = {
  underRange: "Noch {min}–{max} {unit} bis zum Zielbereich",
  withinRangeKcal: "Im Zielbereich, noch {amount} bis zum oberen Zielwert",
  withinRangeMacro: "Im Zielbereich, noch {amount} {macro} bis zum oberen Zielwert",
  overTargetKcal: "{amount} über dem Zielbereich",
  overTargetMacro: "{amount} {macro} über dem Zielbereich",
};

UI_STRINGS.en.history = {
  titleDefault: "Today's entries",
  subtitle:
    "Review what you logged today, grouped by meal type when available.",
  dateLabel: "Date",
  loading: "Loading today's entries...",
  emptyTitle: "No food entries yet",
  emptyDetail: "Use the Food Logger to add your first entry for this day.",
  errorTitle: "Couldn't load food entries",
  deleteAction: "Delete",
  reuseAction: "Use again",
  deleteConfirm: "Delete this entry?",
  deleted: "Entry deleted.",
  mealSectionNone: "No meal type",
  amountLabel: "Logged",
  kcalLabel: "Energy",
  timeUnknown: "Time unavailable",
  sourceUnknown: "Source unavailable",
  reuseSourceLabel: "History entry",
  deleteUnavailable: "This entry could not be deleted right now.",
};

UI_STRINGS.en.profile = {
  titleDefault: "Profile & settings",
  subtitle:
    "Manage your Brizel profile, preferences, body data, and derived nutrition targets.",
  sectionProfile: "Profile",
  sectionPreferences: "Preferences",
  sectionBody: "Body",
  sectionTargets: "Targets",
  fieldDisplayName: "Display name",
  fieldLinkedHaUser: "Linked Home Assistant user",
  fieldProfileId: "Profile ID",
  fieldLanguage: "Language",
  fieldRegion: "Food market",
  fieldUnits: "Units",
  fieldAge: "Age",
  fieldSex: "Sex",
  fieldHeight: "Height (cm)",
  fieldWeight: "Weight (kg)",
  fieldActivity: "Activity level",
  optionLanguageAuto: "Automatic",
  optionLanguageDe: "Deutsch",
  optionLanguageEn: "English",
  optionRegionAuto: "Automatic",
  optionRegionGermany: "Germany",
  optionRegionEu: "EU",
  optionRegionUsa: "USA",
  optionRegionGlobal: "Global",
  optionUnitsAuto: "Automatic",
  optionUnitsMetric: "Metric",
  optionUnitsImperial: "Imperial",
  optionSexUnset: "Not set",
  optionSexFemale: "Female",
  optionSexMale: "Male",
  optionActivityUnset: "Not set",
  optionActivitySedentary: "Sedentary",
  optionActivityLight: "Light",
  optionActivityModerate: "Moderate",
  optionActivityActive: "Active",
  optionActivityVeryActive: "Very active",
  saveProfile: "Save profile",
  saveBody: "Save body data",
  savingProfile: "Saving profile...",
  savingBody: "Saving body data...",
  savedProfile: "Profile settings saved.",
  savedBody: "Body data saved.",
  loadErrorTitle: "Couldn't load profile data",
  targetsDerived:
    "These targets are derived from your saved body profile. They are currently read-only in the frontend.",
  targetsMissingFields: "More body data is needed for stable targets: {fields}",
  targetsUnsupported: "Target calculation is currently limited: {reasons}",
  targetCalories: "Daily kcal",
  targetProtein: "Daily protein",
  targetFat: "Daily fat",
  hydrationTargetNote:
    "Hydration targets are currently configured separately in Home Assistant.",
  bodyEmpty:
    "Save body data here to improve derived nutrition targets and profile guidance.",
};

UI_STRINGS.de.history = {
  titleDefault: "Heutige Einträge",
  subtitle:
    "Prüfe, was du heute erfasst hast, sinnvoll nach Mahlzeiten gruppiert, wenn vorhanden.",
  dateLabel: "Datum",
  loading: "Heutige Einträge werden geladen...",
  emptyTitle: "Noch keine Einträge",
  emptyDetail:
    "Nutze den Lebensmittel-Logger, um deinen ersten Eintrag für diesen Tag hinzuzufügen.",
  errorTitle: "Einträge konnten nicht geladen werden",
  deleteAction: "Löschen",
  reuseAction: "Erneut verwenden",
  deleteConfirm: "Diesen Eintrag löschen?",
  deleted: "Eintrag gelöscht.",
  mealSectionNone: "Keine Mahlzeit",
  amountLabel: "Geloggt",
  kcalLabel: "Energie",
  timeUnknown: "Uhrzeit nicht verfügbar",
  sourceUnknown: "Quelle nicht verfügbar",
  reuseSourceLabel: "Verlaufseintrag",
  deleteUnavailable: "Dieser Eintrag konnte gerade nicht gelöscht werden.",
};

UI_STRINGS.de.profile = {
  titleDefault: "Profil & Einstellungen",
  subtitle:
    "Verwalte dein Brizel-Profil, deine Präferenzen, Körperdaten und abgeleitete Ernährungsziele.",
  sectionProfile: "Profil",
  sectionPreferences: "Präferenzen",
  sectionBody: "Körper",
  sectionTargets: "Ziele",
  fieldDisplayName: "Anzeigename",
  fieldLinkedHaUser: "Verknüpfter Home-Assistant-Nutzer",
  fieldProfileId: "Profil-ID",
  fieldLanguage: "Sprache",
  fieldRegion: "Lebensmittelmarkt",
  fieldUnits: "Einheiten",
  fieldAge: "Alter",
  fieldSex: "Geschlecht",
  fieldHeight: "Größe (cm)",
  fieldWeight: "Gewicht (kg)",
  fieldActivity: "Aktivitätslevel",
  optionLanguageAuto: "Automatisch",
  optionLanguageDe: "Deutsch",
  optionLanguageEn: "Englisch",
  optionRegionAuto: "Automatisch",
  optionRegionGermany: "Deutschland",
  optionRegionEu: "EU",
  optionRegionUsa: "USA",
  optionRegionGlobal: "Global",
  optionUnitsAuto: "Automatisch",
  optionUnitsMetric: "Metrisch",
  optionUnitsImperial: "Imperial",
  optionSexUnset: "Nicht gesetzt",
  optionSexFemale: "Weiblich",
  optionSexMale: "Männlich",
  optionActivityUnset: "Nicht gesetzt",
  optionActivitySedentary: "Sitzend",
  optionActivityLight: "Leicht aktiv",
  optionActivityModerate: "Moderat aktiv",
  optionActivityActive: "Aktiv",
  optionActivityVeryActive: "Sehr aktiv",
  saveProfile: "Profil speichern",
  saveBody: "Körperdaten speichern",
  savingProfile: "Profil wird gespeichert...",
  savingBody: "Körperdaten werden gespeichert...",
  savedProfile: "Profil-Einstellungen gespeichert.",
  savedBody: "Körperdaten gespeichert.",
  loadErrorTitle: "Profildaten konnten nicht geladen werden",
  targetsDerived:
    "Diese Ziele werden aus deinem gespeicherten Körperprofil abgeleitet. Im Frontend sind sie aktuell nur lesbar.",
  targetsMissingFields:
    "Für stabile Ziele werden weitere Körperdaten benötigt: {fields}",
  targetsUnsupported:
    "Die Zielberechnung ist aktuell eingeschränkt: {reasons}",
  targetCalories: "Tägliche Kalorien",
  targetProtein: "Tägliches Protein",
  targetFat: "Tägliches Fett",
  hydrationTargetNote:
    "Hydrationsziele werden aktuell separat in Home Assistant konfiguriert.",
  bodyEmpty:
    "Speichere hier Körperdaten, um abgeleitete Ernährungsziele und Profilhinweise zu verbessern.",
};

UI_STRINGS.en.body = {
  titleDefault: "Body progress",
  subtitle:
    "Track weight and body measurements over time, keep a target weight in view, and review recent progress.",
  overviewTitle: "Progress summary",
  overviewDetail:
    "Your latest measurement, goal distance, and lightweight trends stay in one place.",
  quickWeightTitle: "Quick weight entry",
  quickWeightDetail:
    "Add your latest weight quickly without leaving the app shell.",
  goalTitle: "Target weight",
  goalDetail:
    "Keep one explicit target weight for distance-to-goal and progress context.",
  measurementFormTitle: "Add measurement",
  measurementFormDetail:
    "Weight is the fastest path, but all supported body measurements are ready for logging.",
  historyTitle: "Recent measurements",
  historyDetail:
    "Latest measurements across types, sorted from newest to oldest.",
  fieldWeightValue: "Weight",
  fieldTargetWeight: "Target weight",
  fieldMeasurementType: "Measurement type",
  fieldMeasurementValue: "Value",
  fieldMeasuredAt: "Measured at",
  fieldMeasurementNote: "Note",
  saveWeight: "Log weight",
  saveMeasurement: "Save measurement",
  saveGoal: "Save goal",
  savingWeight: "Saving weight...",
  savingMeasurement: "Saving measurement...",
  savingGoal: "Saving goal...",
  savedWeight: "Weight saved.",
  savedMeasurement: "Measurement saved.",
  savedGoal: "Target weight saved.",
  saveWeightError: "Weight could not be saved right now.",
  saveMeasurementError: "Measurement could not be saved right now.",
  saveGoalError: "Target weight could not be saved right now.",
  loadErrorTitle: "Couldn't load body progress",
  noMeasurementsTitle: "No body measurements yet",
  noMeasurementsDetail:
    "Start with your weight, then add waist or other measurements when you want more detail.",
  deleteConfirm: "Delete this measurement?",
  deleted: "Measurement deleted.",
  deleteUnavailable: "This measurement could not be deleted right now.",
  currentWeight: "Current weight",
  targetWeight: "Target weight",
  distanceToGoal: "Distance to goal",
  changeSincePrevious: "Change since last",
  changeSinceStart: "Change since start",
  trend7d: "7-day trend",
  trend30d: "30-day trend",
  lastMeasured: "Last measured",
  goalUnset: "No target weight set yet",
  latestValueUnavailable: "No current body data yet",
  measurementType: {
    weight: "Weight",
    waist: "Waist",
    abdomen: "Abdomen",
    hip: "Hip",
    chest: "Chest",
    upper_arm: "Upper arm",
    forearm: "Forearm",
    thigh: "Thigh",
    calf: "Calf",
    neck: "Neck",
  },
  measurementSource: {
    manual: "Manual",
    imported: "Imported",
    synced: "Synced",
  },
};

UI_STRINGS.de.body = {
  titleDefault: "Körperfortschritt",
  subtitle:
    "Erfasse Gewicht und Körpermaße über die Zeit, halte dein Zielgewicht im Blick und prüfe deinen Fortschritt.",
  overviewTitle: "Fortschrittsübersicht",
  overviewDetail:
    "Letzte Messung, Zielabstand und leichte Trends bleiben an einem Ort sichtbar.",
  quickWeightTitle: "Gewicht schnell eintragen",
  quickWeightDetail:
    "Erfasse dein aktuelles Gewicht direkt, ohne die App-Struktur zu verlassen.",
  goalTitle: "Zielgewicht",
  goalDetail:
    "Lege ein klares Zielgewicht fest, damit Abstand zum Ziel und Fortschritt sichtbar bleiben.",
  measurementFormTitle: "Messung hinzufügen",
  measurementFormDetail:
    "Gewicht ist der schnellste Einstieg, aber alle unterstützten Körpermaße können direkt erfasst werden.",
  historyTitle: "Letzte Messungen",
  historyDetail:
    "Neueste Messungen über alle Typen hinweg, von neu nach alt sortiert.",
  fieldWeightValue: "Gewicht",
  fieldTargetWeight: "Zielgewicht",
  fieldMeasurementType: "Messart",
  fieldMeasurementValue: "Wert",
  fieldMeasuredAt: "Gemessen am",
  fieldMeasurementNote: "Notiz",
  saveWeight: "Gewicht speichern",
  saveMeasurement: "Messung speichern",
  saveGoal: "Ziel speichern",
  savingWeight: "Gewicht wird gespeichert...",
  savingMeasurement: "Messung wird gespeichert...",
  savingGoal: "Ziel wird gespeichert...",
  savedWeight: "Gewicht gespeichert.",
  savedMeasurement: "Messung gespeichert.",
  savedGoal: "Zielgewicht gespeichert.",
  saveWeightError: "Das Gewicht konnte gerade nicht gespeichert werden.",
  saveMeasurementError: "Die Messung konnte gerade nicht gespeichert werden.",
  saveGoalError: "Das Zielgewicht konnte gerade nicht gespeichert werden.",
  loadErrorTitle: "Körperfortschritt konnte nicht geladen werden",
  noMeasurementsTitle: "Noch keine Körpermessungen",
  noMeasurementsDetail:
    "Starte mit deinem Gewicht und ergänze später Taille oder andere Maße, wenn du mehr Details möchtest.",
  deleteConfirm: "Diese Messung löschen?",
  deleted: "Messung gelöscht.",
  deleteUnavailable: "Diese Messung konnte gerade nicht gelöscht werden.",
  currentWeight: "Aktuelles Gewicht",
  targetWeight: "Zielgewicht",
  distanceToGoal: "Abstand zum Ziel",
  changeSincePrevious: "Veränderung seit der letzten Messung",
  changeSinceStart: "Veränderung seit dem Start",
  trend7d: "7-Tage-Trend",
  trend30d: "30-Tage-Trend",
  lastMeasured: "Zuletzt gemessen",
  goalUnset: "Noch kein Zielgewicht gesetzt",
  latestValueUnavailable: "Noch keine aktuellen Körperdaten",
  measurementType: {
    weight: "Gewicht",
    waist: "Taille",
    abdomen: "Bauch",
    hip: "Hüfte",
    chest: "Brust",
    upper_arm: "Oberarm",
    forearm: "Unterarm",
    thigh: "Oberschenkel",
    calf: "Wade",
    neck: "Hals",
  },
  measurementSource: {
    manual: "Manuell",
    imported: "Importiert",
    synced: "Synchronisiert",
  },
};

const STATUS_META = {
  under: { labelKey: "status.under", color: "#f59e0b", tint: "rgba(245, 158, 11, 0.14)" },
  within: { labelKey: "status.within", color: "#22c55e", tint: "rgba(34, 197, 94, 0.14)" },
  over: { labelKey: "status.over", color: "#ef4444", tint: "rgba(239, 68, 68, 0.14)" },
  unknown: { labelKey: "status.unknown", color: "#94a3b8", tint: "rgba(148, 163, 184, 0.14)" },
  unavailable: {
    labelKey: "status.unavailable",
    color: "#94a3b8",
    tint: "rgba(148, 163, 184, 0.14)",
  },
};

const MACROS = {
  kcal: { key: "kcal", titleKey: "macro.kcal", icon: "mdi:fire", unit: "kcal" },
  protein: { key: "protein", titleKey: "macro.protein", icon: "mdi:food-steak", unit: "g" },
  fat: { key: "fat", titleKey: "macro.fat", icon: "mdi:oil", unit: "g" },
};

const normalizeUiLanguageChoice = (value) => {
  const normalized = trimToNull(value)?.toLowerCase();
  if (!normalized) {
    return UI_LANGUAGE_AUTO;
  }
  if (normalized === UI_LANGUAGE_AUTO) {
    return UI_LANGUAGE_AUTO;
  }
  if (normalized.startsWith(UI_LANGUAGE_DE)) {
    return UI_LANGUAGE_DE;
  }
  if (normalized.startsWith(UI_LANGUAGE_EN)) {
    return UI_LANGUAGE_EN;
  }
  return UI_LANGUAGE_AUTO;
};

const _normalizeDetectedLanguage = (value) => {
  const normalized = trimToNull(value)?.toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized.startsWith(UI_LANGUAGE_DE)) {
    return UI_LANGUAGE_DE;
  }
  if (normalized.startsWith(UI_LANGUAGE_EN)) {
    return UI_LANGUAGE_EN;
  }
  return null;
};

const detectAutoLanguage = (hass = null) => {
  const hints = [
    hass?.language,
    hass?.locale?.language,
    hass?.config?.language,
    globalThis?.document?.documentElement?.lang,
    globalThis?.navigator?.language,
  ];
  for (const hint of hints) {
    const normalized = _normalizeDetectedLanguage(hint);
    if (normalized) {
      return normalized;
    }
  }
  return UI_LANGUAGE_EN;
};

const resolveEffectiveUiLanguage = (context = {}) => {
  if (typeof context === "string") {
    const normalizedChoice = normalizeUiLanguageChoice(context);
    return normalizedChoice === UI_LANGUAGE_AUTO
      ? detectAutoLanguage()
      : normalizedChoice;
  }

  const normalizedChoice = normalizeUiLanguageChoice(
    context?.preferredLanguage ?? context?.language
  );
  if (normalizedChoice !== UI_LANGUAGE_AUTO) {
    return normalizedChoice;
  }
  return detectAutoLanguage(context?.hass);
};

const _lookupTranslation = (language, key) =>
  key
    .split(".")
    .reduce((value, part) => (value && value[part] !== undefined ? value[part] : undefined), UI_STRINGS[language]);

const _interpolateTranslation = (template, vars = {}) =>
  String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (_match, key) =>
    String(vars[key] ?? "")
  );

const translateText = (context, key, vars = {}) => {
  const language = resolveEffectiveUiLanguage(context);
  const template =
    _lookupTranslation(language, key) ?? _lookupTranslation(UI_LANGUAGE_EN, key) ?? key;
  return _interpolateTranslation(template, vars);
};

const createTranslator = (context = {}) => {
  const language = resolveEffectiveUiLanguage(context);
  return {
    language,
    t: (key, vars = {}) =>
      translateText({ ...context, preferredLanguage: language }, key, vars),
  };
};

const getMealTypeLabel = (mealType, context = {}) => {
  const normalized = trimToNull(mealType) || "none";
  return translateText(context, `mealType.${normalized}`);
};

const getMealTypeOptions = (context = {}, { includeEmpty = false } = {}) => {
  const options = [];
  if (includeEmpty) {
    options.push({ value: "", label: getMealTypeLabel("none", context) });
  }
  ["breakfast", "lunch", "dinner", "snack"].forEach((mealType) => {
    options.push({ value: mealType, label: getMealTypeLabel(mealType, context) });
  });
  return options;
};

const getEntrySourceLabel = (source, context = {}) => {
  const normalized = trimToNull(source) || "unknown";
  return translateText(context, `entrySource.${normalized}`);
};

const getBodyMeasurementTypeLabel = (measurementType, context = {}) => {
  const normalized = trimToNull(measurementType) || "weight";
  return translateText(context, `body.measurementType.${normalized}`);
};

const getBodyMeasurementSourceLabel = (source, context = {}) => {
  const normalized = trimToNull(source) || "manual";
  return translateText(context, `body.measurementSource.${normalized}`);
};

const getBodyMeasurementTypeOptions = (
  measurementTypes = [],
  context = {},
  { includeWeight = true } = {}
) =>
  measurementTypes
    .filter((measurementType) => includeWeight || measurementType?.key !== "weight")
    .map((measurementType) => ({
      ...measurementType,
      value: measurementType.key,
      label: getBodyMeasurementTypeLabel(measurementType.key, context),
    }));

const getPreferredLanguageOptions = (context = {}) => [
  { value: "auto", label: translateText(context, "profile.optionLanguageAuto") },
  { value: "de", label: translateText(context, "profile.optionLanguageDe") },
  { value: "en", label: translateText(context, "profile.optionLanguageEn") },
];

const getPreferredRegionOptions = (context = {}) => [
  { value: "", label: translateText(context, "profile.optionRegionAuto") },
  { value: "germany", label: translateText(context, "profile.optionRegionGermany") },
  { value: "eu", label: translateText(context, "profile.optionRegionEu") },
  { value: "usa", label: translateText(context, "profile.optionRegionUsa") },
  { value: "global", label: translateText(context, "profile.optionRegionGlobal") },
];

const getPreferredUnitsOptions = (context = {}) => [
  { value: "", label: translateText(context, "profile.optionUnitsAuto") },
  { value: "metric", label: translateText(context, "profile.optionUnitsMetric") },
  { value: "imperial", label: translateText(context, "profile.optionUnitsImperial") },
];

const getSexOptions = (context = {}) => [
  { value: "", label: translateText(context, "profile.optionSexUnset") },
  { value: "female", label: translateText(context, "profile.optionSexFemale") },
  { value: "male", label: translateText(context, "profile.optionSexMale") },
];

const getActivityLevelOptions = (context = {}) => [
  { value: "", label: translateText(context, "profile.optionActivityUnset") },
  { value: "sedentary", label: translateText(context, "profile.optionActivitySedentary") },
  { value: "light", label: translateText(context, "profile.optionActivityLight") },
  { value: "moderate", label: translateText(context, "profile.optionActivityModerate") },
  { value: "active", label: translateText(context, "profile.optionActivityActive") },
  { value: "very_active", label: translateText(context, "profile.optionActivityVeryActive") },
];

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

const _getIntlLocale = (context = {}) =>
  resolveEffectiveUiLanguage(context) === UI_LANGUAGE_DE ? "de-DE" : "en-US";

const formatDate = (value, context = {}, options = {}) => {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat(_getIntlLocale(context), {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...options,
  }).format(date);
};

const formatTime = (value, context = {}, options = {}) => {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat(_getIntlLocale(context), {
    hour: "2-digit",
    minute: "2-digit",
    ...options,
  }).format(date);
};

const getStatusMeta = (status, context = {}) => {
  const base = STATUS_META[status] || STATUS_META.unknown;
  return {
    label: translateText(context, base.labelKey),
    color: base.color,
    tint: base.tint,
  };
};

const getMacroConfig = (macro, context = {}) => {
  const config = MACROS[String(macro ?? "").toLowerCase()];
  if (!config) {
    throw new Error("Macro must be one of: kcal, protein, fat");
  }
  return {
    ...config,
    title: translateText(context, config.titleKey),
  };
};

const buildMacroDisplayText = (
  {
    macroKey,
    macroTitle,
    unit,
    status,
    remainingToMin,
    remainingToMax,
    overAmount,
  },
  context = {}
) => {
  const normalizedStatus = String(status ?? "unknown").toLowerCase();
  if (
    normalizedStatus === "under" &&
    remainingToMin !== null &&
    remainingToMax !== null
  ) {
    return translateText(context, "macroStatus.underRange", {
      min: formatNumber(remainingToMin),
      max: formatNumber(remainingToMax),
      unit,
    });
  }

  if (normalizedStatus === "within" && remainingToMax !== null) {
    const amount = formatValue(remainingToMax, unit);
    if (macroKey === "kcal") {
      return translateText(context, "macroStatus.withinRangeKcal", {
        amount,
      });
    }
    return translateText(context, "macroStatus.withinRangeMacro", {
      amount,
      macro: macroTitle,
    });
  }

  if (normalizedStatus === "over" && overAmount !== null) {
    const amount = formatValue(overAmount, unit);
    if (macroKey === "kcal") {
      return translateText(context, "macroStatus.overTargetKcal", {
        amount,
      });
    }
    return translateText(context, "macroStatus.overTargetMacro", {
      amount,
      macro: macroTitle,
    });
  }

  return translateText(context, "common.targetRangeUnavailable");
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

const getMacroDataFromOverview = (overview, macro, context = {}) => {
  const macroConfig = getMacroConfig(macro, context);
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
    displayText: buildMacroDisplayText(
      {
        macroKey: macroConfig.key,
        macroTitle: macroConfig.title,
        unit: macroConfig.unit,
        status: raw.status,
        remainingToMin,
        remainingToMax,
        overAmount,
      },
      context
    ),
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

const getMacroDataFromEntity = (hass, { macro, entityId }, context = {}) => {
  const translatorContext = { hass, ...context };
  const macroConfig = getMacroConfig(macro, translatorContext);
  const stateObj = readEntity(hass, entityId);
  if (!stateObj) {
    return {
      ...macroConfig,
      entityId,
      available: false,
      status: "unavailable",
      displayText: translateText(translatorContext, "common.sensorUnavailable"),
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
    displayText: buildMacroDisplayText(
      {
        macroKey: macroConfig.key,
        macroTitle: macroConfig.title,
        unit: macroConfig.unit,
        status: stateObj.state,
        remainingToMin,
        remainingToMax,
        overAmount,
      },
      translatorContext
    ),
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

const getProfile = async (hass, { profileId }) => {
  const parsed = await callBrizelServiceWithResponse(hass, "get_profile", {
    profile_id: profileId,
  });
  if (!parsed.profile || typeof parsed.profile !== "object") {
    throw new Error("Could not parse Brizel Health profile response.");
  }
  return parsed.profile;
};

const getProfiles = async (hass) => {
  const parsed = await callBrizelServiceWithResponse(hass, "get_profiles");
  return Array.isArray(parsed.profiles) ? parsed.profiles : [];
};

const updateProfile = async (
  hass,
  {
    profileId,
    displayName,
    preferredLanguage = undefined,
    preferredRegion = undefined,
    preferredUnits = undefined,
  }
) => {
  const payload = {
    profile_id: profileId,
    display_name: displayName,
  };
  if (preferredLanguage !== undefined && preferredLanguage !== null) {
    payload.preferred_language = String(preferredLanguage);
  }
  if (preferredRegion !== undefined && preferredRegion !== null) {
    payload.preferred_region = String(preferredRegion);
  }
  if (preferredUnits !== undefined && preferredUnits !== null) {
    payload.preferred_units = String(preferredUnits);
  }
  const parsed = await callBrizelServiceWithResponse(hass, "update_profile", payload);
  if (!parsed.profile || typeof parsed.profile !== "object") {
    throw new Error("Could not parse Brizel Health profile response.");
  }
  return parsed.profile;
};

const getBodyProfile = async (hass, { profileId }) => {
  const parsed = await callBrizelServiceWithResponse(hass, "get_body_profile", {
    profile_id: profileId,
  });
  if (!parsed.body_profile || typeof parsed.body_profile !== "object") {
    throw new Error("Could not parse Brizel Health body profile response.");
  }
  return parsed.body_profile;
};

const updateBodyProfile = async (
  hass,
  {
    profileId,
    ageYears = null,
    sex = null,
    heightCm = null,
    weightKg = null,
    activityLevel = null,
  }
) => {
  const payload = {
    profile_id: profileId,
  };
  if (Number.isFinite(Number(ageYears))) {
    payload.age_years = Number(ageYears);
  }
  if (trimToNull(sex)) {
    payload.sex = trimToNull(sex);
  }
  if (Number.isFinite(Number(heightCm))) {
    payload.height_cm = Number(heightCm);
  }
  if (Number.isFinite(Number(weightKg))) {
    payload.weight_kg = Number(weightKg);
  }
  if (trimToNull(activityLevel)) {
    payload.activity_level = trimToNull(activityLevel);
  }
  const parsed = await callBrizelServiceWithResponse(hass, "update_body_profile", payload);
  if (!parsed.body_profile || typeof parsed.body_profile !== "object") {
    throw new Error("Could not parse Brizel Health body profile response.");
  }
  return parsed.body_profile;
};

const getBodyTargets = async (hass, { profileId }) => {
  const parsed = await callBrizelServiceWithResponse(hass, "get_body_targets", {
    profile_id: profileId,
  });
  if (!parsed.targets || typeof parsed.targets !== "object") {
    throw new Error("Could not parse Brizel Health targets response.");
  }
  return parsed.targets;
};

const getBodyMeasurementTypes = async (hass, { profileId }) => {
  const parsed = await callBrizelServiceWithResponse(
    hass,
    "get_body_measurement_types",
    {
      profile_id: profileId,
    }
  );
  return Array.isArray(parsed.measurement_types) ? parsed.measurement_types : [];
};

const addBodyMeasurement = async (
  hass,
  {
    profileId,
    measurementType,
    value,
    unit = undefined,
    measuredAt = undefined,
    source = undefined,
    note = undefined,
  }
) => {
  const payload = {
    profile_id: profileId,
    measurement_type: measurementType,
    value: Number(value),
  };
  if (trimToNull(unit)) {
    payload.unit = trimToNull(unit);
  }
  if (trimToNull(measuredAt)) {
    payload.measured_at = trimToNull(measuredAt);
  }
  if (trimToNull(source)) {
    payload.source = trimToNull(source);
  }
  if (note !== undefined) {
    payload.note = String(note ?? "");
  }
  const parsed = await callBrizelServiceWithResponse(
    hass,
    "add_body_measurement",
    payload
  );
  if (!parsed.measurement || typeof parsed.measurement !== "object") {
    throw new Error("Could not parse Brizel Health body measurement response.");
  }
  return parsed.measurement;
};

const updateBodyMeasurement = async (
  hass,
  {
    measurementId,
    measurementType = undefined,
    value = undefined,
    unit = undefined,
    measuredAt = undefined,
    source = undefined,
    note = undefined,
  }
) => {
  const payload = {
    measurement_id: measurementId,
  };
  if (trimToNull(measurementType)) {
    payload.measurement_type = trimToNull(measurementType);
  }
  if (Number.isFinite(Number(value))) {
    payload.value = Number(value);
  }
  if (trimToNull(unit)) {
    payload.unit = trimToNull(unit);
  }
  if (measuredAt !== undefined) {
    payload.measured_at = String(measuredAt ?? "");
  }
  if (source !== undefined) {
    payload.source = String(source ?? "");
  }
  if (note !== undefined) {
    payload.note = String(note ?? "");
  }
  const parsed = await callBrizelServiceWithResponse(
    hass,
    "update_body_measurement",
    payload
  );
  if (!parsed.measurement || typeof parsed.measurement !== "object") {
    throw new Error("Could not parse Brizel Health body measurement response.");
  }
  return parsed.measurement;
};

const deleteBodyMeasurement = async (hass, { measurementId }) => {
  const parsed = await callBrizelServiceWithResponse(
    hass,
    "delete_body_measurement",
    {
      measurement_id: measurementId,
    }
  );
  if (!parsed.measurement || typeof parsed.measurement !== "object") {
    throw new Error("Could not parse Brizel Health body measurement response.");
  }
  return parsed.measurement;
};

const getBodyMeasurementHistory = async (
  hass,
  { profileId, measurementType = undefined, limit = 30 }
) => {
  const payload = {
    profile_id: profileId,
    limit: Number(limit),
  };
  if (trimToNull(measurementType)) {
    payload.measurement_type = trimToNull(measurementType);
  }
  const parsed = await callBrizelServiceWithResponse(
    hass,
    "get_body_measurement_history",
    payload
  );
  return Array.isArray(parsed.measurements) ? parsed.measurements : [];
};

const getBodyGoal = async (hass, { profileId }) => {
  const parsed = await callBrizelServiceWithResponse(hass, "get_body_goal", {
    profile_id: profileId,
  });
  return parsed.goal && typeof parsed.goal === "object" ? parsed.goal : null;
};

const setBodyGoal = async (
  hass,
  { profileId, targetWeight, unit = undefined }
) => {
  const payload = {
    profile_id: profileId,
    target_weight: Number(targetWeight),
  };
  if (trimToNull(unit)) {
    payload.unit = trimToNull(unit);
  }
  const parsed = await callBrizelServiceWithResponse(hass, "set_body_goal", payload);
  if (!parsed.goal || typeof parsed.goal !== "object") {
    throw new Error("Could not parse Brizel Health body goal response.");
  }
  return parsed.goal;
};

const getBodyProgressSummary = async (
  hass,
  { profileId, measurementType = "weight" }
) => {
  const parsed = await callBrizelServiceWithResponse(
    hass,
    "get_body_progress_summary",
    {
      profile_id: profileId,
      measurement_type: measurementType,
    }
  );
  if (!parsed.summary || typeof parsed.summary !== "object") {
    throw new Error("Could not parse Brizel Health body progress response.");
  }
  return parsed.summary;
};

const getBodyTrends = async (
  hass,
  { profileId, measurementType = "weight", limit = 30 }
) => {
  const parsed = await callBrizelServiceWithResponse(hass, "get_body_trends", {
    profile_id: profileId,
    measurement_type: measurementType,
    limit: Number(limit),
  });
  if (!parsed.trends || typeof parsed.trends !== "object") {
    throw new Error("Could not parse Brizel Health body trends response.");
  }
  return parsed.trends;
};

const getFood = async (hass, { foodId }) => {
  const parsed = await callBrizelServiceWithResponse(hass, "get_food", {
    food_id: foodId,
  });
  if (!parsed.food || typeof parsed.food !== "object") {
    throw new Error("Could not parse Brizel Health food response.");
  }
  return parsed.food;
};

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

const buildProfileError = (
  kind,
  { explicitProfile = null, rawMessage = "", context = {} } = {}
) => {
  if (kind === "no_user") {
    return {
      kind,
      title: translateText(context, "profileError.noUserTitle"),
      detail: translateText(context, "profileError.noUserDetail"),
      rawMessage,
    };
  }
  if (kind === "no_link") {
    return {
      kind,
      title: translateText(context, "profileError.noLinkTitle"),
      detail: translateText(context, "profileError.noLinkDetail"),
      rawMessage,
    };
  }
  if (kind === "invalid_profile") {
    return {
      kind,
      title: translateText(context, "profileError.invalidProfileTitle"),
      detail: explicitProfile
        ? translateText(context, "profileError.invalidProfileConfiguredDetail")
        : translateText(context, "profileError.invalidProfileLinkedDetail"),
      rawMessage,
    };
  }
  return {
    kind: "generic",
    title: translateText(context, "profileError.genericTitle"),
    detail: rawMessage || translateText(context, "profileError.genericDetail"),
    rawMessage,
  };
};

const extractReadableErrorMessage = (value, depth = 0) => {
  if (depth > 4 || value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    return trimToNull(value);
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return trimToNull(String(value));
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const extracted = extractReadableErrorMessage(item, depth + 1);
      if (extracted) {
        return extracted;
      }
    }
    return null;
  }
  if (typeof value === "object") {
    for (const key of [
      "message",
      "detail",
      "error",
      "body",
      "description",
      "reason",
      "title",
    ]) {
      const extracted = extractReadableErrorMessage(value[key], depth + 1);
      if (extracted) {
        return extracted;
      }
    }
  }
  return null;
};

const getReadableErrorMessage = (error, fallback = null) =>
  extractReadableErrorMessage(error) || trimToNull(fallback);

const normalizeServiceError = (error, { explicitProfile = null, context = {} } = {}) => {
  const rawMessage = getReadableErrorMessage(error, "Unknown error") || "Unknown error";
  const kind = classifyProfileErrorMessage(rawMessage);
  return buildProfileError(kind, { explicitProfile, rawMessage, context });
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
      error: buildProfileError("no_user", { context: { hass } }),
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
    const normalizedError = normalizeServiceError(error, {
      explicitProfile,
      context: { hass },
    });
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

const getRecentFoods = async (hass, { profileId = null, limit = 6 } = {}) => {
  const payload = {
    limit,
  };
  if (trimToNull(profileId)) {
    payload.profile_id = trimToNull(profileId);
  }

  const parsed = await callBrizelServiceWithResponse(hass, "get_recent_foods", payload);
  const foods = Array.isArray(parsed.foods) ? parsed.foods : [];
  return {
    profileId: trimToNull(parsed.profile_id),
    foods: foods.map((food) => ({
      ...food,
      name: trimToNull(food?.name) || translateText({ hass }, "common.foodFallback"),
      brand: trimToNull(food?.brand),
      last_used_at: trimToNull(food?.last_used_at),
      use_count: Number.isFinite(Number(food?.use_count)) ? Number(food.use_count) : 0,
      is_favorite: Boolean(food?.is_favorite),
      last_logged_grams:
        Number.isFinite(Number(food?.last_logged_grams)) && Number(food?.last_logged_grams) > 0
          ? Number(food.last_logged_grams)
          : null,
      last_meal_type: trimToNull(food?.last_meal_type),
    })),
  };
};

const getFoodEntriesForProfileDate = async (hass, { profileId, date }) => {
  const parsed = await callBrizelServiceWithResponse(
    hass,
    "get_food_entries_for_profile_date",
    {
      profile_id: profileId,
      date,
    }
  );
  const foodEntries = Array.isArray(parsed.food_entries) ? parsed.food_entries : [];
  return foodEntries.map((entry) => ({
    ...entry,
    food_name: trimToNull(entry?.food_name) || translateText({ hass }, "common.foodFallback"),
    food_brand: trimToNull(entry?.food_brand),
    meal_type: trimToNull(entry?.meal_type),
    source: trimToNull(entry?.source) || "unknown",
    consumed_at: trimToNull(entry?.consumed_at),
  }));
};

const deleteFoodEntry = async (hass, { foodEntryId }) =>
  callBrizelServiceWithResponse(hass, "delete_food_entry", {
    food_entry_id: foodEntryId,
  });

const lookupExternalFoodByBarcode = async (
  hass,
  { barcode, sourceName = null } = {}
) => {
  const payload = {
    barcode,
  };
  if (trimToNull(sourceName)) {
    payload.source_name = trimToNull(sourceName);
  }

  const parsed = await callBrizelServiceWithResponse(
    hass,
    "lookup_external_food_by_barcode",
    payload
  );
  const sourceResults = Array.isArray(parsed.source_results) ? parsed.source_results : [];
  const results = Array.isArray(parsed.results)
    ? parsed.results.map((result) => ({
        ...result,
        source_name: trimToNull(result?.source_name),
      }))
    : [];

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
  {
    sourceName,
    sourceId,
    amount,
    unit = null,
    consumedAt = null,
    mealType = null,
    source = null,
  }
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
  if (trimToNull(mealType)) {
    payload.meal_type = trimToNull(mealType);
  }
  if (trimToNull(source)) {
    payload.source = trimToNull(source);
  }

  return callBrizelServiceWithResponse(hass, "log_external_food_entry", payload);
};

const createFoodEntry = async (
  hass,
  config,
  { foodId, grams, consumedAt = null, mealType = null, source = null }
) => {
  const payload = {
    food_id: foodId,
    grams,
  };
  const configuredProfile = getConfiguredProfile(config);
  if (configuredProfile) {
    payload.profile_id = configuredProfile;
  }
  if (trimToNull(consumedAt)) {
    payload.consumed_at = trimToNull(consumedAt);
  }
  if (trimToNull(mealType)) {
    payload.meal_type = trimToNull(mealType);
  }
  if (trimToNull(source)) {
    payload.source = trimToNull(source);
  }

  return callBrizelServiceWithResponse(hass, "create_food_entry", payload);
};

const addWater = async (
  hass,
  { profileId, amountMl = 250, consumedAt = null }
) => {
  const payload = {
    profile_id: profileId,
    amount_ml: amountMl,
  };
  if (trimToNull(consumedAt)) {
    payload.consumed_at = trimToNull(consumedAt);
  }
  return callBrizelServiceWithResponse(hass, "add_water", payload);
};

const removeWater = async (hass, { profileId, amountMl = 250 }) =>
  callBrizelServiceWithResponse(hass, "remove_water", {
    profile_id: profileId,
    amount_ml: amountMl,
  });

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
    addBodyMeasurement,
    addWater,
    removeWater,
    buildProfileRequestKey,
    callBrizelServiceWithResponse,
    clamp,
    createFoodEntry,
    createTranslator,
    deleteFoodEntry,
    detectAutoLanguage,
    emitProfileRefresh,
    escapeHtml,
    formatDate,
    formatMl,
    formatNumber,
    formatTime,
    formatValue,
    getActivityLevelOptions,
    getBodyGoal,
    getBodyMeasurementHistory,
    getBodyMeasurementSourceLabel,
    getBodyMeasurementTypeLabel,
    getBodyMeasurementTypeOptions,
    getBodyMeasurementTypes,
    getBodyProfile,
    getBodyProgressSummary,
    getBodyTargets,
    getBodyTrends,
    deleteBodyMeasurement,
    getEntrySourceLabel,
    getExternalFoodDetail,
    getFood,
    getFoodEntriesForProfileDate,
    getMealTypeLabel,
    getMealTypeOptions,
    getProfile,
    getProfiles,
    getPreferredLanguageOptions,
    getPreferredRegionOptions,
    getPreferredUnitsOptions,
    getSexOptions,
    getRecentFoods,
    getConfiguredProfile,
    getCurrentHaUserId,
    getHydrationDataFromEntities,
    getMacroConfig,
    getMacroDataFromEntity,
    getMacroDataFromOverview,
    getReadableErrorMessage,
    getStatusMeta,
    lookupExternalFoodByBarcode,
    loadDailyHydrationReport,
    loadDailyOverview,
    logExternalFoodEntry,
    matchesProfileRefresh,
    normalizeServiceError,
    readEntity,
    resolveEffectiveUiLanguage,
    searchExternalFoods,
    setBodyGoal,
    translateText,
    titleize,
    toNumber,
    trimToNull,
    updateBodyMeasurement,
    updateBodyProfile,
    updateProfile,
  });

export { BrizelCardUtils };
