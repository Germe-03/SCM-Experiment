"""Phase 12: firm stories and a yearly chronicle written by a language model from checked facts.

Python builds the facts; the model only words them. Every number in a text must appear
in the facts, otherwise the model is told the offending numbers and tries once more; after that
the text is replaced by a plain summary.
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
