// Zusätze: Tochter-Rendite mit Verboten, «Neues Spiel» mit Rückfrage, Fortschritt der Hintergrund-Simulation.
'use strict';

let tochterRegeln = null;
let dashboardTimer = null;

function zusatzZahl(wert, stellen) {
    const n = Number(wert);
    if (!Number.isFinite(n)) return '–';
    return new Intl.NumberFormat('de-CH', { maximumFractionDigits: stellen ?? 0 }).format(n);
}

function zusatzGeld(wert) {
    const n = Number(wert);
    return Number.isFinite(n) ? `${zusatzZahl(n, 0)} CHF` : '–';
}

async function zusatzAnsicht(name) {
    try {
        const res = await fetch(`/api/view/${encodeURIComponent(name)}`);
        if (!res.ok) return null;
        const daten = await res.json();
        return daten && !Object.prototype.hasOwnProperty.call(daten, 'error') ? daten : null;
    } catch (err) {
        return null;
    }
}

// Je Tochter: Kaufpreis, erhalten, Wert heute, Schulden, Rendite pro Jahr und Verbote.
async function zeichneTochterRendite(container) {
    const daten = await zusatzAnsicht('daughters');
    if (!daten || !Array.isArray(daten.rows) || !daten.rows.length || !container.isConnected) return;

    const gespeichert = (typeof entwurfEntscheide === "object" && entwurfEntscheide && entwurfEntscheide.daughter_rules) || (aktuellerStand && aktuellerStand.choices && aktuellerStand.choices.daughter_rules) || {};
    if (tochterRegeln === null) tochterRegeln = JSON.parse(JSON.stringify(gespeichert));
    daten.rows.forEach((zeile) => {
        const id = String(zeile.id);
        if (!tochterRegeln[id]) tochterRegeln[id] = { ...(zeile.rules || {}) };
    });

    const bereich = document.createElement('section');
    bereich.className = 'tochter-rendite';
    const titel = document.createElement('h2');
    titel.textContent = 'Rendite der Töchter';
    bereich.appendChild(titel);

    const tabelle = document.createElement('table');
    const kopf = document.createElement('thead');
    const kopfZeile = document.createElement('tr');
    ['Tochter', 'Kaufpreis', 'Erhalten', 'Wert heute', 'Schulden', 'Ertrag/Jahr', 'Regeln'].forEach((text) => {
        const th = document.createElement('th');
        th.textContent = text;
        kopfZeile.appendChild(th);
    });
    kopf.appendChild(kopfZeile);
    tabelle.appendChild(kopf);

    const koerper = document.createElement('tbody');
    daten.rows.forEach((zeile) => {
        const id = String(zeile.id);
        const tr = document.createElement('tr');
        // Ertrag pro Jahr in CHF; Rendite in % nur, wenn ein Kaufpreis bekannt ist.
        const ertrag = Number(zeile.return_per_year);
        const preis = Number(zeile.price_paid);
        const rendite = Number.isFinite(ertrag) && preis > 0 ? ertrag / preis : NaN;
        [
            zeile.name, zusatzGeld(zeile.price_paid), zusatzGeld(zeile.received),
            zusatzGeld(zeile.value_now), zusatzGeld(zeile.debt),
            Number.isFinite(ertrag)
                ? `${zusatzGeld(ertrag)}${Number.isFinite(rendite) ? ` (${zusatzZahl(rendite * 100, 1)} %)` : ''}`
                : '–'
        ].forEach((text, i) => {
            const td = document.createElement('td');
            td.textContent = String(text ?? '–');
            if (i === 5 && Number.isFinite(ertrag)) td.className = ertrag >= 0 ? 'positiv' : 'negativ';
            tr.appendChild(td);
        });

        const regelZelle = document.createElement('td');
        const regeln = document.createElement('div');
        regeln.className = 'regeln';
        [['no_credit', 'keine Kredite'], ['no_stakes', 'keine Beteiligungen']].forEach(([schluessel, text]) => {
            const label = document.createElement('label');
            const box = document.createElement('input');
            box.type = 'checkbox';
            box.checked = Boolean(tochterRegeln[id] && tochterRegeln[id][schluessel]);
            box.addEventListener('change', () => {
                tochterRegeln[id] = { ...(tochterRegeln[id] || {}), [schluessel]: box.checked };
                if (typeof entscheidePatch === 'function') {
                    entscheidePatch({ daughter_rules: JSON.parse(JSON.stringify(tochterRegeln)) });
                }
            });
            label.appendChild(box);
            label.appendChild(document.createTextNode(` ${text}`));
            regeln.appendChild(label);
        });
        regelZelle.appendChild(regeln);
        tr.appendChild(regelZelle);
        koerper.appendChild(tr);
    });
    tabelle.appendChild(koerper);
    bereich.appendChild(tabelle);
    // Nur eine Tabelle: eine ältere (von früherem Zeichnen) ersetzen.
    container.querySelectorAll('section.tochter-rendite').forEach((alt) => alt.remove());
    container.appendChild(bereich);
}

// «Neues Spiel» in der Kopfzeile: Rückfrage, optional erst speichern, dann zurücksetzen.
async function neuesSpielStarten() {
    if (beschaeftigt) return;
    if (!window.confirm('Neues Spiel beginnen? Der laufende Spielstand wird beendet, aber vorher automatisch als «vor_neuem_spiel» gesichert.')) return;
    if (window.confirm('Soll der laufende Spielstand vorher gespeichert werden?')) {
        const vorschlag = (aktuellerStand && aktuellerStand.firm && aktuellerStand.firm.name) || 'Spielstand';
        const name = window.prompt('Name des Spielstands', vorschlag);
        if (name && name.trim()) await speichereSpielstand(name);
    }
    tochterRegeln = null;
    await postAktion('/api/reset', {}, 'Bitte warten …', async () => {
        letzterRenderSchluessel = null;
        geplantReiter = {};
        aktualisiereGeplantZaehler();
        if (typeof leereEntwurf === 'function') leereEntwurf();
        await Promise.all([ladeOptionen(), ladeSpielstaende()]);
    });
}

// Nach Spielende: Fortschritt der Hintergrund-Simulation, dann grosser Knopf «Dashboard öffnen».
function zeigeDashboardStatus(state) {
    const bereich = document.getElementById('dashboard-bereich');
    const text = document.getElementById('dashboard-status');
    const link = document.getElementById('dashboard-link');
    if (dashboardTimer) {
        window.clearTimeout(dashboardTimer);
        dashboardTimer = null;
    }
    const status = state && state.dashboard_status;
    if (!bereich || !text || !link) return;
    if (!state.game_over || !status) {
        bereich.hidden = true;
        return;
    }
    bereich.hidden = false;
    link.hidden = status !== 'fertig';
    if (state.dashboard_url) link.href = state.dashboard_url;
    if (status === 'laeuft') {
        const jahr = (state.sim_clock && state.sim_clock.year) || state.dashboard_progress;
        text.textContent = `Simulation läuft bis Jahr ${state.sim_years || 50}: Jahr ${jahr === null || jahr === undefined ? '…' : jahr}`
            + restzeitText(jahr, state.sim_years || 50);
        dashboardTimer = window.setTimeout(async () => {
            dashboardTimer = null;
            try {
                const res = await fetch('/api/game');
                if (res.ok) {
                    const neu = await res.json();
                    if (neu && neu.running !== undefined) {
                        render(neu);
                        return;
                    }
                }
            } catch (err) {
                // beim nächsten Versuch weiter
            }
            zeigeDashboardStatus(state);
        }, 3000);
    } else if (status === 'fertig') {
        text.textContent = 'Die Simulation ist bis Jahr 50 durchgelaufen. Das Dashboard ist bereit.';
    } else {
        text.textContent = 'Die Auswertung konnte nicht erstellt werden.';
    }
}


// Restzeit aus der gemessenen Geschwindigkeit (Jahre seit der ersten Messung in diesem Browser).
const fortschrittMessung = { start: null, startJahr: null };
function restzeitText(jahr, ziel) {
    const j = Number(jahr);
    if (!Number.isFinite(j)) return '';
    const jetzt = Date.now();
    if (fortschrittMessung.start === null || j < fortschrittMessung.startJahr) {
        fortschrittMessung.start = jetzt;
        fortschrittMessung.startJahr = j;
        return ' · Restzeit wird gemessen …';
    }
    const jahre = j - fortschrittMessung.startJahr;
    if (jahre < 1) return ' · Restzeit wird gemessen …';
    const proJahr = (jetzt - fortschrittMessung.start) / 1000 / jahre;
    const rest = Math.max(0, (ziel - j) * proJahr);
    const restText = rest < 90 ? `${Math.round(rest)} s` : `${Math.round(rest / 60)} Minuten`;
    return ` · etwa ${Math.round(proJahr)} s pro Jahr · noch etwa ${restText}`;
}


// «Bis zum Ende»: Firma im Autopilot. Kacheln laufen alle 3 s mit, «Ruder übernehmen» hält wieder an.
let autopilotTimer = null;
function zeigeAutopilot(state) {
    let bereich = document.getElementById('autopilot-bereich');
    if (autopilotTimer) {
        window.clearTimeout(autopilotTimer);
        autopilotTimer = null;
    }
    if (!state || !state.autopilot) {
        if (bereich) bereich.hidden = true;
        return;
    }
    if (!bereich) {
        bereich = document.createElement('div');
        bereich.id = 'autopilot-bereich';
        bereich.className = 'dashboard-bereich';
        bereich.style.position = 'sticky';
        bereich.style.top = 'var(--kopf-hoehe, 0px)';
        bereich.style.zIndex = '20';
        bereich.style.display = 'flex';
        bereich.style.gap = '1em';
        bereich.style.alignItems = 'center';
        bereich.style.flexWrap = 'wrap';
        const text = document.createElement('p');
        text.id = 'autopilot-text';
        text.setAttribute('role', 'status');
        const knopf = document.createElement('button');
        knopf.type = 'button';
        knopf.id = 'autopilot-knopf';
        knopf.className = 'primaer';
        knopf.textContent = 'Ruder übernehmen';
        knopf.addEventListener('click', async () => {
            knopf.disabled = true;
            try {
                await fetch('/api/take_over', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
            } catch (err) {
                knopf.disabled = false;
            }
            const t = document.getElementById('autopilot-text');
            if (t) t.textContent = 'Du übernimmst am nächsten Monatsanfang …';
        });
        bereich.appendChild(text);
        bereich.appendChild(knopf);
        const kopf = document.getElementById('kopf');
        if (kopf && kopf.parentNode) kopf.parentNode.insertBefore(bereich, kopf.nextSibling);
        else document.body.prepend(bereich);
    }
    bereich.hidden = false;
    const uhr = state.sim_clock || {};
    const monate = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
    const text = document.getElementById('autopilot-text');
    const knopf = document.getElementById('autopilot-knopf');
    if (state.takeover_requested) {
        text.textContent = 'Du übernimmst am nächsten Monatsanfang …';
        knopf.disabled = true;
    } else {
        text.textContent = `Autopilot führt deine Firma bis zum Spielende – gerade Jahr ${uhr.year || '…'}, ${monate[(uhr.month || 1) - 1]}.`;
        knopf.disabled = false;
    }
    autopilotTimer = window.setTimeout(async () => {
        autopilotTimer = null;
        try {
            const res = await fetch('/api/game');
            if (res.ok) {
                const neu = await res.json();
                if (neu && neu.running !== undefined) {
                    render(neu);
                    return;
                }
            }
        } catch (err) {
            // beim nächsten Versuch weiter
        }
        zeigeAutopilot(state);
    }, 3000);
}
