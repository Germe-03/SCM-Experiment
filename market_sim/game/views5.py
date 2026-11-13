from __future__ import annotations

import dataclasses
import math


__all__ = ["production", "contracts", "brand_marketing", "contract_notices"]


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
        return result if math.isfinite(result) else default
    except Exception:
        return default


def _round(value, digits: int = 2) -> float:
    result = _number(value)
    rounded = round(result, digits)
    return rounded if math.isfinite(rounded) else 0.0


def _unit(runner) -> int:
    try:
        value = int(runner.config.unit_scale.real_units_per_sim_unit)
        return value if value >= 1 else 1
    except Exception:
        return 1


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    try:
        method = getattr(value, "to_dict", None)
        if callable(method):
            result = method()
            if isinstance(result, dict):
                return result
    except Exception:
        pass
    try:
        result = dataclasses.asdict(value)
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    try:
        result = vars(value)
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    return {}


def _firm_name(runner, firm_id):
    try:
        firm = runner.network.firm(firm_id)
        return _read(firm, "name", firm_id) or firm_id
    except Exception:
        return firm_id


def _contract_items(value):
    if isinstance(value, dict):
        return list(value.values())
    try:
        return list(value or [])
    except Exception:
        return []


def _collect_contracts(runner, player_id) -> list[dict]:
    try:
        book = getattr(runner, "contracts", None)
        if book is None:
            return []

        collected = []
        seen_ids = set()

        def add_items(items):
            for item in _contract_items(items):
                data = _as_dict(item)
                if not data:
                    continue
                if data.get("supplier") != player_id and data.get("buyer") != player_id:
                    continue
                contract_id = data.get("id")
                key = contract_id if contract_id is not None else (
                    data.get("supplier"),
                    data.get("buyer"),
                    data.get("start_day"),
                    data.get("proposed_by"),
                )
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                collected.append(data)

        try:
            method = getattr(book, "all_for", None)
            if callable(method):
                add_items(method(player_id))
        except Exception:
            pass

        try:
            add_items(getattr(book, "contracts", None))
        except Exception:
            pass

        if not collected:
            try:
                method = getattr(book, "active_for", None)
                if callable(method):
                    add_items(method(player_id))
            except Exception:
                pass

        return collected
    except Exception:
        return []


def _partner_for_contract(contract: dict, player_id):
    supplier = contract.get("supplier")
    buyer = contract.get("buyer")
    if supplier == player_id:
        return buyer, "Kunde"
    if buyer == player_id:
        return supplier, "Lieferant"
    return None, None


def _contract_output(contract: dict, player_id, unit: int, runner=None) -> dict:
    result = {}
    fields = (
        "id",
        "supplier",
        "buyer",
        "category",
        "units_per_day",
        "price",
        "start_day",
        "days",
        "status",
        "proposed_by",
    )
    for name in fields:
        value = contract.get(name)
        if name == "units_per_day":
            value = _round(_number(value) * unit, 2)
        elif name == "price":
            value = _round(value, 4)
        result[name] = value
    ordered = _number(contract.get("ordered")) * unit
    delivered = _number(contract.get("delivered")) * unit
    result["ordered"] = _round(ordered, 2)
    result["delivered"] = _round(delivered, 2)
    result["shortfall"] = _round(max(0.0, ordered - delivered), 2)

    change = contract.get("change")
    if isinstance(change, dict):
        result["change"] = {
            "units_per_day": _round(_number(change.get("units_per_day")) * unit, 2),
            "price": _round(change.get("price"), 4),
            "proposed_by": change.get("proposed_by"),
            "day": change.get("day"),
            "by_me": change.get("proposed_by") == player_id,
        }
    else:
        result["change"] = None

    partner_id, role = _partner_for_contract(contract, player_id)
    result["partner_name"] = _firm_name(runner, partner_id) if runner is not None else partner_id
    result["role"] = role
    return result


def _firm_name_from_id(firm_id):
    return firm_id


def _firm_details(runner, firm_id):
    try:
        firm = runner.network.firm(firm_id)
        return (
            _read(firm, "name", firm_id) or firm_id,
            _read(firm, "stage", firm_id) or "",
            _number(_read(firm, "sell_price", 0.0)),
        )
    except Exception:
        return firm_id, "", 0.0


def production(runner, state, player_id, **extra) -> dict:
    """Zeigt Produktionskapazität, Rohstoffe und Kosten pro Flasche."""
    try:
        unit = _unit(runner)
        env = runner.env
        firm = runner.network.firm(player_id)
        runtime = env.runtimes[player_id]

        cap_sim = max(0.0, _number(env._effective_capacity(player_id)))
        capacity_per_day = cap_sim * unit

        amounts = env._component_names(player_id)
        if not isinstance(amounts, dict):
            amounts = {}
        stock = env.component_stock(player_id)
        if not isinstance(stock, dict):
            stock = {}
        prices = env.component_prices(player_id)
        if not isinstance(prices, dict):
            prices = {}
        need = env.component_need(player_id, capacity_per_day)
        if not isinstance(need, dict):
            need = {}

        producible_sim = cap_sim
        positive_amounts = [
            (name, _number(amount))
            for name, amount in amounts.items()
            if _number(amount) > 0
        ]
        if positive_amounts:
            producible_sim = min(
                cap_sim,
                min(
                    max(0.0, _number(stock.get(name, 0.0))) / amount
                    for name, amount in positive_amounts
                ),
            )
        producible_per_day = producible_sim * unit
        # Ohne eigenen Rohstoffplan kauft die Firma automatisch, was die Produktion braucht:
        # dann ist die volle Kapazität produzierbar (solange das Geld reicht).
        try:
            plan = getattr(getattr(runner, "player_choices", {}).get(player_id), "component_plan", None)
            if not plan:
                producible_per_day = max(producible_per_day, float(env._effective_capacity(player_id)) * unit)
        except Exception:
            pass

        labels = {
            "hopfen": "Hopfen",
            "hops": "Hopfen",
            "malz": "Malz",
            "malt": "Malz",
            "wasser": "Wasser",
            "water": "Wasser",
            "energie": "Energie",
            "energy": "Energie",
            "strom": "Energie",
            "electricity": "Energie",
        }
        materials = []
        for name in sorted(amounts, key=lambda item: str(item)):
            amount = _number(amounts.get(name))
            price = _number(prices.get(name, 0.0))
            trend = "im Schnitt"
            try:
                commodity_level = _number(env.commodity_level(name), 1.0)
                if commodity_level < 0.92:
                    trend = "günstig"
                elif commodity_level > 1.08:
                    trend = "teuer"
            except Exception:
                pass
            label = labels.get(str(name).lower(), str(name).capitalize())
            materials.append({
                "name": name,
                "label": label,
                "stock": _round(stock.get(name, 0.0), 4),
                "need_per_day_at_capacity": _round(need.get(name, 0.0), 4),
                "price": _round(price, 4),
                "price_trend": trend,
                "cost_per_bottle": _round(price * amount / unit, 4),
            })

        energy = 0.0
        try:
            energy = max(0.0, _number(env.electricity_cost_per_unit(player_id)) / unit)
        except Exception:
            pass

        material_cost = 0.0
        try:
            material_cost = max(
                0.0,
                _number(env.unit_production_cost(firm)) / unit - energy,
            )
        except Exception:
            pass

        wages = 0.0
        fixed = 0.0
        handling = 0.0
        income = {}
        calculation = {}
        try:
            from market_sim import financials

            income = financials.income_statement(runner, player_id, None) or {}
        except Exception:
            income = {}
        try:
            from market_sim import financials

            calculation = financials.calculation(runner, player_id) or {}
        except Exception:
            calculation = {}

        sell_price = max(0.0, _number(_read(firm, "sell_price", 0.0)))
        revenue = max(0.0, _number(_read(income, "revenue", 0.0)))
        bottles_sold_ytd = revenue / sell_price if revenue > 0 and sell_price > 0 else 0.0
        if bottles_sold_ytd > 0:
            wages = _number(_read(income, "wages", 0.0)) / bottles_sold_ytd
            fixed = (
                _number(_read(income, "rent_fixed", 0.0))
                + _number(_read(income, "storage", 0.0))
            ) / bottles_sold_ytd
        else:
            wages = max(0.0, _number(_read(calculation, "overhead", 0.0)))
        handling = max(0.0, _number(_read(calculation, "procurement_costs", 0.0)))

        costs = {
            "materials": material_cost,
            "energy": energy,
            "wages": wages,
            "fixed": fixed,
            "handling": handling,
        }
        costs["total"] = sum(costs.values())

        orders_per_day = 0.0
        try:
            recent_demand = _read(state, "recent_demand", {})
            if isinstance(recent_demand, dict):
                demand = recent_demand.get(player_id, 0.0)
            else:
                demand = _read(recent_demand, player_id, 0.0)
            orders_per_day = max(0.0, _number(runner._moving_average(demand, 0.0)) * unit)
        except Exception:
            orders_per_day = 0.0

        stock_bottles = max(0.0, _number(_read(runtime, "inventory", 0.0)) * unit)
        days_of_cover = stock_bottles / orders_per_day if orders_per_day > 0 else None
        margin = sell_price - costs["total"]

        return {
            "capacity_per_day": int(round(capacity_per_day)),
            "producible_per_day": int(round(producible_per_day)),
            "materials": materials,
            "cost_per_bottle": {
                name: _round(value, 4) for name, value in costs.items()
            },
            "sell_price": _round(sell_price, 4),
            "margin_per_bottle": _round(margin, 4),
            "break_even_price": _round(costs["total"], 4),
            "orders_per_day": int(round(orders_per_day)),
            "stock_bottles": int(round(stock_bottles)),
            "days_of_cover": _round(days_of_cover, 4) if days_of_cover is not None else None,
        }
    except Exception:
        return {"error": "Produktionsdaten sind noch nicht verfügbar"}


def contracts(runner, state, player_id, **extra) -> dict:
    """Zeigt mögliche Vertragspartner und Lieferverträge."""
    try:
        env = runner.env
        unit = _unit(runner)
        book = getattr(runner, "contracts", None)
        network = runner.network
        player_firm = network.firm(player_id)
        player_stage = _read(player_firm, "stage", "")
        pairs = (
            ("factory", "distributor"),
            ("distributor", "wholesaler"),
            ("wholesaler", "retailer"),
        )
        stage_names = {
            "factory": "Hersteller",
            "distributor": "Verteiler",
            "wholesaler": "Grosshändler",
            "retailer": "Detailhändler",
        }
        partners = []
        try:
            firms = runner._firms()
        except Exception:
            firms = []
        runtimes = _read(env, "runtimes", {})
        for firm in firms:
            try:
                firm_id = _read(firm, "id")
                if firm_id == player_id:
                    continue
                runtime = _read(runtimes, firm_id)
                if runtime is None or not bool(_read(runtime, "active", False)):
                    continue
                stage = _read(firm, "stage", "")
                role = None
                if any(player_stage == supplier and stage == buyer for supplier, buyer in pairs):
                    role = "Kunde"
                elif any(stage == supplier and player_stage == buyer for supplier, buyer in pairs):
                    role = "Lieferant"
                if role is None:
                    continue
                partners.append({
                    "id": firm_id,
                    "name": _read(firm, "name", firm_id) or firm_id,
                    "stage": stage_names.get(stage, stage),
                    "role": role,
                    "market_price": _round(_read(firm, "sell_price", 0.0), 4),
                })
            except Exception:
                continue
        partners.sort(key=lambda item: str(item.get("name", "")))
        try:
            if book is not None and callable(getattr(book, "partners", None)):
                partners = [dict(p, stage=stage_names.get(p.get("stage"), p.get("stage")))
                            for p in book.partners(player_id)]
        except Exception:
            pass

        if book is None:
            return {
                "partners": partners,
                "active": [],
                "offers": [],
                "proposed": [],
                "note": "Lieferverträge sind noch nicht verfügbar",
            }

        active = []
        offers = []
        proposed = []
        for contract in _collect_contracts(runner, player_id):
            try:
                status = contract.get("status")
                proposed_by = contract.get("proposed_by")
                output = _contract_output(contract, player_id, unit, runner)
                if status == "aktiv":
                    active.append(output)
                elif status == "angeboten" and proposed_by != player_id:
                    offers.append(output)
                elif status == "angeboten" and proposed_by == player_id:
                    proposed.append(output)
            except Exception:
                continue

        return {
            "partners": partners,
            "active": active,
            "offers": offers,
            "proposed": proposed,
        }
    except Exception:
        return {
            "partners": [],
            "active": [],
            "offers": [],
            "proposed": [],
        }


def _choices_for(runner, player_id):
    choices_by_player = _read(runner, "player_choices", {})
    return _read(choices_by_player, player_id)


def brand_marketing(runner, state, player_id, **extra) -> dict:
    """Zeigt Markenbekanntheit, Qualität und Marketingbudget."""
    empty_choices = {
        "marketing_budget": None,
        "marketing_focus": None,
        "marketing_target": None,
    }
    try:
        choices = _choices_for(runner, player_id)
        choice_values = {
            "marketing_budget": _read(choices, "marketing_budget"),
            "marketing_focus": _read(choices, "marketing_focus"),
            "marketing_target": _read(choices, "marketing_target"),
        }

        env = runner.env
        book = _read(env, "brand_book")
        if book is None or not bool(_read(book, "categories_on", False)):
            return {"brands": [], "choices": choice_values or empty_choices}

        firm = runner.network.firm(player_id)
        category = _read(firm, "category")
        brands_by_id = _read(book, "brands", {})
        if not isinstance(brands_by_id, dict):
            brands_by_id = {}

        awareness_map = _read(book, "awareness", {})
        if not isinstance(awareness_map, dict):
            awareness_map = {}
        start_awareness = _read(_read(_read(runner, "config"), "marketing"), "start_awareness", 0.0)

        brand_units = _read(book, "brand_units")
        if not isinstance(brand_units, dict):
            brand_units = _read(env, "brand_units", {})
        if not isinstance(brand_units, dict):
            brand_units = _read(runner, "brand_units", {})
        if not isinstance(brand_units, dict):
            brand_units = {}

        category_brands = [
            (brand_id, brand)
            for brand_id, brand in brands_by_id.items()
            if _read(brand, "category") == category
        ]
        total_units = sum(
            max(0.0, _number(brand_units.get(brand_id, 0.0)))
            for brand_id, _brand in category_brands
        )

        marketing = _read(runner, "marketing")
        daily_budget = _read(marketing, "daily_budget", {})
        if not isinstance(daily_budget, dict):
            daily_budget = {}
        days_per_year = max(
            0.0,
            _number(_read(_read(_read(runner, "config"), "simulation"), "days_per_year", 0.0)),
        )

        brands = []
        for brand_id, brand in category_brands:
            try:
                owner = _read(brand, "owner")
                owner_name = _firm_name(runner, owner)
                owner_choice = _read(_read(runner, "player_choices", {}), owner)
                owner_budget = _read(owner_choice, "marketing_budget")
                if owner_budget is not None:
                    marketing_budget_year = max(0.0, _number(owner_budget))
                else:
                    marketing_budget_year = max(
                        0.0,
                        _number(daily_budget.get(owner, 0.0)) * days_per_year,
                    )

                quality = 0.0
                try:
                    quality = _number(book.quality(brand, env))
                except Exception:
                    pass

                try:
                    owner_firm = runner.network.firm(owner)
                    price = _number(_read(owner_firm, "sell_price", 0.0))
                except Exception:
                    price = 0.0

                awareness = _number(awareness_map.get(brand_id, start_awareness))
                share = (
                    max(0.0, _number(brand_units.get(brand_id, 0.0))) / total_units
                    if total_units > 0
                    else 0.0
                )
                brands.append({
                    "id": brand_id,
                    "name": _read(brand, "name", brand_id) or brand_id,
                    "owner": owner_name,
                    "is_mine": owner == player_id,
                    "awareness": _round(awareness, 4),
                    "reputation": _round(_read(brand, "reputation", 0.0), 4),
                    "quality": _round(quality, 4),
                    "price": _round(price, 4),
                    "share_of_sales": _round(share, 4),
                    "marketing_budget_year": _round(marketing_budget_year, 2),
                })
            except Exception:
                continue

        brands.sort(
            key=lambda item: (
                not item["is_mine"],
                -_number(item["awareness"]),
                str(item["id"]),
            )
        )
        return {
            "category": category,
            "brands": brands,
            "choices": choice_values,
            # Verlauf je Runde (vom Controller gemerkt): Bekanntheit und Absatzanteil je Marke.
            "history": list(extra.get("brand_history") or []),
        }
    except Exception:
        return {"brands": [], "choices": empty_choices}


def contract_notices(runner, state, player_id, seen: set, year: int, month: int) -> list[dict]:
    """Erstellt Hinweise zu neuen und beendeten Lieferverträgen."""
    try:
        if getattr(runner, "contracts", None) is None:
            return []
        unit = _unit(runner)
        notices = []
        for contract in _collect_contracts(runner, player_id):
            try:
                contract_id = contract.get("id")
                status = contract.get("status")
                proposed_by = contract.get("proposed_by")
                partner_id, _role = _partner_for_contract(contract, player_id)
                partner_name = _firm_name(runner, partner_id)

                if status == "angeboten" and proposed_by != player_id:
                    key = ("vertrag-angebot", contract_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    quantity = _number(contract.get("units_per_day")) * unit
                    price = _number(contract.get("price"))
                    text = (
                        f"Neues Vertragsangebot von {partner_name}: "
                        f"{round(quantity):,} Flaschen pro Tag zu CHF {price:.2f}. "
                        "Im Reiter Verträge annehmen oder ablehnen."
                    ).replace(",", "'")
                    notices.append({
                        "year": year,
                        "month": month,
                        "level": "gelb",
                        "kind": "vertrag",
                        "text": text,
                    })
                elif status == "aktiv" and (contract.get("change") or contract.get("change_result")):
                    change = contract.get("change")
                    result = contract.get("change_result")
                    if change and change.get("proposed_by") != player_id:
                        key = ("vertrag-aenderung", contract_id, change.get("day"))
                        if key not in seen:
                            seen.add(key)
                            text = (
                                f"{partner_name} schlägt eine Vertragsanpassung vor: "
                                f"{round(_number(change.get('units_per_day')) * unit):,} Flaschen pro Tag "
                                f"zu CHF {_number(change.get('price')):.2f}, Laufzeit {int(_number(change.get('days')))} Tage ab Annahme. "
                                "Im Reiter Verträge annehmen oder ablehnen."
                            ).replace(",", "'")
                            notices.append({"year": year, "month": month, "level": "gelb",
                                            "kind": "vertrag", "text": text})
                    if result and result.get("proposed_by") == player_id:
                        key = ("vertrag-aenderung-ende", contract_id, result.get("day"), result.get("status"))
                        if key not in seen:
                            seen.add(key)
                            word = "angenommen" if result.get("status") == "angenommen" else "abgelehnt"
                            notices.append({"year": year, "month": month, "level": "info", "kind": "vertrag",
                                            "text": f"{partner_name} hat deine Vertragsanpassung {word}."})
                elif status in ("beendet", "abgelehnt"):
                    if status == "abgelehnt" and proposed_by != player_id:
                        continue
                    key = ("vertrag-ende", contract_id, status)
                    if key in seen:
                        continue
                    seen.add(key)
                    if status == "beendet":
                        text = f"Der Liefervertrag mit {partner_name} ist beendet" + (f" ({contract.get('end_reason')})" if contract.get("end_reason") else "") + "."
                    else:
                        text = f"{partner_name} hat deinen Vertragsvorschlag abgelehnt."
                    notices.append({
                        "year": year,
                        "month": month,
                        "level": "info",
                        "kind": "vertrag",
                        "text": text,
                    })
            except Exception:
                continue
        return notices
    except Exception:
        return []
