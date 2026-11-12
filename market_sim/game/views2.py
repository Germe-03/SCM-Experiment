from __future__ import annotations

import math


__all__ = [
    "financials",
    "reports",
    "calculation",
    "pricing",
    "takeover_offers",
    "assortment",
    "check_plan",
]


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


def _round(value, digits: int = 2):
    try:
        return round(float(value), digits)
    except Exception:
        return value


def _unit(runner) -> int:
    try:
        value = int(runner.config.unit_scale.real_units_per_sim_unit)
        return value if value > 0 else 1
    except Exception:
        return 1


def _fin():
    try:
        import market_sim.financials
    except ImportError:
        return None
    return market_sim.financials


def _financial_call(name: str, *args, **kwargs):
    module = _fin()
    if module is None:
        raise ImportError(name)
    function = getattr(module, name, None)
    if not callable(function):
        raise AttributeError(name)
    return function(*args, **kwargs)


def _unavailable():
    return {"error": "Abschlüsse noch nicht verfügbar"}


def _year(state) -> int:
    try:
        return int(_read(state, "year", 1))
    except Exception:
        return 1


def financials(runner, state, player_id, **extra) -> dict:
    """Zeigt die Abschlüsse des laufenden und des letzten Jahres."""
    try:
        year = int(extra.get("year") or _year(state))
        try:
            current = _financial_call("income_statement", runner, player_id, year=None)
            balance_sheet = _financial_call("balance_sheet", runner, player_id)
            cash_flow = _financial_call("cash_flow", runner, player_id)
            ratios = _financial_call("ratios", runner, player_id)
        except Exception:
            return _unavailable()

        last_year = None
        cash_flow_last_year = None
        if year > 1:
            try:
                last_year = _financial_call(
                    "income_statement", runner, player_id, year=year - 1
                )
            except Exception:
                last_year = None
            try:
                cash_flow_last_year = _financial_call(
                    "cash_flow", runner, player_id, year=year - 1
                )
            except Exception:
                cash_flow_last_year = None

        return {
            "year": year,
            "income_current": current,
            "income_last": last_year,
            "balance": balance_sheet,
            "cash_flow": cash_flow,
            "cash_flow_last_year": cash_flow_last_year,
            "ratios": ratios,
        }
    except Exception:
        return _unavailable()


def reports(runner, state, player_id, **extra) -> dict:
    """Zeigt veröffentlichte Jahresabschlüsse anderer Firmen."""
    try:
        annual_reports = getattr(runner, "annual_reports", {})
        if not isinstance(annual_reports, dict) or not annual_reports:
            return {
                "year": None,
                "firms": [],
                "note": "Noch kein Jahresabschluss veröffentlicht.",
            }

        year = max(annual_reports.keys())
        yearly = annual_reports.get(year, {})
        if not isinstance(yearly, dict):
            yearly = {}

        firms = []
        network = _read(runner, "network")
        firm_method = _read(network, "firm")
        for firm_id, report in yearly.items():
            try:
                if firm_id == player_id:
                    continue
                if isinstance(report, dict):
                    report_data = dict(report)
                else:
                    report_data = dict(vars(report))
                name = firm_id
                stage = firm_id
                try:
                    if callable(firm_method):
                        firm = firm_method(firm_id)
                        name = _read(firm, "name", firm_id) or firm_id
                        stage = _read(firm, "stage", firm_id) or firm_id
                except Exception:
                    name = firm_id
                    stage = firm_id
                firms.append({
                    "id": firm_id,
                    "name": name,
                    "stage": stage,
                    **report_data,
                })
            except Exception:
                continue

        firms.sort(key=lambda item: str(item.get("name", item.get("id", ""))))
        return {"year": year, "firms": firms}
    except Exception:
        return {
            "year": None,
            "firms": [],
            "note": "Noch kein Jahresabschluss veröffentlicht.",
        }


def calculation(runner, state, player_id, **extra) -> dict:
    """Zeigt die Selbstkosten und den Verkaufspreis pro Flasche."""
    try:
        result = _financial_call("calculation", runner, player_id)
        if not isinstance(result, dict):
            return _unavailable()
        output = dict(result)
        output["unit_size"] = _unit(runner)
        output["note"] = "Alle Beträge in CHF pro Flasche"
        return output
    except Exception:
        return _unavailable()


def pricing(runner, state, player_id, **extra) -> dict:
    """Zeigt Marge und Preisverlauf pro Flasche."""
    history = extra.get("price_history", [])
    unavailable = {
        "purchase_price": None,
        "sell_price": None,
        "margin_per_bottle": None,
        "margin_pct": None,
        "overhead_per_bottle": None,
        "profit_per_bottle": None,
        "break_even_price": None,
        "history": history,
    }
    try:
        result = _financial_call("calculation", runner, player_id)
        if not isinstance(result, dict):
            return unavailable
        purchase_price = result.get("purchase_price")
        sell_price = result.get("sell_price")
        if purchase_price is None or sell_price is None:
            return unavailable
        margin = _number(sell_price) - _number(purchase_price)
        sell = _number(sell_price)
        return {
            "purchase_price": _round(purchase_price),
            "sell_price": _round(sell_price),
            "margin_per_bottle": _round(margin),
            "margin_pct": _round(margin / sell * 100 if sell else 0),
            "overhead_per_bottle": _round(result.get("overhead")),
            "profit_per_bottle": _round(result.get("profit")),
            "break_even_price": _round(result.get("break_even_price")),
            "history": history,
        }
    except Exception:
        return unavailable


def _firm_details(runner, firm_id):
    name = firm_id
    stage = firm_id
    try:
        network = _read(runner, "network")
        firm_method = _read(network, "firm")
        if callable(firm_method):
            firm = firm_method(firm_id)
            name = _read(firm, "name", firm_id) or firm_id
            stage = _read(firm, "stage", firm_id) or firm_id
    except Exception:
        pass
    return name, stage


def takeover_offers(runner, state, player_id, **extra) -> dict:
    """Zeigt verfügbare Übernahmeangebote."""
    result = []
    try:
        offers = getattr(runner, "takeover_offers", []) or []
        runtimes = _read(_read(runner, "env"), "runtimes", {})
        player_runtime = _read(runtimes, player_id)
        cash = _number(_read(player_runtime, "cash", 0.0))
        for offer in offers:
            try:
                target = _read(offer, "target")
                if target is None or target == player_id:
                    continue
                runtime = _read(runtimes, target)
                try:
                    if runtime is not None and not bool(_read(runtime, "active")):
                        continue
                except Exception:
                    pass

                name, stage = _firm_details(runner, target)
                price = _number(_read(offer, "price"))
                result.append({
                    "target": target,
                    "name": name,
                    "stage": stage,
                    "price": round(price, 2),
                    "year": _read(offer, "year"),
                    "reason": _read(offer, "reason"),
                    "affordable": price <= cash,
                })
            except Exception:
                continue
    except Exception:
        pass
    return {"offers": result}


def assortment(runner, state, player_id, **extra) -> dict:
    """Zeigt Kategorien, Marktanteile und Lagerbestand."""
    category_names = {
        "beer": "Bier",
        "wine": "Wein",
        "spirits": "Spirituosen",
        "softdrinks": "Softdrinks",
        "water": "Wasser",
    }
    keys = list(category_names)
    unit = _unit(runner)
    note = None
    stocks = {key: 0.0 for key in keys}

    try:
        stock_method = _read(_read(runner, "env"), "stock_by_category")
        if callable(stock_method):
            raw_stock = stock_method(player_id)
            for key in keys:
                stocks[key] = _number(_read(raw_stock, key, 0.0)) * unit
        else:
            note = "Lager nach Kategorie nicht verfügbar"
    except Exception:
        note = "Lager nach Kategorie nicht verfügbar"

    shares = {key: 0.0 for key in keys}
    try:
        player_choices = _read(runner, "player_choices", {})
        choices = _read(player_choices, player_id)
        category_shares = _read(choices, "category_shares")
        if isinstance(category_shares, dict):
            values = {key: max(0.0, _number(category_shares.get(key, 0.0))) for key in keys}
            total = sum(values.values())
            if total > 0:
                shares = {key: values[key] / total for key in keys}
            else:
                total_stock = sum(max(0.0, stocks[key]) for key in keys)
                if total_stock > 0:
                    shares = {key: max(0.0, stocks[key]) / total_stock for key in keys}
        else:
            total_stock = sum(max(0.0, stocks[key]) for key in keys)
            if total_stock > 0:
                shares = {key: max(0.0, stocks[key]) / total_stock for key in keys}
    except Exception:
        pass

    market_totals = {key: 0.0 for key in keys}
    try:
        network = _read(runner, "network")
        firm_method = _read(network, "firm")
        player_firm = firm_method(player_id) if callable(firm_method) else None
        player_stage = _read(player_firm, "stage")
        firms_method = _read(runner, "_firms")
        firms = firms_method() if callable(firms_method) else []
        recent_sales = _read(state, "recent_sales", {})
        runtimes = _read(_read(runner, "env"), "runtimes", {})
        for firm in firms:
            try:
                if _read(firm, "stage") != player_stage:
                    continue
                category = _read(firm, "category")
                if category not in market_totals:
                    continue
                runtime = _read(runtimes, _read(firm, "id"))
                if runtime is not None and not bool(_read(runtime, "active", True)):
                    continue
                market_totals[category] += max(
                    0.0, _number(_read(recent_sales, _read(firm, "id"), 0.0))
                )
            except Exception:
                continue
    except Exception:
        market_totals = {key: 0.0 for key in keys}

    total_market = sum(market_totals.values())
    if total_market > 0:
        share_market = {
            key: round(max(0.0, min(1.0, market_totals[key] / total_market)), 3)
            for key in keys
        }
    else:
        equal_share = 1.0 / len(keys)
        share_market = {key: round(equal_share, 3) for key in keys}

    categories = []
    for key in keys:
        categories.append({
            "key": key,
            "name": category_names[key],
            "share_market": share_market[key],
            "share_mine": round(max(0.0, min(1.0, shares[key])), 3),
            "stock_bottles": stocks[key],
        })
    result = {"categories": categories}
    if note is not None:
        result["note"] = note
    return result


def _setting(settings, name, default=None):
    return _read(settings, name, default)


def _expand_quantity(value) -> float:
    if isinstance(value, dict):
        for key in ("quantity", "amount", "bottles", "capacity"):
            if key in value:
                return _number(value[key])
        return 0.0
    return _number(value)


def check_plan(
    runner,
    state,
    player_id,
    settings: dict,
    choices: dict,
    orders: dict,
    unit_size: int,
    snapshot,
) -> list[dict]:
    """Prüft Entscheide und gibt Warnungen für den nächsten Zug zurück."""
    warnings = []

    def warn(level: str, text: str):
        warnings.append({"level": level, "text": text})

    try:
        unit = int(unit_size)
        if unit <= 0:
            unit = 1
    except Exception:
        unit = 1

    try:
        order_qty = _setting(settings, "order_qty")
        if order_qty is not None:
            order_qty = _number(order_qty)
            sales_bottles = max(1.0, _number(_read(snapshot, "recent_sales", 0.0)) * unit)
            env = _read(runner, "env")
            capacity = 0.0
            try:
                capacity = _number(env._effective_capacity(player_id)) * unit
            except Exception:
                capacity = 0.0
            if order_qty > 3 * sales_bottles or (capacity > 0 and order_qty > 3 * capacity):
                warn(
                    "gelb",
                    "Bestellmenge ist deutlich höher als dein Absatz/deine Kapazität "
                    f"({order_qty:.0f} Flaschen; Absatz {sales_bottles:.0f}, "
                    f"Kapazität {capacity:.0f} Flaschen pro Tag)",
                )
    except Exception:
        pass

    try:
        sell_price = _setting(settings, "base_price")
        if sell_price is None:
            sell_price = _read(snapshot, "sell_price")
        if sell_price is not None:
            sell_price = _number(sell_price)
            cal = _financial_call("calculation", runner, player_id)
            full_cost = _read(cal, "full_cost")
            if full_cost is not None:
                full_cost = _number(full_cost)
                if sell_price < full_cost:
                    warn(
                        "rot",
                        f"Dein Preis liegt unter den Selbstkosten ({full_cost:.2f} CHF)",
                    )
                margin_pct = (sell_price - full_cost) / sell_price * 100 if sell_price > 0 else -100.0
                if margin_pct < -30:
                    warn(
                        "rot",
                        f"Deine Marge liegt bei {margin_pct:.2f} % und damit unter -30 %",
                    )
    except Exception:
        pass

    try:
        if (
            _number(_read(snapshot, "inventory", 0)) == 0
            and _number(_read(snapshot, "recent_demand", 0)) > 0
        ):
            warn("gelb", "Das Lager ist leer")
    except Exception:
        pass

    try:
        buy_order = _read(orders, "buy")
        if buy_order:
            target = buy_order
            if isinstance(buy_order, dict):
                target = buy_order.get("target", buy_order.get("id"))
            price = None
            try:
                from market_sim.game import holding_player

                for item in holding_player.buy_targets(runner, state, player_id):
                    if item.get("id") == target:
                        price = item.get("price")
                        break
            except Exception:
                pass
            if price is None:
                offers = getattr(runner, "takeover_offers", []) or []
                for offer in offers:
                    if _read(offer, "target") == target:
                        price = _read(offer, "price")
                        break
            if price is not None and _number(price) > _number(_read(snapshot, "cash", 0.0)):
                warn("rot", "Für diesen Kauf fehlt das Geld")
    except Exception:
        pass

    try:
        env = _read(runner, "env")
        capacity = 0.0
        try:
            capacity = _number(env._effective_capacity(player_id)) * unit
        except Exception:
            capacity = 0.0
        expand_order = _read(orders, "expand")
        if expand_order is None:
            expand_order = _read(choices, "expand_order")
        expand_qty = _expand_quantity(expand_order)
        if capacity > 0 and expand_qty > 3 * capacity:
            warn(
                "gelb",
                f"Der Ausbauauftrag ist mit {expand_qty:.0f} Flaschen höher als "
                f"das Dreifache der Kapazität ({capacity:.0f} Flaschen pro Tag)",
            )
    except Exception:
        pass

    try:
        price = _setting(settings, "base_price")
        if price is None:
            price = _read(snapshot, "sell_price")
        if price is not None:
            network = _read(runner, "network")
            firm_method = _read(network, "firm")
            firm = firm_method(player_id) if callable(firm_method) else None
            stage = _read(firm, "stage")
            stage_prices = _read(_read(runner, "config"), "stage_prices", {})
            band = _read(stage_prices, stage)
            minimum = _read(band, "min")
            maximum = _read(band, "max")
            if isinstance(band, (tuple, list)) and len(band) >= 2:
                minimum, maximum = band[0], band[1]
            price = _number(price)
            if minimum is not None and price < _number(minimum):
                warn(
                    "gelb",
                    f"Dein Preis von {price:.2f} CHF liegt unter dem Preisband "
                    f"von { _number(minimum):.2f} bis { _number(maximum):.2f} CHF",
                )
            elif maximum is not None and price > _number(maximum):
                warn(
                    "gelb",
                    f"Dein Preis von {price:.2f} CHF liegt über dem Preisband "
                    f"von { _number(minimum):.2f} bis { _number(maximum):.2f} CHF",
                )
    except Exception:
        pass

    return warnings
