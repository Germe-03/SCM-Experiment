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
<title>Schweizer Bier-Markt — Simulations-Dashboard</title>
<script src="__CHART_JS__"></script>
<style>
:root{--ink:#17212b;--muted:#637083;--line:#dce2e8;--paper:#fff;--bg:#f3f6f8;--brand:#0b6b57}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
header{background:#12372f;color:#fff;padding:28px max(4vw,20px)}header h1{margin:0 0 6px;font-size:clamp(22px,3vw,34px)}header p{margin:0;color:#cfe0dc}
main{max-width:1500px;margin:auto;padding:22px}.panel,.card{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:18px;box-shadow:0 2px 8px #1020300a}
h2,h3{margin:0 0 14px}h4{margin:16px 0 8px}.controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}button{border:1px solid #aeb9c4;background:#fff;border-radius:7px;padding:7px 11px;cursor:pointer}button:hover{background:#e9f4f1}
#actor-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.stage-group{border-left:4px solid var(--brand);padding:8px 12px;background:#f7faf9}.stage-group strong{display:block;text-transform:capitalize;margin-bottom:5px}.actor{display:block;padding:4px 0}.actor small{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.chartbox{height:290px;position:relative;border:1px solid var(--line);border-radius:9px;padding:10px}.chartbox.wide{grid-column:1/-1}.chartbox h3{font-size:14px;margin:0 0 5px}.chartbox canvas{max-height:245px}
.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;white-space:nowrap}th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right}th{background:#f6f8fa;position:sticky;top:0}th:nth-child(-n+4),td:nth-child(-n+4){text-align:left}tr.selected{background:#e8f5f1}
.headline{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:9px}.kpi{background:#f5f8fa;border-radius:8px;padding:10px}.kpi span{display:block;color:var(--muted);font-size:12px}.kpi b{font-size:17px}.identity{display:flex;gap:10px;align-items:baseline}.pill{background:#e2f1ed;color:#075343;border-radius:20px;padding:3px 9px}.problem{color:#8d3b22}.empty{text-align:center;color:var(--muted);padding:30px}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:800px){main{padding:12px}.grid{grid-template-columns:1fr}.chartbox.wide{grid-column:auto}}
</style></head><body>
<div class="sr-only">Interaktives Dashboard der Schweizer Biermarkt-Simulation. Alle Diagramme reagieren auf die Firmenauswahl.</div>
<header><h1>Schweizer Bier-Markt — Simulations-Dashboard</h1><p id="run-meta"></p></header><main>
<section class="panel" id="actor-selector"><h2>Akteure auswählen</h2><div class="controls"><button data-pick="all">Alle</button><button data-pick="none">Keine</button><button data-pick="retailer">Nur Retailer</button><button data-pick="wholesaler">Nur Wholesaler</button><button data-pick="distributor">Nur Distributor</button><button data-pick="factory">Nur Factory</button></div><div id="actor-groups"></div></section>
<section class="panel"><h2>Übersicht</h2><div class="table-wrap"><table id="ranking"><thead><tr><th>Rang</th><th>Firma</th><th>Stufe</th><th>Archetyp</th><th>Kum. Gewinn</th><th>Endbestand Cash</th><th>Marktanteil</th></tr></thead><tbody></tbody></table></div><div class="grid" id="system-charts"></div></section>
<section class="panel"><h2>Markteintritte und Ereignisse</h2><div class="table-wrap"><table id="events"><thead><tr><th>Jahr</th><th>Tag</th><th>Firma</th><th>Ereignis</th><th>Details</th></tr></thead><tbody></tbody></table></div></section>
<section class="panel" id="brand-panel"><h2>Marken</h2><div class="grid" id="brand-charts"></div></section>
<section class="panel" id="class-panel"><h2>Kundenklassen (letztes Jahr)</h2><div class="grid" id="class-charts"></div></section>
<section class="panel"><h2>Vergleich</h2><div id="selection-hint" class="empty" hidden>Bitte mindestens eine Firma auswählen.</div><div class="grid" id="comparison-charts"></div></section>
<section id="firm-details"></section>
</main><script id="dashboard-data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('dashboard-data').textContent), charts=[];
const colors=['#147d64','#d65f3c','#315ca8','#d49a18','#7b4fab','#168da3','#b3446c','#55752d'];
const color=Object.fromEntries(D.meta.firms.map((f,i)=>[f.id,colors[i%colors.length]]));
const money=v=>v==null?'—':new Intl.NumberFormat('de-CH',{style:'currency',currency:'CHF',maximumFractionDigits:0}).format(v);
const num=(v,d=1)=>v==null?'—':new Intl.NumberFormat('de-CH',{maximumFractionDigits:d}).format(v);
const pct=v=>v==null?'—':new Intl.NumberFormat('de-CH',{style:'percent',maximumFractionDigits:1}).format(v);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.getElementById('run-meta').textContent=`${D.meta.years} Jahre · Seed ${D.meta.seed} · erstellt ${new Date(D.meta.generated_at).toLocaleString('de-CH')}`;
const groups={}; D.meta.firms.forEach(f=>(groups[f.stage]??=[]).push(f));
document.getElementById('actor-groups').innerHTML=Object.entries(groups).map(([stage,fs])=>`<div class="stage-group"><strong>${esc(stage)}</strong>${fs.map((f,i)=>`<label class="actor"><input type="checkbox" value="${esc(f.id)}" ${i<2?'checked':''}> ${esc(f.name)} <small>· ${esc(f.archetype)}</small></label>`).join('')}</div>`).join('');
const selected=()=>[...document.querySelectorAll('#actor-groups input:checked')].map(x=>x.value);
document.querySelectorAll('#actor-selector button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#actor-groups input').forEach(x=>x.checked=b.dataset.pick==='all'||x.closest('.stage-group').querySelector('strong').textContent===b.dataset.pick);render()});
document.querySelectorAll('#actor-groups input').forEach(x=>x.onchange=render);
function destroy(){while(charts.length)charts.pop().destroy()}
function canvas(parent,title,id,wide=false){parent.insertAdjacentHTML('beforeend',`<div class="chartbox ${wide?'wide':''}"><h3>${esc(title)}</h3><canvas id="${id}" role="img" aria-label="${esc(title)}"></canvas></div>`);return document.getElementById(id)}
function line(ctx,labels,datasets,opts={}){charts.push(new Chart(ctx,{type:'line',data:{labels,datasets},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:datasets.length>1},tooltip:{itemSort:(a,b)=>b.parsed.y-a.parsed.y}},...opts}}))}
function renderRanking(ids){document.querySelector('#ranking tbody').innerHTML=D.ranking.map((r,i)=>`<tr class="${ids.includes(r.firm_id)?'selected':''}"><td>${i+1}</td><td>${esc(r.name)}</td><td>${esc(r.stage)}</td><td>${esc(r.archetype)}</td><td>${money(r.cumulative_profit)}</td><td>${money(r.final_cash)}</td><td>${pct(r.final_market_share)}</td></tr>`).join('')}
function renderEvents(){document.querySelector('#events tbody').innerHTML=(D.events||[]).map(e=>`<tr><td>${num(e.year,0)}</td><td>${num(e.day,0)}</td><td>${esc(D.firms[e.firm]?.name||e.firm||'Markt')}</td><td>${esc(e.event)}</td><td>${esc(e.details)}</td></tr>`).join('')}
function renderSystem(){const root=document.getElementById('system-charts');root.innerHTML='';[['total_profit','Gesamtgewinn',true],['bullwhip_ratio','Bullwhip-Ratio'],['market_concentration','Marktkonzentration (HHI)'],['total_lost_sales','Verlorene Verkäufe'],['market_entries','Markteintritte'],['bankruptcies','Konkurse'],['strategy_changes','Strategiewechsel'],['price_index','Preisindex'],['fx_rate','Wechselkurs CHF/EUR'],['transport_cost','Transportkosten',true],['offences','Straftaten'],['offences_detected','Entdeckte Straftaten'],['fines','Bussen',true],['poisonings','Vergiftungen'],['takeovers','Übernahmen'],['takeovers_blocked','Verbotene Übernahmen'],['breakups','Zerschlagungen'],['firms_using_service','Firmen mit Transportdienst'],['expansions','Kapazitätsausbauten'],['new_sites','Neue Standorte'],['export_units','Export (Einheiten)'],['share_beer','Anteil Bier'],['share_wine','Anteil Wein'],['share_spirits','Anteil Spirituosen'],['population_index','Bevölkerungsindex'],...['retailer','wholesaler','distributor','factory'].flatMap(s=>[[`interest_cost_${s}`,`Nettozinsaufwand ${s}`,true],[`debt_${s}`,`Verschuldung ${s}`,true],[`active_firms_${s}`,`Aktive Firmen ${s}`]])].forEach(([key,title,m])=>line(canvas(root,title,'sys-'+key),D.system.map(x=>'Jahr '+x.year),[{label:title,data:D.system.map(x=>x[key]),borderColor:'#147d64',backgroundColor:'#147d6422',tension:.2}],m?{scales:{y:{ticks:{callback:v=>money(v)}}}}:{}))}
const comparisons=[['profit','Gewinn pro Jahr','money'],['cash','Cash am Jahresende','money'],['market_share','Marktanteil Retailer','pct'],['reputation','Reputation'],['average_quality','Durchschnittliche Qualität'],['average_sell_price','Durchschnittlicher Verkaufspreis','money'],['service_level','Service-/Fill-Level','pct']];
function renderComparison(ids){const root=document.getElementById('comparison-charts');root.innerHTML='';document.getElementById('selection-hint').hidden=ids.length>0;if(!ids.length)return;comparisons.forEach(([key,title,fmt])=>{const sets=ids.map(id=>({id,f:D.firms[id],vals:D.firms[id].yearly.map(y=>y[key])})).filter(x=>x.vals.some(v=>v!=null)).map(x=>({label:x.f.name,data:x.vals,borderColor:color[x.id],backgroundColor:color[x.id]+'22',tension:.15}));if(sets.length)line(canvas(root,title,'cmp-'+key),D.firms[ids[0]].yearly.map(y=>'Jahr '+y.year),sets,fmt?{scales:{y:{ticks:{callback:v=>fmt==='money'?money(v):pct(v)}}}}:{})})}
function weekly(values){const out=[];for(let i=0;i<values.length;i+=7){const s=values.slice(i,i+7);out.push(s.reduce((a,b)=>a+b,0)/s.length)}return out}
const yearlyCols=['year','archetype','interest_cost','fixed_cost','revenue','profit','cash','purchase_cost','holding_cost','backlog_cost','wage_cost','hiring_cost','rnd_cost','handling_cost','market_share','average_sell_price','average_quality','stockout_days','lost_sales','employee_turnover','average_wage','reputation','capacity_utilization','service_level'];
function renderDetails(ids){const root=document.getElementById('firm-details');root.innerHTML='';ids.forEach((id,ix)=>{const f=D.firms[id],last=f.yearly.at(-1)||{},card=document.createElement('article');card.className='card';card.innerHTML=`<div class="identity"><h2>${esc(f.name)}</h2><span class="pill">${esc(f.stage)} · ${esc(f.archetype)}</span></div><div class="headline">${[['Gewinn',money(last.profit)],['Cash',money(last.cash)],['Marktanteil',pct(last.market_share)],['Reputation',pct(last.reputation)],['Qualität',pct(last.average_quality)],['Ø Preis',money(last.average_sell_price)],['Kapazitätsnutzung',pct(last.capacity_utilization)],['Stockout-Tage',num(last.stockout_days,0)],['Lost Sales',num(last.lost_sales,0)]].map(x=>`<div class="kpi"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('')}</div><h3>Jahreswerte</h3><div class="table-wrap"><table><thead><tr>${yearlyCols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${f.yearly.map(y=>`<tr>${yearlyCols.map(c=>`<td>${c==='archetype'?esc(y[c]):c.includes('cost')||['revenue','profit','cash','average_wage','average_sell_price'].includes(c)?money(y[c]):['market_share','reputation','capacity_utilization','service_level','average_quality','employee_turnover'].includes(c)?pct(y[c]):num(y[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="grid detailcharts"></div><h3>Lieferanten-Zuverlässigkeit</h3><div class="reliability"></div><h3>Hauptprobleme</h3><div class="problems"></div>`;root.appendChild(card);
const stackKey=d=>d.stack??'default';const cg=card.querySelector('.detailcharts'), costKeys=['interest_cost','fixed_cost','purchase_cost','holding_cost','backlog_cost','wage_cost','hiring_cost','rnd_cost','handling_cost'];charts.push(new Chart(canvas(cg,'Umsatz und Kosten','cost-'+ix,true),{type:'bar',data:{labels:f.yearly.map(y=>'Jahr '+y.year),datasets:[{label:'Umsatz',data:f.yearly.map(y=>y.revenue),backgroundColor:'#147d64'},...costKeys.map((k,j)=>({label:k,data:f.yearly.map(y=>y[k]),backgroundColor:colors[(j+1)%colors.length],stack:'cost'}))]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},onHover:(e,els,chart)=>{chart.hoverStack=els.length?stackKey(chart.data.datasets[els[0].datasetIndex]):null},plugins:{tooltip:{filter:item=>stackKey(item.dataset)===item.chart.hoverStack,itemSort:(a,b)=>b.parsed.y-a.parsed.y,callbacks:{label:c=>`${c.dataset.label}: ${money(c.parsed.y)}`}}},scales:{x:{stacked:true},y:{stacked:true,ticks:{callback:v=>money(v)}}}}}));
['inventory','backlog','cash'].forEach(k=>line(canvas(cg,`${k} (Wochenschnitt)`,`daily-${ix}-${k}`),weekly(f.daily[k]).map((_,i)=>'W '+(i+1)),[{label:f.name,data:weekly(f.daily[k]),borderColor:color[id],pointRadius:0}],k==='cash'?{scales:{y:{ticks:{callback:v=>money(v)}}}}:{}));
card.querySelector('.reliability').innerHTML=f.yearly.map(y=>`<div><b>Jahr ${y.year}:</b> ${Object.keys(y.supplier_reliability||{}).length?Object.entries(y.supplier_reliability).map(([s,v])=>`${esc(D.firms[s]?.name||s)} ${pct(v)}`).join(' · '):'Keine Daten'}</div>`).join('');card.querySelector('.problems').innerHTML=f.yearly.map(y=>`<div><b>Jahr ${y.year}:</b> ${(y.main_problems||[]).length?y.main_problems.map(p=>`<span class="problem">${esc(p)}</span>`).join(' · '):'Keine'}</div>`).join('')})}
function renderBrands(){const root=document.getElementById('brand-charts'),panel=document.getElementById('brand-panel');root.innerHTML='';const rows=D.brands||[];panel.hidden=!rows.length;if(!rows.length)return;const years=[...new Set(rows.map(r=>r.year))],ids=[...new Set(rows.map(r=>r.brand))],name=id=>rows.find(r=>r.brand===id).name;[['market_share','Marktanteil pro Marke'],['reputation','Reputation pro Marke']].forEach(([key,title])=>line(canvas(root,title,'brand-'+key),years.map(y=>'Jahr '+y),ids.map((id,j)=>({label:name(id),data:years.map(y=>(rows.find(r=>r.year===y&&r.brand===id)||{})[key]??null),borderColor:colors[j%colors.length],pointRadius:0})),{scales:{y:{ticks:{callback:v=>pct(v)}}}}))}
function renderClasses(){const root=document.getElementById('class-charts'),panel=document.getElementById('class-panel');root.innerHTML='';const rows=D.classes||[];panel.hidden=!rows.length;if(!rows.length)return;const last=Math.max(...rows.map(r=>r.year)),cur=rows.filter(r=>r.year===last);charts.push(new Chart(canvas(root,'Anteil ohne Kauf pro Klasse','class-nopurchase',true),{type:'bar',data:{labels:cur.map(r=>r.consumer_class),datasets:[{label:'ohne Kauf',data:cur.map(r=>r.no_purchase_rate),backgroundColor:'#c2410c'}]},options:{responsive:true,maintainAspectRatio:false,scales:{y:{ticks:{callback:v=>pct(v)}}}}}));charts.push(new Chart(canvas(root,'Bezahlter Durchschnittspreis pro Klasse','class-price',true),{type:'bar',data:{labels:cur.map(r=>r.consumer_class),datasets:[{label:'CHF pro Flasche',data:cur.map(r=>r.avg_price_paid),backgroundColor:'#147d64'}]},options:{responsive:true,maintainAspectRatio:false}}))}
function render(){destroy();const ids=selected();renderRanking(ids);renderSystem();renderEvents();renderBrands();renderClasses();renderComparison(ids);renderDetails(ids)}render();
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
