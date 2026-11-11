from __future__ import annotations

import re
from typing import Any

from market_sim.llm import unchecked_numbers


SYSTEM = (
    "Du bist ein erfahrener Unternehmensberater in einem Wirtschaftsspiel "
    "(Schweizer Getränkemarkt). Du siehst nur die Zahlen der eigenen Firma und "
    "öffentliche Infos. Antworte auf Deutsch (Schweiz), nie mit ß (immer ss), "
    "einfache Alltagssprache, keine Tabellen."
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value)
    except (OverflowError, ValueError):
        return None


def _money(value: Any) -> str:
    number = _number(value)
    if number is None:
        return str(value)
    return f"{number:,.0f}".replace(",", "'") + " CHF"


def _price(value: Any) -> str:
    number = _number(value)
    if number is None:
        return str(value)
    return f"{number:.2f} CHF"


def _plain(value: Any) -> str:
    if value is None:
        return "keine"
    if isinstance(value, bool):
        return "ja" if value else "nein"
    if isinstance(value, dict):
        return ", ".join(f"{key}: {_plain(item)}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(_plain(item) for item in value)
    return str(value)


def _setting_value(key: str, value: Any) -> str:
    if key in {"base_price"}:
        return _price(value)
    if key in {"r_and_d_budget"}:
        return _money(value)
    return _plain(value)


def _choice_lines(value: Any, path: str = "") -> list[str]:
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            lines.extend(_choice_lines(item, child_path))
        return lines
    if isinstance(value, list):
        return [f"{path}: {_plain(value)}"] if value else []
    return [f"{path}: {_plain(value)}"] if path else []


def facts_from_state(state: dict) -> str:
    """Build compact adviser facts using only the controller's public state."""
    lines: list[str] = []

    if "year" in state or "month" in state:
        period = []
        if "year" in state:
            period.append(f"Jahr {state['year']}")
        if "month" in state:
            period.append(f"Monat {state['month']}")
        lines.append("Zeit: " + ", ".join(period))

    firm = state.get("firm")
    if isinstance(firm, dict):
        details = []
        if firm.get("name") is not None:
            details.append(str(firm["name"]))
        if firm.get("branch") is not None:
            details.append(f"Branche: {firm['branch']}")
        if details:
            lines.append("Firma: " + ", ".join(details))

    kpis = state.get("kpis")
    if isinstance(kpis, dict):
        labels = {
            "cash": ("Kasse", _money),
            "inventory": ("Lager", _plain),
            "backlog": ("Rückstand", _plain),
            "employees": ("Mitarbeitende", _plain),
            "sell_price": ("Eigener Verkaufspreis", _price),
            "profit": ("Gewinn", _money),
            "recent_demand": ("Jüngste Nachfrage", _plain),
            "recent_sales": ("Jüngster Verkauf", _plain),
            "rival_price": ("Konkurrenzpreis", _price),
        }
        for key, (label, formatter) in labels.items():
            if key in kpis and kpis[key] is not None:
                lines.append(f"{label}: {formatter(kpis[key])}")

    settings = state.get("settings")
    if isinstance(settings, dict) and settings:
        setting_labels = {
            "base_price": "Grundpreis",
            "target_safety_stock_days": "Lagerziel in Tagen",
            "order_qty": "Bestellmenge pro Tag",
            "overtime_level": "Überstunden",
            "wage_level": "Lohnniveau",
            "r_and_d_budget": "Forschungsbudget",
            "target_quality": "Zielqualität",
            "hiring_plan": "Einstellungen pro Jahr",
            "supplier_priority": "Lieferantenpriorität",
            "positioning": "Positionierung",
            "risk_tolerance": "Risikotoleranz",
        }
        entries = [
            f"{setting_labels.get(key, key)}: {_setting_value(key, value)}"
            for key, value in settings.items()
        ]
        lines.append("Einstellungen: " + "; ".join(entries))

    choices = state.get("choices")
    if choices:
        entries = _choice_lines(choices)
        if entries:
            lines.append("Entscheide: " + "; ".join(entries))

    price_band = state.get("price_band")
    if isinstance(price_band, dict):
        band = []
        if price_band.get("min") is not None:
            band.append(f"Minimum {_price(price_band['min'])}")
        if price_band.get("max") is not None:
            band.append(f"Maximum {_price(price_band['max'])}")
        if band:
            lines.append("Preisband: " + ", ".join(band))

    history = state.get("history")
    if isinstance(history, list) and history:
        entries = []
        for item in history[-6:]:
            if not isinstance(item, dict):
                continue
            period = []
            if item.get("year") is not None:
                period.append(f"Jahr {item['year']}")
            if item.get("month") is not None:
                period.append(f"Monat {item['month']}")
            details = []
            if item.get("cash") is not None:
                details.append(f"Kasse {_money(item['cash'])}")
            if item.get("profit") is not None:
                details.append(f"Gewinn {_money(item['profit'])}")
            if item.get("sell_price") is not None:
                details.append(f"Preis {_price(item['sell_price'])}")
            if details:
                entries.append(f"{', '.join(period)}: {', '.join(details)}")
        if entries:
            lines.append("Verlauf (letzte Halte): " + "; ".join(entries))

    messages = state.get("messages")
    if isinstance(messages, list):
        important = [
            item for item in messages
            if isinstance(item, dict) and item.get("important") and item.get("text") is not None
        ][:8]
        if important:
            lines.append("Wichtige Meldungen: " + " | ".join(str(item["text"]) for item in important))

    holding = state.get("holding")
    if isinstance(holding, dict):
        details = []
        if holding.get("name") is not None:
            details.append(str(holding["name"]))
        if holding.get("cash") is not None:
            details.append(f"Kasse {_money(holding['cash'])}")
        daughters = holding.get("daughters")
        daughter_facts = []
        if isinstance(daughters, list):
            for daughter in daughters:
                if not isinstance(daughter, dict):
                    continue
                parts = []
                if daughter.get("name") is not None:
                    parts.append(str(daughter["name"]))
                if daughter.get("branch") is not None:
                    parts.append(f"Branche {daughter['branch']}")
                for key, label in (
                    ("cash", "Kasse"),
                    ("revenue", "Umsatz"),
                    ("profit", "Gewinn"),
                ):
                    if daughter.get(key) is not None:
                        parts.append(f"{label} {_money(daughter[key])}")
                if parts:
                    daughter_facts.append(", ".join(parts))
        if daughter_facts:
            details.append("Töchter: " + "; ".join(daughter_facts))
        if details:
            lines.append("Holding: " + "; ".join(details))
    elif "holding" in state:
        lines.append("Holding: keine")

    ceo_of = state.get("ceo_of")
    if isinstance(ceo_of, dict) and ceo_of:
        lines.append(
            "CEO-Zuteilung: "
            + "; ".join(f"{firm_id}: Avatar {nr}" for firm_id, nr in ceo_of.items())
        )

    ceos = state.get("ceos")
    if isinstance(ceos, list) and ceos:
        entries = []
        for ceo in ceos:
            if not isinstance(ceo, dict):
                continue
            parts = []
            for key in ("name", "age", "style_label", "firm"):
                if ceo.get(key) is not None:
                    parts.append(str(ceo[key]))
            if ceo.get("salary") is not None:
                parts.append(f"Lohn {_money(ceo['salary'])}")
            if ceo.get("available") is not None:
                parts.append(f"verfügbar: {_plain(ceo['available'])}")
            if parts:
                entries.append(", ".join(parts))
        if entries:
            lines.append("CEOs: " + "; ".join(entries))

    return "\n".join(lines)


def build_prompt(facts: str, question: str | None) -> str:
    task = (
        "Gib 3 bis 5 konkrete Tipps. Jeder Tipp steht auf einer eigenen Zeile und "
        "beginnt mit «- ». Nenne bei jedem Tipp einen kurzen Grund und beziehe dich "
        "auf die Fakten sowie auf Entscheidungen, die im Cockpit getroffen werden "
        "(Preis, Lagerziel, Menge, Überstunden, Lohn, Einstellungen, Qualität, "
        "Forschung, Marketing, Kredit, Dividende, Transport, Ausbau, Holding/CEO). "
        "Verwende nur Zahlen, die in den Fakten stehen."
    )
    if question:
        task = (
            f"Beantworte zuerst diese Frage in höchstens 3 Sätzen: {question}\n\n"
            + task
        )
    return f"FAKTEN:\n{facts}\n\n{task}"


def parse_tips(text: str) -> list[str]:
    lines = [line.strip() for line in text.replace("ß", "ss").splitlines() if line.strip()]
    marker = re.compile(r"^(?:[-•*]\s*|\d+[.)]\s*)")
    tips = []
    for line in lines:
        match = marker.match(line)
        if match:
            tip = line[match.end():].strip()
            if tip:
                tips.append(tip)
    if not tips:
        tips = lines
    return tips[:5]


def advise(llm, state: dict, question: str | None = None) -> dict:
    if not state.get("running"):
        return {"tips": [], "answer": "Es läuft kein Spiel.", "checked": True, "error": None}

    facts = facts_from_state(state)
    prompt = build_prompt(facts, question)
    try:
        text = llm.generate(SYSTEM, prompt).replace("ß", "ss").strip()
    except Exception as error:
        return {
            "tips": [],
            "answer": "",
            "checked": False,
            "error": (
                f"Der Berater antwortet nicht ({error.__class__.__name__}). "
                "Ist der API-Schlüssel gesetzt?"
            ),
        }

    bad = unchecked_numbers(text, facts)
    if bad:
        text += "\n\n(Einzelne Zahlen stehen nicht in den Daten und sind ungeprüft.)"
    return {
        "tips": parse_tips(text),
        "answer": text,
        "checked": not bad,
        "error": None,
    }
