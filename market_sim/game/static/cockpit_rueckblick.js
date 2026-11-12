// Spielmodus Phase 6: Rückblick nach Spielende.
'use strict';

function rueckblickGeld(wert) {
    return `${Number(wert || 0).toLocaleString('de-CH', { maximumFractionDigits: 0 })} CHF`;
}

function rueckblickLinien(curves) {
    const reihen = [
        ['player_revenue', 'Dein Umsatz'],
        ['stage_avg_revenue', 'Durchschnitt der Konkurrenz'],
        ['stage_best_revenue', 'Beste Konkurrenz']
    ].filter(([key]) => Array.isArray(curves[key]) && curves[key].length);
    if (!reihen.length) return null;
    return diagramm(reihen.map(([key, name]) => ({ name, werte: curves[key] })),
        { labels: curves.labels || [], format: 'chf', hoehe: 260 });
}

function zeigeRueckblick(state) {
    let ziel = document.getElementById('rueckblick');
    const spielende = document.getElementById('spielende');
    if (!spielende) return;
    if (!ziel) {
        ziel = document.createElement('div');
        ziel.id = 'rueckblick';
        spielende.insertBefore(ziel, document.getElementById('neu-btn'));
    }
    ziel.replaceChildren();
    const r = state.review;
    if (!state.game_over) return;
    if (!r) {
        ziel.textContent = 'Der Rückblick wird berechnet, sobald die Simulation fertig ist. Lade die Seite gleich nochmals.';
        return;
    }
    const titel = document.createElement('h3');
    titel.textContent = 'Rückblick';
    const satz = document.createElement('p');
    satz.textContent = r.summary || '';
    ziel.append(titel, satz);
    if (r.curves) {
        const grafik = rueckblickLinien(r.curves);
        if (grafik) ziel.appendChild(grafik);
    }
    if (Array.isArray(r.leaders) && r.leaders.length) {
        const h = document.createElement('h3');
        h.textContent = 'Rangliste nach Firmenwert';
        const liste = document.createElement('ol');
        r.leaders.forEach((f) => {
            const li = document.createElement('li');
            li.textContent = `${f.name}: ${rueckblickGeld(f.value)}`;
            if (f.is_player) li.className = 'rueckblick-ich';
            liste.appendChild(li);
        });
        ziel.append(h, liste);
    }
    if (Array.isArray(r.decisions) && r.decisions.length) {
        const h = document.createElement('h3');
        h.textContent = 'Deine wichtigsten Entscheide';
        const liste = document.createElement('ul');
        r.decisions.forEach((d) => {
            const li = document.createElement('li');
            li.textContent = d;
            liste.appendChild(li);
        });
        ziel.append(h, liste);
    }
}
