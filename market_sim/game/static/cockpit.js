'use strict';

let aktuellerStand = null;
let beschaeftigt = false;
let meldungsFilter = 'alle';
let statusTimer = null;
let buttonZustaende = new Map();
let geplantReiter = {};
let aktiverReiter = 'uebersicht';
let zeichnungsNr = 0;
let reiterInitialisiert = false;
let letzterRenderSchluessel = null;
let themeModus = 'system';

const svgNs = 'http://www.w3.org/2000/svg';
const REITER_KEYS = [
    'uebersicht',
    'firma',
    'markt',
    'forschung',
    'logistik',
    'einkauf',
    'vertraege',
    'lager',
    'finanzen',
    'bank',
    'abschluesse',
    'boerse',
    'rohstoffe',
    'bevoelkerung',
    'holding',
    'graubereich',
    'hilfe'
];

function element(id) {
    return document.getElementById(id);
}

function zeigeFehler(text) {
    const fehler = element('fehler');
    if (!fehler) return;
    fehler.textContent = text;
    fehler.hidden = false;
}

function verbergeFehler() {
    const fehler = element('fehler');
    if (fehler) fehler.hidden = true;
}

async function neuLadenNachFehler() {
    try {
        const res = await fetch('/api/game');
        const neu = await res.json();
        if (neu && neu.running !== undefined) render(neu);
    } catch (err) {
        // Der Fehlerhinweis bleibt stehen.
    }
}

async function api(pfad, body) {
    const optionen = body === undefined
        ? { method: 'GET' }
        : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        };

    try {
        const res = await fetch(pfad, optionen);
        let daten;

        try {
            daten = await res.json();
        } catch (err) {
            zeigeFehler('Die Antwort vom Server konnte nicht gelesen werden.');
            return null;
        }

        if (!res.ok || (daten && Object.prototype.hasOwnProperty.call(daten, 'error'))) {
            const fehlerText = daten && daten.error
                ? String(daten.error)
                : `Serverfehler (${res.status}).`;
            zeigeFehler(fehlerText);
            if (/Kein Spiel aktiv/i.test(fehlerText) && pfad !== '/api/game') {
                window.setTimeout(neuLadenNachFehler, 0);
            }
            return null;
        }

        verbergeFehler();
        return daten;
    } catch (err) {
        zeigeFehler(err && err.message ? err.message : 'Der Server ist nicht erreichbar.');
        return null;
    }
}

function setzeSichtbar(id, sichtbar) {
    const feld = element(id);
    if (feld) feld.hidden = !sichtbar;
}

function schalteGruendungsfelder() {
    // Region ist für alle Branchen wählbar, die Kategorie nur für Hersteller.
    const branche = element('branche-select');
    setzeSichtbar('region-wrap', true);
    setzeSichtbar('kategorie-wrap', Boolean(branche) && branche.value === 'hersteller');
    setzeSichtbar('dauer-wrap', true);
}

const KATEGORIE_NAMEN = {
    beer: 'Bier',
    wine: 'Wein',
    spirits: 'Spirituosen',
    softdrinks: 'Softdrinks',
    water: 'Wasser'
};

function kategorieName(name) {
    return KATEGORIE_NAMEN[name] || name;
}

function fuelleAuswahl(id, werte, mitLabel) {
    const auswahl = element(id);
    if (!auswahl) return;

    auswahl.replaceChildren();
    (werte || []).forEach((wert) => {
        const option = document.createElement('option');
        if (mitLabel) {
            option.value = wert.key;
            option.textContent = wert.label;
        } else {
            option.value = wert;
            option.textContent = id === 'kategorie-select' ? kategorieName(wert) : wert;
        }
        auswahl.appendChild(option);
    });
}

function regionName(id, optionen) {
    const namen = (optionen && optionen.region_labels) || (spielOptionen && spielOptionen.region_labels) || {};
    return namen[id] || id;
}

function fuelleGruendung(daten) {
    if (!daten) return;
    if (typeof merkeOptionen === 'function') merkeOptionen(daten);

    fuelleAuswahl('branche-select', daten.branches, true);
    fuelleAuswahl('region-select', daten.regions, false);
    const regionen = element('region-select');
    if (regionen) {
        Array.from(regionen.options).forEach((option) => {
            option.textContent = regionName(option.value, daten);
        });
    }
    fuelleAuswahl('kategorie-select', daten.categories, false);

    const dauer = element('dauer-select');
    if (dauer) {
        const wahl = Array.isArray(daten.years_choices) && daten.years_choices.length
            ? daten.years_choices.map(Number).filter(Number.isFinite)
            : [10];
        dauer.replaceChildren();
        wahl.forEach((jahre) => {
            const option = document.createElement('option');
            option.value = String(jahre);
            option.textContent = `${jahre} Jahre`;
            dauer.appendChild(option);
        });
        dauer.value = wahl.includes(10) ? '10' : String(wahl[0]);
    }
    schalteGruendungsfelder();
}

async function ladeOptionen() {
    const daten = await api('/api/options');
    fuelleGruendung(daten);
}

function formatiereDatum(wert) {
    if (!wert) return '';
    const datum = new Date(wert);
    if (Number.isNaN(datum.getTime())) return String(wert);
    return datum.toLocaleString('de-CH');
}

function fuelleSpielstaende(daten) {
    const liste = element('spielstaende-liste');
    if (!liste || !daten) return;

    liste.replaceChildren();
    const spielstaende = daten.saves || [];
    setzeSichtbar('keine-spielstaende', spielstaende.length === 0);

    spielstaende.forEach((spielstand) => {
        const li = document.createElement('li');
        const name = spielstand.name || '';
        const firma = spielstand.firm || '';
        const label = spielstand.label || '';
        const datum = formatiereDatum(spielstand.saved_at);
        const teile = [label, datum].filter(Boolean);
        const text = document.createTextNode(
            `${name} – ${firma} (${teile.join(', ')}) `
        );
        const laden = document.createElement('button');
        laden.type = 'button';
        laden.className = 'laden';
        laden.textContent = 'Laden';
        laden.addEventListener('click', () => ladeSpielstand(name));

        li.append(text, laden);
        liste.appendChild(li);
    });
}

async function ladeSpielstaende() {
    const liste = element('spielstaende-liste');
    if (!liste) return;

    const daten = await api('/api/saves');
    if (daten) fuelleSpielstaende(daten);
}

function setzeStatus(text, dauer) {
    const status = element('status');
    if (!status) return;

    window.clearTimeout(statusTimer);
    status.textContent = text;
    status.hidden = false;

    if (dauer) {
        statusTimer = window.setTimeout(() => {
            status.hidden = true;
        }, dauer);
    }
}

function setBusy(aktiv, text) {
    beschaeftigt = aktiv;
    const status = element('status');

    if (aktiv) {
        buttonZustaende.clear();
        document.querySelectorAll('button').forEach((knopf) => {
            if (knopf.closest('dialog')) return;
            buttonZustaende.set(knopf, knopf.disabled);
            knopf.disabled = true;
        });
        document.body.classList.add('beschaeftigt');
        if (status) {
            window.clearTimeout(statusTimer);
            status.textContent = text;
            status.hidden = false;
        }
        return;
    }

    document.body.classList.remove('beschaeftigt');
    buttonZustaende.forEach((warDeaktiviert, knopf) => {
        if (knopf.isConnected) knopf.disabled = warDeaktiviert;
    });
    buttonZustaende.clear();
    if (status) status.hidden = true;
}

function updateButtons() {
    const spielBeendet = Boolean(aktuellerStand && aktuellerStand.game_over);
    const spielKnopfIds = ['runde-btn', 'weiter-btn', 'jahr-btn', 'ende-btn', 'verkaufen-btn'];

    spielKnopfIds.forEach((id) => {
        const knopf = element(id);
        if (knopf) {
            knopf.disabled = beschaeftigt || spielBeendet;
            knopf.hidden = spielBeendet;
        }
    });
    const fuss = element('fussleiste');
    if (fuss) fuss.hidden = spielBeendet;

    const firma = element('tab-firma');
    if (firma) {
        firma.querySelectorAll('input, select, textarea, button').forEach((feld) => {
            if (spielBeendet) feld.disabled = true;
        });
    }

    if (beschaeftigt) {
        document.querySelectorAll('button').forEach((knopf) => {
            if (!knopf.closest('dialog')) knopf.disabled = true;
        });
    }
}

async function postAktion(pfad, body, statusText, nachErfolg) {
    if (beschaeftigt) return;

    setBusy(true, statusText);
    try {
        const daten = await api(pfad, body);
        if (daten) {
            if (daten.running !== undefined) render(daten);
            if (nachErfolg) await nachErfolg(daten);
        }
    } finally {
        setBusy(false);
        updateButtons();
    }
}

async function ladeSpielstand(name) {
    await postAktion('/api/load', { name }, 'Bitte warten …');
}

function setzeText(id, text) {
    const feld = element(id);
    if (feld) feld.textContent = text;
}

function formatierePreis(wert) {
    let zahl = Number(wert);
    if (!Number.isFinite(zahl) || Math.abs(zahl) < 0.005) zahl = 0;
    return `${new Intl.NumberFormat('de-CH', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(zahl)} CHF`;
}

function messeKopf() {
    const kopf = element('kopf');
    if (!kopf) return;
    document.documentElement.style.setProperty('--kopf-hoehe', `${Math.ceil(kopf.getBoundingClientRect().height)}px`);
}

function formatiereGeld(wert) {
    const zahl = Number(wert);
    let gueltig = Number.isFinite(zahl) ? zahl : 0;
    if (Math.abs(gueltig) < 0.005) gueltig = 0;
    const dezimalen = Math.abs(gueltig) < 100 && !Number.isInteger(gueltig) ? 2 : 0;
    return `${new Intl.NumberFormat('de-CH', {
        minimumFractionDigits: dezimalen,
        maximumFractionDigits: dezimalen
    }).format(gueltig)} CHF`;
}

function formatiereGanzzahl(wert) {
    const zahl = Number(wert);
    return new Intl.NumberFormat('de-CH', {
        maximumFractionDigits: 0
    }).format(Number.isFinite(zahl) ? zahl : 0);
}

function formatiereZahl(wert, stellen) {
    const zahl = Number(wert);
    if (!Number.isFinite(zahl)) return '0';
    return new Intl.NumberFormat('de-CH', {
        minimumFractionDigits: stellen,
        maximumFractionDigits: stellen
    }).format(zahl);
}

function formatiereProzent(wert) {
    const zahl = Number(wert);
    if (!Number.isFinite(zahl)) return '0.0 %';
    return `${new Intl.NumberFormat('de-CH', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1
    }).format(zahl * 100)} %`;
}

function zeigeSpielende(state) {
    const spielende = Boolean(state.game_over);
    setzeSichtbar('spielende', spielende);
    if (!spielende) return;

    const grund = state.reason === null || state.reason === undefined
        ? ''
        : String(state.reason);
    const klartext = state.end_reason_text ? String(state.end_reason_text) : '';
    const grundKlein = grund.toLowerCase();
    let titel = 'Spiel beendet';

    if (grundKlein === 'konkurs' || grundKlein === 'bankruptcy') {
        titel = 'Die Firma ist pleite';
    } else if (grundKlein === 'verkauft' || grundKlein === 'sold') {
        titel = 'Firma verkauft';
    }

    setzeText('spielende-titel', titel);
    const box = element('spielende');
    if (box) box.classList.toggle('konkurs', grundKlein === 'konkurs' || grundKlein === 'bankruptcy');

    let text = klartext || (grund ? `Grund: ${grund}` : 'Das Spiel ist beendet.');
    if (state.sale) {
        text += ` Verkaufspreis: ${formatiereGeld(state.sale.price)} (Jahr ${state.sale.year}, Monat ${state.sale.month})`;
    }
    setzeText('spielende-text', text);
}

function springeZuCeo() {
    waehleReiter('holding', false);
    window.setTimeout(() => {
        const bereich = element('holding-bereich');
        if (bereich) bereich.scrollIntoView({ behavior: 'smooth', block: 'start' });
        const knopf = document.querySelector('#holding-bereich .ceo-aktionen button');
        if (knopf) knopf.focus();
    }, 50);
}

function zeichneMeldungen(messages) {
    const liste = element('meldungen-liste');
    if (!liste) return;

    liste.replaceChildren();
    const sichtbar = (messages || []).filter((meldung) => {
        return meldungsFilter === 'alle' || meldung.kind === meldungsFilter;
    });

    if (sichtbar.length === 0) {
        const li = document.createElement('li');
        li.textContent = 'Keine Meldungen.';
        liste.appendChild(li);
        return;
    }

    sichtbar.forEach((meldung) => {
        const li = document.createElement('li');
        const art = meldung.kind === 'eigen' ? 'eigen' : 'markt';
        li.className = `meldung ${art}${meldung.important ? ' wichtig' : ''}`;

        const zeit = document.createElement('span');
        zeit.className = 'zeit';
        zeit.textContent = meldung.day === undefined || meldung.day === null ? `Jahr ${meldung.year}` : `Jahr ${meldung.year}, Tag ${meldung.day}`;

        li.append(zeit, document.createTextNode(` ${meldung.text || ''}`));
        if (meldung.action === 'ceo') {
            const knopf = document.createElement('button');
            knopf.type = 'button';
            knopf.className = 'meldung-knopf';
            knopf.textContent = 'CEO wählen';
            knopf.addEventListener('click', springeZuCeo);
            li.appendChild(knopf);
        }
        liste.appendChild(li);
    });
}

function aktualisiereFilter() {
    document.querySelectorAll('.filter-btn[data-filter]').forEach((knopf) => {
        const aktiv = knopf.dataset.filter === meldungsFilter;
        knopf.classList.toggle('aktiv', aktiv);
        knopf.setAttribute('aria-pressed', aktiv ? 'true' : 'false');
    });
}

function aktualisiereGeplantZaehler() {
    const zaehler = element('geplant-zaehler');
    if (!zaehler) return;

    const anzahl = Object.keys(geplantReiter).length;
    zaehler.hidden = anzahl === 0;
    zaehler.textContent = anzahl === 1
        ? 'Geplant: 1 Auftrag'
        : `Geplant: ${anzahl} Aufträge`;
}

function planeReiter(key, value) {
    if (value === null || value === undefined) {
        delete geplantReiter[key];
    } else {
        geplantReiter[key] = value;
    }
    aktualisiereGeplantZaehler();
}

function baueCtx(state) {
    const roh = state || aktuellerStand || {};
    // Noch nicht abgeschickte Entscheide (Entwurf bis «Runde beenden») über die Serverwerte legen,
    // damit Eingaben beim Wechsel zwischen Reitern nicht verloren gehen.
    const entwurf = (typeof entwurfEntscheide === 'object' && entwurfEntscheide) ? entwurfEntscheide : {};
    const aktueller = Object.keys(entwurf).length
        ? { ...roh, choices: { ...(roh.choices || {}), ...entwurf } }
        : roh;

    return {
        state: aktueller,
        ansicht: async (name, query) => {
            const parameter = new URLSearchParams();
            if (query && typeof query === 'object') {
                Object.keys(query).forEach((key) => {
                    const wert = query[key];
                    if (wert !== null && wert !== undefined) {
                        parameter.set(key, String(wert));
                    }
                });
            }
            const suffix = parameter.toString();
            const pfad = `/api/view/${encodeURIComponent(name)}${suffix ? `?${suffix}` : ''}`;

            try {
                const res = await fetch(pfad, { method: 'GET' });
                if (!res.ok) return null;
                const daten = await res.json();
                if (daten && Object.prototype.hasOwnProperty.call(daten, 'error')) return null;
                return daten;
            } catch (err) {
                return null;
            }
        },
        plane: (key, value) => planeReiter(key, value),
        geplant: () => ({ ...geplantReiter }),
        entscheide: (patch) => {
            if (typeof entscheidePatch === 'function') entscheidePatch(patch);
        },
        geld: formatiereGeld,
        preis: formatierePreis,
        zahl: (wert, stellen = 0) => formatiereZahl(wert, stellen),
        prozent: formatiereProzent,
        linien: (series, optionen) => diagramm(series, optionen),
        neuZeichnen: () => zeichneReiter(aktiverReiter)
    };
}

window.CockpitCtx = baueCtx;

function baueLinienGrafik(series, optionen) {
    const grafik = document.createElementNS(svgNs, 'svg');
    const hoehe = Math.max(120, Number(optionen && optionen.hoehe) || 200);
    const labels = (optionen && optionen.labels) || [];
    const serien = (series || []).map((reihe, index) => ({
        name: reihe.name || `Serie ${index + 1}`,
        werte: (reihe.werte || []).map(Number),
        farbe: reihe.farbe || `var(--linie-${(index % 4) + 1})`
    }));

    grafik.setAttribute('class', 'linien-grafik');
    grafik.setAttribute('viewBox', `0 0 600 ${hoehe}`);
    grafik.setAttribute('width', '100%');
    grafik.setAttribute('preserveAspectRatio', 'none');
    grafik.setAttribute('role', 'img');

    const alleWerte = serien.flatMap((reihe) => reihe.werte.filter(Number.isFinite));
    if (!alleWerte.length) return grafik;

    let min = Math.min(...alleWerte);
    let max = Math.max(...alleWerte);
    if (min === max) {
        min -= 1;
        max += 1;
    }

    const links = 52;
    const rechts = 590;
    const oben = 34;
    const unten = hoehe - 32;
    const yFuer = (wert) => unten - ((wert - min) / (max - min)) * (unten - oben);

    const beschriftungMin = document.createElementNS(svgNs, 'text');
    beschriftungMin.setAttribute('x', '4');
    beschriftungMin.setAttribute('y', String(unten));
    beschriftungMin.setAttribute('class', 'achsen-beschriftung');
    beschriftungMin.textContent = formatiereZahl(min, 1);
    grafik.appendChild(beschriftungMin);

    const beschriftungMax = document.createElementNS(svgNs, 'text');
    beschriftungMax.setAttribute('x', '4');
    beschriftungMax.setAttribute('y', String(oben + 4));
    beschriftungMax.setAttribute('class', 'achsen-beschriftung');
    beschriftungMax.textContent = formatiereZahl(max, 1);
    grafik.appendChild(beschriftungMax);

    if (min <= 0 && max >= 0) {
        const nulllinie = document.createElementNS(svgNs, 'line');
        nulllinie.setAttribute('x1', String(links));
        nulllinie.setAttribute('x2', String(rechts));
        nulllinie.setAttribute('y1', String(yFuer(0)));
        nulllinie.setAttribute('y2', String(yFuer(0)));
        nulllinie.setAttribute('class', 'nulllinie');
        nulllinie.setAttribute('stroke-dasharray', '4 4');
        grafik.appendChild(nulllinie);
    }

    const laengsteSerie = Math.max(0, ...serien.map((reihe) => reihe.werte.length));
    const abstand = laengsteSerie > 1 ? (rechts - links) / (laengsteSerie - 1) : 0;
    serien.forEach((reihe, index) => {
        const punkte = reihe.werte
            .map((wert, punktIndex) => Number.isFinite(wert)
                ? `${laengsteSerie > 1 ? links + punktIndex * abstand : (links + rechts) / 2},${yFuer(wert)}`
                : null)
            .filter(Boolean);
        if (punkte.length < 2) return;

        const linie = document.createElementNS(svgNs, 'polyline');
        linie.setAttribute('class', 'linie');
        linie.setAttribute('points', punkte.join(' '));
        linie.setAttribute('fill', 'none');
        linie.style.stroke = reihe.farbe;
        linie.setAttribute('role', 'img');
        linie.setAttribute('aria-label', reihe.name);
        grafik.appendChild(linie);
    });

    const sichtbareLabels = [];
    const schritt = Math.max(1, Math.ceil(labels.length / 6));
    for (let index = 0; index < labels.length; index += schritt) {
        sichtbareLabels.push(index);
    }
    if (labels.length && sichtbareLabels[sichtbareLabels.length - 1] !== labels.length - 1) {
        sichtbareLabels.push(labels.length - 1);
    }

    sichtbareLabels.forEach((index) => {
        const x = labels.length > 1
            ? links + (index * (rechts - links)) / (labels.length - 1)
            : (links + rechts) / 2;
        const text = document.createElementNS(svgNs, 'text');
        text.setAttribute('x', String(x));
        text.setAttribute('y', String(hoehe - 7));
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('class', 'achsen-beschriftung');
        text.textContent = String(labels[index]);
        grafik.appendChild(text);
    });

    serien.forEach((reihe, index) => {
        const x = links + index * 145;
        const quadrat = document.createElementNS(svgNs, 'rect');
        quadrat.setAttribute('x', String(x));
        quadrat.setAttribute('y', '8');
        quadrat.setAttribute('width', '9');
        quadrat.setAttribute('height', '9');
        quadrat.style.fill = reihe.farbe;
        grafik.appendChild(quadrat);

        const text = document.createElementNS(svgNs, 'text');
        text.setAttribute('x', String(x + 13));
        text.setAttribute('y', '16');
        text.setAttribute('class', 'legende');
        text.textContent = reihe.name;
        grafik.appendChild(text);
    });

    return grafik;
}

function baueKarte(titel) {
    const karte = document.createElement('section');
    karte.className = 'karte';
    const kopf = document.createElement('h2');
    kopf.textContent = titel;
    karte.appendChild(kopf);
    return karte;
}

function baueKpiRaster() {
    const raster = document.createElement('div');
    raster.className = 'kpi-raster';
    return raster;
}

function fuegeKpi(raster, label, wert, hinweis, info, klasse) {
    const kpi = document.createElement('article');
    kpi.className = 'kpi';

    const kopf = document.createElement('div');
    kopf.className = 'kpi-kopf';
    const beschriftung = document.createElement('span');
    beschriftung.className = 'kpi-label';
    beschriftung.textContent = label;
    kopf.appendChild(beschriftung);

    if (info && typeof infoKnopf === 'function') {
        const hilfe = infoKnopf(info.wofuer, info.wenn);
        if (hilfe) kopf.appendChild(hilfe);
    }

    const anzeige = document.createElement('strong');
    anzeige.className = 'kpi-wert';
    if (klasse) anzeige.classList.add(klasse);
    anzeige.textContent = wert;
    kpi.append(kopf, anzeige);

    if (hinweis) {
        const zusatz = document.createElement('small');
        zusatz.className = 'kpi-hinweis';
        if (hinweis.nodeType) zusatz.appendChild(hinweis);
        else zusatz.textContent = hinweis;
        kpi.appendChild(zusatz);
    }

    raster.appendChild(kpi);
}

function ersterWert(eintrag, namen) {
    for (const name of namen) {
        const wert = Number(eintrag && eintrag[name]);
        if (Number.isFinite(wert)) return wert;
    }
    return null;
}

function zeichneAmpel(karte, warnings) {
    const liste = document.createElement('ul');
    liste.className = 'ampel-liste';

    if (!warnings || warnings.length === 0) {
        const li = document.createElement('li');
        li.className = 'ampel gruen';
        const punkt = document.createElement('span');
        punkt.className = 'ampel-punkt';
        li.append(punkt, document.createTextNode('Alles im grünen Bereich'));
        liste.appendChild(li);
    } else {
        warnings.forEach((warning) => {
            const li = document.createElement('li');
            const stufe = warning.level === 'rot' ? 'rot' : 'gelb';
            li.className = `ampel ${stufe}`;
            const punkt = document.createElement('span');
            punkt.className = 'ampel-punkt';
            li.append(punkt, document.createTextNode(String(warning.text || '')));
            liste.appendChild(li);
        });
    }

    karte.appendChild(liste);
}

function zeichneWirkungsprotokoll(karte, effects) {
    const erklaerung = document.createElement('p');
    erklaerung.textContent = 'Hier siehst du, wie deine Entscheide die Firma verändert haben.';
    karte.appendChild(erklaerung);

    const liste = document.createElement('ol');
    liste.className = 'wirkung-liste';
    const eintraege = (effects || []).slice(-12).reverse();

    if (!eintraege.length) {
        const leer = document.createElement('p');
        leer.textContent = 'Noch kein Wirkungsprotokoll: es erscheint nach der ersten Runde.';
        karte.appendChild(leer);
        return;
    }

    const deltaNamen = {
        sales: 'Absatz',
        revenue: 'Umsatz',
        cash: 'Kasse',
        price: 'Preis',
        demand: 'Nachfrage'
    };

    eintraege.forEach((effekt) => {
        const li = document.createElement('li');
        const titel = document.createElement('strong');
        titel.textContent = String(effekt.label || 'Entscheid');
        li.appendChild(titel);

        const aenderungen = document.createElement('ul');
        aenderungen.className = 'wirkung-aenderungen';
        (effekt.changes || []).forEach((text) => {
            const aenderung = document.createElement('li');
            aenderung.textContent = String(text);
            aenderungen.appendChild(aenderung);
        });
        if (aenderungen.childNodes.length) li.appendChild(aenderungen);

        const chips = document.createElement('div');
        chips.className = 'delta-chips';
        Object.keys(deltaNamen).forEach((key) => {
            const wert = Number(effekt.deltas && effekt.deltas[key]);
            if (!Number.isFinite(wert)) return;

            const chip = document.createElement('span');
            const klasse = wert > 0 ? 'hoch' : (wert < 0 ? 'runter' : 'gleich');
            const vorzeichen = wert > 0 ? '+' : '';
            chip.className = `delta-chip ${klasse}`;
            chip.textContent = `${deltaNamen[key]} ${vorzeichen}${formatiereProzent(wert)}`;
            chips.appendChild(chip);
        });
        if (chips.childNodes.length) li.appendChild(chips);

        liste.appendChild(li);
    });

    karte.appendChild(liste);
}

function zeichnePunktGrafik(karte, history, kpis) {
    const punkte = (history || []).map((eintrag) => ({
        preis: Number(eintrag.sell_price),
        absatz: ersterWert(eintrag, ['sales', 'recent_sales'])
    })).filter((punkt) => Number.isFinite(punkt.preis) && punkt.absatz !== null);

    if (punkte.length < 2) {
        const preis = Number(kpis.sell_price);
        const absatz = Number(kpis.recent_sales);
        const text = document.createElement('p');
        text.textContent = `Sobald du mehrere Runden gespielt hast, siehst du hier, wie dein Preis den Absatz verändert. Aktuell: Preis ${formatierePreis(preis)}${Number.isFinite(absatz) ? `, Absatz ${formatiereGanzzahl(absatz)}` : ''}.`;
        karte.appendChild(text);
        return;
    }

    const labels = (history || []).filter((e) => Number.isFinite(Number(e.sell_price))).map((e) => `Jahr ${e.year}, ${e.month_name || `Monat ${e.month}`}`);
    karte.appendChild(streuDiagramm(punkte.map((p, i) => ({ x: p.preis, y: p.absatz, label: labels[i] })), {
        xName: 'Preis', yName: 'Absatz', xFormat: 'preis', yFormat: 'ganz', xTitel: 'Preis (CHF)', yTitel: 'Absatz pro Tag'
    }));
}

function zeichneEngpassKarte(el, daten) {
    if (!daten || typeof daten !== 'object' || !daten.text) return;

    const karte = baueKarte('Engpass');
    karte.id = 'karte-engpass';
    const text = document.createElement('p');
    text.className = 'engpass-text';
    text.style.fontSize = '1.25rem';
    text.style.fontWeight = '600';
    text.textContent = String(daten.text);
    karte.appendChild(text);

    const raster = baueKpiRaster();
    const flaschen = (wert) => (wert === null || wert === undefined || !Number.isFinite(Number(wert))
        ? '–'
        : formatiereGanzzahl(wert));
    fuegeKpi(raster, 'Kapazität pro Tag', flaschen(daten.capacity_per_day), 'Flaschen', null);
    fuegeKpi(raster, 'Nachfrage pro Tag', flaschen(daten.demand_per_day), 'Flaschen', null);
    fuegeKpi(raster, 'Absatz pro Tag', flaschen(daten.sales_per_day), 'Flaschen', null);
    if (daten.transport_per_day !== null && daten.transport_per_day !== undefined) {
        fuegeKpi(raster, 'Transport pro Tag', flaschen(daten.transport_per_day), 'Flaschen', null);
    }
    const nutzung = Number(daten.utilization_now);
    if (daten.utilization_now !== null && daten.utilization_now !== undefined && Number.isFinite(nutzung)) {
        const leerKosten = Number(daten.idle_cost_per_bottle);
        const kostenText = Number.isFinite(leerKosten) && leerKosten > 0
            ? `Leerkapazität kostet ${formatierePreis(leerKosten)} pro Flasche`
            : null;
        fuegeKpi(raster, 'Auslastung jetzt', formatiereProzent(nutzung), kostenText, null,
            nutzung < 0.7 ? 'negativ' : (nutzung > 0.95 ? '' : 'positiv'));
        if (nutzung < 0.7) {
            const warn = document.createElement('p');
            warn.className = 'engpass-warnung';
            warn.setAttribute('role', 'alert');
            warn.textContent = `Warnung: Nur ${formatiereProzent(nutzung)} der Kapazität sind ausgelastet. Die Fixkosten verteilen sich auf weniger Flaschen${kostenText ? ' (' + kostenText + ')' : ''}.`;
            karte.appendChild(warn);
        }
    }
    const tage = Number(daten.days_of_stock);
    fuegeKpi(raster, 'Lagerdauer', Number.isFinite(tage) ? `${formatiereZahl(tage, 1)} Tage` : '–', null, null);
    karte.appendChild(raster);
    el.appendChild(karte);
}

function zeichneKostenKarte(el, daten, ctx) {
    if (!daten || !Array.isArray(daten.items) || !daten.items.length) return;

    const karte = baueKarte('Wofür geht das Geld weg');
    karte.id = 'karte-kosten';
    const items = daten.items.filter((eintrag) => Number.isFinite(Number(eintrag.chf_year)));

    const kopf = document.createElement('p');
    kopf.textContent = `Kosten im Jahr ${daten.year ?? ''}: Umsatz ${formatiereGeld(daten.revenue_year)}, Gewinn ${formatiereGeld(daten.profit_year)}.`;
    karte.appendChild(kopf);

    try {
        karte.appendChild(ctx.linien([{
            name: 'Kosten in CHF',
            werte: items.map((eintrag) => Number(eintrag.chf_year)),
            farbe: 'var(--linie-1)',
            typ: 'bar',
            format: 'chf'
        }], {
            labels: items.map((eintrag) => eintrag.label || eintrag.key),
            typ: 'bar',
            format: 'chf',
            hoehe: Math.max(200, 38 * items.length),
            horizontal: true
        }));
    } catch (err) {
        // Die Tabelle unten zeigt dieselben Werte.
    }

    const tabelle = document.createElement('table');
    tabelle.className = 'rd-tabelle kosten-tabelle';
    const kopfZeile = document.createElement('tr');
    ['Posten', 'CHF im Jahr', 'Anteil am Umsatz'].forEach((titel) => {
        const th = document.createElement('th');
        th.textContent = titel;
        kopfZeile.appendChild(th);
    });
    const thead = document.createElement('thead');
    thead.appendChild(kopfZeile);
    const tbody = document.createElement('tbody');
    items.forEach((eintrag) => {
        const zeile = document.createElement('tr');
        [
            eintrag.label || eintrag.key || '',
            formatiereGeld(eintrag.chf_year),
            formatiereProzent(eintrag.share)
        ].forEach((text) => {
            const td = document.createElement('td');
            td.textContent = text;
            zeile.appendChild(td);
        });
        tbody.appendChild(zeile);
    });
    tabelle.append(thead, tbody);
    karte.appendChild(tabelle);
    el.appendChild(karte);
}

function zeichnePreisKarte(el, preise, ctx) {
    if (!preise || typeof preise !== 'object') return;

    const karte = baueKarte('Einkaufs- und Verkaufspreis');
    karte.id = 'karte-preise';
    const raster = baueKpiRaster();
    fuegeKpi(raster, 'Einkaufspreis pro Flasche', formatierePreis(preise.purchase_price), null, null);
    fuegeKpi(raster, 'Verkaufspreis pro Flasche', formatierePreis(preise.sell_price), null, null);
    fuegeKpi(raster, 'Gewinn pro Flasche', formatierePreis(preise.profit_per_bottle),
        Number.isFinite(Number(preise.margin_pct)) ? `Marge ${formatiereZahl(preise.margin_pct, 1)} %` : null, null,
        Number(preise.profit_per_bottle) < 0 ? 'negativ' : 'positiv');
    fuegeKpi(raster, 'Verlustgrenze', formatierePreis(preise.break_even_price), 'Darunter machst du Verlust.', null);
    karte.appendChild(raster);

    const verlauf = Array.isArray(preise.history) ? preise.history : [];
    if (verlauf.length >= 2) {
        karte.appendChild(ctx.linien([
            { name: 'Einkaufspreis', werte: verlauf.map((e) => Number(e.purchase)), farbe: 'var(--linie-1)' },
            { name: 'Verkaufspreis', werte: verlauf.map((e) => Number(e.sell)), farbe: 'var(--linie-2)' }
        ], { labels: verlauf.map((e) => e.label), hoehe: 220, format: 'preis' }));
    } else {
        karte.appendChild(Object.assign(document.createElement('p'), {
            textContent: 'Die Preiskurve erscheint nach der ersten Runde.'
        }));
    }
    el.appendChild(karte);
}

async function zeichneUebersicht(el) {
    const state = aktuellerStand || {};
    const kpis = state.kpis || {};
    const ctx = baueCtx(state);
    const [capacity, classification, engpass, kosten, preise] = await Promise.all([
        ctx.ansicht('capacity'),
        ctx.ansicht('classification'),
        ctx.ansicht('bottleneck'),
        ctx.ansicht('costs'),
        ctx.ansicht('pricing')
    ]);

    const raster = baueKpiRaster();
    const history = state.history || [];
    const letzterVerlauf = history.length ? history[history.length - 1] : {};
    const umsatzHistorie = history.slice().reverse().find((eintrag) => {
        return eintrag.revenue !== undefined && eintrag.revenue !== null
            && Number.isFinite(Number(eintrag.revenue));
    });
    const umsatz = umsatzHistorie
        ? Number(umsatzHistorie.revenue)
        : Number(kpis.sell_price || 0) * Number(kpis.recent_sales || 0);
    const kasse = Number(kpis.cash);
    const gewinn = Number(kpis.profit);

    const infos = {
        cash: {
            wofuer: 'Das verfügbare Geld deiner Firma.',
            wenn: 'Eine knappe Kasse erschwert Einkäufe, Investitionen und Lohnzahlungen.'
        },
        profit: {
            wofuer: 'Der Gewinn deiner Firma im letzten Zeitraum.',
            wenn: 'Ein höherer Gewinn stärkt die Firma; Verluste belasten ihre Kasse.'
        },
        revenue: {
            wofuer: 'Dein Umsatz im laufenden Jahr in CHF.',
            wenn: 'Der Umsatz ergibt sich aus verkauften Flaschen und ihrem Preis.'
        },
        profitYear: {
            wofuer: 'Dein Gewinn im laufenden Jahr in CHF (Umsatz minus alle Kosten).',
            wenn: 'Ist er negativ, verlierst du in diesem Jahr Geld.'
        },
        sales: {
            wofuer: 'Wie viele Flaschen deine Firma zuletzt verkauft hat.',
            wenn: 'Der Absatz hängt unter anderem von Preis, Nachfrage und Lieferfähigkeit ab.'
        },
        inventory: {
            wofuer: 'Wie viele Flaschen aktuell auf Lager liegen.',
            wenn: 'Mehr Lager kann Lieferungen sichern, bindet aber Geld.'
        },
        backlog: {
            wofuer: 'Noch nicht erfüllte Nachfrage.',
            wenn: 'Ein Rückstand kann entstehen, wenn die Nachfrage deine Lieferfähigkeit übersteigt.'
        },
        employees: {
            wofuer: 'Die Anzahl der Mitarbeitenden deiner Firma.',
            wenn: 'Mehr Mitarbeitende können die verfügbare Arbeitsleistung erhöhen und kosten Lohn.'
        },
        demand: {
            wofuer: 'Die geschätzte Nachfrage pro Tag.',
            wenn: 'Die Spanne zeigt mögliche Werte; der Durchschnitt hilft bei der Planung.'
        },
        capacity: {
            wofuer: 'Wie viele Flaschen deine Firma pro Tag liefern kann.',
            wenn: 'Eine hohe Auslastung lässt wenig Spielraum für zusätzliche Nachfrage.'
        },
        classification: {
            wofuer: 'Die Einstufung deiner Firma durch die Simulation.',
            wenn: 'Deine Entscheide beeinflussen, wie die Firma eingestuft wird.'
        }
    };

    fuegeKpi(raster, 'Kasse', formatiereGeld(kpis.cash), null, infos.cash,
        Number.isFinite(kasse) ? (kasse >= 0 ? 'positiv' : 'negativ') : '');
    fuegeKpi(raster, 'Gewinn seit Gründung', formatiereGeld(kpis.profit), null, infos.profit,
        Number.isFinite(gewinn) ? (gewinn >= 0 ? 'positiv' : 'negativ') : '');
    // Am Jahresanfang ist das laufende Jahr noch leer: dann das letzte volle Jahr zeigen.
    const jahrLeer = Number(kpis.revenue_year) === 0 || kpis.revenue_year === undefined || kpis.revenue_year === null;
    const letztesJahrDa = kpis.revenue_last_year !== undefined && kpis.revenue_last_year !== null
        && Number.isFinite(Number(kpis.revenue_last_year));
    const nimmLetztes = jahrLeer && letztesJahrDa;
    const umsatzJahr = nimmLetztes ? kpis.revenue_last_year : (kpis.revenue_year ?? umsatz);
    const gewinnJahrWert = nimmLetztes ? kpis.profit_last_year : kpis.profit_year;
    fuegeKpi(raster, nimmLetztes ? 'Umsatz im letzten Jahr' : 'Umsatz im Jahr', formatiereGeld(umsatzJahr),
        nimmLetztes ? 'Das neue Jahr hat gerade begonnen.' : null, infos.revenue);
    if (gewinnJahrWert !== undefined && gewinnJahrWert !== null) {
        const gewinnJahr = Number(gewinnJahrWert);
        fuegeKpi(raster, nimmLetztes ? 'Gewinn im letzten Jahr' : 'Gewinn im Jahr', formatiereGeld(gewinnJahrWert), null, infos.profitYear,
            Number.isFinite(gewinnJahr) ? (gewinnJahr >= 0 ? 'positiv' : 'negativ') : '');
    }
    fuegeKpi(raster, 'Absatz pro Tag (Flaschen)', formatiereGanzzahl(kpis.recent_sales), null, infos.sales);
    const lagerLink = document.createElement('a');
    lagerLink.href = '#lager';
    lagerLink.textContent = 'Details im Reiter Lager';
    fuegeKpi(raster, 'Lager (Flaschen)', formatiereGanzzahl(kpis.inventory), lagerLink, infos.inventory);
    fuegeKpi(raster, 'Rückstand (Flaschen)', formatiereGanzzahl(kpis.backlog), null, infos.backlog);
    fuegeKpi(raster, 'Mitarbeiter', formatiereGanzzahl(kpis.employees), null, infos.employees);

    const nachfrage = capacity && capacity.demand;
    const nachfrageMin = nachfrage && Number(nachfrage.min);
    const nachfrageMax = nachfrage && Number(nachfrage.max);
    const nachfrageWert = nachfrage && Number.isFinite(nachfrageMin) && Number.isFinite(nachfrageMax)
        ? `${formatiereGanzzahl(nachfrageMin)} bis ${formatiereGanzzahl(nachfrageMax)}`
        : formatiereGanzzahl(kpis.recent_demand);
    const nachfrageAvg = nachfrage && Number(nachfrage.avg);
    fuegeKpi(
        raster,
        'Nachfrage-Spanne (Flaschen pro Tag)',
        nachfrageWert,
        Number.isFinite(nachfrageAvg) ? `Durchschnitt: ${formatiereGanzzahl(nachfrageAvg)}` : null,
        infos.demand
    );

    const kapazitaet = Number(capacity && capacity.capacity_per_day);
    const ersteresJahr = Number(state.year) === 1;
    const auslastungJetzt = Number(engpass && engpass.utilization_now);
    const auslastung = ersteresJahr && engpass && engpass.utilization_now !== null && engpass.utilization_now !== undefined && Number.isFinite(auslastungJetzt)
        ? auslastungJetzt : Number(capacity && capacity.utilization_last_year);
    fuegeKpi(
        raster,
        'Kapazität (Flaschen pro Tag)',
        Number.isFinite(kapazitaet) ? formatiereGanzzahl(kapazitaet) : '–',
        Number.isFinite(auslastung) ? `${ersteresJahr && Number.isFinite(auslastungJetzt) ? 'Auslastung jetzt' : 'Auslastung letztes Jahr'}: ${formatiereProzent(auslastung)}` : null,
        infos.capacity
    );

    const einstufungsLabel = classification && classification.label
        ? classification.label
        : (typeof state.classification === 'string' ? state.classification : '');
    const erklaerung = classification && classification.explanation
        ? String(classification.explanation).split(/\r?\n/)[0].slice(0, 140)
        : '';
    fuegeKpi(raster, 'Einstufung', einstufungsLabel || '–', erklaerung || null, infos.classification);

    el.appendChild(raster);

    zeichnePreisKarte(el, preise, ctx);
    zeichneEngpassKarte(el, engpass);
    zeichneKostenKarte(el, kosten, ctx);

    const ampelKarte = baueKarte('Auf einen Blick');
    zeichneAmpel(ampelKarte, state.warnings || []);
    el.appendChild(ampelKarte);

    const verlaufKarte = baueKarte('Kassenverlauf und Gewinn');
    if (history.length < 2) {
        const hinweis = document.createElement('p');
        hinweis.textContent = 'Der Verlauf erscheint nach der ersten Runde';
        verlaufKarte.appendChild(hinweis);
    } else {
        const labels = history.map((eintrag) => `J${eintrag.year}/${eintrag.month}`);
        verlaufKarte.appendChild(ctx.linien([
            {
                name: 'Kasse',
                werte: history.map((eintrag) => Number(eintrag.cash)),
                farbe: 'var(--linie-1)'
            },
            {
                name: 'Gewinn',
                werte: history.map((eintrag) => Number(eintrag.profit)),
                farbe: 'var(--linie-2)'
            }
        ], { labels, hoehe: 220 }));
    }
    el.appendChild(verlaufKarte);

    const wirkungsKarte = baueKarte('Was haben deine Entscheide bewirkt?');
    zeichneWirkungsprotokoll(wirkungsKarte, state.effects || []);
    el.appendChild(wirkungsKarte);

    const preisKarte = baueKarte('Preis und Absatz');
    zeichnePunktGrafik(preisKarte, history, kpis);
    el.appendChild(preisKarte);
}

async function zeichneReiter(key) {
    const normalisiert = REITER_KEYS.includes(key) ? key : 'uebersicht';
    const el = element(`tab-${normalisiert}`);
    if (!el || normalisiert !== aktiverReiter) return;

    const nr = ++zeichnungsNr;
    const scrollY = window.scrollY;
    const staging = document.createElement('div');
    const state = aktuellerStand || {};
    const ctx = baueCtx(state);

    try {
        if (normalisiert === 'uebersicht') {
            await zeichneUebersicht(staging);
        } else if (normalisiert === 'firma') {
            const [autopilot, einstufung, preise] = await Promise.all([
                ctx.ansicht('autopilot'),
                ctx.ansicht('classification'),
                ctx.ansicht('pricing')
            ]);
            if (nr !== zeichnungsNr || normalisiert !== aktiverReiter) return;
            if (typeof zeichneFirma === 'function') {
                zeichneFirma(staging, state, autopilot, einstufung, preise);
            } else {
                staging.appendChild(bauePlatzhalterkarte(PLATZHALTER_TEXT));
            }
        } else if (normalisiert === 'holding') {
            if (typeof fuelleHolding === 'function') fuelleHolding(state);
            return;
        } else if (window.REITER && window.REITER[normalisiert]) {
            await window.REITER[normalisiert].render(staging, ctx);
        } else {
            staging.appendChild(bauePlatzhalterkarte(PLATZHALTER_TEXT));
        }

        if (nr !== zeichnungsNr || normalisiert !== aktiverReiter) return;
        el.replaceChildren(...staging.childNodes);
        window.scrollTo(window.scrollX, scrollY);
    } catch (err) {
        if (nr !== zeichnungsNr || normalisiert !== aktiverReiter) return;
        const karte = baueKarte('Hinweis');
        const hinweis = document.createElement('p');
        hinweis.textContent = `Dieser Bereich konnte nicht angezeigt werden: ${err && err.message ? err.message : 'Unbekannter Fehler'}`;
        karte.appendChild(hinweis);
        el.replaceChildren(karte);
        window.scrollTo(window.scrollX, scrollY);
    }
}

const PLATZHALTER_TEXT = 'Dieser Reiter konnte nicht geladen werden. Drücke Ctrl + F5.';

function bauePlatzhalterkarte(text) {
    const karte = baueKarte('Hinweis');
    const absatz = document.createElement('p');
    absatz.textContent = text;
    karte.appendChild(absatz);
    return karte;
}

function waehleReiter(key, nurHash) {
    const gewaehlt = REITER_KEYS.includes(key) ? key : 'uebersicht';
    aktiverReiter = gewaehlt;

    document.querySelectorAll('.reiter-btn[data-tab]').forEach((knopf) => {
        const aktiv = knopf.dataset.tab === gewaehlt;
        knopf.classList.toggle('aktiv', aktiv);
        knopf.setAttribute('aria-selected', aktiv ? 'true' : 'false');
        knopf.tabIndex = aktiv ? 0 : -1;
    });

    REITER_KEYS.forEach((reiter) => {
        const abschnitt = element(`tab-${reiter}`);
        if (abschnitt) abschnitt.hidden = reiter !== gewaehlt;
    });

    if (!nurHash && window.location.hash !== `#${gewaehlt}`) {
        window.history.replaceState(null, '', `#${gewaehlt}`);
    }
    reiterInitialisiert = true;
    zeichneReiter(gewaehlt);
}

function leseHashReiter() {
    const key = window.location.hash.replace(/^#/, '');
    return REITER_KEYS.includes(key) ? key : 'uebersicht';
}

let ladeTimer = null;

function zeigeAutosave(state) {
    const feld = element('autosave-anzeige');
    if (!feld) return;
    const zeit = state && state.autosaved_at ? new Date(state.autosaved_at) : null;
    if (!zeit || Number.isNaN(zeit.getTime())) {
        feld.hidden = true;
        return;
    }
    const hhmm = zeit.toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' });
    feld.textContent = `Automatisch gesichert: ${hhmm}`;
    feld.hidden = false;
}

function zeigeLadehinweis(state) {
    window.clearTimeout(ladeTimer);
    ladeTimer = null;
    if (state && state.loading) {
        setzeStatus('Dein letztes Spiel wird wiederhergestellt …');
        ladeTimer = window.setTimeout(neuLadenNachFehler, 2000);
    } else {
        const status = element('status');
        if (!beschaeftigt && status && status.textContent.startsWith('Dein letztes Spiel wird')) status.hidden = true;
    }
}

function render(state) {
    if (!state) return;

    const firma = state.firm || {};
    const schluessel = `${state.year ?? ''}|${state.month ?? ''}|${firma.id ?? ''}`;
    if (letzterRenderSchluessel !== null && schluessel !== letzterRenderSchluessel) {
        if (typeof leereEntwurf === 'function') leereEntwurf();
        geplantReiter = {};
        aktualisiereGeplantZaehler();
    }
    letzterRenderSchluessel = schluessel;
    aktuellerStand = state;
    zeigeAutosave(state);
    zeigeLadehinweis(state);

    if (!state.running) {
        setzeSichtbar('ansicht-gruendung', true);
        setzeSichtbar('ansicht-cockpit', false);
        setzeSichtbar('speichern-btn', false);
        setzeSichtbar('neues-spiel-btn', false);
        document.title = 'SCM-Spiel';
        ladeSpielstaende();
        updateButtons();
        return;
    }

    setzeSichtbar('ansicht-gruendung', false);
    setzeSichtbar('ansicht-cockpit', true);
    setzeSichtbar('speichern-btn', true);
    setzeSichtbar('neues-spiel-btn', true);

    const brancheNamen = {
        hersteller: 'Hersteller',
        grosshaendler: 'Grosshändler',
        verteiler: 'Verteiler',
        detailhaendler: 'Detailhändler',
        gastro: 'Gastro'
    };
    const branche = brancheNamen[firma.branch] || firma.branch || '';
    const einstufung = state.classification && typeof state.classification === 'object'
        ? state.classification.label
        : state.classification;

    setzeText('firmenname', firma.name || '');
    setzeText('branche-anzeige', branche);
    const einkaufKnopf = document.querySelector('.reiter-btn[data-tab="einkauf"]');
    if (einkaufKnopf) einkaufKnopf.textContent = firma.branch === 'hersteller' ? 'Produktion' : 'Einkauf';
    setzeText('einstufung-anzeige', einstufung || '');
    setzeSichtbar('einstufung-anzeige', Boolean(einstufung));
    setzeText('zeit-anzeige', `Jahr ${state.year}, ${state.month_name || `Monat ${state.month}`}`);
    const verbleibend = Number(state.years_left);
    const dauerAnzeige = element('dauer-anzeige');
    if (dauerAnzeige) {
        const zeigen = state.years_left !== null && state.years_left !== undefined
            && Number.isFinite(verbleibend) && !state.game_over;
        dauerAnzeige.hidden = !zeigen;
        if (zeigen) {
            dauerAnzeige.textContent = verbleibend <= 0
                ? 'letztes Jahr'
                : (verbleibend === 1 ? 'noch 1 Jahr' : `noch ${verbleibend} Jahre`);
            dauerAnzeige.classList.toggle('knapp', verbleibend <= 1);
        }
    }
    window.setTimeout(messeKopf, 0);

    if (typeof fuelleHolding === 'function') fuelleHolding(state);
    zeigeSpielende(state);
    if (typeof zeigeDashboardStatus === 'function') zeigeDashboardStatus(state);
    if (typeof zeigeRueckblick === 'function') zeigeRueckblick(state);
    zeichneMeldungen(state.messages || []);
    aktualisiereFilter();
    aktualisiereGeplantZaehler();

    if (!reiterInitialisiert) {
        waehleReiter(leseHashReiter(), false);
    } else {
        waehleReiter(aktiverReiter, true);
    }

    updateButtons();
}

function kopiereUeberstunden(quelle) {
    const andereId = quelle.id === 'f-overtime_level'
        ? 'f-overtime_level-2'
        : 'f-overtime_level';
    const andere = element(andereId);
    if (andere) andere.value = quelle.value;
}

function oeffneVerkaufDialog() {
    if (beschaeftigt) return;

    const dialog = element('bestaetigen-dialog');
    if (!dialog || typeof dialog.showModal !== 'function') {
        if (window.confirm('Wirklich verkaufen? Das Spiel endet dann.')) {
            postAktion('/api/sell', {}, 'Bitte warten …');
        }
        return;
    }

    setzeText('bestaetigen-text', 'Wirklich verkaufen? Das Spiel endet dann.');
    dialog.showModal();
}

function oeffneSpeichernDialog() {
    if (beschaeftigt) return;

    const dialog = element('speichern-dialog');
    const nameFeld = element('speichern-name');
    if (nameFeld) nameFeld.value = (aktuellerStand && aktuellerStand.firm && aktuellerStand.firm.name) || '';

    if (!dialog || typeof dialog.showModal !== 'function') {
        const name = window.prompt(
            'Name für den Spielstand:',
            nameFeld ? nameFeld.value : ''
        );
        if (name !== null) speichereSpielstand(name);
        return;
    }

    dialog.showModal();
}

async function speichereSpielstand(name) {
    const saubererName = String(name || '').trim();
    if (!saubererName || beschaeftigt) return;

    await postAktion(
        '/api/save',
        { name: saubererName },
        'Bitte warten …',
        async (daten) => {
            if (daten.ok) {
                setzeStatus(`Gespeichert als ${saubererName}`, 3000);
                await ladeSpielstaende();
            }
        }
    );
}

function fragePruefung(warnungen) {
    return new Promise((fertig) => {
        const dialog = element('check-dialog');
        const liste = element('check-liste');
        if (!dialog || !liste || typeof dialog.showModal !== 'function') {
            fertig(window.confirm(warnungen.map((w) => w.text).join(' ') + ' Trotzdem beenden?'));
            return;
        }
        liste.replaceChildren();
        warnungen.forEach((w) => {
            const li = document.createElement('li');
            li.className = w.level === 'rot' ? 'rot' : 'gelb';
            li.textContent = String(w.text || '');
            liste.appendChild(li);
        });
        const ja = element('check-ja');
        const nein = element('check-nein');
        const aufraeumen = (antwort) => {
            ja.removeEventListener('click', onJa);
            nein.removeEventListener('click', onNein);
            dialog.removeEventListener('cancel', onNein);
            if (dialog.open) dialog.close();
            fertig(antwort);
        };
        const onJa = (e) => { e.preventDefault(); aufraeumen(true); };
        const onNein = (e) => { e.preventDefault(); aufraeumen(false); };
        ja.addEventListener('click', onJa);
        nein.addEventListener('click', onNein);
        dialog.addEventListener('cancel', onNein);
        dialog.showModal();
    });
}

async function rundeBeenden(weiterWieBisher, ueberspringen, bisEnde) {
    const settings = weiterWieBisher || typeof geaenderteEinstellungen !== 'function'
        ? {}
        : geaenderteEinstellungen();
    const choices = weiterWieBisher || typeof geaenderteEntscheide !== 'function'
        ? {}
        : geaenderteEntscheide();
    const holding = typeof geplanteAuftraegeHolding === 'function'
        ? geplanteAuftraegeHolding()
        : {};
    const orders = { ...(holding || {}), ...geplantReiter };

    if (beschaeftigt) return;
    setBusy(true, 'Prüfe …');
    let pruefung = null;
    try {
        pruefung = await api('/api/check', { settings, choices, orders });
    } finally {
        setBusy(false);
        updateButtons();
    }
    const warnungen = pruefung && Array.isArray(pruefung.warnings) ? pruefung.warnings : [];
    if (warnungen.length && !(await fragePruefung(warnungen))) return;

    if (bisEnde) {
        await postAktion('/api/run_to_end', { settings, choices, orders }, 'Simuliere bis zum Ende …', async () => {
            if (typeof leereAuftraegeHolding === 'function') leereAuftraegeHolding();
            if (typeof leereEntwurf === 'function') leereEntwurf();
            geplantReiter = {};
            aktualisiereGeplantZaehler();
        });
        return;
    }

    await postAktion(
        ueberspringen ? '/api/skip_year' : '/api/round',
        { settings, choices, orders },
        ueberspringen ? 'Rechne bis zum nächsten Halt im nächsten Jahr …' : 'Rechne …',
        async () => {
            if (typeof leereAuftraegeHolding === 'function') leereAuftraegeHolding();
            if (typeof leereEntwurf === 'function') leereEntwurf();
            geplantReiter = {};
            aktualisiereGeplantZaehler();
            const liste = element('meldungen-liste');
            if (liste) liste.scrollTop = 0;
        }
    );
}

function setzeTheme(modus) {
    themeModus = modus;
    const knopf = element('theme-btn');

    if (modus === 'system') {
        delete document.documentElement.dataset.theme;
        try {
            localStorage.removeItem('cockpit-theme');
        } catch (err) {
            // Lokaler Speicher kann im Browser gesperrt sein.
        }
    } else {
        document.documentElement.dataset.theme = modus === 'hell' ? 'light' : 'dark';
        try {
            localStorage.setItem('cockpit-theme', modus);
        } catch (err) {
            // Lokaler Speicher kann im Browser gesperrt sein.
        }
    }

    if (knopf) {
        const titel = modus === 'system'
            ? 'Darstellung: System'
            : `Darstellung: ${modus}`;
        knopf.title = titel;
        knopf.setAttribute('aria-label', titel);
    }
}

function ladeTheme() {
    let gespeichert = null;
    try {
        gespeichert = localStorage.getItem('cockpit-theme');
    } catch (err) {
        gespeichert = null;
    }

    if (gespeichert === 'hell' || gespeichert === 'dunkel') {
        setzeTheme(gespeichert);
    } else {
        themeModus = 'system';
        delete document.documentElement.dataset.theme;
        const knopf = element('theme-btn');
        if (knopf) {
            knopf.title = 'Darstellung: System';
            knopf.setAttribute('aria-label', 'Darstellung: System');
        }
    }
}

function wechsleTheme() {
    const naechster = themeModus === 'system'
        ? 'hell'
        : (themeModus === 'hell' ? 'dunkel' : 'system');
    setzeTheme(naechster);
}

function verbindeEreignisse() {
    const branche = element('branche-select');
    if (branche) branche.addEventListener('change', schalteGruendungsfelder);

    const gruendung = element('gruendung-form');
    if (gruendung) {
        gruendung.addEventListener('submit', async (ereignis) => {
            ereignis.preventDefault();
            if (beschaeftigt) return;

            const nameFeld = element('name-input') || gruendung.querySelector('[name="name"]');
            const name = nameFeld ? nameFeld.value.trim() : '';
            if (!name) {
                if (nameFeld) nameFeld.focus();
                return;
            }

            const regionSichtbar = element('region-wrap') && !element('region-wrap').hidden;
            const kategorieSichtbar = element('kategorie-wrap') && !element('kategorie-wrap').hidden;
            await postAktion('/api/new', {
                branch: branche ? branche.value : '',
                name,
                region: regionSichtbar && element('region-select')
                    ? element('region-select').value
                    : null,
                years: element('dauer-select') ? Number(element('dauer-select').value) || 10 : 10,
                category: kategorieSichtbar && element('kategorie-select')
                    ? element('kategorie-select').value
                    : null
            }, 'Bitte warten …');
        });
    }

    const reiterleiste = element('reiterleiste');
    if (reiterleiste) {
        reiterleiste.addEventListener('click', (ereignis) => {
            const knopf = ereignis.target.closest('.reiter-btn[data-tab]');
            if (!knopf || !reiterleiste.contains(knopf)) return;
            waehleReiter(knopf.dataset.tab, false);
        });
    }

    window.addEventListener('hashchange', () => {
        waehleReiter(leseHashReiter(), true);
    });

    const theme = element('theme-btn');
    if (theme) theme.addEventListener('click', wechsleTheme);

    const runde = element('runde-btn');
    if (runde) runde.addEventListener('click', () => rundeBeenden(false));

    const jahr = element('jahr-btn');
    if (jahr) jahr.addEventListener('click', () => rundeBeenden(false, true));

    const ende = element('ende-btn');
    if (ende) {
        ende.addEventListener('click', () => {
            if (beschaeftigt) return;
            if (!window.confirm('Deine Firma läuft danach mit Autopilot bis Jahr 50 weiter, dann öffnet sich das Dashboard. Dein Spiel ist danach beendet. Wirklich bis zum Ende simulieren?')) return;
            rundeBeenden(false, false, true);
        });
    }

    const neuesSpiel = element('neues-spiel-btn');
    if (neuesSpiel && typeof neuesSpielStarten === 'function') neuesSpiel.addEventListener('click', neuesSpielStarten);

    const weiter = element('weiter-btn');
    if (weiter) weiter.addEventListener('click', () => rundeBeenden(true));

    document.querySelectorAll('.filter-btn[data-filter]').forEach((knopf) => {
        knopf.addEventListener('click', () => {
            meldungsFilter = knopf.dataset.filter || 'alle';
            aktualisiereFilter();
            zeichneMeldungen((aktuellerStand && aktuellerStand.messages) || []);
        });
    });

    const verkaufen = element('verkaufen-btn');
    if (verkaufen) verkaufen.addEventListener('click', oeffneVerkaufDialog);

    const bestaetigenJa = element('bestaetigen-ja');
    if (bestaetigenJa) {
        bestaetigenJa.addEventListener('click', (ereignis) => {
            ereignis.preventDefault();
            const dialog = element('bestaetigen-dialog');
            if (dialog && typeof dialog.close === 'function') dialog.close();
            postAktion('/api/sell', {}, 'Bitte warten …');
        });
    }

    const bestaetigenNein = element('bestaetigen-nein');
    if (bestaetigenNein) {
        bestaetigenNein.addEventListener('click', (ereignis) => {
            ereignis.preventDefault();
            const dialog = element('bestaetigen-dialog');
            if (dialog && typeof dialog.close === 'function') dialog.close();
        });
    }

    const speichern = element('speichern-btn');
    if (speichern) speichern.addEventListener('click', oeffneSpeichernDialog);

    const speichernDialog = element('speichern-dialog');
    if (speichernDialog) {
        speichernDialog.addEventListener('close', () => {
            if (speichernDialog.returnValue === 'ok') {
                const feld = element('speichern-name');
                speichereSpielstand(feld ? feld.value : '');
            }
        });
    }

    const neu = element('neu-btn');
    if (neu) {
        neu.addEventListener('click', async () => {
            if (beschaeftigt) return;
            render({ running: false });
            letzterRenderSchluessel = null;
            geplantReiter = {};
            aktualisiereGeplantZaehler();
            if (typeof leereEntwurf === 'function') leereEntwurf();
            await Promise.all([ladeOptionen(), ladeSpielstaende()]);
        });
    }
}

async function start() {
    ladeTheme();
    verbindeEreignisse();

    const [spiel, optionen, spielstaende] = await Promise.all([
        api('/api/game'),
        api('/api/options'),
        api('/api/saves')
    ]);

    if (optionen) fuelleGruendung(optionen);
    messeKopf();
    window.addEventListener('resize', messeKopf);
    if (window.ResizeObserver && element('kopf')) new ResizeObserver(messeKopf).observe(element('kopf'));

    if (spiel) {
        render(spiel);
    } else {
        setzeSichtbar('ansicht-gruendung', true);
        setzeSichtbar('ansicht-cockpit', false);
        setzeSichtbar('speichern-btn', false);
    }

    if (spielstaende) fuelleSpielstaende(spielstaende);
    aktualisiereFilter();
}

function init() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
        start();
    }
}

init();
