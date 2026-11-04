"""Phase 12: firm stories and a yearly chronicle written by a local model from checked facts.

Python builds the facts; the model only words them. Every number in a text must appear
in the facts, otherwise the text is regenerated once and then replaced by a plain summary.
"""

from __future__ import annotations

import re
from collections import defaultdict

from market_sim.llm import unchecked_numbers

STAGE_DE = {"retailer": "Detailhandel", "wholesaler": "Grosshandel", "distributor": "Verteilung", "factory": "Hersteller"}
CAT_DE = {"beer": "Bier", "wine": "Wein", "spirits": "Spirituosen"}
EXIT_DE = {"bankruptcy": "Konkurs", "takeover": "Übernahme", "poisoning": "Vergiftung"}
KEY_EVENTS = {"takeover", "poisoning", "offence_detected", "rnd_success", "site_finished", "expand_finished",
              "restructuring", "strategy_change", "bankruptcy", "stake_bought", "breakup", "spin_off"}
YEAR_EVENTS = {"recession", "raw_material_shortage", "cost_shock", "wage_push", "trend_change", "poisoning",
               "law_enacted", "breakup", "heat_summer", "harvest_failure"}

SYSTEM = (
    "Du bist Wirtschaftsjournalist und schreibst auf Deutsch (Schweizer Rechtschreibung, kein ß). "
    "Verwende ausschliesslich die gegebenen Fakten. Erfinde keine Zahlen, Namen oder Ursachen. "
    "Die Jahre heissen 'Jahr 1', 'Jahr 2' und so weiter; nenne nie Kalenderjahre wie 2002. "
    "Übernimm Beträge genau so, wie sie in den Fakten stehen. "
    "Schreibe sachlich und verständlich, ohne Aufzählung, ohne Überschrift."
)


def _mio(value: float) -> str:
    return f"{value / 1e6:,.0f}".replace(",", "'")


def _readable(details: str) -> str:
    """Write amounts like 51'609'492 CHF as 52 Mio. CHF, as a journalist would."""
    def to_mio(match: re.Match) -> str:
        value = float(match.group(1).replace("'", ""))
        return f"{_mio(value)} Mio. CHF" if abs(value) >= 1e6 else match.group(0)
    return re.sub(r"(-?\d[\d']*) CHF", to_mio, str(details))


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
        lines.append(f"Gewinn insgesamt: {_mio(total)} Mio. CHF")
        lines.append(f"Bestes Jahr: Jahr {best['year']} mit {_mio(best['profit'])} Mio. CHF Gewinn")
        lines.append(f"Schlechtestes Jahr: Jahr {worst['year']} mit {_mio(worst['profit'])} Mio. CHF Gewinn")
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
        f"Gewinn aller Firmen: {_mio(kpi['total_profit'])} Mio. CHF",
        f"Anteil bediente Nachfrage: {kpi['service_level'] * 100:.0f} Prozent",
        f"Aktive Firmen: {active}",
        f"Markteintritte: {kpi.get('market_entries', 0)}, Konkurse: {kpi.get('bankruptcies', 0)}, Übernahmen: {kpi.get('takeovers', 0)}",
    ]
    if kpi.get("trend"):
        lines.append(f"Aktueller Trend: {kpi['trend']}")
    profits = []
    for firm_id, firm in data["firms"].items():
        row = next((y for y in firm.get("yearly", []) if y["year"] == year), None)
        if row and row.get("revenue", 0) > 0:
            profits.append((row.get("profit", 0), firm["name"]))
    profits.sort()
    if profits:
        lines.append("Grösste Gewinner: " + ", ".join(f"{n} ({_mio(p)} Mio. CHF)" for p, n in profits[-2:][::-1]))
        lines.append("Grösste Verlierer: " + ", ".join(f"{n} ({_mio(p)} Mio. CHF)" for p, n in profits[:2]))
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
        if text and not unchecked_numbers(text, facts):
            return {"text": text, "checked": True}
        prompt = (f"{task} Verwende nur Zahlen, die wörtlich in den Fakten stehen.\n\nFAKTEN:\n{facts}")
    plain = " ".join(line.lstrip("- ") + "." for line in facts.splitlines()[:5])
    return {"text": plain, "checked": False}


def generate_texts(data: dict, llm, firm_ids=None, years=None, progress=None) -> dict:
    stories, chronicle = {}, {}
    firm_ids = list(data["firms"]) if firm_ids is None else firm_ids
    years = [k["year"] for k in data["system"]] if years is None else years
    total = len(firm_ids) + len(years)
    done = 0
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
