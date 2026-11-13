from __future__ import annotations

from copy import deepcopy


__all__ = [
    "snapshot",
    "begin_year",
    "record_year",
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "ratios",
    "annual_report",
    "calculation",
]


_COUNTERS = (
    "revenue",
    "purchase_cost",
    "wage_cost",
    "fixed_cost",
    "marketing_cost",
    "handling_cost",
    "cumulative_holding_cost",
    "cumulative_backlog_cost",
    "hiring_cost",
    "rnd_spend",
    "interest_cost",
    "investment_depreciation",
)


def _number(value, default: float = 0.0) -> float:
    """Return a finite-looking numeric value, or a safe default."""
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _dict(value) -> dict:
    """Return a dictionary value or an empty dictionary."""
    return value if isinstance(value, dict) else {}


def _runtimes(runner) -> dict:
    """Get runtimes without assuming the runner or environment exists."""
    return _dict(getattr(getattr(runner, "env", None), "runtimes", None))


def _unit_cost_cache(runner) -> dict:
    """Get the remembered unit costs, creating the cache when possible."""
    cache = getattr(runner, "_fin_unit_cost", None)
    if isinstance(cache, dict):
        return cache
    try:
        cache = {}
        setattr(runner, "_fin_unit_cost", cache)
        return cache
    except Exception:
        return {}


def _cash_flows(runtime) -> dict[str, float]:
    """Copy cash flows as rounded CHF amounts."""
    flows = _dict(getattr(runtime, "cash_flows", None))
    return {str(key): round(_number(value), 2) for key, value in flows.items()}


def _purchased_units(runtime) -> float:
    """Sum purchased units across the paid-items ledger."""
    items = _dict(getattr(runtime, "paid_items", None))
    total = 0.0
    for item in items.values():
        total += _number(_dict(item).get("units", 0))
    return total


def _truck_value(runner, firm_id: str) -> float:
    """Return the current book or market value of a firm's fleet."""
    env = getattr(runner, "env", None)
    geography = getattr(env, "geography", None)
    trucks = getattr(geography, "trucks", None)
    fleets = _dict(getattr(trucks, "fleets", None))
    fleet = fleets.get(firm_id, [])
    if not isinstance(fleet, (list, tuple)):
        return 0.0

    value_method = getattr(trucks, "value", None)
    total = 0.0
    for truck in fleet:
        value = None
        if callable(value_method):
            try:
                value = value_method(env, truck)
            except Exception:
                value = None
        if value is None:
            value = getattr(truck, "book_value", 0.0)
        total += _number(value)
    return round(total, 2)


def snapshot(runner, only=None) -> dict[str, dict]:
    """Build a detached snapshot of the current firm financials."""
    runtimes = _runtimes(runner)
    cache = _dict(getattr(runner, "_fin_unit_cost", None))
    result = {}

    for firm_id, runtime in runtimes.items():
        if only is not None and firm_id != only:
            continue
        if runtime is None:
            runtime = object()
        values = {
            name: round(_number(getattr(runtime, name, 0.0)), 2)
            for name in _COUNTERS
        }
        purchased_units = _purchased_units(runtime)
        if purchased_units > 0:
            unit_cost = values["purchase_cost"] / purchased_units
        else:
            unit_cost = _number(cache.get(firm_id, 0.0))

        values.update(
            {
                "cash": round(_number(getattr(runtime, "cash", 0.0)), 2),
                "inventory": _number(getattr(runtime, "inventory", 0), 0.0),
                "purchased_units": purchased_units,
                "cash_flows": _cash_flows(runtime),
                "truck_value": _truck_value(runner, firm_id),
                "unit_cost": round(unit_cost, 2),
            }
        )
        result[firm_id] = deepcopy(values)

    return result


def begin_year(runner) -> None:
    """Mark the current financial state as the start of a year."""
    if not isinstance(getattr(runner, "_fin_unit_cost", None), dict):
        try:
            setattr(runner, "_fin_unit_cost", {})
        except Exception:
            pass
    try:
        setattr(runner, "fin_start", snapshot(runner))
    except Exception:
        pass


def _zero_start() -> dict:
    """Return an empty snapshot for a firm without a start-of-year record."""
    result = {name: 0.0 for name in _COUNTERS}
    result.update(
        {
            "cash": 0.0,
            "inventory": 0.0,
            "purchased_units": 0.0,
            "cash_flows": {},
            "truck_value": 0.0,
            "unit_cost": 0.0,
        }
    )
    return result


def _period(runner, firm_id) -> dict:
    """Calculate current-year deltas for a firm."""
    runtimes = _runtimes(runner)
    runtime = runtimes.get(firm_id)
    if runtime is None:
        current = _zero_start()
    else:
        current = snapshot(runner, firm_id).get(firm_id, _zero_start())

    starts = _dict(getattr(runner, "fin_start", None))
    start = _dict(starts.get(firm_id)) or _zero_start()
    result = {
        name: round(_number(current.get(name, 0.0)) - _number(start.get(name, 0.0)), 2)
        for name in _COUNTERS
    }
    result["purchased_units"] = (
        _number(current.get("purchased_units", 0.0))
        - _number(start.get("purchased_units", 0.0))
    )

    current_flows = _dict(current.get("cash_flows"))
    start_flows = _dict(start.get("cash_flows"))
    flow_keys = set(current_flows) | set(start_flows)
    result["cash_flows"] = {
        str(key): round(
            _number(current_flows.get(key, 0.0)) - _number(start_flows.get(key, 0.0)),
            2,
        )
        for key in flow_keys
    }

    for label, key in (
        ("cash_start", "cash"),
        ("inventory_start", "inventory"),
        ("truck_value_start", "truck_value"),
        ("unit_cost_start", "unit_cost"),
    ):
        result[label] = round(_number(start.get(key, 0.0)), 2)
    for label, key in (
        ("cash_end", "cash"),
        ("inventory_end", "inventory"),
        ("truck_value_end", "truck_value"),
    ):
        result[label] = round(_number(current.get(key, 0.0)), 2)

    purchased_units = result["purchased_units"]
    if purchased_units > 0:
        unit_cost_end = result["purchase_cost"] / purchased_units
    else:
        unit_cost_end = result["unit_cost_start"]

    cache = _unit_cost_cache(runner)
    if unit_cost_end <= 0:
        unit_cost_end = _number(cache.get(firm_id, 0.0))
    if unit_cost_end > 0:
        try:
            cache[firm_id] = round(unit_cost_end, 2)
        except Exception:
            pass
    result["unit_cost_end"] = round(unit_cost_end, 2)
    return result


def _year_number(runner, year) -> int:
    """Resolve the displayed year for a current-year report."""
    if year is not None:
        return year
    reports = _dict(getattr(runner, "annual_reports", None))
    return len(reports) + 1 if reports else 1


def _stored_section(runner, firm_id, year, section):
    """Return a detached stored report section, if it exists."""
    if year is None:
        return None
    reports = _dict(getattr(runner, "annual_reports", None))
    report = _dict(_dict(reports.get(year)).get(firm_id))
    stored = report.get(section)
    return deepcopy(stored) if isinstance(stored, dict) else None


def _income(runner, firm_id, year) -> dict:
    """Build an income statement from the current period."""
    period = _period(runner, firm_id)
    revenue = period["revenue"]
    purchases = period["purchase_cost"]
    inventory_value_start = period["inventory_start"] * period["unit_cost_start"]
    inventory_value_end = period["inventory_end"] * period["unit_cost_end"]
    cogs_cap = max(0.0, purchases + inventory_value_start)
    cogs = min(
        cogs_cap,
        max(0.0, purchases + inventory_value_start - inventory_value_end),
    )
    gross_profit = revenue - cogs

    wages = max(0.0, period["wage_cost"])
    marketing = max(0.0, period["marketing_cost"])
    rent_fixed = max(0.0, period["fixed_cost"] - period["marketing_cost"])
    handling = max(0.0, period["handling_cost"])
    storage = period["cumulative_holding_cost"] + period["cumulative_backlog_cost"]
    research = max(0.0, period["rnd_spend"])

    flows = period["cash_flows"]
    fines_and_fees = sum(
        -value
        for key, value in flows.items()
        if key.startswith("staat:Busse") or key == "staat:Patentgebühr"
    )
    other_opex = max(
        0.0,
        period["hiring_cost"]
        + fines_and_fees
        - flows.get("ceo_lohn", 0.0)
        - flows.get("leasing_rate", 0.0),
    )

    ebitda = gross_profit - (
        wages + rent_fixed + handling + storage + marketing + research + other_opex
    )
    depreciation = max(
        0.0,
        period["investment_depreciation"]
        + max(0.0, period["truck_value_start"] - period["truck_value_end"]),
    )
    ebit = ebitda - depreciation
    interest = period["interest_cost"]  # netto: positiv = Zinskosten, negativ = Zinsertrag auf Guthaben
    ebt = ebit - interest
    taxes = max(
        0.0,
        -(
            flows.get("staat:Gewinnsteuer", 0.0)
            + flows.get("staat:Verrechnungssteuer", 0.0)
        ),
    )

    return {
        "year": _year_number(runner, year),
        "revenue": round(revenue, 2),
        "cogs": round(cogs, 2),
        "gross_profit": round(gross_profit, 2),
        "wages": round(wages, 2),
        "rent_fixed": round(rent_fixed, 2),
        "handling": round(handling, 2),
        "storage": round(storage, 2),
        "marketing": round(marketing, 2),
        "research": round(research, 2),
        "other_opex": round(other_opex, 2),
        "ebitda": round(ebitda, 2),
        "depreciation": round(depreciation, 2),
        "ebit": round(ebit, 2),
        "interest": round(interest, 2),
        "ebt": round(ebt, 2),
        "taxes": round(taxes, 2),
        "net_income": round(ebt - taxes, 2),
    }


def income_statement(runner, firm_id, year=None) -> dict:
    """Return a current or stored income statement."""
    stored = _stored_section(runner, firm_id, year, "income_statement")
    if stored is not None:
        return stored
    return _income(runner, firm_id, year)


def _loan_total(runner, firm_id) -> float:
    """Sum outstanding bank loans for a firm."""
    banking = getattr(getattr(runner, "env", None), "banking", None)
    loans = _dict(getattr(banking, "loans", None))
    total = 0.0
    for loan in loans.values():
        if getattr(loan, "firm_id", None) == firm_id:
            total += _number(getattr(loan, "outstanding", 0.0))
    return total


def _site_value(runner, firm_id) -> float:
    """Estimate the book value of additional sites."""
    geography = getattr(getattr(runner, "env", None), "geography", None)
    sites_method = getattr(geography, "sites", None)
    if not callable(sites_method):
        return 0.0
    network = getattr(runner, "network", None)
    firm_method = getattr(network, "firm", None)
    if not callable(firm_method):
        return 0.0
    try:
        sites = sites_method(firm_method(firm_id))
    except Exception:
        return 0.0
    config_geography = getattr(getattr(runner, "config", None), "geography", None)
    book_value = _number(getattr(config_geography, "site_book_value", 0.0))
    try:
        count = len(sites)
    except Exception:
        count = 0
    return round(max(0, count - 1) * book_value, 2)


def _participation_value(runner, firm_id) -> float:
    """Sum recorded purchase prices of a firm's participations."""
    holdings = getattr(runner, "holdings", None)
    paid = _dict(getattr(holdings, "paid", None))
    return round(
        sum(_number(value) for (owner, _target), value in paid.items()
            if owner == firm_id),
        2,
    )


def _securities_value(runner, firm_id) -> float:
    """Get the optional securities valuation."""
    method = getattr(runner, "securities_value", None)
    if not callable(method):
        return 0.0
    try:
        return round(_number(method(firm_id)), 2)
    except Exception:
        return 0.0


def balance_sheet(runner, firm_id) -> dict:
    """Build a current balance sheet, using equity as the balancing item."""
    runtime = _runtimes(runner).get(firm_id)
    if runtime is None:
        cash = 0.0
        inventory_units = 0.0
    else:
        cash = _number(getattr(runtime, "cash", 0.0))
        inventory_units = _number(getattr(runtime, "inventory", 0.0))

    period = _period(runner, firm_id)
    inventory_unit_cost = period["unit_cost_end"]
    if inventory_unit_cost <= 0:
        inventory_unit_cost = _number(_unit_cost_cache(runner).get(firm_id, 0.0))
    if inventory_unit_cost <= 0 and inventory_units > 0:
        # Hersteller ohne Einkaufsmengen: Herstellkosten naeherungsweise 60 % des Verkaufspreises.
        try:
            price = _number(getattr(runner.network.firm(firm_id), "sell_price", 0.0))
            size = _number(runner.config.unit_scale.real_units_per_sim_unit, 1.0)
            inventory_unit_cost = 0.6 * price * size
        except Exception:
            inventory_unit_cost = 0.0

    assets = {
        "cash": round(max(0.0, cash), 2),
        "inventory": round(max(0.0, inventory_units) * max(0.0, inventory_unit_cost), 2),
        "trucks": _truck_value(runner, firm_id),
        "sites": _site_value(runner, firm_id),
        "participations": _participation_value(runner, firm_id),
        "securities": _securities_value(runner, firm_id),
    }
    assets["total"] = round(sum(assets[key] for key in assets), 2)

    loans = round(_loan_total(runner, firm_id), 2)
    overdraft = round(max(0.0, -cash), 2)
    liabilities = {
        "loans": loans,
        "overdraft": overdraft,
        "other": overdraft,
        "total": round(loans + overdraft, 2),
    }
    equity = round(assets["total"] - liabilities["total"], 2)
    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total": round(liabilities["total"] + equity, 2),
    }


def _cash(runner, firm_id, year) -> dict:
    """Build a cash-flow statement from the current period."""
    period = _period(runner, firm_id)
    flows = period["cash_flows"]
    investing_keys = {
        "lastwagen_kauf",
        "lastwagen_verkauf",
        "aktien_kauf",
        "aktien_verkauf",
    }
    investing = sum(
        value
        for key, value in flows.items()
        if key in investing_keys
        or key.startswith(
            (
                "beteiligung:",
                "beteiligung_verkauft:",
                "uebernahme:",
                "kapital_von:",
                "holding_verkauf:",
            )
        )
    )
    financing = flows.get("bank:Investitionskredit", 0.0) + flows.get(
        "bank:Kredit getilgt", 0.0
    )
    dividends_received = sum(
        max(0.0, value)
        for key, value in flows.items()
        if key.startswith("dividende_von:")
    ) + max(0.0, flows.get("dividende:holding", 0.0))
    dividends_paid_delta = flows.get("dividende:aktionaere", 0.0) + sum(
        value for key, value in flows.items() if key.startswith("dividende_an:")
    )
    holding_dividend = flows.get("dividende:holding", 0.0)
    if holding_dividend < 0:
        dividends_paid_delta += holding_dividend
    dividends_paid = max(0.0, -dividends_paid_delta)
    change = period["cash_end"] - period["cash_start"]
    operating = change - investing - financing - dividends_received + dividends_paid

    return {
        "operating": round(operating, 2),
        "investing": round(investing, 2),
        "financing": round(financing, 2),
        "dividends_received": round(dividends_received, 2),
        "dividends_paid": round(dividends_paid, 2),
        "change": round(change, 2),
    }


def cash_flow(runner, firm_id, year=None) -> dict:
    """Return a current or stored cash-flow statement."""
    stored = _stored_section(runner, firm_id, year, "cash_flow")
    if stored is not None:
        return stored
    return _cash(runner, firm_id, year)


def _ratios(income, balance) -> dict:
    """Calculate common financial ratios from statement dictionaries."""
    assets = _dict(balance.get("assets"))
    liabilities = _dict(balance.get("liabilities"))
    revenue = _number(income.get("revenue", 0.0))
    total = _number(balance.get("total", 0.0))
    equity = _number(balance.get("equity", 0.0))
    liability_total = _number(liabilities.get("total", 0.0))
    return {
        "gross_margin": round(
            _number(income.get("gross_profit", 0.0)) / revenue if revenue else 0.0,
            4,
        ),
        "ebit_margin": round(
            _number(income.get("ebit", 0.0)) / revenue if revenue else 0.0,
            4,
        ),
        "equity_ratio": round(equity / total if total > 0 else 0.0, 4),
        "liquidity": round(
            _number(assets.get("cash", 0.0)) / liability_total
            if liability_total else 0.0,
            4,
        ),
        "roe": round(
            _number(income.get("net_income", 0.0)) / equity if equity > 0 else 0.0,
            4,
        ),
    }


def ratios(runner, firm_id, year=None) -> dict:
    """Return financial ratios for the current period or a stored year."""
    income = income_statement(runner, firm_id, year)
    stored_balance = _stored_section(runner, firm_id, year, "balance_sheet")
    balance = stored_balance if stored_balance is not None else balance_sheet(runner, firm_id)
    return _ratios(income, balance)


def _calculation(runner, firm_id) -> dict:
    """Build the current unit-cost calculation in CHF per bottle."""
    period = _period(runner, firm_id)
    config = getattr(runner, "config", None)
    unit_scale = getattr(config, "unit_scale", None)
    unit_size = _number(getattr(unit_scale, "real_units_per_sim_unit", 1.0), 1.0)
    if unit_size <= 0:
        unit_size = 1.0

    network = getattr(runner, "network", None)
    firm_method = getattr(network, "firm", None)
    firm = None
    if callable(firm_method):
        try:
            firm = firm_method(firm_id)
        except Exception:
            firm = None
    # Firm.sell_price is already CHF per bottle; revenue = sim units * price * unit_size.
    sell_price = _number(getattr(firm, "sell_price", 0.0))
    bottles_sold = period["revenue"] / sell_price if sell_price > 0 else 0.0
    sold_units = bottles_sold / unit_size

    unit_cost = period["unit_cost_end"]
    cache = _unit_cost_cache(runner)
    if unit_cost <= 0:
        unit_cost = _number(cache.get(firm_id, 0.0))
    purchases = period["purchase_cost"]
    if unit_cost <= 0 and sold_units > 0:
        unit_cost = purchases / sold_units
    purchase_price = unit_cost / unit_size
    if purchase_price <= 0 and getattr(firm, "stage", None) != "factory":
        # Noch nichts eingekauft (Spielbeginn): Durchschnittspreis der möglichen Lieferanten zeigen.
        try:
            candidates = runner.env.supplier_candidates(firm_id)
            prices = [float(c.sell_price) for c in candidates if getattr(c, "sell_price", 0) > 0]
            if prices:
                purchase_price = sum(prices) / len(prices)
        except Exception:
            pass
    if getattr(firm, "stage", None) == "factory":
        # Hersteller: Herstellkosten pro Flasche (Rohstoffe + Strom) statt Einkauf ÷ Verkauf,
        # sonst zählt ein Rohstoffvorrat als Kosten der verkauften Flaschen.
        try:
            env = runner.env
            purchase_price = _number(env.unit_production_cost(firm)) / unit_size
        except Exception:
            pass
    procurement_costs = (
        period["handling_cost"] / bottles_sold if bottles_sold > 0 else 0.0
    )

    income = _income(runner, firm_id, None)
    overhead = (
        income["wages"] + income["rent_fixed"] + income["storage"]
    ) / bottles_sold if bottles_sold > 0 else 0.0
    landed_cost = purchase_price + procurement_costs
    full_cost = landed_cost + overhead
    profit = sell_price - full_cost
    margin_pct = profit / sell_price * 100 if sell_price > 0 else 0.0

    simulation = getattr(config, "simulation", None)
    days_per_year = _number(getattr(simulation, "days_per_year", 1), 1.0)
    days_elapsed = max(1.0, days_per_year)
    bottles_per_day = bottles_sold / days_elapsed
    try:  # Händler: tatsächlicher Tagesabsatz statt Jahresumsatz durch 360 (sonst mitten im Jahr zu tief)
        runtime = runner.env.runtimes[firm_id]
        daily = _number(getattr(runtime, "consumer_units_sold", 0.0))
        if daily > 0:
            bottles_per_day = daily * unit_size
    except Exception:
        pass

    values = {
        "purchase_price": purchase_price,
        "procurement_costs": procurement_costs,
        "landed_cost": landed_cost,
        "overhead": overhead,
        "full_cost": full_cost,
        "sell_price": sell_price,
        "profit": profit,
        "margin_pct": margin_pct,
        "break_even_price": full_cost,
        "bottles_per_day": bottles_per_day,
    }
    return {key: round(_number(value), 2) for key, value in values.items()}


def calculation(runner, firm_id) -> dict:
    """Return the current cost calculation per bottle."""
    try:
        return _calculation(runner, firm_id)
    except Exception:
        return {
            "purchase_price": 0.0,
            "procurement_costs": 0.0,
            "landed_cost": 0.0,
            "overhead": 0.0,
            "full_cost": 0.0,
            "sell_price": 0.0,
            "profit": 0.0,
            "margin_pct": 0.0,
            "break_even_price": 0.0,
            "bottles_per_day": 0.0,
        }


def annual_report(runner, firm_id, year) -> dict:
    """Build a complete annual report from the current period state."""
    income = _income(runner, firm_id, year)
    balance = balance_sheet(runner, firm_id)
    cash = _cash(runner, firm_id, year)
    return {
        "year": year,
        "income_statement": income,
        "balance_sheet": balance,
        "cash_flow": cash,
        "ratios": _ratios(income, balance),
        "calculation": calculation(runner, firm_id),
    }


def record_year(runner, year) -> None:
    """Store annual reports, isolating failures to individual firms."""
    reports = getattr(runner, "annual_reports", None)
    if not isinstance(reports, dict):
        reports = {}
        try:
            setattr(runner, "annual_reports", reports)
        except Exception:
            return

    year_reports = reports.setdefault(year, {})
    if not isinstance(year_reports, dict):
        year_reports = {}
        reports[year] = year_reports

    for firm_id, runtime in _runtimes(runner).items():
        try:
            period = _period(runner, firm_id)
            if getattr(runtime, "active", True) is False and period["revenue"] == 0:
                continue
            year_reports[firm_id] = annual_report(runner, firm_id, year)
        except Exception:
            continue
