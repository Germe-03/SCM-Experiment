// Diagramme wie im Beobachter-Dashboard: Chart.js, gleiche Farben, Zahlen beim Darüberfahren.
'use strict';

const DIAGRAMME = [];

function diagrammFarbe(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888';
}

function diagrammPalette() {
    return ['--c1', '--c2', '--c3', '--c4', '--c5', '--c6', '--c7', '--c8'].map(diagrammFarbe);
}

// Farbe einer Reihe: CSS-Variable ("var(--akzent)") auflösen, sonst Palette.
function diagrammReihenFarbe(farbe, index) {
    if (typeof farbe === 'string' && farbe.startsWith('var(')) {
        return diagrammFarbe(farbe.slice(4, -1).split(',')[0].trim());
    }
    return farbe || diagrammPalette()[index % 8];
}

function diagrammZahl(wert, stellen) {
    if (wert === null || wert === undefined || !Number.isFinite(Number(wert))) return '–';
    return new Intl.NumberFormat('de-CH', { maximumFractionDigits: stellen ?? 2 }).format(Number(wert));
}

function diagrammFormat(format) {
    if (format === 'chf') return (v) => `${diagrammZahl(v, Math.abs(v) < 100 ? 2 : 0)} CHF`;
    if (format === 'preis') return (v) => `${diagrammZahl(v, 2)} CHF`;
    if (format === 'pct') return (v) => `${diagrammZahl(v * 100, 1)} %`;
    if (format === 'ganz') return (v) => diagrammZahl(v, 0);
    return (v) => diagrammZahl(v, 2);
}

// Kurze Achsenbeschriftung: 1.2 Mio., 350'000 …
function diagrammAchse(format) {
    const voll = diagrammFormat(format);
    return (v) => {
        if (format === 'pct') return voll(v);
        const abs = Math.abs(v);
        const einheit = format === 'chf' ? ' CHF' : '';
        if (abs >= 1e9) return `${diagrammZahl(v / 1e9, 1)} Mrd.${einheit}`;
        if (abs >= 1e6) return `${diagrammZahl(v / 1e6, 1)} Mio.${einheit}`;
        return voll(v);
    };
}

// Errät das Format aus den Namen der Reihen, wenn keines angegeben ist.
function diagrammRateFormat(serien, optionen) {
    if (optionen && optionen.format) return optionen.format;
    const text = serien.map((s) => (s.name || '').toLowerCase()).join(' ');
    if (/kasse|umsatz|gewinn|preis|kurs|chf|wert/.test(text)) return 'chf';
    if (/zins|teuerung|anteil|quote|%/.test(text)) return 'pct';
    return 'zahl';
}

/**
 * Baut ein Diagramm wie im Dashboard.
 * serien: [{name, werte:[...], farbe?, typ?: 'line'|'bar', achse?: 'y'|'y2', format?}]
 * optionen: {labels, hoehe, format, typ, gestapelt, titel, y2Format}
 * Gibt ein <div class="chart"> zurück (mit Canvas); ohne Chart.js eine einfache Liste.
 */
function diagramm(serien, optionen) {
    optionen = optionen || {};
    serien = (serien || []).filter((s) => s && Array.isArray(s.werte));
    const box = document.createElement('div');
    box.className = 'chart';
    box.style.height = `${Math.max(160, Number(optionen.hoehe) || 260)}px`;
    if (!serien.length || !serien.some((s) => s.werte.length)) {
        box.classList.add('chart-leer');
        box.textContent = 'Noch keine Daten.';
        return box;
    }
    const laenge = Math.max(...serien.map((s) => s.werte.length));
    const labels = (optionen.labels && optionen.labels.length ? optionen.labels : Array.from({ length: laenge }, (_, i) => i + 1));
    const format = diagrammRateFormat(serien, optionen);
    const canvas = document.createElement('canvas');
    box.appendChild(canvas);
    if (!window.Chart) {
        box.textContent = 'Diagramme brauchen eine Internetverbindung (Chart.js).';
        return box;
    }
    Chart.defaults.color = diagrammFarbe('--muted') || diagrammFarbe('--text-leise');
    Chart.defaults.borderColor = diagrammFarbe('--line') || diagrammFarbe('--rand');
    Chart.defaults.font.family = 'system-ui,-apple-system,Segoe UI,sans-serif';
    const datasets = serien.map((s, i) => {
        const farbe = diagrammReihenFarbe(s.farbe, i);
        const balken = (s.typ || optionen.typ) === 'bar';
        return {
            label: s.name || `Reihe ${i + 1}`,
            data: s.werte.map((v) => (v === null || v === undefined ? null : Number(v))),
            type: balken ? 'bar' : 'line',
            borderColor: farbe,
            backgroundColor: balken ? farbe : `${farbe}22`,
            borderWidth: balken ? 0 : (i === 0 ? 2.5 : 2),
            pointRadius: laenge > 40 ? 0 : 2,
            pointHoverRadius: 5,
            tension: 0.25,
            fill: false,
            spanGaps: true,
            yAxisID: s.achse === 'y2' ? 'y2' : 'y',
            stack: optionen.gestapelt ? 'a' : undefined,
            _format: s.format || (s.achse === 'y2' ? (optionen.y2Format || 'zahl') : format),
        };
    });
    const scales = optionen.horizontal
        ? {
            x: { stacked: !!optionen.gestapelt, ticks: { callback: diagrammAchse(format) } },
            y: { grid: { display: false }, stacked: !!optionen.gestapelt },
        }
        : {
            x: { grid: { display: false }, stacked: !!optionen.gestapelt },
            y: { stacked: !!optionen.gestapelt, ticks: { callback: diagrammAchse(format) } },
        };
    if (datasets.some((d) => d.yAxisID === 'y2')) {
        scales.y2 = { position: 'right', grid: { display: false }, ticks: { callback: diagrammAchse(optionen.y2Format || 'zahl') } };
    }
    // Chart.js braucht das Element im DOM für die Grösse: erst zeichnen, wenn es eingehängt ist.
    const zeichne = () => {
        const alt = Chart.getChart(canvas);
        if (alt) alt.destroy();
        const chart = new Chart(canvas, {
            type: optionen.typ === 'bar' ? 'bar' : 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                indexAxis: optionen.horizontal ? 'y' : 'x',
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: datasets.length > 1, labels: { boxWidth: 12, usePointStyle: true } },
                    tooltip: {
                        itemSort: (a, b) => (b.parsed.y ?? 0) - (a.parsed.y ?? 0),
                        callbacks: {
                            label: (c) => `${c.dataset.label}: ${diagrammFormat(c.dataset._format)(optionen.horizontal ? c.parsed.x : c.parsed.y)}`,
                        },
                    },
                },
                scales,
            },
        });
        DIAGRAMME.push(chart);
    };
    let versuche = 0;
    const warte = () => { if (box.isConnected) { zeichne(); } else if (versuche++ < 200) { setTimeout(warte, 25); } };
    setTimeout(warte, 0);
    return box;
}

// Beim Wechsel Hell/Dunkel alle Diagramme mit den neuen Farben neu zeichnen.
new MutationObserver(() => {
    DIAGRAMME.splice(0).forEach((chart) => {
        if (!chart.canvas || !chart.canvas.isConnected) { chart.destroy(); return; }
        Chart.defaults.color = diagrammFarbe('--muted');
        Chart.defaults.borderColor = diagrammFarbe('--line');
        chart.update();
        DIAGRAMME.push(chart);
    });
}).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

// Streudiagramm (z.B. Preis gegen Absatz) mit Werten beim Darüberfahren.
function streuDiagramm(punkte, optionen) {
    optionen = optionen || {};
    const box = document.createElement('div');
    box.className = 'chart';
    box.style.height = `${Math.max(160, Number(optionen.hoehe) || 260)}px`;
    const canvas = document.createElement('canvas');
    box.appendChild(canvas);
    if (!window.Chart) {
        box.textContent = 'Diagramme brauchen eine Internetverbindung (Chart.js).';
        return box;
    }
    const farbe = diagrammFarbe('--c1');
    const letzte = diagrammFarbe('--c2');
    // Rand um die Daten: Achsen reichen etwas weiter als die Punkte.
    const rand = (werte) => {
        const gueltig = werte.map(Number).filter(Number.isFinite);
        if (!gueltig.length) return {};
        const lo = Math.min(...gueltig);
        const hi = Math.max(...gueltig);
        const luft = (hi - lo) * 0.12 || Math.abs(hi) * 0.1 || 1;
        return { min: lo - luft, max: hi + luft };
    };
    const xRand = rand(punkte.map((p) => p.x));
    const yRand = rand(punkte.map((p) => p.y));
    if (yRand.min !== undefined && Math.min(...punkte.map((p) => Number(p.y))) >= 0) yRand.min = Math.max(0, yRand.min);
    const zeichne = () => {
        const chart = new Chart(canvas, {
            type: 'scatter',
            data: { datasets: [{
                label: optionen.name || 'Runden',
                data: punkte.map((p) => ({ x: p.x, y: p.y, label: p.label })),
                pointRadius: punkte.map((_, i) => (i === punkte.length - 1 ? 7 : 4)),
                pointBackgroundColor: punkte.map((_, i) => (i === punkte.length - 1 ? letzte : farbe)),
            }] },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                layout: { padding: 8 },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => `${c.raw.label ? c.raw.label + ': ' : ''}${optionen.xName || 'x'} ${diagrammFormat(optionen.xFormat)(c.parsed.x)}, ${optionen.yName || 'y'} ${diagrammFormat(optionen.yFormat)(c.parsed.y)}` } },
                },
                scales: {
                    x: { ...xRand, title: { display: true, text: optionen.xTitel || '' }, ticks: { callback: diagrammAchse(optionen.xFormat) } },
                    y: { ...yRand, title: { display: true, text: optionen.yTitel || '' }, ticks: { callback: diagrammAchse(optionen.yFormat) } },
                },
            },
        });
        DIAGRAMME.push(chart);
    };
    let versuche = 0;
    const warte = () => { if (box.isConnected) { zeichne(); } else if (versuche++ < 200) { setTimeout(warte, 25); } };
    setTimeout(warte, 0);
    return box;
}


// Deutsche Namen der Rohstoffe (Simulation nutzt englische Schlüssel).
const ROHSTOFF_NAMEN = {"co2":"CO2","cork":"Kork","fruit":"Früchte","grapes":"Trauben","hops":"Hopfen","malt":"Malz","packaging":"Verpackung (Glas)","glass":"Glas","sugar":"Zucker","water":"Wasser","wheat":"Weizen","barley":"Gerste","electricity":"Strom","energy":"Energie","aluminium":"Aluminium","pet":"PET-Flaschen","yeast":"Hefe","trucks":"Lastwagen"};
function rohstoffName(key) { return ROHSTOFF_NAMEN[key] || key; }
