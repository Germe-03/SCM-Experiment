# Spielmodus Phase 4: Übernahmen, Holding und CEOs

Regeln (vom Nutzer): Kauft der Spieler eine Firma, gehört sie seiner Holding. Selbst führen darf er nur die gegründete Firma. Jede Tochter braucht einen CEO aus 20 Avataren. Avatare sind ab 25 wählbar und gehen mit 65 in Pension. Ohne CEO läuft die Tochter vorsichtig auf Autopilot, und jede Runde kommt eine Mahnung. Ein CEO führt nur eine Firma.

## market_sim/game/ceos.py (reine Logik, keine Simulation importieren)
```python
@dataclass(frozen=True)
class Avatar:
    nr: int                 # 1..20
    name: str
    sex: str                # "w" | "m"
    birth_month: int; birth_day: int     # Geburtstag
    appear_year: int        # Spieljahr, in dem der Avatar auftaucht (0 = Start)
    appear_age: int         # Alter beim Auftauchen (am Spielstart bzw. Jahresbeginn von appear_year)
    style: str              # "vorsichtig" | "wachstum" | "sparsam" | "marketing"
    salary: float           # CHF pro Jahr

AVATARS: list[Avatar]       # genau die 20 aus docs/avatar-prompts.md (Namen, Geburtstage, Auftauchjahr, Alter, Stil)
STYLE_TENDENCY = {"vorsichtig": "reliable", "wachstum": "growth", "sparsam": "low_cost", "marketing": "premium"}
STYLE_LABEL = {"vorsichtig": "Vorsichtig", "wachstum": "Auf Wachstum aus", "sparsam": "Sparsam", "marketing": "Auf Marketing aus"}
CAUTIOUS_TENDENCY = "reliable"   # Tochter ohne CEO
RETIRE_AGE = 65; MIN_AGE = 25

def age(avatar, year: int, day_of_year: int, days_per_year: int) -> int
    # Spieljahr year (1-basiert wie RoundSnapshot.year; Spieljahr 1 = erstes Jahr = "Spieljahr 0" im Dokument).
    # Geburtsjahr = appear_year - appear_age (Dokument-Jahre, 0-basiert). Tag im Jahr des Geburtstags = round((birth_month-1)*days_per_year/12 + (birth_day-1)*days_per_year/365).
def visible(avatar, year, day, dpy) -> bool         # aufgetaucht (year-1 >= appear_year)
def available(avatar, year, day, dpy) -> bool       # visible und MIN_AGE <= age < RETIRE_AGE
def stage(avatar, year, day, dpy) -> str            # "jung" (<40) | "mittel" (<55) | "alt"
def image_name(avatar, year, day, dpy) -> str       # f"ceo_{nr:02d}_{stage}.png"

class CeoBook:
    def __init__(self): self.assignments: dict[str, int] = {}   # firm_id -> avatar nr
    def ceo_of(self, firm_id) -> Avatar | None
    def firm_of(self, nr) -> str | None
    def hire(self, firm_id, nr, year, day, dpy) -> None   # ValueError, wenn nicht available oder schon CEO anderswo; ersetzt bisherigen CEO
    def fire(self, firm_id) -> Avatar | None
    def retire_due(self, year, day, dpy) -> list[tuple[str, Avatar]]   # entfernt alle CEOs mit age >= 65, gibt (firm_id, avatar) zurück
    def roster(self, year, day, dpy) -> list[dict]  # alle sichtbaren Avatare: {nr,name,sex,age,style,style_label,salary,image,available,firm}
```
Löhne: zwischen 240'000 und 480'000 CHF/Jahr, älter und Stil «wachstum» teurer; feste Werte in AVATARS.

## market_sim/game/holding_player.py
```python
def firm_value(runner, state, firm_id) -> float
    # runner.holdings.value(...) falls vorhanden, sonst max(0, cash); mal (1 + holdings.control_premium falls vorhanden sonst 0.2)
def buy_targets(runner, state, player_id) -> list[dict]
    # aktive Firmen der Stufen retailer/wholesaler/distributor/factory (keine Händler/Banken/Kuriere), nicht der Spieler,
    # nicht schon in einer Holding (runner.holding_groups.sub_of); category_allows_buy(player.category, target.category) beachten.
    # {"id","name","branch","region","category","price","revenue","profit"} (Umsatz/Gewinn aus dem letzten Jahresabschluss, öffentlich)
def buy(runner, state, player_id, target_id, year, day) -> dict
    # runner.holding_groups.acquire(runner, state, player_firm, target, price, year, day); {"ok": bool, "price", "message"}
    # Fehler (nicht kaufbar, zu wenig Geld) -> {"ok": False, "message": "..."} (deutsch)
def daughters(runner, player_id) -> list[str]    # Töchter der Spieler-Holding ohne die Spielerfirma
def sell_daughter(runner, state, player_id, firm_id, year, day) -> dict
    # Tochter verlässt die Holding (aus group.subs und sub_of entfernen), wird eigenständig; Erlös = firm_value ohne Prämie,
    # geht an die Spielerfirma (runtime.adjust_cash). Ereignis "holding_sold". CEO bleibt bei der Firma (Controller entfernt ihn aus dem CeoBook).
def holding_info(runner, state, player_id) -> dict | None
    # {"id","name","cash","daughters":[{"id","name","branch","cash","revenue","profit","tendency"}]} oder None
```

## Session/Controller (market_sim/game/session.py, controller.py, saves.py, server.py)
- Neuer Rundenteil `orders` (dict, alles optional), ausgeführt am Halt vor dem Weiterrechnen, in dieser Reihenfolge:
  `{"buy": target_id, "sell": daughter_id, "hire": {daughter_id: avatar_nr}, "fire": [daughter_id], "guidelines": {daughter_id: {"payout_ratio": 0..1|None, "auto_invest": bool|None}}}`
- Session hält `ceo_book: CeoBook`. Bei jedem Halt:
  - Pensionierungen (retire_due) -> Meldung (eigen, wichtig) «<Name> geht in Pension. <Firma> braucht einen neuen CEO.»
  - Tochter ohne CEO: `firm.tendency = CAUTIOUS_TENDENCY`, Mahnung jede Runde (eigen, wichtig).
  - Tochter mit CEO: `firm.tendency = STYLE_TENDENCY[style]`; CEO-Lohn anteilig abziehen: `salary * days_since_last_halt / days_per_year` von der Tochter (runtime.adjust_cash(-x, "ceo_lohn")).
  - Leitplanken: Töchter bekommen einen Eintrag in runner.player_choices (nur payout_ratio/auto_invest gesetzt, offences leer).
- Nach Kauf: neue Tochter ohne CEO. Nach Verkauf einer Tochter: CEO frei, player_choices-Eintrag weg.
- Wird die eigene Firma verkauft (sell_firm), gehen Holding und Töchter mit; ceo_book bleibt fürs Ende unverändert.
- Controller `end_round(settings, choices=None, orders=None)`, Server `/api/round` nimmt `{settings, choices, orders}`. Spielstände speichern orders je Runde (alte Stände ohne orders laden weiter).
- State-JSON neu: `"holding": holding_info | null`, `"targets": buy_targets` (höchstens 30, nach Preis), `"ceos": roster`, `"ceo_of": {firm_id: avatar_nr}`, `"order_results": [ {"ok","message"} ]` (Ergebnisse der letzten Aufträge).

## Oberfläche (market_sim/game/static/)
Neuer Reiter/Bereich «Holding» neben den Entscheiden:
- **Firmen kaufen:** Tabelle der kaufbaren Firmen (Name, Branche, Region, Umsatz, Gewinn, Preis) mit Knopf «Kaufen» (Bestätigung, wird mit der Runde geschickt, als «geplant» angezeigt).
- **Töchter:** je Tochter eine Karte: Kennzahlen, CEO mit Bild (`avatare/<image>`, Fallback: Kreis mit Initialen), Stil, Alter, Lohn; Knöpfe «CEO wählen» (Auswahl nur verfügbare, freie Avatare mit Bild, Stil, Alter, Lohn), «Entlassen», «Tochter verkaufen» (Bestätigung); Leitplanken: Gewinnabgabe an Holding (%), automatischer Ausbau an/aus.
- Tochter ohne CEO deutlich markieren («Kein CEO – läuft vorsichtig auf Autopilot»).
- Bilder liegen später in `market_sim/game/static/avatare/` (Ordner mit .gitkeep anlegen).
