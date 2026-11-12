from __future__ import annotations

import math

from market_sim.game.world_market import _day_stats, _recent, _runtime_total
from market_sim.kpi import ARCHETYPE_DE, PROJECT_DE
from market_sim.models import behaviour_of
from market_sim.research_tree import tree_key


__all__ = ["research_tree", "autopilot", "classification", "glossary", "costs", "bottleneck", "year_baseline"]


GLOSSARY = [
    {"term": "Umsatz", "text": "Geld, das die Firma mit dem Verkauf von Bier und Getränken einnimmt. Davon sind Kosten noch nicht abgezogen."},
    {"term": "Gewinn", "text": "Was nach Abzug der Kosten vom Umsatz übrig bleibt. Ein Verlust ist ein negativer Gewinn."},
    {"term": "Kasse", "text": "Geld, das der Firma gerade zur Verfügung steht. Damit bezahlt sie zum Beispiel Löhne, Rohstoffe und Kredite."},
    {"term": "Rückstand", "text": "Bestellungen, die noch nicht geliefert wurden. Ein grosser Rückstand kann Kundinnen und Kunden kosten."},
    {"term": "Lagerziel", "text": "Wie viele Tage Vorrat die Firma anstrebt. Mehr Vorrat kann Lieferungen sichern, kostet aber Platz und Geld."},
    {"term": "Überstunden", "text": "Zusätzliche Arbeitszeit, wenn mehr produziert oder geliefert werden muss. Sie kann helfen, kostet aber oft mehr."},
    {"term": "Lohnniveau", "text": "Die Löhne der Firma im Vergleich zu ihrem Startwert. Höhere Löhne können helfen, Mitarbeitende zu halten."},
    {"term": "Qualität", "text": "Wie gut die Getränke der Firma sein sollen. Höhere Qualität kann mehr Kosten verursachen."},
    {"term": "Ruf", "text": "Wie Kundinnen und Kunden die Firma einschätzen. Ein guter Ruf kann die Nachfrage stärken."},
    {"term": "Marktanteil", "text": "Der Anteil am Verkauf in einem Markt, den die Firma erreicht. Er hängt unter anderem von Preis und Nachfrage ab."},
    {"term": "Servicegrad", "text": "Wie gut die Firma Bestellungen rechtzeitig erfüllen kann. Ein hoher Servicegrad bedeutet weniger fehlende Lieferungen."},
    {"term": "Kapazität", "text": "Wie viel die Firma an einem Tag herstellen oder liefern kann. Sie hängt unter anderem von Anlagen und Fahrzeugen ab."},
    {"term": "Auslastung", "text": "Wie stark die vorhandene Kapazität genutzt wird. Eine sehr hohe Auslastung lässt wenig Platz für zusätzliche Nachfrage."},
    {"term": "Leitzins", "text": "Ein wichtiger Zinssatz der Zentralbank. Er beeinflusst die Kosten von Krediten."},
    {"term": "Teuerung", "text": "Wie stark die Preise im Allgemeinen steigen. Sie kann Kosten und Verkaufspreise verändern."},
    {"term": "Wechselkurs", "text": "Der Wert des Schweizer Frankens gegenüber anderen Währungen. Er beeinflusst zum Beispiel importierte Rohstoffe."},
    {"term": "Kredit", "text": "Geld, das eine Bank der Firma leiht. Die Firma muss es mit Zins zurückzahlen."},
    {"term": "Zins", "text": "Der Preis dafür, geliehenes Geld zu nutzen. Ein höherer Zins macht einen Kredit teurer."},
    {"term": "Dividende", "text": "Ein Teil des Bilanzgewinns, der an die Aktionärinnen und Aktionäre ausgezahlt wird. Eine Auszahlung lässt weniger Geld in der Firma."},
    {"term": "Börsengang", "text": "Wenn eine Firma an die Börse geht und ihre Aktien gehandelt werden können. Dafür muss sie die Regeln der Simulation erfüllen."},
    {"term": "Aktie", "text": "Ein Anteil an einer Firma. Der Wert einer Aktie kann sich mit dem Geschäftserfolg verändern."},
    {"term": "ETF", "text": "Ein Fonds, der viele Anlagen bündelt und an der Börse gehandelt wird. Er verteilt das Risiko auf mehrere Anlagen."},
    {"term": "Holding", "text": "Eine Firma, die Anteile an anderen Firmen hält. Sie kann ihre Tochterfirmen verwalten."},
    {"term": "Tochter", "text": "Eine Firma, die einer Holding gehört. Ihre Gewinne können an die Holding fliessen."},
    {"term": "CEO", "text": "Die Geschäftsleitung einer Firma. Sie trifft wichtige Entscheide für den Betrieb."},
    {"term": "Patent", "text": "Ein zeitlich begrenztes Recht an einer erforschten Neuerung. Es kann anderen Firmen die Nutzung erschweren."},
    {"term": "Forschungsstufe", "text": "Ein Vorhaben im Forschungsbaum, das einen Vorteil für die Firma bringen kann. Forschung braucht Zeit und Geld."},
    {"term": "Umsetzung", "text": "Der Schritt, bei dem eine erforschte Stufe in der Firma eingeführt wird. Auch die Umsetzung kann Zeit und Geld kosten."},
    {"term": "Rohstoffindex", "text": "Ein Richtwert für die Preise wichtiger Rohstoffe. Er hilft, die Entwicklung der Einkaufskosten zu verfolgen."},
    {"term": "Vorkauf", "text": "Rohstoffe werden vor dem eigentlichen Bedarf gekauft. Das kann bei später höheren Preisen helfen, bindet aber Geld und Lagerplatz."},
    {"term": "Aufschlag", "text": "Der Betrag, um den ein Restaurantpreis über dem Ladenpreis liegt. Er hilft, Kosten des Restaurants zu decken."},
    {"term": "Wettbewerbsbehörde", "text": "Eine Stelle, die den fairen Wettbewerb schützt. Verstösse können Folgen für die Firma haben."},
    {"term": "Autopilot", "text": "Die Simulation trifft bestimmte Entscheide für die Firma. Die genaue Regel hängt vom jeweiligen Bereich ab."},
    {"term": "Einstufung", "text": "Ein Typ, den die Simulation aus dem Verhalten der Firma ableitet. Sie wird jedes Jahr neu geprüft."},
]


COST_FIELDS = (
    "revenue",
    "purchase_cost",
    "wage_cost",
    "fixed_cost",
    "handling_cost",
    "cumulative_holding_cost",
    "cumulative_backlog_cost",
    "hiring_cost",
    "rnd_spend",
    "marketing_cost",
    "interest_cost",
    "profit",
)


def _text(value, default: str = "") -> str:
    """Gibt einen sicheren Text ohne scharfes s zurück."""
    try:
        return str(value).replace("ß", "ss")
    except Exception:
        return default


def _number(value, default: float = 0.0, digits: int = 4) -> float:
    """Liest eine endliche Zahl und rundet sie."""
    try:
        result = float(value)
        if not math.isfinite(result):
            return default
        return round(result, digits)
    except Exception:
        return default


def _json_value(value):
    """Wandelt Werte defensiv in JSON-taugliche Grundtypen um."""
    try:
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return _number(value)
        if isinstance(value, str):
            return _text(value)
        if isinstance(value, dict):
            return {_text(key): _json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_value(item) for item in value]
    except Exception:
        return None
    return None


def _read(obj, name: str, default=None):
    """Liest ein Attribut ohne Fehler nach aussen weiterzugeben."""
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _read_map(mapping, key, default=None):
    """Liest einen Eintrag aus einer Zuordnung defensiv."""
    try:
        return mapping.get(key, default)
    except Exception:
        return default


def _read_path(obj, *names, default=None):
    """Liest eine kurze Attributkette defensiv."""
    current = obj
    for name in names:
        current = _read(current, name, None)
        if current is None:
            return default
    return current


def _readable(name: str) -> str:
    """Macht aus einem technischen Namen einen lesbaren Text."""
    value = _text(name).replace("_", " ")
    return value[:1].upper() + value[1:] if value else ""


def _stage_label(name: str) -> str:
    """Erzeugt die deutsche Anzeige für eine Forschungsstufe."""
    try:
        direct = PROJECT_DE.get(name)
        if direct is not None:
            return _text(direct)
        for suffix, roman in (("_2", " II"), ("_3", " III")):
            if name.endswith(suffix):
                basis = name[:-len(suffix)]
                label = PROJECT_DE.get(basis, _readable(basis))
                return _text(label) + roman
        return _readable(name)
    except Exception:
        return _readable(name)


def research_tree(runner, state, player_id, **extra) -> dict:
    """Zeigt den Forschungsbaum und den laufenden Auftrag."""
    result = {"tree": None, "stages": [], "running": None}
    try:
        env = _read(runner, "env")
        lab = _read(runner, "lab")
        if lab is None:
            lab = _read(env, "research")
        if lab is None or _read(lab, "stages") is None or _read(lab, "progress") is None:
            return result

        network = _read(runner, "network")
        firm_method = _read(network, "firm")
        if not callable(firm_method):
            return result
        firm = firm_method(player_id)
        tree = tree_key(firm)
        result["tree"] = _text(tree)
        tree_stages = _read_map(_read(lab, "stages"), tree, {})
        if not isinstance(tree_stages, dict):
            return result

        year = _read(state, "year", 0)
        try:
            year = int(year)
        except Exception:
            year = 0

        progress = _read_map(_read(lab, "progress"), player_id, {})
        running_map = _read(lab, "running", {})
        running_record = _read_map(running_map, player_id)
        running_name = None
        if isinstance(running_record, (tuple, list)) and running_record:
            running_name = _text(running_record[0])

        options = set()
        options_method = _read(lab, "options")
        if callable(options_method):
            try:
                options = {
                    _text(_read(option, "name", ""))
                    for option in options_method(firm)
                    if _read(option, "name") is not None
                }
            except Exception:
                options = set()

        available_stages = []
        for key, stage in tree_stages.items():
            try:
                name = _text(_read(stage, "name", key))
                available_method = _read(lab, "available")
                if not callable(available_method) or not available_method(firm, stage):
                    continue
                requires_value = _read(stage, "requires", [])
                if not isinstance(requires_value, (list, tuple)):
                    requires_value = []
                requires = [_text(item) for item in requires_value]
                available_stages.append((name, stage, requires))
            except Exception:
                continue

        names = {name for name, _, _ in available_stages}
        requirements = {name: requires for name, _, requires in available_stages}

        def depth(name, path=None):
            if path is None:
                path = set()
            if name in path:
                return 0
            path = set(path)
            path.add(name)
            parents = [item for item in requirements.get(name, []) if item in names]
            if not parents:
                return 0
            return 1 + max(depth(parent, path) for parent in parents)

        stage_rows = []
        for name, stage, requires in available_stages:
            try:
                status_value = _read_map(progress, player_id, {}) if False else None
                try:
                    status_value = progress.get(name, "") if isinstance(progress, dict) else ""
                except Exception:
                    status_value = ""
                if status_value == "implemented":
                    status = "implemented"
                elif status_value == "researched":
                    status = "researched"
                elif running_name == name:
                    status = "running"
                elif name in options:
                    status = "available"
                else:
                    status = "locked"

                cost_value = 0.0
                cost_method = _read(lab, "research_cost")
                if callable(cost_method):
                    try:
                        cost_value = cost_method(tree, stage, year)
                    except Exception:
                        cost_value = 0.0
                branch = _read(stage, "branch")
                kind = _read(stage, "kind")
                stage_rows.append({
                    "name": name,
                    "label": _stage_label(name),
                    "branch": _text(branch) if branch is not None else "",
                    "kind": _text(kind) if kind is not None else "",
                    "cost": _number(cost_value, digits=0),
                    "duration_days": int(_number(_read(stage, "duration_days", 0), digits=0)),
                    "effect": _number(_read(stage, "effect", 0.0), digits=4),
                    "requires": requires,
                    "status": status,
                    "depth": depth(name),
                    "patentable": bool(_read(stage, "patentable", False)),
                })
            except Exception:
                continue

        stage_rows.sort(key=lambda row: (row["depth"], row["label"]))
        result["stages"] = stage_rows

        if isinstance(running_record, (tuple, list)) and len(running_record) >= 3:
            try:
                period = _read(env, "period", 0)
                days_left = max(0, int(float(running_record[2]) - float(period)))
                result["running"] = {"stage": running_name or "", "days_left": days_left}
            except Exception:
                result["running"] = {"stage": running_name or "", "days_left": 0}
    except Exception:
        return result
    return result


def _percent_text(value) -> str:
    """Formatiert einen Anteil als Prozenttext."""
    return f"{_number(value) * 100:.0f} %"


def _autopilot_item(text: str, value):
    """Erstellt einen sicheren Autopilot-Eintrag."""
    return {"text": _text(text), "value": _json_value(value)}


def autopilot(runner, state, player_id, **extra) -> dict:
    """Erklärt die automatischen Entscheide der Simulation."""
    result = {}

    try:
        firm = _read(_read(runner, "network"), "firm")
        firm = firm(player_id) if callable(firm) else None
    except Exception:
        firm = None

    try:
        marketing_value = None
        marketing = _read(runner, "marketing")
        daily_budget = _read_map(_read(marketing, "daily_budget"), player_id)
        if daily_budget is not None:
            days = _read_path(runner, "config", "simulation", "days_per_year", default=0)
            marketing_value = _number(daily_budget) * _number(days)
        else:
            try:
                config = _read(runner, "config")
                marketing_cfg = _read(config, "marketing")
                share_map = _read(marketing_cfg, "budget_share", {})
                share = _read_map(share_map, behaviour_of(firm), 0.0)
                runtime = _read_map(_read(env := _read(runner, "env"), "runtimes", {}), player_id)
                marketing_value = _number(share) * _number(_read(runtime, "last_year_revenue", 0.0))
            except Exception:
                marketing_value = None
        result["marketing_budget"] = _autopilot_item(
            "Das Budget ist ein Anteil vom Umsatz des Vorjahrs. Gross- und Verteilhandel werben nicht bei Kundinnen und Kunden.",
            marketing_value,
        )
    except Exception:
        result["marketing_budget"] = _autopilot_item(
            "Das Budget ist ein Anteil vom Umsatz des Vorjahrs. Gross- und Verteilhandel werben nicht bei Kundinnen und Kunden.",
            None,
        )

    try:
        lab = _read(runner, "lab")
        if lab is None:
            lab = _read(_read(runner, "env"), "research")
        record = _read_map(_read(lab, "running", {}), player_id)
        value = record[0] if isinstance(record, (tuple, list)) and record else None
        result["research_target"] = _autopilot_item(
            "Die Simulation wählt zufällig eine mögliche Stufe, gewichtet nach Auswahlgewicht und geschätzter Wirkung. Sie forscht nur, wenn die Firma Gewinn macht.",
            value,
        )
    except Exception:
        result["research_target"] = _autopilot_item(
            "Die Simulation wählt zufällig eine mögliche Stufe, gewichtet nach Auswahlgewicht und geschätzter Wirkung. Sie forscht nur, wenn die Firma Gewinn macht.",
            None,
        )

    try:
        result["credit_mode"] = _autopilot_item(
            "Die Firma nimmt einen Kredit, wenn die Kasse für eine Investition nicht reicht oder wenn der Kredit günstig ist.",
            "auto",
        )
    except Exception:
        result["credit_mode"] = _autopilot_item(
            "Die Firma nimmt einen Kredit, wenn die Kasse für eine Investition nicht reicht oder wenn der Kredit günstig ist.",
            None,
        )

    try:
        bank_id = None
        env = _read(runner, "env")
        for banking in (_read(env, "banking"), _read(runner, "banking")):
            primary = _read(banking, "primary_bank")
            if callable(primary):
                try:
                    bank = primary(player_id)
                    bank_id = _read(bank, "id")
                    if bank_id is not None:
                        break
                except Exception:
                    pass
        result["bank_id"] = _autopilot_item(
            "Die Firma wählt die beste Bank nach Zins und Sicherheit, gemessen am Eigenkapital.",
            bank_id,
        )
    except Exception:
        result["bank_id"] = _autopilot_item(
            "Die Firma wählt die beste Bank nach Zins und Sicherheit, gemessen am Eigenkapital.",
            None,
        )

    try:
        payout = _read_path(runner, "profit_distribution", "cfg", "payout_ratio", default=None)
        if payout is None:
            payout = 0.4
        result["payout_ratio"] = _autopilot_item(
            "Ein Anteil des Bilanzgewinns wird als Dividende ausgezahlt, nach Verlustverrechnung und Reserve. Mindestens drei Monatskosten bleiben als Kasse reserviert.",
            payout,
        )
    except Exception:
        result["payout_ratio"] = _autopilot_item(
            "Ein Anteil des Bilanzgewinns wird als Dividende ausgezahlt, nach Verlustverrechnung und Reserve. Mindestens drei Monatskosten bleiben als Kasse reserviert.",
            0.4,
        )

    try:
        result["listing"] = _autopilot_item(
            "Die Firma geht automatisch ab dem Jahr an die Börse, ab dem sie handelbar ist, wenn die Börse eingeschaltet ist.",
            _read(runner, "stock_market") is not None,
        )
    except Exception:
        result["listing"] = _autopilot_item(
            "Die Firma geht automatisch ab dem Jahr an die Börse, ab dem sie handelbar ist, wenn die Börse eingeschaltet ist.",
            False,
        )

    try:
        result["transport_mode"] = _autopilot_item(
            "Die Simulation vergleicht die Kosten der eigenen Flotte mit denen eines Transportdienstes und nimmt die günstigere Möglichkeit.",
            _read(firm, "transport_mode"),
        )
    except Exception:
        result["transport_mode"] = _autopilot_item(
            "Die Simulation vergleicht die Kosten der eigenen Flotte mit denen eines Transportdienstes und nimmt die günstigere Möglichkeit.",
            None,
        )

    try:
        threshold = _read_path(runner, "config", "geography", "expand_utilization", default=0.0)
        result["auto_invest"] = _autopilot_item(
            f"Die Firma baut aus, sobald die Auslastung über {_percent_text(threshold)} liegt.",
            True,
        )
    except Exception:
        result["auto_invest"] = _autopilot_item(
            "Die Firma baut aus, sobald die Auslastung über dem festgelegten Wert liegt.",
            True,
        )

    try:
        courage = _read_map(_read(_read(runner, "env"), "commodity_courage", {}), player_id, 0.5)
        result["commodity_courage"] = _autopilot_item(
            "Dieser Wert zeigt, wie mutig die Firma Rohstoffe vorkauft oder auf Vorrat kauft: 0 ist vorsichtig, 1 ist mutig.",
            courage,
        )
    except Exception:
        result["commodity_courage"] = _autopilot_item(
            "Dieser Wert zeigt, wie mutig die Firma Rohstoffe vorkauft oder auf Vorrat kauft: 0 ist vorsichtig, 1 ist mutig.",
            0.5,
        )

    try:
        markup = _read_path(runner, "config", "restaurants", "markup", default=None)
        result["markup_factor"] = _autopilot_item(
            "Das ist der normale Aufschlag des Restaurantpreises gegenüber dem Ladenpreis.",
            markup,
        )
    except Exception:
        result["markup_factor"] = _autopilot_item(
            "Das ist der normale Aufschlag des Restaurantpreises gegenüber dem Ladenpreis.",
            None,
        )

    try:
        weights = _read(_read(runner, "config"), "supplier_score_weights", {})
        labels = (
            ("price", "Preis"),
            ("reliability", "Zuverlässigkeit"),
            ("quality", "Qualität"),
            ("reputation", "Ruf"),
            ("lead_time", "Lieferzeit"),
            ("capacity", "Kapazität"),
        )
        parts = []
        for key, label in labels:
            weight = _read_map(weights, key, None)
            if weight is None:
                weight = _read(weights, key, 0.0)
            parts.append(f"{label} {_percent_text(weight)}")
        text = "Die Simulation wählt den Lieferanten nach einem Wert aus " + ", ".join(parts) + "."
        result["supplier"] = _autopilot_item(text, None)
    except Exception:
        result["supplier"] = _autopilot_item(
            "Die Simulation wählt den Lieferanten nach Preis, Zuverlässigkeit, Qualität, Ruf, Lieferzeit und Kapazität.",
            None,
        )

    keys = (
        "marketing_budget",
        "research_target",
        "credit_mode",
        "bank_id",
        "payout_ratio",
        "listing",
        "transport_mode",
        "auto_invest",
        "commodity_courage",
        "markup_factor",
        "supplier",
    )
    for key in keys:
        if key not in result:
            result[key] = _autopilot_item("Die Simulation entscheidet automatisch.", None)
    return {key: result[key] for key in keys}


def classification(runner, state, player_id, **extra) -> dict:
    """Erklärt die Einstufung und zeigt ihren Verlauf."""
    archetype = None
    label = None
    history = []
    explanations = {
        "low_cost": "Die Firma setzt tiefe Preise und eher knappe Löhne ein. Sie achtet eher wenig auf Qualität und Forschung und hält ein kleines Lager.",
        "standard": "Die Firma liegt bei Preis, Löhnen, Qualität, Forschung und Lager meist im mittleren Bereich.",
        "premium": "Die Firma setzt hohe Preise, hohe Qualität, gute Löhne und viel Forschung ein.",
        "reliable": "Die Firma hält ein grosses Lager, geht wenig Risiko ein und macht wenige Überstunden. Lieferfähigkeit ist wichtiger als der Preis.",
        "growth": "Die Firma geht viel Risiko ein, investiert viel in Forschung und Ausbau und setzt eher tiefe Preise für mehr Marktanteil. Sie nutzt viele Überstunden.",
    }
    try:
        network = _read(runner, "network")
        firm_method = _read(network, "firm")
        firm = firm_method(player_id) if callable(firm_method) else None
        raw_archetype = _read(firm, "archetype")
        archetype = _text(raw_archetype) if raw_archetype is not None else None
        if archetype:
            label = _text(ARCHETYPE_DE.get(archetype, archetype))
        explanation = explanations.get(
            archetype,
            "Die Simulation ordnet die Firma nach ihrem beobachteten Verhalten ein.",
        )
    except Exception:
        explanation = "Die Simulation ordnet die Firma nach ihrem beobachteten Verhalten ein."

    explanation += (
        " Dabei beobachtet sie jedes Jahr sechs Dinge: Preis im Preisband, Lohn im Vergleich zum Start, "
        "Forschungsausgaben, angestrebte Qualität, Lagerziel in Tagen und Überstunden. "
        "Die Einstufung wird jedes Jahr neu geprüft und kann sich durch deine Entscheide ändern."
    )

    try:
        reports = _read(state, "annual_reports", [])
        if isinstance(reports, (list, tuple)):
            for yearly in reports:
                try:
                    report = _read_map(yearly, player_id)
                    if report is None:
                        continue
                    report_archetype = _read(report, "archetype")
                    if isinstance(report, dict):
                        report_archetype = report.get("archetype")
                    if not report_archetype:
                        continue
                    report_year = _read(report, "year")
                    if isinstance(report, dict):
                        report_year = report.get("year")
                    report_label = ARCHETYPE_DE.get(report_archetype, report_archetype)
                    history.append({
                        "year": _json_value(report_year),
                        "label": _text(report_label),
                    })
                except Exception:
                    continue
    except Exception:
        history = []

    return {
        "archetype": _json_value(archetype),
        "label": _json_value(label),
        "explanation": _text(explanation),
        "history": history,
    }


def glossary(runner, state, player_id, **extra) -> dict:
    """Gibt die Begriffe der Hilfe zurück."""
    try:
        return {"terms": [dict(item) for item in GLOSSARY]}
    except Exception:
        return {"terms": []}


def year_baseline(runner, player_id, year) -> dict:
    """Speichert und liefert die Laufzeitwerte vom Jahresbeginn."""
    empty_values = {field: 0.0 for field in COST_FIELDS}
    try:
        try:
            year = int(year)
        except Exception:
            year = 1

        env = _read(runner, "env")
        runtime = _read_map(_read(env, "runtimes", {}), player_id)
        marks = _read(runner, "_game_year_marks", None)
        if not isinstance(marks, dict):
            marks = {}
            try:
                setattr(runner, "_game_year_marks", marks)
            except Exception:
                pass

        record = _read_map(marks, player_id)
        if not isinstance(record, dict) or record.get("year") != year:
            values = {
                field: _number(_read(runtime, field, 0.0))
                for field in COST_FIELDS
            }
            record = {"year": year, "values": values}
            try:
                marks[player_id] = record
            except Exception:
                pass
            return values

        stored_values = record.get("values")
        if not isinstance(stored_values, dict):
            stored_values = {}
        values = {
            field: _number(stored_values.get(field, 0.0))
            for field in COST_FIELDS
        }
        record["values"] = values
        try:
            marks[player_id] = record
        except Exception:
            pass
        return values
    except Exception:
        return empty_values


def costs(runner, state, player_id, **extra) -> dict:
    """Zeigt die Kosten und den Gewinn des laufenden Jahres."""
    try:
        try:
            year = int(extra.get("year") or _read(state, "year", 1))
        except Exception:
            year = 1
        try:
            config = _read(runner, "config")
            unit_size = int(_read_path(config, "unit_scale", "real_units_per_sim_unit", default=1))
        except Exception:
            unit_size = 1

        env = _read(runner, "env")
        runtime = _read_map(_read(env, "runtimes", {}), player_id)
        baseline = year_baseline(runner, player_id, year)

        def annual_value(field, costs_field=False):
            current = _number(_read(runtime, field, 0.0))
            start = _number(_read_map(baseline, field, 0.0))
            value = current - start
            if costs_field:
                value = max(0.0, value)
            return _number(value, digits=2)

        revenue_year = annual_value("revenue")
        profit_year = _number(
            _number(_read(runtime, "profit", 0.0))
            - _number(_read_map(baseline, "profit", 0.0)),
            digits=2,
        )

        entries = [
            ("purchase", "Wareneinkauf", "purchase_cost"),
            ("wages", "Löhne", "wage_cost"),
            ("fixed", "Miete und Fixkosten", "fixed_cost"),
            ("handling", "Umschlag", "handling_cost"),
            ("holding", "Lagerkosten", "cumulative_holding_cost"),
            ("backlog", "Lieferrückstand", "cumulative_backlog_cost"),
            ("hiring", "Einstellungen", "hiring_cost"),
            ("rnd", "Forschung", "rnd_spend"),
            ("marketing", "Marketing", "marketing_cost"),
            ("interest", "Zinsen", "interest_cost"),
        ]
        items = []
        marketing_year = annual_value("marketing_cost", costs_field=True)
        for key, label, field in entries:
            chf_year = annual_value(field, costs_field=True)
            if key == "fixed":
                chf_year = _number(max(0.0, chf_year - marketing_year), digits=2)
            share = chf_year / revenue_year if revenue_year > 0 else 0.0
            items.append({
                "key": _text(key),
                "label": _text(label),
                "chf_year": _number(chf_year, digits=2),
                "share": _number(share, digits=2),
            })
        items.sort(key=lambda item: item["chf_year"], reverse=True)
        return {
            "year": year,
            "unit_size": unit_size,
            "revenue_year": _number(revenue_year, digits=2),
            "profit_year": _number(profit_year, digits=2),
            "items": items,
        }
    except Exception:
        return {
            "year": 1,
            "unit_size": 1,
            "revenue_year": 0.0,
            "profit_year": 0.0,
            "items": [],
        }


def bottleneck(runner, state, player_id, **extra) -> dict:
    """Ermittelt den wahrscheinlichsten Engpass der Firma."""
    texts = {
        "lager": "Dein Engpass ist das Lager: Der Vorrat reicht nicht einmal für einen Tag, bestelle mehr Rohstoffe oder erhöhe das Lagerziel.",
        "personal": "Dein Engpass ist das Personal: Du verkaufst fast alles, was du herstellen kannst, stelle mehr Mitarbeitende ein.",
        "transport": "Dein Engpass ist der Transport: Deine Lastwagen schaffen nicht mehr als dein heutiger Absatz, ein weiterer Lastwagen kann sich lohnen.",
        "nachfrage": "Dein Engpass ist die Nachfrage: Du könntest mehr herstellen, als gekauft wird, senke den Preis oder wirb mehr.",
    }
    result = {
        "kind": "nachfrage",
        "text": texts["nachfrage"],
        "capacity_per_day": 0.0,
        "demand_per_day": 0.0,
        "sales_per_day": 0.0,
        "transport_per_day": None,
        "days_of_stock": 999.0,
    }
    try:
        try:
            config = _read(runner, "config")
            unit_size = int(_read_path(config, "unit_scale", "real_units_per_sim_unit", default=1))
        except Exception:
            unit_size = 1
        if unit_size <= 0:
            unit_size = 1

        env = _read(runner, "env")
        try:
            capacity = _number(env._effective_capacity(player_id))
        except Exception:
            capacity = 0.0

        demand = _day_stats(_recent(state, "recent_demand", player_id))["avg"]
        sales = _day_stats(_recent(state, "recent_sales", player_id))["avg"]

        runtimes = _read(env, "runtimes", {})
        runtime = _read_map(runtimes, player_id)
        inventory = _runtime_total(runtime, ("inventory", "stock"))
        days_of_stock = inventory / sales if sales > 0 else 999.0

        transport = None
        try:
            geography = _read(env, "geography")
            trucks = _read(geography, "trucks")
            lookup = _read(trucks, "capacity")
            if callable(lookup):
                truck_capacity = _number(lookup(player_id), None)
                if truck_capacity is not None and truck_capacity > 0:
                    transport = truck_capacity * unit_size
        except Exception:
            transport = None

        capacity_per_day = capacity * unit_size
        demand_per_day = demand * unit_size
        sales_per_day = sales * unit_size

        if days_of_stock < 1 and sales < demand:
            kind = "lager"
        elif sales >= 0.95 * capacity and demand > capacity and capacity > 0:
            kind = "personal"
        elif transport is not None and transport < sales_per_day * 1.05:
            kind = "transport"
        else:
            kind = "nachfrage"

        result = {
            "kind": kind,
            "text": texts[kind],
            "capacity_per_day": _number(capacity_per_day, digits=2),
            "demand_per_day": _number(demand_per_day, digits=2),
            "sales_per_day": _number(sales_per_day, digits=2),
            "transport_per_day": _number(transport, digits=2) if transport is not None else None,
            "days_of_stock": _number(days_of_stock, digits=2),
        }
    except Exception:
        pass
    return result
