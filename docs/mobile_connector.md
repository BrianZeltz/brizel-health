# Mobile Home Assistant Connector

Stand: 2026-04-18

Diese Dokumentation beschreibt den aktuellen kostenlosen Mobile-Connector-Pfad zwischen der Brizel Health Mobile App und dem Home-Assistant-Host.

## Zweck

Der kostenlose Mobile Connector ist ein schmaler Verbindungspfad:

1. Die Mobile App meldet sich per Home-Assistant-OAuth am lokalen HA-Host an.
2. Die App nutzt die Brizel Health App Bridge mit dem Home-Assistant-Access-Token.
3. Die App liest auf Android Schritte aus Health Connect.
4. Der Home-Assistant-Host importiert diese Schritte in das serverseitig erlaubte Brizel-Health-Profil.

Dieser Pfad ist nicht das spaetere Premium- oder Full-App-Host-Modell. Er baut keine lokale Brizel-Core-Engine in der App, keine lokale Vollnormalisierung und keine lokale Gesundheitsdaten-Persistenz in der App.

## OAuth und HA Login

Die Mobile App verwendet den normalen Home-Assistant-Login:

- Nutzer gibt die Home-Assistant-URL in der App ein.
- Die App startet den Home-Assistant-OAuth-Flow im Browser.
- Home Assistant authentifiziert den Nutzer.
- Die App empfaengt den Callback-Code automatisch.
- Die App tauscht den Code gegen eine Home-Assistant-Session.
- App-Bridge-Aufrufe nutzen danach das Home-Assistant-Access-Token als Bearer Token.

Die Bridge-Endpunkte sind als Home-Assistant-HTTP-Views mit `requires_auth = True` registriert. Der authentifizierte Home-Assistant-User kommt aus dem Request-Kontext.

## App Bridge v1

Basisroute:

```text
/api/brizel_health/app_bridge
```

Aktuelle Endpunkte:

- `GET /ping`
- `GET /capabilities`
- `GET /profiles`
- `GET /sync_status`
- `POST /steps`

`ping` und `capabilities` beschreiben die Bridge selbst. Profilbezogene Endpunkte werden serverseitig an den authentifizierten Home-Assistant-User gebunden.

## Serverseitige Profilbindung

Jedes Brizel-Health-Profil kann optional eine Home-Assistant-User-ID in `linked_ha_user_id` tragen. Diese Zuordnung wird im Home-Assistant-Options-Flow verwaltet.

Die App Bridge erzwingt fuer profilbezogene Routen:

- Der Request muss einen authentifizierten Home-Assistant-User-Kontext haben.
- Genau ein Brizel-Health-Profil muss mit diesem HA-User verlinkt sein.
- Wenn kein Profil verlinkt ist, wird der Request abgelehnt.
- Wenn mehrere Profile mit demselben HA-User verlinkt sind, wird der Request abgelehnt.
- Ein Client kann nicht durch eine andere `profile_id` in fremde Profile schreiben.

Diese Pruefung passiert serverseitig in der App Bridge. UI-Filtering in der Mobile App ist nur zusaetzliche Ergonomie und kein Sicherheitsmodell.

### Fehlercodes

Die Bridge nutzt strukturierte Fehlerantworten mit `ok: false`, `error_code`, `message`, `field_errors` und `correlation_id`.

Profilbindungsrelevante Fehler:

- `AUTH_FAILED`: kein verwendbarer authentifizierter HA-User-Kontext
- `PROFILE_NOT_LINKED`: der HA-User ist keinem Brizel-Profil zugeordnet
- `PROFILE_LINK_AMBIGUOUS`: der HA-User ist mehreren Brizel-Profilen zugeordnet
- `PROFILE_ACCESS_DENIED`: der Client wollte ein anderes Profil nutzen als das verlinkte Profil

## Multi-User-Household-Verhalten

In einem Haushalt mit mehreren Home-Assistant-Nutzern gilt:

- Jedes Brizel-Profil kann mit einem HA-User verlinkt werden.
- Ein HA-User darf fuer den Mobile-Connector genau ein verlinktes Brizel-Profil haben.
- `GET /profiles` gibt fuer die mobile Session nur dieses eine erlaubte Profil zurueck.
- `GET /sync_status` gibt nur den Sync-Status dieses Profils zurueck.
- `POST /steps` importiert nur in dieses Profil.

Andere Profile im Haushalt bleiben fuer diese mobile Session unsichtbar und nicht beschreibbar.

## Schritte Upload: Android App zu HA zu Profil

Der aktuelle echte Health-Daten-Pfad ist Android-Schritte:

1. Die Android-App prueft Health-Connect-Verfuegbarkeit.
2. Die Android-App prueft oder beantragt die Step-Leseberechtigung.
3. Die Android-App liest die heutigen Schritte aus Health Connect.
4. Die App sendet einen App-Bridge-v1-Request an `POST /steps`.
5. Die Bridge validiert das Request-Schema.
6. Die Bridge ermittelt das serverseitig verlinkte Profil aus dem HA-User-Kontext.
7. Falls der Client eine `profile_id` sendet, muss sie zu diesem Profil passen.
8. Die Bridge importiert die Schritte in FIT fuer dieses Profil.
9. Profile-scoped Sensoren und Sync-Status koennen danach aktualisiert werden.

Der Client darf `profile_id` nicht als Autorisierung verwenden. Die serverseitige HA-User-zu-Profil-Bindung ist die massgebliche Autorisierung.

## Sicherheitsmodell

Der kostenlose Connector verlaesst sich auf:

- Home-Assistant-Authentifizierung fuer den HTTP-Request
- serverseitige Zuordnung `HA user -> Brizel profile`
- profilgebundene Bridge-Antworten und Imports
- keine Ausgabe fremder Profile in `/profiles`
- keine Imports in fremde Profile ueber Client-Payloads
- Security-Logs ohne Tokens, Namen oder Gesundheitsdaten

Nicht Teil dieses Sicherheitsmodells:

- Mobile-App-Dropdown-Filtering als alleinige Kontrolle
- manuell eingefuegte Long-Lived Access Tokens als Produktweg
- lokale App-Datenbank als zentrale Wahrheit
- Cloud-Sync als zentrale Wahrheit

## Bekannte Grenzen und Next Steps

Aktuelle Grenzen:

- Die Profilbindung haengt an `linked_ha_user_id` in den Brizel-Profilen.
- Korrupte Storage-Zustaende mit mehrfacher Link-Zuordnung werden erkannt und abgelehnt, aber nicht automatisch repariert.
- Die Mobile App nutzt aktuell nur Android Health Connect Schritte.
- Kein Retry-/Offline-System im kostenlosen Connector-Pfad.

Sinnvolle naechste Schritte:

1. Optionen-Flow weiterhin als zentrale Stelle fuer HA-User/Profile-Linking pflegen.
2. Admin-Hinweise fuer `PROFILE_NOT_LINKED` und `PROFILE_LINK_AMBIGUOUS` in UI oder Doku verbessern.
3. Mobile-App-DTOs nur noch als Anzeige des serverseitig erlaubten Profils behandeln.
4. Weitere Health-Daten erst spaeter und weiterhin profilgebunden anbinden.
