// Spielmodus Phase 4: Holding, Töchter und CEOs.
'use strict';

const HOLDING_BRANCHEN = { hersteller: 'Hersteller', grosshaendler: 'Grosshändler', verteiler: 'Verteiler', detailhaendler: 'Detailhändler', gastro: 'Gastro' };
function holdingBranche(key) { return HOLDING_BRANCHEN[key] || key || ''; }

let holdingAuftraege = {};
let holdingState = null;

function holdingElement(tag, text, klasse) {
    const knoten = document.createElement(tag);
    if (text !== undefined && text !== null) knoten.textContent = String(text);
    if (klasse) knoten.className = klasse;
    return knoten;
}

function holdingGeld(wert) {
    return `${Number(wert || 0).toLocaleString('de-CH', { maximumFractionDigits: 0 })} CHF`;
}

function holdingInitialen(name) {
    return String(name || '?').trim().split(/\s+/).slice(0, 2)
        .map((teil) => teil.charAt(0)).join('').toUpperCase() || '?';
}

function holdingAvatar(person, klasse) {
    const avatar = holdingElement('div', null, `avatar ${klasse || ''}`.trim());
    if (person.image) {
        const bild = document.createElement('img');
        bild.className = 'avatar-bild';
        bild.src = `avatare/${person.image}`;
        bild.alt = person.name || 'Avatar';
        bild.onerror = () => {
            const initialen = holdingElement('div', holdingInitialen(person.name), 'avatar-initialen');
            bild.replaceWith(initialen);
        };
        avatar.appendChild(bild);
    } else {
        avatar.appendChild(holdingElement('div', holdingInitialen(person.name), 'avatar-initialen'));
    }
    return avatar;
}

function holdingKnopf(text, aktion, klasse) {
    const knopf = holdingElement('button', text, klasse);
    knopf.type = 'button';
    knopf.addEventListener('click', aktion);
    return knopf;
}

function holdingHat(knoten, eigenschaft) {
    return Object.prototype.hasOwnProperty.call(knoten, eigenschaft);
}

function holdingGuidelineBasis(tochter, feld) {
    if (!holdingHat(tochter, feld)) return null;
    const wert = tochter[feld];
    if (wert === null || wert === undefined) return null;
    if (feld === 'payout_ratio') {
        const zahl = Number(wert);
        return Number.isFinite(zahl) ? Math.min(1, Math.max(0, zahl)) : null;
    }
    return Boolean(wert);
}

function holdingGuidelineText(auftrag) {
    const teile = [];
    if (holdingHat(auftrag, 'payout_ratio')) {
        teile.push(auftrag.payout_ratio === null
            ? 'Gewinnabgabe automatisch'
            : `Gewinnabgabe ${Math.round(auftrag.payout_ratio * 100)} %`);
    }
    if (holdingHat(auftrag, 'auto_invest')) {
        teile.push(auftrag.auto_invest === null
            ? 'Ausbau automatisch'
            : `Automatisch ausbauen: ${auftrag.auto_invest ? 'an' : 'aus'}`);
    }
    return teile.join(', ');
}

function holdingSetzeGuideline(tochterId, feld, wert, basis, geplant) {
    if (wert === basis) {
        delete geplant[feld];
    } else {
        geplant[feld] = wert;
    }

    if (Object.keys(geplant).length) {
        if (!holdingAuftraege.guidelines) holdingAuftraege.guidelines = {};
        holdingAuftraege.guidelines[tochterId] = geplant;
    } else if (holdingAuftraege.guidelines) {
        delete holdingAuftraege.guidelines[tochterId];
        if (!Object.keys(holdingAuftraege.guidelines).length) delete holdingAuftraege.guidelines;
    }
}

function holdingZeigeGuidelines(knoten, auftrag) {
    knoten.hidden = !auftrag || !Object.keys(auftrag).length;
    knoten.textContent = knoten.hidden ? '' : `Geplant: ${holdingGuidelineText(auftrag)}`;
}

function holdingErgebnisse(parent, ergebnisse) {
    if (!ergebnisse || !ergebnisse.length) return;
    const abschnitt = holdingElement('div');
    ergebnisse.forEach((ergebnis) => {
        abschnitt.appendChild(holdingElement(
            'p',
            ergebnis.message || '',
            ergebnis.ok ? 'ergebnis-ok' : 'ergebnis-fehler'
        ));
    });
    parent.appendChild(abschnitt);
}

function holdingKaufbereich(parent, targets) {
    const abschnitt = holdingElement('section');
    abschnitt.appendChild(holdingElement('h3', 'Firmen kaufen'));

    if (holdingAuftraege.buy) {
        const ziel = (targets || []).find((firma) => String(firma.id) === String(holdingAuftraege.buy));
        const geplant = holdingElement('p', `Geplant: Kauf von ${ziel ? ziel.name : holdingAuftraege.buy}`, 'geplant');
        geplant.appendChild(document.createTextNode(' '));
        geplant.appendChild(holdingKnopf('Rückgängig', () => {
            delete holdingAuftraege.buy;
            fuelleHolding(holdingState || {});
        }));
        abschnitt.appendChild(geplant);
    }

    const tabelle = document.createElement('table');
    tabelle.className = 'holding-tabelle';
    const kopf = document.createElement('thead');
    const kopfzeile = document.createElement('tr');
    ['Name', 'Branche', 'Region', 'Umsatz', 'Gewinn', 'Preis', ''].forEach((text) => {
        kopfzeile.appendChild(holdingElement('th', text));
    });
    kopf.appendChild(kopfzeile);
    tabelle.appendChild(kopf);

    const koerper = document.createElement('tbody');
    (targets || []).forEach((firma) => {
        const zeile = document.createElement('tr');
        [firma.name, holdingBranche(firma.branch), firma.region, holdingGeld(firma.revenue),
            holdingGeld(firma.profit), holdingGeld(firma.price)].forEach((text) => {
            zeile.appendChild(holdingElement('td', text));
        });
        const aktion = document.createElement('td');
        const kaufen = holdingKnopf('Kaufen', () => {
            const preis = holdingGeld(firma.price);
            if (!window.confirm(`${firma.name} für ${preis} kaufen? Der Kauf wird mit der nächsten Runde ausgeführt.`)) return;
            holdingAuftraege.buy = firma.id;
            fuelleHolding(holdingState || {});
        });
        kaufen.disabled = Boolean(holdingAuftraege.buy);
        aktion.appendChild(kaufen);
        zeile.appendChild(aktion);
        koerper.appendChild(zeile);
    });
    tabelle.appendChild(koerper);
    abschnitt.appendChild(tabelle);
    parent.appendChild(abschnitt);
}

function holdingCeoBlock(parent, tochter, ceo) {
    const block = holdingElement('div', null, 'tochter-ceo');
    if (!ceo) {
        block.appendChild(holdingElement(
            'p',
            'Kein CEO – die Firma läuft vorsichtig auf Autopilot.',
            'warnung'
        ));
    } else {
        const zeile = holdingElement('div', null, 'ceo-zeile');
        zeile.appendChild(holdingAvatar(ceo));
        const details = holdingElement('div');
        details.appendChild(holdingElement('strong', ceo.name));
        details.appendChild(holdingElement('p', `${ceo.age} Jahre`));
        details.appendChild(holdingElement('p', ceo.style_label || ceo.style || ''));
        details.appendChild(holdingElement('p', `${holdingGeld(ceo.salary)} / Jahr`));
        zeile.appendChild(details);
        block.appendChild(zeile);
    }

    const auswahl = holdingElement('div', null, 'ceo-auswahl');
    auswahl.hidden = true;
    const freieCeos = (holdingState.ceos || []).filter((person) => person.available && !person.firm);
    if (!freieCeos.length) {
        auswahl.appendChild(holdingElement('p', 'Keine freien CEOs verfügbar.'));
    }
    freieCeos.forEach((person) => {
        const zeileCeo = holdingElement('div', null, 'ceo-auswahl-zeile');
        zeileCeo.appendChild(holdingAvatar(person));
        const detailsCeo = holdingElement('div');
        detailsCeo.appendChild(holdingElement('strong', person.name));
        detailsCeo.appendChild(holdingElement('span', ` ${person.age} Jahre`));
        detailsCeo.appendChild(holdingElement('p', person.style_label || person.style || ''));
        detailsCeo.appendChild(holdingElement('p', `${holdingGeld(person.salary)} / Jahr`));
        zeileCeo.appendChild(detailsCeo);
        const bereitsGeplant = Object.keys(holdingAuftraege.hire || {}).some((id) =>
            String(id) !== String(tochter.id) &&
            Number(holdingAuftraege.hire[id]) === Number(person.nr)
        );
        const einstellen = holdingKnopf('Einstellen', () => {
            if (!holdingAuftraege.hire) holdingAuftraege.hire = {};
            holdingAuftraege.hire[tochter.id] = person.nr;
            if (holdingAuftraege.fire) {
                holdingAuftraege.fire = holdingAuftraege.fire.filter((id) => String(id) !== String(tochter.id));
                if (!holdingAuftraege.fire.length) delete holdingAuftraege.fire;
            }
            fuelleHolding(holdingState || {});
        });
        einstellen.disabled = bereitsGeplant;
        zeileCeo.appendChild(einstellen);
        auswahl.appendChild(zeileCeo);
    });

    const aktionen = holdingElement('div', null, 'ceo-aktionen');
    aktionen.appendChild(holdingKnopf('CEO wählen', () => {
        auswahl.hidden = !auswahl.hidden;
    }));
    if (ceo) {
        aktionen.appendChild(holdingKnopf('Entlassen', () => {
            if (!window.confirm(`CEO von ${tochter.name} entlassen? Der Auftrag wird mit der nächsten Runde ausgeführt.`)) return;
            if (!holdingAuftraege.fire) holdingAuftraege.fire = [];
            if (!holdingAuftraege.fire.some((id) => String(id) === String(tochter.id))) {
                holdingAuftraege.fire.push(tochter.id);
            }
            if (holdingAuftraege.hire) {
                delete holdingAuftraege.hire[tochter.id];
                if (!Object.keys(holdingAuftraege.hire).length) delete holdingAuftraege.hire;
            }
            fuelleHolding(holdingState || {});
        }));
    }
    block.appendChild(aktionen);
    block.appendChild(auswahl);
    parent.appendChild(block);
}

function holdingTochterKarte(tochter, state) {
    const karte = holdingElement('article', null, 'tochter-karte');
    karte.appendChild(holdingElement('h3', tochter.name));

    const kennzahlen = holdingElement('p');
    kennzahlen.appendChild(document.createTextNode(`${holdingBranche(tochter.branch)} · Kasse: ${holdingGeld(tochter.cash)} · Umsatz: ${holdingGeld(tochter.revenue)} · Gewinn: ${holdingGeld(tochter.profit)}`));
    karte.appendChild(kennzahlen);

    const ceoNr = state.ceo_of ? state.ceo_of[tochter.id] : null;
    const ceo = (state.ceos || []).find((person) => Number(person.nr) === Number(ceoNr));
    holdingCeoBlock(karte, tochter, ceo);

    const ceoGeplant = holdingElement('p', '', 'geplant');
    const geplanteEinstellung = holdingAuftraege.hire && holdingAuftraege.hire[tochter.id];
    const entlassen = (holdingAuftraege.fire || []).some((id) => String(id) === String(tochter.id));
    if (geplanteEinstellung) {
        const person = (state.ceos || []).find((eintrag) => Number(eintrag.nr) === Number(geplanteEinstellung));
        ceoGeplant.textContent = `Geplant: ${person ? `CEO ${person.name} einstellen` : 'CEO einstellen'}`;
    } else if (entlassen) {
        ceoGeplant.textContent = 'Geplant: CEO entlassen';
    }
    ceoGeplant.hidden = !ceoGeplant.textContent;
    karte.appendChild(ceoGeplant);

    const guidelineBasisPayout = holdingGuidelineBasis(tochter, 'payout_ratio');
    const guidelineBasisInvest = holdingGuidelineBasis(tochter, 'auto_invest');
    const guidelineAlt = holdingAuftraege.guidelines && holdingAuftraege.guidelines[tochter.id];
    const guidelineAuftrag = guidelineAlt ? { ...guidelineAlt } : {};
    const richtlinien = holdingElement('div', null, 'tochter-richtlinien');
    const labelPayout = holdingElement('label', 'Gewinnabgabe an Holding (%)');
    const feldPayout = document.createElement('input');
    feldPayout.type = 'number';
    feldPayout.min = '0';
    feldPayout.max = '100';
    feldPayout.step = '1';
    feldPayout.value = guidelineAuftrag.payout_ratio !== undefined
        ? (guidelineAuftrag.payout_ratio === null ? '' : String(Math.round(guidelineAuftrag.payout_ratio * 100)))
        : (guidelineBasisPayout === null ? '' : String(Math.round(guidelineBasisPayout * 100)));
    labelPayout.appendChild(feldPayout);
    richtlinien.appendChild(labelPayout);

    const labelInvest = holdingElement('label', 'Automatisch ausbauen');
    const feldInvest = document.createElement('select');
    [
        ['', 'Autopilot'],
        ['ja', 'an'],
        ['nein', 'aus']
    ].forEach(([wert, text]) => {
        const option = holdingElement('option', text);
        option.value = wert;
        feldInvest.appendChild(option);
    });
    const geplanterInvest = guidelineAuftrag.auto_invest;
    const investWert = geplanterInvest !== undefined
        ? (geplanterInvest === null ? '' : (geplanterInvest ? 'ja' : 'nein'))
        : (guidelineBasisInvest === null ? '' : (guidelineBasisInvest ? 'ja' : 'nein'));
    feldInvest.value = investWert;
    labelInvest.appendChild(feldInvest);
    richtlinien.appendChild(labelInvest);

    const guidelineGeplant = holdingElement('p', '', 'geplant');
    holdingZeigeGuidelines(guidelineGeplant, guidelineAlt);
    const payoutAendern = () => {
        const text = feldPayout.value.trim();
        const wert = text === '' ? null : Math.min(100, Math.max(0, Number(text))) / 100;
        if (wert !== null && !Number.isFinite(wert)) return;
        holdingSetzeGuideline(tochter.id, 'payout_ratio', wert, guidelineBasisPayout, guidelineAuftrag);
        holdingZeigeGuidelines(guidelineGeplant, Object.keys(guidelineAuftrag).length ? guidelineAuftrag : null);
    };
    feldPayout.addEventListener('change', payoutAendern);
    feldPayout.addEventListener('input', payoutAendern);
    feldInvest.addEventListener('change', () => {
        const wert = feldInvest.value === '' ? null : feldInvest.value === 'ja';
        holdingSetzeGuideline(tochter.id, 'auto_invest', wert, guidelineBasisInvest, guidelineAuftrag);
        holdingZeigeGuidelines(guidelineGeplant, Object.keys(guidelineAuftrag).length ? guidelineAuftrag : null);
    });
    richtlinien.appendChild(guidelineGeplant);
    karte.appendChild(richtlinien);

    if (holdingAuftraege.sell && String(holdingAuftraege.sell) === String(tochter.id)) {
        const geplant = holdingElement('p', `Geplant: Verkauf von ${tochter.name}`, 'geplant');
        geplant.appendChild(document.createTextNode(' '));
        geplant.appendChild(holdingKnopf('Rückgängig', () => {
            delete holdingAuftraege.sell;
            fuelleHolding(holdingState || {});
        }));
        karte.appendChild(geplant);
    } else {
        karte.appendChild(holdingKnopf('Tochter verkaufen', () => {
            if (!window.confirm(`${tochter.name} verkaufen? Der Verkauf wird mit der nächsten Runde ausgeführt.`)) return;
            holdingAuftraege.sell = tochter.id;
            if (holdingAuftraege.hire) {
                delete holdingAuftraege.hire[tochter.id];
                if (!Object.keys(holdingAuftraege.hire).length) delete holdingAuftraege.hire;
            }
            if (holdingAuftraege.fire) {
                holdingAuftraege.fire = holdingAuftraege.fire.filter((id) => String(id) !== String(tochter.id));
                if (!holdingAuftraege.fire.length) delete holdingAuftraege.fire;
            }
            if (holdingAuftraege.guidelines) {
                delete holdingAuftraege.guidelines[tochter.id];
                if (!Object.keys(holdingAuftraege.guidelines).length) delete holdingAuftraege.guidelines;
            }
            fuelleHolding(holdingState || {});
        }));
    }
    return karte;
}

function fuelleHolding(state) {
    holdingState = state || {};
    const container = document.getElementById('holding-bereich');
    if (!container) return;
    while (container.firstChild) container.removeChild(container.firstChild);

    holdingErgebnisse(container, holdingState.order_results || []);
    holdingKaufbereich(container, holdingState.targets || []);

    if (!holdingState.holding) {
        container.appendChild(holdingElement(
            'p',
            'Noch keine Holding. Kaufe eine Firma, um eine Holding zu gründen.'
        ));
        return;
    }

    const abschnitt = holdingElement('section');
    abschnitt.appendChild(holdingElement('h2', 'Töchter'));
    (holdingState.holding.daughters || []).forEach((tochter) => {
        abschnitt.appendChild(holdingTochterKarte(tochter, holdingState));
    });
    container.appendChild(abschnitt);
}

function geplanteAuftraegeHolding() {
    const auftraege = {};
    if (holdingAuftraege.buy) auftraege.buy = holdingAuftraege.buy;
    if (holdingAuftraege.sell) auftraege.sell = holdingAuftraege.sell;
    if (holdingAuftraege.hire && Object.keys(holdingAuftraege.hire).length) {
        auftraege.hire = { ...holdingAuftraege.hire };
    }
    if (holdingAuftraege.fire && holdingAuftraege.fire.length) {
        auftraege.fire = [...holdingAuftraege.fire];
    }
    if (holdingAuftraege.guidelines && Object.keys(holdingAuftraege.guidelines).length) {
        auftraege.guidelines = {};
        Object.keys(holdingAuftraege.guidelines).forEach((id) => {
            const richtlinie = holdingAuftraege.guidelines[id];
            if (richtlinie && Object.keys(richtlinie).length) {
                auftraege.guidelines[id] = { ...richtlinie };
            }
        });
        if (!Object.keys(auftraege.guidelines).length) delete auftraege.guidelines;
    }
    return auftraege;
}

function leereAuftraegeHolding() {
    holdingAuftraege = {};
    fuelleHolding(holdingState || {});
}
