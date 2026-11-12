"""Meldungen für den Spieler."""

from __future__ import annotations


def build_notices(
    runner,
    state,
    player_id,
    year,
    day,
    seen: set,
    ceo_book,
    years_left: int | None,
) -> list[dict]:
    """Liefert neue Meldungen für den Spieler."""
    notices: list[dict] = []

    try:
        for entry in getattr(runner, "takeover_offers", []):
            try:
                target = entry["target"]
                if target == player_id:
                    continue

                key = ("offer", entry["year"], target)
                if key in seen:
                    continue

                stages = {
                    "factory": "Hersteller",
                    "wholesaler": "Grosshändler",
                    "distributor": "Verteiler",
                    "retailer": "Detailhandel",
                }
                stage_name = stages.get(entry["stage"], entry["stage"])
                price = f"{entry['price']:,.0f}".replace(",", "'")
                notices.append({
                    "year": year,
                    "day": day,
                    "text": (
                        f"Verkaufsangebot: {entry['name']} ({stage_name}) steht "
                        f"für {price} CHF zum Verkauf – {entry['reason']}. "
                        "Du kannst sie unter Übernahmen kaufen."
                    ),
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
