"""Meldungen für den Spieler."""

from __future__ import annotations


def margin_notice(runner, player_id, year: int, month: int, margins: list) -> dict | None:
    """Meldung, wenn die Bruttomarge drei Monate in Folge sinkt oder unter 15 % fällt."""
    try:
        from market_sim import financials
        statement = financials.income_statement(runner, player_id, None)
        revenue = float(statement.get("revenue") or 0.0)
        gross = float(statement.get("gross_profit") or 0.0)
    except Exception:
        return None
    if revenue <= 0:
        return None
    margin = gross / revenue
    margins.append(margin)
    del margins[:-4]
    falling = len(margins) >= 4 and margins[-4] > margins[-3] > margins[-2] > margins[-1]
    if margin < 0.15:
        text = (f"Deine Bruttomarge liegt bei {margin * 100:.1f} % und damit unter 15 %. "
                "Rat: Verkaufspreis erhöhen oder günstiger einkaufen.")
    elif falling:
        text = (f"Deine Bruttomarge sinkt seit drei Monaten: jetzt {margin * 100:.1f} % "
                f"(vor drei Monaten {margins[-4] * 100:.1f} %). "
                "Rat: Preise und Einkaufskosten prüfen.")
    else:
        return None
    return {"year": year, "month": month, "level": "gelb", "kind": "marge", "text": text}


def build_notices(
    runner,
    state,
    player_id,
    year,
    day,
    seen: set,
    ceo_book,
    years_left: int | None,
    events: list | None = None,
) -> list[dict]:
    """Liefert neue Meldungen für den Spieler."""
    notices: list[dict] = []

    try:
        offers_by_year = {}
        for entry in getattr(runner, "takeover_offers", []):
            try:
                target = entry["target"]
                if target == player_id:
                    continue

                offer_year = entry["year"]
                key = ("offer", offer_year, target)
                if key in seen:
                    continue

                seen.add(key)
                offers_by_year.setdefault(offer_year, []).append(entry)
            except Exception:
                pass

        stages = {
            "factory": "Hersteller",
            "wholesaler": "Grosshändler",
            "distributor": "Verteiler",
            "retailer": "Detailhandel",
        }
        for offer_year, offers in offers_by_year.items():
            try:
                key = ("offers", offer_year)
                if key in seen:
                    continue

                if len(offers) == 1:
                    entry = offers[0]
                    stage_name = stages.get(entry["stage"], entry["stage"])
                    price = f"{entry['price']:,.0f}".replace(",", "'")
                    text = (
                        f"Verkaufsangebot: {entry['name']} ({stage_name}) steht "
                        f"für {price} CHF zum Verkauf – {entry['reason']}. "
                        "Du kannst sie unter Übernahmen kaufen."
                    )
                else:
                    names = []
                    for entry in offers[:5]:
                        stage_name = stages.get(entry["stage"], entry["stage"])
                        price = f"{entry['price']:,.0f}".replace(",", "'")
                        names.append(
                            f"{entry['name']} ({stage_name}, {price} CHF)"
                        )

                    if len(offers) > 5:
                        names.append("und weitere")

                    text = (
                        f"Verkaufsangebote: {len(offers)} Firmen stehen zum "
                        f"Verkauf: {', '.join(names)}. "
                        "Du kannst sie unter Übernahmen kaufen."
                    )

                notices.append({
                    "year": year,
                    "day": day,
                    "text": text,
                    "kind": "markt",
                    "important": True,
                })
                seen.add(key)
            except Exception:
                pass

        try:
            from market_sim.game import holding_player

            for firm_id in holding_player.daughters(runner, player_id):
                try:
                    if ceo_book.ceo_of(firm_id) is not None:
                        continue

                    key = ("noceo", firm_id, year)
                    if key in seen:
                        continue

                    name = runner.network.firm(firm_id).name
                    notices.append({
                        "year": year,
                        "day": day,
                        "text": (
                            f"Deine Tochter {name} hat keinen CEO. Stelle einen "
                            "CEO ein, sonst läuft sie ohne Führung."
                        ),
                        "kind": "eigen",
                        "important": True,
                        "action": {"action": "ceo", "firm": firm_id},
                    })
                    seen.add(key)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            from market_sim.game import holding_player

            daughters = set(holding_player.daughters(runner, player_id))
        except Exception:
            daughters = set()

        try:
            for event in events or []:
                try:
                    firm_id = event["firm"]
                    event_type = event["event"]
                    details = str(event["details"])

                    if event_type in ("loan_granted", "stake_bought"):
                        if firm_id not in daughters:
                            continue

                        name = runner.network.firm(firm_id).name
                        if event_type == "loan_granted":
                            text = (
                                f"Deine Tochter {name} hat einen Kredit aufgenommen "
                                f"({details})."
                            )
                            action = None
                        else:
                            text = (
                                f"Deine Tochter {name} hat Anteile gekauft "
                                f"({details}). Du kannst das unter Töchter verbieten."
                            )
                            action = {
                                "action": "daughter_rules",
                                "firm": firm_id,
                            }

                        notice = {
                            "year": year,
                            "day": day,
                            "text": text,
                            "kind": "eigen",
                            "important": True,
                        }
                        if action is not None:
                            notice["action"] = action
                        notices.append(notice)

                    elif event_type == "holding_sweep":
                        text = (
                            "Die Holding hat Geld bei einer Tochter abgeschöpft "
                            f"({details})."
                        )
                        if firm_id in daughters:
                            try:
                                cash = runner.env.runtimes[firm_id].cash
                                if cash < 0:
                                    name = runner.network.firm(firm_id).name
                                    cash_text = f"{cash:,.0f}".replace(",", "'")
                                    text += (
                                        f" Achtung: {name} ist danach im Minus "
                                        f"(Kasse {cash_text} CHF). Gib ihr Geld "
                                        "zurück oder senke die Abschöpfung."
                                    )
                            except Exception:
                                pass

                        notices.append({
                            "year": year,
                            "day": day,
                            "text": text,
                            "kind": "eigen",
                            "important": True,
                        })
                except Exception:
                    pass
        except Exception:
            pass

        try:
            delivery_book = getattr(runner.env, "delivery_book", {}).get(
                player_id, {}
            )
            for supplier_id, delivery in delivery_book.items():
                try:
                    ordered = delivery.get("ordered", 0)
                    delivered = delivery.get("delivered", 0)
                    if ordered <= 0 or delivered / ordered >= 0.9 or day < 30:
                        continue

                    key = ("underdelivery", supplier_id, year)
                    if key in seen:
                        continue

                    try:
                        supplier_name = runner.network.firm(supplier_id).name
                    except Exception:
                        supplier_name = supplier_id

                    pct = f"{delivered / ordered * 100:.0f}"
                    notices.append({
                        "year": year,
                        "day": day,
                        "text": (
                            f"Unterlieferung: {supplier_name} liefert nur {pct} % "
                            "deiner Bestellungen. Suche einen zweiten Lieferanten "
                            "oder bestelle bei einem anderen."
                        ),
                        "kind": "eigen",
                        "important": True,
                        "action": {"action": "suppliers"},
                    })
                    seen.add(key)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            labor = getattr(runner, "labor", None)
            missing = int(getattr(labor, "open_positions", {}).get(player_id, 0) or 0) if labor else 0
            key = ("openpos", year)
            if missing > 0 and key not in seen:
                notices.append({
                    "year": year,
                    "day": day,
                    "text": (
                        f"Du wolltest mehr Leute einstellen, aber {missing} Stellen bleiben leer: "
                        "In deiner Region gibt es keine freien Arbeitskräfte. Andere Firmen zahlen "
                        "mehr und bekommen die Leute zuerst. Erhöhe dein Lohnniveau."
                    ),
                    "kind": "eigen",
                    "important": True,
                })
                seen.add(key)
        except Exception:
            pass

        try:
            if years_left == 1:
                key = ("lastyear",)
                if key not in seen:
                    notices.append({
                        "year": year,
                        "day": day,
                        "text": (
                            "Noch 1 Jahr: Das Spiel endet am Ende dieses Jahres. "
                            "Prüfe jetzt Kasse, Lager und Kredite."
                        ),
                        "kind": "eigen",
                        "important": True,
                    })
                    seen.add(key)
        except Exception:
            pass
    except Exception:
        pass

    return notices
