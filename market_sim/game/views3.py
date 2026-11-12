from __future__ import annotations

import math


__all__ = ["purchasing", "deliveries", "daughters", "stocks_all"]


_CATEGORY_NAMES = {
    "beer": "Bier",
    "wine": "Wein",
    "spirits": "Spirituosen",
    "softdrinks": "Softdrinks",
    "water": "Wasser",
}

_BRANCH_NAMES = {
    "factory": "Hersteller",
    "wholesaler": "Grosshändler",
    "distributor": "Verteiler",
    "retailer": "Detailhandel",
    "truck_dealer": "Lastwagenhandel",
    "bank": "Bank",
    "courier": "Kurier",
}


def _read(obj, name: str, default=None):
    try:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)
    except Exception:
        return default


def _number(value, default: float = 0.0) -> float:
    try:
        result = float(value)
        if not math.isfinite(result):
            return default
        return result
    except Exception:
        return default


def _unit(runner) -> int:
    try:
        value = int(runner.config.unit_scale.real_units_per_sim_unit)
        return value if value > 0 else 1
    except Exception:
        return 1


def _clean(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else 0.0
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            try:
                result[str(key)] = _clean(item)
            except Exception:
                continue
        return result
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    try:
        return str(value)
    except Exception:
        return ""


def _mapping(value) -> dict:
    return value if isinstance(value, dict) else {}


def _method(obj, name: str, *args, default=None):
    try:
        function = getattr(obj, name, None)
        if callable(function):
            return function(*args)
    except Exception:
        pass
    return default


def _player_choices(runner, player_id):
    try:
        choices = getattr(runner, "player_choices", {})
        if isinstance(choices, dict):
            return choices.get(player_id)
    except Exception:
        pass
    return None


def _storage(env, player_id) -> dict:
    capacity = _method(env, "storage_capacity", player_id)
    used = _method(env, "storage_used", player_id)
    return {
        "capacity": _clean(capacity) if capacity is not None else None,
        "used": _clean(used) if used is not None else None,
    }


def _firm(runner, firm_id):
    try:
        network = getattr(runner, "network", None)
        function = getattr(network, "firm", None)
        if callable(function):
            return function(firm_id)
    except Exception:
        pass
    return None


def _numeric_map(value) -> dict:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, item in value.items():
        try:
            result[str(key)] = _number(item)
        except Exception:
            continue
    return result


def purchasing(runner, state, player_id, **extra) -> dict:
    """Zeigt Rohstoff- oder Markeneinkauf und Lagerbestand."""
    try:
        env = getattr(runner, "env", None)
        firm = _firm(runner, player_id)
        choices = _player_choices(runner, player_id)
        storage = _storage(env, player_id)

        if _read(firm, "stage") == "factory":
            try:
                capacity = _number(_method(env, "_effective_capacity", player_id)) * _unit(runner)
            except Exception:
                capacity = 0.0
            # Vorschlag: so viel brauen, wie die Kunden zuletzt bestellt haben (nicht die volle Kapazität,
            # sonst stapeln sich Rohstoffe, die niemand braucht).
            try:
                runtime = env.runtimes[player_id]
                recent = list(getattr(runtime, "orders_received_history", []))[-30:]
                demand = (sum(recent) / len(recent)) * _unit(runner) if recent else 0.0
            except Exception:
                demand = 0.0
            if demand <= 0:  # neu gegründet: Durchschnitt der anderen Hersteller derselben Kategorie
                try:
                    me = runner.network.firm(player_id)
                    values = []
                    for other in runner.network.firms_in("factory"):
                        if other.id == player_id or other.category != me.category or not env.runtimes[other.id].active:
                            continue
                        hist = list(env.runtimes[other.id].orders_received_history)[-30:]
                        if hist:
                            values.append(sum(hist) / len(hist))
                    if values:
                        demand = sum(values) / len(values) * _unit(runner) * 0.5  # Neuling: halber Marktanteil
                except Exception:
                    demand = 0.0
            if demand > 0:
                capacity = min(capacity, demand) if capacity > 0 else demand
            need = _method(env, "component_need", player_id, capacity, default={})
            stock = _method(env, "component_stock", player_id, default={})
            prices = _method(env, "component_prices", player_id, default={})
            plan = _read(choices, "component_plan", {})
            if not isinstance(plan, dict):
                plan = {}
            history = extra.get("history", [])
            if not isinstance(history, list):
                history = []
            return {
                "kind": "hersteller",
                "target_bottles": capacity,
                "need": _numeric_map(need),
                "stock": _numeric_map(stock),
                "prices": _numeric_map(prices),
                "plan": _clean(plan),
                "history": [
                    _clean(row) for row in history if isinstance(row, dict)
                ],
                "storage": storage,
            }

        book = getattr(env, "brand_book", None)
        catalog = _method(book, "brand_catalog", runner, player_id, default=[])
        if not isinstance(catalog, list):
            catalog = []
        demand = _method(book, "demand_by_category", runner, default={})
        if not isinstance(demand, dict):
            demand = {}

        stock_by_category = _method(env, "stock_by_category", player_id, default={})
        if not isinstance(stock_by_category, dict):
            stock_by_category = {}
        total_stock = sum(max(0.0, _number(amount)) for amount in stock_by_category.values())

        categories = []
        for key, amount in demand.items():
            category_stock = max(0.0, _number(stock_by_category.get(key, 0.0)))
            categories.append({
                "key": _clean(key),
                "name": _CATEGORY_NAMES.get(key, str(key)),
                "demand_per_day": _number(amount),
                "rival_cover": (
                    round(category_stock / total_stock, 3) if total_stock > 0 else 0.0
                ),
            })

        plan = _read(choices, "brand_plan", {})
        if not isinstance(plan, dict):
            plan = {}
        return {
            "kind": "haendler",
            "categories": categories,
            "brands": _with_buy_prices(runner, state, player_id, [_clean(item) for item in catalog if isinstance(item, dict)]),
            "plan": _clean(plan),
            "storage": storage,
        }
    except Exception:
        return {
            "kind": "haendler",
            "categories": [],
            "brands": [],
            "plan": {},
            "storage": {"capacity": None, "used": None},
        }


def deliveries(runner, state, player_id, **extra) -> dict:
    """Zeigt Lieferungen der Lieferanten in Flaschen."""
    suppliers = []
    try:
        env = getattr(runner, "env", None)
        delivery_book = getattr(env, "delivery_book", {})
        player_deliveries = (
            delivery_book.get(player_id, {})
            if isinstance(delivery_book, dict)
            else {}
        )
        if not isinstance(player_deliveries, dict):
            player_deliveries = {}
        unit = _unit(runner)

        for supplier_id, data in player_deliveries.items():
            try:
                data = data if isinstance(data, dict) else {}
                ordered = int(round(_number(data.get("ordered")) * unit))
                delivered = int(round(_number(data.get("delivered")) * unit))
                open_amount = int(round(_number(data.get("open")) * unit))
                fill_rate = (
                    1.0
                    if ordered == 0
                    else round(max(0.0, min(1.0, delivered / ordered)), 3)
                )
                supplier = _firm(runner, supplier_id)
                name = _read(supplier, "name", supplier_id) or supplier_id
                suppliers.append({
                    "id": _clean(supplier_id),
                    "name": _clean(name),
                    "ordered": ordered,
                    "delivered": delivered,
                    "open": open_amount,
                    "fill_rate": fill_rate,
                })
            except Exception:
                continue

        suppliers.sort(key=lambda item: item["ordered"], reverse=True)
    except Exception:
        suppliers = []
    return {"suppliers": suppliers}


def _paid_price(runner, player_id, firm_id) -> float:
    try:
        holding_groups = getattr(runner, "holding_groups", None)
        group = None
        group_of = getattr(holding_groups, "group_of", None)
        if callable(group_of):
            group = group_of(player_id)
        paid = _read(group, "paid", {})
        if isinstance(paid, dict):
            return _number(paid.get(firm_id, 0.0))
    except Exception:
        pass
    return 0.0


def _received_amount(runner, firm_id) -> float:
    try:
        holdings = getattr(runner, "holdings", None)
        paid = getattr(holdings, "paid", {})
        if not isinstance(paid, dict):
            return 0.0
        return sum(
            _number(amount)
            for key, amount in paid.items()
            if isinstance(key, tuple) and len(key) >= 2 and key[1] == firm_id
        )
    except Exception:
        return 0.0


def _purchase_year(runner, player_id, firm_id):
    try:
        holding_groups = getattr(runner, "holding_groups", None)
        group = None
        group_of = getattr(holding_groups, "group_of", None)
        if callable(group_of):
            group = group_of(player_id)
        for field in ("acquired_year", "purchase_year", "bought_year"):
            value = _read(group, field)
            if isinstance(value, dict):
                value = value.get(firm_id)
            if value is not None:
                return int(value)
        for field in ("acquired", "purchased", "bought"):
            values = _read(group, field)
            if isinstance(values, dict) and firm_id in values:
                value = values[firm_id]
                if isinstance(value, dict):
                    value = value.get("year")
                elif not isinstance(value, (int, float, str)):
                    value = _read(value, "year")
                if value is not None:
                    return int(value)
    except Exception:
        pass
    return None


def _loan_amount(value, firm_id) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, _number(value))
    if isinstance(value, (list, tuple)):
        return sum(_loan_amount(item, firm_id) for item in value)
    if isinstance(value, dict):
        for key in ("borrower", "firm_id", "debtor", "owner"):
            if value.get(key) == firm_id:
                for amount_key in ("amount", "principal", "balance", "debt", "outstanding"):
                    if amount_key in value:
                        return max(0.0, _number(value.get(amount_key)))
        if firm_id in value:
            return _loan_amount(value.get(firm_id), firm_id)
        total = 0.0
        for key, item in value.items():
            if key in ("loans", "loan_book"):
                total += _loan_amount(item, firm_id)
            elif isinstance(item, (dict, list, tuple)):
                total += _loan_amount(item, firm_id)
        return total
    borrower = _read(value, "borrower", _read(value, "firm_id", _read(value, "debtor")))
    if borrower == firm_id:
        for key in ("amount", "principal", "balance", "debt", "outstanding"):
            amount = _read(value, key)
            if amount is not None:
                return max(0.0, _number(amount))
    return 0.0


def _daughter_debt(env, firm_id) -> float:
    loans = 0.0
    try:
        banking = getattr(env, "banking", None)
        banks = getattr(banking, "banks", {})
        if isinstance(banks, dict):
            for bank in banks.values():
                for field in ("loans", "loan_book"):
                    loans += _loan_amount(_read(bank, field, {}), firm_id)
    except Exception:
        loans = 0.0
    try:
        runtime = _read(getattr(env, "runtimes", {}), firm_id)
        cash_debt = max(0.0, -_number(_read(runtime, "cash", 0.0)))
    except Exception:
        cash_debt = 0.0
    return max(loans, cash_debt)


def _last_profit(state, firm_id) -> float:
    try:
        summaries = _read(state, "summaries", [])
        if summaries:
            summary = _read(summaries[-1], firm_id)
            return _number(_read(summary, "profit", 0.0))
    except Exception:
        pass
    return 0.0


def daughters(runner, state, player_id, **extra) -> dict:
    """Zeigt Rendite, Wert und Regeln der Töchter."""
    rows = []
    try:
        from market_sim.game import holding_player

        daughter_ids = holding_player.daughters(runner, player_id)
        if not isinstance(daughter_ids, (list, tuple)):
            daughter_ids = []
        env = getattr(runner, "env", None)
        current_year = _read(state, "year")
        choices = _player_choices(runner, player_id)
        rules_by_daughter = _read(choices, "daughter_rules", {})
        if not isinstance(rules_by_daughter, dict):
            rules_by_daughter = {}

        for firm_id in daughter_ids:
            try:
                firm = _firm(runner, firm_id)
                received = _received_amount(runner, firm_id)
                purchase_year = _purchase_year(runner, player_id, firm_id)
                if purchase_year is not None and current_year is not None:
                    years = max(1, int(current_year) - purchase_year + 1)
                    return_per_year = received / years
                else:
                    return_per_year = _last_profit(state, firm_id)

                try:
                    value_now = holding_player.firm_value(runner, state, firm_id)
                except Exception:
                    value_now = 0.0

                rules = rules_by_daughter.get(firm_id, {})
                if not isinstance(rules, dict):
                    rules = {}
                rules = {
                    "no_credit": bool(rules.get("no_credit", False)),
                    "no_stakes": bool(rules.get("no_stakes", False)),
                }

                rows.append({
                    "id": _clean(firm_id),
                    "name": _clean(_read(firm, "name", firm_id) or firm_id),
                    "price_paid": round(_paid_price(runner, player_id, firm_id), 2),
                    "received": round(received, 2),
                    "value_now": round(_number(value_now), 2),
                    "debt": round(_daughter_debt(env, firm_id), 2),
                    "return_per_year": round(_number(return_per_year), 2),
                    "rules": rules,
                })
            except Exception:
                continue
    except Exception:
        rows = []
    return {"rows": rows}


def _listed_ids(stock_market) -> set:
    try:
        listed = getattr(stock_market, "listed", set())
        if isinstance(listed, dict):
            return {key for key, value in listed.items() if value}
        return set(listed or [])
    except Exception:
        return set()


def _truck_dealer_items(env):
    try:
        dealers = getattr(env, "truck_dealers", [])
        if isinstance(dealers, dict):
            return list(dealers.items())
        result = []
        for index, dealer in enumerate(dealers or []):
            result.append((_read(dealer, "id", index), dealer))
        return result
    except Exception:
        return []


def stocks_all(runner, state, player_id, **extra) -> dict:
    """Zeigt alle börsennotierten Firmen und ihre Kursverläufe."""
    try:
        stock_market = getattr(runner, "stock_market", None)
        if stock_market is None:
            return {"firms": [], "series": {}}

        listed = _listed_ids(stock_market)
        env = getattr(runner, "env", None)
        firms_by_id = {}

        try:
            network = getattr(runner, "network", None)
            stages = getattr(network, "stages", [])
            for stage in stages or []:
                stage_firms = getattr(stage, "firms", [])
                for firm in stage_firms or []:
                    firm_id = _read(firm, "id")
                    if firm_id is None:
                        continue
                    stage_name = _read(firm, "stage")
                    firms_by_id[firm_id] = {
                        "id": _clean(firm_id),
                        "name": _clean(_read(firm, "name", firm_id) or firm_id),
                        "branch": _BRANCH_NAMES.get(stage_name, _clean(stage_name)),
                        "listed": firm_id in listed,
                    }
        except Exception:
            pass

        try:
            banking = getattr(env, "banking", None)
            banks = getattr(banking, "banks", {})
            if isinstance(banks, dict):
                for bank_id, bank in banks.items():
                    firms_by_id[bank_id] = {
                        "id": _clean(bank_id),
                        "name": _clean(_read(bank, "name", bank_id) or bank_id),
                        "branch": "Bank",
                        "listed": bank_id in listed,
                    }
        except Exception:
            pass

        for dealer_id, dealer in _truck_dealer_items(env):
            try:
                firm_id = _read(dealer, "id", dealer_id)
                firms_by_id[firm_id] = {
                    "id": _clean(firm_id),
                    "name": _clean(_read(dealer, "name", firm_id) or firm_id),
                    "branch": "Lastwagenhandel",
                    "listed": firm_id in listed,
                }
            except Exception:
                continue

        firms = list(firms_by_id.values())
        firms.sort(key=lambda item: (not item["listed"], str(item["name"])))

        series = {}
        try:
            daily_rows = getattr(stock_market, "daily_rows", [])
            for row in daily_rows or []:
                if not isinstance(row, dict):
                    continue
                day = _clean(row.get("global_day"))
                for firm_id, price in row.items():
                    if firm_id in ("global_day", "year", "day", "index"):
                        continue
                    key = str(firm_id)
                    series.setdefault(key, []).append({
                        "day": day,
                        "price": round(_number(price), 2),
                    })
        except Exception:
            series = {}

        for firm_id in listed:
            series.setdefault(str(firm_id), [])

        for key, points in list(series.items()):
            if len(points) > 600:
                step = int(math.ceil(len(points) / 600))
                sampled = points[::step]
                if sampled[-1] is not points[-1]:
                    sampled.append(points[-1])
                series[key] = sampled

        return {"firms": firms, "series": series}
    except Exception:
        return {"firms": [], "series": {}}


def _with_buy_prices(runner, state, player_id, brands):
    """Für Händler: Preis = was du beim Grosshändler zahlst (nicht der Herstellerpreis)."""
    try:
        from market_sim.game.views4 import buy_prices
        buy = buy_prices(runner, state, player_id)
        for item in brands:
            if item.get("id") in buy:
                item["producer_price"] = item.get("price")
                item["price"] = buy[item["id"]]
    except Exception:
        pass
    return brands
