'use strict';

let aktuellerStand = null;
let basisEinstellungen = {};
let beschaeftigt = false;
let meldungsFilter = 'alle';
let statusTimer = null;
let buttonZustaende = new Map();

const svgNs = 'http://www.w3.org/2000/svg';

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
            zeigeFehler(
                daten && daten.error
                    ? String(daten.error)
                    : `Serverfehler (${res.status}).`
            );
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
    const branche = element('branche-select');
    const hersteller = branche && branche.value === 'hersteller';
    setzeSichtbar('region-wrap', Boolean(hersteller));
    setzeSichtbar('kategorie-wrap', Boolean(hersteller));
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
            option.textContent = wert;
        }
        auswahl.appendChild(option);
    });
}

async function ladeOptionen() {
    const daten = await api('/api/options');
    if (!daten) return;
    merkeOptionen(daten);

    fuelleAuswahl('branche-select', daten.branches, true);
    fuelleAuswahl('region-select', daten.regions, false);
    fuelleAuswahl('kategorie-select', daten.categories, false);
    schalteGruendungsfelder();
}

function formatiereDatum(wert) {
    if (!wert) return '';
    const datum = new Date(wert);
    if (Number.isNaN(datum.getTime())) return String(wert);
    return datum.toLocaleString('de-CH');
}

async function ladeSpielstaende() {
    const liste = element('spielstaende-liste');
    if (!liste) return;

    const daten = await api('/api/saves');
    if (!daten) return;

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
    const spielKnopfIds = ['runde-btn', 'weiter-btn', 'verkaufen-btn'];

    spielKnopfIds.forEach((id) => {
        const knopf = element(id);
        if (knopf) knopf.disabled = beschaeftigt || spielBeendet;
    });

    document.querySelectorAll('[data-key]').forEach((feld) => {
        feld.disabled = spielBeendet;
    });

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

function formatiereGeld(wert) {
    const zahl = Number(wert);
    return `${new Intl.NumberFormat('de-CH', {
        maximumFractionDigits: 0
    }).format(Number.isFinite(zahl) ? zahl : 0)} CHF`;
}

function formatiereGanzzahl(wert) {
    const zahl = Number(wert);
    return new Intl.NumberFormat('de-CH', {
        maximumFractionDigits: 0
    }).format(Number.isFinite(zahl) ? zahl : 0);
}

function setzeKpi(id, text, klasse) {
    const feld = element(id);
    if (!feld) return;

    const wert = feld.matches('.kpi-wert') ? feld : feld.querySelector('.kpi-wert');
    const ziel = wert || feld;
    ziel.textContent = text;
    if (wert) {
        wert.classList.remove('positiv', 'negativ');
        if (klasse) wert.classList.add(klasse);
    }
}

function zeichneKassenverlauf(history) {
    const svg = element('kassenverlauf');
    if (!svg) return;

    svg.replaceChildren();
    svg.setAttribute('viewBox', '0 0 300 80');

    const werte = (history || [])
        .map((eintrag) => Number(eintrag.cash))
        .filter(Number.isFinite);

    if (werte.length === 0) return;

    const min = Math.min(...werte);
    const max = Math.max(...werte);
    const gleicherWert = min === max;
    const punkte = werte.map((wert, index) => {
        const x = werte.length === 1
            ? 4
            : 4 + (index * 292) / (werte.length - 1);
        const y = gleicherWert
            ? 40
            : 76 - ((wert - min) / (max - min)) * 72;
        return `${x},${y}`;
    });

    if (werte.length === 1) punkte.push(`296,${punkte[0].split(',')[1]}`);

    if (min <= 0 && max >= 0) {
        const nulllinie = document.createElementNS(svgNs, 'line');
        const y = gleicherWert
            ? 40
            : 76 - ((0 - min) / (max - min)) * 72;
        nulllinie.setAttribute('x1', '4');
        nulllinie.setAttribute('x2', '296');
        nulllinie.setAttribute('y1', String(y));
        nulllinie.setAttribute('y2', String(y));
        nulllinie.setAttribute('class', 'nulllinie');
        nulllinie.setAttribute('stroke-dasharray', '4 4');
        svg.appendChild(nulllinie);
    }

    if (werte.length >= 2) {
        const linie = document.createElementNS(svgNs, 'polyline');
        linie.setAttribute('class', 'linie');
        linie.setAttribute('points', punkte.join(' '));
        linie.setAttribute('fill', 'none');
        svg.appendChild(linie);
    }
}

function fuelleEinstellungen(settings) {
    basisEinstellungen = { ...(settings || {}) };

    document.querySelectorAll('[data-key]').forEach((feld) => {
        if (document.activeElement === feld) return;

        const key = feld.dataset.key;
        const wert = basisEinstellungen[key];

        if (key === 'order_qty' && wert === null) {
            feld.value = '';
        } else if (feld.dataset.typ === 'prozent') {
            const zahl = Number(wert);
            feld.value = Number.isFinite(zahl) ? String(Math.round(zahl * 100)) : '';
        } else if (wert !== undefined && wert !== null) {
            feld.value = String(wert);
        } else {
            feld.value = '';
        }
    });
}

function zeigeSpielende(state) {
    const spielende = Boolean(state.game_over);
    setzeSichtbar('spielende', spielende);
    if (!spielende) return;

    const grund = state.reason === null || state.reason === undefined
        ? ''
        : String(state.reason);
    const grundKlein = grund.toLowerCase();
    let titel = 'Spiel beendet';

    if (grundKlein === 'konkurs' || grundKlein === 'bankruptcy') {
        titel = 'Die Firma ist pleite';
    } else if (grundKlein === 'verkauft' || grundKlein === 'sold') {
        titel = 'Firma verkauft';
    }

    setzeText('spielende-titel', titel);

    let text = grund ? `Grund: ${grund}` : 'Das Spiel ist beendet.';
    if (state.sale) {
        text += ` Verkaufspreis: ${formatiereGeld(state.sale.price)} (Jahr ${state.sale.year}, Monat ${state.sale.month})`;
    }
    setzeText('spielende-text', text);
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
        zeit.textContent = `Jahr ${meldung.year}, Tag ${meldung.day}`;

        li.append(zeit, document.createTextNode(` ${meldung.text || ''}`));
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

function render(state) {
    if (!state) return;
    aktuellerStand = state;

    if (!state.running) {
        setzeSichtbar('ansicht-gruendung', true);
        setzeSichtbar('ansicht-cockpit', false);
        setzeSichtbar('speichern-btn', false);
        document.title = 'SCM-Spiel';
        ladeSpielstaende();
        updateButtons();
        return;
    }

    setzeSichtbar('ansicht-gruendung', false);
    setzeSichtbar('ansicht-cockpit', true);
    setzeSichtbar('speichern-btn', true);

    const firma = state.firm || {};
    const kpis = state.kpis || {};
    const brancheNamen = { hersteller: 'Hersteller', grosshaendler: 'Grosshändler', verteiler: 'Verteiler', detailhaendler: 'Detailhändler', gastro: 'Gastro' };
    const branche = brancheNamen[firma.branch] || firma.branch || '';

    setzeText('firmenname', firma.name || '');
    setzeText('branche-anzeige', branche);
    setzeText('zeit-anzeige', `Jahr ${state.year}, Monat ${state.month}`);

    const kasse = Number(kpis.cash);
    const gewinn = Number(kpis.profit);
    setzeKpi('kpi-cash', formatiereGeld(kpis.cash), kasse >= 0 ? 'positiv' : 'negativ');
    setzeKpi('kpi-profit', formatiereGeld(kpis.profit), gewinn >= 0 ? 'positiv' : 'negativ');
    setzeKpi('kpi-inventory', formatiereGanzzahl(kpis.inventory));
    setzeKpi('kpi-backlog', formatiereGanzzahl(kpis.backlog));
    setzeKpi('kpi-employees', formatiereGanzzahl(kpis.employees));
    setzeKpi('kpi-demand', formatiereGanzzahl(kpis.recent_demand));
    setzeKpi('kpi-sales', formatiereGanzzahl(kpis.recent_sales));

    const preis = Number(kpis.sell_price);
    const konkurrenz = kpis.rival_price === null || kpis.rival_price === undefined
        ? ' (kein Konkurrenzpreis)'
        : ` (Konkurrenz: ${Number(kpis.rival_price).toFixed(2)} CHF)`;
    setzeKpi(
        'kpi-price',
        `${Number.isFinite(preis) ? preis.toFixed(2) : '0.00'} CHF${konkurrenz}`
    );

    zeichneKassenverlauf(state.history || []);
    fuelleEinstellungen(state.settings || {});
    fuelleEntscheide(state);
    fuelleHolding(state);

    const preisband = state.price_band || {};
    setzeText(
        'preisband-hinweis',
        `Erlaubt: ${preisband.min} bis ${preisband.max} CHF`
    );

    zeigeSpielende(state);
    zeigeRueckblick(state);
    zeichneMeldungen(state.messages || []);
    aktualisiereFilter();
    updateButtons();
}

function geaenderteEinstellungen() {
    const settings = {};
    const gesehen = new Set();

    document.querySelectorAll('[data-key]').forEach((feld) => {
        const key = feld.dataset.key;
        if (gesehen.has(key)) return;
        gesehen.add(key);

        let wert;
        if (feld.dataset.typ === 'prozent') {
            const zahl = Number(feld.value);
            if (feld.value.trim() === '' || !Number.isFinite(zahl)) return;
            wert = Math.round(Math.min(100, Math.max(0, zahl)) / 100 * 10000) / 10000;
        } else if (feld.dataset.typ === 'zahl') {
            if (key === 'order_qty' && feld.value.trim() === '') {
                wert = null;
            } else {
                const zahl = Number(feld.value);
                if (!Number.isFinite(zahl)) return;
                wert = zahl;
            }
        } else {
            wert = String(feld.value);
        }

        const vorher = basisEinstellungen[key];
        const gleich = typeof wert === 'number' && typeof vorher === 'number'
            ? Math.abs(wert - vorher) < (feld.dataset.typ === 'prozent' ? 0.005 : 1e-9)
            : wert === vorher;
        if (!gleich) settings[key] = wert;
    });

    return settings;
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

function verbindeEreignisse() {
    const branche = element('branche-select');
    if (branche) branche.addEventListener('change', schalteGruendungsfelder);

    const gruendung = element('gruendung-form');
    if (gruendung) {
        gruendung.addEventListener('submit', async (ereignis) => {
            ereignis.preventDefault();
            if (beschaeftigt) return;

            const nameFeld = element('firmenname-eingabe') || gruendung.querySelector('[name="name"]');
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
                category: kategorieSichtbar && element('kategorie-select')
                    ? element('kategorie-select').value
                    : null
            }, 'Bitte warten …');
        });
    }

    const einstellungen = element('einstellungen-form');
    if (einstellungen) {
        einstellungen.addEventListener('submit', async (ereignis) => {
            ereignis.preventDefault();
            await postAktion(
                '/api/round',
                { settings: geaenderteEinstellungen(), choices: geaenderteEntscheide(), orders: geplanteAuftraegeHolding() },
                'Rechne …',
                async () => {
                    leereAuftraegeHolding();
                    const liste = element('meldungen-liste');
                    if (liste) liste.scrollTop = 0;
                }
            );
        });
    }

    const weiter = element('weiter-btn');
    if (weiter) {
        weiter.addEventListener('click', () => {
            postAktion('/api/round', { settings: {}, choices: {}, orders: geplanteAuftraegeHolding() }, 'Rechne …', async () => {
                leereAuftraegeHolding();
                const liste = element('meldungen-liste');
                if (liste) liste.scrollTop = 0;
            });
        });
    }

    document.querySelectorAll('[data-key="overtime_level"]').forEach((feld) => {
        feld.addEventListener('input', () => kopiereUeberstunden(feld));
    });

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
            await Promise.all([ladeOptionen(), ladeSpielstaende()]);
        });
    }
}

async function start() {
    verbindeEreignisse();
    verbindeEntscheide();

    const [spiel, optionen, spielstaende] = await Promise.all([
        api('/api/game'),
        api('/api/options'),
        api('/api/saves')
    ]);

    if (optionen) merkeOptionen(optionen);
    if (spiel) render(spiel);

    if (optionen) {
        fuelleAuswahl('branche-select', optionen.branches, true);
        fuelleAuswahl('region-select', optionen.regions, false);
        fuelleAuswahl('kategorie-select', optionen.categories, false);
        schalteGruendungsfelder();
    }

    if (spielstaende) {
        const liste = element('spielstaende-liste');
        if (liste) {
            liste.replaceChildren();
            const eintraege = spielstaende.saves || [];
            setzeSichtbar('keine-spielstaende', eintraege.length === 0);
            eintraege.forEach((spielstand) => {
                const li = document.createElement('li');
                const datum = formatiereDatum(spielstand.saved_at);
                const teile = [spielstand.label || '', datum].filter(Boolean);
                const laden = document.createElement('button');
                laden.type = 'button';
                laden.className = 'laden';
                laden.textContent = 'Laden';
                laden.addEventListener('click', () => ladeSpielstand(spielstand.name || ''));
                li.append(
                    document.createTextNode(
                        `${spielstand.name || ''} – ${spielstand.firm || ''} (${teile.join(', ')}) `
                    ),
                    laden
                );
                liste.appendChild(li);
            });
        }
    }

    if (!spiel) {
        setzeSichtbar('ansicht-gruendung', true);
        setzeSichtbar('ansicht-cockpit', false);
        setzeSichtbar('speichern-btn', false);
    }

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
