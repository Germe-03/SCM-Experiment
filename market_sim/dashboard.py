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
  <button role="tab" data-tab="firms">Firmen</button>
  <button role="tab" data-tab="compare">Vergleich</button>
  <button role="tab" data-tab="chain">Lieferkette</button>
  <button role="tab" data-tab="finance">Finanzen</button>
  <button role="tab" data-tab="state">Staat</button>
  <button role="tab" data-tab="rnd">F&amp;E</button>
  <button role="tab" data-tab="events">Ereignisse</button>
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
  <div class="card wide"><h3>Trends</h3><ul class="list" id="mk-trends"></ul></div>
 </div>
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
<section role="tabpanel" id="tab-compare">
 <h2>Vergleich</h2><p class="lead">Wähle Firmen aus und vergleiche ihre Entwicklung.</p>
 <div class="card" id="actor-selector" style="margin-bottom:16px">
  <div class="filters">
   <select id="cp-add" aria-label="Firma hinzufügen"></select>
   <button class="btn" id="cp-top">Top 5 nach Gewinn</button>
   <button class="btn" id="cp-retail">Alle aktiven Händler</button>
   <button class="btn" id="cp-clear">Keine</button>
  </div>
  <div class="chips" id="cp-chips"></div>
 </div>
 <div class="grid" id="cp-charts"></div>
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
 <div class="grid">
  <div class="card"><h3>Verschuldung pro Stufe</h3><div class="chart"><canvas id="fi-debt"></canvas></div></div>
  <div class="card"><h3>Nettozinsen pro Stufe</h3><div class="chart"><canvas id="fi-interest"></canvas></div></div>
  <div class="card"><h3>Eintritte, Konkurse, Strategiewechsel</h3><div class="chart"><canvas id="fi-churn"></canvas></div></div>
  <div class="card"><h3>Konzentration (HHI der Händler)</h3><div class="chart"><canvas id="fi-hhi"></canvas></div></div>
 </div>
</section>
<section role="tabpanel" id="tab-state">
 <h2>Staat</h2><p class="lead">Steuern, Straftaten, Bussen, Skandale und Wettbewerbsaufsicht.</p>
 <div class="kpis" id="st-kpis"></div>
 <div class="grid">
  <div class="card"><h3>Straftaten: begangen und entdeckt</h3><div class="chart"><canvas id="st-off"></canvas></div></div>
  <div class="card"><h3>Steuern und Bussen</h3><div class="chart"><canvas id="st-money"></canvas></div></div>
  <div class="card"><h3>Vergiftungen und Angst</h3><div class="chart"><canvas id="st-fear"></canvas></div></div>
  <div class="card"><h3>Übernahmen und Wettbewerbsaufsicht</h3><div class="chart"><canvas id="st-tko"></canvas></div></div>
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
</main>
<script id="dashboard-data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('dashboard-data').textContent);
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const STAGE={retailer:'Detailhandel',wholesaler:'Grosshandel',distributor:'Verteilung',factory:'Hersteller'};
const STAGES=Object.keys(STAGE);
const CAT={beer:'Bier',wine:'Wein',spirits:'Spirituosen'};
const ARCH={low_cost:'Discount',standard:'Standard',premium:'Premium',reliable:'Zuverlässig',growth:'Wachstum'};
const EVENT={bankruptcy:'Konkurs',market_entry:'Markteintritt',strategy_change:'Strategiewechsel',price_increase:'Preiserhöhung',price_cut:'Preissenkung',supplier_switch:'Lieferantenwechsel',capacity_limit:'Kapazitätsgrenze',heat_summer:'Hitzesommer',harvest_failure:'Ernteausfall',recall:'Rückruf',recession:'Rezession',raw_material_shortage:'Rohstoffknappheit',cost_shock:'Kostenschock',wage_push:'Lohnschub',inflation:'Teuerung',trend_change:'Trendwechsel',restructuring:'Sanierung',transport_switch:'Transportwechsel',expand_started:'Ausbau begonnen',expand_finished:'Ausbau fertig',site_started:'Standort begonnen',site_finished:'Neuer Standort',offence_detected:'Straftat entdeckt',poisoning:'Vergiftung',takeover:'Übernahme',takeover_blocked:'Übernahme verboten',breakup:'Zerschlagung',spin_off:'Abspaltung',rnd_started:'F&E-Projekt gestartet',rnd_success:'F&E-Erfolg',rnd_failure:'F&E-Fehlschlag'};
const TREND={none:'kein Trend',craft_welle:'Craft-Welle',alkoholfrei:'Alkoholfrei',sparwelle:'Sparwelle',tradition:'Tradition',wein_boom:'Wein-Boom'};
const trendText=d=>String(d).split(/->|→/).map(x=>TREND[x.trim()]||x.trim()).join(' → ');
const REGION={genfersee:'Genferseeregion',bern:'Bern',jura_freiburg:'Jura/Freiburg/Neuenburg',nordwestschweiz:'Nordwestschweiz',zuerich:'Zürich',ostschweiz:'Ostschweiz',zentralschweiz:'Zentralschweiz',tessin:'Tessin'};
// Firm ids and region keys in event texts become readable names.
const pretty=t=>String(t??'').replace(/[a-z]+(?:_[a-z0-9]+)*/g,m=>D.firms[m]?.name||REGION[m]||m);
const KEY_EVENTS=new Set(['trend_change','recession','raw_material_shortage','cost_shock','poisoning','breakup','wage_push']);
const firm=id=>D.firms[id],fname=id=>firm(id)?.name||id||'Markt';
const nf=(v,d=0)=>v==null||isNaN(v)?'—':new Intl.NumberFormat('de-CH',{maximumFractionDigits:d}).format(v);
const pct=v=>v==null||isNaN(v)?'—':new Intl.NumberFormat('de-CH',{style:'percent',maximumFractionDigits:1}).format(v);
const chf=v=>{if(v==null||isNaN(v))return'—';const a=Math.abs(v);return a>=1e9?nf(v/1e9,2)+' Mrd. CHF':a>=1e6?nf(v/1e6,1)+' Mio. CHF':nf(v)+' CHF'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const store={get(k,d){try{return JSON.parse(localStorage.getItem('bm-'+k))??d}catch{return d}},set(k,v){try{localStorage.setItem('bm-'+k,JSON.stringify(v))}catch{}}};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const pal=()=>[1,2,3,4,5,6,7,8].map(i=>css('--c'+i));
const stageColor=()=>Object.fromEntries(STAGES.map((s,i)=>[s,pal()[i]]));
const catColor=()=>({beer:pal()[3],wine:pal()[6],spirits:pal()[2]});

// --- state ---------------------------------------------------------------
const years=D.system.map(x=>x.year);
let range={from:years[0],to:years.at(-1)};
const S={tab:'overview',fmStage:new Set(STAGES),fmStatus:'all',fmSort:['profit',-1],fmFirm:null,cmp:store.get('cmp',null),evTypes:null,evLimit:200};
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
const status=f=>f.exit_year?`<span class="badge off">ausgeschieden Jahr ${f.exit_year}</span>`:'<span class="badge ok">aktiv</span>';
const empty=msg=>`<div class="empty">${esc(msg)}</div>`;
function firmRows(ids,cols){return ids.map(id=>`<tr class="click" data-firm="${esc(id)}">${cols(firm(id))}</tr>`).join('')}
function wireFirmLinks(root){root.querySelectorAll('[data-firm]').forEach(r=>{r.tabIndex=0;const go=()=>{S.fmFirm=r.dataset.firm;openTab('firms');setTimeout(()=>$('#fm-detail').scrollIntoView(),50)};r.onclick=go;r.onkeydown=e=>{if(e.key==='Enter')go()}})}

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
function renderMarket(){const rows=(D.brands||[]).filter(r=>inRange(r.year));const yrs=[...new Set(rows.map(r=>r.year))];
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
 $('#fm-stage').innerHTML=STAGES.map(s=>`<button class="chip" data-s="${s}" aria-pressed="${S.fmStage.has(s)}"><span class="dot" style="background:${stageColor()[s]}"></span>${STAGE[s]}</button>`).join('');
 $('#fm-status').innerHTML=[['all','Alle'],['active','Aktiv'],['exited','Ausgeschieden']].map(([k,l])=>`<button class="chip" data-st="${k}" aria-pressed="${S.fmStatus===k}">${l}</button>`).join('');
 $$('#fm-stage .chip').forEach(c=>c.onclick=()=>{const s=c.dataset.s;S.fmStage.has(s)?S.fmStage.delete(s):S.fmStage.add(s);renderFirms()});
 $$('#fm-status .chip').forEach(c=>c.onclick=()=>{S.fmStatus=c.dataset.st;renderFirms()});
 const q=$('#fm-search').value.trim().toLowerCase();
 const cols=[['name','Firma'],['stage','Stufe'],['category','Kategorie'],['region','Region'],['arch','Archetyp heute'],['profit','Gewinn im Zeitraum',1],['cash','Cash am Ende',1],['share','Marktanteil',1],['status','Status']];
 let ids=Object.keys(D.firms).filter(id=>{const f=firm(id);return S.fmStage.has(f.stage)&&(S.fmStatus==='all'||(S.fmStatus==='active')===!f.exit_year)&&(!q||f.name.toLowerCase().includes(q)||id.includes(q))});
 const val=(id,k)=>{const f=firm(id),y=f.yearly.filter(r=>inRange(r.year)),l=y.at(-1)||{};return{name:f.name,stage:STAGES.indexOf(f.stage),category:f.category,region:f.region||'',arch:l.archetype||f.archetype,profit:firmProfit(id),cash:l.cash,share:f.stage==='retailer'?l.market_share:null,status:f.exit_year||0}[k]};
 const [sk,sd]=S.fmSort;ids.sort((a,b)=>{const x=val(a,sk),y=val(b,sk);return(x>y?1:x<y?-1:0)*sd});
 $('#fm-table').innerHTML=`<thead><tr>${cols.map(([k,l,n])=>`<th class="sort ${n?'num':''} ${sk===k?(sd>0?'asc':'desc'):''}" data-k="${k}" tabindex="0">${l}</th>`).join('')}</tr></thead><tbody>${ids.length?ids.map(id=>{const f=firm(id);return`<tr class="click ${S.fmFirm===id?'current':''}" data-firm="${esc(id)}"><td><span class="dot" style="background:${stageColor()[f.stage]}"></span>${esc(f.name)}</td><td>${STAGE[f.stage]}</td><td>${esc(CAT[f.category]||f.category)}${f.importer?' (Import)':''}</td><td>${esc(REGION[f.region]||f.region||'—')}</td><td>${esc(ARCH[val(id,'arch')]||val(id,'arch'))}</td><td class="num">${chf(val(id,'profit'))}</td><td class="num">${chf(val(id,'cash'))}</td><td class="num">${pct(val(id,'share'))}</td><td>${status(f)}</td></tr>`}).join(''):`<tr><td colspan="9">${empty('Keine Firma passt zu Suche und Filter. Entferne einen Filter oder ändere die Suche.')}</td></tr>`}</tbody>`;
 $$('#fm-table th.sort').forEach(th=>{const go=()=>{const k=th.dataset.k;S.fmSort=[k,S.fmSort[0]===k?-S.fmSort[1]:(['name','stage','category','region','arch'].includes(k)?1:-1)];renderFirms()};th.onclick=go;th.onkeydown=e=>{if(e.key==='Enter')go()}});
 $$('#fm-table tr[data-firm]').forEach(r=>{r.tabIndex=0;const go=()=>{S.fmFirm=r.dataset.firm;renderFirms();$('#fm-detail').scrollIntoView({block:'start'})};r.onclick=go;r.onkeydown=e=>{if(e.key==='Enter')go()}});
 renderFirmDetail()}
function renderFirmDetail(){const root=$('#fm-detail');destroy();if(S.tab!=='firms')return;const id=S.fmFirm;
 if(!id||!firm(id)){root.innerHTML=empty('Wähle oben eine Firma, um ihre Entwicklung zu sehen.');return}
 const f=firm(id),y=f.yearly.filter(r=>inRange(r.year)),l=y.at(-1)||{};const inCmp=(S.cmp||[]).includes(id);
 root.innerHTML=`<div class="card"><div class="detail-head"><h2>${esc(f.name)}</h2><span class="badge">${STAGE[f.stage]}</span><span class="badge">${esc(CAT[f.category]||f.category)}${f.importer?' · Import':''}</span><span class="badge">${esc(REGION[f.region]||f.region||'')}</span>${status(f)}<button class="btn ${inCmp?'':'primary'}" id="fd-cmp" style="margin-left:auto">${inCmp?'Aus Vergleich entfernen':'Zum Vergleich hinzufügen'}</button></div>
 <div class="kpis">${kpi('Gewinn im Zeitraum',chf(firmProfit(id)))}${kpi('Cash am Ende',chf(l.cash))}${kpi('Reputation',pct(l.reputation))}${kpi('Qualität',pct(l.average_quality))}${kpi('Auslastung',pct(l.capacity_utilization))}${f.stage==='retailer'?kpi('Marktanteil',pct(l.market_share)):kpi('Lieferquote',pct(l.service_level??null))}</div>
 <div class="grid"><div class="card wide"><h3>Umsatz und Kosten pro Jahr</h3><p class="hint">Fahre über die Kostensäule, um die Kostenarten zu sehen.</p><div class="chart"><canvas id="fd-cost"></canvas></div></div>
 <div class="card"><h3>Cash (Wochenschnitt)</h3><div class="chart"><canvas id="fd-cash"></canvas></div></div><div class="card"><h3>Lager und Rückstand (Wochenschnitt)</h3><div class="chart"><canvas id="fd-stock"></canvas></div></div>
 <div class="card"><h3>Reputation und Qualität</h3><div class="chart"><canvas id="fd-rep"></canvas></div></div><div class="card"><h3>Ereignisse dieser Firma</h3><ul class="list" id="fd-events" style="max-height:270px;overflow:auto"></ul></div></div></div>`;
 $('#fd-cmp').onclick=()=>{const c=new Set(S.cmp||[]);c.has(id)?c.delete(id):c.add(id);S.cmp=[...c];store.set('cmp',S.cmp);renderFirmDetail()};
 const lbl=y.map(r=>r.year),costs={purchase_cost:'Einkauf/Rohstoffe',wage_cost:'Löhne',fixed_cost:'Fixkosten',handling_cost:'Handling & Transport',rnd_cost:'F&E',holding_cost:'Lager',backlog_cost:'Rückstand',hiring_cost:'Einstellung',interest_cost:'Zinsen'};
 const stackKey=d=>d.stack??'rev';
 chart('fd-cost',{type:'bar',data:{labels:lbl,datasets:[{label:'Umsatz',data:y.map(r=>r.revenue),backgroundColor:pal()[0],stack:'rev'},...Object.entries(costs).map(([k,n],j)=>({label:n,data:y.map(r=>r[k]),backgroundColor:pal()[(j+1)%8]+'cc',stack:'cost'}))]},
  options:{onHover:(e,els,c)=>{c.hoverStack=els.length?stackKey(c.data.datasets[els[0].datasetIndex]):null},plugins:{tooltip:{filter:i=>stackKey(i.dataset)===i.chart.hoverStack,itemSort:(a,b)=>b.parsed.y-a.parsed.y,callbacks:{label:c=>`${c.dataset.label}: ${chf(c.parsed.y)}`}}},scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,...fmtAxis('chf')}}}});
 const weeks=D.meta.days_per_year/7,w=f.weekly,from=Math.floor((range.from-1)*weeks),to=Math.ceil(range.to*weeks);const wl=w.cash.slice(from,to).map((_,i)=>((from+i)/weeks+1).toFixed(1));
 chart('fd-cash',{type:'line',data:{labels:wl,datasets:[{label:'Cash',data:w.cash.slice(from,to),borderColor:pal()[2],pointRadius:0,borderWidth:1.5}]},options:{scales:{x:{ticks:{maxTicksLimit:10,callback:function(v){return'Jahr '+Math.floor(this.getLabelForValue(v))}}},y:fmtAxis('chf')}}});
 chart('fd-stock',{type:'line',data:{labels:wl,datasets:[{label:'Lager',data:w.inventory.slice(from,to),borderColor:pal()[0],pointRadius:0,borderWidth:1.5},{label:'Rückstand',data:w.backlog.slice(from,to),borderColor:pal()[1],pointRadius:0,borderWidth:1.5}]},options:{scales:{x:{ticks:{maxTicksLimit:10,callback:function(v){return'Jahr '+Math.floor(this.getLabelForValue(v))}}}}}});
 chart('fd-rep',{type:'line',data:{labels:lbl,datasets:[{label:'Reputation',data:y.map(r=>r.reputation),borderColor:pal()[4],pointRadius:0,borderWidth:2},{label:'Qualität',data:y.map(r=>r.average_quality),borderColor:pal()[5],pointRadius:0,borderWidth:2}]},options:{scales:{y:fmtAxis('pct')}}});
 const fe=f.events.filter(e=>inRange(e.year)&&e.event!=='inflation').slice().reverse();
 $('#fd-events').innerHTML=fe.length?fe.map(e=>`<li><span class="yr">Jahr ${e.year}</span><span><b>${esc(EVENT[e.event]||e.event)}</b> <span class="badge">${esc(pretty(e.details))}</span></span></li>`).join(''):'<li>Keine Ereignisse im Zeitraum.</li>'}

// --- Vergleich -----------------------------------------------------------
function renderCompare(){if(S.cmp==null)S.cmp=Object.keys(D.firms).map(id=>[id,firmProfit(id)]).sort((a,b)=>b[1]-a[1]).slice(0,3).map(x=>x[0]);
 const opts=STAGES.map(st=>`<optgroup label="${STAGE[st]}">${Object.keys(D.firms).filter(id=>firm(id).stage===st&&!S.cmp.includes(id)).map(id=>`<option value="${esc(id)}">${esc(fname(id))}${firm(id).exit_year?' (ausgeschieden)':''}</option>`).join('')}</optgroup>`).join('');
 $('#cp-add').innerHTML='<option value="">Firma hinzufügen …</option>'+opts;
 $('#cp-add').onchange=e=>{if(e.target.value){S.cmp=[...S.cmp,e.target.value];store.set('cmp',S.cmp);renderCompare()}};
 $('#cp-top').onclick=()=>{S.cmp=Object.keys(D.firms).map(id=>[id,firmProfit(id)]).sort((a,b)=>b[1]-a[1]).slice(0,5).map(x=>x[0]);store.set('cmp',S.cmp);renderCompare()};
 $('#cp-retail').onclick=()=>{S.cmp=Object.keys(D.firms).filter(id=>firm(id).stage==='retailer'&&!firm(id).exit_year);store.set('cmp',S.cmp);renderCompare()};
 $('#cp-clear').onclick=()=>{S.cmp=[];store.set('cmp',S.cmp);renderCompare()};
 const col=Object.fromEntries(S.cmp.map((id,i)=>[id,pal()[i%8]]));
 $('#cp-chips').innerHTML=S.cmp.length?S.cmp.map(id=>`<button class="chip" data-id="${esc(id)}" aria-label="${esc(fname(id))} entfernen"><span class="dot" style="background:${col[id]}"></span>${esc(fname(id))}<span class="x">✕</span></button>`).join(''):'<span class="badge">Noch keine Firma gewählt. Füge oben Firmen hinzu.</span>';
 $$('#cp-chips .chip').forEach(c=>c.onclick=()=>{S.cmp=S.cmp.filter(x=>x!==c.dataset.id);store.set('cmp',S.cmp);renderCompare()});
 destroy();const root=$('#cp-charts');
 if(!S.cmp.length){root.innerHTML=`<div class="card wide">${empty('Wähle mindestens eine Firma, dann erscheinen hier die Vergleiche.')}</div>`;return}
 const defs=[['profit','Gewinn pro Jahr','chf'],['cash','Cash am Jahresende','chf'],['revenue','Umsatz','chf'],['market_share','Marktanteil (nur Händler)','pct'],['reputation','Reputation','pct'],['average_sell_price','Durchschnittspreis',null],['capacity_utilization','Auslastung','pct'],['service_level','Lieferquote (Händler)','pct']];
 root.innerHTML=defs.map(([k,t])=>`<div class="card"><h3>${t}</h3><div class="chart"><canvas id="cp-${k}"></canvas></div></div>`).join('');
 const lbl=years.filter(inRange);defs.forEach(([k,t,f])=>chart('cp-'+k,{type:'line',data:{labels:lbl,datasets:S.cmp.map(id=>({label:fname(id),data:lbl.map(y=>(firm(id).yearly.find(r=>r.year===y)||{})[k]??null),borderColor:col[id],pointRadius:0,borderWidth:2,spanGaps:false}))},options:{scales:{y:fmtAxis(f)}}}))}

// --- Lieferkette, Finanzen, Staat, F&E ----------------------------------
function renderChain(){lines('ch-margin',byStage('margin_'),{fmt:'pct'});lines('ch-util',byStage('utilization_'),{fmt:'pct'});
 lines('ch-lost',[{label:'Verlorene Verkäufe',get:x=>x.total_lost_sales,color:css('--bad')}]);lines('ch-bull',[{label:'Bullwhip',get:x=>x.bullwhip_ratio}]);
 lines('ch-transport',[{label:'Transportkosten',get:x=>x.transport_cost,fmt:'chf'},{label:'Treibstoffindex',get:x=>x.fuel_index,axis:'y2'}],{fmt:'chf'});
 lines('ch-service',[{label:'Firmen mit Transportdienst',get:x=>x.firms_using_service},{label:'Schäden (Einheiten)',get:x=>x.damaged_units,axis:'y2'}]);
 const s=sys();chart('ch-build',{type:'bar',data:{labels:s.map(x=>x.year),datasets:[{label:'Ausbauten',data:s.map(x=>x.expansions),backgroundColor:pal()[0]+'bb'},{label:'Neue Standorte',data:s.map(x=>x.new_sites),backgroundColor:pal()[2]+'bb'}]},options:{scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true}}}})}
function renderFinance(){lines('fi-debt',byStage('debt_','chf'),{fmt:'chf'});lines('fi-interest',byStage('interest_cost_','chf'),{fmt:'chf'});
 const s=sys(),restr=y=>D.events.filter(e=>e.year===y&&e.event==='restructuring').length;
 chart('fi-churn',{type:'bar',data:{labels:s.map(x=>x.year),datasets:[{label:'Eintritte',data:s.map(x=>x.market_entries),backgroundColor:pal()[0]+'bb'},{label:'Konkurse',data:s.map(x=>x.bankruptcies),backgroundColor:css('--bad')+'bb'},{label:'Sanierungen',data:s.map(x=>restr(x.year)),backgroundColor:pal()[3]+'bb'},{type:'line',label:'Strategiewechsel',data:s.map(x=>x.strategy_changes),borderColor:pal()[4],pointRadius:0}]},options:{scales:{x:{grid:{display:false}}}}});
 lines('fi-hhi',[{label:'HHI',get:x=>x.market_concentration}])}
function renderState(){const s=sys();$('#st-kpis').innerHTML=[kpi('Steuern',chf(sumBy(s,'taxes')),'im Zeitraum'),kpi('Straftaten',nf(sumBy(s,'offences')),nf(sumBy(s,'offences_detected'))+' entdeckt'),kpi('Bussen',chf(sumBy(s,'fines'))),kpi('Vergiftungen',nf(sumBy(s,'poisonings'))),kpi('Übernahmen',nf(sumBy(s,'takeovers')),nf(sumBy(s,'takeovers_blocked'))+' verboten'),kpi('Zerschlagungen',nf(sumBy(s,'breakups')))].join('');
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
 const P={prozessautomation:'Prozessautomation',rezeptur_optimierung:'Rezeptur-Optimierung',neue_marke:'Neue Marke',alkoholfreies_bier:'Alkoholfreies Bier'};
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
const VIEWS={overview:renderOverview,market:renderMarket,firms:renderFirms,compare:renderCompare,chain:renderChain,finance:renderFinance,state:renderState,rnd:renderRnd,events:renderEvents};
function render(){destroy();VIEWS[S.tab]()}
openTab(location.hash.slice(1)||'overview');
</script></body></html>'''


def main(argv: list[str] | None = None) -> Path:
    config = load_market_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, default=config.simulation.years)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--days-per-year", type=int)
    parser.add_argument("--out", default="runs")
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args(argv)
    days = args.days_per_year or config.simulation.days_per_year
    effective = config.model_copy(update={"simulation": config.simulation.model_copy(
        update={"years": max(1, args.years), "days_per_year": days}
    )})
    network = load_firms()
    result = run_simulation(args.years, args.seed, days, effective, network)
    path = write_dashboard_html(
        build_dashboard_data(result, network, effective, args.seed),
        Path(args.out) / "dashboard.html",
    ).resolve()
    print(path)
    if args.open_browser:
        webbrowser.open(path.as_uri())
    return path


if __name__ == "__main__":
    main()
