"""Player-facing helpers for buying and managing holding subsidiaries."""

from __future__ import annotations


def _base_firm_value(runner, state, firm_id: str) -> float:
    holdings = getattr(runner, "holdings", None)
    value = getattr(holdings, "value", None)
    base = float(value(runner, state, firm_id)) if callable(value) else max(0.0, float(runner.env.runtimes[firm_id].cash))
    # Untergrenze: auch eine Firma mit Verlust hat Läden, Lager und Kunden. Wie bei den Verkaufsangeboten
    # zählt die Kapazität (sonst wäre eine Verlustfirma gratis zu haben).
    try:
        cfg = runner.config.state
        floor = cfg.price_per_capacity_unit * runner.long_run.price_index * runner.env._effective_capacity(firm_id)
    except Exception:
        floor = 0.0
    return max(base, float(floor))


def firm_value(runner, state, firm_id: str) -> float:
    """Return a firm's value including the holding control premium."""
    holdings = getattr(runner, "holdings", None)
    cfg = getattr(holdings, "cfg", None)
    premium = getattr(cfg, "control_premium", 0.2)
    return _base_firm_value(runner, state, firm_id) * (1.0 + premium)


def _branch(firm) -> str:
    if firm.stage == "factory":
        return "hersteller"
    if firm.stage == "wholesaler":
        return "grosshaendler"
    if firm.stage == "distributor":
        return "verteiler"
    if firm.stage == "retailer" and firm.channel == "restaurant":
        return "gastro"
    if firm.stage == "retailer":
        return "detailhaendler"
    return firm.stage


def _last_summary(state, firm_id: str):
    if not state.summaries:
        return None
    return state.summaries[-1].get(firm_id)


def buy_targets(runner, state, player_id: str) -> list[dict]:
    """Return active firms the player can acquire, ordered by price."""
    from market_sim.holding_groups import category_allows_buy

    player = runner.network.firm(player_id)
    holding_groups = getattr(runner, "holding_groups", None)
    sub_of = getattr(holding_groups, "sub_of", {}) if holding_groups is not None else {}
    targets = []

    for firm in runner._firms():
        runtime = runner.env.runtimes[firm.id]
        if (
            not runtime.active
            or firm.id == player_id
            or firm.stage not in ("retailer", "wholesaler", "distributor", "factory")
            or firm.id in sub_of
            or not category_allows_buy(player.category, firm.category)
        ):
            continue

        summary = _last_summary(state, firm.id)
        targets.append({
            "id": firm.id,
            "name": firm.name,
            "branch": _branch(firm),
            "region": firm.region,
            "category": firm.category,
            "price": firm_value(runner, state, firm.id),
            "revenue": summary.revenue if summary is not None else 0.0,
            "profit": summary.profit if summary is not None else 0.0,
        })

    return sorted(targets, key=lambda target: (target["price"], target["id"]))


def buy(runner, state, player_id: str, target_id: str, year: int, day: int) -> dict:
    """Buy an eligible firm into the player's holding."""
    holding_groups = getattr(runner, "holding_groups", None)
    if holding_groups is None:
        return {
            "ok": False,
            "message": "Übernahmen sind in dieser Simulation ausgeschaltet",
        }

    targets = {target["id"]: target for target in buy_targets(runner, state, player_id)}
    target_info = targets.get(target_id)
    if target_info is None:
        return {"ok": False, "message": "Diese Firma kann nicht übernommen werden"}

    price = target_info["price"]
    player = runner.network.firm(player_id)
    target = runner.network.firm(target_id)
    group = holding_groups.group_of(player_id)
    available = runner.env.runtimes[player_id].cash
    if group is not None:
        available += group.cash
    if available < price:
        return {"ok": False, "message": "Nicht genug Geld für die Übernahme"}

    # Wettbewerbsbehörde: wie bei Fusionen kein gemeinsamer Marktanteil über der Grenze.
    limit = getattr(getattr(runner.config, "mergers", None), "max_market_share", 0.40)
    if state.summaries:
        last = state.summaries[-1]
        same = [f for f in runner._firms() if f.stage == target.stage and f.id in last]
        total = sum(max(0.0, last[f.id].revenue) for f in same)
        own = {player_id, target_id, *(group.subs if group is not None else [])}
        combined = sum(max(0.0, last[f.id].revenue) for f in same if f.id in own)
        if total > 0 and combined / total > limit:
            return {"ok": False, "message": (
                f"Die Wettbewerbsbehörde verbietet den Kauf: zusammen über "
                f"{round(limit * 100)} % Marktanteil")}

    acquired = holding_groups.acquire(
        runner, state, player, target, price, year, day
    )
    if not acquired:
        return {"ok": False, "message": "Die Übernahme konnte nicht abgeschlossen werden"}
    # Kaufpreis und Jahr für die Rendite-Rechnung im Cockpit merken.
    paid = getattr(runner, "player_purchases", None)
    if not isinstance(paid, dict):
        paid = {}
        runner.player_purchases = paid
    paid[target.id] = {"price": float(price), "year": int(year)}

    return {
        "ok": True,
        "price": price,
        "message": f"{target.name} wurde für die Holding übernommen",
    }


def daughters(runner, player_id: str) -> list[str]:
    """Return the player's subsidiaries, excluding the player's own firm."""
    holding_groups = getattr(runner, "holding_groups", None)
    if holding_groups is None:
        return []
    group = holding_groups.group_of(player_id)
    if group is None:
        return []
    return [firm_id for firm_id in group.subs if firm_id != player_id]


def sell_daughter(
    runner, state, player_id: str, firm_id: str, year: int, day: int
) -> dict:
    """Remove a subsidiary from the player's holding and pay its value to the player."""
    holding_groups = getattr(runner, "holding_groups", None)
    group = holding_groups.group_of(player_id) if holding_groups is not None else None
    if group is None or firm_id == player_id or firm_id not in group.subs:
        return {"ok": False, "message": "Diese Tochter gehört nicht zur Holding"}

    price = _base_firm_value(runner, state, firm_id)
    group.subs.remove(firm_id)
    if holding_groups.sub_of.get(firm_id) == group.id:
        del holding_groups.sub_of[firm_id]

    runner.env.runtimes[player_id].adjust_cash(price, f"holding_verkauf:{firm_id}")
    firm = runner.network.firm(firm_id)
    state.events.append({
        "year": year,
        "day": day,
        "firm": player_id,
        "event": "holding_sold",
        "details": f"Tochter {firm.name} verlässt die Holding und wird für {price:,.0f} CHF verkauft",
    })
    return {
        "ok": True,
        "price": price,
        "message": f"{firm.name} wurde für {price:,.0f} CHF verkauft",
    }


def holding_info(runner, state, player_id: str) -> dict | None:
    """Return the player's holding and subsidiary details, if one exists."""
    holding_groups = getattr(runner, "holding_groups", None)
    group = holding_groups.group_of(player_id) if holding_groups is not None else None
    if group is None:
        return None

    subsidiaries = []
    for firm_id in group.subs:
        if firm_id == player_id:
            continue
        firm = runner.network.firm(firm_id)
        runtime = runner.env.runtimes[firm_id]
        summary = _last_summary(state, firm_id)
        subsidiaries.append({
            "id": firm_id,
            "name": firm.name,
            "branch": _branch(firm),
            "cash": runtime.cash,
            "revenue": summary.revenue if summary is not None else 0.0,
            "profit": summary.profit if summary is not None else 0.0,
            "tendency": firm.tendency,
        })

    return {
        "id": group.id,
        "name": group.name,
        "cash": group.cash,
        "daughters": subsidiaries,
    }
