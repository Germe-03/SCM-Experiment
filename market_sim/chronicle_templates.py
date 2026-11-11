"""Pure-data German templates for market event chronicles and firm stories."""

from __future__ import annotations


EVENT_TEMPLATES: dict[str, list[dict[str, str | None]]] = {
    "takeover": [
        {"text": "{zeit} wurde {firma} übernommen.", "when": None},
        {"text": "{zeit} wechselte {firma} den Besitzer.", "when": None},
        {"text": "{zeit} endete die Eigenständigkeit von {firma} durch eine Übernahme.", "when": None},
        {"text": "{zeit} wurde {firma} als grösste Firma ihrer Stufe übernommen.", "when": "largest_in_stage"},
    ],
    "merger_formed": [
        {"text": "{zeit} entstand {firma} aus einer Fusion.", "when": None},
        {"text": "{zeit} nahm {firma} als neues Unternehmen den Betrieb auf.", "when": None},
        {"text": "{zeit} führte eine Fusion zur Gründung von {firma}.", "when": None},
        {"text": "{zeit} trat {firma} als erste Firma ihrer Stufe aus einer Fusion hervor.", "when": "first_in_stage"},
    ],
    "merger_blocked": [
        {"text": "{zeit} scheiterte die geplante Fusion von {firma}.", "when": None},
        {"text": "{zeit} verhinderte man die Fusion mit Beteiligung von {firma}.", "when": None},
        {"text": "{zeit} blieb die geplante Zusammenlegung von {firma} aus.", "when": None},
    ],
    "holding_formed": [
        {"text": "{zeit} wurde die Holding {firma} gegründet.", "when": None},
        {"text": "{zeit} entstand {firma} als Holdinggesellschaft.", "when": None},
        {"text": "{zeit} nahm die Holding {firma} ihre Tätigkeit auf.", "when": None},
    ],
    "holding_takeover": [
        {"text": "{zeit} übernahm die Holding {firma} ein Unternehmen.", "when": None},
        {"text": "{zeit} weitete {firma} ihre Beteiligungen durch eine Übernahme aus.", "when": None},
        {"text": "{zeit} vollzog die Holding {firma} eine Übernahme.", "when": None},
    ],
    "holding_dissolved": [
        {"text": "{zeit} wurde die Holding {firma} aufgelöst.", "when": None},
        {"text": "{zeit} endete die Tätigkeit der Holding {firma}.", "when": None},
        {"text": "{zeit} bestand {firma} nicht mehr als Holdinggesellschaft.", "when": None},
    ],
    "holding_sold": [
        {"text": "{zeit} wurde die Holding {firma} verkauft.", "when": None},
        {"text": "{zeit} wechselte die Holding {firma} den Besitzer.", "when": None},
        {"text": "{zeit} ging {firma} in den Besitz einer neuen Eigentümerschaft über.", "when": None},
    ],
    "poisoning": [
        {"text": "{zeit} wurde bei {firma} ein Vergiftungsfall verzeichnet.", "when": None},
        {"text": "{zeit} prägte ein Vergiftungsfall bei {firma} die Schlagzeilen.", "when": None},
        {"text": "{zeit} kam es bei {firma} zu einer Vergiftung.", "when": None},
        {"text": "{zeit} wurde der Vergiftungsfall bei {firma} öffentlich bekannt.", "when": None},
    ],
    "offence_detected": [
        {"text": "{zeit} wurde bei {firma} ein Vergehen festgestellt.", "when": None},
        {"text": "{zeit} entdeckte man ein Vergehen von {firma}.", "when": None},
        {"text": "{zeit} brachte ein festgestelltes Vergehen {firma} in die Schlagzeilen.", "when": None},
    ],
    "rnd_success": [
        {"text": "{zeit} meldete {firma} einen Forschungserfolg.", "when": None},
        {"text": "{zeit} gelang {firma} ein Erfolg in der Forschung.", "when": None},
        {"text": "{zeit} erzielte {firma} einen Forschungserfolg.", "when": None},
        {"text": "{zeit} erzielte {firma} einen Forschungserfolg in der Stufe {stufe}.", "when": None},
    ],
    "site_finished": [
        {"text": "{zeit} stellte {firma} einen neuen Standort fertig.", "when": None},
        {"text": "{zeit} schloss {firma} den Bau eines Standorts ab.", "when": None},
        {"text": "{zeit} wurde ein neuer Standort von {firma} fertiggestellt.", "when": None},
    ],
    "expand_finished": [
        {"text": "{zeit} schloss {firma} eine Erweiterung ab.", "when": None},
        {"text": "{zeit} wurde die Erweiterung von {firma} fertiggestellt.", "when": None},
        {"text": "{zeit} ergänzte eine abgeschlossene Erweiterung den Betrieb von {firma}.", "when": None},
    ],
    "restructuring": [
        {"text": "{zeit} nahm {firma} eine Umstrukturierung vor.", "when": None},
        {"text": "{zeit} ordnete {firma} ihre Organisation neu.", "when": None},
        {"text": "{zeit} prägte eine Umstrukturierung die Firma {firma}.", "when": None},
    ],
    "strategy_change": [
        {"text": "{zeit} änderte {firma} ihre Strategie.", "when": None},
        {"text": "{zeit} richtete {firma} ihre Strategie neu aus.", "when": None},
        {"text": "{zeit} vollzog {firma} einen Strategiewechsel.", "when": None},
    ],
    "bankruptcy": [
        {"text": "{zeit} musste {firma} Konkurs anmelden.", "when": None},
        {"text": "{zeit} endete die Geschäftstätigkeit von {firma} mit einem Konkurs.", "when": None},
        {"text": "{zeit} wurde der Konkurs von {firma} verzeichnet.", "when": None},
        {"text": "{zeit} musste {firma} nach drei Verlustjahren in Folge Konkurs anmelden.", "when": "loss_streak3"},
    ],
    "stake_bought": [
        {"text": "{zeit} erwarb {firma} eine Beteiligung.", "when": None},
        {"text": "{zeit} stieg {firma} mit dem Kauf einer Beteiligung bei einem Unternehmen ein.", "when": None},
        {"text": "{zeit} erweiterte der Erwerb einer Beteiligung das Portfolio von {firma}.", "when": None},
        {"text": "{zeit} kaufte {firma} eine Beteiligung an {ziel}.", "when": None},
    ],
    "breakup": [
        {"text": "{zeit} wurde {firma} aufgespalten.", "when": None},
        {"text": "{zeit} endete der gemeinsame Verbund von {firma} mit einer Aufspaltung.", "when": None},
        {"text": "{zeit} wurde die Aufspaltung von {firma} vollzogen.", "when": None},
    ],
    "spin_off": [
        {"text": "{zeit} wurde ein Teil von {firma} abgespalten.", "when": None},
        {"text": "{zeit} brachte {firma} einen Unternehmensteil als eigenständige Einheit hervor.", "when": None},
        {"text": "{zeit} veränderte eine Abspaltung die Struktur von {firma}.", "when": None},
    ],
    "rnd_implemented": [
        {"text": "{zeit} setzte {firma} eine Forschungsstufe um.", "when": None},
        {"text": "{zeit} überführte {firma} Forschung in die Umsetzung.", "when": None},
        {"text": "{zeit} setzte {firma} eine Entwicklung in der Stufe {stufe} um.", "when": None},
    ],
    "patent_granted": [
        {"text": "{zeit} erhielt {firma} ein Patent.", "when": None},
        {"text": "{zeit} wurde {firma} ein Patent erteilt.", "when": None},
        {"text": "{zeit} gewährte man {firma} ein Patent.", "when": None},
    ],
    "patent_expired": [
        {"text": "{zeit} lief ein Patent von {firma} aus.", "when": None},
        {"text": "{zeit} verlor ein Patent von {firma} seine Gültigkeit.", "when": None},
        {"text": "{zeit} endete der Patentschutz für {firma}.", "when": None},
    ],
    "recession": [
        {"text": "{zeit} verzeichnete die Wirtschaft eine Rezession.", "when": None},
        {"text": "{zeit} prägte eine Rezession die wirtschaftliche Entwicklung.", "when": None},
        {"text": "{zeit} stand die Wirtschaft im Zeichen einer Rezession.", "when": None},
    ],
    "raw_material_shortage": [
        {"text": "{zeit} herrschte ein Mangel an Rohstoffen.", "when": None},
        {"text": "{zeit} war die Rohstoffversorgung knapp.", "when": None},
        {"text": "{zeit} bestimmte ein Rohstoffmangel die Lage am Markt.", "when": None},
    ],
    "cost_shock": [
        {"text": "{zeit} kam es zu einem Kostenschock.", "when": None},
        {"text": "{zeit} prägte ein Kostenschock die wirtschaftliche Lage.", "when": None},
        {"text": "{zeit} brachte die Kostenentwicklung einen Kostenschock mit sich.", "when": None},
    ],
    "wage_push": [
        {"text": "{zeit} kam es zu einem allgemeinen Lohndruck.", "when": None},
        {"text": "{zeit} nahm der Lohndruck zu.", "when": None},
        {"text": "{zeit} stand die Lohnentwicklung im Zeichen eines Lohndrucks.", "when": None},
    ],
    "trend_change": [
        {"text": "{zeit} änderte sich der Markttrend.", "when": None},
        {"text": "{zeit} prägte ein neuer Trend den Markt.", "when": None},
        {"text": "{zeit} wechselte der bisherige Markttrend.", "when": None},
    ],
    "law_enacted": [
        {"text": "{zeit} trat ein neues Gesetz in Kraft.", "when": None},
        {"text": "{zeit} prägte ein neues Gesetz die rechtlichen Rahmenbedingungen.", "when": None},
        {"text": "{zeit} änderten sich die gesetzlichen Rahmenbedingungen.", "when": None},
    ],
    "heat_summer": [
        {"text": "{zeit} prägte ein heisser Sommer den Markt.", "when": None},
        {"text": "{zeit} fiel der Sommer besonders heiss aus.", "when": None},
        {"text": "{zeit} brachte ein heisser Sommer besondere Bedingungen mit sich.", "when": None},
    ],
    "harvest_failure": [
        {"text": "{zeit} fiel die Ernte schlecht aus.", "when": None},
        {"text": "{zeit} prägte ein Ernteausfall die Lage.", "when": None},
        {"text": "{zeit} blieb die Ernte hinter den Erwartungen zurück.", "when": None},
    ],
    "bank_failed": [
        {"text": "{zeit} ging die Bank {firma} in Konkurs.", "when": None},
        {"text": "{zeit} stellte die Bank {firma} ihren Betrieb ein.", "when": None},
        {"text": "{zeit} endete die Geschäftstätigkeit der Bank {firma}.", "when": None},
    ],
    "bank_entry": [
        {"text": "{zeit} trat die Bank {firma} in den Markt ein.", "when": None},
        {"text": "{zeit} nahm die Bank {firma} ihre Tätigkeit auf.", "when": None},
        {"text": "{zeit} kam mit {firma} eine neue Bank auf den Markt.", "when": None},
    ],
    "exchange_opened": [
        {"text": "{zeit} öffnete die Börse ihren Betrieb.", "when": None},
        {"text": "{zeit} nahm eine Börse ihre Tätigkeit auf.", "when": None},
        {"text": "{zeit} begann eine Börse ihren Betrieb.", "when": None},
    ],
    "delisted": [
        {"text": "{zeit} verschwand die Aktie von {firma} von der Börse.", "when": None},
        {"text": "{zeit} wurde die Aktie von {firma} nicht mehr an der Börse gehandelt.", "when": None},
    ],
    "delisted_holding": [
        {"text": "{zeit} verschwand die Aktie von {firma} von der Börse, nachdem {nachfolger} sie übernommen hatte.", "when": None},
        {"text": "{zeit} ging {firma} in der Holding {nachfolger} auf und wurde nicht mehr an der Börse gehandelt.", "when": None},
        {"text": "{zeit} wurde die Aktie von {firma} vom Handel genommen, weil eine Holding die Firma übernommen hatte.", "when": None},
    ],
    "delisted_merger": [
        {"text": "{zeit} verschwand die Aktie von {firma} von der Börse, weil die Firma mit {nachfolger} fusionierte.", "when": None},
        {"text": "{zeit} endete der Börsenhandel mit {firma} nach einer Fusion mit {nachfolger}.", "when": None},
        {"text": "{zeit} wurde die Aktie von {firma} nach einer Fusion nicht mehr gehandelt.", "when": None},
    ],
    "delisted_takeover": [
        {"text": "{zeit} verschwand die Aktie von {firma} von der Börse, nachdem {nachfolger} die Firma übernommen hatte.", "when": None},
        {"text": "{zeit} endete der Börsenhandel mit {firma} nach der Übernahme durch {nachfolger}.", "when": None},
        {"text": "{zeit} wurde die Aktie von {firma} nach einer Übernahme vom Handel genommen.", "when": None},
    ],
    "delisted_bankruptcy": [
        {"text": "{zeit} verschwand die Aktie von {firma} nach dem Konkurs von der Börse.", "when": None},
        {"text": "{zeit} wurde die Aktie von {firma} wegen des Konkurses wertlos und vom Handel genommen.", "when": None},
        {"text": "{zeit} endete der Börsenhandel mit {firma} mit dem Konkurs der Firma.", "when": None},
    ],
    "delisted_exit": [
        {"text": "{zeit} verschwand die Aktie von {firma} von der Börse, weil die Firma den Markt verliess.", "when": None},
        {"text": "{zeit} zog sich {firma} vom Markt und von der Börse zurück.", "when": None},
        {"text": "{zeit} wurde die Aktie von {firma} nach dem Marktaustritt der Firma nicht mehr gehandelt.", "when": None},
    ],
    "lease_started": [
        {"text": "{zeit} schloss {firma} einen Leasingvertrag für einen Lastwagen ab.", "when": None},
        {"text": "{zeit} mietete {firma} einen Lastwagen im Leasing.", "when": None},
        {"text": "{zeit} nahm {firma} einen geleasten Lastwagen in Betrieb.", "when": None},
    ],
    "lease_ended": [
        {"text": "{zeit} lief der Leasingvertrag von {firma} für einen Lastwagen aus.", "when": None},
        {"text": "{zeit} gab {firma} einen geleasten Lastwagen zurück.", "when": None},
        {"text": "{zeit} endete ein Lastwagen-Leasing von {firma}.", "when": None},
    ],
    "lease_default": [
        {"text": "{zeit} konnte {firma} die Leasingraten für einen Lastwagen nicht bezahlen.", "when": None},
        {"text": "{zeit} geriet {firma} mit dem Lastwagen-Leasing in Zahlungsverzug.", "when": None},
        {"text": "{zeit} fiel bei {firma} ein Leasingvertrag für einen Lastwagen aus.", "when": None},
    ],
    "lease_transferred": [
        {"text": "{zeit} übernahm {firma} auch die laufenden Lastwagen-Leasingverträge.", "when": None},
        {"text": "{zeit} führte {firma} ein übernommenes Lastwagen-Leasing weiter.", "when": None},
    ],
    "market_entry": [
        {"text": "{zeit} trat {firma} in den Markt ein.", "when": None},
        {"text": "{zeit} nahm {firma} den Betrieb in der Stufe {stufe} auf.", "when": None},
        {"text": "{zeit} wurde {firma} als neue Firma am Markt aktiv.", "when": None},
        {"text": "{zeit} war {firma} die erste Firma ihrer Stufe am Markt.", "when": "first_in_stage"},
        {"text": "{zeit} wurde {firma} als letzte verbleibende Firma ihrer Stufe aktiv.", "when": "last_in_stage"},
    ],
}


GENERIC_TEMPLATES: list[str] = [
    "{zeit} gab es eine Meldung: {ereignis}.",
    "{zeit} brachte ein Ereignis: {ereignis}.",
    "{zeit} ist folgende Meldung verzeichnet: {ereignis}.",
    "{zeit} wurde das Ereignis {ereignis} registriert.",
    "{zeit} betrifft eine Nachricht: {ereignis}.",
]


GROUP_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "takeover": {
        "two": [
            "{zeit} wurden {liste} übernommen.",
            "{zeit} wechselten {liste} den Besitzer.",
        ],
        "many": [
            "{zeit} wurden {anzahl} Firmen übernommen, darunter {liste}.",
            "{zeit} wechselten {anzahl} Firmen den Besitzer, darunter {liste}.",
        ],
    },
    "merger_formed": {
        "two": [
            "{zeit} fusionierten {liste} zu einer Firma.",
            "{zeit} schlossen sich {liste} zu einem Unternehmen zusammen.",
        ],
        "many": [
            "{zeit} fusionierten {anzahl} Firmen, darunter {liste}, zu einem Unternehmen.",
            "{zeit} schlossen sich {anzahl} Firmen, darunter {liste}, zusammen.",
        ],
    },
    "holding_formed": {
        "two": [
            "{zeit} gründeten {liste} je eine Holding.",
            "{zeit} entstanden die Holdings {liste}.",
        ],
        "many": [
            "{zeit} gründeten {anzahl} Firmen je eine Holding, darunter {liste}.",
            "{zeit} entstanden {anzahl} Holdings, darunter die von {liste}.",
        ],
    },
    "holding_takeover": {
        "two": [
            "{zeit} übernahmen die Holdings {liste} je ein Unternehmen.",
            "{zeit} vollzogen die Holdings {liste} je eine Übernahme.",
        ],
        "many": [
            "{zeit} übernahmen {anzahl} Holdings, darunter {liste}, je ein Unternehmen.",
            "{zeit} vollzogen {anzahl} Holdings, darunter {liste}, je eine Übernahme.",
        ],
    },
    "rnd_success": {
        "two": [
            "{zeit} meldeten {liste} einen Forschungserfolg.",
            "{zeit} gelang {liste} je ein Forschungserfolg.",
        ],
        "many": [
            "{zeit} meldeten {anzahl} Firmen, darunter {liste}, einen Forschungserfolg.",
            "{zeit} gelang {anzahl} Firmen, darunter {liste}, je ein Forschungserfolg.",
        ],
    },
    "rnd_implemented": {
        "two": [
            "{zeit} setzten {liste} eine Forschungsstufe um.",
            "{zeit} überführten {liste} ihre Forschung in die Umsetzung.",
        ],
        "many": [
            "{zeit} setzten {anzahl} Firmen, darunter {liste}, eine Forschungsstufe um.",
            "{zeit} überführten {anzahl} Firmen, darunter {liste}, ihre Forschung in die Umsetzung.",
        ],
    },
    "patent_granted": {
        "two": [
            "{zeit} erhielten {liste} je ein Patent.",
            "{zeit} wurden {liste} je ein Patent erteilt.",
        ],
        "many": [
            "{zeit} erhielten {anzahl} Firmen, darunter {liste}, je ein Patent.",
            "{zeit} wurden {anzahl} Firmen, darunter {liste}, je ein Patent erteilt.",
        ],
    },
    "patent_expired": {
        "two": [
            "{zeit} liefen Patente von {liste} aus.",
            "{zeit} verloren Patente von {liste} ihre Gültigkeit.",
        ],
        "many": [
            "{zeit} liefen Patente von {anzahl} Firmen, darunter {liste}, aus.",
            "{zeit} verloren Patente von {anzahl} Firmen, darunter {liste}, ihre Gültigkeit.",
        ],
    },
    "stake_bought": {
        "two": [
            "{zeit} erwarben {liste} Beteiligungen.",
            "{zeit} stiegen {liste} mit dem Kauf von Beteiligungen ein.",
        ],
        "many": [
            "{zeit} erwarben {anzahl} Firmen Beteiligungen, darunter {liste}.",
            "{zeit} stiegen {anzahl} Firmen mit dem Kauf von Beteiligungen ein, darunter {liste}.",
        ],
    },
    "bankruptcy": {
        "two": [
            "{zeit} mussten {liste} Konkurs anmelden.",
            "{zeit} stellten {liste} ihren Betrieb nach einem Konkurs ein.",
        ],
        "many": [
            "{zeit} mussten {anzahl} Firmen Konkurs anmelden, darunter {liste}.",
            "{zeit} stellten {anzahl} Firmen ihren Betrieb nach einem Konkurs ein, darunter {liste}.",
        ],
    },
    "strategy_change": {
        "two": [
            "{zeit} änderten {liste} ihre Strategie.",
            "{zeit} richteten {liste} ihre Strategie neu aus.",
        ],
        "many": [
            "{zeit} änderten {anzahl} Firmen ihre Strategie, darunter {liste}.",
            "{zeit} richteten {anzahl} Firmen ihre Strategie neu aus, darunter {liste}.",
        ],
    },
    "restructuring": {
        "two": [
            "{zeit} nahmen {liste} eine Umstrukturierung vor.",
            "{zeit} ordneten {liste} ihre Organisation neu.",
        ],
        "many": [
            "{zeit} nahmen {anzahl} Firmen eine Umstrukturierung vor, darunter {liste}.",
            "{zeit} ordneten {anzahl} Firmen ihre Organisation neu, darunter {liste}.",
        ],
    },
    "site_finished": {
        "two": [
            "{zeit} stellten {liste} je einen neuen Standort fertig.",
            "{zeit} schlossen {liste} je den Bau eines Standorts ab.",
        ],
        "many": [
            "{zeit} stellten {anzahl} Firmen je einen neuen Standort fertig, darunter {liste}.",
            "{zeit} schlossen {anzahl} Firmen je den Bau eines Standorts ab, darunter {liste}.",
        ],
    },
    "expand_finished": {
        "two": [
            "{zeit} schlossen {liste} je eine Erweiterung ab.",
            "{zeit} stellten {liste} je eine Erweiterung fertig.",
        ],
        "many": [
            "{zeit} schlossen {anzahl} Firmen je eine Erweiterung ab, darunter {liste}.",
            "{zeit} stellten {anzahl} Firmen je eine Erweiterung fertig, darunter {liste}.",
        ],
    },
    "offence_detected": {
        "two": [
            "{zeit} wurde bei {liste} je ein Vergehen festgestellt.",
            "{zeit} entdeckte man bei {liste} je ein Vergehen.",
        ],
        "many": [
            "{zeit} wurde bei {anzahl} Firmen, darunter {liste}, je ein Vergehen festgestellt.",
            "{zeit} entdeckte man bei {anzahl} Firmen, darunter {liste}, je ein Vergehen.",
        ],
    },
    "market_entry": {
        "two": [
            "{zeit} traten {liste} in den Markt ein.",
            "{zeit} nahmen {liste} den Betrieb am Markt auf.",
        ],
        "many": [
            "{zeit} traten {anzahl} Firmen in den Markt ein, darunter {liste}.",
            "{zeit} nahmen {anzahl} Firmen den Betrieb am Markt auf, darunter {liste}.",
        ],
    },
    "breakup": {
        "two": [
            "{zeit} wurden {liste} aufgespalten.",
            "{zeit} endeten die Verbünde von {liste} mit einer Aufspaltung.",
        ],
        "many": [
            "{zeit} wurden {anzahl} Firmen aufgespalten, darunter {liste}.",
            "{zeit} endeten die Verbünde von {anzahl} Firmen mit einer Aufspaltung, darunter {liste}.",
        ],
    },
    "spin_off": {
        "two": [
            "{zeit} wurde von {liste} je ein Unternehmensteil abgespalten.",
            "{zeit} spalteten {liste} je einen Unternehmensteil ab.",
        ],
        "many": [
            "{zeit} wurde von {anzahl} Firmen, darunter {liste}, je ein Unternehmensteil abgespalten.",
            "{zeit} spalteten {anzahl} Firmen, darunter {liste}, je einen Unternehmensteil ab.",
        ],
    },
    "bank_entry": {
        "two": [
            "{zeit} traten die Banken {liste} in den Markt ein.",
            "{zeit} nahmen die Banken {liste} ihre Tätigkeit auf.",
        ],
        "many": [
            "{zeit} traten {anzahl} Banken in den Markt ein, darunter die Banken {liste}.",
            "{zeit} nahmen {anzahl} Banken ihre Tätigkeit auf, darunter die Banken {liste}.",
        ],
    },
    "bank_failed": {
        "two": [
            "{zeit} gingen die Banken {liste} in Konkurs.",
            "{zeit} stellten die Banken {liste} ihren Betrieb ein.",
        ],
        "many": [
            "{zeit} gingen {anzahl} Banken in Konkurs, darunter die Banken {liste}.",
            "{zeit} stellten {anzahl} Banken ihren Betrieb ein, darunter die Banken {liste}.",
        ],
    },
}


EVENT_IMPORTANCE: dict[str, int] = {
    "takeover": 8,
    "merger_formed": 8,
    "merger_blocked": 5,
    "holding_formed": 6,
    "holding_takeover": 6,
    "holding_dissolved": 6,
    "holding_sold": 5,
    "poisoning": 8,
    "offence_detected": 6,
    "rnd_success": 5,
    "site_finished": 4,
    "expand_finished": 4,
    "restructuring": 5,
    "strategy_change": 3,
    "bankruptcy": 9,
    "stake_bought": 4,
    "breakup": 7,
    "spin_off": 6,
    "rnd_implemented": 5,
    "patent_granted": 5,
    "patent_expired": 3,
    "recession": 9,
    "raw_material_shortage": 7,
    "cost_shock": 7,
    "wage_push": 5,
    "trend_change": 5,
    "law_enacted": 6,
    "heat_summer": 4,
    "harvest_failure": 7,
    "bank_failed": 9,
    "bank_entry": 4,
    "exchange_opened": 6,
    "market_entry": 3,
    "delisted": 6,
    "lease_started": 2,
    "lease_ended": 2,
    "lease_default": 5,
    "lease_transferred": 2,
}

DEFAULT_IMPORTANCE = 3


INTRO: dict[str, list[str]] = {
    "good": [
        "Das Jahr {jahr} war ein gutes Jahr: Die Firmen verdienten zusammen {gewinn}; {firmen} Firmen waren aktiv.",
        "Die Firmen erzielten im Jahr {jahr} zusammen {gewinn}; aktiv waren {firmen} Firmen.",
        "Im Jahr {jahr} fiel die Bilanz der Firmen mit zusammen {gewinn} erfreulich aus; {firmen} Firmen waren aktiv.",
        "Bei {firmen} aktiven Firmen ergab sich im Jahr {jahr} ein gutes Gesamtergebnis von {gewinn}.",
    ],
    "bad": [
        "Das Jahr {jahr} schloss mit einem Gesamtergebnis von {gewinn} schwach ab; {firmen} Firmen waren aktiv.",
        "Für die {firmen} aktiven Firmen fiel das Jahr {jahr} mit einem Gesamtergebnis von {gewinn} schwierig aus.",
        "Das Jahr {jahr} war für die Firmen schwierig und endete mit einem Gesamtergebnis von {gewinn}; aktiv waren {firmen} Firmen.",
        "Bei {firmen} aktiven Firmen fiel die Bilanz im schwierigen Jahr {jahr} auf insgesamt {gewinn}.",
    ],
    "neutral": [
        "Im Jahr {jahr} belief sich das Gesamtergebnis der Firmen auf {gewinn}; {firmen} Firmen waren aktiv.",
        "{firmen} Firmen waren im Jahr {jahr} aktiv und erzielten zusammen ein Ergebnis von {gewinn}.",
        "Das Jahr {jahr} endete für {firmen} aktive Firmen mit einem Gesamtergebnis von {gewinn}.",
        "Für das Jahr {jahr} wurden bei {firmen} aktiven Firmen insgesamt {gewinn} verzeichnet.",
    ],
}


CONNECTORS: dict[str, list[str]] = {
    "first": ["Im Jahr {jahr}"],
    "same_year": ["Im selben Jahr", "Ebenfalls im Jahr {jahr}", "Ausserdem", "Gleichzeitig"],
    "later": ["Kurz darauf", "Später im Jahr", "Wenig später"],
    "contrast": ["Trotzdem", "Dennoch"],
    "story": ["Im Jahr {jahr}"],
}


FOLLOW_UPS: dict[str, list[str]] = {
    "takeover>spin_off": [
        "Im Jahr {frueher} wurde {firma} übernommen. Im Jahr {jahr} folgte die Abspaltung.",
        "Die Übernahme von {firma} erfolgte im Jahr {frueher}. Im Jahr {jahr} wurde ein Teil des Unternehmens abgespalten.",
    ],
    "takeover>breakup": [
        "{firma} wurde im Jahr {frueher} übernommen. Im Jahr {jahr} kam es zur Aufspaltung.",
        "Auf die Übernahme von {firma} im Jahr {frueher} folgte im Jahr {jahr} die Aufspaltung.",
    ],
    "patent_granted>patent_expired": [
        "{firma} erhielt das Patent im Jahr {frueher}. Im Jahr {jahr} lief es aus.",
        "Im Jahr {frueher} wurde {firma} ein Patent erteilt. Im Jahr {jahr} endete dessen Gültigkeit.",
    ],
    "merger_formed>breakup": [
        "{firma} entstand im Jahr {frueher} aus einer Fusion. Im Jahr {jahr} wurde der Verbund aufgespalten.",
        "Die Fusion führte im Jahr {frueher} zur Gründung von {firma}. Im Jahr {jahr} folgte die Aufspaltung.",
    ],
    "holding_formed>holding_dissolved": [
        "Die Holding {firma} wurde im Jahr {frueher} gegründet. Im Jahr {jahr} wurde sie aufgelöst.",
        "{firma} entstand im Jahr {frueher} als Holdinggesellschaft. Im Jahr {jahr} endete ihre Tätigkeit.",
    ],
    "rnd_success>rnd_implemented": [
        "{firma} verzeichnete im Jahr {frueher} einen Forschungserfolg. Im Jahr {jahr} setzte das Unternehmen die Entwicklung um.",
        "Im Jahr {frueher} gelang {firma} ein Forschungsschritt. Im Jahr {jahr} folgte dessen Umsetzung.",
    ],
    "bank_entry>bank_failed": [
        "Die Bank {firma} trat im Jahr {frueher} in den Markt ein. Im Jahr {jahr} ging sie in Konkurs.",
        "{firma} nahm als Bank im Jahr {frueher} ihre Tätigkeit auf. Im Jahr {jahr} endete ihr Geschäftsbetrieb.",
    ],
}


STORY_START: list[str] = [
    "{firma} trat im Jahr {jahr} in der Stufe {stufe} in den Markt ein.",
    "Im Jahr {jahr} wurde {firma} in der Stufe {stufe} am Markt aktiv.",
    "Der Markteintritt von {firma} in der Stufe {stufe} erfolgte im Jahr {jahr}.",
    "{firma} begann seine Tätigkeit in der Stufe {stufe} im Jahr {jahr}.",
]


STORY_END: dict[str, list[str]] = {
    "bankruptcy": [
        "{firma} musste im Jahr {jahr} Konkurs anmelden; insgesamt erzielte die Firma einen Gewinn von {gewinn}.",
        "Im Jahr {jahr} endete die Geschichte von {firma} mit einem Konkurs und einem Gesamtergebnis von {gewinn}.",
        "Der Konkurs beendete die Tätigkeit von {firma} im Jahr {jahr}; über die Laufzeit ergab sich ein Gewinn von {gewinn}.",
    ],
    "takeover": [
        "{firma} wurde im Jahr {jahr} übernommen; insgesamt erzielte die Firma einen Gewinn von {gewinn}.",
        "Mit der Übernahme von {firma} im Jahr {jahr} endete ihre Eigenständigkeit; das Gesamtergebnis betrug {gewinn}.",
        "Im Jahr {jahr} wechselte {firma} den Besitzer und verzeichnete insgesamt einen Gewinn von {gewinn}.",
    ],
    "poisoning": [
        "Die Tätigkeit von {firma} endete im Jahr {jahr} nach einem Vergiftungsfall; insgesamt erzielte die Firma {gewinn}.",
        "{firma} schied im Jahr {jahr} nach einem Vergiftungsfall aus dem Markt aus; das Gesamtergebnis betrug {gewinn}.",
        "Im Jahr {jahr} endete die Geschichte von {firma} nach einem Vergiftungsfall mit einem Gesamtgewinn von {gewinn}.",
    ],
    "merger": [
        "{firma} ging im Jahr {jahr} in einer Fusion auf; insgesamt erzielte die Firma einen Gewinn von {gewinn}.",
        "Im Jahr {jahr} endete die Eigenständigkeit von {firma} durch eine Fusion; das Gesamtergebnis betrug {gewinn}.",
        "Die Fusion beendete die eigenständige Tätigkeit von {firma} im Jahr {jahr}; insgesamt ergab sich ein Gewinn von {gewinn}.",
    ],
    "other_exit": [
        "{firma} verliess den Markt im Jahr {jahr}; insgesamt erzielte die Firma einen Gewinn von {gewinn}.",
        "Die Tätigkeit von {firma} endete im Jahr {jahr} mit einem Gesamtergebnis von {gewinn}.",
        "Im Jahr {jahr} schied {firma} aus dem Markt aus und verzeichnete insgesamt einen Gewinn von {gewinn}.",
    ],
    "active": [
        "{firma} war im Jahr {jahr} noch aktiv und erzielte insgesamt einen Gewinn von {gewinn}.",
        "Bis zum Jahr {jahr} blieb {firma} am Markt; das Gesamtergebnis belief sich auf {gewinn}.",
        "Am Ende des Jahres {jahr} war {firma} weiterhin aktiv und hatte insgesamt einen Gewinn von {gewinn} erzielt.",
    ],
}


STORY_PROFIT: dict[str, list[str]] = {
    "profit": [
        "{firma} erzielte insgesamt einen Gewinn von {gewinn}; das beste Jahr war Jahr {bestjahr}, das schwächste Jahr {schlechtjahr}.",
        "Die Gesamtbilanz von {firma} fiel mit einem Gewinn von {gewinn} positiv aus; am besten lief es im Jahr {bestjahr}, am schwächsten im Jahr {schlechtjahr}.",
        "{firma} kam insgesamt auf einen Gewinn von {gewinn}; das stärkste Jahr war Jahr {bestjahr}, das schwächste Jahr {schlechtjahr}.",
    ],
    "loss": [
        "{firma} verzeichnete insgesamt einen Verlust von {gewinn}; das beste Jahr war Jahr {bestjahr}, das schwächste Jahr {schlechtjahr}.",
        "Die Gesamtbilanz von {firma} fiel mit {gewinn} negativ aus; am besten lief es im Jahr {bestjahr}, am schwächsten im Jahr {schlechtjahr}.",
        "{firma} schloss insgesamt mit einem Verlust von {gewinn} ab; das stärkste Jahr war Jahr {bestjahr}, das schwächste Jahr {schlechtjahr}.",
    ],
}
