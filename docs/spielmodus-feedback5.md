# Spielmodus – Feedback 5 (verbindlich)

Deutsch mit Umlauten, nie ß. Flaschen, CHF pro Flasche.

## A. Spiel darf nie verloren gehen (Backend, controller.py + server.py)
- Nach jedem erfolgreichen new_game, end_round, skip_year, load und vor reset schreibt der Controller den
  Spielstand (gleiches Format wie save()) nach `save_dir/automatisch.json`; die vorherige Datei wird zu
  `automatisch_vorher.json`. Label wie bei save(). Bei Spielende (game_over) bleibt die letzte Sicherung liegen.
- `reset()` sichert vorher zusätzlich nach `vor_neuem_spiel.json`.
- server.main: Existiert `automatisch.json`, lädt der Server sie beim Start automatisch (im Hintergrund-Thread
  nach dem Start, damit der Server sofort antwortet; bis dahin liefert /api/game {"running": false,
  "loading": true}).
- state() enthält `autosaved_at` (ISO-Zeit der letzten Sicherung).

## B. Bis zum Ende simulieren
- `POST /api/run_to_end` {settings, choices, orders}: Eingaben übernehmen, dann endet das Spiel wie beim
  Spielzeit-Ende (Grund "ende", Spielerfirma läuft mit Autopilot weiter), Rest bis Jahr 50 im Hintergrund,
  danach Dashboard (bestehender Mechanismus dashboard_status/url). Antwort = state.
- end_reason_text für diesen Fall: «Du hast bis zum Ende simuliert.»

## C. Fehler sichtbar
- Jede Aktion ohne aktives Spiel liefert {"error": "Kein Spiel aktiv – Seite neu laden"}; das Cockpit zeigt
  jede error-Antwort deutlich an und lädt den Zustand neu (erscheint dann die Gründung, ist klar warum).

## D. Verkaufspreis pro Marke (nur Spielerfirma)
- Neues Feld `PlayerChoices.brand_prices: {brand_id: chf_pro_flasche}`.
- brands.py: Für die Spielerfirma ist der Ladenpreis einer Marke = brand_prices[brand], sonst wie bisher.
  Kunden reagieren darauf wie auf jeden Ladenpreis. Normale Firmen unverändert, keine neuen Zufallsziehungen.
- Ansicht purchasing (Händler) je Marke zusätzlich `sell_price` (aktueller Ladenpreis bei dir) und
  `rival_price` (Durchschnitt Ladenpreis der Konkurrenz für diese Marke).

## E. Lastwagen gegen Kurier rechnen
- trucks-Ansicht je Angebot zusätzlich `courier_cost_year` (heutige Kurier-/Postkosten der Firma pro Jahr,
  hochgerechnet), `own_cost_year` (Betrieb + Abschreibung + Fahrer), `saving_year` (= courier − own,
  kann negativ sein); payback/advice berücksichtigen die Ersparnis.

## F–I. Kleinere Punkte (Backend)
- F: kpis.recent_demand / capacity-Ansicht / bottleneck: Nachfrage nie kleiner als der tatsächliche Absatz
  anzeigen (Nachfrage = max(gemessene Nachfrage, Absatz + verpasste Verkäufe)); Engpass-Logik danach.
- G: Meldung, wenn die Bruttomarge drei Monate in Folge sinkt oder unter 15 % fällt (mit Zahlen und Rat).
- H: Änderungsprotokoll (change_log.describe_changes) zeigt dict-Entscheide lesbar, z.B.
  «Einkaufsplan geändert: Alpen Gold 40'000 → 30'000, …» (höchstens 5 Einträge, dann «und N weitere»).
- I: Börsengang: Standard heisst «Nein (Standard)», Erklärung wann er ausgeführt wird (Jahreswechsel) und
  was er bringt/kostet.
