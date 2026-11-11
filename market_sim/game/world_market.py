from __future__ import annotations

import math

from market_sim.kpi import ARCHETYPE_DE


CH_OUTLINE = [
    [485, 118], [497, 128], [506, 136], [520, 153], [537, 168],
    [553, 187], [565, 203], [575, 220], [570, 240], [590, 252],
    [606, 262], [612, 268], [625, 270], [640, 272], [660, 276],
    [680, 283], [700, 287], [720, 280], [735, 276], [750, 270],
    [760, 264], [770, 250], [780, 240], [790, 230], [800, 224],
    [815, 220], [830, 210], [834, 195], [825, 180], [815, 170],
    [812, 155], [800, 145], [790, 140], [775, 140], [760, 130],
    [745, 118], [730, 112], [722, 100], [718, 80], [705, 77],
    [700, 90], [690, 105], [670, 115], [650, 112], [630, 100],
    [610, 92], [590, 90], [570, 96], [555, 105], [540, 112],
    [525, 115], [510, 113], [495, 112],
]


def _get(obj, key, default=None):
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    except Exception:
        return default


def _number(value, default=0.0):
    try:
        result = float(value)
        return round(result, 4) if math.isfinite(result) else default
    except Exception:
        return default


def _items(value):
    try:
        if isinstance(value, dict):
            return list(value.values())
        return list(value or [])
    except Exception:
        return []


def _config(runner):
    try:
        env = getattr(runner, "env", None)
        return getattr(runner, "config", None) or getattr(env, "config", None)
    except Exception:
        return None


def _firms(runner):
    try:
        firms = runner._firms()
        return _items(firms)
    except Exception:
        return []


def _firm(runner, fid):
    try:
        network = getattr(runner, "network", None)
        lookup = getattr(network, "firm", None)
        if callable(lookup):
            firm = lookup(fid)
            if firm is not None:
                return firm
    except Exception:
        pass
    for firm in _firms(runner):
        if _get(firm, "id") == fid:
            return firm
    return None


def _record(collection, fid):
    try:
        if isinstance(collection, dict):
            if fid in collection:
                return collection[fid]
            for key, value in collection.items():
                if str(key) == str(fid):
                    return value
            return None
        for item in _items(collection):
            if _get(item, "firm_id", _get(item, "id")) == fid:
                return item
    except Exception:
        pass
    return None


def _year_data(year):
    return year if isinstance(year, dict) else year or {}


def _last(summaries):
    try:
        if not summaries:
            return {}
        return _year_data(summaries[-1])
    except Exception:
        return {}


def _summaries(state):
    try:
        return list(getattr(state, "summaries", []) or [])
    except Exception:
        return []


def _reports(state):
    try:
        return list(getattr(state, "annual_reports", []) or [])
    except Exception:
        return []


def _branch(firm):
    stage = _get(firm, "stage")
    if stage == "factory":
        return "hersteller"
    if stage == "wholesaler":
        return "grosshaendler"
    if stage == "distributor":
        return "verteiler"
    if stage == "retailer":
        restaurant = (
            _get(firm, "channel") == "restaurant"
            or _get(firm, "category") == "restaurant"
            or bool(_get(firm, "restaurant", False))
        )
        return "gastro" if restaurant else "detailhaendler"
    return str(stage) if stage is not None else ""


def _firm_name(firm, fid):
    return _get(firm, "name") or str(fid)


def _summary_value(summary, key, default=0.0):
    return _number(_get(summary, key, default), default)


def _day_stats(values):
    numbers = [_number(value) for value in _items(values)]
    if not numbers:
        return {"min": 0.0, "max": 0.0, "avg": 0.0}
    return {
        "min": round(min(numbers), 4),
        "max": round(max(numbers), 4),
        "avg": round(sum(numbers) / len(numbers), 4),
    }


def _runtime_total(runtime, names):
    for name in names:
        value = _get(runtime, name)
        if value is None:
            continue
        try:
            if isinstance(value, dict):
                return round(sum(_number(item) for item in value.values()), 4)
            return _number(value)
        except Exception:
            continue
    return 0.0


def _recent(state, key, fid):
    try:
        return getattr(state, key, {}).get(fid, []) or []
    except Exception:
        return []


def _stock_info(runner, fid):
    listed = False
    price = None
    for market_name in ("stock_market", "exchange"):
        try:
            market = getattr(runner, market_name, None)
            if market is None:
                continue

            explicit_listed = None
            for name in ("is_listed", "listed"):
                value = _get(market, name)
                if callable(value):
                    try:
                        value = value(fid)
                    except Exception:
                        value = None
                if value is not None:
                    explicit_listed = bool(value)
                    break

            for name in ("stock_price", "price", "get_price", "price_for"):
                lookup = _get(market, name)
                if callable(lookup):
                    try:
                        value = lookup(fid)
                    except Exception:
                        continue
                    if value is not None:
                        price = _number(value, None)
                        listed = explicit_listed if explicit_listed is not None else True
                        return listed, price

            for name in ("prices", "stock_prices", "prices_by_firm"):
                prices = _get(market, name)
                if isinstance(prices, dict) and fid in prices:
                    price = _number(prices[fid], None)
                    listed = explicit_listed if explicit_listed is not None else price is not None
                    return listed, price

            if explicit_listed is not None:
                listed = explicit_listed
                if not listed:
                    return False, None
        except Exception:
            continue
    return listed, price


def compare(runner, state, player_id, **extra) -> dict:
    firms = _firms(runner)
    player = _firm(runner, player_id)
    stage = _get(player, "stage")
    summaries = _summaries(state)
    reports = _reports(state)
    latest_summary = _last(summaries)
    latest_report = _last(reports)
    same_stage = [firm for firm in firms if _get(firm, "stage") == stage]
    same_stage.sort(key=lambda firm: 0 if _get(firm, "id") == player_id else 1)
    rows = []

    for firm in same_stage:
        fid = _get(firm, "id")
        summary = _record(latest_summary, fid)
        report = _record(latest_report, fid)
        listed, stock_price = _stock_info(runner, fid)
        archetype = _get(report, "archetype", "") or ""
        row = {
            "id": fid,
            "name": _firm_name(firm, fid),
            "is_player": fid == player_id,
            "branch": _branch(firm),
            "region": _get(firm, "region"),
            "category": _get(firm, "category"),
            "revenue": _summary_value(summary, "revenue"),
            "market_share": _summary_value(summary, "market_share"),
            "avg_price": _summary_value(summary, "avg_sell_price"),
            "quality": _summary_value(summary, "quality"),
            "reputation": _number(_get(report, "reputation", 0.0)),
            "service_level": _summary_value(summary, "service_level"),
            "capacity_utilization": _summary_value(summary, "capacity_utilization"),
            "archetype": archetype,
            "archetype_label": ARCHETYPE_DE.get(archetype, archetype),
            "listed": listed,
            "stock_price": stock_price,
            "revenue_history": [
                _summary_value(_record(_year_data(year), fid), "revenue")
                for year in summaries
            ],
        }
        if fid == player_id:
            row["profit"] = _summary_value(summary, "profit")
        rows.append(row)

    return {
        "stage": stage,
        "rows": rows,
        "years": list(range(1, len(summaries) + 1)),
    }


def capacity(runner, state, player_id, **extra) -> dict:
    player = _firm(runner, player_id)
    stage = _get(player, "stage")
    env = _get(runner, "env")
    capacity_per_day = None
    try:
        capacity_per_day = _number(env._effective_capacity(player_id), None)
    except Exception:
        pass

    truck_capacity = None
    try:
        geography = _get(env, "geography")
        trucks = _get(geography, "trucks")
        lookup = _get(trucks, "capacity")
        if callable(lookup):
            truck_capacity = _number(lookup(player_id), None)
    except Exception:
        pass

    summaries = _summaries(state)
    last_summary = _record(_last(summaries), player_id)
    demand = _recent(state, "recent_demand", player_id)
    sales = _recent(state, "recent_sales", player_id)
    stage_firms = [firm for firm in _firms(runner) if _get(firm, "stage") == stage]
    stage_stats = [
        _day_stats(_recent(state, "recent_demand", _get(firm, "id")))
        for firm in stage_firms
    ]
    stage_demand = {
        key: round(sum(stats[key] for stats in stage_stats), 4)
        for key in ("min", "max", "avg")
    }

    runtime = None
    try:
        runtimes = _get(env, "runtimes", {})
        runtime = runtimes.get(player_id) if isinstance(runtimes, dict) else None
    except Exception:
        pass
    inventory = _runtime_total(runtime, ("inventory", "stock"))
    backlog = _runtime_total(runtime, ("backlog",))
    demand_stats = _day_stats(demand)
    sales_stats = _day_stats(sales)

    return {
        "capacity_per_day": capacity_per_day,
        "truck_capacity": truck_capacity,
        "utilization_last_year": _summary_value(last_summary, "capacity_utilization"),
        "demand": demand_stats,
        "sales": sales_stats,
        "stage_demand": stage_demand,
        "inventory": inventory,
        "backlog": backlog,
        "days_of_stock": round(inventory / sales_stats["avg"], 4)
        if sales_stats["avg"] > 0 else None,
    }


def market(runner, state, player_id, **extra) -> dict:
    player = _firm(runner, player_id)
    stage = _get(player, "stage")
    firms = [firm for firm in _firms(runner) if _get(firm, "stage") == stage]
    env = _get(runner, "env")
    categories = []
    try:
        brand_book = _get(env, "brand_book")
        base_share = _get(brand_book, "base_share", {})
        if isinstance(base_share, dict):
            categories = [
                {"name": str(name), "share": _number(share)}
                for name, share in base_share.items()
            ]
    except Exception:
        pass

    capacities = []
    prices = []
    rival_prices = []
    latest = _last(_summaries(state))
    for firm in firms:
        fid = _get(firm, "id")
        try:
            capacities.append(_number(env._effective_capacity(fid)))
        except Exception:
            pass
        average_demand = _day_stats(_recent(state, "recent_demand", fid))["avg"]
        demand_value = average_demand
        summary = _record(latest, fid)
        price = _number(_get(summary, "avg_sell_price", 0.0))
        if price > 0:
            prices.append(price)
            if fid != player_id:
                rival_prices.append(price)
        # Keep the demand sum independent of whether a firm has a summary.
        if demand_value < 0:
            demand_value = 0.0

    stage_demand = sum(
        _day_stats(_recent(state, "recent_demand", _get(firm, "id")))["avg"]
        for firm in firms
    )
    return {
        "categories": categories,
        "stage_capacity_per_day": round(sum(capacities), 4),
        "stage_demand_per_day": round(stage_demand, 4),
        "firms_in_stage": len(firms),
        "price_band": {
            "min": round(min(prices), 4) if prices else None,
            "max": round(max(prices), 4) if prices else None,
        },
        "rival_price": round(sum(rival_prices) / len(rival_prices), 4)
        if rival_prices else None,
    }


def suppliers(runner, state, player_id, **extra) -> dict:
    env = _get(runner, "env")
    try:
        candidates_raw = env.supplier_candidates(player_id)
    except Exception:
        candidates_raw = []
    candidates = []
    latest_summary = _last(_summaries(state))
    latest_report = _last(_reports(state))

    for candidate in _items(candidates_raw):
        fid = _get(candidate, "id", candidate)
        firm = _firm(runner, fid) or candidate
        summary = _record(latest_summary, fid)
        report = _record(latest_report, fid)
        price = _get(summary, "avg_sell_price")
        if price is None:
            try:
                network_firm = runner.network.firm(fid)
                price = _get(network_firm, "sell_price", 0.0)
            except Exception:
                price = 0.0
        candidates.append({
            "id": fid,
            "name": _firm_name(firm, fid),
            "price": _number(price),
            "quality": _summary_value(summary, "quality"),
            "reliability": _summary_value(summary, "service_level"),
            "reputation": _number(_get(report, "reputation", 0.0)),
            "lead_time_days": _get(firm, "lead_time_days"),
            "region": _get(firm, "region"),
        })

    player = _firm(runner, player_id)
    current = _get(player, "suppliers", []) or []
    current = [_get(supplier, "id", supplier) for supplier in _items(current)]
    choices = _get(runner, "player_choices", {})
    try:
        choice = choices.get(player_id) if isinstance(choices, dict) else None
    except Exception:
        choice = None

    return {
        "candidates": candidates,
        "current": current,
        "rule": _get(choice, "supplier_rule"),
        "fixed": _get(choice, "supplier_id"),
    }


def population(runner, state, player_id, **extra) -> dict:
    config = _config(runner)
    env = _get(runner, "env")
    consumers = _get(config, "consumers", _get(_get(env, "config"), "consumers"))
    classes_raw = _get(consumers, "classes", [])
    classes = _items(classes_raw)

    index = 1.0
    try:
        long_run = _get(runner, "long_run")
        value = _get(long_run, "population_index", 1.0)
        index = _number(value() if callable(value) else value, 1.0)
    except Exception:
        index = 1.0

    age_totals = {}
    income_totals = {}
    class_rows = []
    total_persons = 0.0
    for consumer_class in classes:
        base_persons = _number(_get(consumer_class, "persons"))
        persons = round(base_persons * index, 4)
        total_persons += persons
        age_group = _get(consumer_class, "age_group")
        income_level = _get(consumer_class, "income_level")
        if age_group is not None:
            age_totals[age_group] = age_totals.get(age_group, 0.0) + persons
        if income_level is not None:
            income_totals[income_level] = income_totals.get(income_level, 0.0) + persons
        class_rows.append({
            "name": _get(consumer_class, "name"),
            "persons": persons,
            "age_group": age_group,
            "income_level": income_level,
            "units_per_person_per_year": _number(
                _get(consumer_class, "units_per_person_per_year")
            ),
        })

    geography = _get(config, "geography", _get(_get(env, "config"), "geography"))
    regions = []
    for region in _items(_get(geography, "regions", [])):
        share = _number(_get(region, "population_share"))
        regions.append({
            "name": _get(region, "name"),
            "share": share,
            "persons": round(total_persons * share, 4),
        })

    return {
        "persons": round(total_persons, 4),
        "index": index,
        "age_groups": [
            {"group": group, "persons": round(persons, 4)}
            for group, persons in age_totals.items()
        ],
        "income_levels": [
            {"level": level, "persons": round(persons, 4)}
            for level, persons in income_totals.items()
        ],
        "regions": regions,
        "classes": class_rows,
    }


def swiss_map(runner, state, player_id, **extra) -> dict:
    config = _config(runner)
    env = _get(runner, "env")
    geography = _get(config, "geography", _get(_get(env, "config"), "geography"))
    regions = []
    for region in _items(_get(geography, "regions", [])):
        regions.append({
            "name": _get(region, "name"),
            "x": _number(_get(region, "x")),
            "y": _number(_get(region, "y")),
            "share": _number(_get(region, "population_share")),
        })

    firms = []
    for firm in _firms(runner):
        parent = _get(firm, "parent")
        parent_id = _get(firm, "parent_id")
        owner = _get(firm, "owner")
        firms.append({
            "id": _get(firm, "id"),
            "name": _firm_name(firm, _get(firm, "id")),
            "region": _get(firm, "region"),
            "stage": _get(firm, "stage"),
            "branch": _branch(firm),
            "is_player": _get(firm, "id") == player_id,
            "is_daughter": bool(parent or parent_id or owner),
        })

    return {
        "outline": [point[:] for point in CH_OUTLINE],
        "regions": regions,
        "firms": firms,
    }
