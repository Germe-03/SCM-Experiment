"""Phase 12: firm stories and a yearly chronicle written by a language model from checked facts.

Python builds the facts; the model only words them. Every number in a text must appear
in the facts, otherwise the model is told the offending numbers and tries once more; after that
the text is replaced by a plain summary. Template mode is also available for deterministic
stories and chronicles without a language model.
"""

from __future__ import annotations

import random
import re
from collections import defaultdict

from market_sim import chronicle_templates as ct
from market_sim.kpi import PROJECT_DE
from market_sim.llm import unchecked_numbers

USE_LLM_DEFAULT = False

STAGE_DE = {"retailer": "Detailhandel", "wholesaler": "Grosshandel", "distributor": "Verteilung", "factory": "Hersteller"}
CAT_DE = {"beer": "Bier", "wine": "Wein", "spirits": "Spirituosen"}
EXIT_DE = {"bankruptcy": "Konkurs", "takeover": "Übernahme", "poisoning": "Vergiftung", "merger": "Fusion"}
KEY_EVENTS = {"takeover", "merger_formed", "merger_blocked", "holding_formed", "holding_takeover",
              "holding_dissolved", "holding_sold", "poisoning", "offence_detected", "rnd_success", "site_finished", "expand_finished",
              "restructuring", "strategy_change", "bankruptcy", "stake_bought", "breakup", "spin_off",
              "rnd_implemented", "patent_granted", "patent_expired"}
YEAR_EVENTS = {"merger_formed", "merger_blocked", "holding_formed", "holding_takeover", "holding_dissolved", "recession", "raw_material_shortage", "cost_shock", "wage_push", "trend_change", "poisoning",
               "law_enacted", "breakup", "heat_summer", "harvest_failure",
               "bank_failed", "bank_entry", "exchange_opened"}

SYSTEM = (
    "Du bist Wirtschaftsjournalist und schreibst auf Deutsch (Schweizer Rechtschreibung, kein ß). "
    "Verwende ausschliesslich die gegebenen Fakten. Erfinde keine Zahlen, Namen oder Ursachen. "
    "Regeln für Zahlen: Jede Zahl in deinem Text muss genau so in den FAKTEN stehen, Ziffer für Ziffer. "
    "Rechne nichts aus: keine Summen, Differenzen, Durchschnitte, Prozent-Veränderungen oder Verhältnisse. "
    "Runde nicht und rechne nicht um (nicht Mio. in Mia., nicht CHF in Prozent). "
    "Schreibe Beträge mit Mio. und Mia. genau so wie in den FAKTEN (z. B. 52 Mio. CHF, 2,65 Mia. CHF). "
    "Nenne keine Mitarbeiterzahlen, Marktanteile, Preise oder Mengen, die nicht in den FAKTEN stehen. "
    "Brauchst du eine Zahl, die nicht dasteht, beschreibe es mit Worten (z. B. 'stark gestiegen', 'fast halbiert'). "
    "Die Jahre heissen 'Jahr 1', 'Jahr 2' und so weiter; nenne nie Kalenderjahre wie 2002. "
    "Schreibe sachlich und verständlich, ohne Aufzählung, ohne Überschrift."
)


def _mio(value: float) -> str:
    return f"{value / 1e6:,.0f}".replace(",", "'")


def _chf(value: float) -> str:
    """52 Mio. CHF below 1'000 Mio., from there 2,65 Mia. CHF (comma, two decimals)."""
    if abs(round(value / 1e6)) >= 1000:
        return f"{value / 1e9:.2f}".replace(".", ",") + " Mia. CHF"
    return f"{_mio(value)} Mio. CHF"


def _readable(details: str) -> str:
    """Write amounts like 51'609'492 CHF (or 51,609,492 CHF from the bank events) as 52 Mio. CHF."""
    def to_mio(match: re.Match) -> str:
        value = float(match.group(1).replace("'", "").replace(",", ""))
        return _chf(value) if abs(value) >= 1e6 else match.group(0)
    return re.sub(r"(-?\d{1,3}(?:['’,]\d{3})+|-?\d+) CHF", to_mio, str(details))


def _stage_label(data: dict, tree, name) -> str:
    trees = data.get("rnd_trees") or {}
    tree_lists = [trees.get(tree, [])] if tree is not None else trees.values()
    for entries in tree_lists:
        for entry in entries:
            if entry.get("name") == name:
                return entry.get("label", PROJECT_DE.get(name, name))
    return PROJECT_DE.get(name, name)


def _name(data: dict, firm_id) -> str:
    if firm_id is None:
        return ""
    return data["firms"].get(firm_id, {}).get("name", firm_id)


def rnd_firm_lines(data: dict, firm_id: str) -> list[str]:
    lines = []
    implemented = sorted(
        (row for row in data.get("rnd") or []
         if row.get("firm") == firm_id and row.get("step") == "implementation"),
        key=lambda row: row.get("end_year", 0))
    labels = []
    for row in implemented:
        label = _stage_label(data, row.get("tree"), row.get("stage") or row.get("project") or row.get("name"))
        if label not in labels:
            labels.append(label)
    if labels:
        lines.append(f"Forschungsstufen umgesetzt: {len(labels)} ({', '.join(labels)})")

    for patent in data.get("patents") or []:
        if patent.get("holder") == firm_id or patent.get("first_holder") == firm_id:
            label = _stage_label(data, patent.get("tree"), patent.get("stage"))
            lines.append(f"Patent auf {label} von Jahr {patent.get('granted_year')} bis Jahr "
                         f"{patent.get('expires_year')}, Gebühr {_chf(patent.get('fee') or 0)}")

    paid = received = 0
    firm = (data.get("firms") or {}).get(firm_id, {})
    for row in firm.get("yearly", []) or []:
        for key, value in (row.get("cash_flows") or {}).items():
            if key.startswith("schadenersatz:"):
                if value < 0:
                    paid += -value
                elif value > 0:
                    received += value
    if paid > 0:
        lines.append(f"Schadenersatz bezahlt: {_chf(paid)}")
    if received > 0:
        lines.append(f"Schadenersatz erhalten: {_chf(received)}")

    for row in data.get("offence_ledger") or []:
        if row.get("firm") == firm_id and row.get("offence") == "patentverletzung":
            lines.append(f"Patentverletzung entdeckt in Jahr {row.get('year')}: Busse "
                         f"{_chf(row.get('fine') or 0)}, Schadenersatz "
                         f"{_chf(row.get('compensation') or 0)}")
    return lines


def rnd_year_lines(data: dict, year: int) -> list[str]:
    lines = []
    rnd_rows = [row for row in data.get("rnd") or [] if row.get("end_year") == year]
    impl = sum(row.get("step") == "implementation" for row in rnd_rows)
    res = sum(row.get("step") != "implementation" and row.get("success") is True for row in rnd_rows)
    if impl + res > 0:
        lines.append(f"Forschung: {impl} Stufen umgesetzt, {res} Stufen erfolgreich erforscht")

    for patent in data.get("patents") or []:
        label = _stage_label(data, patent.get("tree"), patent.get("stage"))
        if patent.get("granted_year") == year:
            holder = patent.get("first_holder", patent.get("holder"))
            lines.append(f"Patent erteilt: {_name(data, holder)} für {label} bis Jahr "
                         f"{patent.get('expires_year')}")
        if patent.get("end_year") == year:
            if patent.get("status") == "expired":
                lines.append(f"Patent abgelaufen: {label} von {_name(data, patent.get('holder'))}")
            elif patent.get("status") == "lapsed":
                lines.append(f"Patent verfallen: {label} von {_name(data, patent.get('holder'))}")

    for row in data.get("offence_ledger") or []:
        if row.get("year") == year and row.get("offence") == "patentverletzung":
            line = (f"Patentverletzung entdeckt: {_name(data, row.get('firm'))}, Busse "
                    f"{_chf(row.get('fine') or 0)}, Schadenersatz "
                    f"{_chf(row.get('compensation') or 0)}")
            if row.get("holder"):
                line += f" an {_name(data, row.get('holder'))}"
            lines.append(line)
    return lines


def firm_facts(data: dict, firm_id: str) -> str:
    firm = data["firms"][firm_id]
    yearly = firm.get("yearly", [])
    lines = [f"Name: {firm['name']}", f"Stufe: {'Gastronomie' if firm.get('channel') == 'restaurant' else STAGE_DE.get(firm['stage'], firm['stage'])}"]
    if firm.get("category") and firm["stage"] == "factory":
        lines.append(f"Kategorie: {CAT_DE.get(firm['category'], firm['category'])}{' (Import)' if firm.get('importer') else ''}")
    lines.append(f"Im Markt ab Jahr {firm.get('entry_year', 1)}")
    active = [y for y in yearly if y.get("revenue", 0) > 0]
    if active:
        best = max(active, key=lambda y: y.get("profit", 0))
        worst = min(active, key=lambda y: y.get("profit", 0))
        total = sum(y.get("profit", 0) for y in active)
        lines.append(f"Gewinn insgesamt: {_chf(total)}")
        lines.append(f"Bestes Jahr: Jahr {best['year']} mit {_chf(best['profit'])} Gewinn")
        lines.append(f"Schlechtestes Jahr: Jahr {worst['year']} mit {_chf(worst['profit'])} Gewinn")
        share = max(active, key=lambda y: y.get("market_share") or 0)
        if share.get("market_share"):
            lines.append(f"Höchster Marktanteil: {share['market_share'] * 100:.0f} Prozent in Jahr {share['year']}")
    exit_info = (data.get("exit_analysis") or {}).get(firm_id)
    if exit_info:
        lines.append(f"Austritt: Jahr {exit_info['exit_year']} durch {EXIT_DE.get(exit_info['exit_type'], exit_info['exit_type'])}")
        lines.append(f"Analyse: {_readable(exit_info['summary_de'])}")
    elif firm.get("exit_year"):
        lines.append(f"Austritt: Jahr {firm['exit_year']}")
    else:
        lines.append("Am Ende noch aktiv")
    lines.extend(rnd_firm_lines(data, firm_id))
    events = [e for e in firm.get("events", []) if e["event"] in KEY_EVENTS][-8:]
    for e in events:
        lines.append(f"Jahr {e['year']}: {e['event'].replace('_', ' ')} – {_readable(e['details'])}")
    return "\n".join(f"- {line}" for line in lines)


def year_facts(data: dict, year: int) -> str:
    kpi = next((k for k in data["system"] if k["year"] == year), None)
    if kpi is None:
        return ""
    active = sum(kpi.get(f"active_firms_{s}", 0) for s in STAGE_DE)
    lines = [
        f"Jahr {year}",
        f"Gewinn aller Firmen: {_chf(kpi['total_profit'])}",
        f"Anteil bediente Nachfrage: {kpi['service_level'] * 100:.0f} Prozent",
        f"Aktive Firmen: {active}",
        f"Markteintritte: {kpi.get('market_entries', 0)}, Konkurse: {kpi.get('bankruptcies', 0)}, Übernahmen: {kpi.get('takeovers', 0)}",
    ]
    if kpi.get("trend"):
        lines.append(f"Aktueller Trend: {kpi['trend']}")
    # Phase 13-17: SNB, commercial banks and the stock exchange.
    if kpi.get("policy_rate") is not None:
        lines.append(f"Leitzins der SNB für das nächste Jahr: {kpi['policy_rate'] * 100:.2f} Prozent, "
                     f"Teuerung: {kpi.get('inflation', 0) * 100:.1f} Prozent")
    banks = [b for b in data.get("banks", []) if b["year"] == year]
    if banks:
        active_banks = [b for b in banks if b["active"]]
        lines.append(f"Banken: {len(active_banks)} aktiv, Eigenkapital zusammen "
                     f"{_chf(sum(b['equity'] for b in active_banks))}, Kredite "
                     f"{_chf(sum(b['loans'] for b in active_banks))}, Einlagen "
                     f"{_chf(sum(b['deposits'] for b in active_banks))}")
        for b in sorted(banks, key=lambda b: -b["equity"]):
            status = "" if b["active"] else ", in diesem Jahr pleite gegangen"
            lines.append(f"Bank {b['name']}: {b['customers']} Kunden, Eigenkapital {_chf(b['equity'])}, "
                         f"Gewinn {_chf(b['profit'])}{status}")
    if kpi.get("stock_index"):
        lines.append(f"Börsenindex: {kpi['stock_index']:.0f} Punkte, {kpi.get('listed_firms', 0)} Firmen an der Börse")
    profits = []
    for firm_id, firm in data["firms"].items():
        row = next((y for y in firm.get("yearly", []) if y["year"] == year), None)
        if row and row.get("revenue", 0) > 0:
            profits.append((row.get("profit", 0), firm["name"]))
    profits.sort()
    if profits:
        lines.append("Grösste Gewinner: " + ", ".join(f"{n} ({_chf(p)})" for p, n in profits[-2:][::-1]))
        lines.append("Grösste Verlierer: " + ", ".join(f"{n} ({_chf(p)})" for p, n in profits[:2]))
    lines.extend(rnd_year_lines(data, year))
    names = {fid: f["name"] for fid, f in data["firms"].items()}
    for e in [e for e in data.get("events", []) if e["year"] == year and e["event"] in YEAR_EVENTS][:6]:
        who = f" ({names.get(e['firm'], e['firm'])})" if e.get("firm") else ""
        lines.append(f"Ereignis: {e['event'].replace('_', ' ')}{who} – {_readable(e['details'])}")
    return "\n".join(f"- {line}" for line in lines)


def write_checked(llm, task: str, facts: str) -> dict:
    """Ask the model; keep the text only if every number is covered by the facts."""
    prompt = f"{task}\n\nFAKTEN:\n{facts}"
    for attempt in range(2):
        try:
            text = llm.generate(SYSTEM, prompt).replace("ß", "ss").strip()
        except Exception:  # model offline or timed out: fall back to the facts
            break
        bad = unchecked_numbers(text, facts) if text else []
        if text and not bad:
            return {"text": text, "checked": True}
        # Second try: name the numbers that are not in the facts.
        wrong = ", ".join(f"{value:g}" for value in bad) or "keine Antwort"
        prompt = (f"{task}\n\nDein erster Text enthielt Zahlen, die nicht in den FAKTEN stehen: {wrong}. "
                  f"Schreibe den Text neu und lass diese Zahlen weg oder beschreibe sie mit Worten. "
                  f"Verwende nur Zahlen, die wörtlich in den FAKTEN stehen.\n\nFAKTEN:\n{facts}")
    plain = " ".join(line.lstrip("- ") + "." for line in facts.splitlines()[:5])
    return {"text": plain, "checked": False}


class _Picker:
    """Choose deterministic templates while avoiding recently used options."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.recent: list[str] = []

    def pick(self, candidates: list[str]) -> str:
        choices = list(candidates)
        if not choices:
            return ""
        available = [candidate for candidate in choices if candidate not in self.recent]
        if available:
            choices = available
        else:
            last_use = {c: len(self.recent) - 1 - self.recent[::-1].index(c) for c in choices}
            least_recent = min(choices, key=lambda c: last_use[c])
            choices = [least_recent]
        selected = self.rng.choice(choices)
        self.recent.append(selected)
        del self.recent[:-6]
        return selected


class _FormatValues(dict):
    """Return an empty string for a missing template value."""

    def __missing__(self, key):
        return ""


def _safe_format(template: str, **values) -> str:
    """Format a template and remove any unresolved braces and repeated spaces."""
    text = str(template).format_map(_FormatValues(values))
    while "  " in text:
        text = text.replace("  ", " ")
    return text.replace("{", "").replace("}", "").strip()


def _conditions(data: dict, firm_id, year) -> set[str]:
    """Compute the applicable event-template conditions for a firm and year."""
    firms = data.get("firms") or {}
    if firm_id is None or firm_id not in firms:
        return set()

    firm = firms[firm_id]
    stage = firm.get("stage")
    yearly = firm.get("yearly") or []
    row = next((item for item in yearly if item.get("year") == year), None)
    conditions = set()
    if row is not None:
        profit = row.get("profit", 0) or 0
        if profit > 0:
            conditions.add("profit")
        elif profit < 0:
            conditions.add("loss")

    year_rows = {
        item.get("year"): item
        for item in yearly
        if item.get("year") in {year - 2, year - 1, year}
    }
    if all(
        item_year in year_rows and (year_rows[item_year].get("profit", 0) or 0) < 0
        for item_year in (year - 2, year - 1, year)
    ):
        conditions.add("loss_streak3")

    peers = [(other_id, other) for other_id, other in firms.items() if other.get("stage") == stage]
    stage_rows = []
    for other_id, other in peers:
        other_row = next(
            (item for item in (other.get("yearly") or []) if item.get("year") == year),
            None,
        )
        if other_row is not None and (other_row.get("revenue", 0) or 0) > 0:
            stage_rows.append((other_id, other_row.get("revenue", 0) or 0))
    firm_revenue = next((revenue for other_id, revenue in stage_rows if other_id == firm_id), None)
    if firm_revenue is not None and stage_rows and firm_revenue == max(revenue for _, revenue in stage_rows):
        conditions.add("largest_in_stage")
    if peers:
        entry_year = firm.get("entry_year", 1)
        if entry_year == min(other.get("entry_year", 1) for _, other in peers):
            conditions.add("first_in_stage")
    if len(peers) > 1 and len(stage_rows) == 1 and stage_rows[0][0] == firm_id:
        conditions.add("last_in_stage")
    return conditions


def _event_sentence(data: dict, event: dict, picker: _Picker, zeit: str = "") -> str:
    """Choose and format a sentence for an event; it starts with the time phrase `zeit`."""
    key = event.get("event", "")
    firm_id = event.get("firm")
    firma = _name(data, firm_id)
    firm = (data.get("firms") or {}).get(firm_id, {}) if firm_id is not None else {}
    stage = firm.get("stage", "")
    stufe = (
        "Gastronomie"
        if firm.get("channel") == "restaurant"
        else STAGE_DE.get(stage, "")
    )
    target = re.search(r"(?:^| )an (\S+?)(?: für|,|$)", str(event.get("details", "")))
    values = {
        "zeit": zeit or _safe_format(ct.CONNECTORS["story"][0], jahr=event.get("year", "")),
        "ziel": _name(data, target.group(1)) if target and target.group(1) in (data.get("firms") or {}) else "",
        "firma": firma if firma else "",
        "jahr": event.get("year", ""),
        "details": _readable(event.get("details", "")),
        "stufe": stufe,
        "ereignis": str(key).replace("_", " "),
    }

    templates = ct.EVENT_TEMPLATES.get(key)
    candidates = []
    if templates:
        conditions = _conditions(data, firm_id, event.get("year")) if firm_id is not None else set()
        for entry in templates:
            when = entry.get("when")
            if when is not None and (firm_id is None or when not in conditions):
                continue
            template = entry.get("text", "")
            if "{firma}" in template and not values["firma"]:
                continue
            if "{ziel}" in template and not values["ziel"]:
                continue
            candidates.append(template)
    if not candidates:
        candidates = list(ct.GENERIC_TEMPLATES)
    return _safe_format(picker.pick(candidates), **values)


def _importance(event: dict) -> int:
    """Return the configured importance of an event."""
    return ct.EVENT_IMPORTANCE.get(event.get("event"), ct.DEFAULT_IMPORTANCE)


def _year_mood(kpi: dict, prev_kpi: dict | None) -> str:
    """Classify a year's total profit as good, bad, or neutral."""
    total_profit = kpi.get("total_profit", 0) or 0
    previous = prev_kpi.get("total_profit", 0) if prev_kpi is not None else None
    if total_profit > 0 and (
        previous is None or total_profit >= previous * 0.9 or previous <= 0
    ):
        return "good"
    if total_profit < 0 or (
        previous is not None and previous > 0 and total_profit < previous * 0.5
    ):
        return "bad"
    return "neutral"


def _follow_ups_for(events: list[dict]) -> dict[int, tuple[str, int]]:
    """Find earlier related events for each event in an event list."""
    follow_ups = {}
    for event in events:
        firm_id = event.get("firm")
        if firm_id is None or firm_id == "":
            continue
        year = event.get("year")
        event_key = event.get("event")
        for follow_key in ct.FOLLOW_UPS:
            earlier_key, later_key = follow_key.split(">", 1)
            if event_key != later_key:
                continue
            earlier = [
                (earlier_event.get("year"), earlier_index)
                for earlier_index, earlier_event in enumerate(events)
                if earlier_event.get("firm") == firm_id
                and earlier_event.get("event") == earlier_key
                and earlier_event.get("year") is not None
                and year is not None
                and earlier_event.get("year") < year
            ]
            if earlier:
                earlier_year, _ = max(earlier, key=lambda item: (item[0], item[1]))
                follow_ups[id(event)] = (follow_key, earlier_year)
            break
    return follow_ups


def template_chronicle(
    data: dict,
    year: int,
    picker: _Picker,
    follow_ups: dict[int, tuple[str, int]],
    max_items: int = 4,
) -> str:
    """Build one year's chronicle from its KPI row and notable events."""
    system = data.get("system") or []
    kpi = next((row for row in system if row.get("year") == year), None)
    if kpi is None:
        return ""
    prev_kpi = next((row for row in system if row.get("year") == year - 1), None)
    mood = _year_mood(kpi, prev_kpi)
    active_firms = sum(kpi.get(f"active_firms_{stage}", 0) for stage in STAGE_DE)
    sentences = [
        _safe_format(
            picker.pick(ct.INTRO[mood]),
            jahr=year,
            gewinn=_chf(kpi.get("total_profit", 0) or 0),
            firmen=active_firms,
        )
    ]

    ignored_events = {
        "capacity_limit",
        "transport_switch",
        "bank_payout",
        "account_opened",
        "inflation",
        "policy_rate_changed",
        "bundesbeitrag",
        "rnd_started",
        "market_entry",
    }
    indexed_events = [
        (index, event)
        for index, event in enumerate(data.get("events") or [])
        if event.get("year") == year
        and event.get("event") not in ignored_events
        and (
            event.get("event") in YEAR_EVENTS | KEY_EVENTS
            or event.get("event") not in ignored_events
        )
    ]
    # Merge repeated kinds of one year into a single group item (or keep only the first one).
    kinds: dict[str, list] = {}
    for item in indexed_events:
        kinds.setdefault(item[1].get("event"), []).append(item)
    items = []
    for kind, members in kinds.items():
        firm_members = [m for m in members if m[1].get("firm") and (data.get("firms") or {}).get(m[1].get("firm"))]
        if len(members) >= 2 and kind in ct.GROUP_TEMPLATES and len(firm_members) >= 2:
            seen, uniq = set(), []
            for m in firm_members:
                if m[1]["firm"] not in seen:
                    seen.add(m[1]["firm"])
                    uniq.append(m)
            if len(uniq) >= 2:
                first = uniq[0]
                group_event = dict(first[1], group=[m[1] for m in uniq])
                items.append((first[0], group_event))
                continue
        items.append(members[0])
    ranked = sorted(
        items,
        key=lambda item: (
            -_importance(item[1]),
            item[1].get("day") if item[1].get("day") is not None else 0,
            item[0],
        ),
    )
    target = (5 if mood != "neutral" else 4) if max_items == 4 else max_items
    limit = max(target, min(3, len(ranked)))
    selected = ranked[:limit]
    selected.sort(
        key=lambda item: (
            item[1].get("day") if item[1].get("day") is not None else 0,
            item[0],
        )
    )

    previous_event = None
    contrast_used = False
    first_done = False
    positive_events = {
        "rnd_success",
        "patent_granted",
        "market_entry",
        "bank_entry",
        "exchange_opened",
        "site_finished",
        "expand_finished",
        "rnd_implemented",
    }
    for _, event in selected:
        if id(event) in follow_ups and not event.get("group"):
            follow_key, earlier_year = follow_ups[id(event)]
            sentences.append(_safe_format(
                picker.pick(ct.FOLLOW_UPS[follow_key]),
                firma=_name(data, event.get("firm")),
                jahr=event.get("year", ""),
                frueher=earlier_year,
            ))
            previous_event = event
            continue

        if not first_done:
            connector_key = "first"
        elif mood == "bad" and event.get("event") in positive_events and not contrast_used:
            connector_key = "contrast"
            contrast_used = True
        else:
            previous_day = previous_event.get("day") if previous_event else None
            current_day = event.get("day")
            if (previous_day is not None and current_day is not None
                    and abs(current_day - previous_day) > 60):
                connector_key = "later"
            else:
                connector_key = "same_year"
        zeit = _safe_format(picker.pick(ct.CONNECTORS[connector_key]), jahr=year)
        if event.get("group"):
            names = [_name(data, e["firm"]) for e in event["group"]]
            count = len(names)
            kind_group = ct.GROUP_TEMPLATES[event["event"]]
            if count == 2:
                sentence = _safe_format(picker.pick(kind_group["two"]), zeit=zeit, liste=f"{names[0]} und {names[1]}")
            else:
                words = {3: "drei", 4: "vier", 5: "fünf", 6: "sechs"}
                sentence = _safe_format(picker.pick(kind_group["many"]), zeit=zeit,
                                        liste=f"{names[0]} und {names[1]}",
                                        anzahl=words.get(count, "mehrere"))
        else:
            sentence = _event_sentence(data, event, picker, zeit)
        sentences.append(sentence)
        first_done = True
        previous_event = event

    if kpi.get("policy_rate") is not None:
        rate = f"{kpi['policy_rate'] * 100:.2f}".replace(".", ",")
        sentences.append(f"Der Leitzins der SNB beträgt für das Folgejahr {rate} Prozent.")
    return " ".join(sentences).replace("ß", "ss")


def template_story(
    data: dict,
    firm_id: str,
    picker: _Picker,
    follow_ups: dict[int, tuple[str, int]],
) -> str:
    """Build a firm's story from its yearly results, events, and exit information."""
    firm = data["firms"][firm_id]
    firma = _name(data, firm_id)
    stage = firm.get("stage", "")
    stufe = (
        "Gastronomie"
        if firm.get("channel") == "restaurant"
        else STAGE_DE.get(stage, "")
    )
    entry_year = firm.get("entry_year", 1)
    sentences = []
    if firma and stufe and entry_year is not None:
        sentences.append(
            _safe_format(
                picker.pick(ct.STORY_START),
                firma=firma,
                stufe=stufe,
                jahr=entry_year,
            )
        )

    active_years = [
        row for row in (firm.get("yearly") or []) if (row.get("revenue", 0) or 0) > 0
    ]
    total_profit = sum(row.get("profit", 0) or 0 for row in active_years)
    if active_years:
        best_year = max(active_years, key=lambda row: row.get("profit", 0) or 0)
        worst_year = min(active_years, key=lambda row: row.get("profit", 0) or 0)
        profit_key = "profit" if total_profit >= 0 else "loss"
        sentences.append(
            _safe_format(
                picker.pick(ct.STORY_PROFIT[profit_key]),
                firma=firma,
                gewinn=_chf(abs(total_profit)),
                bestjahr=best_year.get("year", ""),
                schlechtjahr=worst_year.get("year", ""),
            )
        )

    firm_events = [
        event
        for event in (firm.get("events") or [])
        if event.get("event") in KEY_EVENTS
    ]
    ranked_events = sorted(
        firm_events,
        key=lambda event: (
            -_importance(event),
            event.get("year") if event.get("year") is not None else 0,
        ),
    )[:3]
    ranked_events.sort(key=lambda event: event.get("year") if event.get("year") is not None else 0)

    exit_info = (data.get("exit_analysis") or {}).get(firm_id)
    if exit_info:
        ranked_events = [
            event
            for event in ranked_events
            if event.get("event") not in {"bankruptcy", "takeover", "poisoning", "merger"}
        ]

    local_follow_ups = _follow_ups_for(firm.get("events") or [])
    for event in ranked_events:
        if id(event) in local_follow_ups:
            follow_key, earlier_year = local_follow_ups[id(event)]
            sentence = _safe_format(
                picker.pick(ct.FOLLOW_UPS[follow_key]),
                firma=firma,
                jahr=event.get("year", ""),
                frueher=earlier_year,
            )
        else:
            sentence = _event_sentence(data, event, picker)
        if sentence:
            sentences.append(sentence)

    exit_year = None
    end_key = None
    if exit_info:
        exit_year = exit_info.get("exit_year")
        exit_type = exit_info.get("exit_type")
        end_key = exit_type if exit_type in {"bankruptcy", "takeover", "poisoning", "merger"} else "other_exit"
    elif firm.get("exit_year"):
        exit_year = firm.get("exit_year")
        end_key = "other_exit"
    else:
        system = data.get("system") or []
        if system:
            exit_year = system[-1].get("year")
            end_key = "active"

    if (
        end_key is not None
        and exit_year is not None
        and active_years
        and firma
    ):
        sentences.append(
            _safe_format(
                picker.pick(ct.STORY_END[end_key]),
                firma=firma,
                jahr=exit_year,
                gewinn=_chf(total_profit),
            )
        )
    return " ".join(sentence for sentence in sentences if sentence).replace("ß", "ss")


def generate_texts(
    data: dict,
    llm=None,
    firm_ids=None,
    years=None,
    progress=None,
    use_llm: bool = False,
    seed: int = 0,
) -> dict:
    stories, chronicle = {}, {}
    firm_ids = list(data["firms"]) if firm_ids is None else list(firm_ids)
    years = [k["year"] for k in data["system"]] if years is None else list(years)
    total = len(firm_ids) + len(years)
    done = 0

    if use_llm and llm is not None:
        for firm_id in firm_ids:
            stories[firm_id] = write_checked(
                llm, "Schreibe in 4 bis 6 Sätzen die Geschichte dieser Firma: Gründung, Entwicklung, Wendepunkte "
                     "und wie es endete oder wo sie heute steht.", firm_facts(data, firm_id))
            done += 1
            if progress:
                progress(done, total)
        for year in years:
            chronicle[str(year)] = write_checked(
                llm, "Schreibe einen kurzen Zeitungsbericht (3 bis 5 Sätze) über dieses Jahr im Schweizer Getränkemarkt.",
                year_facts(data, year))
            done += 1
            if progress:
                progress(done, total)
        return {"stories": stories, "chronicle": chronicle}

    story_picker = _Picker(seed)
    chronicle_picker = _Picker(seed + 1)
    story_follow_ups = {
        firm_id: _follow_ups_for((data.get("firms") or {}).get(firm_id, {}).get("events") or [])
        for firm_id in firm_ids
    }
    chronicle_follow_ups = _follow_ups_for(data.get("events") or [])

    for firm_id in firm_ids:
        if firm_id in (data.get("firms") or {}):
            stories[firm_id] = {
                "text": template_story(data, firm_id, story_picker, story_follow_ups[firm_id]),
                "checked": True,
            }
        else:
            stories[firm_id] = {"text": "", "checked": True}
        done += 1
        if progress:
            progress(done, total)
    for year in sorted(years):
        chronicle[str(year)] = {
            "text": template_chronicle(data, year, chronicle_picker, chronicle_follow_ups),
            "checked": True,
        }
        done += 1
        if progress:
            progress(done, total)
    return {"stories": stories, "chronicle": chronicle}


def context_for_question(data: dict, question: str, max_firms: int = 3) -> tuple[str, list[str]]:
    """Pick the facts a question is about: named firms, mentioned years, otherwise the last year."""
    q = question.lower()
    sources, parts = [], []
    hits = []
    for firm_id, firm in data["firms"].items():
        name = firm["name"].lower()
        if name in q or firm_id in q or (len(name.split()[0]) > 3 and name.split()[0] in q):
            hits.append(firm_id)
    for firm_id in hits[:max_firms]:
        parts.append(firm_facts(data, firm_id))
        sources.append(f"Firma {data['firms'][firm_id]['name']}")
    years = [k["year"] for k in data["system"]]
    mentioned = sorted({y for y in years if re.search(rf"jahr {y}\b", q)})
    if not mentioned and not hits:
        mentioned = [years[-1]] if years else []
    for year in mentioned[:3]:
        parts.append(year_facts(data, year))
        sources.append(f"Jahresbericht Jahr {year}")
    by_kind = defaultdict(int)
    for e in data.get("events", []):
        by_kind[e["event"]] += 1
    parts.append("- Ganzer Lauf: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted(by_kind.items())
                                                if k in YEAR_EVENTS | {"bankruptcy", "takeover", "market_entry"}))
    return "\n".join(parts), sources
