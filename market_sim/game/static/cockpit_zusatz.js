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
    ['Tochter', 'Kaufpreis', 'Erhalten', 'Wert heute', 'Schulden', 'Rendite/Jahr', 'Regeln'].forEach((text) => {
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
        const rendite = Number(zeile.return_per_year);
        [
            zeile.name, zusatzGeld(zeile.price_paid), zusatzGeld(zeile.received),
            zusatzGeld(zeile.value_now), zusatzGeld(zeile.debt),
            Number.isFinite(rendite) ? `${zusatzZahl(rendite * 100, 1)} %` : '–'
        ].forEach((text, i) => {
            const td = document.createElement('td');
            td.textContent = String(text ?? '–');
            if (i === 5 && Number.isFinite(rendite)) td.className = rendite >= 0 ? 'positiv' : 'negativ';
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
    container.appendChild(bereich);
}

// «Neues Spiel» in der Kopfzeile: Rückfrage, optional erst speichern, dann zurücksetzen.
async function neuesSpielStarten() {
    if (beschaeftigt) return;
    if (!window.confirm('Neues Spiel beginnen? Der laufende Spielstand wird beendet.')) return;
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
        const jahr = state.dashboard_progress;
        text.textContent = `Simulation läuft bis Jahr 50: Jahr ${jahr === null || jahr === undefined ? '…' : jahr}`;
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
