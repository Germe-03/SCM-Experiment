// Spielmodus Phase 6: Rückblick nach Spielende.
'use strict';

function rueckblickGeld(wert) {
    return `${Number(wert || 0).toLocaleString('de-CH', { maximumFractionDigits: 0 })} CHF`;
}

function rueckblickLinien(curves) {
    const reihen = [
        ['player_revenue', 'Dein Umsatz', 'var(--akzent, #4a7fa8)'],
        ['stage_avg_revenue', 'Durchschnitt der Konkurrenz', 'var(--text-leise, #999)'],
        ['stage_best_revenue', 'Beste Konkurrenz', 'var(--negativ, #c0504d)']
    ].filter(([key]) => Array.isArray(curves[key]) && curves[key].length);
    const werte = reihen.flatMap(([key]) => curves[key].map(Number));
    if (!werte.length) return null;
    const max = Math.max(1, ...werte);
    const n = Math.max(...reihen.map(([key]) => curves[key].length));
    const breite = 600, hoehe = 200, rand = 10;
    const x = (i) => rand + (n > 1 ? i * (breite - 2 * rand) / (n - 1) : (breite - 2 * rand) / 2);
    const y = (v) => hoehe - rand - (Number(v) / max) * (hoehe - 2 * rand);
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', `0 0 ${breite} ${hoehe}`);
    svg.setAttribute('class', 'rueckblick-grafik');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Umsatz pro Jahr im Vergleich');
    const legende = document.createElement('div');
    legende.className = 'rueckblick-legende';
    reihen.forEach(([key, name, farbe]) => {
        const linie = document.createElementNS(ns, 'polyline');
        linie.setAttribute('points', curves[key].map((v, i) => `${x(i)},${y(v)}`).join(' '));
        linie.setAttribute('fill', 'none');
        linie.style.stroke = farbe;
        linie.setAttribute('stroke-width', key === 'player_revenue' ? '3' : '2');
        svg.appendChild(linie);
        const eintrag = document.createElement('span');
        eintrag.style.borderBottom = `3px solid ${farbe}`;
        eintrag.textContent = name;
        legende.appendChild(eintrag);
    });
    const box = document.createElement('div');
    box.append(svg, legende);
    return box;
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
