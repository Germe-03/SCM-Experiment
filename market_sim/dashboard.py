"""Standalone interactive HTML dashboard and command-line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import webbrowser

from market_sim.config import load_market_config
from market_sim.dashboard_data import build_dashboard_data
from market_sim.models import load_firms
from market_sim.run import run_simulation


CHART_JS_URL = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"


def write_dashboard_html(data: dict, path: str | Path) -> Path:
    """Write one directly-openable HTML document containing all run data."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = _HTML.replace("__DATA__", payload).replace("__CHART_JS__", CHART_JS_URL)
    target.write_text(html, encoding="utf-8")
    return target


_HTML = r'''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Biermarkt Schweiz – Simulation</title>
<script src="__CHART_JS__"></script>
<style>
:root{--bg:#f4f6f8;--panel:#fff;--ink:#16202a;--muted:#5b6876;--line:#dfe5ea;--soft:#eef2f5;--brand:#0b6b57;--brand-ink:#fff;--accent:#c2410c;--good:#15803d;--bad:#b42318;--focus:#2563eb;
--c1:#0b6b57;--c2:#d65f3c;--c3:#315ca8;--c4:#c48a12;--c5:#7b4fab;--c6:#168da3;--c7:#b3446c;--c8:#55752d;--shadow:0 1px 2px #10203010,0 4px 14px #1020300c}
:root[data-theme=dark]{--bg:#0f1418;--panel:#171e24;--ink:#e6edf2;--muted:#9aa8b5;--line:#2a343d;--soft:#1e272e;--brand:#3fb68f;--brand-ink:#08130f;--accent:#f08a5d;--good:#4ade80;--bad:#f87171;--focus:#60a5fa;
--c1:#3fb68f;--c2:#f08a5d;--c3:#7aa2f7;--c4:#e0b04a;--c5:#b48ef0;--c6:#4cc3d9;--c7:#e07aa0;--c8:#9bc46a;--shadow:none}
*{box-sizing:border-box}html{scroll-behavior:smooth}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--brand)}button,select,input{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.top{position:sticky;top:0;z-index:5;background:var(--panel);border-bottom:1px solid var(--line)}
.bar{max-width:1440px;margin:auto;padding:12px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.title h1{font-size:18px;margin:0}.title p{margin:0;color:var(--muted);font-size:12px}
.tools{margin-left:auto;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.tools label{color:var(--muted);font-size:12px;display:flex;gap:6px;align-items:center}
select,input[type=search]{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px}
.btn{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer}
.btn:hover{background:var(--soft)}.btn.primary{background:var(--brand);color:var(--brand-ink);border-color:var(--brand)}
nav.tabs{max-width:1440px;margin:auto;padding:0 12px;display:flex;gap:2px;overflow-x:auto;scrollbar-width:thin}
nav.tabs button{border:0;background:none;padding:10px 14px;border-bottom:3px solid transparent;color:var(--muted);cursor:pointer;white-space:nowrap;font-weight:500}
nav.tabs button:hover{color:var(--ink)}nav.tabs button[aria-selected=true]{color:var(--ink);border-bottom-color:var(--brand)}
main{max-width:1440px;margin:auto;padding:20px}
section[role=tabpanel]{display:none}section[role=tabpanel].active{display:block}
.lead{color:var(--muted);margin:-4px 0 16px;max-width:900px}
h2{font-size:20px;margin:0 0 6px}h3{font-size:14px;margin:0 0 8px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:18px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
.kpi span{display:block;color:var(--muted);font-size:12px}.kpi b{display:block;font-size:22px;margin-top:2px;font-variant-numeric:tabular-nums}
.kpi small{color:var(--muted)}.up{color:var(--good)}.down{color:var(--bad)}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:var(--shadow);min-width:0}
.card.wide{grid-column:1/-1}.chart{position:relative;height:270px}.card.wide .chart{height:300px}
.card p.hint{color:var(--muted);font-size:12px;margin:-4px 0 8px}
.table-wrap{overflow:auto;max-height:560px;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{background:var(--soft);position:sticky;top:0;font-weight:600;font-size:12px;color:var(--muted)}
th.sort{cursor:pointer}th.sort::after{content:" ↕";opacity:.4}th.asc::after{content:" ↑";opacity:1}th.desc::after{content:" ↓";opacity:1}
td.num,th.num{text-align:right}tbody tr.click{cursor:pointer}tbody tr.click:hover{background:var(--soft)}tr.current{background:var(--soft)}
.chips{display:flex;gap:6px;flex-wrap:wrap}.chip{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:4px 12px;cursor:pointer;font-size:13px}
.chip[aria-pressed=true]{background:var(--brand);border-color:var(--brand);color:var(--brand-ink)}
.chip .x{margin-left:6px;opacity:.7}
.filters{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.badge{display:inline-block;border-radius:999px;padding:1px 8px;font-size:12px;background:var(--soft);color:var(--muted)}
.badge.ok{background:#15803d1a;color:var(--good)}.badge.off{background:#b423181a;color:var(--bad)}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}
.empty{color:var(--muted);text-align:center;padding:28px;border:1px dashed var(--line);border-radius:10px}
.split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
.heat td{text-align:center}.heat td.lbl{text-align:left;color:var(--muted)}
.list{margin:0;padding:0;list-style:none}.list li{padding:8px 0;border-bottom:1px solid var(--line);display:flex;gap:10px}.list li:last-child{border:0}
.list .yr{color:var(--muted);min-width:56px;font-variant-numeric:tabular-nums}
.detail-head{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;margin-bottom:12px}.detail-head h2{margin:0}
.more{display:block;margin:10px auto 0}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(max-width:900px){.grid,.split{grid-template-columns:1fr}.card.wide{grid-column:auto}main{padding:12px}.bar{padding:10px 12px}}
.compare-layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:20px}.compare-layout aside{max-height:760px;overflow:auto}.compare-layout label.firm-choice{display:block;padding:7px 0}.compare-layout input[type=search]{width:100%;margin:8px 0}.best{font-weight:700;background:var(--soft)}.structure svg{min-width:900px;width:100%}.structure svg text{fill:var(--ink)}.structure [data-firm]{cursor:pointer}.structure [data-firm]:focus rect{stroke:var(--ink);stroke-width:3}@media(max-width:900px){.compare-layout{grid-template-columns:1fr}}
#flow{width:min(1040px,96vw);max-height:94vh;border:1px solid var(--line);border-radius:14px;background:var(--panel);color:inherit;padding:18px 22px;box-shadow:0 8px 30px #0003}
#flow::backdrop{background:#0006}.flow-head{display:flex;gap:8px;align-items:center}.flow-head h3{margin:0;margin-right:auto}
#flow text:not([fill]){fill:currentColor}.flow-node[tabindex]{cursor:pointer}.flow-node.off{opacity:.4}.flow-node[tabindex]:hover rect,.flow-node:focus rect{stroke-width:3.5}.flow-node:focus{outline:none}
#flow-detail h4{margin:6px 0}.flow-row{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(80px,1fr) 7.5em;gap:12px;align-items:center;padding:5px 0;border-top:1px solid var(--line)}
.flow-bar{height:8px;border-radius:4px;background:var(--soft)}.flow-bar span{display:block;height:8px;border-radius:4px}.flow-row .num{font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right}
</style></head><body>
<header class="top">
 <div class="bar">
  <div class="title"><h1>Biermarkt Schweiz – Simulation</h1><p id="meta"></p></div>
  <div class="tools">
   <label>Zeitraum <select id="from" aria-label="Erstes Jahr"></select> bis <select id="to" aria-label="Letztes Jahr"></select></label>
   <button class="btn" id="reset-range" title="Ganzen Zeitraum zeigen">Alle Jahre</button>
   <button class="btn" id="theme" aria-label="Hell oder dunkel umschalten">◐ Darstellung</button>
  </div>
 </div>
 <nav class="tabs" role="tablist" aria-label="Bereiche">
  <button role="tab" data-tab="overview">Überblick</button>
  <button role="tab" data-tab="market">Markt &amp; Kunden</button>
  <button role="tab" data-tab="map">Karte</button>
  <button role="tab" data-tab="people">Bevölkerung</button>
  <button role="tab" data-tab="firms">Firmen</button>
  <button role="tab" data-tab="structure">Marktaufbau</button>
  <button role="tab" data-tab="compare">Vergleich</button>
  <button role="tab" data-tab="chain">Lieferkette</button>
  <button role="tab" data-tab="finance">Finanzen</button>
  <button role="tab" data-tab="state">Staat</button>
  <button role="tab" data-tab="rnd">F&amp;E</button>
  <button role="tab" data-tab="events">Ereignisse</button>
  <button role="tab" data-tab="chronicle">Chronik</button>
 </nav>
</header>
<main>
<section role="tabpanel" id="tab-overview">
 <h2>Überblick</h2><p class="lead">Wie hat sich der Markt im gewählten Zeitraum entwickelt? Kennzahlen beziehen sich auf den Zeitraum oben rechts.</p>
 <div class="kpis" id="ov-kpis"></div>
 <div class="grid">
  <div class="card wide"><h3>Gewinn des ganzen Marktes und Service-Level</h3><p class="hint">Balken: Gewinn aller Firmen pro Jahr. Linie: Anteil der Nachfrage, die bedient wurde.</p><div class="chart"><canvas id="ov-profit"></canvas></div></div>
  <div class="card"><h3>Aktive Firmen pro Stufe</h3><div class="chart"><canvas id="ov-firms"></canvas></div></div>
  <div class="card"><h3>Was getrunken wird</h3><div class="chart"><canvas id="ov-cats"></canvas></div></div>
  <div class="card"><h3>Gewinner (kumulierter Gewinn)</h3><div class="table-wrap"><table id="ov-top"></table></div></div>
  <div class="card"><h3>Verlierer</h3><div class="table-wrap"><table id="ov-flop"></table></div></div>
  <div class="card wide"><h3>Wichtige Ereignisse</h3><ul class="list" id="ov-events"></ul></div>
 </div>
</section>
<section role="tabpanel" id="tab-market">
 <h2>Markt &amp; Kunden</h2><p class="lead">Kategorien, Marken, Kundenklassen und das Umfeld (Teuerung, Bevölkerung, Wechselkurs, Trends).</p>
 <div class="grid">
  <div class="card"><h3>Marktanteil der Marken</h3><p class="hint">Die acht grössten Marken am Ende des Zeitraums, der Rest als «Übrige».</p><div class="chart"><canvas id="mk-brand-share"></canvas></div></div>
  <div class="card"><h3>Reputation der Marken</h3><div class="chart"><canvas id="mk-brand-rep"></canvas></div></div>
  <div class="card"><h3>Teuerung und Bevölkerung</h3><div class="chart"><canvas id="mk-index"></canvas></div></div>
  <div class="card"><h3>Wechselkurs und Export</h3><div class="chart"><canvas id="mk-fx"></canvas></div></div>
  <div class="card"><h3>Kunden ohne Kauf (letztes Jahr)</h3><p class="hint">Anteil der Nachfrage, die keinen passenden Preis fand. Zeilen: Einkommen, Spalten: Alter.</p><div id="mk-heat"></div></div>
  <div class="card"><h3>Bezahlter Preis pro Einkommen (letztes Jahr)</h3><div class="chart"><canvas id="mk-price"></canvas></div></div>
  <div class="card"><h3>Gastronomie und Läden</h3><p class="hint">Anteil der Restaurants und Bars an Menge und Umsatz.</p><div class="chart"><canvas id="mk-channel"></canvas></div></div>
  <div class="card"><h3>Marketing und Bekanntheit</h3><p class="hint">Ausgaben aller Firmen und Bekanntheit der vier bekanntesten Marken.</p><div class="chart"><canvas id="mk-marketing"></canvas></div></div>
  <div class="card wide"><h3>Trends</h3><ul class="list" id="mk-trends"></ul></div>
 </div>
</section>
<section role="tabpanel" id="tab-map">
 <h2>Karte</h2><p class="lead">Die acht Regionen der Simulation, schematisch. Gezeigt wird das letzte Jahr des Zeitraums oben rechts.</p>
 <div class="filters"><div class="chips" id="map-layers" role="group" aria-label="Ebene"></div></div>
 <div class="split"><div class="card"><div id="map-svg"></div><div id="map-legend" class="hint" style="margin-top:8px"></div></div>
 <div class="card"><h3 id="map-title">Regionen</h3><div class="table-wrap"><table id="map-table"></table></div></div></div>
</section>
<section role="tabpanel" id="tab-people">
 <h2>Bevölkerung</h2><p class="lead">Die 30 Kundenklassen im letzten Jahr des Zeitraums. Klicke auf eine Klasse, um zwei typische Personen kennenzulernen.</p>
 <div class="card" style="margin-bottom:16px"><div class="table-wrap" style="max-height:none"><table id="pp-grid" class="heat"></table></div><p class="hint" style="margin-top:8px">Zahl oben: Personen. Unten: Anteil der Nachfrage, die gekauft wurde, und Lieblingskategorie.</p></div>
 <div id="pp-detail"></div>
</section>
<section role="tabpanel" id="tab-firms">
 <h2>Firmen</h2><p class="lead">Alle Firmen, auch ausgeschiedene. Klicke auf eine Zeile für die Details.</p>
 <div class="filters">
  <input type="search" id="fm-search" placeholder="Firma suchen …" aria-label="Firma suchen">
  <div class="chips" id="fm-stage" role="group" aria-label="Stufe"></div>
  <div class="chips" id="fm-status" role="group" aria-label="Status"></div>
 </div>
 <div class="table-wrap"><table id="fm-table"></table></div>
 <div id="fm-detail" style="margin-top:20px"></div>
</section>
<section role="tabpanel" id="tab-structure">
 <h2>Marktaufbau</h2><p class="lead">Firmen von der Gründung bis zum Austritt. Wähle einen Balken für die Firmendetails.</p>
 <div class="card"><h3>Was es zu kaufen gibt</h3><div id="ms-brands"></div></div>
 <p class="hint" id="ms-legend"></p>
 <div class="table-wrap structure" id="ms-timeline" style="max-height:none"></div>
</section>
<section role="tabpanel" id="tab-compare">
 <h2>Vergleich</h2><p class="lead">Wähle Firmen aus und vergleiche ihre Entwicklung.</p>
 <div class="compare-layout">
  <aside class="card" id="actor-selector">
   <label for="cp-search">Firmen suchen</label><input id="cp-search" type="search" placeholder="Name oder Kennung">
   <div class="filters"><button class="btn" id="cp-top">Top 5 nach Gewinn</button><button class="btn" id="cp-clear">Leeren</button></div>
   <p class="hint" id="cp-limit" aria-live="polite"></p><div id="cp-firms"></div>
  </aside>
  <div><div class="chips" id="cp-metrics" role="group" aria-label="Kennzahl"></div>
   <label><input type="checkbox" id="cp-relative"> relativ zum Stufenschnitt</label>
   <div id="cp-charts"></div>
  </div>
 </div>
</section>
<section role="tabpanel" id="tab-chain">
 <h2>Lieferkette</h2><p class="lead">Margen, Auslastung, Bestellschwankungen und Logistik pro Stufe.</p>
 <div class="grid">
  <div class="card"><h3>Marge pro Stufe</h3><div class="chart"><canvas id="ch-margin"></canvas></div></div>
  <div class="card"><h3>Auslastung pro Stufe</h3><div class="chart"><canvas id="ch-util"></canvas></div></div>
  <div class="card"><h3>Verlorene Verkäufe</h3><div class="chart"><canvas id="ch-lost"></canvas></div></div>
  <div class="card"><h3>Bullwhip (Bestellschwankung ÷ Nachfrageschwankung)</h3><div class="chart"><canvas id="ch-bull"></canvas></div></div>
  <div class="card"><h3>Transportkosten und Treibstoff</h3><div class="chart"><canvas id="ch-transport"></canvas></div></div>
  <div class="card"><h3>Eigene Flotte oder Transportdienst</h3><div class="chart"><canvas id="ch-service"></canvas></div></div>
  <div class="card wide"><h3>Ausbau und neue Standorte</h3><div class="chart"><canvas id="ch-build"></canvas></div></div>
 </div>
</section>
<section role="tabpanel" id="tab-finance">
 <h2>Finanzen</h2><p class="lead">Schulden, Zinsen, Ein- und Austritte.</p>
 <div class="card"><h3>Negativzinsen pro Stufe</h3><div class="chart"><canvas id="fi-negative"></canvas></div></div>
 <div class="grid">
  <div class="card"><h3>Verschuldung pro Stufe</h3><div class="chart"><canvas id="fi-debt"></canvas></div></div>
  <div class="card"><h3>Nettozinsen pro Stufe</h3><div class="chart"><canvas id="fi-interest"></canvas></div></div>
  <div class="card"><h3>Eintritte, Konkurse, Strategiewechsel</h3><div class="chart"><canvas id="fi-churn"></canvas></div></div>
  <div class="card"><h3>Konzentration (HHI der Händler)</h3><div class="chart"><canvas id="fi-hhi"></canvas></div></div>
  <div class="card"><h3>Arbeitsmarkt</h3><p class="hint">Offene Stellen, abgeworbene Arbeitskräfte und Lohnniveau (1 = ohne Knappheit).</p><div class="chart"><canvas id="fi-labor"></canvas></div></div>
  <div class="card"><h3>Beteiligungen und Dividenden</h3><div class="chart"><canvas id="fi-stakes"></canvas></div></div>
  <div class="card"><h3>Wer hält was (Ende des Zeitraums)</h3><div class="table-wrap"><table id="fi-holdings"></table></div></div>
 </div>
</section>
<section role="tabpanel" id="tab-state">
 <h2>Staat</h2><p class="lead">Steuern, Straftaten, Bussen, Skandale und Wettbewerbsaufsicht.</p>
 <div class="kpis" id="st-kpis"></div><div id="st-ledger"></div>
 <div class="grid">
  <div class="card"><h3>Straftaten: begangen und entdeckt</h3><div class="chart"><canvas id="st-off"></canvas></div></div>
  <div class="card"><h3>Steuern und Bussen</h3><div class="chart"><canvas id="st-money"></canvas></div></div>
  <div class="card"><h3>Vergiftungen und Angst</h3><div class="chart"><canvas id="st-fear"></canvas></div></div>
  <div class="card"><h3>Übernahmen und Wettbewerbsaufsicht</h3><div class="chart"><canvas id="st-tko"></canvas></div></div>
  <div class="card wide"><h3>Gesetze</h3><p class="hint">Eine Folge wird erst gezeigt, wenn sie nach mindestens drei Jahren deutlich grösser ist als die normale Schwankung vor dem Gesetz.</p><div class="table-wrap"><table id="st-laws"></table></div></div>
  <div class="card wide"><h3>Urteile und Eingriffe</h3><div class="table-wrap"><table id="st-table"></table></div></div>
 </div>
</section>
<section role="tabpanel" id="tab-rnd">
 <h2>Forschung &amp; Entwicklung</h2><p class="lead">Teure, langsame und unsichere Projekte und was dabei herauskam.</p>
 <div class="kpis" id="rd-kpis"></div>
 <div class="grid">
  <div class="card"><h3>Projekte pro Jahr</h3><div class="chart"><canvas id="rd-count"></canvas></div></div>
  <div class="card"><h3>Ausgaben für Projekte</h3><div class="chart"><canvas id="rd-spend"></canvas></div></div>
  <div class="card wide"><h3>Alle abgeschlossenen Projekte</h3><div class="table-wrap"><table id="rd-table"></table></div></div>
 </div>
</section>
<section role="tabpanel" id="tab-events">
 <h2>Ereignisse</h2><p class="lead">Alles, was passiert ist. Filtere nach Art oder Firma.</p>
 <div class="filters"><input type="search" id="ev-search" placeholder="Firma oder Text suchen …" aria-label="Ereignisse durchsuchen"><button class="btn" id="ev-none">Alle Arten abwählen</button><button class="btn" id="ev-all">Alle Arten</button></div>
 <div class="chips" id="ev-types" role="group" aria-label="Art des Ereignisses" style="margin-bottom:12px"></div>
 <div class="table-wrap"><table id="ev-table"></table></div>
 <button class="btn more" id="ev-more" hidden>Weitere anzeigen</button>
</section>
<section role="tabpanel" id="tab-chronicle">
 <h2>Chronik</h2><p class="lead">Jahresberichte, vom lokalen Sprachmodell aus geprüften Fakten geschrieben.</p>
 <div id="ch-list"></div>
</section>
</main>
<dialog id="flow" aria-labelledby="flow-title"><div class="flow-head"><h3 id="flow-title"></h3><button class="btn" id="flow-prev" aria-label="Jahr davor">‹</button><button class="btn" id="flow-next" aria-label="Jahr danach">›</button><button class="btn" id="flow-close" aria-label="Schliessen">✕</button></div><div id="flow-body"></div><div id="flow-detail"></div><p class="hint" style="margin-top:10px">Schliessen mit Esc, Jahr wechseln mit den Pfeiltasten.</p></dialog>
<button id="chat-open" class="btn primary" aria-haspopup="dialog" aria-controls="chat" style="position:fixed;right:20px;bottom:20px;border-radius:999px;padding:12px 18px;box-shadow:var(--shadow);z-index:20">💬 Fragen</button>
<div id="chat" role="dialog" aria-label="Fragen an die Daten" hidden style="position:fixed;right:20px;bottom:76px;width:min(380px,calc(100vw - 40px));max-height:70vh;display:none;flex-direction:column;background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:0 8px 30px #0003;z-index:21">
 <div style="display:flex;align-items:center;padding:12px 14px;border-bottom:1px solid var(--line)"><b>Fragen an die Daten</b><button class="btn" id="chat-close" aria-label="Chat schliessen" style="margin-left:auto">✕</button></div>
 <div id="chat-log" aria-live="polite" style="padding:12px 14px;overflow:auto;flex:1;display:grid;gap:10px"><div class="hint">Frag zum Beispiel: «Warum ging Rigi Markt Konkurs?» oder «Was passierte in Jahr 20?». Die Antworten kommen vom lokalen Modell und stützen sich nur auf die Daten dieses Laufs.</div></div>
 <form id="chat-form" style="display:flex;gap:8px;padding:12px 14px;border-top:1px solid var(--line)"><input id="chat-input" type="text" placeholder="Deine Frage …" aria-label="Deine Frage" style="flex:1;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 10px" maxlength="500"><button class="btn primary" id="chat-send">Senden</button></form>
</div>
<script id="dashboard-data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('dashboard-data').textContent);
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const STAGE={retailer:'Detailhandel',wholesaler:'Grosshandel',distributor:'Verteilung',factory:'Hersteller'};
const STAGES=Object.keys(STAGE);
const CAT={beer:'Bier',wine:'Wein',spirits:'Spirituosen'};
const ARCH={low_cost:'Discount',standard:'Standard',premium:'Premium',reliable:'Zuverlässig',growth:'Wachstum'};
const EVENT={policy_rate_changed:'Leitzins ge?ndert',law_enacted:'Neues Gesetz',stake_bought:'Beteiligung gekauft',stake_sold:'Beteiligung verkauft',stake_lost:'Beteiligung verloren',bankruptcy:'Konkurs',market_entry:'Markteintritt',strategy_change:'Strategiewechsel',price_increase:'Preiserhöhung',price_cut:'Preissenkung',supplier_switch:'Lieferantenwechsel',capacity_limit:'Kapazitätsgrenze',heat_summer:'Hitzesommer',harvest_failure:'Ernteausfall',recall:'Rückruf',recession:'Rezession',raw_material_shortage:'Rohstoffknappheit',cost_shock:'Kostenschock',wage_push:'Lohnschub',inflation:'Teuerung',trend_change:'Trendwechsel',restructuring:'Sanierung',transport_switch:'Transportwechsel',expand_started:'Ausbau begonnen',expand_finished:'Ausbau fertig',site_started:'Standort begonnen',site_finished:'Neuer Standort',offence_detected:'Straftat entdeckt',poisoning:'Vergiftung',takeover:'Übernahme',takeover_blocked:'Übernahme verboten',breakup:'Zerschlagung',spin_off:'Abspaltung',rnd_started:'F&E-Projekt gestartet',rnd_success:'F&E-Erfolg',rnd_failure:'F&E-Fehlschlag'};
const TREND={none:'kein Trend',craft_welle:'Craft-Welle',alkoholfrei:'Alkoholfrei',sparwelle:'Sparwelle',tradition:'Tradition',wein_boom:'Wein-Boom'};
const trendText=d=>String(d).split(/->|→/).map(x=>TREND[x.trim()]||x.trim()).join(' → ');
const REGION={genfersee:'Genferseeregion',bern:'Bern',jura_freiburg:'Jura/Freiburg/Neuenburg',nordwestschweiz:'Nordwestschweiz',zuerich:'Zürich',ostschweiz:'Ostschweiz',zentralschweiz:'Zentralschweiz',tessin:'Tessin'};
// Firm ids and region keys in event texts become readable names.
const pretty=t=>String(t??'').replace(/[a-z]+(?:_[a-z0-9]+)*/g,m=>D.firms[m]?.name||REGION[m]||m);
const KEY_EVENTS=new Set(['law_enacted','trend_change','recession','raw_material_shortage','cost_shock','poisoning','breakup','wage_push']);
const firm=id=>D.firms[id],fname=id=>firm(id)?.name||id||'Markt';
const stageLabel=f=>f?.channel==='restaurant'?'Gastronomie':STAGE[f?.stage]||'';
const nf=(v,d=0)=>v==null||isNaN(v)?'—':new Intl.NumberFormat('de-CH',{maximumFractionDigits:d}).format(v);
const pct=v=>v==null||isNaN(v)?'—':new Intl.NumberFormat('de-CH',{style:'percent',maximumFractionDigits:1}).format(v);
const chf=v=>{if(v==null||isNaN(v))return'—';const a=Math.abs(v);return a>=1e9?nf(v/1e9,2)+' Mrd. CHF':a>=1e6?nf(v/1e6,1)+' Mio. CHF':nf(v)+' CHF'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const store={get(k,d){try{return JSON.parse(localStorage.getItem('bm-'+k))??d}catch{return d}},set(k,v){try{localStorage.setItem('bm-'+k,JSON.stringify(v))}catch{}}};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const pal=()=>[1,2,3,4,5,6,7,8].map(i=>css('--c'+i));
const stageColor=()=>({...Object.fromEntries(STAGES.map((s,i)=>[s,pal()[i]])),restaurant:pal()[5]});
// The firms tab shows restaurants as their own group next to the stores.
const FM_GROUPS=[...STAGES.slice(0,1),'restaurant',...STAGES.slice(1)];const fmGroup=f=>f?.channel==='restaurant'?'restaurant':f?.stage;
// Only producers make one category; traders, stores and restaurants carry everything.
const catLabel=f=>f.stage==='factory'?CAT[f.category]||f.category:'alle Produkte';
const fmGroupLabel=g=>g==='restaurant'?'Gastronomie':STAGE[g];
const catColor=()=>({beer:pal()[3],wine:pal()[6],spirits:pal()[2]});

// --- state ---------------------------------------------------------------
const years=D.system.map(x=>x.year);
let range={from:years[0],to:years.at(-1)};
const S={tab:'overview',fmStage:new Set([...STAGES,'restaurant']),fmStatus:'all',fmSort:['profit',-1],fmFirm:null,cmp:store.get('cmp',null),evTypes:null,evLimit:200};
S.cmp=[...new Set(Array.isArray(S.cmp)?S.cmp:[])].filter(id=>firm(id)).slice(0,6);
const inRange=y=>y>=range.from&&y<=range.to;
const sys=()=>D.system.filter(x=>inRange(x.year));

// --- theme ---------------------------------------------------------------
const theme=store.get('theme',matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
document.documentElement.dataset.theme=theme;
$('#theme').onclick=()=>{const t=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=t;store.set('theme',t);render()};

// --- header --------------------------------------------------------------
$('#meta').textContent=`${D.meta.years} Jahre · Seed ${D.meta.seed} · ${Object.keys(D.firms).length} Firmen · erstellt ${new Date(D.meta.generated_at).toLocaleString('de-CH')}`;
for(const id of ['#from','#to'])$(id).innerHTML=years.map(y=>`<option value="${y}">Jahr ${y}</option>`).join('');
$('#from').value=range.from;$('#to').value=range.to;
$('#from').onchange=e=>{range.from=+e.target.value;if(range.from>range.to){range.to=range.from;$('#to').value=range.to}render()};
$('#to').onchange=e=>{range.to=+e.target.value;if(range.to<range.from){range.from=range.to;$('#from').value=range.from}render()};
$('#reset-range').onclick=()=>{range={from:years[0],to:years.at(-1)};$('#from').value=range.from;$('#to').value=range.to;render()};

// --- tabs ----------------------------------------------------------------
const tabs=$$('nav.tabs button');
function openTab(name,focus=false){if(!tabs.some(b=>b.dataset.tab===name))name='overview';if(S.tab!==name)window.scrollTo(0,0);S.tab=name;
 tabs.forEach(b=>{const on=b.dataset.tab===name;b.setAttribute('aria-selected',on);b.tabIndex=on?0:-1;if(on&&focus)b.focus()});
 $$('section[role=tabpanel]').forEach(p=>p.classList.toggle('active',p.id==='tab-'+name));
 if(location.hash!=='#'+name)history.replaceState(null,'','#'+name);render()}
tabs.forEach((b,i)=>{b.id='t-'+b.dataset.tab;b.setAttribute('aria-controls','tab-'+b.dataset.tab);b.onclick=()=>openTab(b.dataset.tab);
 b.onkeydown=e=>{const k={ArrowRight:1,ArrowLeft:-1}[e.key];if(k){e.preventDefault();openTab(tabs[(i+k+tabs.length)%tabs.length].dataset.tab,true)}}});
window.addEventListener('hashchange',()=>openTab(location.hash.slice(1)));

// --- charts --------------------------------------------------------------
const charts=[];
function destroy(){while(charts.length)charts.pop().destroy()}
function chart(id,cfg){const el=document.getElementById(id);if(!el)return;el.setAttribute('role','img');el.setAttribute('aria-label',el.closest('.card')?.querySelector('h3')?.textContent||id);
 Chart.defaults.color=css('--muted');Chart.defaults.borderColor=css('--line');Chart.defaults.font.family='system-ui,-apple-system,Segoe UI,sans-serif';
 const o=cfg.options||{};cfg.options={responsive:true,maintainAspectRatio:false,animation:matchMedia('(prefers-reduced-motion: reduce)').matches?false:{duration:250},interaction:{mode:'index',intersect:false},
  plugins:{legend:{display:cfg.data.datasets.length>1,labels:{boxWidth:12,usePointStyle:true}},tooltip:{itemSort:(a,b)=>b.parsed.y-a.parsed.y},...(o.plugins||{})},...o};
 charts.push(new Chart(el,cfg))}
// Hover mode for side-by-side stacks: the bar nearest to the mouse decides which stack is shown.
Chart.Interaction.modes.stack=(chart,e,opts,useFinal)=>{const near=Chart.Interaction.modes.nearest(chart,e,{axis:'x',intersect:false},useFinal);if(!near.length)return[];
 const i=near[0].index,key=d=>d.stack??'',st=key(chart.data.datasets[near[0].datasetIndex]);
 return chart.data.datasets.flatMap((d,di)=>key(d)===st&&chart.isDatasetVisible(di)?[{element:chart.getDatasetMeta(di).data[i],datasetIndex:di,index:i}]:[])};
const fmtAxis=f=>({ticks:{callback:v=>f==='chf'?chf(v):f==='pct'?pct(v):nf(v,2)}});
function lines(id,series,{fmt,stacked,area}={}){const s=sys();chart(id,{type:'line',data:{labels:s.map(x=>x.year),datasets:series.map((d,i)=>({label:d.label,data:s.map(d.get),borderColor:d.color||pal()[i%8],backgroundColor:(d.color||pal()[i%8])+(area?'55':'22'),fill:area?'stack':false,pointRadius:0,borderWidth:2,tension:.2,yAxisID:d.axis||'y'}))},
 options:{scales:{x:{grid:{display:false}},y:{stacked:!!stacked,...fmtAxis(fmt),...(fmt==='pct'&&!stacked?{}:{})},...(series.some(d=>d.axis==='y2')?{y2:{position:'right',grid:{display:false},...fmtAxis(series.find(d=>d.axis==='y2').fmt)}}:{})}}})}
const byStage=(prefix,fmt)=>STAGES.map(s=>({label:STAGE[s],get:x=>x[prefix+s],color:stageColor()[s],fmt}));

// --- helpers -------------------------------------------------------------
const sumBy=(arr,k)=>arr.reduce((a,x)=>a+(+x[k]||0),0);
const kpi=(label,value,note='',cls='')=>`<div class="kpi"><span>${esc(label)}</span><b>${value}</b><small class="${cls}">${note}</small></div>`;
function trend(a,b,fmt=pct){if(a==null||b==null||!isFinite(a)||!a)return['',''];const d=(b-a)/Math.abs(a);return[`${d>=0?'▲':'▼'} ${pct(Math.abs(d))} seit Jahr ${range.from}`,d>=0?'up':'down']}
const evs=()=>D.events.filter(e=>inRange(e.year));
const firmProfit=id=>firm(id).yearly.filter(y=>inRange(y.year)).reduce((a,y)=>a+(y.profit||0),0);
const status=f=>f.exit_year?`<span class="badge off">Jahr ${f.entry_year||1}–${f.exit_year}, ausgeschieden</span>`:`<span class="badge ok">aktiv seit Jahr ${f.entry_year||1}</span>`;
const empty=msg=>`<div class="empty">${esc(msg)}</div>`;
function firmRows(ids,cols){return ids.map(id=>`<tr class="click" data-firm="${esc(id)}">${cols(firm(id))}</tr>`).join('')}
function wireFirmLinks(root){root.querySelectorAll('[data-firm]').forEach(r=>{r.tabIndex=0;const go=()=>{S.fmFirm=r.dataset.firm;openTab('firms');setTimeout(()=>$('#fm-detail').scrollIntoView(),50)};r.onclick=go;r.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}}})}

// --- Überblick -----------------------------------------------------------
function renderOverview(){const s=sys(),first=s[0],last=s.at(-1);const e=evs();
 const active=STAGES.reduce((a,st)=>a+(last['active_firms_'+st]||0),0);
 const [pt,pc]=trend(first.total_profit,last.total_profit);
 $('#ov-kpis').innerHTML=[kpi('Gewinn aller Firmen (Jahr '+last.year+')',chf(last.total_profit),pt,pc),kpi('Service-Level im Schnitt',pct(s.reduce((a,x)=>a+x.service_level,0)/s.length),'Anteil der bedienten Nachfrage'),
  kpi('Aktive Firmen am Ende',nf(active),STAGES.map(st=>STAGE[st][0]+': '+(last['active_firms_'+st]||0)).join(' · ')),kpi('Markteintritte',nf(sumBy(s,'market_entries')),'im Zeitraum'),
  kpi('Konkurse',nf(sumBy(s,'bankruptcies')),nf(sumBy(s,'takeovers'))+' Übernahmen'),kpi('Preisindex',nf(last.price_index,2),'Jahr 1 = 1.00')].join('');
 const ss=sys();chart('ov-profit',{type:'bar',data:{labels:ss.map(x=>x.year),datasets:[{label:'Gewinn',data:ss.map(x=>x.total_profit),backgroundColor:ss.map(x=>x.total_profit>=0?pal()[0]+'aa':css('--bad')+'aa'),yAxisID:'y',order:2},{type:'line',label:'Service-Level',data:ss.map(x=>x.service_level),borderColor:pal()[1],pointRadius:0,borderWidth:2,yAxisID:'y2',order:1}]},
  options:{scales:{x:{grid:{display:false}},y:fmtAxis('chf'),y2:{position:'right',min:0,max:1,grid:{display:false},...fmtAxis('pct')}}}});
 lines('ov-firms',byStage('active_firms_'),{});
 lines('ov-cats',Object.keys(CAT).map(c=>({label:CAT[c],get:x=>x['share_'+c],color:catColor()[c]})),{fmt:'pct',stacked:true,area:true});
 const ranked=Object.keys(D.firms).map(id=>[id,firmProfit(id)]).sort((a,b)=>b[1]-a[1]);
 const head='<thead><tr><th>Firma</th><th>Stufe</th><th class="num">Gewinn</th><th>Status</th></tr></thead>';
 const row=([id,p])=>`<tr class="click" data-firm="${esc(id)}"><td><span class="dot" style="background:${stageColor()[firm(id).stage]}"></span>${esc(fname(id))}</td><td>${STAGE[firm(id).stage]}</td><td class="num">${chf(p)}</td><td>${status(firm(id))}</td></tr>`;
 $('#ov-top').innerHTML=head+'<tbody>'+ranked.slice(0,6).map(row).join('')+'</tbody>';
 $('#ov-flop').innerHTML=head+'<tbody>'+ranked.slice(-6).reverse().map(row).join('')+'</tbody>';
 wireFirmLinks($('#ov-top'));wireFirmLinks($('#ov-flop'));
 const key=e.filter(x=>KEY_EVENTS.has(x.event)).slice(-12).reverse();
 $('#ov-events').innerHTML=key.length?key.map(x=>`<li><span class="yr">Jahr ${x.year}</span><span><b>${esc(EVENT[x.event]||x.event)}</b>${x.firm?' · '+esc(fname(x.firm)):''} <span class="badge">${esc(x.event==='trend_change'?trendText(x.details):pretty(x.details))}</span></span></li>`).join(''):'<li>Im gewählten Zeitraum gab es keine grossen Ereignisse.</li>'}

// --- Markt & Kunden ------------------------------------------------------
function renderPhase10Market(){lines('mk-channel',[{label:'Anteil Menge',get:x=>x.restaurant_unit_share},{label:'Anteil Umsatz',get:x=>x.restaurant_revenue_share}],{fmt:'pct'});
 const rows=(D.brands||[]).filter(r=>inRange(r.year)&&r.awareness!=null);const s=sys();if(!rows.length)return;const last=Math.max(...rows.map(r=>r.year));
 const top=rows.filter(r=>r.year===last).sort((a,b)=>b.awareness-a.awareness).slice(0,4);const yrs=s.map(x=>x.year);
 chart('mk-marketing',{type:'bar',data:{labels:yrs,datasets:[{label:'Marketing',data:s.map(x=>x.marketing_spend),backgroundColor:pal()[3]+'88',yAxisID:'y',order:2},...top.map((t,i)=>({type:'line',label:t.name,data:yrs.map(y=>(rows.find(r=>r.year===y&&r.brand===t.brand)||{}).awareness??null),borderColor:pal()[i],pointRadius:0,yAxisID:'y2',order:1}))]},
  options:{scales:{x:{grid:{display:false}},y:fmtAxis('chf'),y2:{position:'right',min:0,max:1,grid:{display:false},...fmtAxis('pct')}}}})}
function renderMarket(){renderPhase10Market();const rows=(D.brands||[]).filter(r=>inRange(r.year));const yrs=[...new Set(rows.map(r=>r.year))];
 if(rows.length){const last=yrs.at(-1);const top=rows.filter(r=>r.year===last).sort((a,b)=>b.market_share-a.market_share).slice(0,8).map(r=>r.brand);const nm=id=>rows.find(r=>r.brand===id).name;
  const val=(y,id,k)=>(rows.find(r=>r.year===y&&r.brand===id)||{})[k]??null;
  const shareSets=top.map((id,i)=>({label:nm(id),data:yrs.map(y=>val(y,id,'market_share')),borderColor:pal()[i],backgroundColor:pal()[i]+'55',fill:'stack',pointRadius:0}));
  shareSets.push({label:'Übrige',data:yrs.map(y=>1-top.reduce((a,id)=>a+(val(y,id,'market_share')||0),0)),borderColor:css('--muted'),backgroundColor:css('--muted')+'33',fill:'stack',pointRadius:0});
  chart('mk-brand-share',{type:'line',data:{labels:yrs,datasets:shareSets},options:{scales:{y:{stacked:true,max:1,...fmtAxis('pct')}}}});
  chart('mk-brand-rep',{type:'line',data:{labels:yrs,datasets:top.map((id,i)=>({label:nm(id),data:yrs.map(y=>val(y,id,'reputation')),borderColor:pal()[i],pointRadius:0,borderWidth:2}))},options:{scales:{y:fmtAxis('pct')}}})}
 lines('mk-index',[{label:'Preisindex',get:x=>x.price_index},{label:'Bevölkerung',get:x=>x.population_index}]);
 lines('mk-fx',[{label:'CHF pro EUR',get:x=>x.fx_rate},{label:'Export (Einheiten)',get:x=>x.export_units,axis:'y2'}]);
 const cls=(D.classes||[]).filter(r=>inRange(r.year));
 if(cls.length){const last=Math.max(...cls.map(r=>r.year)),cur=cls.filter(r=>r.year===last);const ages=['18-34','35-64','65+'];
  const cell=(inc,age)=>{const m=cur.filter(r=>r.consumer_class.startsWith('income_'+inc+'_'+age));const d=sumBy(m,'demand'),n=sumBy(m,'no_purchase');return d?n/d:0};
  $('#mk-heat').innerHTML=`<table class="heat"><thead><tr><th>Einkommen</th>${ages.map(a=>`<th>${a} J.</th>`).join('')}</tr></thead><tbody>${[1,2,3,4,5].map(i=>`<tr><td class="lbl">Stufe ${i}${i===1?' (tief)':i===5?' (hoch)':''}</td>${ages.map(a=>{const v=cell(i,a);return`<td style="background:${css('--accent')}${Math.round(Math.min(1,v*1.5)*200).toString(16).padStart(2,'0')}">${pct(v)}</td>`}).join('')}</tr>`).join('')}</tbody></table>`;
  const price=[1,2,3,4,5].map(i=>{const m=cur.filter(r=>r.consumer_class.startsWith('income_'+i+'_'));const b=sumBy(m,'bought');return b?m.reduce((a,r)=>a+r.avg_price_paid*r.bought,0)/b:null});
  chart('mk-price',{type:'bar',data:{labels:['Stufe 1','Stufe 2','Stufe 3','Stufe 4','Stufe 5'],datasets:[{label:'CHF pro Einheit',data:price,backgroundColor:pal()[0]+'bb'}]},options:{scales:{y:fmtAxis()}}})}
 else $('#mk-heat').innerHTML=empty('Dieser Lauf nutzt das alte Nachfragemodell ohne Kundenklassen.');
 const tr=evs().filter(e=>e.event==='trend_change');
 $('#mk-trends').innerHTML=tr.length?tr.map(e=>`<li><span class="yr">Jahr ${e.year}</span><span>${esc(trendText(e.details))}</span></li>`).join(''):'<li>Kein Trendwechsel im gewählten Zeitraum.</li>'}

// --- Firmen --------------------------------------------------------------
function renderFirms(){
 $('#fm-stage').innerHTML=FM_GROUPS.map(s=>`<button class="chip" data-s="${s}" aria-pressed="${S.fmStage.has(s)}"><span class="dot" style="background:${stageColor()[s]}"></span>${fmGroupLabel(s)}</button>`).join('');
 $('#fm-status').innerHTML=[['all','Alle'],['active','Aktiv'],['exited','Ausgeschieden']].map(([k,l])=>`<button class="chip" data-st="${k}" aria-pressed="${S.fmStatus===k}">${l}</button>`).join('');
 $$('#fm-stage .chip').forEach(c=>c.onclick=()=>{const s=c.dataset.s;S.fmStage.has(s)?S.fmStage.delete(s):S.fmStage.add(s);renderFirms()});
 $$('#fm-status .chip').forEach(c=>c.onclick=()=>{S.fmStatus=c.dataset.st;renderFirms()});
 const q=$('#fm-search').value.trim().toLowerCase();
 const cols=[['name','Firma'],['stage','Stufe'],['category','Kategorie'],['region','Region'],['arch','Archetyp heute'],['profit','Gewinn im Zeitraum',1],['cash','Cash am Ende',1],['share','Marktanteil',1],['status','Status']];
 let ids=Object.keys(D.firms).filter(id=>{const f=firm(id);return S.fmStage.has(fmGroup(f))&&(S.fmStatus==='all'||(S.fmStatus==='active')===!f.exit_year)&&(!q||f.name.toLowerCase().includes(q)||id.includes(q))});
 const val=(id,k)=>{const f=firm(id),y=f.yearly.filter(r=>inRange(r.year)),l=y.at(-1)||{};return{name:f.name,stage:FM_GROUPS.indexOf(fmGroup(f)),category:catLabel(f),region:f.region||'',arch:l.archetype||f.archetype,profit:firmProfit(id),cash:l.cash,share:l.market_share,status:f.exit_year||0}[k]};
 const [sk,sd]=S.fmSort;ids.sort((a,b)=>{const x=val(a,sk),y=val(b,sk);return(x>y?1:x<y?-1:0)*sd});
 $('#fm-table').innerHTML=`<thead><tr>${cols.map(([k,l,n])=>`<th class="sort ${n?'num':''} ${sk===k?(sd>0?'asc':'desc'):''}" data-k="${k}" tabindex="0">${l}</th>`).join('')}</tr></thead><tbody>${ids.length?ids.map(id=>{const f=firm(id);return`<tr class="click ${S.fmFirm===id?'current':''}" data-firm="${esc(id)}"><td><span class="dot" style="background:${stageColor()[fmGroup(f)]}"></span>${esc(f.name)}</td><td>${stageLabel(f)}</td><td>${esc(catLabel(f))}${f.importer?' (Import)':''}</td><td>${esc(REGION[f.region]||f.region||'—')}</td><td>${esc(ARCH[val(id,'arch')]||val(id,'arch'))}</td><td class="num">${chf(val(id,'profit'))}</td><td class="num">${chf(val(id,'cash'))}</td><td class="num">${pct(val(id,'share'))}</td><td>${status(f)}</td></tr>`}).join(''):`<tr><td colspan="9">${empty('Keine Firma passt zu Suche und Filter. Entferne einen Filter oder ändere die Suche.')}</td></tr>`}</tbody>`;
 $$('#fm-table th.sort').forEach(th=>{const go=()=>{const k=th.dataset.k;S.fmSort=[k,S.fmSort[0]===k?-S.fmSort[1]:(['name','stage','category','region','arch'].includes(k)?1:-1)];renderFirms()};th.onclick=go;th.onkeydown=e=>{if(e.key==='Enter')go()}});
 $$('#fm-table tr[data-firm]').forEach(r=>{r.tabIndex=0;const go=()=>{S.fmFirm=r.dataset.firm;renderFirms();$('#fm-detail').scrollIntoView({block:'start'})};r.onclick=go;r.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}}});
 renderFirmDetail()}
const DEC_GROUP={price_band:'Preis',wage_level:'Lohn',overtime_level:'Lohn',r_and_d_budget:'F&E',rnd_started:'F&E',offence:'Straftaten',expand_started:'Investitionen',site_started:'Investitionen',takeover_bought:'Investitionen',transport_mode:'Investitionen',transport_switch:'Investitionen',archetype:'Strategie',strategy_change:'Strategie',risk_tolerance:'Strategie',target_safety_stock_days:'Strategie'};
const DEC_LABEL={price_band:'Preisband',wage_level:'Lohn',overtime_level:'Überstunden',r_and_d_budget:'F&E-Budget',rnd_started:'F&E-Projekt',offence:'Straftat',expand_started:'Ausbau',site_started:'Neuer Standort',takeover_bought:'Übernahme',transport_mode:'Transport',transport_switch:'Transportwechsel',archetype:'Strategie',strategy_change:'Strategiewechsel',risk_tolerance:'Risikobereitschaft',target_safety_stock_days:'Lagerziel (Tage)'};
const OFFENCE={lohndumping:'Lohndumping',pfusch:'Pfusch bei Rohstoffen',steuerhinterziehung:'Steuerhinterziehung'};
const EXIT_TYPE={bankruptcy:'Konkurs',takeover:'Übernahme',poisoning:'Vergiftung'};
S.decFilter=new Set(Object.values(DEC_GROUP));
function decText(d){const v=d.value;if(d.decision==='price_band')return`${nf(v.min,2)}–${nf(v.max,2)} CHF (Basis ${nf(v.base,2)})`;
 if(d.decision==='offence')return`${OFFENCE[v.offence]||v.offence}: begangen (erwarteter Vorteil ${chf(v.expected_gain)}, geschätzte Entdeckung ${pct(v.believed_detection_probability)})`;
 if(d.decision==='takeover_bought')return`kauft ${fname(v.target)} für ${chf(v.price)}`;
 if(d.decision==='archetype')return ARCH[v]||v;if(d.decision==='transport_mode')return v==='service'?'Transportdienst':'eigene Flotte';
 if(['wage_level','r_and_d_budget'].includes(d.decision))return chf(v);if(['overtime_level','risk_tolerance'].includes(d.decision))return pct(v);
 return pretty(typeof v==='object'?JSON.stringify(v):v)}
function decisionRows(id){const all=(D.decisions||[]).filter(d=>d.firm===id&&inRange(d.year));const last={},rows=[];
 for(const d of all){const key=d.decision;if(d.decision==='offence'&&!d.value.committed)continue;
  const val=JSON.stringify(d.value);const annual=['price_band','wage_level','overtime_level','r_and_d_budget','risk_tolerance','target_safety_stock_days','archetype','transport_mode'].includes(key);
  if(annual){const prev=last[key];last[key]=val;if(prev===val)continue;if(prev!==undefined&&key==='price_band'){const a=JSON.parse(prev),b=d.value;if(Math.abs(b.base-a.base)/a.base<0.02)continue}}
  rows.push(d)}
 return rows}
function renderDecisions(id){const groups=[...new Set(Object.values(DEC_GROUP))];
 $('#fd-dec-filter').innerHTML=groups.map(g=>`<button class="chip" data-g="${g}" aria-pressed="${S.decFilter.has(g)}">${g}</button>`).join('');
 $$('#fd-dec-filter .chip').forEach(c=>c.onclick=()=>{const g=c.dataset.g;S.decFilter.has(g)?S.decFilter.delete(g):S.decFilter.add(g);renderDecisions(id)});
 const rows=decisionRows(id).filter(d=>S.decFilter.has(DEC_GROUP[d.decision]||'Strategie'));const byYear={};rows.forEach(d=>(byYear[d.year]??=[]).push(d));
 const years=Object.keys(byYear).map(Number).sort((a,b)=>b-a);
 $('#fd-decisions').innerHTML=years.length?years.map(y=>`<li><span class="yr">Jahr ${y}</span><span>${byYear[y].map(d=>`<b>${esc(DEC_LABEL[d.decision]||d.decision)}:</b> ${esc(decText(d))}`).join('<br>')}</span></li>`).join(''):'<li>Keine Entscheidungen für diese Auswahl.</li>'}
function renderExit(id){const box=$('#fd-exit'),a=(D.exit_analysis||{})[id];if(!a){box.hidden=true;return}box.hidden=false;
 const max=Math.max(...a.drivers.map(d=>d.value),1);
 box.innerHTML=`<h3>Warum ausgeschieden? <span class="badge off">${EXIT_TYPE[a.exit_type]||a.exit_type} in Jahr ${a.exit_year}</span></h3><p>${esc(a.summary_de)}</p>
 ${a.drivers.length?`<div style="display:grid;gap:8px;max-width:640px">${a.drivers.map(d=>`<div><div style="display:flex;justify-content:space-between"><span>${esc(d.label_de)}</span><span>${chf(d.value)}</span></div><div style="height:8px;border-radius:4px;background:var(--soft)"><div style="height:8px;border-radius:4px;width:${Math.round(d.value/max*100)}%;background:var(--bad)"></div></div></div>`).join('')}</div>`:''}
 ${a.events.length?`<p class="hint" style="margin-top:10px">In derselben Zeit: ${a.events.slice(-6).map(e=>`Jahr ${e.year} ${esc(EVENT[e.event]||e.event)}${e.firm?' ('+esc(fname(e.firm))+')':''}`).join(' · ')}</p>`:''}
 <p class="hint">Die Treiber sind Buchhaltungszahlen der letzten Jahre, kein Beweis einer einzelnen Ursache.</p>`}
function renderFirmDetail(){const root=$('#fm-detail');destroy();if(S.tab!=='firms')return;const id=S.fmFirm;
 if(!id||!firm(id)){root.innerHTML=empty('Wähle oben eine Firma, um ihre Entwicklung zu sehen.');return}
 const f=firm(id),y=f.yearly.filter(r=>inRange(r.year)),l=y.at(-1)||{};const inCmp=(S.cmp||[]).includes(id);
 root.innerHTML=`<div class="card"><div class="detail-head"><h2>${esc(f.name)}</h2><span class="badge">${stageLabel(f)}</span><span class="badge">${esc(catLabel(f))}${f.importer?' · Import':''}</span><span class="badge">${esc(REGION[f.region]||f.region||'')}</span>${status(f)}<button class="btn ${inCmp?'':'primary'}" id="fd-cmp" style="margin-left:auto">${inCmp?'Aus Vergleich entfernen':'Zum Vergleich hinzufügen'}</button></div>
 <div class="kpis">${kpi('Gewinn im Zeitraum',chf(firmProfit(id)))}${kpi('Cash am Ende',chf(l.cash))}${kpi('Reputation',pct(l.reputation))}${kpi('Qualität',pct(l.average_quality))}${kpi('Auslastung',pct(l.capacity_utilization))}${kpi('Marktanteil',pct(l.market_share))}${kpi('Lieferquote',pct(l.service_level))}</div>
 <div class="grid"><div class="card wide"><h3>Umsatz und Kosten pro Jahr</h3><p class="hint">Fahre über eine Säule für die Kostenarten. Klicke auf ein Jahr, um zu sehen, wohin das Geld floss.</p><div class="chart"><canvas id="fd-cost"></canvas></div></div>
 <div class="card"><h3>Cash (Wochenschnitt)</h3><div class="chart"><canvas id="fd-cash"></canvas></div></div><div class="card"><h3>Lager und Rückstand (Wochenschnitt)</h3><div class="chart"><canvas id="fd-stock"></canvas></div></div>
 <div class="card"><h3>Reputation und Qualität</h3><div class="chart"><canvas id="fd-rep"></canvas></div></div><div class="card"><h3>Ereignisse dieser Firma</h3><ul class="list" id="fd-events" style="max-height:270px;overflow:auto"></ul></div>
 <div class="card wide" id="fd-story" hidden></div>
 <div class="card wide" id="fd-exit" hidden></div>
 <div class="card wide"><h3>Entscheidungen</h3><p class="hint">Pro Jahr nur, was sich geändert hat, dazu Straftaten, Investitionen und Projekte.</p><div class="chips" id="fd-dec-filter" style="margin-bottom:10px"></div><ul class="list" id="fd-decisions" style="max-height:420px;overflow:auto"></ul></div></div></div>`;
 $('#fd-cmp').disabled=!inCmp&&(S.cmp||[]).length>=6;
 root.insertAdjacentHTML('beforeend',ledgerHtml(id));
 $('#fd-cmp').onclick=()=>{const c=new Set(S.cmp||[]);c.has(id)?c.delete(id):(c.size<6&&c.add(id));S.cmp=[...c];store.set('cmp',S.cmp);renderFirmDetail()};
 const lbl=y.map(r=>r.year),costs={purchase_cost:'Einkauf/Rohstoffe',wage_cost:'Löhne',fixed_cost:'Fixkosten',handling_cost:'Handling & Transport',rnd_cost:'F&E',holding_cost:'Lager',backlog_cost:'Rückstand',hiring_cost:'Einstellung',interest_cost:'Zinsen'};
 chart('fd-cost',{type:'bar',data:{labels:lbl,datasets:[{label:'Umsatz',data:y.map(r=>r.revenue),backgroundColor:pal()[0],stack:'rev'},...Object.entries(costs).map(([k,n],j)=>({label:n,data:y.map(r=>r[k]),backgroundColor:pal()[(j+1)%8]+'cc',stack:'cost'}))]},
  options:{interaction:{mode:'stack'},onClick:(e,els,c)=>{const p=c.getElementsAtEventForMode(e,'index',{intersect:false},true);if(p.length)openFlow(id,+c.data.labels[p[0].index])},onHover:(e,els)=>{e.native.target.style.cursor=els.length?'pointer':'default'},plugins:{tooltip:{itemSort:(a,b)=>b.parsed.y-a.parsed.y,callbacks:{label:c=>`${c.dataset.label}: ${chf(c.parsed.y)}`,footer:it=>it.length>1?`Total Kosten: ${chf(it.reduce((a,c)=>a+c.parsed.y,0))}`:''}}},scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,...fmtAxis('chf')}}}});
 const weeks=D.meta.days_per_year/7,w=f.weekly,from=Math.floor((range.from-1)*weeks),to=Math.ceil(range.to*weeks);const wl=w.cash.slice(from,to).map((_,i)=>((from+i)/weeks+1).toFixed(1));
 chart('fd-cash',{type:'line',data:{labels:wl,datasets:[{label:'Cash',data:w.cash.slice(from,to),borderColor:pal()[2],pointRadius:0,borderWidth:1.5}]},options:{scales:{x:{ticks:{maxTicksLimit:10,callback:function(v){return'Jahr '+Math.floor(this.getLabelForValue(v))}}},y:fmtAxis('chf')}}});
 chart('fd-stock',{type:'line',data:{labels:wl,datasets:[{label:'Lager',data:w.inventory.slice(from,to),borderColor:pal()[0],pointRadius:0,borderWidth:1.5},{label:'Rückstand',data:w.backlog.slice(from,to),borderColor:pal()[1],pointRadius:0,borderWidth:1.5}]},options:{scales:{x:{ticks:{maxTicksLimit:10,callback:function(v){return'Jahr '+Math.floor(this.getLabelForValue(v))}}}}}});
 chart('fd-rep',{type:'line',data:{labels:lbl,datasets:[{label:'Reputation',data:y.map(r=>r.reputation),borderColor:pal()[4],pointRadius:0,borderWidth:2},{label:'Qualität',data:y.map(r=>r.average_quality),borderColor:pal()[5],pointRadius:0,borderWidth:2}]},options:{scales:{y:fmtAxis('pct')}}});
 const fe=f.events.filter(e=>inRange(e.year)&&e.event!=='inflation').slice().reverse();
 $('#fd-events').innerHTML=fe.length?fe.map(e=>`<li><span class="yr">Jahr ${e.year}</span><span><b>${esc(EVENT[e.event]||e.event)}</b> <span class="badge">${esc(pretty(e.details))}</span></span></li>`).join(''):'<li>Keine Ereignisse im Zeitraum.</li>';
 renderExit(id);renderDecisions(id);
 const st=((D.texts||{}).stories||{})[id],sb=$('#fd-story');sb.hidden=!st;if(st)sb.innerHTML=`<h3>Geschichte ${st.checked?'<span class="badge ok">vom lokalen Modell, Zahlen geprüft</span>':'<span class="badge">Kurzfassung aus den Fakten</span>'}</h3><p style="margin:0">${esc(pretty(st.text))}</p>`}

// --- Vergleich -----------------------------------------------------------
const CMP_METRICS=[['profit','Gewinn','chf'],['revenue','Umsatz','chf'],['cash','Cash','chf'],['market_share','Marktanteil','pct'],['reputation','Reputation','pct'],['average_quality','Qualität','pct'],['average_sell_price','Preis',null],['capacity_utilization','Auslastung','pct'],['service_level','Lieferquote','pct']];
const savedCmpColors=store.get('cmp-colors',{});
const cmpColors=savedCmpColors&&typeof savedCmpColors==='object'&&!Array.isArray(savedCmpColors)?savedCmpColors:{};
function assignCompareColors(){for(const id of Object.keys(cmpColors)){if(!S.cmp.includes(id))delete cmpColors[id]}for(const id of S.cmp){if(cmpColors[id]==null||S.cmp.some(other=>other!==id&&cmpColors[other]===cmpColors[id])){const used=S.cmp.filter(x=>x!==id).map(x=>cmpColors[x]);cmpColors[id]=[0,1,2,3,4,5].find(c=>!used.includes(c))??0}}store.set('cmp-colors',cmpColors)}
function activeInYear(f,y){return y>=f.entry_year&&(!f.exit_year||y<=f.exit_year)}
function renderCompare(){S.cmp=[...new Set(Array.isArray(S.cmp)?S.cmp:[])].filter(id=>firm(id)).slice(0,6);assignCompareColors();
 const save=()=>{store.set('cmp',S.cmp);renderCompare()};
 const q=$('#cp-search').value.toLowerCase().trim();
 $('#cp-limit').textContent=S.cmp.length===6?'6 von 6 gewählt. Entferne eine Firma, um eine andere zu wählen.':S.cmp.length+' von höchstens 6 Firmen gewählt.';
 $('#cp-firms').innerHTML=STAGES.map(st=>`<h3>${STAGE[st]}</h3>`+Object.values(D.firms).filter(f=>f.stage===st&&(!q||(f.name+' '+f.id).toLowerCase().includes(q))).map(f=>`<label class="firm-choice"><input type="checkbox" data-id="${esc(f.id)}" ${S.cmp.includes(f.id)?'checked':S.cmp.length>=6?'disabled':''}>${S.cmp.includes(f.id)?`<span class="dot" style="background:${pal()[cmpColors[f.id]]}"></span>`:''}${esc(f.name)}</label>`).join('')).join('');
 $$('#cp-firms input').forEach(c=>c.onchange=()=>{S.cmp=c.checked?[...S.cmp,c.dataset.id]:S.cmp.filter(id=>id!==c.dataset.id);save()});
 $('#cp-search').oninput=renderCompare;
 $('#cp-top').onclick=()=>{S.cmp=Object.keys(D.firms).sort((a,b)=>firmProfit(b)-firmProfit(a)).slice(0,5);save()};
 $('#cp-clear').onclick=()=>{S.cmp=[];save()};
 const key=S.cmpMetric||'profit',relative=!!S.cmpRelative;
 $('#cp-metrics').innerHTML=CMP_METRICS.map(([k,t])=>`<button class="chip" data-metric="${k}" aria-pressed="${k===key}">${t}</button>`).join('');
 $$('#cp-metrics button').forEach(b=>b.onclick=()=>{S.cmpMetric=b.dataset.metric;renderCompare()});
 $('#cp-relative').checked=relative;$('#cp-relative').onchange=e=>{S.cmpRelative=e.target.checked;renderCompare()};
 destroy();const root=$('#cp-charts');if(!S.cmp.length){root.innerHTML=empty('Wähle links bis zu sechs Firmen oder nutze «Top 5 nach Gewinn».');return}
 const [,title,fmt]=CMP_METRICS.find(x=>x[0]===key),labels=years.filter(inRange),format=v=>fmt==='chf'?chf(v):fmt==='pct'?pct(v):nf(v,2);
 const value=(id,y)=>{const f=firm(id);if(!activeInYear(f,y))return null;const v=f.yearly.find(r=>r.year===y)?.[key];if(v==null)return null;if(!relative)return v;
  const peers=Object.values(D.firms).filter(p=>p.stage===f.stage&&activeInYear(p,y)).map(p=>p.yearly.find(r=>r.year===y)?.[key]).filter(v=>v!=null);return peers.length?v-peers.reduce((a,b)=>a+b,0)/peers.length:null};
 root.innerHTML=`<div class="card"><h3>${title}${relative?' relativ zum Stufenschnitt':''}</h3><div class="chart" style="height:400px"><canvas id="cp-metric"></canvas></div></div><div class="table-wrap"><table id="cp-summary"></table></div>`;
 chart('cp-metric',{type:'line',data:{labels,datasets:S.cmp.map(id=>({label:fname(id),data:labels.map(y=>value(id,y)),borderColor:pal()[cmpColors[id]],pointRadius:0,borderWidth:2,spanGaps:false}))},options:{scales:{y:fmtAxis(fmt)}}});
 const stats=S.cmp.map(id=>{const pairs=labels.map(y=>[y,value(id,y)]).filter(p=>p[1]!=null),v=pairs.map(p=>p[1]);return{id,pairs,values:v.length?[value(id,labels.at(-1)),v.reduce((a,b)=>a+b,0)/v.length,Math.max(...v),Math.min(...v)]:[null,null,null,null]}});
 const best=[0,1,2,3].map(i=>Math.max(...stats.map(r=>r.values[i]).filter(v=>v!=null)));
 $('#cp-summary').innerHTML='<thead><tr><th>Firma</th><th>Letztes Jahr</th><th>Durchschnitt</th><th>Bestes Jahr</th><th>Schlechtestes Jahr</th></tr></thead><tbody>'+stats.map(r=>`<tr><td><span class="dot" style="background:${pal()[cmpColors[r.id]]}"></span>${esc(fname(r.id))}</td>${r.values.map((v,i)=>`<td class="num ${v!=null&&v===best[i]?'best':''}">${v!=null&&v===best[i]?'<strong>':''}${format(v)}${i>=2&&v!=null?' (Jahr '+r.pairs.find(p=>p[1]===v)[0]+')':''}${v!=null&&v===best[i]?'</strong>':''}</td>`).join('')}</tr>`).join('')+'</tbody>'}

function ledgerHtml(id){const rows=(D.offence_ledger||[]).filter(r=>inRange(r.year)&&(!id||r.firm===id));
 return `<div class="card"><h3>Hat es sich gelohnt?</h3><div class="kpis">${kpi('lohnend:',nf(rows.filter(r=>r.paid_off).length)+' von '+nf(rows.length))}</div><p class="hint">Schaden ist eine Schätzung aus Reputationsverlust und Vorjahresumsatz.</p>${rows.length?`<div class="table-wrap"><table><thead><tr><th>Firma</th><th>Straftat</th><th>Jahr</th><th>Gewinn</th><th>Busse</th><th>Schaden</th><th>Netto</th><th>Urteil</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(fname(r.firm))}</td><td>${esc(({lohndumping:'Lohndumping',pfusch:'Pfusch bei Rohstoffen',steuerhinterziehung:'Steuerhinterziehung'})[r.offence]||r.offence)}</td><td>${r.year}</td>${['gain','fine','damage','net'].map(k=>`<td class="num">${chf(r[k])}</td>`).join('')}<td><span class="badge ${r.paid_off?'ok':'off'}">${r.paid_off?'lohnend':'nicht lohnend'}</span></td></tr>`).join('')}</tbody></table></div>`:empty('Keine Straftaten im Zeitraum.')}</div>`}

function renderStructure(){$('#ms-legend').innerHTML=['factory','distributor','wholesaler','retailer'].map(st=>`<span class="dot" style="background:${stageColor()[st]}"></span>${STAGE[st]}`).join(' · ')+' · Austritte: × Konkurs · ◆ Übernahme · ▲ Vergiftung';const brands=new Map();for(const r of D.brands||[]){if(r.year>range.to)continue;const old=brands.get(r.brand);brands.set(r.brand,{...r,first:old?Math.min(old.first,r.year):r.year})}
 $('#ms-brands').innerHTML=Object.entries(CAT).map(([cat,name])=>`<details><summary>${name}</summary><ul class="list">${[...brands.values()].filter(b=>b.category===cat).map(b=>`<li><b>${esc(b.name)}</b> · ${esc(fname(b.owner))} · seit Jahr ${b.first} · ${esc(({cheap:'Discount',standard:'Standard',premium:'Premium'})[b.positioning]||b.positioning)} · ${esc((b.traits||[]).map(t=>({wine:'Wein',spirits:'Spirituosen',lager:'Lager',craft:'Craft',discount:'Discount',import:'Import',alkoholfrei:'Alkoholfrei'})[t]||t).join(', '))}</li>`).join('')||'<li>Keine Marken vorhanden.</li>'}</ul></details>`).join('');
 const groups=[...Object.keys(CAT).map(c=>['Hersteller · '+CAT[c],f=>f.stage==='factory'&&!f.importer&&f.category===c]),['Hersteller · Import',f=>f.stage==='factory'&&f.importer],...['distributor','wholesaler','retailer'].map(st=>[STAGE[st],f=>f.stage===st])];
 const x=y=>290+(y-range.from)*650/Math.max(1,range.to-range.from+1),end=y=>x(y+1);let top=35,svg='';
 for(const y of years.filter(inRange).filter((y,i)=>i%Math.max(1,Math.ceil((range.to-range.from+1)/15))===0))svg+=`<text x="${x(y)}" y="18" font-size="12">${y}</text>`;
 for(const [title,predicate] of groups){svg+=`<text x="10" y="${top}" font-weight="bold">${title}</text>`;top+=25;
  for(const f of Object.values(D.firms).filter(predicate).filter(f=>f.entry_year<=range.to&&(!f.exit_year||f.exit_year>=range.from))){const start=Math.max(range.from,f.entry_year),last=Math.min(range.to,f.exit_year||D.meta.years),exit=D.events.find(e=>e.firm===f.id&&['bankruptcy','takeover','poisoning'].includes(e.event)),marker={bankruptcy:'×',takeover:'◆',poisoning:'▲'}[exit?.event]||'';
   svg+=`<g data-firm="${esc(f.id)}" role="button" aria-label="${esc(f.name)}: Jahr ${f.entry_year} bis ${f.exit_year||D.meta.years}"><title>${esc(f.name)} · ${esc(ARCH[f.archetype]||f.archetype)} · Jahr ${f.entry_year}–${f.exit_year||D.meta.years}${exit?' · '+EVENT[exit.event]:''}</title><text x="10" y="${top+14}" font-size="12">${esc(f.name)}</text><rect x="${x(start)}" y="${top}" width="${Math.max(3,end(last)-x(start)-3)}" height="20" rx="3" fill="${stageColor()[f.stage]}"/>${f.exit_year&&inRange(f.exit_year)?`<text x="${end(last)-12}" y="${top+16}" font-size="18">${marker}</text>`:''}</g>`;top+=28}
  top+=16}
 $('#ms-timeline').innerHTML=`<svg viewBox="0 0 970 ${top}" aria-label="Firmen nach Stufe und Lebensdauer">${svg}</svg>`;wireFirmLinks($('#ms-timeline'))}

// --- Lieferkette, Finanzen, Staat, F&E ----------------------------------
function renderChain(){lines('ch-margin',byStage('margin_'),{fmt:'pct'});lines('ch-util',byStage('utilization_'),{fmt:'pct'});
 lines('ch-lost',[{label:'Verlorene Verkäufe',get:x=>x.total_lost_sales,color:css('--bad')}]);lines('ch-bull',[{label:'Bullwhip',get:x=>x.bullwhip_ratio}]);
 lines('ch-transport',[{label:'Transportkosten',get:x=>x.transport_cost,fmt:'chf'},{label:'Treibstoffindex',get:x=>x.fuel_index,axis:'y2'}],{fmt:'chf'});
 lines('ch-service',[{label:'Firmen mit Transportdienst',get:x=>x.firms_using_service},{label:'Schäden (Einheiten)',get:x=>x.damaged_units,axis:'y2'}]);
 const s=sys();chart('ch-build',{type:'bar',data:{labels:s.map(x=>x.year),datasets:[{label:'Ausbauten',data:s.map(x=>x.expansions),backgroundColor:pal()[0]+'bb'},{label:'Neue Standorte',data:s.map(x=>x.new_sites),backgroundColor:pal()[2]+'bb'}]},options:{scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true}}}})}
function renderHoldings(){lines('fi-stakes',[{label:'Gehaltene Beteiligungen',get:x=>x.stakes_held},{label:'Dividenden',get:x=>x.dividends,axis:'y2',fmt:'chf'}]);
 const end=(D.holdings||[]).filter(h=>h.action==null&&h.year===Math.max(...(D.holdings||[]).filter(x=>x.action==null).map(x=>x.year),0));
 $('#fi-holdings').innerHTML='<thead><tr><th>Eigentümer</th><th>Beteiligung an</th><th class="num">Anteil</th><th class="num">Dividenden</th></tr></thead><tbody>'+(end.length?end.sort((a,b)=>b.share-a.share).map(h=>`<tr class="click" data-firm="${esc(h.owner)}"><td>${esc(fname(h.owner))}</td><td>${esc(fname(h.target))}</td><td class="num">${pct(h.share)}</td><td class="num">${chf(h.dividends)}</td></tr>`).join(''):`<tr><td colspan="4">${empty('Am Ende des Laufs hält keine Firma Anteile an einer anderen.')}</td></tr>`)+'</tbody>';wireFirmLinks($('#fi-holdings'))}
function renderFinance(){renderHoldings();lines('fi-labor',[{label:'Offene Stellen',get:x=>x.open_positions},{label:'Abgeworben',get:x=>x.poached_workers},{label:'Lohnniveau',get:x=>x.wage_index_mean,axis:'y2'}]);lines('fi-negative',byStage('negative_interest_','chf'),{fmt:'chf'});lines('fi-debt',byStage('debt_','chf'),{fmt:'chf'});lines('fi-interest',byStage('interest_cost_','chf'),{fmt:'chf'});
 const s=sys(),restr=y=>D.events.filter(e=>e.year===y&&e.event==='restructuring').length;
 chart('fi-churn',{type:'bar',data:{labels:s.map(x=>x.year),datasets:[{label:'Eintritte',data:s.map(x=>x.market_entries),backgroundColor:pal()[0]+'bb'},{label:'Konkurse',data:s.map(x=>x.bankruptcies),backgroundColor:css('--bad')+'bb'},{label:'Sanierungen',data:s.map(x=>restr(x.year)),backgroundColor:pal()[3]+'bb'},{type:'line',label:'Strategiewechsel',data:s.map(x=>x.strategy_changes),borderColor:pal()[4],pointRadius:0}]},options:{scales:{x:{grid:{display:false}}}}});
 lines('fi-hhi',[{label:'HHI',get:x=>x.market_concentration}])}
function renderLaws(){const laws=(D.laws||[]).filter(l=>l.year<=range.to);
 const badge=v=>v==='Folge erkennbar'?'<span class="badge ok">Folge erkennbar</span>':v==='keine klare Folge erkennbar'?'<span class="badge">keine klare Folge erkennbar</span>':'<span class="badge">Folgen noch unklar</span>';
 $('#st-laws').innerHTML='<thead><tr><th class="num">Jahr</th><th>Gesetz</th><th>Beurteilung</th><th>Was sich verändert hat</th></tr></thead><tbody>'+(laws.length?laws.map(l=>`<tr><td class="num">${l.year}</td><td>${esc(l.title_de)}</td><td>${badge(l.verdict)}<br><small>${l.years_observed} Jahre beobachtet</small></td><td>${l.findings.length?l.findings.map(f=>`${esc(f.label_de)}: ${['offences','offences_detected'].includes(f.metric)?nf(f.before,1)+' → '+nf(f.after,1):pct(f.before)+' → '+pct(f.after)}`).join('<br>'):'—'}</td></tr>`).join(''):`<tr><td colspan="4">${empty('Bis zu diesem Jahr wurde kein neues Gesetz erlassen.')}</td></tr>`)+'</tbody>'}
function renderState(){renderLaws();$('#st-ledger').innerHTML=ledgerHtml();const s=sys();$('#st-kpis').innerHTML=[kpi('Steuern',chf(sumBy(s,'taxes')),'im Zeitraum'),kpi('Straftaten',nf(sumBy(s,'offences')),nf(sumBy(s,'offences_detected'))+' entdeckt'),kpi('Bussen',chf(sumBy(s,'fines'))),kpi('Vergiftungen',nf(sumBy(s,'poisonings'))),kpi('Übernahmen',nf(sumBy(s,'takeovers')),nf(sumBy(s,'takeovers_blocked'))+' verboten'),kpi('Zerschlagungen',nf(sumBy(s,'breakups')))].join('');
 chart('st-off',{type:'bar',data:{labels:s.map(x=>x.year),datasets:[{label:'Begangen',data:s.map(x=>x.offences),backgroundColor:pal()[3]+'99'},{label:'Entdeckt',data:s.map(x=>x.offences_detected),backgroundColor:css('--bad')+'cc'}]},options:{scales:{x:{grid:{display:false}}}}});
 lines('st-money',[{label:'Steuern',get:x=>x.taxes},{label:'Bussen',get:x=>x.fines}],{fmt:'chf'});
 chart('st-fear',{type:'bar',data:{labels:s.map(x=>x.year),datasets:[{label:'Vergiftungen',data:s.map(x=>x.poisonings),backgroundColor:css('--bad')+'cc',yAxisID:'y'},{type:'line',label:'Angst (Nachfrageminus)',data:s.map(x=>x.fear),borderColor:pal()[4],pointRadius:0,yAxisID:'y2'}]},options:{scales:{x:{grid:{display:false}},y:{ticks:{precision:0}},y2:{position:'right',grid:{display:false},...fmtAxis('pct')}}}});
 chart('st-tko',{type:'bar',data:{labels:s.map(x=>x.year),datasets:[{label:'Übernahmen',data:s.map(x=>x.takeovers),backgroundColor:pal()[0]+'bb'},{label:'Verboten',data:s.map(x=>x.takeovers_blocked),backgroundColor:pal()[1]+'bb'},{label:'Zerschlagungen',data:s.map(x=>x.breakups),backgroundColor:pal()[4]+'bb'}]},options:{scales:{x:{grid:{display:false}}}}});
 const e=evs().filter(x=>['offence_detected','poisoning','takeover','breakup'].includes(x.event)).reverse();
 $('#st-table').innerHTML='<thead><tr><th>Jahr</th><th>Art</th><th>Firma</th><th>Details</th></tr></thead><tbody>'+(e.length?e.map(x=>`<tr class="click" data-firm="${esc(x.firm)}"><td>${x.year}</td><td>${esc(EVENT[x.event])}</td><td>${esc(fname(x.firm))}</td><td>${esc(pretty(x.details))}</td></tr>`).join(''):`<tr><td colspan="4">${empty('Keine Urteile oder Eingriffe im Zeitraum.')}</td></tr>`)+'</tbody>';wireFirmLinks($('#st-table'))}
function renderRnd(){const s=sys(),r=(D.rnd||[]).filter(x=>inRange(x.end_year));const ok=r.filter(x=>x.success).length;
 $('#rd-kpis').innerHTML=[kpi('Projekte gestartet',nf(sumBy(s,'rnd_started'))),kpi('Abgeschlossen',nf(r.length),r.length?pct(ok/r.length)+' erfolgreich':''),kpi('Ausgaben',chf(sumBy(s,'rnd_project_spend'))),kpi('Neue Marken',nf(r.filter(x=>x.success&&/^(new brand|neue Marke)/.test(String(x.result))).length))].join('');
 chart('rd-count',{type:'bar',data:{labels:s.map(x=>x.year),datasets:[{label:'Erfolg',data:s.map(x=>x.rnd_successes),backgroundColor:css('--good')+'bb'},{label:'Fehlschlag',data:s.map(x=>x.rnd_failures),backgroundColor:css('--bad')+'bb'},{type:'line',label:'Gestartet',data:s.map(x=>x.rnd_started),borderColor:pal()[2],pointRadius:0}]},options:{scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true}}}});
 lines('rd-spend',[{label:'Ausgaben',get:x=>x.rnd_project_spend}],{fmt:'chf'});
 const P={leichtere_flaschen:'Leichtere Flaschen',waermerueckgewinnung:'Wärmerückgewinnung',ausbeute_optimierung:'Ausbeute-Optimierung',routenplanung:'Routenplanung',lagerautomation:'Lagerautomation',robotik:'Robotik',prozessautomation:'Prozessautomation',rezeptur_optimierung:'Rezeptur-Optimierung',neue_marke:'Neue Marke',alkoholfreies_bier:'Alkoholfreies Bier'};
 $('#rd-table').innerHTML='<thead><tr><th>Firma</th><th>Projekt</th><th class="num">Start</th><th class="num">Ende</th><th class="num">Kosten</th><th>Ergebnis</th></tr></thead><tbody>'+(r.length?r.slice().reverse().map(x=>`<tr class="click" data-firm="${esc(x.firm)}"><td>${esc(fname(x.firm))}</td><td>${esc(P[x.project]||x.project)}</td><td class="num">${x.start_year}</td><td class="num">${x.end_year}</td><td class="num">${chf(x.cost)}</td><td>${x.success?'<span class="badge ok">'+esc(pretty(x.result))+'</span>':'<span class="badge off">kein Ergebnis</span>'}</td></tr>`).join(''):`<tr><td colspan="6">${empty('Im Zeitraum wurde kein Projekt abgeschlossen.')}</td></tr>`)+'</tbody>';wireFirmLinks($('#rd-table'))}

// --- Ereignisse ----------------------------------------------------------
function renderEvents(){const all=evs();const counts={};all.forEach(e=>counts[e.event]=(counts[e.event]||0)+1);
 if(S.evTypes==null)S.evTypes=new Set(Object.keys(counts).filter(k=>k!=='inflation'));
 const types=Object.keys(counts).sort((a,b)=>counts[b]-counts[a]);
 $('#ev-types').innerHTML=types.map(t=>`<button class="chip" data-t="${t}" aria-pressed="${S.evTypes.has(t)}">${esc(EVENT[t]||t)} <span class="badge">${counts[t]}</span></button>`).join('');
 $$('#ev-types .chip').forEach(c=>c.onclick=()=>{const t=c.dataset.t;S.evTypes.has(t)?S.evTypes.delete(t):S.evTypes.add(t);S.evLimit=200;renderEvents()});
 $('#ev-all').onclick=()=>{S.evTypes=new Set(types);renderEvents()};$('#ev-none').onclick=()=>{S.evTypes=new Set();renderEvents()};
 const q=$('#ev-search').value.trim().toLowerCase();
 const rows=all.filter(e=>S.evTypes.has(e.event)&&(!q||fname(e.firm).toLowerCase().includes(q)||String(e.details).toLowerCase().includes(q))).reverse();
 $('#ev-table').innerHTML='<thead><tr><th class="num">Jahr</th><th class="num">Tag</th><th>Art</th><th>Firma</th><th>Details</th></tr></thead><tbody>'+(rows.length?rows.slice(0,S.evLimit).map(e=>`<tr${e.firm?` class="click" data-firm="${esc(e.firm)}"`:''}><td class="num">${e.year}</td><td class="num">${e.day}</td><td>${esc(EVENT[e.event]||e.event)}</td><td>${esc(e.firm?fname(e.firm):'Markt')}</td><td>${esc(pretty(e.details))}</td></tr>`).join(''):`<tr><td colspan="5">${empty('Keine Ereignisse für diese Auswahl. Wähle mehr Arten oder ändere die Suche.')}</td></tr>`)+'</tbody>';
 $('#ev-more').hidden=rows.length<=S.evLimit;$('#ev-more').textContent=`Weitere anzeigen (${nf(rows.length-S.evLimit)} übrig)`;$('#ev-more').onclick=()=>{S.evLimit+=200;renderEvents()};wireFirmLinks($('#ev-table'))}
$('#ev-search').oninput=()=>{S.evLimit=200;renderEvents()};$('#fm-search').oninput=()=>renderFirms();

// --- render --------------------------------------------------------------
// Schematic Switzerland: a rough outline in Swiss grid km, split into Voronoi cells around the region centres.
const CH_OUTLINE=[[485,118],[497,128],[506,136],[520,153],[537,168],[553,187],[565,203],[575,220],[570,240],[590,252],[606,262],[612,268],[625,270],[640,272],[660,276],[680,283],[700,287],[720,280],[735,276],[750,270],[760,264],[770,250],[780,240],[790,230],[800,224],[815,220],[830,210],[834,195],[825,180],[815,170],[812,155],[800,145],[790,140],[775,140],[760,130],[745,118],[730,112],[722,100],[718,80],[705,77],[700,90],[690,105],[670,115],[650,112],[630,100],[610,92],[590,90],[570,96],[555,105],[540,112],[525,115],[510,113],[495,112]];
function clipHalf(poly,a,b){const out=[],mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2,nx=b[0]-a[0],ny=b[1]-a[1],side=p=>(p[0]-mx)*nx+(p[1]-my)*ny;
 for(let i=0;i<poly.length;i++){const p=poly[i],q=poly[(i+1)%poly.length],sp=side(p),sq=side(q);if(sp<=0)out.push(p);if((sp<0)!==(sq<0)){const t=sp/(sp-sq);out.push([p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])])}}return out}
function regionCells(){const regs=D.regions||[];return Object.fromEntries(regs.map(r=>{let poly=CH_OUTLINE;for(const o of regs)if(o!==r)poly=clipHalf(poly,[r.x,r.y],[o.x,o.y]);return[r.name,poly]}))}
const MAP_LAYERS={population:'Bevölkerung',firms:'Firmen',capacity:'Händler pro Kopf',margin:'Händlermarge',revenue:'Umsatz pro Region',wage:'Lohnniveau',labor:'Arbeitsmarkt'};
S.mapLayer='population';
function renderMap(){const regs=D.regions||[];const root=$('#map-svg');
 $('#map-layers').innerHTML=Object.entries(MAP_LAYERS).map(([k,l])=>`<button class="chip" data-l="${k}" aria-pressed="${S.mapLayer===k}">${l}</button>`).join('');
 $$('#map-layers .chip').forEach(c=>c.onclick=()=>{S.mapLayer=c.dataset.l;renderMap()});
 if(!regs.length){root.innerHTML=empty('Dieser Lauf hat keine Regionen.');return}
 const year=range.to,rows=Object.fromEntries((D.region_reports||[]).filter(r=>r.year===year).map(r=>[r.region,r]));
 const val={population:r=>r?.population_share,firms:r=>r?.population_share,capacity:r=>r&&r.population?r.retail_capacity/r.population*1e6:null,margin:r=>r?.mean_retail_margin,revenue:r=>r?.consumer_revenue,wage:r=>r?.wage_index,labor:r=>r?.labor_tightness}[S.mapLayer];
 const fmt={population:pct,firms:pct,capacity:v=>nf(v,1)+' pro Mio.',margin:pct,revenue:chf,wage:v=>v==null?'—':'Index '+nf(v,2),labor:v=>v==null?'—':pct(v)+' belegt'}[S.mapLayer];
 const vals=regs.map(r=>val(rows[r.name])).filter(v=>v!=null&&isFinite(v));const lo=Math.min(...vals,0),hi=Math.max(...vals,1e-9);
 const shade=v=>v==null?css('--soft'):S.mapLayer==='margin'&&v<0?css('--bad'):css('--brand');
 const alpha=v=>v==null?1:0.15+0.75*Math.abs((v-(S.mapLayer==='margin'?0:lo))/((S.mapLayer==='margin'?Math.max(Math.abs(lo),Math.abs(hi)):hi-lo)||1));
 const cells=regionCells(),Y=y=>300-y,pts=p=>p.map(q=>`${q[0].toFixed(1)},${Y(q[1]).toFixed(1)}`).join(' ');
 let svg=`<svg viewBox="475 5 370 230" role="img" aria-label="Schematische Karte der Schweiz, Ebene ${MAP_LAYERS[S.mapLayer]}" style="width:100%;height:auto">`;
 for(const r of regs){const v=val(rows[r.name]);svg+=`<polygon points="${pts(cells[r.name])}" fill="${shade(v)}" fill-opacity="${S.mapLayer==='firms'?0.12:alpha(v).toFixed(2)}" stroke="${css('--panel')}" stroke-width="1.5" tabindex="0"><title>${esc(REGION[r.name]||r.name)}: ${fmt(v)}</title></polygon>`}
 if(S.mapLayer==='firms'){const loc=(D.firm_locations||[]).filter(l=>l.year===year);const offs={factory:[-7,-6],distributor:[7,-6],wholesaler:[-7,6],retailer:[7,6]};
  for(const r of regs)for(const st of STAGES){const here=loc.filter(l=>l.region===r.name&&l.stage===st);if(!here.length)continue;const cap=here.reduce((a,l)=>a+l.capacity,0);const [dx,dy]=offs[st];
   svg+=`<circle cx="${r.x+dx}" cy="${Y(r.y)+dy}" r="${(2+Math.sqrt(cap)/2.2).toFixed(1)}" fill="${stageColor()[st]}" fill-opacity=".85"><title>${STAGE[st]} in ${esc(REGION[r.name])}: ${here.length} Firmen, Kapazität ${nf(cap)}</title></circle>`}}
 for(const r of regs)svg+=`<text x="${r.x}" y="${Y(r.y)-12}" text-anchor="middle" font-size="7.5" fill="${css('--ink')}" style="pointer-events:none">${esc(REGION[r.name]||r.name)}</text>`;
 root.innerHTML=svg+'</svg>';
 $('#map-legend').innerHTML=S.mapLayer==='firms'?STAGES.map(st=>`<span class="dot" style="background:${stageColor()[st]}"></span>${STAGE[st]}`).join(' · ')+' · Kreisgrösse = Kapazität · schematische Karte':`Hell = tief, dunkel = hoch${S.mapLayer==='margin'?' · rot = negative Marge':''} · Jahr ${year} · schematische Karte`;
 $('#map-title').textContent=`${MAP_LAYERS[S.mapLayer]} · Jahr ${year}`;
 $('#map-table').innerHTML='<thead><tr><th>Region</th><th class="num">Bevölkerung</th><th class="num">Händler</th><th class="num">Umsatz</th><th class="num">Marge Händler</th></tr></thead><tbody>'+regs.map(r=>{const x=rows[r.name]||{};return`<tr><td>${esc(REGION[r.name]||r.name)}</td><td class="num">${pct(x.population_share)}</td><td class="num">${nf(x.retailers)}</td><td class="num">${chf(x.consumer_revenue)}</td><td class="num">${pct(x.mean_retail_margin)}</td></tr>`}).join('')+'</tbody>'}
const HABIT={light:'gelegentlich',regular:'regelmässig'};
S.ppClass=null;
function renderPeople(){const rows=(D.classes||[]).filter(r=>r.year<=range.to);if(!rows.length){$('#pp-grid').innerHTML=`<tr><td>${empty('Keine Kundenklassen in diesem Lauf.')}</td></tr>`;return}
 const year=Math.max(...rows.map(r=>r.year)),cur=Object.fromEntries(rows.filter(r=>r.year===year).map(r=>[r.consumer_class,r]));
 const ages=['18-34','35-64','65+'],habits=['light','regular'];
 const cell=(i,a,h)=>{const r=cur[`income_${i}_${a}_${h}`];if(!r)return'<td>—</td>';const fav=Object.entries(r.category_shares||{}).sort((x,y)=>y[1]-x[1])[0];const sel=S.ppClass===r.consumer_class;
  return`<td class="click" data-c="${esc(r.consumer_class)}" tabindex="0" style="cursor:pointer;${sel?'outline:2px solid var(--brand);':''}background:${css('--brand')}${Math.round(40+150*(r.purchase_rate||0)).toString(16).padStart(2,'0')}"><b>${nf((r.persons||0)/1000)}k</b><br><small>${pct(r.purchase_rate)} · ${fav?esc(CAT[fav[0]]||fav[0]):''}</small></td>`};
 $('#pp-grid').innerHTML=`<thead><tr><th>Einkommen</th>${ages.map(a=>habits.map(h=>`<th>${a} J., ${HABIT[h]}</th>`).join('')).join('')}</tr></thead><tbody>${[1,2,3,4,5].map(i=>`<tr><td class="lbl">Stufe ${i}${i===1?' (tief)':i===5?' (hoch)':''}</td>${ages.map(a=>habits.map(h=>cell(i,a,h)).join('')).join('')}</tr>`).join('')}</tbody>`;
 $$('#pp-grid td[data-c]').forEach(td=>{const go=()=>{S.ppClass=td.dataset.c;renderPeople();$('#pp-detail').scrollIntoView({block:'nearest'})};td.onclick=go;td.onkeydown=e=>{if(e.key==='Enter')go()}});
 const det=$('#pp-detail');if(!S.ppClass||!cur[S.ppClass]){det.innerHTML=empty('Wähle oben eine Klasse, um ihre Personas zu sehen.');return}
 const r=cur[S.ppClass],ps=(D.personas||[]).filter(p=>p.consumer_class===S.ppClass);
 const shares=Object.entries(r.category_shares||{}).map(([c,v])=>`${CAT[c]||c} ${pct(v)}`).join(' · ');
 det.innerHTML=`<div class="card"><h3>Klasse: Einkommen ${r.income_level}, ${esc(r.age_group)} Jahre, trinkt ${HABIT[r.drinking_habit]||r.drinking_habit}</h3>
 <div class="kpis">${kpi('Personen',nf(r.persons))}${kpi('Einheiten pro Person und Jahr',nf(r.units_per_person,0))}${kpi('Höchstpreis',nf(r.max_price,2)+' CHF')}${kpi('Gekauft',pct(r.purchase_rate))}${kpi('Bezahlter Preis',nf(r.avg_price_paid,2)+' CHF')}</div><p class="hint">Kategorien: ${esc(shares)}</p>
 <div class="grid">${ps.map(p=>`<div class="card"><div style="display:flex;gap:12px;align-items:center"><div aria-hidden="true" style="width:48px;height:48px;border-radius:50%;background:${p.gender==='woman'?pal()[6]:pal()[2]};color:#fff;display:grid;place-items:center;font-weight:700">${esc(p.first_name[0]+p.surname[0])}</div><div><b>${esc(p.first_name)} ${esc(p.surname)}</b>, ${p.age}<br><small>${esc(p.job)} · ${esc(REGION[p.region]||p.region||'')}</small></div></div>
 <p style="margin:10px 0 4px">«${esc(p.priority_de)}»</p><p class="hint">Einkommen ${nf(p.monthly_income_range[0])}–${nf(p.monthly_income_range[1])} CHF pro Monat · trinkt ${HABIT[p.drinking_habit]||p.drinking_habit} · kauft oft ${esc(pretty(p.typical_brand))}</p></div>`).join('')}</div></div>`}
function renderChronicle(){const c=(D.texts||{}).chronicle||{};const yrs=Object.keys(c).map(Number).filter(inRange).sort((a,b)=>b-a);
 $('#ch-list').innerHTML=yrs.length?yrs.map(y=>`<div class="card" style="margin-bottom:12px"><h3>Jahr ${y} ${c[y].checked?'<span class="badge ok">Zahlen geprüft</span>':'<span class="badge">Kurzfassung aus den Fakten</span>'}</h3><p style="margin:0">${esc(pretty(c[y].text))}</p></div>`).join(''):empty('Noch keine Chronik. Erzeuge sie mit: python -m market_sim.dashboard --texts (dauert je nach Rechner eine halbe Stunde oder länger).')}
// Money flow of one firm in one year as a circular flow: the firm in the middle, its partners around it.
const FLOW_REASON={Gewinnsteuer:'Gewinnsteuer auf den Jahresgewinn',Alkoholsteuer:'Alkoholsteuer, steckt im Rohstoffpreis',Zoll:'Zoll auf importierte Ware',Schuldenschnitt:'Die Bank erlässt Schulden, damit die letzte Firma der Stufe bleibt'};
const FLOW_CF={dividende_an:'Anteil am Gewinn für Beteiligte',dividende_von:'Anteil am Gewinn einer Beteiligung',kapital_von:'neues Eigenkapital',beteiligung:'Kauf eines Anteils',beteiligung_verkauft:'Verkauf eines Anteils',uebernahme:'Kaufpreis samt übernommenen Schulden',uebernommen:'Kasse geht an den Käufer'};
const flowName=k=>{const [g,r]=k.split(':');if(k==='rohstoffe')return'Rohstoffe & Produktion';if(r===undefined)return D.firms[k]?fname(k):k;if(g==='staat')return r.startsWith('Busse')?'Busse: '+(OFFENCE[r.slice(6)]||r.slice(6)):r;
 return({uebernahme:'Übernahme von ',uebernommen:'Kasse an ',dividende_an:'Dividende an ',dividende_von:'Dividende von ',beteiligung:'Beteiligung an ',beteiligung_verkauft:'Beteiligung verkauft: ',kapital_von:'Kapital von ',bank:''}[g]??'')+(D.firms[r]?fname(r):r)};
// Partners around the firm: position in the picture, colour and the arrow labels.
const FLOW_NODES=[
 {k:'kunden',label:'Kunden',x:120,y:300,c:3,lin:'Umsatz'},
 {k:'lieferanten',label:'Lieferanten',x:840,y:300,c:6,lout:'Einkauf'},
 {k:'staat',label:'Staat',x:480,y:62,c:4,lout:'Steuern, Zoll, Bussen'},
 {k:'beteiligungen',label:'Beteiligungen',x:180,y:92,c:5,lin:'Dividenden, Kapital',lout:'Dividenden, Käufe'},
 {k:'forschung',label:'Forschung',x:780,y:92,c:8,lout:'F&E'},
 {k:'personal',label:'Mitarbeitende',x:180,y:508,c:1,lout:'Löhne'},
 {k:'bank',label:'Bank',x:480,y:540,c:7,lin:'Schuldenschnitt',lout:'Zinsen'},
 {k:'betrieb',label:'Betrieb & Logistik',x:780,y:508,c:2,lout:'Fixkosten, Transport, Lager'}];
function flowGroups(id,year){const r=firm(id).yearly.find(x=>x.year===year)||{},paid=r.paid_to||{},cf=r.cash_flows||{};
 const G=Object.fromEntries(FLOW_NODES.map(n=>[n.k,{in:[],out:[]}]));
 const put=(g,dir,n,v,info,firmId)=>{if(v>0.5)G[g][dir].push({n,v,info,firm:firmId||null})};
 put('kunden','in','Umsatz',r.revenue,'Verkäufe an Kunden');
 for(const [k,v] of Object.entries(paid))k.startsWith('staat:')?put('staat','out',flowName(k),v,FLOW_REASON[k.slice(6)]||''):put('lieferanten','out',flowName(k),v,D.firms[k]?stageLabel(firm(k)):'eigene Produktion',D.firms[k]?k:null);
 put('lieferanten','out','Ohne Zuordnung',(r.purchase_cost||0)-Object.values(paid).reduce((a,v)=>a+v,0),'Lauf ohne Empfängerdaten');
 put('personal','out','Löhne',r.wage_cost,'');put('personal','out','Einstellung',r.hiring_cost,'Kosten für neue Mitarbeitende');
 put('betrieb','out','Fixkosten',r.fixed_cost,'Miete, Maschinen, Abschreibungen');put('betrieb','out','Handling & Transport',r.handling_cost,'');
 put('betrieb','out','Lager',r.holding_cost,'');put('betrieb','out','Rückstand',r.backlog_cost,'Strafkosten für offene Aufträge');
 put('forschung','out','F&E',r.rnd_cost,'Forschungsprojekte');put('bank','out','Zinsen',r.interest_cost,'');
 for(const [k,v] of Object.entries(cf)){const [g,other]=k.split(':'),grp=g==='staat'?'staat':g==='bank'?'bank':'beteiligungen';
  const info=g==='staat'?(FLOW_REASON[other]||(other.startsWith('Busse')?'Straftat wurde entdeckt':'')):g==='bank'?FLOW_REASON.Schuldenschnitt:FLOW_CF[g]||'';
  put(grp,v>0?'in':'out',flowName(k),Math.abs(v),info,D.firms[other]?other:null)}
 for(const g of Object.values(G)){g.in.sort((a,b)=>b.v-a.v);g.out.sort((a,b)=>b.v-a.v)}
 return G}
const sumV=a=>a.reduce((s,x)=>s+x.v,0);
function flowSvg(id,year,G,sel){const W=960,H=600,C={x:480,y:300,w:250,h:124},NW=176,NH=58;
 const tin=Object.values(G).reduce((a,g)=>a+sumV(g.in),0),tout=Object.values(G).reduce((a,g)=>a+sumV(g.out),0),net=tin-tout;
 const max=Math.max(1,...Object.values(G).flatMap(g=>[sumV(g.in),sumV(g.out)]));
 const edge=(b,tx,ty)=>{const dx=tx-b.x,dy=ty-b.y,s=Math.min(b.w/2/Math.abs(dx||1e-9),b.h/2/Math.abs(dy||1e-9));return[b.x+dx*s,b.y+dy*s]};
 const halo='paint-order:stroke;stroke:var(--panel);stroke-width:5px;stroke-linejoin:round';let arrows='',labels='',nodes='';
 for(const n of FLOW_NODES){const g=G[n.k],nb={x:n.x,y:n.y,w:NW,h:NH},both=g.in.length&&g.out.length;
  for(const [dir,items] of [['in',g.in],['out',g.out]]){if(!items.length)continue;const v=sumV(items),w=2+15*Math.sqrt(v/max);
   // Two arrows between the same pair bend to opposite sides.
   const off=both?(dir==='in'?-14:14):0,[ax,ay]=edge(C,n.x,n.y),[bx,by]=edge(nb,C.x,C.y),len=Math.hypot(bx-ax,by-ay),px=-(by-ay)/len,py=(bx-ax)/len;
   let [sx,sy,ex,ey]=dir==='out'?[ax,ay,bx,by]:[bx,by,ax,ay];sx+=px*off;sy+=py*off;ex+=px*off;ey+=py*off;
   const bend=(both?off*1.6:18),cx=(sx+ex)/2+px*bend,cy=(sy+ey)/2+py*bend,dl=Math.hypot(ex-cx,ey-cy),ux=(ex-cx)/dl,uy=(ey-cy)/dl,head=Math.max(11,w*1.5);
   const tx=ex-ux*head,ty=ey-uy*head,col=dir==='in'?'var(--good)':'var(--c2)';
   arrows+=`<path d="M${sx},${sy}Q${cx},${cy} ${tx},${ty}" fill="none" stroke="${col}" stroke-width="${w}" stroke-opacity=".85"><title>${esc(n.label)}: ${chf(v)}</title></path>`+
    `<polygon points="${ex},${ey} ${tx-uy*head*.6},${ty+ux*head*.6} ${tx+uy*head*.6},${ty-ux*head*.6}" fill="${col}"/>`;
   let nx=px,ny=py;if(ny>0||(Math.abs(ny)<1e-6&&nx<0)){nx=-nx;ny=-ny}
   // Labels sit beside the arrow, above it when the arrow runs sideways.
   const side=Math.abs(ny)>.5?w/2+22:0,mx=.25*sx+.5*cx+.25*tx+nx*side,my=.25*sy+.5*cy+.25*ty+ny*side,name=items.length===1?items[0].n:(dir==='in'?n.lin:n.lout)||n.label;
   labels+=`<text x="${mx}" y="${my-4}" text-anchor="middle" font-size="13" style="${halo}"><tspan font-weight="600">${esc(name)}</tspan><tspan x="${mx}" dy="16" fill="var(--muted)">${chf(v)}</tspan></text>`}
  const active=g.in.length||g.out.length,on=sel===n.k;
  nodes+=`<g class="flow-node${active?'':' off'}${on?' on':''}" data-k="${n.k}" ${active?`tabindex="0" role="button" aria-pressed="${on}" aria-label="${esc(n.label)} anzeigen"`:''}>`+
   `<rect x="${n.x-NW/2}" y="${n.y-NH/2}" width="${NW}" height="${NH}" rx="14" fill="var(--c${n.c})" fill-opacity="${on?.32:.14}" stroke="var(--c${n.c})" stroke-width="${on?3:2}"/>`+
   `<text x="${n.x}" y="${n.y-3}" text-anchor="middle" font-size="15" font-weight="700">${esc(n.label)}</text>`+
   `<text x="${n.x}" y="${n.y+16}" text-anchor="middle" font-size="12" fill="var(--muted)">${active?[g.in.length?'+'+chf(sumV(g.in)):'',g.out.length?'−'+chf(sumV(g.out)):''].filter(Boolean).join(' · '):'kein Geldfluss'}</text></g>`}
 const center=`<rect x="${C.x-C.w/2}" y="${C.y-C.h/2}" width="${C.w}" height="${C.h}" rx="16" fill="var(--panel)" stroke="currentColor" stroke-width="2.5"/>`+
  `<text x="${C.x}" y="${C.y-24}" text-anchor="middle" font-size="17" font-weight="700">${esc(firm(id).name.length>26?firm(id).name.slice(0,25)+'…':firm(id).name)}</text>`+
  `<text x="${C.x}" y="${C.y}" text-anchor="middle" font-size="13" fill="var(--muted)">rein ${chf(tin)} · raus ${chf(tout)}</text>`+
  `<text x="${C.x}" y="${C.y+28}" text-anchor="middle" font-size="15" font-weight="700" fill="${net>=0?'var(--good)':'var(--bad)'}">${net>=0?'Bleibt in der Kasse +':'Aus der Kasse −'}${chf(Math.abs(net))}</text>`;
 return`<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Geldfluss Jahr ${year}">${arrows}${center}${nodes}${labels}</svg>`}
function flowDetail(id,year,G,k){const box=$('#flow-detail');if(!k){box.innerHTML=`<p class="hint">Grün fliesst Geld zur Firma, orange fliesst es weg. Die Dicke zeigt den Betrag. Klicke auf einen Partner für die Einzelheiten, ‹ und › wechseln das Jahr.</p>`;return}
 const n=FLOW_NODES.find(x=>x.k===k),g=G[k],max=Math.max(...[...g.in,...g.out].map(x=>x.v));
 const rows=(items,dir)=>items.map(x=>`<div class="flow-row"><div><b>${x.firm?`<a href="#" data-go="${esc(x.firm)}">${esc(x.n)}</a>`:esc(x.n)}</b>${x.info?`<span class="hint"> · ${esc(x.info)}</span>`:''}</div>`+
  `<div class="flow-bar"><span style="width:${Math.max(1,x.v/max*100)}%;background:${dir==='in'?'var(--good)':'var(--c2)'}"></span></div><div class="num">${dir==='in'?'+':'−'}${chf(x.v)}</div></div>`).join('');
 box.innerHTML=`<h4>${esc(n.label)}</h4>${g.in.length?`<p class="hint">Fliesst zur Firma: ${chf(sumV(g.in))}</p>${rows(g.in,'in')}`:''}${g.out.length?`<p class="hint">Fliesst weg: ${chf(sumV(g.out))}</p>${rows(g.out,'out')}`:''}`;
 $$('#flow-detail [data-go]').forEach(a=>a.onclick=e=>{e.preventDefault();$('#flow').close();S.fmFirm=a.dataset.go;openTab('firms');renderFirms();$('#fm-detail').scrollIntoView({block:'start'})})}
function openFlow(id,year,sel=null){const dlg=$('#flow'),years=firm(id).yearly.map(r=>r.year).filter(inRange),G=flowGroups(id,year);
 $('#flow-title').textContent=`Geldfluss ${firm(id).name} – Jahr ${year}`;
 const i=years.indexOf(year);$('#flow-prev').disabled=i<=0;$('#flow-next').disabled=i<0||i>=years.length-1;
 $('#flow-prev').onclick=()=>openFlow(id,years[i-1],sel);$('#flow-next').onclick=()=>openFlow(id,years[i+1],sel);
 if(sel&&!(G[sel].in.length||G[sel].out.length))sel=null;
 $('#flow-body').innerHTML=flowSvg(id,year,G,sel);flowDetail(id,year,G,sel);
 $$('#flow-body .flow-node[tabindex]').forEach(el=>{const go=()=>openFlow(id,year,sel===el.dataset.k?null:el.dataset.k);el.onclick=go;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}}});
 dlg.onkeydown=e=>{if(e.key==='ArrowLeft'&&!$('#flow-prev').disabled)$('#flow-prev').click();if(e.key==='ArrowRight'&&!$('#flow-next').disabled)$('#flow-next').click()};
 $('#flow-close').onclick=()=>dlg.close();if(!dlg.open)dlg.showModal()}
$('#flow').addEventListener('click',e=>{if(e.target.id==='flow')e.target.close()});

// Chat with the local model through python -m market_sim.serve.
(function(){const box=$('#chat'),log=$('#chat-log'),input=$('#chat-input');
 const open=v=>{box.hidden=!v;box.style.display=v?'flex':'none';$('#chat-open').setAttribute('aria-expanded',v);if(v)input.focus()};
 $('#chat-open').onclick=()=>open(box.hidden);$('#chat-close').onclick=()=>open(false);
 box.addEventListener('keydown',e=>{if(e.key==='Escape')open(false)});
 const add=(who,html)=>{const d=document.createElement('div');d.style.cssText=who==='me'?'justify-self:end;background:var(--brand);color:var(--brand-ink);padding:8px 12px;border-radius:12px 12px 2px 12px;max-width:85%':'background:var(--soft);padding:8px 12px;border-radius:12px 12px 12px 2px;max-width:92%';d.innerHTML=html;log.appendChild(d);log.scrollTop=log.scrollHeight;return d};
 $('#chat-form').onsubmit=async e=>{e.preventDefault();const q=input.value.trim();if(!q)return;input.value='';add('me',esc(q));
  if(location.protocol==='file:'){add('bot','Der Chat braucht den lokalen Server. Starte im Projektordner <code>python -m market_sim.serve</code> und öffne dann <code>http://localhost:8770/dashboard.html</code>.');return}
  const wait=add('bot','<span class="hint">Das Modell denkt nach …</span>');$('#chat-send').disabled=true;
  try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});if(!r.ok)throw new Error(r.status);const a=await r.json();
   wait.innerHTML=esc(pretty(a.answer)).replace(/\n/g,'<br>')+(a.sources&&a.sources.length?`<div class="hint" style="margin-top:6px">Quellen: ${a.sources.map(esc).join(' · ')}</div>`:'')}
  catch(err){wait.innerHTML='Keine Antwort vom Chat-Server. Läuft <code>python -m market_sim.serve</code> und ist Ollama gestartet?'}
  finally{$('#chat-send').disabled=false;input.focus()}}})();
const VIEWS={chronicle:renderChronicle,map:renderMap,people:renderPeople,structure:renderStructure,overview:renderOverview,market:renderMarket,firms:renderFirms,compare:renderCompare,chain:renderChain,finance:renderFinance,state:renderState,rnd:renderRnd,events:renderEvents};
function render(){destroy();VIEWS[S.tab]()}
openTab(location.hash.slice(1)||'overview');
</script></body></html>'''


def _texts(data: dict, config, out: Path, seed: int, years: int) -> dict:
    """Stories and chronicle from the local model, cached per seed and run length."""
    from market_sim.llm import OllamaClient
    from market_sim.texts import generate_texts

    cache = out / f"texts_seed{seed}_{years}y.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    cfg = config.ollama
    llm = OllamaClient(cfg.story_model, cfg.host, cfg.timeout_seconds, cfg.temperature, cfg.max_tokens)
    if not llm.available():
        print(f"Ollama oder Modell {cfg.story_model} nicht erreichbar: es entstehen nur Kurzfassungen aus den Fakten.")
    texts = generate_texts(data, llm, progress=lambda done, total: print(f"Texte {done}/{total}", end="\r"))
    print()
    out.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(texts, ensure_ascii=False, indent=1), encoding="utf-8")
    return texts


def main(argv: list[str] | None = None) -> Path:
    config = load_market_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, default=config.simulation.years)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--days-per-year", type=int)
    parser.add_argument("--out", default="runs")
    parser.add_argument("--open", action="store_true", dest="open_browser")
    parser.add_argument("--texts", action="store_true",
                        help="write firm stories and a yearly chronicle with the local Ollama model (slow)")
    args = parser.parse_args(argv)
    days = args.days_per_year or config.simulation.days_per_year
    effective = config.model_copy(update={"simulation": config.simulation.model_copy(
        update={"years": max(1, args.years), "days_per_year": days}
    )})
    network = load_firms()
    result = run_simulation(args.years, args.seed, days, effective, network)
    data = build_dashboard_data(result, network, effective, args.seed)
    if args.texts:
        data["texts"] = _texts(data, effective, Path(args.out), args.seed, args.years)
    path = write_dashboard_html(data, Path(args.out) / "dashboard.html").resolve()
    print(path)
    if args.open_browser:
        webbrowser.open(path.as_uri())
    return path


if __name__ == "__main__":
    main()
