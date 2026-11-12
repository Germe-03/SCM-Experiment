from __future__ import annotations

import math


__all__ = ["inventory", "brand_sources"]


_CATEGORY_NAMES = {
    "beer": "Bier",
    "wine": "Wein",
    "spirits": "Spirituosen",
    "softdrinks": "Softdrinks",
    "water": "Wasser",
}

_ROHSTOFFE_DE = {
    "co2": "CO2",
    "cork": "Kork",
    "fruit": "Früchte",
    "grapes": "Trauben",
    "hops": "Hopfen",
    "malt": "Malz",
    "packaging": "Verpackung",
    "glass": "Glas",
    "sugar": "Zucker",
    "water": "Wasser",
    "wheat": "Weizen",
    "barley": "Gerste",
    "electricity": "Strom",
    "energy": "Energie",
    "aluminium": "Aluminium",
    "pet": "PET",
    "yeast": "Hefe",
    "grain": "Getreide",
    "potatoes": "Kartoffeln",
    "wood": "Holz",
    "labels": "Etiketten",
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


def _method(obj, name: str, *args, default=None):
    try:
        function = getattr(obj, name, None)
        if callable(function):
            return function(*args)
    except Exception:
        pass
    return default


def _firm(runner, firm_id):
    try:
        network = getattr(runner, "network", None)
        function = getattr(network, "firm", None)
        if callable(function):
            return function(firm_id)
    except Exception:
        pass
    return None


def _player_choices(runner, player_id):
    try:
        choices = getattr(runner, "player_choices", {})
        if isinstance(choices, dict):
            return choices.get(player_id)
    except Exception:
        pass
    return None


def _empty_inventory() -> dict:
    return {
        "kind": "haendler",
        "summary": {
            "bottles": 0,
            "value_chf": 0,
            "capacity": 0,
            "used": 0,
            "days_of_cover": 0,
            "in_transit": 0,
        },
        "brands": [],
        "components": [],
        "history": [],
        "warnings": [],
    }


def _history_bottles(entry, brand_id):
    brands = _read(entry, "brands", {})
    if not isinstance(brands, dict):
        return 0.0
    if brand_id in brands:
        return _number(brands.get(brand_id))
    key = str(brand_id)
    return _number(brands.get(key))


def inventory(runner, state, player_id, **extra) -> dict:
    """Zeigt Lagerbestand, Verlauf und Warnungen."""
    try:
        env = getattr(runner, "env", None)
        runtime = _read(_read(env, "runtimes", {}), player_id)
        stock = _read(runtime, "stock", {})
        if not isinstance(stock, dict):
            stock = {}

        unit = _unit(runner)
        book = _read(env, "brand_book")
        brand_book = _read(book, "brands", {})
        if not isinstance(brand_book, dict):
            brand_book = {}

        catalog = _method(book, "brand_catalog", runner, player_id, default=[])
        if not isinstance(catalog, list):
            catalog = []
        prices = {}
        for row in catalog:
            if isinstance(row, dict):
                prices[row.get("id")] = _number(row.get("price"))
                prices[str(row.get("id"))] = _number(row.get("price"))

        incoming_by_brand = {}
        incoming = _read(runtime, "incoming_brands", [])
        if isinstance(incoming, (list, tuple)):
            for entry in incoming:
                if not isinstance(entry, dict):
                    continue
                for brand_id, amount in entry.items():
                    incoming_by_brand[brand_id] = (
                        incoming_by_brand.get(brand_id, 0.0) + _number(amount)
                    )

        history = extra.get("stock_history", [])
        if not isinstance(history, list):
            history = []
        history = [entry for entry in history if isinstance(entry, dict)]

        firm = _firm(runner, player_id)
        kind = "hersteller" if _read(firm, "stage") == "factory" else "haendler"
        brand_ids = set(stock) | set(incoming_by_brand)
        brand_rows = []

        days_per_year = max(
            1.0,
            _number(_read(_read(_read(runner, "config"), "simulation"), "days_per_year"), 1),
        )
        days_per_round = days_per_year / 12.0

        for brand_id in brand_ids:
            try:
                stock_bottles = max(
                    0, int(round(max(0.0, _number(stock.get(brand_id))) * unit))
                )
                transit_bottles = max(
                    0,
                    int(round(max(0.0, _number(incoming_by_brand.get(brand_id))) * unit)),
                )
                if stock_bottles <= 0 and transit_bottles <= 0:
                    continue

                brand = brand_book.get(brand_id)
                if brand is None:
                    brand = brand_book.get(str(brand_id))
                category = _read(brand, "category", "")
                name = _read(brand, "name", brand_id) or brand_id

                # Verkauf pro Tag: tatsächlicher Tagesabsatz der Firma, aufgeteilt nach dem Einkaufsplan
                # (sonst nach Lager + unterwegs). Der Lagerabgang allein zeigt 0, wenn alles sofort verkauft wird.
                sales_per_day = 0.0
                try:
                    runtime = runner.env.runtimes[player_id]
                    daily = max(0.0, float(getattr(runtime, "consumer_units_sold", 0) or 0)) * unit
                    choice = getattr(runner, "player_choices", {}).get(player_id)
                    plan = getattr(choice, "brand_plan", None) or {}
                    plan_total = sum(max(0.0, float(v or 0)) for v in plan.values())
                    if plan_total > 0:
                        sales_per_day = daily * max(0.0, float(plan.get(brand_id, 0) or 0)) / plan_total
                    else:
                        weights = {b: max(0.0, _number(v)) + max(0.0, _number(incoming_by_brand.get(b)))
                                   for b, v in dict(getattr(runtime, "stock", {}) or {}).items()}
                        total = sum(weights.values())
                        if total > 0:
                            sales_per_day = daily * weights.get(brand_id, 0.0) / total
                except Exception:
                    sales_per_day = 0.0
                if sales_per_day <= 0 and len(history) >= 2 and days_per_round > 0:
                    previous = _history_bottles(history[-2], brand_id)
                    current = _history_bottles(history[-1], brand_id)
                    sales_per_day = max(0.0, previous - current) / days_per_round

                unit_price = _number(prices.get(brand_id, prices.get(str(brand_id), 0)))
                unit_price = round(unit_price, 2)
                value_chf = round(stock_bottles * unit_price, 2)
                days_of_cover = (
                    round(stock_bottles / sales_per_day, 1)
                    if sales_per_day > 0
                    else (0 if stock_bottles <= 0 else 999)
                )

                brand_rows.append({
                    "id": _clean(brand_id),
                    "name": _clean(name),
                    "category": _clean(category),
                    "category_name": _clean(_CATEGORY_NAMES.get(category, str(category))),
                    "stock": stock_bottles,
                    "in_transit": transit_bottles,
                    "sales_per_day": round(sales_per_day, 2),
                    "days_of_cover": days_of_cover,
                    "unit_price": unit_price,
                    "value_chf": value_chf,
                })
            except Exception:
                continue

        brand_rows.sort(
            key=lambda row: (
                str(row["category"]),
                str(row["name"]).casefold(),
            )
        )

        components = []
        component_value = 0.0
        if kind == "hersteller":
            component_stock = _method(env, "component_stock", player_id, default={})
            component_prices = _method(env, "component_prices", player_id, default={})
            if not isinstance(component_stock, dict):
                component_stock = {}
            if not isinstance(component_prices, dict):
                component_prices = {}

            capacity_bottles_per_day = max(
                0.0,
                _number(_method(env, "_effective_capacity", player_id)) * unit,
            )
            component_need = _method(
                env,
                "component_need",
                player_id,
                capacity_bottles_per_day,
                default={},
            )
            if not isinstance(component_need, dict):
                component_need = {}

            for component_key, amount in component_stock.items():
                try:
                    component_amount = _number(amount)
                    use_per_day = _number(component_need.get(component_key))
                    price = round(_number(component_prices.get(component_key)), 2)
                    value_chf = round(component_amount * price, 2)
                    component_value += value_chf
                    components.append({
                        "name": _clean(
                            _ROHSTOFFE_DE.get(str(component_key), str(component_key))
                        ),
                        "stock": _clean(component_amount),
                        "use_per_day": _clean(use_per_day),
                        "days_of_cover": (
                            round(component_amount / use_per_day, 1)
                            if use_per_day > 0
                            else 999
                        ),
                        "price": price,
                        "value_chf": value_chf,
                    })
                except Exception:
                    continue
            components.sort(key=lambda row: str(row["name"]).casefold())

        bottles = sum(row["stock"] for row in brand_rows)
        in_transit_total = sum(row["in_transit"] for row in brand_rows)
        brand_value = sum(_number(row["value_chf"]) for row in brand_rows)
        total_sales_per_day = sum(_number(row["sales_per_day"]) for row in brand_rows)

        capacity = _number(_method(env, "storage_capacity", player_id))
        used = _number(_method(env, "storage_used", player_id))
        summary = {
            "bottles": int(bottles),
            "value_chf": round(brand_value + component_value, 2),
            "capacity": _clean(capacity),
            "used": _clean(used),
            "days_of_cover": (
                round(bottles / total_sales_per_day, 1)
                if total_sales_per_day > 0
                else 999
            ),
            "in_transit": int(in_transit_total),
        }

        history_rows = []
        category_names = set(_CATEGORY_NAMES.values())
        for entry in history[-120:]:
            row = {"label": _clean(_read(entry, "label", ""))}
            totals = {name: 0 for name in category_names}
            entry_brands = _read(entry, "brands", {})
            if isinstance(entry_brands, dict):
                for brand_id, amount in entry_brands.items():
                    brand = brand_book.get(brand_id)
                    if brand is None:
                        brand = brand_book.get(str(brand_id))
                    category = _read(brand, "category", "")
                    category_name = _CATEGORY_NAMES.get(category, str(category))
                    totals[category_name] = totals.get(category_name, 0) + max(
                        0, int(round(max(0.0, _number(amount))))
                    )
            row.update(totals)
            history_rows.append(row)

        choices = _player_choices(runner, player_id)
        brand_plan = _read(choices, "brand_plan", {})
        if not isinstance(brand_plan, dict):
            brand_plan = {}

        warnings = []
        previous_entry = history[-2] if len(history) >= 2 else None
        for row in brand_rows:
            brand_id = row["id"]
            plan_amount = brand_plan.get(brand_id, brand_plan.get(str(brand_id), 0))
            if isinstance(plan_amount, dict):
                plan_amount = _read(plan_amount, "amount", 0)
            had_previous_stock = (
                _history_bottles(previous_entry, brand_id) > 0
                if previous_entry is not None
                else False
            )
            if (
                row["stock"] == 0
                and (
                    _number(plan_amount) > 0
                    or _number(row["sales_per_day"]) > 0
                    or had_previous_stock
                )
            ):
                warnings.append({
                    "level": "rot",
                    "text": f'{row["name"]}: Lager leer',
                })

            cover = _number(row["days_of_cover"])
            if 30 < cover <= 998:
                warnings.append({
                    "level": "gelb",
                    "text": f'{row["name"]}: Lager reicht {int(cover)} Tage (über 30 Tage)',
                })

        if used > capacity:
            warnings.append({
                "level": "gelb",
                "text": "Lager ist über der Kapazität: Mietkosten fallen an",
            })

        return _clean({
            "kind": kind,
            "summary": summary,
            "brands": brand_rows,
            "components": components,
            "history": history_rows,
            "warnings": warnings[:20],
        })
    except Exception:
        return _empty_inventory()


def brand_sources(runner, state, player_id, **extra) -> dict:
    """Zeigt Lieferanten je Marke und Einkauf nach Lieferant."""
    try:
        env = getattr(runner, "env", None)
        book = _read(env, "brand_book")
        book_brands = _read(book, "brands", {})
        if not isinstance(book_brands, dict):
            book_brands = {}

        unit = _unit(runner)
        candidates = _method(env, "supplier_candidates", player_id, default=[])
        if not isinstance(candidates, (list, tuple)):
            try:
                candidates = list(candidates or [])
            except Exception:
                candidates = []

        runtime_map = _read(env, "runtimes", {})
        brand_sources_map = {}

        for brand_id, brand in book_brands.items():
            category = _read(brand, "category", "")
            if category not in _CATEGORY_NAMES:
                continue

            supplier_rows = []
            candidate_data = []
            for supplier in candidates:
                try:
                    supplier_id = _read(supplier, "id")
                    if supplier_id is None:
                        continue
                    supplier_runtime = _read(runtime_map, supplier_id)
                    supplier_stock = _read(supplier_runtime, "stock", {})
                    if not isinstance(supplier_stock, dict):
                        supplier_stock = {}

                    brand_sim_stock = max(0.0, _number(
                        supplier_stock.get(brand_id, supplier_stock.get(str(brand_id), 0))
                    ))
                    stock_bottles = max(0, int(round(brand_sim_stock * unit)))
                    total_sim_stock = sum(
                        max(0.0, _number(amount)) for amount in supplier_stock.values()
                    )
                    capacity = max(
                        0.0,
                        _number(_method(env, "_effective_capacity", supplier_id)) * unit,
                    )
                    deliverable = (
                        int(round(capacity * brand_sim_stock / total_sim_stock))
                        if total_sim_stock > 0
                        else 0
                    )

                    price = _method(
                        book,
                        "retail_price",
                        _read(supplier, "sell_price", 0),
                        brand,
                        default=0,
                    )
                    price = round(_number(price), 2)

                    delivery_book = _read(env, "delivery_book", {})
                    player_deliveries = (
                        delivery_book.get(player_id, {})
                        if isinstance(delivery_book, dict)
                        else {}
                    )
                    if not isinstance(player_deliveries, dict):
                        player_deliveries = {}
                    delivery = player_deliveries.get(
                        supplier_id,
                        player_deliveries.get(str(supplier_id)),
                    )
                    delivery = delivery if isinstance(delivery, dict) else {}
                    ordered = _number(delivery.get("ordered"))
                    delivered = _number(delivery.get("delivered"))
                    fill_rate = (
                        1.0
                        if delivery is None or ordered == 0
                        else max(0.0, min(1.0, delivered / ordered))
                    )

                    supplier_name = _read(supplier, "name", supplier_id) or supplier_id
                    row = {
                        "supplier_id": _clean(supplier_id),
                        "supplier_name": _clean(supplier_name),
                        "price": price,
                        "stock": stock_bottles,
                        "deliverable_per_day": deliverable,
                        "fill_rate": round(fill_rate, 3),
                    }
                    candidate_data.append((stock_bottles, row))
                except Exception:
                    continue

            has_stock = any(stock > 0 for stock, _ in candidate_data)
            for stock, row in candidate_data:
                if stock > 0 or not has_stock:
                    supplier_rows.append(row)
            supplier_rows.sort(key=lambda row: row["price"])
            brand_sources_map[str(brand_id)] = supplier_rows

        runtime = _read(runtime_map, player_id)
        paid_items = _read(runtime, "paid_items", {})
        if not isinstance(paid_items, dict):
            paid_items = {}

        grouped = {}
        for key, value in paid_items.items():
            try:
                if not isinstance(key, str) or "|" not in key:
                    continue
                partner, category = key.split("|", 1)
                supplier = _firm(runner, partner)
                if supplier is None:
                    continue
                units = _number(_read(value, "units", 0))
                group = grouped.setdefault(partner, {})
                group[category] = group.get(category, 0.0) + units * unit
            except Exception:
                continue

        delivery_book = _read(env, "delivery_book", {})
        player_deliveries = (
            delivery_book.get(player_id, {})
            if isinstance(delivery_book, dict)
            else {}
        )
        if not isinstance(player_deliveries, dict):
            player_deliveries = {}

        by_supplier = []
        for supplier_id, category_delivered in grouped.items():
            try:
                supplier = _firm(runner, supplier_id)
                if supplier is None:
                    continue
                categories = sorted(category_delivered)
                delivered_by_category = {
                    category: max(
                        0, int(round(max(0.0, _number(category_delivered[category]))))
                    )
                    for category in categories
                }
                total_category_delivered = sum(delivered_by_category.values())

                delivery = player_deliveries.get(
                    supplier_id,
                    player_deliveries.get(str(supplier_id)),
                )
                if isinstance(delivery, dict):
                    delivered_total = max(
                        0, int(round(max(0.0, _number(delivery.get("delivered"))) * unit))
                    )
                    ordered_total = max(
                        0, int(round(max(0.0, _number(delivery.get("ordered"))) * unit))
                    )
                    open_total = max(
                        0, int(round(max(0.0, _number(delivery.get("open"))) * unit))
                    )
                else:
                    delivered_total = total_category_delivered
                    ordered_total = delivered_total
                    open_total = 0

                allocated_ordered = {}
                allocated_open = {}
                if categories:
                    if total_category_delivered > 0:
                        cumulative_delivered = 0
                        previous_ordered = 0
                        previous_open = 0
                        for category in categories:
                            cumulative_delivered += delivered_by_category[category]
                            order_boundary = int(round(
                                ordered_total * cumulative_delivered / total_category_delivered
                            ))
                            open_boundary = int(round(
                                open_total * cumulative_delivered / total_category_delivered
                            ))
                            allocated_ordered[category] = order_boundary - previous_ordered
                            allocated_open[category] = open_boundary - previous_open
                            previous_ordered = order_boundary
                            previous_open = open_boundary
                    else:
                        allocated_ordered = {category: 0 for category in categories}
                        allocated_open = {category: 0 for category in categories}
                        allocated_ordered[categories[0]] = ordered_total
                        allocated_open[categories[0]] = open_total

                category_rows = {}
                for category in categories:
                    category_rows[category] = {
                        "ordered": allocated_ordered.get(category, 0),
                        "delivered": delivered_by_category[category],
                        "open": allocated_open.get(category, 0),
                    }

                supplier_name = _read(supplier, "name", supplier_id) or supplier_id
                by_supplier.append({
                    "supplier_id": _clean(supplier_id),
                    "name": _clean(supplier_name),
                    "categories": category_rows,
                })
            except Exception:
                continue

        by_supplier.sort(key=lambda row: str(row["name"]).casefold())
        return _clean({
            "brands": brand_sources_map,
            "by_supplier": by_supplier,
        })
    except Exception:
        return {"brands": {}, "by_supplier": []}
