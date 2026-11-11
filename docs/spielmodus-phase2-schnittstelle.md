# Spielmodus Phase 2: Schnittstelle

Ziel: Cockpit im Browser, Meldungen, Spielstände. Eigener Spielserver, getrennt vom Beobachter-Dashboard (`serve.py` bleibt unverändert).
Alle Texte für den Spieler auf Deutsch mit ä/ö/ü, nie ß (immer ss). Einfache Alltagssprache.

## market_sim/game/messages.py
```python
def message_for(event: dict, player_id: str, names: dict[str, str]) -> dict | None
def messages_for(events: list[dict], player_id: str, names: dict[str, str]) -> list[dict]
```
- `event` hat die Schlüssel `year`, `day`, `firm`, `event`, `details` (wie `state.events`).
- Ergebnis: `{"year": int, "day": int, "text": str, "kind": "eigen" | "markt", "important": bool}`.
  `kind="eigen"`, wenn `event["firm"] == player_id`, sonst `"markt"`.
- Ein kurzer deutscher Satz je Ereignistyp, Firmenname aus `names` (Fallback: id). Bekannte Typen u.a.: market_entry, bankruptcy, takeover, takeover_blocked, merger_formed, merger_blocked, law_enacted, recession, inflation, policy_rate_emergency, price_increase, poisoning, offence_detected, listed, delisted, exchange_opened, patent_granted, patent_expired, rnd_success, rnd_implemented, loan_granted, credit_rejected, capacity_limit, supplier_switch, transport_switch, trend_change, holding_takeover, holding_sold, stake_bought, stake_sold, player_sale, strategy_change. Unbekannte Typen: `"<Name>: <details>"`.
- `important=True` für: alles Eigene ausser rnd_started; bei Markt: law_enacted, recession, inflation, policy_rate_emergency, bankruptcy, takeover, merger_formed, poisoning.
- Nicht öffentliche Dinge anderer Firmen weglassen (`None`): rnd_started, rnd_success, rnd_inherited, supplier_switch, strategy_change, credit_rejected, loan_granted, account_opened, bank_switched, holding_cover, holding_no_cover, holding_sweep.

## market_sim/game/saves.py
Spielstand = Wiederholungsprotokoll (die Simulation ist mit gleichem Seed deterministisch; ein Zwischenstand mitten im Jahr lässt sich nicht pickeln).
```python
@dataclass
class SaveGame:
    seed: int
    years: int | None
    days_per_year: int | None
    branch: str
    name: str
    region: str | None
    category: str | None
    rounds: list[dict]        # je beendeter Runde: asdict(PlayerSettings), in Reihenfolge
    saved_at: str = ""        # ISO-Zeit
    label: str = ""           # z.B. "Jahr 3, Monat 5"

def write_save(save: SaveGame, path: Path) -> Path      # JSON, utf-8, Ordner anlegen
def read_save(path: Path) -> SaveGame
def list_saves(directory: Path) -> list[dict]           # [{"name": stem, "label", "saved_at", "firm": name}] neueste zuerst
def replay(save: SaveGame) -> tuple[GameSession, RoundSnapshot]
    # GameSession(seed, years, days_per_year).found(...); start(); für jede Runde end_round(PlayerSettings(**r)); gibt Session und letzten Snapshot zurück
```

## market_sim/game/controller.py
```python
class GameController:
    def __init__(self, save_dir: Path, seed: int = 0, years: int | None = None, days_per_year: int | None = None)
    def options(self) -> dict      # {"branches": [{"key","label"}], "regions": [str], "categories": [str]}
    def new_game(self, branch: str, name: str, region: str | None = None, category: str | None = None) -> dict
    def end_round(self, settings: dict | None = None) -> dict   # settings: Teilmenge der PlayerSettings-Felder, wird mit den aktuellen zusammengeführt
    def sell(self) -> dict
    def save(self, name: str) -> dict          # {"ok": True, "name": ...}; Name auf [A-Za-z0-9_-äöüÄÖÜ ] begrenzen
    def load(self, name: str) -> dict
    def saves(self) -> dict                    # {"saves": list_saves(...)}
    def state(self) -> dict
```
Ein Lock schützt alle Methoden (Server ist mehrfädig). Fehler (ValueError/RuntimeError) als `{"error": text}` zurückgeben, nicht auslösen.

State-JSON (`state()` und Rückgabe von new_game/end_round/sell/load):
```json
{"running": true, "game_over": false, "reason": null,
 "year": 1, "month": 1,
 "firm": {"id": "factory_p01", "name": "Testbräu", "branch": "hersteller"},
 "kpis": {"cash": 0, "inventory": 0, "backlog": 0, "employees": 0, "sell_price": 0, "profit": 0,
          "recent_demand": 0, "recent_sales": 0, "rival_price": null},
 "settings": {"base_price": 0, "target_safety_stock_days": 7, "order_qty": null, "overtime_level": 0.2,
              "wage_level": 1.0, "r_and_d_budget": 0, "target_quality": 0.72, "hiring_plan": 0,
              "supplier_priority": "reliability", "positioning": "standard", "risk_tolerance": 0.5},
 "price_band": {"min": 0, "max": 0},
 "messages": [{"year":1,"day":0,"text":"...","kind":"eigen","important":true}],
 "history": [{"year":1,"month":1,"cash":0,"profit":0,"sell_price":0}],
 "sale": null}
```
Ohne Spiel: `{"running": false}`. `messages`: alle bisherigen, neueste zuerst, höchstens 200. `history`: ein Eintrag pro Halt. `price_band` = `config.stage_prices[stage]`. `sale` nach Verkauf: `{"price", "year", "month"}`.

## market_sim/game/server.py
`python -m market_sim.game.server --port 8771 --saves runs/spielstaende [--seed 0 --years N --days-per-year N]`
Statische Dateien aus `market_sim/game/static/`, `/` liefert `cockpit.html`. JSON-API (utf-8):
- GET `/api/game` → state()
- GET `/api/options` → options()
- GET `/api/saves` → saves()
- POST `/api/new` `{branch, name, region, category}` → new_game
- POST `/api/round` `{settings: {...}}` → end_round
- POST `/api/sell` → sell
- POST `/api/save` `{name}` → save
- POST `/api/load` `{name}` → load
Nur 127.0.0.1. Unbekannter Pfad → 404.

## market_sim/game/static/ (cockpit.html, cockpit.css, cockpit.js)
Ohne externe Bibliotheken. Zwei Ansichten:
1. **Gründung** (wenn running=false): Branche, Name, Region, Kategorie (nur bei Hersteller sichtbar), Knopf «Firma gründen»; Liste der Spielstände mit «Laden».
2. **Cockpit**: Kopfzeile mit Firmenname, Branche, «Jahr X, Monat Y». Übersicht (Kasse, Gewinn, Lager, Rückstand, Mitarbeiter, Nachfrage, Verkauf, eigener Preis gegen Konkurrenzpreis), kleiner Kassenverlauf (SVG-Linie aus history).
   Entscheide nach Bereichen in eigenen Karten, was zusammengehört zusammen:
   - **Verkauf:** Preis (Zahl, mit Band als Hinweis)
   - **Einkauf und Produktion:** Lagerziel in Tagen, feste Menge pro Tag (leer = automatisch)
   - **Mitarbeiter:** Überstunden (0–100 %), Lohnniveau, Einstellungen pro Jahr
   - **Produkt:** Zielqualität, Forschungsbudget, Positionierung
   - **Lieferanten:** Priorität (Preis, Zuverlässigkeit, Qualität, Kapazität)
   Felder, die erst ab Jahresbeginn wirken, tragen den Hinweis «wirkt ab nächstem Jahr». Überstunden gehören zu Mitarbeiter und zu Produktion: in beiden Karten anzeigen, dasselbe Feld synchron.
   Meldungen rechts: wichtige hervorgehoben, Filter Alle / Eigene / Markt.
   Knöpfe: «Runde beenden» (schickt geänderte Einstellungen), «Wie bisher weiter» (ohne Änderung), «Speichern» (Name abfragen), «Firma verkaufen» (Bestätigung: Spiel endet).
   Spielende: Hinweis mit Grund (Konkurs, verkauft, Ende) und ggf. Verkaufspreis.
   Zahlen in CHF mit Hochkomma-Tausendern (de-CH). Hell/Dunkel über prefers-color-scheme. Funktioniert auch schmal (Handy).
