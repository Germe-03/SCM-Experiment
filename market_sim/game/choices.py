"""Player choices that override the automatic decisions of the subsystems (Spielmodus Phase 3).

Every field set to ``None`` means "Autopilot": the subsystem decides as for any other firm.
Subsystems read the choices with ``choices_for(runner, firm_id)`` and must treat a missing
entry exactly like today's behaviour. One-time orders (``*_order``) are cleared by the
subsystem once executed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


@dataclass
class PlayerChoices:
    # Marketing: yearly budget in CHF (real money, before price index). None = autopilot.
    marketing_budget: float | None = None
    # Research: name of the next stage to research; "" = no research at all. None = autopilot.
    research_target: str | None = None
    # Money: "auto" (autopilot), "never" (pay from cash only), "prefer" (take a loan whenever offered).
    # Feedback 2: the player never gets a loan without asking, so the default is "never".
    credit_mode: str = "never"
    # Preferred bank id for new loans and the main account. None = autopilot.
    bank_id: str | None = None
    # Share of the free profit paid out as dividend (0..1). None = autopilot.
    payout_ratio: float | None = None
    # Stock exchange: True = go public as soon as allowed, False = never, None = autopilot.
    listing: bool | None = None
    # Transport: "own" (own trucks) or "service" (post/courier). None = autopilot.
    transport_mode: str | None = None
    # Growth: False = no automatic expansion or new sites; None = autopilot.
    auto_invest: bool | None = None
    # One-time orders, executed at the next possible point and then reset to None.
    expand_order: int | None = None          # extra capacity units
    site_order: str | None = None            # region name for a new site (retailers)
    # Raw materials: courage 0..1 for buying ahead (0 = only what is needed). None = autopilot.
    commodity_courage: float | None = None
    # Restaurants: markup factor relative to the standard markup (e.g. 1.1 = 10 % dearer). None = autopilot.
    markup_factor: float | None = None
    # Offences the player commits deliberately (names from config.state.offences). Player firms
    # never commit offences on their own. A list means full intensity; a dict maps name -> 0..1.
    offences: list[str] | dict = field(default_factory=list)
    # Marketing (Cockpit 2): share of the budget for the brand (rest for stores/restaurants), 0..1,
    # and an age group to focus on ("18-34", "35-64", "65+"). None = as before.
    marketing_focus: float | None = None
    marketing_target: str | None = None
    # Suppliers: a fixed supplier firm id, or a rule "price" | "quality" | "reliability" | "lead_time".
    supplier_id: str | None = None
    supplier_rule: str | None = None
    # Suppliers (Feedback 1): split of the order between suppliers, firm id -> share (any positive
    # numbers, normalised). Unknown or inactive ids are ignored. Wins over supplier_id/supplier_rule.
    supplier_shares: dict | None = None
    # Replaces the hidden "Risikobereitschaft" (Feedback 1): couriers "cheap" | "reliable",
    # patent suits True/False. None = neutral middle (as risk 0.5).
    courier_preference: str | None = None
    patent_lawsuits: bool | None = None
    # Feedback 2: assortment of trading firms, category -> share (beer, wine, spirits, softdrinks,
    # water; any positive numbers, normalised). None = as the market buys.
    category_shares: dict | None = None
    # Feedback 3 – producers: daily raw-material purchase per component (name -> amount per day in the
    # component's own unit, as config amounts per sim unit × units). None = automatic buying as before.
    component_plan: dict | None = None
    # Feedback 3 – traders: daily purchase per brand (brand id -> bottles per day). Wins over
    # category_shares. None = as before.
    brand_plan: dict | None = None
    # Feedback 3 – storage: one-time order to add storage places (bottles); reset after execution.
    storage_order: int | None = None
    # Feedback 3 – cancel all open (ordered, not yet delivered) orders once; reset after execution.
    cancel_open_orders: bool | None = None
    # Feedback 3 – rules for daughters run by a CEO: firm id -> {"no_credit": bool, "no_stakes": bool}.
    daughter_rules: dict | None = None
    # Feedback 4 – traders: fixed wholesaler per brand (brand id -> supplier firm id); missing = automatic.
    # The controller turns it into supplier_shares before each round.
    brand_suppliers: dict | None = None

    def offence_intensity(self, name: str) -> float:
        """Intensity 0..1 of an offence the player chose (0 = not committed)."""
        if isinstance(self.offences, dict):
            return max(0.0, min(1.0, float(self.offences.get(name, 0.0) or 0.0)))
        return 1.0 if name in (self.offences or []) else 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def update(self, values: dict) -> None:
        """Merge known keys from ``values``; unknown keys raise ValueError."""
        names = {f.name for f in fields(self)}
        unknown = set(values) - names
        if unknown:
            raise ValueError(f"Unbekannte Entscheide: {', '.join(sorted(unknown))}")
        for key, value in values.items():
            setattr(self, key, value)


def choices_for(runner, firm_id: str) -> PlayerChoices | None:
    """The player's choices for ``firm_id``, or None for a normal firm."""
    return getattr(runner, "player_choices", {}).get(firm_id)
