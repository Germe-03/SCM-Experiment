# Spielmodus Phase 1: Schnittstelle

Package `market_sim/game/` (`__init__.py` exportiert PlayerSettings, PlayerPolicy, GameSession, RoundSnapshot, SaleResult, BRANCHES).

## Haltepunkt (schon eingebaut)
`SimulationRunner.day_hook: Callable[[runner, state, year, day], None] | None` wird zu Beginn jedes Tages in `run_year` aufgerufen (year ist 1-basiert, day 0-basiert im Jahr), bevor die Firmen entscheiden.

## market_sim/game/player.py
```python
@dataclass
class PlayerSettings:
    base_price: float                  # Verkaufspreis pro Einheit
    target_safety_stock_days: int = 7  # Lagerziel in Tagen Nachfrage (für automatische Bestellmenge)
    order_qty: int | None = None       # feste Bestell-/Produktionsmenge pro Tag; None = automatisch
    overtime_level: float = 0.2        # 0..1
    wage_level: float = 1.0            # wirkt ab nächstem Jahresbeginn
    r_and_d_budget: float = 0.0        # wirkt ab nächstem Jahresbeginn
    target_quality: float = 0.72       # 0..1, ab nächstem Jahresbeginn
    hiring_plan: int = 0               # ab nächstem Jahresbeginn
    supplier_priority: str = "reliability"  # price|reliability|quality|capacity
    positioning: str = "standard"
    risk_tolerance: float = 0.5

    @classmethod
    def from_strategy(cls, strategy: AnnualStrategy) -> "PlayerSettings": ...  # übernimmt alle gleichnamigen Felder, order_qty=None

class PlayerPolicy(FirmPolicy):
    def __init__(self, settings: PlayerSettings): self.settings = settings
    def decide_annual(self, firm, last_summary, config, rival_price=None) -> AnnualStrategy
        # Preisband = ganzes Stufenband: min_price=config.stage_prices[firm.stage].min, max_price=...max,
        # base_price = settings.base_price auf das Band begrenzt; übrige Felder aus settings.
        # Ergebnis .validate_for_config(config) muss bestehen (falls stage-Band ausserhalb config.price liegt: auf config.price.min/max begrenzen).
    def decide_daily(self, firm, obs, strategy, config) -> DailyDecision
        # sell_price = strategy.clamp_price(settings.base_price)  (kein automatisches Nudging)
        # order_qty = settings.order_qty, falls gesetzt; sonst Base-Stock wie FirmPolicy.decide_daily
        #   (target = settings.target_safety_stock_days * max(1, obs.recent_demand); position = inventory + on_order - backlog; Deckel max_order_demand_multiple)
        # overtime_level = settings.overtime_level
```

## market_sim/game/session.py
```python
BRANCHES = {  # Spielbare Branchen -> (stage, channel)
    "hersteller": ("factory", None), "grosshaendler": ("wholesaler", None),
    "verteiler": ("distributor", None), "detailhaendler": ("retailer", "store"),
    "gastro": ("retailer", "restaurant"),
}

@dataclass
class RoundSnapshot:
    year: int; month: int            # month 1..12 (aus day // days_per_month + 1)
    firm_id: str; name: str
    cash: float; inventory: int; backlog: int; employees: int
    sell_price: float; profit: float     # runtime.profit (kumuliert)
    recent_demand: float; recent_sales: float
    rival_price: float | None            # Durchschnittspreis der anderen aktiven Firmen derselben Stufe
    events: list[dict]                   # neue state.events seit dem letzten Halt
    settings: PlayerSettings             # aktuelle Einstellungen
    game_over: bool = False
    reason: str | None = None            # "konkurs" | "verkauft" | "ende"

@dataclass
class SaleResult:
    year: int; month: int; price: float; firm_id: str

class GameSession:
    def __init__(self, seed: int = 0, years: int | None = None, days_per_year: int | None = None, config=None)
        # runner, _ = build_runner(years, seed, days_per_year, config)
    def found(self, branch: str, name: str, region: str | None = None, category: str | None = None) -> str
        # nur vor start(); ValueError bei unbekannter Branche/Region/Kategorie oder Kategorie ausserhalb Hersteller.
        # Merkt sich die Wahl; die Firma wird in start() angelegt.
    def start(self) -> RoundSnapshot
        # state = runner.start(); Firma anlegen wie runner._enter_market (Vorlage = mittlere Firma der Stufe nach Kasse,
        # bei Gastro/Detailhandel nach channel gefiltert, bei Hersteller nach category); id f"{stage}_p01";
        # cash = market_entry.start_cash_fraction * runner._entry_cash[stage]; capacity/machines/employees * start_capacity_fraction;
        # reputation = Mittel von start_reputation; quality * start_quality_fraction; inventory/backlog 0; suppliers [];
        # region = gewählte Region oder Vorlage; extra_regions []; transport_mode wie in _enter_market.
        # runner.add_firm(firm, state, policy=PlayerPolicy(settings)); runner._entry_year[id] = 0; Wein-Startkapital wie _enter_market.
        # settings = PlayerSettings.from_strategy(FirmPolicy().decide_annual(firm, None, config)).
        # Simulation in einem Hintergrund-Thread (runner.continue_run(state, runner.config.simulation.years));
        # day_hook hält bei day % workforce.days_per_month == 0, liefert Snapshot über Queue und wartet auf Befehl.
        # Gibt den ersten Snapshot zurück (Jahr 1, Monat 1).
    def end_round(self, settings: PlayerSettings | None = None) -> RoundSnapshot
        # neue Einstellungen übernehmen (policy.settings ersetzen; wage_level sofort auch auf firm.wage_level? nein: erst Jahresbeginn),
        # bis zum nächsten Halt rechnen. Endet die Simulation: Snapshot mit game_over=True, reason="ende".
        # Ist die Spielerfirma nicht mehr aktiv (runtime.active False): Snapshot game_over=True, reason="konkurs", danach ohne Halt fertig rechnen.
    def sell_firm(self) -> SaleResult
        # nur während Halt. Preis = runner.holdings.market_value(runner, state, id) falls runner.holdings, sonst max(0, cash).
        # Policy der Firma durch policy_for_firm(firm) ersetzen, day_hook entfernen, Ereignis
        # {"year","day","firm","event":"player_sale","details":...} anhängen, Simulation ohne Halt zu Ende rechnen (blockierend).
    result: RunResult | None   # nach Ende gesetzt
    finished: bool
    # Fehler im Thread werden im Hauptthread erneut ausgelöst.
```
