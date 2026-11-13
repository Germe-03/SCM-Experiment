'use strict';

let spielOptionen = {};
let entwurfEinstellungen = {};
let entwurfEntscheide = {};
let geplanteAuftraege = {};
let basisEinstellungen = {};
let basisEntscheide = {};

const FELD_HILFE = {
    base_price: {
        wofuer: 'Der Preis, zu dem du verkaufst.',
        wenn: 'Höher: mehr Gewinn pro Flasche, aber meist weniger Kunden. Tiefer: mehr Kunden, aber weniger Gewinn pro Flasche.'
    },
    target_safety_stock_days: {
        wofuer: 'Wie viele Tage Vorrat du als Ziel hast.',
        wenn: 'Mehr Vorrat: weniger Risiko, nichts liefern zu können, aber mehr Geld liegt im Lager.'
    },
    order_qty: {
        wofuer: 'Wie viele Flaschen du pro Tag fest bestellst oder herstellst.',
        wenn: 'Mehr Flaschen: mehr Vorrat, aber auch mehr Lagerkosten. Leer: die Menge wird automatisch gewählt.'
    },
    overtime_level: {
        wofuer: 'Wie viele Überstunden dein Team macht.',
        wenn: 'Mehr Überstunden: mehr Arbeit ist möglich, aber die Kosten steigen.'
    },
    wage_level: {
        wofuer: 'Das Lohnniveau deiner Firma.',
        wenn: 'Höher: die Arbeit kostet mehr, aber Stellen lassen sich meist leichter besetzen.'
    },
    hiring_plan: {
        wofuer: 'Wie viele Mitarbeitende du einstellen möchtest.',
        wenn: 'Mehr Einstellungen: mehr Mitarbeitende ab dem nächsten Jahr, aber höhere Lohnkosten.'
    },
    target_quality: {
        wofuer: 'Welche Qualität du für deine Produkte anstrebst.',
        wenn: 'Höher: die Produkte werden besser, aber die Kosten können steigen.'
    },
    marketing_budget: {
        wofuer: 'Wie viel Geld du pro Jahr für Marketing einsetzt.',
        wenn: 'Mehr Geld: mehr Menschen erfahren von deiner Firma, aber die Kosten steigen.'
    },
    marketing_focus: {
        wofuer: 'Wie du dein Marketing zwischen Laden und Marke aufteilst.',
        wenn: 'Mehr Marke: mehr Werbung für deine Marke. Mehr Laden: mehr Werbung vor Ort.'
    },
    marketing_target: {
        wofuer: 'Welche Altersgruppe du mit deinem Marketing ansprichst.',
        wenn: 'Eine gewählte Gruppe reagiert stärker auf dein Marketing.'
    },
    auto_invest: {
        wofuer: 'Ob die Firma ihre Kapazität selbst ausbaut (neue Maschinen, Lager, Personalplätze).',
        wenn: 'Ja: sobald genug Geld da ist und die Nachfrage die Kapazität übersteigt, baut die Firma von selbst aus und bezahlt das aus der Kasse. Nein: die Kapazität wächst nur, wenn du unten einen Ausbau planst.'
    },
    expand_order: {
        wofuer: 'Um wie viele Flaschen pro Tag du die Kapazität erweitern willst.',
        wenn: 'Der Ausbau kostet einmalig Geld und wird nach dem Klick auf «Ausbau planen» in der nächsten Runde bezahlt. Danach kannst du pro Tag entsprechend mehr herstellen oder bearbeiten.'
    },
    site_order: {
        wofuer: 'In welcher Region du einen neuen Standort planst.',
        wenn: 'Ein neuer Standort kann mehr Kunden erreichen, kostet aber Geld.'
    },
    credit_mode: {
        wofuer: 'Ob die Firma bei Geldknappheit selbst einen Bankkredit aufnimmt. Kredite gibt es nur auf deinen Wunsch.',
        wenn: 'Nie Kredit (Standard): die Firma leiht nie Geld, kann dann aber bei leerer Kasse zahlungsunfähig werden und Investitionen fallen aus. Kredit, wenn möglich: fehlt Geld, nimmt sie bei der Bank einen Kredit auf und zahlt Zinsen dafür. Autopilot: die Simulation entscheidet nach Kassenlage.'
    },
    bank_id: {
        wofuer: 'Bei welcher Bank die Firma ihr Geld verwahrt.',
        wenn: 'Die gewählte Bank bestimmt, wo dein Geld liegt.'
    },
    payout_ratio: {
        wofuer: 'Welcher Anteil des Gewinns ausgeschüttet wird.',
        wenn: 'Mehr Ausschüttung: mehr Geld wird ausgezahlt, aber weniger bleibt in der Firma.'
    },
    listing: {
        wofuer: 'Ob die Firma an der Börse gelistet wird.',
        wenn: 'Der Börsengang wird zum Jahreswechsel ausgeführt. Er bringt Geld aus dem Aktienverkauf, dafür zahlst du Dividenden und musst öffentliche Zahlen veröffentlichen. Standard ist Nein.'
    },
    transport_mode: {
        wofuer: 'Wie deine Firma Waren transportiert.',
        wenn: 'Eigener Transport kostet Geld, kann aber mehr Kontrolle geben. Ein Dienst nutzt fremde Fahrzeuge.'
    },
    commodity_courage: {
        wofuer: 'Wie viel Rohstoff-Vorrat die Firma auf Vorrat einkauft.',
        wenn: 'Hoch: du kaufst viel auf Vorrat ein. Das schützt vor Engpässen und Preissprüngen, bindet aber Geld im Lager und kostet Lagerkosten. Tief: du kaufst nur, was du brauchst, und bist bei Engpässen verwundbar.'
    },
    markup_factor: {
        wofuer: 'Wie viel Aufschlag du auf deine Kosten rechnest.',
        wenn: 'Mehr Aufschlag: mehr Gewinn pro Verkauf, aber meist weniger Kunden.'
    },
    courier_preference: {
        wofuer: 'Welchen Kurier deine Firma für Lieferungen bucht.',
        wenn: 'Günstig: die Lieferung kostet weniger, aber Verspätungen und Ausfälle sind häufiger. Zuverlässig: der Kurier kostet mehr, liefert aber pünktlicher. Automatisch: ein Mittelweg.'
    },
    patent_lawsuits: {
        wofuer: 'Ob deine Firma Konkurrenten verklagt, die deine Patente nachahmen.',
        wenn: 'Ja: Nachahmer werden verklagt, das bringt Schadenersatz, kostet aber Anwaltskosten und kann Streit auslösen. Nein: du klagst nie. Automatisch: die Simulation entscheidet von Fall zu Fall.'
    }
};

function merkeOptionen(daten) {
    spielOptionen = daten || {};
}

function baue(tag, klasse, text) {
    const knoten = document.createElement(tag);
    if (klasse) knoten.className = klasse;
    if (text !== undefined && text !== null) knoten.textContent = String(text);
    return knoten;
}

function registriereInfoListener() {
    if (document.documentElement.dataset.infoListener === 'aktiv') return;
    document.documentElement.dataset.infoListener = 'aktiv';

    document.addEventListener('click', (ereignis) => {
        const knopf = ereignis.target.closest('.info-btn');
        if (!knopf) {
            document.querySelectorAll('.info-btn[aria-expanded="true"]').forEach((offen) => {
                offen.setAttribute('aria-expanded', 'false');
                const info = offen.parentElement.querySelector('.info-pop');
                if (info) info.hidden = true;
            });
            return;
        }

        const wrap = knopf.closest('.info-wrap');
        const info = wrap && wrap.querySelector('.info-pop');
        const wirdGeoeffnet = knopf.getAttribute('aria-expanded') !== 'true';

        document.querySelectorAll('.info-btn[aria-expanded="true"]').forEach((offen) => {
            offen.setAttribute('aria-expanded', 'false');
            const andereInfo = offen.parentElement.querySelector('.info-pop');
            if (andereInfo) andereInfo.hidden = true;
        });

        if (info && wirdGeoeffnet) {
            knopf.setAttribute('aria-expanded', 'true');
            info.hidden = false;
        }
    });

    document.addEventListener('keydown', (ereignis) => {
        if (ereignis.key !== 'Escape') return;
        document.querySelectorAll('.info-btn[aria-expanded="true"]').forEach((knopf) => {
            knopf.setAttribute('aria-expanded', 'false');
            const info = knopf.parentElement.querySelector('.info-pop');
            if (info) info.hidden = true;
        });
    });
}

function infoKnopf(wofuer, wenn) {
    registriereInfoListener();

    const wrap = baue('span', 'info-wrap');
    const knopf = baue('button', 'info-btn', 'ⓘ');
    knopf.type = 'button';
    knopf.setAttribute('aria-label', 'Erklärung');
    knopf.setAttribute('aria-expanded', 'false');

    const info = baue('div', 'info-pop');
    info.setAttribute('role', 'note');
    info.hidden = true;

    const absatzWofuer = baue('p');
    const fettWofuer = baue('strong', '', 'Wofür:');
    absatzWofuer.append(fettWofuer, document.createTextNode(` ${wofuer || ''}`));

    const absatzWenn = baue('p');
    const fettWenn = baue('strong', '', 'Was passiert, wenn …:');
    absatzWenn.append(fettWenn, document.createTextNode(` ${wenn || ''}`));

    info.append(absatzWofuer, absatzWenn);
    wrap.append(knopf, info);
    return wrap;
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
    const zahl = Number(wert);
    if (feld.dataset.stellen && Number.isFinite(zahl)) {
        return String(Number(zahl.toFixed(Number(feld.dataset.stellen))));
    }
    if (typ === 'prozent') return Number.isFinite(zahl) ? String(Math.round(zahl * 100)) : '';
    if (typ === 'faktor') return Number.isFinite(zahl) ? String(Math.round((zahl - 1) * 100)) : '';
    return String(wert);
}

function leseFeld(feld) {
    const typ = feld.dataset.typ;
    const text = feld.value.trim();
    if (typ === 'dreifach') return textNachDreifach(text);
    if (typ === 'prozent') {
        if (text === '') return null;
        const zahl = Number(text);
        return Number.isFinite(zahl) ? Math.min(100, Math.max(0, zahl)) / 100 : NaN;
    }
    if (typ === 'faktor') {
        if (text === '') return null;
        const zahl = Number(text);
        return Number.isFinite(zahl) ? 1 + zahl / 100 : NaN;
    }
    if (typ === 'zahl') {
        if (text === '') return null;
        const zahl = Number(text);
        return Number.isFinite(zahl) ? zahl : NaN;
    }
    return text;
}

function rundeProzent(wert) {
    return Math.round(wert * 10000) / 10000;
}

function gleichWert(a, b) {
    if (a === b) return true;
    if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) < 1e-9;
    return false;
}

function holeHilfe(key) {
    return FELD_HILFE[key] || {
        wofuer: 'Diese Einstellung beeinflusst deine Firma.',
        wenn: 'Eine Änderung kann Kosten, Verkäufe oder die Arbeit deiner Firma verändern.'
    };
}

function macheFeldKopf(label, id, key) {
    const kopf = baue('div', 'feld-kopf');
    const name = baue('label', 'feld-name', label);
    name.htmlFor = id;
    const hilfe = holeHilfe(key);
    kopf.append(name, infoKnopf(hilfe.wofuer, hilfe.wenn));
    return kopf;
}

function macheAutopilotZeile(key, feld, autopilot, format) {
    const zeile = baue('label', 'autopilot-zeile');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.dataset.auto = key;
    box.checked = false;
    zeile.append(box, document.createTextNode(' Autopilot'));

    const eintrag = autopilot && autopilot[key];
    if (!eintrag || !eintrag.text) return { zeile, text: null };

    let text = `Wenn an: ${eintrag.text}`;
    if (eintrag.value !== null && eintrag.value !== undefined) {
        { const anzeige = format ? format(eintrag.value) : eintrag.value; if (anzeige !== undefined && anzeige !== null) text += ` (aktuell: ${anzeige === true ? "ja" : anzeige === false ? "nein" : anzeige})`; }
    }

    return { zeile, text: baue('small', 'autopilot-text', text) };
}

function formatiereAutopilotWert(wert, typ) {
    const zahl = Number(wert);
    if (!Number.isFinite(zahl)) return String(wert);
    if (typ === 'prozent') return `${Math.round(zahl * 100)} %`;
    if (typ === 'faktor') return `${Math.round((zahl - 1) * 100)} %`;
    if (typ === 'zahl') return new Intl.NumberFormat('de-CH', { maximumFractionDigits: 2 }).format(zahl);
    return String(wert);
}

function waehleQuelle(feld, key, istEinstellung) {
    const entwurf = istEinstellung ? entwurfEinstellungen : entwurfEntscheide;
    if (Object.prototype.hasOwnProperty.call(entwurf, key)) return entwurf[key];
    const basis = istEinstellung ? basisEinstellungen : basisEntscheide;
    return basis[key] === undefined ? null : basis[key];
}

function baueEingabefeld(form, optionen) {
    const {
        key,
        label,
        istEinstellung = false,
        typ = 'text',
        eingabeTyp = 'number',
        hinweis,
        jahr = false,
        autopilot = null,
        autopilotWert,
        stellen,
        optionen: listenOptionen,
        leerText,
        min,
        max,
        schritt
    } = optionen;

    const praefix = istEinstellung ? 'f-' : 'c-';
    const id = `${praefix}${key}`;
    const feld = baue('div', 'feld');
    feld.appendChild(macheFeldKopf(label, id, key));

    const eingabe = document.createElement(listenOptionen ? 'select' : 'input');
    eingabe.id = id;
    eingabe.dataset[istEinstellung ? 'key' : 'choice'] = key;
    eingabe.dataset.typ = typ;
    if (stellen !== undefined) eingabe.dataset.stellen = String(stellen);

    if (!listenOptionen) {
        eingabe.type = eingabeTyp;
        if (min !== undefined) eingabe.min = String(min);
        if (max !== undefined) eingabe.max = String(max);
        if (schritt !== undefined) eingabe.step = String(schritt);
    } else {
        if (leerText !== undefined) {
            const leer = baue('option', '', leerText);
            leer.value = '';
            eingabe.appendChild(leer);
        }
        listenOptionen.forEach((eintrag) => {
            const option = baue('option');
            option.value = String(eintrag.value);
            option.textContent = eintrag.label;
            eingabe.appendChild(option);
        });
    }

    const wert = waehleQuelle(eingabe, key, istEinstellung);
    eingabe.value = feldWert(eingabe, wert);
    if (autopilot) {
        const automatisch = wert === null || wert === undefined;
        eingabe.disabled = automatisch;
        const teile = macheAutopilotZeile(key, eingabe, autopilot, () => {
            return formatiereAutopilotWert(autopilotWert, typ);
        });
        teile.zeile.querySelector('input').checked = automatisch;
        feld.append(eingabe, teile.zeile);
        if (teile.text) feld.appendChild(teile.text);
    } else {
        feld.appendChild(eingabe);
    }

    if (hinweis) feld.appendChild(baue('small', `hinweis${jahr ? ' jahr' : ''}`, hinweis));
    form.appendChild(feld);
    return eingabe;
}

function firmaKarte(form, titel) {
    const karte = baue('section', 'karte');
    karte.appendChild(baue('h2', '', titel));
    form.appendChild(karte);
    return karte;
}

function bauePlanungsFeld(form, key, label, buttonText) {
    const feld = baue('div', 'feld');
    const id = `c-${key}`;
    feld.appendChild(macheFeldKopf(label, id, key));

    const eingabe = document.createElement('input');
    eingabe.type = key === 'expand_order' ? 'number' : 'text';
    eingabe.id = id;
    eingabe.dataset.choice = key;
    eingabe.dataset.typ = key === 'expand_order' ? 'zahl' : 'text';
    if (key === 'expand_order') {
        eingabe.min = '1';
        eingabe.step = '100';
    }
    feld.appendChild(eingabe);

    const knopf = baue('button', '', buttonText);
    knopf.type = 'button';
    knopf.dataset.plan = key;
    feld.appendChild(knopf);

    const geplant = baue('small', 'geplant');
    geplant.dataset.geplant = key;
    geplant.hidden = true;
    feld.appendChild(geplant);

    const zurueck = baue('button', '', 'Zurücknehmen');
    zurueck.type = 'button';
    zurueck.dataset.zurueck = key;
    zurueck.hidden = true;
    feld.appendChild(zurueck);

    form.appendChild(feld);
}

function firmaPreis(wert) {
    let zahl = Number(wert);
    if (!Number.isFinite(zahl) || Math.abs(zahl) < 0.005) zahl = 0;
    return `${new Intl.NumberFormat('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(zahl)} CHF`;
}

function firmaGeld(wert) {
    if (typeof formatierePreis === 'function') return formatierePreis(wert);
    const zahl = Number(wert);
    return `${new Intl.NumberFormat('de-CH', { maximumFractionDigits: 2 }).format(zahl)} CHF`;
}

function setzeGeplant(form, key, wert) {
    const knoten = form.querySelector(`[data-geplant="${key}"]`);
    const zurueck = form.querySelector(`[data-zurueck="${key}"]`);
    if (!knoten || !zurueck) return;

    const aktiv = wert !== null && wert !== undefined && wert !== '';
    knoten.hidden = !aktiv;
    zurueck.hidden = !aktiv;
    if (!aktiv) {
        knoten.textContent = '';
    } else if (key === 'expand_order') {
        knoten.textContent = `Geplant: +${wert} Flaschen pro Tag`;
    } else {
        knoten.textContent = `Geplant: Standort in ${wert}`;
    }
}

function fuelleRegionen(auswahl) {
    const leer = baue('option', '', 'Region wählen');
    leer.value = '';
    auswahl.appendChild(leer);

    (spielOptionen.regions || []).forEach((eintrag) => {
        const option = baue('option');
        if (typeof eintrag === 'string') {
            option.value = eintrag;
            option.textContent = eintrag;
        } else {
            option.value = eintrag.id || eintrag.name || '';
            option.textContent = eintrag.label || eintrag.name || eintrag.id || '';
        }
        auswahl.appendChild(option);
    });
}

function formatiereEinstufung(form, einstufung, state) {
    const karte = firmaKarte(form, 'Einstufung');
    const daten = einstufung || {};
    const label = daten.label || (state && state.classification) || 'Noch keine Einstufung';
    karte.appendChild(baue('p', 'einstufung-label', label));
    if (daten.explanation) karte.appendChild(baue('p', '', daten.explanation));

    const verlauf = baue('ul', 'einstufung-verlauf');
    (daten.history || []).forEach((eintrag) => {
        verlauf.appendChild(baue('li', '', `Jahr ${eintrag.year}: ${eintrag.label}`));
    });
    if (verlauf.childNodes.length) karte.appendChild(verlauf);

    karte.appendChild(baue(
        'small',
        'hinweis',
        'Die Simulation stuft deine Firma nach deinen Entscheiden ein, du wählst sie nicht.'
    ));
}

function verbindeForm(form, state, spielBeendet) {
    form.addEventListener('submit', (ereignis) => ereignis.preventDefault());

    form.addEventListener('input', (ereignis) => {
        const feld = ereignis.target;
        if (!feld.matches('[data-key], [data-choice]')) return;

        const key = feld.dataset.key || feld.dataset.choice;
        const ziel = feld.dataset.key ? entwurfEinstellungen : entwurfEntscheide;
        ziel[key] = leseFeld(feld);

        if (key === 'overtime_level') {
            form.querySelectorAll('[data-key="overtime_level"]').forEach((anderes) => {
                if (anderes !== feld) anderes.value = feld.value;
            });
        }

        if (key === 'marketing_focus') aktualisiereFokus(form);
    });

    form.addEventListener('change', (ereignis) => {
        const feld = ereignis.target;
        if (feld.matches('[data-auto]')) {
            const ziel = entwurfEntscheide;
            const key = feld.dataset.auto;
            const eingabe = form.querySelector(`[data-choice="${key}"]`);
            if (eingabe) eingabe.disabled = feld.checked || spielBeendet;
            ziel[key] = feld.checked ? null : leseFeld(eingabe);
            if (key === 'marketing_focus') aktualisiereFokus(form);
            return;
        }

        if (!feld.matches('[data-key], [data-choice]')) return;
        const key = feld.dataset.key || feld.dataset.choice;
        const ziel = feld.dataset.key ? entwurfEinstellungen : entwurfEntscheide;
        ziel[key] = leseFeld(feld);
        if (key === 'marketing_target') ziel[key] = feld.value || null;
        if (key === 'marketing_focus') aktualisiereFokus(form);
    });

    form.querySelectorAll('[data-plan]').forEach((knopf) => {
        knopf.addEventListener('click', () => {
            if (spielBeendet) return;
            const key = knopf.dataset.plan;
            const feld = form.querySelector(`[data-choice="${key}"]`);
            const wert = feld && leseFeld(feld);
            if (key === 'expand_order') {
                if (!Number.isFinite(wert) || wert < 1) return;
                geplanteAuftraege[key] = Math.round(wert);
            } else {
                if (!feld || !feld.value) return;
                geplanteAuftraege[key] = feld.value;
            }
            setzeGeplant(form, key, geplanteAuftraege[key]);
        });
    });

    form.querySelectorAll('[data-zurueck]').forEach((knopf) => {
        knopf.addEventListener('click', () => {
            if (spielBeendet) return;
            const key = knopf.dataset.zurueck;
            delete geplanteAuftraege[key];
            setzeGeplant(form, key, null);
        });
    });
}

function aktualisiereFokus(form) {
    const feld = form.querySelector('[data-choice="marketing_focus"]');
    const anzeige = form.querySelector('[data-fokus-anzeige]');
    if (!feld || !anzeige) return;
    if (feld.value === '') {
        anzeige.textContent = 'Automatisch';
        return;
    }
    const marke = Math.min(100, Math.max(0, Number(feld.value)));
    anzeige.textContent = `${marke} % Marke, ${100 - marke} % Laden`;
}

// Einkaufspreis, Marge und Live-Vorschau beim Tippen eines neuen Preises.
function zeichnePreisInfo(karte, preise, state) {
    if (!preise || typeof preise !== 'object') return;
    const stk = (wert) => firmaPreis(wert);
    const tabelle = baue('table', 'preis-tabelle');
    [
        ['Einkaufspreis pro Flasche', preise.purchase_price],
        ['Marge pro Flasche (Verkaufs- minus Einkaufspreis)', preise.margin_per_bottle],
        ['Gewinn pro Flasche (nach Gemeinkosten)', preise.profit_per_bottle],
        ['Verlustgrenze (darunter machst du Verlust)', preise.break_even_price]
    ].forEach(([name, wert]) => {
        const zeile = baue('tr');
        zeile.append(baue('td', '', name), baue('td', '', stk(wert)));
        tabelle.appendChild(zeile);
    });
    karte.appendChild(tabelle);

    const vorschau = baue('div', 'preis-vorschau');
    vorschau.id = 'preis-vorschau';
    vorschau.hidden = true;
    karte.appendChild(vorschau);

    const eingabe = karte.querySelector('#f-base_price');
    if (!eingabe) return;
    const aktualisieren = () => {
        const neu = Number(String(eingabe.value).replace(',', '.'));
        const alt = Number(preise.sell_price);
        const einkauf = Number(preise.purchase_price);
        const marge = Number(preise.margin_per_bottle);
        if (eingabe.value.trim() === '' || !Number.isFinite(neu) || !Number.isFinite(einkauf)) {
            vorschau.hidden = true;
            return;
        }
        vorschau.replaceChildren();
        const margeNeu = neu - einkauf;
        const gewinnNeu = Number.isFinite(Number(preise.profit_per_bottle)) && Number.isFinite(alt)
            ? Number(preise.profit_per_bottle) + (neu - alt) : null;
        vorschau.appendChild(baue('p', '', `Neue Marge pro Flasche: ${stk(margeNeu)}` +
            (gewinnNeu === null ? '' : `, Gewinn pro Flasche: ${stk(gewinnNeu)}`)));
        if (Number.isFinite(marge) && Math.abs(neu - alt) >= 0.005) {
            let satz;
            if (margeNeu <= 0) {
                satz = 'Bei diesem Preis verdienst du an einer Flasche nichts mehr: Mehrabsatz hilft nicht.';
            } else if (marge > 0) {
                const faktor = marge / margeNeu - 1;
                const prozent = formatiereProzent(Math.abs(faktor));
                const tag = Number((state && state.kpis && state.kpis.recent_sales) || 0);
                const flaschen = tag > 0 ? ` (rund ${new Intl.NumberFormat('de-CH', { maximumFractionDigits: 0 }).format(Math.abs(faktor) * tag)} Flaschen pro Tag)` : '';
                satz = faktor > 0.0005
                    ? `Damit dein Gewinn gleich bleibt, musst du ${prozent} mehr verkaufen${flaschen}.`
                    : (faktor < -0.0005
                        ? `Du kannst bis zu ${prozent} weniger verkaufen${flaschen}, ohne weniger zu verdienen.`
                        : 'Dein Gewinn bleibt bei gleichem Absatz gleich.');
            } else {
                satz = 'Mit diesem Preis verdienst du pro Flasche wieder etwas.';
            }
            vorschau.appendChild(baue('p', '', satz));
        }
        if (Number.isFinite(Number(preise.break_even_price)) && neu < Number(preise.break_even_price)) {
            vorschau.appendChild(baue('p', 'negativ', 'Achtung: Der Preis liegt unter deiner Verlustgrenze.'));
        }
        vorschau.hidden = false;
    };
    eingabe.addEventListener('input', aktualisieren);
    aktualisieren();
}

function zeichneFirma(el, state, autopilot, einstufung, preise) {
    if (!el) return;

    state = state || {};
    const settings = state.settings || {};
    const choices = state.choices || {};
    const firma = state.firm || {};
    const kpis = state.kpis || {};
    const branch = firma.branch || '';
    const spielBeendet = Boolean(state.game_over);

    basisEinstellungen = { ...settings };
    basisEntscheide = { ...choices };
    // Kredite nur auf Wunsch: ohne Angabe gilt «Nie Kredit».
    if (basisEntscheide.credit_mode === undefined) basisEntscheide.credit_mode = 'never';

    const form = document.createElement('form');
    form.id = 'einstellungen-form';
    form.noValidate = true;

    formatiereEinstufung(form, einstufung, state);

    const verkauf = firmaKarte(form, branch === 'hersteller' ? 'Verkauf' : 'Verkauf und Einkauf');
    if (branch === 'hersteller') {
        baueEingabefeld(verkauf, {
            key: 'base_price',
            label: 'Preis',
            istEinstellung: true,
            typ: 'zahl',
            min: 0,
            schritt: '0.01',
            stellen: 2,
            hinweis: `Erlaubt: ${state.price_band ? firmaGeld(state.price_band.min) : ''} bis ${state.price_band ? firmaGeld(state.price_band.max) : ''}`
        });
        zeichnePreisInfo(verkauf, preise, state);
        const konkurrenz = kpis.rival_price === null || kpis.rival_price === undefined
            ? 'kein Konkurrenzpreis'
            : `${firmaGeld(kpis.rival_price)}`;
        verkauf.appendChild(baue('small', 'hinweis', `Konkurrenzpreis: ${konkurrenz}`));
    }

    if (branch === 'hersteller') {
        const produktion = firmaKarte(form, 'Produktion');
        baueEingabefeld(produktion, {
            key: 'target_safety_stock_days',
            label: 'Lagerziel in Tagen',
            istEinstellung: true,
            typ: 'zahl',
            min: 0,
            schritt: '1'
        });
        baueEingabefeld(produktion, {
            key: 'order_qty',
            label: 'Feste Menge pro Tag (Flaschen)',
            istEinstellung: true,
            typ: 'zahl',
            min: 0,
            schritt: '1',
            hinweis: 'In Flaschen pro Tag. Leer = automatisch.'
        });
        baueEingabefeld(produktion, {
            key: 'overtime_level',
            label: 'Überstunden %',
            istEinstellung: true,
            typ: 'prozent',
            min: 0,
            max: 100,
            schritt: '1'
        });
    } else {
        verkauf.appendChild(baue('p', 'hinweis', 'Verkaufspreise und Mengen legst du pro Marke im Reiter Einkauf fest.'));
        const zumEinkauf = baue('button', '', 'Zum Reiter Einkauf');
        zumEinkauf.type = 'button';
        zumEinkauf.addEventListener('click', () => { window.location.hash = '#einkauf'; });
        verkauf.appendChild(zumEinkauf);
    }

    const mitarbeiter = firmaKarte(form, 'Mitarbeiter');
    baueEingabefeld(mitarbeiter, {
        key: 'wage_level',
        label: 'Lohnniveau',
        istEinstellung: true,
        typ: 'zahl',
        hinweis: 'Wirkt sofort'
    });
    baueEingabefeld(mitarbeiter, {
        key: 'hiring_plan',
        label: 'Einstellungen pro Jahr',
        istEinstellung: true,
        typ: 'zahl',
        min: 0,
        schritt: '1',
        hinweis: 'Wirkt ab nächstem Jahr',
        jahr: true
    });
    baueEingabefeld(mitarbeiter, {
        key: 'overtime_level',
        label: 'Überstunden %',
        istEinstellung: true,
        typ: 'prozent',
        min: 0,
        max: 100,
        schritt: '1'
    });

    // Händler brauchen keine Zielqualität: sie führen Marken, die Qualität steckt in der Marke.
    if (branch === 'hersteller') {
        const qualitaet = firmaKarte(form, 'Qualität');
        baueEingabefeld(qualitaet, {
            key: 'target_quality',
            label: 'Zielqualität %',
            istEinstellung: true,
            typ: 'prozent',
            min: 0,
            max: 100,
            schritt: '1'
        });
    }

    if (['hersteller', 'detailhaendler', 'gastro'].includes(branch)) {
        const marketing = firmaKarte(form, 'Marketing');
        baueEingabefeld(marketing, {
            key: 'marketing_budget',
            label: 'Budget CHF/Jahr',
            typ: 'zahl',
            min: 0,
            schritt: '1',
            autopilot,
            autopilotWert: autopilot && autopilot.marketing_budget
                ? autopilot.marketing_budget.value
                : null
        });

        const fokusFeld = baueEingabefeld(marketing, {
            key: 'marketing_focus',
            label: 'Fokus',
            typ: 'prozent',
            eingabeTyp: 'range',
            min: 0,
            max: 100,
            schritt: '1',
            autopilot
        });
        const fokusHinweis = baue('div', 'fokus-beschriftung');
        fokusHinweis.append(
            baue('span', '', 'Laden/Lokal'),
            baue('span', '', 'Marke')
        );
        marketing.appendChild(fokusHinweis);
        const fokusAnzeige = baue('small', 'hinweis');
        fokusAnzeige.dataset.fokusAnzeige = '';
        marketing.appendChild(fokusAnzeige);
        aktualisiereFokus(form);
        fokusFeld.addEventListener('input', () => aktualisiereFokus(form));

        baueEingabefeld(marketing, {
            key: 'marketing_target',
            label: 'Zielgruppe',
            typ: 'text',
            optionen: [
                { value: '18-34', label: '18–34' },
                { value: '35-64', label: '35–64' },
                { value: '65+', label: '65+' }
            ],
            leerText: 'Alle'
        });
    }

    const wachstum = firmaKarte(form, 'Wachstum');
    baueEingabefeld(wachstum, {
        key: 'auto_invest',
        label: 'Automatisch investieren',
        typ: 'dreifach',
        optionen: [
            { value: 'auto', label: 'Autopilot' },
            { value: 'ja', label: 'Ja' },
            { value: 'nein', label: 'Nein' }
        ],
        autopilot
    });
    bauePlanungsFeld(wachstum, 'expand_order', 'Kapazität ausbauen (Flaschen pro Tag)', 'Ausbau planen');

    if (['detailhaendler', 'gastro'].includes(branch)) {
        const feld = baue('div', 'feld');
        feld.appendChild(macheFeldKopf('Standort planen', 'c-site_order', 'site_order'));
        const auswahl = document.createElement('select');
        auswahl.id = 'c-site_order';
        auswahl.dataset.choice = 'site_order';
        auswahl.dataset.typ = 'text';
        fuelleRegionen(auswahl);
        const wert = waehleQuelle(auswahl, 'site_order', false);
        auswahl.value = wert || '';
        feld.appendChild(auswahl);

        const knopf = baue('button', '', 'Standort planen');
        knopf.type = 'button';
        knopf.dataset.plan = 'site_order';
        feld.appendChild(knopf);
        const geplant = baue('small', 'geplant');
        geplant.dataset.geplant = 'site_order';
        geplant.hidden = true;
        feld.appendChild(geplant);
        const zurueck = baue('button', '', 'Zurücknehmen');
        zurueck.type = 'button';
        zurueck.dataset.zurueck = 'site_order';
        zurueck.hidden = true;
        feld.appendChild(zurueck);
        wachstum.appendChild(feld);
    }

    const geld = firmaKarte(form, 'Geld-Grundsätze');
    baueEingabefeld(geld, {
        key: 'credit_mode',
        label: 'Kredite',
        typ: 'text',
        optionen: [
            { value: 'auto', label: 'Autopilot' },
            { value: 'never', label: 'Nie Kredit' },
            { value: 'prefer', label: 'Kredit, wenn möglich' }
        ],
        autopilot,
        hinweis: 'Standard ist «Nie Kredit»: Die Firma leiht nur Geld, wenn du es hier erlaubst. Mit «Kredit, wenn möglich» nimmt sie bei Geldknappheit selbst einen Bankkredit auf und zahlt Zinsen dafür.'
    });

    const bankOptionen = (spielOptionen.banks || []).map((eintrag) => {
        if (typeof eintrag === 'string') return { value: eintrag, label: eintrag };
        return {
            value: eintrag.id || eintrag.name || '',
            label: eintrag.label || eintrag.name || eintrag.id || ''
        };
    });
    baueEingabefeld(geld, {
        key: 'bank_id',
        label: 'Bank',
        typ: 'text',
        optionen: bankOptionen,
        leerText: 'Keine Auswahl',
        autopilot
    });
    baueEingabefeld(geld, {
        key: 'payout_ratio',
        label: 'Ausschüttung %',
        typ: 'prozent',
        min: 0,
        max: 100,
        schritt: '1',
        autopilot
    });
    // Jede Firma ist börsenkotiert: Startfirmen ab Tag 1, neue Firmen (auch deine) nach 3 Jahren.
    geld.appendChild(baue('p', 'hinweis',
        'Börse: Deine Firma geht automatisch nach 3 Jahren an die Börse, wie jede neue Firma. '
        + 'Die Firmen vom Start sind ab Tag 1 kotiert.'));

    if (['hersteller', 'grosshaendler', 'verteiler'].includes(branch)) {
        const transport = firmaKarte(form, 'Transport');
        baueEingabefeld(transport, {
            key: 'transport_mode',
            label: 'Transport',
            typ: 'text',
            optionen: [
                { value: 'own', label: 'Eigener Transport' },
                { value: 'service', label: 'Transportdienst' }
            ],
            autopilot
        });
    }

    if (branch === 'hersteller') {
        const rohstoffe = firmaKarte(form, 'Rohstoffe');
        baueEingabefeld(rohstoffe, {
            key: 'commodity_courage',
            label: 'Einsatz für Rohstoffe %',
            typ: 'prozent',
            min: 0,
            max: 100,
            schritt: '1',
            autopilot
        });
    }

    if (branch === 'gastro') {
        const gastro = firmaKarte(form, 'Gastro');
        baueEingabefeld(gastro, {
            key: 'markup_factor',
            label: 'Aufschlag in %',
            typ: 'faktor',
            min: 0,
            max: 500,
            schritt: '1',
            autopilot
        });
    }

    const kurier = firmaKarte(form, 'Kurier und Patente');
    baueEingabefeld(kurier, {
        key: 'courier_preference',
        label: 'Kurier',
        typ: 'kurier',
        optionen: [
            { value: 'cheap', label: 'Günstig' },
            { value: 'reliable', label: 'Zuverlässig' }
        ],
        leerText: 'Automatisch'
    });
    baueEingabefeld(kurier, {
        key: 'patent_lawsuits',
        label: 'Patente: gegen Nachahmer klagen',
        typ: 'dreifach',
        optionen: [
            { value: 'auto', label: 'Automatisch' },
            { value: 'ja', label: 'Ja, klagen' },
            { value: 'nein', label: 'Nein, nicht klagen' }
        ]
    });

    form.querySelectorAll('[data-geplant]').forEach((knoten) => {
        const key = knoten.dataset.geplant;
        const aktuellerPlan = Object.prototype.hasOwnProperty.call(geplanteAuftraege, key)
            ? geplanteAuftraege[key]
            : choices[key];
        setzeGeplant(form, key, aktuellerPlan);
    });

    verbindeForm(form, state, spielBeendet);
    if (spielBeendet) {
        form.querySelectorAll('input, select, button').forEach((feld) => {
            feld.disabled = true;
        });
    }

    el.replaceChildren(form);
}

function geaenderteEinstellungen() {
    const geaendert = {};
    Object.keys(entwurfEinstellungen).forEach((key) => {
        let wert = entwurfEinstellungen[key];
        if (typeof wert === 'number' && !Number.isFinite(wert)) return;
        if (key === 'order_qty' && wert === '') wert = null;
        if (['target_quality', 'overtime_level'].includes(key)
            && typeof wert === 'number') {
            wert = rundeProzent(wert);
        }
        const vorher = basisEinstellungen[key] === undefined ? null : basisEinstellungen[key];
        if (!gleichWert(wert, vorher)) geaendert[key] = wert;
    });
    return geaendert;
}

function geaenderteEntscheide() {
    const geaendert = {};
    Object.keys(entwurfEntscheide).forEach((key) => {
        let wert = entwurfEntscheide[key];
        if (typeof wert === 'number' && !Number.isFinite(wert)) return;
        if (key === 'courier_preference' && wert === '') wert = null;
        if (key === 'supplier_shares' && wert && typeof wert === 'object'
            && Object.keys(wert).length === 0) wert = null;
        if (['marketing_focus', 'payout_ratio', 'commodity_courage'].includes(key)
            && typeof wert === 'number') {
            wert = rundeProzent(wert);
        }
        const vorher = basisEntscheide[key] === undefined ? null : basisEntscheide[key];
        if (!gleichWert(wert, vorher)) geaendert[key] = wert;
    });

    Object.assign(geaendert, geplanteAuftraege);
    Object.assign(geaendert, entwurfEntscheide);
    if (geaendert.courier_preference === '') geaendert.courier_preference = null;
    if (geaendert.supplier_shares && typeof geaendert.supplier_shares === 'object'
        && Object.keys(geaendert.supplier_shares).length === 0) geaendert.supplier_shares = null;
    return geaendert;
}

function entscheidePatch(patch) {
    if (!patch || typeof patch !== 'object') return;
    Object.keys(patch).forEach((key) => {
        entwurfEntscheide[key] = patch[key] === undefined ? null : patch[key];
    });
}

function leereEntwurf() {
    entwurfEinstellungen = {};
    entwurfEntscheide = {};
    geplanteAuftraege = {};
}
