from __future__ import annotations

import math


def _get(obj, key, default=None):
    """Liest ein Attribut oder einen Dictionary-Eintrag sicher aus."""
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    except Exception:
        return default


def _lookup(mapping, key, default=None):
    """Liest einen Dictionary-Eintrag sicher aus."""
    try:
        if isinstance(mapping, dict):
            return mapping.get(key, default)
    except Exception:
        pass
    return default


def _items(mapping):
    """Gibt Dictionary-Einträge sicher als Liste zurück."""
    try:
        if isinstance(mapping, dict):
            return list(mapping.items())
    except Exception:
        pass
    return []


def _r(x, n=4):
    """Rundet Zahlen und ersetzt ungültige Werte durch None."""
    try:
        value = float(x)
        if not math.isfinite(value):
            return None
        rounded = round(value, n)
        if not math.isfinite(rounded):
            return None
        return rounded
    except (TypeError, ValueError, OverflowError):
        return None


def _number(x):
    """Wandelt einen endlichen Wert sicher in eine Zahl um."""
    try:
        value = float(x)
        if math.isfinite(value):
            return value
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _text(value, fallback=""):
    """Wandelt einen Wert sicher in Text um."""
    if value is None:
        return fallback
    try:
        return str(value)
    except Exception:
        return fallback


def _plain(value):
    """Wandelt Werte rekursiv in JSON-fähige Werte um."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return _r(value)
    if isinstance(value, dict):
        result = {}
        try:
            for key, item in value.items():
                result[_text(key)] = _plain(item)
        except Exception:
            return {}
        return result
    if isinstance(value, (list, tuple)):
        try:
            return [_plain(item) for item in value]
        except Exception:
            return []
    return _text(value)


def _thin(values, n=60):
    """Dünnt eine Liste gleichmässig aus und behält ihre Endpunkte."""
    try:
        items = list(values)
    except Exception:
        return []
    if n <= 0 or not items:
        return []
    if len(items) <= n:
        return items
    if n == 1:
        return [items[0]]
    last = len(items) - 1
    indices = [int(round(i * last / (n - 1))) for i in range(n)]
    return [items[index] for index in indices]


def _history_rows(history, fields):
    """Kopiert ausgewählte Felder aus einer Verlaufsliste."""
    result = []
    try:
        rows = list(history)
    except Exception:
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        copied = {}
        for field in fields:
            value = _lookup(row, field)
            if field == "label":
                copied[field] = _text(value)
            else:
                copied[field] = _r(value)
        result.append(copied)
    return result


def _firm(runner, firm_id):
    """Liest eine Firma aus dem Netzwerk, falls verfügbar."""
    network = _get(runner, "network")
    method = _get(network, "firm")
    if not callable(method):
        return None
    try:
        return method(firm_id)
    except Exception:
        return None


def macro(runner, state, player_id, history=None):
    """Liefert die aktuellen Makrodaten und deren Verlauf."""
    env = _get(runner, "env")
    cb = _get(env, "central_bank")
    long_run = _get(runner, "long_run")

    if cb is None:
        inflation = _get(long_run, "inflation")
    else:
        inflation = _get(cb, "inflation")

    return {
        "policy_rate": _r(_get(cb, "policy_rate")),
        "inflation": _r(inflation),
        "price_index": _r(_get(long_run, "price_index")),
        "fx_rate": _r(_get(env, "fx_rate")),
        "history": _history_rows(
            history, ("label", "policy_rate", "inflation", "fx_rate")
        ),
    }


def banks(runner, state, player_id, amount=None):
    """Liefert öffentliche Bankdaten und die eigenen Konten und Kredite."""
    env = _get(runner, "env")
    banking = _get(env, "banking")

    banks_data = []
    bank_objects = {}
    for bank_id, bank in _items(_get(banking, "banks")):
        bank_objects[bank_id] = bank
        banks_data.append(
            {
                "id": _plain(_get(bank, "id", bank_id)),
                "name": _text(_get(bank, "name", bank_id)),
                "margin": _r(_get(bank, "margin")),
                "equity": _r(_get(bank, "equity")),
                "capital_ratio": _r(_get(bank, "capital_ratio")),
                "active": bool(_get(bank, "active", False)),
            }
        )
    banks_data.sort(key=lambda item: _text(item["id"]))

    accounts = {}
    player_accounts = _lookup(_get(banking, "accounts"), player_id, {})
    for bank_id, share in _items(player_accounts):
        accounts[_text(bank_id)] = _r(share)

    try:
        from market_sim.banking import PURPOSE_DE
    except Exception:
        PURPOSE_DE = {}

    loans = []
    player_loans = _lookup(_get(banking, "by_firm"), player_id, [])
    try:
        loan_items = list(player_loans)
    except Exception:
        loan_items = []
    for loan in loan_items:
        bank_id = _get(loan, "bank_id")
        bank = _lookup(_get(banking, "banks"), bank_id)
        bank_name = _get(bank, "name", bank_id)
        purpose = _get(loan, "purpose")
        purpose = _lookup(PURPOSE_DE, purpose, purpose)
        loans.append(
            {
                "bank": _text(bank_name, _text(bank_id)),
                "amount": _r(_get(loan, "principal"), 2),
                "rate": _r(_get(loan, "rate")),
                "years": _r(_get(loan, "years")),
                "remaining": _r(_get(loan, "outstanding"), 2),
                "purpose": _text(purpose),
            }
        )

    offers = []
    amount_value = _number(amount) if amount is not None else None
    if amount_value is not None and amount_value > 0:
        try:
            from market_sim.game.actions import loan_offers

            offers = _plain(loan_offers(runner, player_id, float(amount_value)))
            if not isinstance(offers, list):
                offers = []
        except Exception:
            offers = []

    credit_limit = None
    runtimes = _get(env, "runtimes")
    runtime = _lookup(runtimes, player_id)
    credit_limit = _r(_get(runtime, "credit_limit"), 2)

    try:
        own = _own_bank(runner, state, player_id, env, banking, runtime, loan_items, credit_limit)
    except Exception:
        own = _own_bank_empty(credit_limit)

    return {
        "banks": banks_data,
        "accounts": accounts,
        "loans": loans,
        "offers": offers,
        "credit_limit": credit_limit,
        "own": own,
    }


_OWN_FIELDS = (
    "bank_id", "bank_name", "deposit_rate", "overdraft_rate", "loan_rate", "policy_rate",
    "cash", "credit_limit", "debt_total", "interest_paid_year", "interest_received_year",
    "next_payment_year",
)


def _own_bank_empty(credit_limit=None):
    """Leere Hausbank-Angaben, falls nichts berechnet werden kann."""
    own = {key: None for key in _OWN_FIELDS}
    own["credit_limit"] = credit_limit
    return own


def _own_bank(runner, state, player_id, env, banking, runtime, loan_items, credit_limit):
    """Berechnet Hausbank, Zinssätze, Schulden und Zinszahlungen der eigenen Firma."""
    own = _own_bank_empty(credit_limit)
    cfg = _get(_get(env, "config"), "bank")
    cb_cfg = _get(_get(env, "config"), "central_bank")
    cb = _get(env, "central_bank")
    policy_rate = _number(_get(cb, "policy_rate"))
    cb_on = bool(_get(cb_cfg, "enabled", False)) and policy_rate is not None

    bank = None
    try:
        if _lookup(_get(banking, "accounts"), player_id):
            bank = banking.primary_bank(player_id)
    except Exception:
        bank = None
    margin = _number(_get(bank, "margin"))
    if margin is None:
        margin = _number(_get(cfg, "loan_margin")) or 0.0

    deposit_rate = _number(_get(cfg, "deposit_rate"))
    negative_rate = _number(_get(cfg, "negative_rate"))
    base = _number(_get(cfg, "base_rate"))
    if cb_on:
        deposit_rate = max(_number(_get(cfg, "deposit_rate_floor")) or 0.0,
                           policy_rate - (_number(_get(cfg, "deposit_spread")) or 0.0))
        negative_rate = max(_number(_get(cfg, "negative_rate_floor")) or 0.0,
                            (_number(_get(cfg, "negative_policy_factor")) or 0.0) * policy_rate,
                            -policy_rate)
        base = policy_rate
    loan_rate = None
    overdraft_rate = None
    if base is not None:
        max_rate = _number(_get(cfg, "max_rate"))
        overdraft_rate = base + margin
        loan_rate = overdraft_rate
        if max_rate is not None:
            overdraft_rate = min(max_rate, overdraft_rate)
    cash = _number(_get(runtime, "cash"))
    debt_total = 0.0
    next_payment = 0.0
    for loan in loan_items:
        outstanding = _number(_get(loan, "outstanding")) or 0.0
        rate = _number(_get(loan, "rate")) or 0.0
        installment = _number(_get(loan, "installment"))
        if installment is None:
            years = _number(_get(loan, "years")) or 1.0
            installment = (_number(_get(loan, "principal")) or outstanding) / max(1.0, years)
        debt_total += outstanding
        next_payment += min(outstanding, installment) + outstanding * rate

    paid = received = None
    try:
        from market_sim.game.world_firm import year_baseline

        baseline = year_baseline(runner, player_id, _get(state, "year", 1))
        net = (_number(_get(runtime, "interest_cost")) or 0.0) - (
            _number(_lookup(baseline, "interest_cost", 0.0)) or 0.0)
        paid = max(0.0, net)
        received = max(0.0, -net)
    except Exception:
        paid = received = None

    own.update({
        "bank_id": _plain(_get(bank, "id")),
        "bank_name": _text(_get(bank, "name")) if bank is not None else None,
        "deposit_rate": _r(deposit_rate),
        "overdraft_rate": _r(overdraft_rate),
        "loan_rate": _r(loan_rate),
        "policy_rate": _r(policy_rate),
        "cash": _r(cash, 2),
        "debt_total": _r(debt_total, 2),
        "interest_paid_year": _r(paid, 2),
        "interest_received_year": _r(received, 2),
        "next_payment_year": _r(next_payment, 2),
    })
    return own


def stocks(runner, state, player_id, depot=None, history=None):
    """Liefert Börsenkurse, Kursverläufe und das eigene Depot."""
    sm = _get(runner, "stock_market")
    if sm is None:
        return {
            "listed": [],
            "index": None,
            "depot": [],
            "fee": 0.0,
            "index_history": [],
            "note": "Keine Börse aktiv.",
        }

    cfg = _get(sm, "cfg")
    shares_per_firm = _number(_get(cfg, "shares_per_firm"))
    prices = _get(sm, "prices")
    try:
        listed_ids = list(_get(sm, "listed", []))
    except Exception:
        listed_ids = []
    listed_ids.sort(key=lambda value: _text(value))

    try:
        daily_rows = list(_get(sm, "daily_rows", []))
    except Exception:
        daily_rows = []

    index_history = []
    try:
        history_rows = list(history) if history is not None else []
    except Exception:
        history_rows = []
    if history_rows and all(
        isinstance(row, dict) and "value" in row for row in history_rows
    ):
        for row in history_rows:
            index_history.append(
                {
                    "label": _text(_lookup(row, "label")),
                    "value": _r(_lookup(row, "value")),
                }
            )
    else:
        simulation = _get(_get(runner, "config"), "simulation")
        dpm = _number(_get(simulation, "days_per_month"))
        if dpm is None or dpm <= 0:
            dpm = 30
        monthly_values = {}
        for row in daily_rows:
            if not isinstance(row, dict):
                continue
            year = _number(_lookup(row, "year"))
            day = _number(_lookup(row, "day"))
            if year is None or day is None:
                continue
            month = int((day - 1) // dpm) + 1
            monthly_values[(year, month)] = _lookup(row, "index")
        for (year, month), value in sorted(monthly_values.items()):
            year_label = int(year) if year.is_integer() else year
            index_history.append(
                {
                    "label": f"Jahr {year_label}, Monat {month}",
                    "value": _r(value, 2),
                }
            )

    listed = []
    for firm_id in listed_ids:
        firm = _firm(runner, firm_id)
        name = _text(_get(firm, "name", firm_id), _text(firm_id))
        branch = _get(firm, "branch")
        if branch is None:
            branch = _get(firm, "stage", "")
        branch = _text(branch)

        price_raw = _lookup(prices, firm_id)
        price = _r(price_raw, 4)

        raw_history = []
        for row in daily_rows:
            value = _lookup(row, firm_id)
            if isinstance(row, dict) and firm_id in row:
                rounded = _r(value, 4)
                if rounded is not None:
                    raw_history.append(rounded)

        change = 0.0
        current_price = _number(price_raw)
        if len(raw_history) >= 2 and current_price is not None:
            baseline_index = max(0, len(raw_history) - 31)
            baseline = _number(raw_history[baseline_index])
            if baseline is not None and baseline != 0:
                calculated_change = _r(current_price / baseline - 1.0, 4)
                if calculated_change is not None:
                    change = calculated_change

        market_cap = None
        if current_price is not None and shares_per_firm is not None:
            market_cap = _r(current_price * shares_per_firm, 2)

        listed.append(
            {
                "id": _plain(firm_id),
                "name": name,
                "branch": branch,
                "price": price,
                "change": change,
                "market_cap": market_cap,
                "history": _thin(raw_history, 60),
            }
        )

    fee = 0.005
    config = _get(runner, "config")
    for attribute in ("holdings", "holding", "stakes"):
        section = _get(config, attribute)
        if section is None:
            continue
        broker_fee = _get(section, "broker_fee")
        if broker_fee is not None:
            fee_value = _number(broker_fee)
            if fee_value is not None:
                fee = _r(fee_value)
            break

    depot_positions = []
    if depot is not None:
        try:
            positions = depot.positions(runner)
            depot_positions = _plain(positions)
            if not isinstance(depot_positions, list):
                depot_positions = []
        except Exception:
            depot_positions = []

    current_year = _number(_get(state, "year"))
    if current_year is None:
        for row in reversed(daily_rows):
            if isinstance(row, dict):
                current_year = _number(_lookup(row, "year"))
                if current_year is not None:
                    break
    if current_year is None:
        current_year = 1
    tradable_from_year = _number(_get(cfg, "tradable_from_year"))
    if listed:
        note = None
    elif tradable_from_year is not None and tradable_from_year > current_year:
        note = (
            f"Die Börse eröffnet erst ab Jahr {int(tradable_from_year)}, "
            "vorher ist niemand kotiert."
        )
    else:
        note = (
            "Zurzeit ist keine Firma kotiert. Neue Firmen kommen frühestens "
            "nach einem vollen Jahr im Markt an die Börse."
        )

    return {
        "listed": listed,
        "index": _r(_get(sm, "index")),
        "depot": depot_positions,
        "fee": fee,
        "index_history": index_history,
        "note": note,
    }


def commodities(runner, state, player_id, history=None):
    """Liefert aktuelle Rohstoffpreise und deren Verlauf."""
    env = _get(runner, "env")
    prices = _get(env, "commodity_price")
    history_rows = _get(env, "commodity_history")

    try:
        price_items = _items(prices)
        rows = list(history_rows) if history_rows is not None else []
    except Exception:
        price_items = []
        rows = []

    price_items.sort(key=lambda item: _text(item[0]))
    current = []
    for name, price_raw in price_items:
        change = 0.0
        if len(rows) >= 2:
            previous_prices = _get(rows[-2], "prices")
            previous = _number(_lookup(previous_prices, name))
            current_value = _number(price_raw)
            if (
                previous is not None
                and previous != 0
                and current_value is not None
            ):
                calculated_change = _r(current_value / previous - 1.0, 4)
                if calculated_change is not None:
                    change = calculated_change
        current.append(
            {
                "name": _text(name),
                "index": _r(price_raw),
                "change": change,
            }
        )

    electricity = None
    electricity_method = _get(env, "electricity_level")
    if callable(electricity_method):
        try:
            electricity = _r(electricity_method())
        except Exception:
            electricity = None

    if history:
        history_result = []
        try:
            controller_rows = list(history)
        except Exception:
            controller_rows = []
        for row in controller_rows:
            if isinstance(row, dict):
                copied = _plain(row)
                if isinstance(copied, dict):
                    history_result.append(copied)
    else:
        history_result = []
        for row in rows:
            prices_in_row = _get(row, "prices")
            if not isinstance(prices_in_row, dict):
                continue
            year = _get(row, "year")
            copied = {"label": f"Jahr {_text(year)}"}
            for name, value in _items(prices_in_row):
                copied[_text(name)] = _r(value)
            history_result.append(copied)

    return {
        "current": current,
        "electricity": electricity,
        "history": history_result,
    }


def _truck_context(runner, state, player_id):
    """Berechnet einmalig die Absatz- und Transportlage für Lastwagenangebote."""
    env = _get(runner, "env")
    config = _get(runner, "config")
    scale = _number(
        _get(_get(config, "unit_scale"), "real_units_per_sim_unit")
    )
    if scale is None:
        scale = 1.0
    dpy = _number(_get(_get(config, "simulation"), "days_per_year"))
    if dpy is None:
        dpy = 360.0

    recent_demand = _get(state, "recent_demand")
    try:
        demand_values = _lookup(recent_demand, player_id, [])
        demand_values = list(demand_values) if demand_values is not None else []
    except Exception:
        demand_values = []
    numeric_demand = [
        value
        for value in (_number(item) for item in demand_values)
        if value is not None
    ]
    demand = sum(numeric_demand) / len(numeric_demand) if numeric_demand else 0.0

    personnel_cap = None
    effective_capacity = _get(env, "_effective_capacity")
    if callable(effective_capacity):
        try:
            personnel_cap = _number(effective_capacity(player_id))
        except Exception:
            personnel_cap = None
    if personnel_cap is None:
        personnel_cap = 0.0

    firm = _firm(runner, player_id)
    own_transport = firm is not None and _get(firm, "transport_mode") == "own"
    tm = _get(_get(env, "geography"), "trucks")
    transport_now = math.inf
    if own_transport:
        transport_now = 0.0
        capacity = _get(tm, "capacity")
        ref_km = _number(_get(tm, "REF_KM"))
        if ref_km is None or ref_km == 0:
            ref_km = 100.0
        if callable(capacity):
            try:
                current_capacity = _number(capacity(player_id))
                if current_capacity is not None:
                    transport_now = current_capacity / ref_km
            except Exception:
                pass

    price = _number(_get(firm, "sell_price"))
    if price is None:
        price = 0.0
    runtime = _lookup(_get(env, "runtimes"), player_id)
    revenue = _number(_get(runtime, "revenue"))
    purchase_cost = _number(_get(runtime, "purchase_cost"))
    if revenue is not None and revenue > 0:
        if purchase_cost is None:
            purchase_cost = 0.0
        margin = price * max(0.0, 1.0 - purchase_cost / revenue)
    else:
        margin = 0.3 * price

    return {
        "scale": scale,
        "dpy": dpy,
        "demand": demand,
        "personnel_cap": personnel_cap,
        "transport_now": transport_now,
        "own_transport": own_transport,
        "price": price,
        "margin": margin,
    }


def _truck_advice(offer, ctx):
    """Berechnet Mehrabsatz, Wirtschaftlichkeit und Engpassrat für ein Angebot."""
    try:
        demand = _number(ctx.get("demand"))
        personnel_cap = _number(ctx.get("personnel_cap"))
        demand = demand if demand is not None else 0.0
        personnel_cap = personnel_cap if personnel_cap is not None else 0.0
        transport_now = ctx.get("transport_now")
        if transport_now is None:
            transport_now = 0.0
        own_transport = bool(ctx.get("own_transport"))

        demand_limited = min(demand, personnel_cap)
        truck_cap = _number(_lookup(offer, "capacity"))
        if truck_cap is None:
            truck_cap = 0.0
        extra_units = 0.0
        if own_transport:
            extra_units = max(0.0, demand_limited - transport_now)
            extra_units = min(extra_units, max(0.0, truck_cap))

        scale = _number(ctx.get("scale"))
        if scale is None:
            scale = 1.0
        extra_sales_per_day = _r(extra_units * scale)
        if extra_sales_per_day is None:
            extra_sales_per_day = 0.0

        margin = _number(ctx.get("margin"))
        if margin is None:
            margin = 0.0
        dpy = _number(ctx.get("dpy"))
        if dpy is None:
            dpy = 360.0
        annual_cost = _number(_lookup(offer, "annual_cost"))
        if annual_cost is None:
            annual_cost = 0.0
        extra_profit_year = _r(
            extra_sales_per_day * margin * dpy - annual_cost, 2
        )
        if extra_profit_year is None:
            extra_profit_year = 0.0

        price = _number(_lookup(offer, "price"))
        payback_years = None
        if extra_profit_year > 0 and price is not None:
            payback_years = _r(price / extra_profit_year, 2)

        if not own_transport:
            advice = (
                "Du lieferst über Kurier oder Post, ein eigener Lastwagen "
                "ändert deinen Absatz nicht."
            )
        elif (
            personnel_cap <= min(demand, transport_now)
            and demand_limited < transport_now
        ):
            advice = (
                "Dein Engpass ist Personal, nicht Transport. Dieser Lastwagen "
                "erhöht deinen Absatz nicht."
            )
        elif demand < transport_now and demand <= personnel_cap:
            advice = (
                "Dein Engpass ist die Nachfrage, nicht Transport. Dieser "
                "Lastwagen erhöht deinen Absatz nicht."
            )
        elif extra_units > 0:
            advice = (
                f"Dein Engpass ist der Transport. Dieser Lastwagen bringt etwa "
                f"{extra_sales_per_day:.0f} Flaschen mehr Absatz pro Tag."
            )
            if extra_profit_year <= 0:
                advice += (
                    " Er lohnt sich trotzdem nicht, weil die Kosten den "
                    "Mehrertrag übersteigen."
                )
        else:
            advice = "Dieser Lastwagen erhöht deinen Absatz nicht."

        return {
            "extra_sales_per_day": extra_sales_per_day,
            "extra_profit_year": extra_profit_year,
            "payback_years": payback_years,
            "advice": advice,
        }
    except Exception:
        return {
            "extra_sales_per_day": 0.0,
            "extra_profit_year": 0.0,
            "payback_years": None,
            "advice": "",
        }


def trucks(runner, state, player_id):
    """Liefert Lastwagenangebote, die eigene Flotte und Händler."""
    env = _get(runner, "env")
    geography = _get(env, "geography")
    tm = _get(geography, "trucks")

    transport_mode = None
    firm = _firm(runner, player_id)
    mode = _get(firm, "transport_mode")
    if mode is not None:
        transport_mode = _text(mode)

    if tm is None:
        return {
            "offers": [],
            "fleet": [],
            "transport_mode": transport_mode,
            "dealers": [],
        }

    offers = []
    try:
        from market_sim.game.actions import truck_offers

        offers = _plain(truck_offers(runner, player_id))
        if not isinstance(offers, list):
            offers = []
    except Exception:
        offers = []

    context = _truck_context(runner, state, player_id)
    for offer in offers:
        if isinstance(offer, dict):
            offer.update(_truck_advice(offer, context))

    fleet = []
    fleet_items = _lookup(_get(tm, "fleets"), player_id, [])
    try:
        fleet_items = list(fleet_items)
    except Exception:
        fleet_items = []
    types = _get(tm, "types")
    for truck in fleet_items:
        truck_type = _get(truck, "type")
        truck_type_name = _text(truck_type)
        truck_info = _lookup(types, truck_type)
        label = _text(_get(truck_info, "label", truck_type), truck_type_name)
        try:
            value = _r(tm.value(env, truck), 2)
        except Exception:
            value = 0.0
        if value is None:
            value = 0.0
        age = _get(truck, "age")
        try:
            age_years = int(age)
        except (TypeError, ValueError, OverflowError):
            age_years = 0
        fleet.append(
            {
                "type": truck_type_name,
                "label": label,
                "age_years": age_years,
                "value": value,
                "leased": bool(_get(truck, "leased", False)),
            }
        )

    dealers = []
    active_dealers = _get(tm, "_active_dealers")
    if callable(active_dealers):
        try:
            for dealer in active_dealers():
                dealers.append(
                    {
                        "id": _plain(_get(dealer, "id")),
                        "name": _text(_get(dealer, "name")),
                    }
                )
        except Exception:
            dealers = []

    return {
        "offers": offers,
        "fleet": fleet,
        "transport_mode": transport_mode,
        "dealers": dealers,
    }
