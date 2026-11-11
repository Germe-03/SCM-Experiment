// Spielmodus Phase 3: Entscheide mit Autopilot (choices). Wird von cockpit.js aufgerufen.
'use strict';

let spielOptionen = {};
let basisEntscheide = {};
let geplanteAuftraege = {};

function merkeOptionen(daten) {
    spielOptionen = daten || {};
}

function fuelleListe(id, eintraege, leerText) {
    const auswahl = document.getElementById(id);
    if (!auswahl) return;
    const behalten = leerText !== undefined ? `<option value="">${leerText}</option>` : '';
    auswahl.innerHTML = behalten;
    (eintraege || []).forEach((e) => {
        const option = document.createElement('option');
        option.value = typeof e === 'string' ? e : (e.id || e.name);
        option.textContent = typeof e === 'string' ? e : (e.label || e.name || e.id);
        auswahl.appendChild(option);
    });
}

function zeigeBranchenKarten(branche) {
    document.querySelectorAll('[data-branchen]').forEach((knoten) => {
        const liste = knoten.dataset.branchen.split(/\s+/);
        knoten.hidden = !liste.includes(branche);
    });
}

function dreifachNachText(wert) {
    if (wert === true) return 'ja';
    if (wert === false) return 'nein';
    return 'auto';
}

function textNachDreifach(text) {
    if (text === 'ja') return true;
    if (text === 'nein') return false;
    return null;
}

function feldWert(feld, wert) {
    const typ = feld.dataset.typ;
    if (typ === 'dreifach') return dreifachNachText(wert);
    if (wert === null || wert === undefined) return '';
    if (typ === 'prozent') return String(Math.round(Number(wert) * 100));
    if (typ === 'faktor') return String(Math.round((Number(wert) - 1) * 100));
    return String(wert);
}

function leseFeld(feld) {
    const typ = feld.dataset.typ;
    const text = feld.value.trim();
    if (typ === 'dreifach') return textNachDreifach(text);
    if (typ === 'prozent') return text === '' ? null : Math.min(100, Math.max(0, Number(text))) / 100;
    if (typ === 'faktor') return text === '' ? null : 1 + Number(text) / 100;
    if (typ === 'zahl') return text === '' ? null : Number(text);
    return text;
}

function fuelleEntscheide(state) {
    const entscheide = state.choices || {};
    basisEntscheide = { ...entscheide };
    const firma = state.firm || {};
    zeigeBranchenKarten(firma.branch || '');

    fuelleListe('c-research_target', spielOptionen.research, 'keine Forschung');
    fuelleListe('c-bank_id', spielOptionen.banks);
    const besetzt = new Set();
    fuelleListe('c-site_order', (spielOptionen.regions || []).filter((r) => !besetzt.has(r)), 'Region wählen');

    document.querySelectorAll('[data-choice]').forEach((feld) => {
        const key = feld.dataset.choice;
        if (key === 'expand_order' || key === 'site_order') return;
        const wert = entscheide[key];
        const auto = document.querySelector(`[data-auto="${key}"]`);
        if (auto) {
            auto.checked = wert === null || wert === undefined;
            feld.disabled = auto.checked;
        }
        feld.value = feldWert(feld, wert);
    });

    zeigeGeplant('expand-geplant', entscheide.expand_order, (v) => `Geplant: +${v} Einheiten`);
    zeigeGeplant('site-geplant', entscheide.site_order, (v) => `Geplant: Standort in ${v}`);
    if (!entscheide.expand_order) delete geplanteAuftraege.expand_order;
    if (!entscheide.site_order) delete geplanteAuftraege.site_order;
    zeichneVerstoesse(entscheide.offences || []);
    if (state.running && !state.game_over) aktualisiereForschung(entscheide.research_target);
}

// Die möglichen Forschungsstufen ändern sich im Spiel: nach jeder Runde neu holen.
async function aktualisiereForschung(ziel) {
    try {
        const antwort = await fetch('/api/options', { cache: 'no-store' });
        const daten = await antwort.json();
        spielOptionen.research = daten.research || [];
        fuelleListe('c-research_target', spielOptionen.research, 'keine Forschung');
        const feld = document.getElementById('c-research_target');
        if (feld && ziel) feld.value = ziel;
    } catch (fehler) {
        // Ohne Verbindung bleibt die alte Liste stehen.
    }
}

function zeigeGeplant(id, wert, text) {
    const knoten = document.getElementById(id);
    if (!knoten) return;
    knoten.hidden = !wert;
    knoten.textContent = wert ? text(wert) : '';
}

function zeichneVerstoesse(aktiv) {
    const liste = document.getElementById('offences-liste');
    if (!liste) return;
    liste.innerHTML = '';
    (spielOptionen.offences || []).forEach((v) => {
        const zeile = document.createElement('label');
        zeile.className = 'autopilot';
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.dataset.offence = v.name;
        box.checked = aktiv.includes(v.name);
        zeile.appendChild(box);
        const nutzen = Math.round(Number(v.benefit) * 100);
        const busse = Number(v.fine).toLocaleString('de-CH');
        zeile.appendChild(document.createTextNode(` ${v.name} (Vorteil ${nutzen} %, Busse ab ${busse} CHF)`));
        liste.appendChild(zeile);
    });
}

function geaenderteEntscheide() {
    const geaendert = {};
    document.querySelectorAll('[data-choice]').forEach((feld) => {
        const key = feld.dataset.choice;
        if (key === 'expand_order' || key === 'site_order') return;
        const auto = document.querySelector(`[data-auto="${key}"]`);
        const wert = auto && auto.checked ? null : leseFeld(feld);
        if (wert !== null && typeof wert === 'number' && !Number.isFinite(wert)) return;
        const vorher = basisEntscheide[key] === undefined ? null : basisEntscheide[key];
        if (wert !== vorher) geaendert[key] = wert;
    });
    const verstoesse = [...document.querySelectorAll('[data-offence]')]
        .filter((b) => b.checked).map((b) => b.dataset.offence);
    const vorher = basisEntscheide.offences || [];
    if (verstoesse.length !== vorher.length || verstoesse.some((n) => !vorher.includes(n))) {
        geaendert.offences = verstoesse;
    }
    Object.assign(geaendert, geplanteAuftraege);
    return geaendert;
}

function verbindeEntscheide() {
    document.querySelectorAll('[data-auto]').forEach((box) => {
        box.addEventListener('change', () => {
            const feld = document.querySelector(`[data-choice="${box.dataset.auto}"]`);
            if (feld) feld.disabled = box.checked;
        });
    });
    const ausbau = document.getElementById('expand-btn');
    if (ausbau) {
        ausbau.addEventListener('click', () => {
            const zahl = Number(document.getElementById('c-expand_order').value);
            if (!Number.isFinite(zahl) || zahl < 1) return;
            geplanteAuftraege.expand_order = Math.round(zahl);
            zeigeGeplant('expand-geplant', geplanteAuftraege.expand_order,
                (v) => `Wird mit der nächsten Runde geschickt: +${v} Einheiten`);
        });
    }
    const standort = document.getElementById('site-btn');
    if (standort) {
        standort.addEventListener('click', () => {
            const region = document.getElementById('c-site_order').value;
            if (!region) return;
            geplanteAuftraege.site_order = region;
            zeigeGeplant('site-geplant', region, (v) => `Wird mit der nächsten Runde geschickt: Standort in ${v}`);
        });
    }
}
