from __future__ import annotations


def _firm_value(runner, state, firm_id: str) -> float:
    holdings = getattr(runner, "holdings", None)
    if holdings is not None:
        return float(holdings.value(runner, state, firm_id))
    runtime = runner.env.runtimes.get(firm_id)
    return max(0.0, float(runtime.cash)) if runtime is not None else 0.0


def _summary_value(summary, key: str) -> float:
    return float(getattr(summary, key, 0.0)) if summary is not None else 0.0


def _format_chf(value: float) -> str:
    return f"{value:,.0f}".replace(",", "'")


def _round_decisions(protocol, start_price: float | None = None) -> list[str]:
    rounds = getattr(protocol, "rounds", []) or []
    choices = getattr(protocol, "choices", []) or []
    orders = getattr(protocol, "orders", []) or []
    decisions = []
    previous_price = start_price

    for index, settings in enumerate(rounds):
        settings = settings if isinstance(settings, dict) else {}
        price = settings.get("base_price")
        if price is not None:
            try:
                price = float(price)
            except (TypeError, ValueError):
                price = None

        if price is not None and previous_price is not None and previous_price != 0:
            if abs(price / previous_price - 1) >= 0.05:
                decisions.append(
                    f"Runde {index + 1}: Preis von {previous_price:.2f} "
                    f"auf {price:.2f} CHF"
                )
        if price is not None:
            previous_price = price

        choice = choices[index] if index < len(choices) else None
        if isinstance(choice, dict) and choice:
            decisions.append(
                f"Runde {index + 1}: Entscheide geändert "
                f"({', '.join(str(key) for key in choice)})"
            )

        order = orders[index] if index < len(orders) else None
        if isinstance(order, dict):
            for key, text in (
                ("buy", "Kauf einer Firma"),
                ("sell", "Verkauf einer Tochter"),
                ("hire", "CEO eingestellt"),
            ):
                if order.get(key):
                    decisions.append(f"Runde {index + 1}: {text}")

        if len(decisions) >= 12:
            break

    return decisions[:12]


def build_review(
    runner, state, player_id: str, protocol, sale: dict | None, reason: str | None,
    start_price: float | None = None,
) -> dict:
    from market_sim.game import holding_player

    firms = runner._firms()
    firms_by_id = {firm.id: firm for firm in firms}
    player_firm = firms_by_id.get(player_id)
    player_name = player_firm.name if player_firm is not None else player_id
    player_stage = player_firm.stage if player_firm is not None else None

    try:
        daughters = holding_player.daughters(runner, player_id)
    except Exception:
        daughters = []
    daughters = list(daughters or [])
    owned_ids = [player_id, *daughters]

    player_value = (
        float(sale["price"])
        if sale is not None
        else sum(_firm_value(runner, state, firm_id) for firm_id in owned_ids)
    )

    stage_firms = [
        firm for firm in firms
        if firm.stage == player_stage
        and (
            getattr(runner.env.runtimes.get(firm.id), "active", False)
            or firm.id == player_id
        )
    ]
    ranked = [
        {
            "id": firm.id,
            "name": firm.name,
            "value": player_value if firm.id == player_id else _firm_value(runner, state, firm.id),
            "is_player": firm.id == player_id,
        }
        for firm in stage_firms
    ]
    if player_firm is None:
        ranked.append({
            "id": player_id,
            "name": player_name,
            "value": player_value,
            "is_player": True,
        })

    ranked.sort(key=lambda item: (-item["value"], item["id"]))
    rank = next(
        (index for index, item in enumerate(ranked, start=1) if item["is_player"]),
        1,
    )
    leaders = [
        {"name": item["name"], "value": item["value"], "is_player": item["is_player"]}
        for item in ranked[:5]
    ]

    labels = []
    player_revenue = []
    player_profit = []
    stage_avg_revenue = []
    stage_best_revenue = []

    for year_index, summaries in enumerate(state.summaries):
        summaries = summaries or {}
        labels.append(f"Jahr {year_index + 1}")
        player_revenue.append(
            sum(_summary_value(summaries.get(firm_id), "revenue") for firm_id in owned_ids)
        )
        player_profit.append(
            sum(_summary_value(summaries.get(firm_id), "profit") for firm_id in owned_ids)
        )

        other_revenues = [
            _summary_value(summaries.get(firm.id), "revenue")
            for firm in firms
            if firm.stage == player_stage
            and firm.id != player_id
            and getattr(runner.env.runtimes.get(firm.id), "active", False)
            and _summary_value(summaries.get(firm.id), "revenue") > 0
        ]
        stage_avg_revenue.append(
            sum(other_revenues) / len(other_revenues) if other_revenues else 0.0
        )

        stage_revenues = [
            _summary_value(summaries.get(firm.id), "revenue")
            for firm in firms
            if firm.stage == player_stage
            and (
                getattr(runner.env.runtimes.get(firm.id), "active", False)
                or firm.id == player_id
            )
        ]
        stage_best_revenue.append(max(stage_revenues, default=0.0))

    reason_text = {
        "verkauft": " Die Firma wurde verkauft.",
        "konkurs": " Die Firma ging in Konkurs.",
        "ende": "",
    }.get(reason, "")
    summary_text = (
        f"{player_name} landet auf Rang {rank} von {len(ranked)} "
        f"mit einem Wert von {_format_chf(player_value)} CHF."
        f"{reason_text}"
    )

    return {
        "reason": reason,
        "years": len(state.summaries),
        "player": {"id": player_id, "name": player_name, "value": player_value},
        "rank": rank,
        "of": len(ranked),
        "leaders": leaders,
        "curves": {
            "labels": labels,
            "player_revenue": player_revenue,
            "player_profit": player_profit,
            "stage_avg_revenue": stage_avg_revenue,
            "stage_best_revenue": stage_best_revenue,
        },
        "decisions": _round_decisions(protocol, start_price),
        "summary": summary_text,
    }
