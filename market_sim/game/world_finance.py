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

    return {
        "banks": banks_data,
        "accounts": accounts,
        "loans": loans,
        "offers": offers,
        "credit_limit": credit_limit,
    }


def stocks(runner, state, player_id, depot=None):
    """Liefert Börsenkurse, Kursverläufe und das eigene Depot."""
    sm = _get(runner, "stock_market")
    if sm is None:
        return {"listed": [], "index": None, "depot": [], "fee": 0.0}

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

    return {
        "listed": listed,
        "index": _r(_get(sm, "index")),
        "depot": depot_positions,
        "fee": fee,
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
