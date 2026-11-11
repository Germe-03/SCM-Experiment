"""Wirkungsprotokoll: welche Entscheide der Spieler in einer Runde geändert hat (lesbar, deutsch)."""

from __future__ import annotations

SETTING_LABELS = {
    "base_price": ("Preis", "chf"),
    "target_safety_stock_days": ("Lagerziel", "tage"),
    "order_qty": ("Feste Menge pro Tag", "zahl"),
    "overtime_level": ("Überstunden", "prozent"),
    "wage_level": ("Lohn", "zahl"),
    "r_and_d_budget": ("Qualitätsbudget", "chf"),
    "target_quality": ("Zielqualität", "prozent"),
    "hiring_plan": ("Einstellungen pro Jahr", "zahl"),
    "supplier_priority": ("Lieferanten-Priorität", "text"),
    "positioning": ("Positionierung", "text"),
    "risk_tolerance": ("Risikobereitschaft", "prozent"),
}

CHOICE_LABELS = {
    "marketing_budget": "Marketingbudget",
    "marketing_focus": "Marketing-Fokus",
    "marketing_target": "Marketing-Zielgruppe",
    "research_target": "Forschungsziel",
    "credit_mode": "Kreditregel",
    "bank_id": "Bank",
    "payout_ratio": "Dividende",
    "listing": "Börse",
    "transport_mode": "Transport",
    "auto_invest": "Automatischer Ausbau",
    "expand_order": "Kapazitätsausbau",
    "site_order": "Neuer Standort",
    "commodity_courage": "Rohstoff-Vorkauf",
    "markup_factor": "Gastro-Aufschlag",
    "offences": "Graubereich",
    "supplier_id": "Fester Lieferant",
    "supplier_rule": "Lieferanten-Regel",
}

ORDER_LABELS = {
    "buy": "Firmenkauf", "sell": "Verkauf einer Tochter", "hire": "CEO eingestellt",
    "fire": "CEO entlassen", "guidelines": "Leitplanken für Töchter", "loan": "Kredit beantragt",
    "truck": "Lastwagen bestellt", "stock": "Aktienhandel",
}


def _fmt(value, kind: str) -> str:
    if value is None:
        return "automatisch"
    if kind == "chf":
        return f"{float(value):,.2f} CHF".replace(",", "'")
    if kind == "prozent":
        return f"{float(value) * 100:.0f} %"
    if kind == "tage":
        return f"{value} Tage"
    return str(value)


def describe_changes(current, updates: dict, choices: dict, orders: dict) -> list[str]:
    """Kurze Sätze wie «Preis: 2.10 → 2.30 CHF (+10 %)» für alle Änderungen dieser Runde."""
    lines: list[str] = []
    for key, new in updates.items():
        label, kind = SETTING_LABELS.get(key, (key, "text"))
        old = getattr(current, key, None)
        if old == new:
            continue
        text = f"{label}: {_fmt(old, kind)} → {_fmt(new, kind)}"
        if isinstance(old, (int, float)) and isinstance(new, (int, float)) and old:
            text += f" ({(new - old) / abs(old) * 100:+.0f} %)"
        lines.append(text)
    for key, value in choices.items():
        label = CHOICE_LABELS.get(key, key)
        lines.append(f"{label}: {'Autopilot' if value is None else value}")
    for key in orders:
        if orders[key]:
            lines.append(ORDER_LABELS.get(key, key))
    return lines
