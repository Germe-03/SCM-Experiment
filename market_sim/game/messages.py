"""Spielermeldungen aus Ereignissen der Simulation."""

from __future__ import annotations


_PRIVATE_EVENTS = {
    "rnd_started",
    "rnd_success",
    "rnd_inherited",
    "supplier_switch",
    "strategy_change",
    "credit_rejected",
    "loan_granted",
    "account_opened",
    "bank_switched",
    "holding_cover",
    "holding_no_cover",
    "holding_sweep",
}

_IMPORTANT_MARKET_EVENTS = {
    "law_enacted",
    "recession",
    "inflation",
    "policy_rate_emergency",
    "bankruptcy",
    "takeover",
    "merger_formed",
    "poisoning",
}


def _details(event: dict) -> dict:
    """Liefert Details nur dann, wenn sie als Wörterbuch vorliegen."""
    value = event.get("details")
    return value if isinstance(value, dict) else {}


def _value(details: dict, *keys: str) -> object | None:
    """Gibt den ersten vorhandenen Detailwert zurück."""
    for key in keys:
        value = details.get(key)
        if value is not None and value != "":
            return value
    return None


def _text(value: object) -> str:
    """Wandelt einen Wert in Text um und ersetzt das Eszett."""
    return str(value).replace("ß", "ss")


def _firm_value(value: object, names: dict[str, str]) -> str:
    """Löst eine Firmen-ID in einen Namen auf."""
    if value is None:
        return ""
    try:
        resolved = names.get(value, value)
    except TypeError:
        resolved = value
    return _text(resolved)


def _with_value(sentence: str, details: dict, keys: tuple[str, ...], label: str) -> str:
    value = _value(details, *keys)
    if value is None:
        return sentence
    return f"{sentence[:-1]}: {label} {_text(value)}."


def _with_firm(sentence: str, details: dict, names: dict[str, str], keys: tuple[str, ...], label: str) -> str:
    value = _value(details, *keys)
    if value is None:
        return sentence
    resolved = _firm_value(value, names)
    return f"{sentence[:-1]}: {label} {resolved}."


def _company_event(own: bool, name: str, own_text: str, market_text: str) -> str:
    """Wählt die Formulierung aus der Sicht des Spielers oder des Markts."""
    return own_text if own else market_text.format(name=name)


def _market_entry(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    stage = _value(details, "stage", "level", "stufe")
    if own:
        sentence = "Du bist in den Markt eingetreten."
    else:
        sentence = f"{name} ist in den Markt eingetreten."
    if stage is not None:
        sentence = f"{sentence[:-1]} und ist in Stufe {_text(stage)} gestartet."
    return sentence


def _bankruptcy(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return _company_event(own, name, "Deine Firma ist in Konkurs gegangen.", "{name} ist in Konkurs gegangen.")


def _takeover(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Firma wurde übernommen.", "{name} wurde übernommen.")
    return _with_firm(
        sentence,
        details,
        names,
        ("by", "buyer", "acquirer", "takeover_by", "partner", "partner_id"),
        "Käufer",
    )


def _takeover_blocked(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(
        own,
        name,
        "Du hast eine Übernahme verhindert.",
        "Die geplante Übernahme von {name} wurde verhindert.",
    )
    return _with_firm(sentence, details, names, ("target", "target_id", "partner", "partner_id"), "Ziel")


def _merger_formed(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Firma ist aus einer Fusion entstanden.", "{name} ist aus einer Fusion entstanden.")
    return _with_firm(sentence, details, names, ("partner", "partner_id", "other_firm", "other_firm_id"), "Partner")


def _merger_blocked(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(
        own,
        name,
        "Die geplante Fusion deiner Firma wurde verhindert.",
        "Die geplante Fusion von {name} wurde verhindert.",
    )
    return _with_firm(sentence, details, names, ("partner", "partner_id", "other_firm", "other_firm_id"), "Partner")


def _law_enacted(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    title = _value(details, "law", "name", "title", "gesetz")
    if title is None:
        return "Ein neues Gesetz ist in Kraft getreten."
    return f"Das Gesetz «{_text(title)}» ist in Kraft getreten."


def _recession(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return "Die Wirtschaft ist in eine Rezession geraten."


def _inflation(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    rate = _value(details, "rate", "inflation", "percent", "percentage", "rate_change")
    if rate is None:
        return "Die Inflation ist gestiegen."
    return f"Die Inflation ist auf {_text(rate)} gestiegen."


def _policy_rate_emergency(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    rate = _value(details, "rate", "policy_rate", "interest_rate", "new_rate")
    if rate is None:
        return "Die Zentralbank hat den Leitzins ausserplanmässig angepasst."
    return f"Die Zentralbank hat den Leitzins ausserplanmässig auf {_text(rate)} angepasst."


def _price_increase(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    price = _value(details, "price", "new_price", "sell_price", "preis")
    if own:
        sentence = "Du hast deinen Preis erhöht."
    else:
        sentence = f"{name} hat den Preis erhöht."
    if price is not None:
        sentence = f"{sentence[:-1]} auf {_text(price)}."
    return sentence


def _poisoning(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return _company_event(own, name, "Bei deiner Firma kam es zu einer Vergiftung.", "Bei {name} kam es zu einer Vergiftung.")


def _offence_detected(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return _company_event(own, name, "Bei deiner Firma wurde ein Vergehen festgestellt.", "Bei {name} wurde ein Vergehen festgestellt.")


def _listed(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return _company_event(own, name, "Deine Firma ist neu an der Börse.", "{name} ist neu an der Börse.")


def _delisted(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return _company_event(own, name, "Deine Firma wurde von der Börse genommen.", "{name} wurde von der Börse genommen.")


def _exchange_opened(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return "Eine Börse hat ihren Betrieb aufgenommen."


def _patent_granted(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Firma hat ein Patent erhalten.", "{name} hat ein Patent erhalten.")
    return _with_value(sentence, details, ("patent", "patent_name", "technology", "technology_name"), "für")


def _patent_expired(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Ein Patent deiner Firma ist ausgelaufen.", "Ein Patent von {name} ist ausgelaufen.")
    return _with_value(sentence, details, ("patent", "patent_name", "technology", "technology_name"), "für")


def _rnd_started(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast ein neues Forschungsprojekt gestartet.", "{name} hat ein neues Forschungsprojekt gestartet.")
    return _with_value(sentence, details, ("stage", "level", "stufe", "project"), "Bereich")


def _rnd_success(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Forschung war erfolgreich.", "{name} hatte einen Forschungserfolg.")
    return _with_value(sentence, details, ("stage", "level", "stufe", "technology"), "Bereich")


def _rnd_implemented(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast eine Forschung umgesetzt.", "{name} hat eine Forschung umgesetzt.")
    return _with_value(sentence, details, ("stage", "level", "stufe", "technology"), "Bereich")


def _rnd_inherited(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast eine Forschung übernommen.", "{name} hat eine Forschung übernommen.")
    return _with_value(sentence, details, ("stage", "level", "stufe", "technology"), "Bereich")


def _loan_granted(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Firma hat einen Kredit erhalten.", "{name} hat einen Kredit erhalten.")
    return _with_value(sentence, details, ("amount", "loan_amount", "betrag", "sum"), "Betrag")


def _credit_rejected(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return _company_event(own, name, "Dein Kreditantrag wurde abgelehnt.", "Der Kreditantrag von {name} wurde abgelehnt.")


def _capacity_limit(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Firma hat ihre Kapazitätsgrenze erreicht.", "{name} hat die Kapazitätsgrenze erreicht.")
    return _with_value(sentence, details, ("capacity", "limit", "amount", "kapazitaet"), "Grenze")


def _supplier_switch(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast den Lieferanten gewechselt.", "{name} hat den Lieferanten gewechselt.")
    return _with_firm(sentence, details, names, ("supplier", "supplier_id", "new_supplier", "new_supplier_id", "target"), "Neuer Lieferant")


def _transport_switch(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast den Transport gewechselt.", "{name} hat den Transport gewechselt.")
    return _with_firm(sentence, details, names, ("carrier", "carrier_id", "transport", "transport_id", "target"), "Neuer Anbieter")


def _trend_change(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    trend = _value(details, "trend", "new_trend", "category", "product")
    if trend is None:
        return "Der Markttrend hat sich geändert."
    return f"Der Markttrend für {_text(trend)} hat sich geändert."


def _holding_takeover(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Holding hat ein Unternehmen übernommen.", "Die Holding {name} hat ein Unternehmen übernommen.")
    return _with_firm(sentence, details, names, ("target", "target_id", "company", "company_id", "acquired"), "Ziel")


def _holding_sold(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return _company_event(own, name, "Deine Holding wurde verkauft.", "Die Holding {name} wurde verkauft.")


def _stake_bought(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast eine Beteiligung gekauft.", "{name} hat eine Beteiligung gekauft.")
    sentence = _with_firm(sentence, details, names, ("target", "target_id", "company", "company_id", "firm_id"), "Ziel")
    return _with_value(sentence, details, ("share", "percentage", "percent", "stake", "amount", "price"), "Anteil oder Betrag")


def _stake_sold(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast eine Beteiligung verkauft.", "{name} hat eine Beteiligung verkauft.")
    sentence = _with_firm(sentence, details, names, ("target", "target_id", "company", "company_id", "firm_id"), "Ziel")
    return _with_value(sentence, details, ("share", "percentage", "percent", "stake", "amount", "price"), "Anteil oder Betrag")


def _player_sale(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast deine Firma verkauft.", "{name} wurde verkauft.")
    return _with_value(sentence, details, ("price", "sale_price", "amount", "betrag"), "Verkaufspreis")


def _strategy_change(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast deine Strategie geändert.", "{name} hat die Strategie geändert.")
    return _with_value(sentence, details, ("strategy", "new_strategy", "positioning"), "Neue Strategie")


def _account_opened(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    return _company_event(own, name, "Deine Firma hat ein Bankkonto eröffnet.", "{name} hat ein Bankkonto eröffnet.")


def _bank_switched(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Du hast die Bank gewechselt.", "{name} hat die Bank gewechselt.")
    return _with_firm(sentence, details, names, ("bank", "bank_id", "new_bank", "new_bank_id"), "Neue Bank")


def _holding_cover(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Holding hat deine Firma finanziell unterstützt.", "Die Holding {name} hat eine Firma finanziell unterstützt.")
    return _with_firm(sentence, details, names, ("target", "target_id", "company", "company_id"), "Ziel")


def _holding_no_cover(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Holding konnte deine Firma nicht unterstützen.", "Die Holding {name} konnte eine Firma nicht unterstützen.")
    return _with_firm(sentence, details, names, ("target", "target_id", "company", "company_id"), "Ziel")


def _holding_sweep(own: bool, name: str, details: dict, names: dict[str, str]) -> str:
    sentence = _company_event(own, name, "Deine Holding hat Geld aus einer Tochterfirma erhalten.", "Die Holding {name} hat Geld aus einer Tochterfirma erhalten.")
    return _with_value(sentence, details, ("amount", "betrag", "sum", "cash"), "Betrag")


_MESSAGE_TEMPLATES = {
    "market_entry": lambda own, name, details, names: _market_entry(own, name, details, names),
    "bankruptcy": lambda own, name, details, names: _bankruptcy(own, name, details, names),
    "takeover": lambda own, name, details, names: _takeover(own, name, details, names),
    "takeover_blocked": lambda own, name, details, names: _takeover_blocked(own, name, details, names),
    "merger_formed": lambda own, name, details, names: _merger_formed(own, name, details, names),
    "merger_blocked": lambda own, name, details, names: _merger_blocked(own, name, details, names),
    "law_enacted": lambda own, name, details, names: _law_enacted(own, name, details, names),
    "recession": lambda own, name, details, names: _recession(own, name, details, names),
    "inflation": lambda own, name, details, names: _inflation(own, name, details, names),
    "policy_rate_emergency": lambda own, name, details, names: _policy_rate_emergency(own, name, details, names),
    "price_increase": lambda own, name, details, names: _price_increase(own, name, details, names),
    "poisoning": lambda own, name, details, names: _poisoning(own, name, details, names),
    "offence_detected": lambda own, name, details, names: _offence_detected(own, name, details, names),
    "listed": lambda own, name, details, names: _listed(own, name, details, names),
    "delisted": lambda own, name, details, names: _delisted(own, name, details, names),
    "exchange_opened": lambda own, name, details, names: _exchange_opened(own, name, details, names),
    "patent_granted": lambda own, name, details, names: _patent_granted(own, name, details, names),
    "patent_expired": lambda own, name, details, names: _patent_expired(own, name, details, names),
    "rnd_started": lambda own, name, details, names: _rnd_started(own, name, details, names),
    "rnd_success": lambda own, name, details, names: _rnd_success(own, name, details, names),
    "rnd_implemented": lambda own, name, details, names: _rnd_implemented(own, name, details, names),
    "rnd_inherited": lambda own, name, details, names: _rnd_inherited(own, name, details, names),
    "loan_granted": lambda own, name, details, names: _loan_granted(own, name, details, names),
    "credit_rejected": lambda own, name, details, names: _credit_rejected(own, name, details, names),
    "capacity_limit": lambda own, name, details, names: _capacity_limit(own, name, details, names),
    "supplier_switch": lambda own, name, details, names: _supplier_switch(own, name, details, names),
    "transport_switch": lambda own, name, details, names: _transport_switch(own, name, details, names),
    "trend_change": lambda own, name, details, names: _trend_change(own, name, details, names),
    "holding_takeover": lambda own, name, details, names: _holding_takeover(own, name, details, names),
    "holding_sold": lambda own, name, details, names: _holding_sold(own, name, details, names),
    "stake_bought": lambda own, name, details, names: _stake_bought(own, name, details, names),
    "stake_sold": lambda own, name, details, names: _stake_sold(own, name, details, names),
    "player_sale": lambda own, name, details, names: _player_sale(own, name, details, names),
    "strategy_change": lambda own, name, details, names: _strategy_change(own, name, details, names),
    "account_opened": lambda own, name, details, names: _account_opened(own, name, details, names),
    "bank_switched": lambda own, name, details, names: _bank_switched(own, name, details, names),
    "holding_cover": lambda own, name, details, names: _holding_cover(own, name, details, names),
    "holding_no_cover": lambda own, name, details, names: _holding_no_cover(own, name, details, names),
    "holding_sweep": lambda own, name, details, names: _holding_sweep(own, name, details, names),
}


def message_for(event: dict, player_id: str, names: dict[str, str]) -> dict | None:
    """Erstellt eine Spielermeldung oder lässt private Fremdmeldungen weg."""
    firm_id = event.get("firm")
    event_type = event.get("event")
    own = firm_id == player_id

    if not own and event_type in _PRIVATE_EVENTS:
        return None

    if firm_id is None or firm_id == "" or firm_id == "market":
        name = "Der Markt"
    else:
        name = _firm_value(firm_id, names)

    details = _details(event)
    template = _MESSAGE_TEMPLATES.get(event_type)
    if template is None:
        raw_details = event.get("details")
        text = f"{name}: {_text(raw_details)}"
    else:
        text = template(own, name, details, names)

    year = event.get("year", 0)
    day = event.get("day", 0)
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = 0
    try:
        day = int(day)
    except (TypeError, ValueError):
        day = 0

    important = event_type != "rnd_started" if own else event_type in _IMPORTANT_MARKET_EVENTS
    return {
        "year": year,
        "day": day,
        "text": _text(text),
        "kind": "eigen" if own else "markt",
        "important": important,
    }


def messages_for(events: list[dict], player_id: str, names: dict[str, str]) -> list[dict]:
    """Erstellt Meldungen für Ereignisse und lässt ausgelassene heraus."""
    result = []
    for event in events:
        message = message_for(event, player_id, names)
        if message is not None:
            result.append(message)
    return result
