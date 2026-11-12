'use strict';

(function () {
  var STIL = [
    '.rd-reiter{display:grid;gap:1rem}',
    '.rd-block{padding:1rem;border:1px solid var(--rand);background:var(--flaeche);border-radius:.5rem;min-width:0}',
    '.rd-block h3{margin:0 0 .75rem}',
    '.rd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));gap:.75rem}',
    '.rd-kachel{padding:.75rem;border:1px solid var(--rand);border-radius:.4rem}',
    '.rd-kachel strong,.rd-kachel span{display:block}',
    '.rd-kachel span,.rd-leise{color:var(--text-leise)}',
    '.rd-tabelle{width:100%;border-collapse:collapse}',
    '.rd-tabelle th,.rd-tabelle td{padding:.45rem .55rem;border-bottom:1px solid var(--rand);text-align:left;vertical-align:top}',
    '.rd-tabelle th button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer}',
    '.rd-eigen{background:color-mix(in srgb,var(--akzent) 12%,var(--flaeche))}',
    '.rd-balken-zeile,.rd-spanne{margin:.6rem 0}',
    '.rd-balken-kopf,.rd-spanne-kopf{display:flex;justify-content:space-between;gap:.5rem;margin-bottom:.25rem}',
    '.rd-balken-rahmen,.rd-spanne-rahmen{height:.8rem;background:var(--rand);border-radius:1rem;position:relative;overflow:hidden}',
    '.rd-balken-fuellung{height:100%;background:var(--akzent);border-radius:1rem}',
    '.rd-spanne-markierung{position:absolute;top:-.15rem;height:1.1rem;width:2px;background:var(--text-leise)}',
    '.rd-plan{border:1px solid var(--akzent);padding:.7rem;border-radius:.4rem;display:flex;justify-content:space-between;align-items:center;gap:1rem}',
    '.rd-form{display:flex;flex-wrap:wrap;align-items:end;gap:.6rem;margin:.75rem 0}',
    '.rd-form label{display:grid;gap:.25rem}',
    '.rd-positiv{color:var(--positiv)}.rd-negativ{color:var(--negativ)}',
    '.rd-legende{display:flex;flex-wrap:wrap;gap:.8rem;margin:.5rem 0}',
    '.rd-punkt{display:inline-block;width:.65rem;height:.65rem;border-radius:50%;margin-right:.3rem}',
    '.rd-map{width:100%;height:auto;max-height:30rem}',
    '.rd-map text{font-size:11px;fill:var(--text-leise)}',
    '.rd-mini{vertical-align:middle}',
    '.rd-note{margin:.5rem 0;color:var(--text-leise)}',
    '.rd-scroll{overflow-x:auto}',
    ':root{--rd-farbe-5:#8e6bbf;--rd-farbe-6:#d98c2b;--rd-farbe-7:#2b9dd9;--rd-farbe-8:#7a8b3c}',
    '@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--rd-farbe-5:#8e6bbf;--rd-farbe-6:#d98c2b;--rd-farbe-7:#2b9dd9;--rd-farbe-8:#7a8b3c}}'
  ].join('');

  if (typeof document !== 'undefined' && document.head && !document.getElementById('reiter-daten-stil')) {
    var stil = document.createElement('style');
    stil.id = 'reiter-daten-stil';
    stil.textContent = STIL;
    document.head.appendChild(stil);
  }

  var sortierung = { key: null, richtung: 1 };
  var kreditBetrag = 100000;
  var aktienAuswahl = null;
  var aktienAnzahl = 1;
  var bevoelkerungsStufe = '';

  var REITER = window.REITER = window.REITER || {};

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function svgEl(tag) {
    return document.createElementNS('http://www.w3.org/2000/svg', tag);
  }

  function wert(obj, key, fallback) {
    if (!obj || obj[key] === undefined || obj[key] === null) return fallback;
    return obj[key];
  }

  function array(v) {
    return Array.isArray(v) ? v : [];
  }

  function zahlRoh(v) {
    var n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  function format(ctx, v, art, stellen) {
    var n = Number(v);
    if (!Number.isFinite(n)) return '–';
    try {
      if (art === 'geld' && typeof ctx.geld === 'function') return ctx.geld(n);
      if (art === 'prozent' && typeof ctx.prozent === 'function') return ctx.prozent(n);
      if (typeof ctx.zahl === 'function') return ctx.zahl(n, stellen);
    } catch (e) {
      return String(n);
    }
    return String(n);
  }

  function geld(ctx, v) {
    return format(ctx, v, 'geld');
  }

  function zahl(ctx, v, stellen) {
    return format(ctx, v, 'zahl', stellen);
  }

  function prozent(ctx, v) {
    return format(ctx, v, 'prozent');
  }

  function textZeile(parent, text, cls) {
    parent.appendChild(el('p', cls || '', text || 'Keine Daten'));
  }

  function abschnitt(parent, titel) {
    var block = el('div', 'rd-block');
    block.appendChild(el('h3', '', titel));
    parent.appendChild(block);
    return block;
  }

  function tabelle(spalten, zeilen, opts) {
    var wrap = el('div', 'rd-scroll');
    if (!zeilen.length) {
      wrap.appendChild(el('p', 'rd-leise', 'Keine Daten'));
      return wrap;
    }
    var table = el('table', 'rd-tabelle');
    var head = el('thead');
    var hr = el('tr');
    spalten.forEach(function (spalte) {
      var th = el('th');
      if (opts && opts.sortable) {
        var button = el('button', '', spalte.label + (sortierung.key === spalte.key ? (sortierung.richtung > 0 ? ' ▲' : ' ▼') : ''));
        button.type = 'button';
        button.addEventListener('click', function () {
          if (sortierung.key === spalte.key) sortierung.richtung *= -1;
          else {
            sortierung.key = spalte.key;
            sortierung.richtung = 1;
          }
          if (opts.onSort) opts.onSort();
        });
        th.appendChild(button);
      } else {
        th.textContent = spalte.label;
      }
      hr.appendChild(th);
    });
    head.appendChild(hr);
    table.appendChild(head);
    var body = el('tbody');
    zeilen.forEach(function (zeile) {
      var tr = el('tr', opts && opts.rowClass ? opts.rowClass(zeile) : '');
      spalten.forEach(function (spalte) {
        var td = el('td');
        var value = typeof spalte.value === 'function' ? spalte.value(zeile) : zeile[spalte.key];
        if (value && value.nodeType) td.appendChild(value);
        else td.textContent = value === undefined || value === null || value === '' ? '–' : String(value);
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    table.appendChild(body);
    wrap.appendChild(table);
    return wrap;
  }

  function container(elm) {
    elm.replaceChildren();
    var root = el('div', 'rd-reiter');
    elm.appendChild(root);
    return root;
  }

  function kachel(parent, titel, inhalt, cls) {
    var box = el('div', 'rd-kachel');
    box.appendChild(el('span', 'rd-leise', titel));
    var value = el('strong', cls || '', inhalt);
    box.appendChild(value);
    parent.appendChild(box);
    return box;
  }

  function erklaerung(parent, titel, text) {
    var details = el('details', 'rd-note');
    details.appendChild(el('summary', '', titel));
    details.appendChild(el('p', '', text));
    parent.appendChild(details);
    return details;
  }

  function balken(parent, titel, wertText, anteil) {
    var row = el('div', 'rd-balken-zeile');
    var head = el('div', 'rd-balken-kopf');
    head.appendChild(el('span', '', titel));
    head.appendChild(el('span', '', wertText));
    row.appendChild(head);
    var track = el('div', 'rd-balken-rahmen');
    var fill = el('div', 'rd-balken-fuellung');
    fill.style.width = Math.max(0, Math.min(100, Number(anteil) || 0)) + '%';
    track.appendChild(fill);
    row.appendChild(track);
    parent.appendChild(row);
    return row;
  }

  function spanne(parent, titel, daten, maximum, ctx) {
    if (!daten) {
      textZeile(parent, titel + ': Keine Daten');
      return;
    }
    var min = zahlRoh(daten.min);
    var max = zahlRoh(daten.max);
    var avg = zahlRoh(daten.avg);
    var skala = maximum > 0 ? maximum : 1;
    var row = el('div', 'rd-spanne');
    var head = el('div', 'rd-spanne-kopf');
    head.appendChild(el('strong', '', titel));
    head.appendChild(el('span', '', zahl(ctx, min) + ' – ' + zahl(ctx, max) + ' (Ø ' + zahl(ctx, avg) + ')'));
    row.appendChild(head);
    var track = el('div', 'rd-spanne-rahmen');
    var fill = el('div', 'rd-balken-fuellung');
    fill.style.position = 'absolute';
    fill.style.left = Math.max(0, min / skala * 100) + '%';
    fill.style.width = Math.max(0, Math.min(100, (max - min) / skala * 100)) + '%';
    track.appendChild(fill);
    var marker = el('div', 'rd-spanne-markierung');
    marker.style.left = Math.max(0, Math.min(100, avg / skala * 100)) + '%';
    track.appendChild(marker);
    row.appendChild(track);
    parent.appendChild(row);
  }

  function planBox(parent, ctx, key, text) {
    var geplant = {};
    try {
      geplant = typeof ctx.geplant === 'function' ? (ctx.geplant() || {}) : {};
    } catch (e) {
      geplant = {};
    }
    if (!geplant[key]) return;
    var box = el('div', 'rd-plan');
    box.appendChild(el('span', '', 'Geplant für die nächste Runde: ' + (text || 'Auftrag')));
    var button = el('button', '', 'Rückgängig');
    button.type = 'button';
    button.addEventListener('click', function () {
      ctx.plane(key, null);
      ctx.neuZeichnen();
    });
    box.appendChild(button);
    parent.appendChild(box);
  }

  function laden(ctx, name, query) {
    return Promise.resolve().then(function () {
      return ctx.ansicht(name, query);
    }).catch(function () {
      return null;
    });
  }

  function fehlerBlock(parent, titel) {
    var block = abschnitt(parent, titel);
    textZeile(block, 'Daten nicht verfuegbar', 'rd-leise');
    return block;
  }

  function formatWert(ctx, value, art) {
    if (art === 'geld') return geld(ctx, value);
    if (art === 'prozent') return prozent(ctx, value);
    return zahl(ctx, value);
  }

  function linien(parent, ctx, series, optionen) {
    if (!series.length || typeof ctx.linien !== 'function') {
      textZeile(parent, 'Keine Daten', 'rd-leise');
      return;
    }
    try {
      var chart = ctx.linien(series, optionen || {});
      if (chart) parent.appendChild(chart);
    } catch (e) {
      textZeile(parent, 'Keine Daten', 'rd-leise');
    }
  }

  function legende(parent, series) {
    var node = el('div', 'rd-legende');
    series.forEach(function (s) {
      var item = el('span');
      var dot = el('span', 'rd-punkt');
      dot.style.backgroundColor = s.farbe;
      item.appendChild(dot);
      item.appendChild(document.createTextNode(s.name));
      node.appendChild(item);
    });
    parent.appendChild(node);
  }

  function marktRender(elm, ctx) {
    var root = container(elm);
    planBox(root, ctx, 'stock', 'Aktienauftrag');
    return Promise.all([laden(ctx, 'compare'), laden(ctx, 'market')]).then(function (result) {
      var vergleich = result[0];
      var markt = result[1];
      if (!vergleich) fehlerBlock(root, 'Vergleich');
      else {
        var block = abschnitt(root, 'Vergleich');
        var rows = array(vergleich.rows).slice();
        function sortRows() {
          var sorted = rows.slice();
          if (sortierung.key) {
            var key = sortierung.key;
            sorted.sort(function (a, b) {
              var av = a[key];
              var bv = b[key];
              var numeric = typeof av === 'number' || typeof bv === 'number';
              var cmp = numeric ? zahlRoh(av) - zahlRoh(bv) : String(av || '').localeCompare(String(bv || ''), 'de');
              return cmp * sortierung.richtung;
            });
          }
          block.querySelector('.rd-scroll')?.remove();
          block.appendChild(tabelle([
            { key: 'name', label: 'Name', value: function (r) {
              var wrap = el('span');
              wrap.appendChild(document.createTextNode(wert(r, 'name', '–')));
              if (r.is_player && r.profit !== undefined) {
                wrap.appendChild(el('small', 'rd-leise', 'Gewinn: ' + geld(ctx, r.profit)));
              }
              return wrap;
            } },
            { key: 'branch', label: 'Branche' },
            { key: 'region', label: 'Region' },
            { key: 'revenue', label: 'Umsatz', value: function (r) { return geld(ctx, r.revenue); } },
            { key: 'market_share', label: 'Marktanteil', value: function (r) { return prozent(ctx, r.market_share); } },
            { key: 'avg_price', label: 'Ø Preis', value: function (r) { return (ctx.preis ? ctx.preis(r.avg_price) : geld(ctx, r.avg_price)); } },
            { key: 'quality', label: 'Qualität', value: function (r) { return zahl(ctx, r.quality); } },
            { key: 'reputation', label: 'Ruf', value: function (r) { return zahl(ctx, r.reputation); } },
            { key: 'service_level', label: 'Servicegrad', value: function (r) { return prozent(ctx, r.service_level); } },
            { key: 'capacity_utilization', label: 'Auslastung', value: function (r) { return prozent(ctx, r.capacity_utilization); } },
            { key: 'archetype_label', label: 'Einstufung' },
            { key: 'stock_price', label: 'Aktie', value: function (r) { return r.listed ? geld(ctx, r.stock_price) : '–'; } }
          ], sorted, { sortable: true, rowClass: function (r) { return r.is_player ? 'rd-eigen' : ''; }, onSort: sortRows }));
        }
        sortRows();
        textZeile(block, 'Gewinne der Konkurrenz sind geheim: Du siehst nur öffentliche Zahlen.', 'rd-note');
      }

      if (vergleich) {
        var verlauf = abschnitt(root, 'Umsatzverlauf');
        var rows = array(vergleich.rows);
        var eigene = rows.find(function (r) { return r.is_player; });
        var andere = rows.filter(function (r) { return !r.is_player; })
          .sort(function (a, b) { return zahlRoh(b.revenue) - zahlRoh(a.revenue); }).slice(0, 3);
        var palette = ['var(--text-leise)', 'var(--positiv)', 'var(--negativ)'];
        var series = [];
        if (eigene) series.push({ name: eigene.name || 'Eigene Firma', werte: array(eigene.revenue_history), farbe: 'var(--akzent)' });
        andere.forEach(function (r, i) {
          series.push({ name: r.name || 'Firma', werte: array(r.revenue_history), farbe: palette[i] });
        });
        if (!series.length) textZeile(verlauf, 'Keine Daten', 'rd-leise');
        else {
          legende(verlauf, series);
          linien(verlauf, ctx, series, { labels: array(vergleich.years), hoehe: 200 });
        }
      } else {
        fehlerBlock(root, 'Umsatzverlauf');
      }

      if (!markt) fehlerBlock(root, 'Marktdaten');
      else {
        var mb = abschnitt(root, 'Marktdaten');
        var categories = array(markt.categories);
        if (!categories.length) textZeile(mb, 'Keine Daten');
        var maxShare = Math.max.apply(null, categories.map(function (c) { return zahlRoh(c.share); }).concat([1]));
        categories.forEach(function (c) {
          var kategorienDe = { beer: 'Bier', wine: 'Wein', spirits: 'Spirituosen', softdrinks: 'Softdrinks', water: 'Wasser' };
          var kname = wert(c, 'name', '–');
          balken(mb, kategorienDe[kname] || kname,prozent(ctx, c.share), zahlRoh(c.share) / maxShare * 100);
        });
        var cap = zahlRoh(markt.stage_capacity_per_day);
        var dem = zahlRoh(markt.stage_demand_per_day);
        var scale = Math.max(cap, dem, 1);
        balken(mb, 'Stufenkapazität pro Tag', zahl(ctx, cap), cap / scale * 100);
        balken(mb, 'Stufennachfrage pro Tag', zahl(ctx, dem), dem / scale * 100);
        textZeile(mb, 'Firmen in dieser Stufe: ' + zahl(ctx, markt.firms_in_stage));
        var band = markt.price_band;
        textZeile(mb, 'Preisband: ' + (band ? geld(ctx, band.min) + ' – ' + geld(ctx, band.max) : '–'));
        textZeile(mb, 'Konkurrenzpreis: ' + (ctx.preis ? ctx.preis(markt.rival_price) : geld(ctx, markt.rival_price)));
      }
    });
  }

  REITER.markt = { async render(elm, ctx) { return marktRender(elm, ctx); } };

  // Anteile je Lieferant: erst der Entwurf dieser Runde, sonst der gespeicherte Stand.
  function aktuelleAnteile(ctx) {
    var quelle = null;
    try {
      if (typeof entwurfEntscheide !== 'undefined' &&
          Object.prototype.hasOwnProperty.call(entwurfEntscheide, 'supplier_shares')) {
        quelle = entwurfEntscheide.supplier_shares;
      } else if (ctx.state && ctx.state.choices) {
        quelle = ctx.state.choices.supplier_shares;
      }
    } catch (e) {
      quelle = null;
    }
    return quelle && typeof quelle === 'object' ? quelle : {};
  }

  function sendeAnteileAnzeige(knoten, eingaben, ctx) {
    var summeWert = 0;
    var anzahl = 0;
    Object.keys(eingaben).forEach(function (id) {
      var n = Number(String(eingaben[id].value).replace(',', '.'));
      if (Number.isFinite(n) && n > 0) {
        summeWert += n;
        anzahl += 1;
      }
    });
    knoten.textContent = anzahl
      ? 'Summe der Eingaben: ' + zahl(ctx, summeWert, 1) + ' % (wird auf 100 % umgerechnet)'
      : 'Keine Anteile gesetzt: es gilt die Regel unten.';
  }

  function logistikRender(elm, ctx) {
    var root = container(elm);
    planBox(root, ctx, 'truck', 'Lastwagenauftrag');
    return Promise.all([laden(ctx, 'capacity'), laden(ctx, 'suppliers'), laden(ctx, 'trucks')]).then(function (r) {
      var cap = r[0];
      var sortimentPromise = null;
      if (!cap) fehlerBlock(root, 'Kapazität und Nachfrage');
      else {
        var block = abschnitt(root, 'Kapazität und Nachfrage');
        var ranges = [cap.demand, cap.sales, cap.stage_demand];
        var max = Math.max.apply(null, ranges.map(function (x) { return zahlRoh(x && x.max); }).concat([1])) * 1.1;
        spanne(block, 'Nachfrage', cap.demand, max, ctx);
        spanne(block, 'Verkauf', cap.sales, max, ctx);
        spanne(block, 'Stufen-Nachfrage', cap.stage_demand, max, ctx);
        var grid = el('div', 'rd-grid');
        kachel(grid, 'Eigene Kapazität pro Tag', zahl(ctx, cap.capacity_per_day));
        kachel(grid, 'Lastwagen-Kapazität', zahl(ctx, cap.truck_capacity));
        kachel(grid, 'Auslastung letztes Jahr', prozent(ctx, cap.utilization_last_year));
        kachel(grid, 'Lager', zahl(ctx, cap.inventory));
        kachel(grid, 'Rückstand', zahl(ctx, cap.backlog));
        kachel(grid, 'Lagerreichweite', zahl(ctx, cap.days_of_stock) + ' Tage');
        block.appendChild(grid);
      }

      var suppliers = r[1];
      if (!suppliers) fehlerBlock(root, 'Lieferanten');
      else {
        var sb = abschnitt(root, 'Lieferanten');
        var candidates = array(suppliers.candidates);
        var current = array(suppliers.current).map(String);
        sb.appendChild(tabelle([
          { key: 'name', label: 'Name', value: function (s) {
            return (current.indexOf(String(s.id)) >= 0 ? '✓ ' : '') + wert(s, 'name', '–');
          } },
          { key: 'region', label: 'Region' },
          { key: 'price', label: 'Preis', value: function (s) { return (ctx.preis ? ctx.preis(s.price) : geld(ctx, s.price)); } },
          { key: 'quality', label: 'Qualität', value: function (s) { return s.quality ? Math.round(s.quality * 100) + ' %' : '–'; } },
          { key: 'reliability', label: 'Zuverlässigkeit', value: function (s) { return s.reliability ? Math.round(s.reliability * 100) + ' %' : '–'; } },
          { key: 'reputation', label: 'Ruf', value: function (s) { return zahl(ctx, s.reputation); } },
          { key: 'lead_time_days', label: 'Lieferzeit in Tagen', value: function (s) {
            var tage = s.lead_time_days !== undefined && s.lead_time_days !== null ? s.lead_time_days : s.lead_time;
            return tage === undefined || tage === null ? '–' : zahl(ctx, tage);
          } }
        ], candidates));

        var label = el('label', 'rd-form');
        label.appendChild(document.createTextNode('Lieferant wählen '));
        var select = el('select');
        [
          ['', 'Automatisch'],
          ['price', 'Immer günstigster'],
          ['quality', 'Beste Qualität'],
          ['reliability', 'Zuverlässigster'],
          ['lead_time', 'Schnellster']
        ].forEach(function (pair) {
          var option = el('option', '', pair[1]);
          option.value = pair[0];
          select.appendChild(option);
        });
        candidates.forEach(function (candidate) {
          var option = el('option', '', 'Fester Lieferant: ' + wert(candidate, 'name', '–'));
          option.value = 'id:' + candidate.id;
          select.appendChild(option);
        });
        if (suppliers.fixed !== undefined && suppliers.fixed !== null) select.value = 'id:' + suppliers.fixed;
        else select.value = suppliers.rule || '';
        select.addEventListener('change', function () {
          if (select.value.indexOf('id:') === 0) {
            ctx.entscheide({ supplier_rule: null, supplier_id: select.value.slice(3) });
          } else if (select.value) {
            ctx.entscheide({ supplier_rule: select.value, supplier_id: null });
          } else {
            ctx.entscheide({ supplier_rule: null, supplier_id: null });
          }
        });
        label.appendChild(select);
        sb.appendChild(label);
        textZeile(sb, 'Du kannst einen Lieferanten fest wählen oder eine Regel vorgeben. Automatisch wählt die Simulation passend.');

        // Sortiment pro Getränkeart (nur Handelsfirmen) mit Preisvergleich der Lieferanten.
        var branche = ctx.state && ctx.state.firm ? ctx.state.firm.branch : '';
        if (branche !== 'hersteller' && typeof window.zeichneSortiment === 'function') {
          var sortimentHalter = el('div');
          root.appendChild(sortimentHalter);
          sortimentPromise = window.zeichneSortiment(sortimentHalter, ctx, candidates);
        }
      }

      var trucks = r[2];
      if (!trucks) fehlerBlock(root, 'Lastwagen');
      else {
        var tb = abschnitt(root, 'Lastwagen-Angebote');
        var offers = array(trucks.offers);
        var table = el('div', 'rd-scroll');
        var rows = offers.map(function (offer) {
          return {
            offer: offer,
            label: wert(offer, 'label', wert(offer, 'type', '–')),
            capacity: zahl(ctx, offer.capacity),
            price: geld(ctx, offer.price),
            annual_cost: geld(ctx, offer.annual_cost),
            life_years: zahl(ctx, offer.life_years),
            extra_sales: offer.extra_sales_per_day === undefined || offer.extra_sales_per_day === null
              ? '–' : zahl(ctx, offer.extra_sales_per_day) + ' Flaschen',
            extra_profit: offer.extra_profit_year === undefined || offer.extra_profit_year === null
              ? '–' : geld(ctx, offer.extra_profit_year),
            payback: offer.extra_profit_year === undefined && offer.payback_years === undefined
              ? '–'
              : (offer.payback_years === null || offer.payback_years === undefined
                ? 'lohnt sich nie' : zahl(ctx, offer.payback_years, 1) + ' Jahre'),
            advice: offer.advice || ''
          };
        });
        var columns = [
          { key: 'label', label: 'Typ' }, { key: 'capacity', label: 'Kapazität' },
          { key: 'price', label: 'Preis' }, { key: 'annual_cost', label: 'Jahreskosten' },
          { key: 'life_years', label: 'Lebensdauer' },
          { key: 'extra_sales', label: 'Mehr Absatz pro Tag' },
          { key: 'extra_profit', label: 'Mehr Gewinn pro Jahr', value: function (row) {
            var n = Number(row.offer.extra_profit_year);
            return Number.isFinite(n) ? el('span', n >= 0 ? 'rd-positiv' : 'rd-negativ', row.extra_profit) : row.extra_profit;
          } },
          { key: 'payback', label: 'Amortisation' },
          { key: 'advice', label: 'Rat' },
          { key: 'offer', label: 'Aktion', value: function (row) {
            var actions = el('span');
            ['buy', 'lease'].forEach(function (mode) {
              if (mode === 'lease' && !row.offer.lease_possible) return;
              var button = el('button', '', mode === 'buy' ? 'Kaufen' : 'Leasen');
              button.type = 'button';
              button.addEventListener('click', function () {
                var verb = mode === 'buy' ? 'kaufen' : 'leasen';
                var frage = row.label + ' ' + verb + '?';
                if (Number(row.offer.extra_sales_per_day) === 0 && row.offer.extra_sales_per_day !== null) {
                  frage = (row.offer.advice ? row.offer.advice + '\n\n' : 'Dieser Lastwagen erhöht deinen Absatz nicht.\n\n') +
                    'Trotzdem ' + row.label + ' ' + verb + '?';
                }
                if (window.confirm(frage)) {
                  ctx.plane('truck', { type: row.offer.type, mode: mode });
                  ctx.neuZeichnen();
                }
              });
              actions.appendChild(button);
            });
            return actions;
          } }
        ];
        table.appendChild(tabelle(columns, rows));
        tb.appendChild(table);
        var fleet = abschnitt(root, 'Eigene Flotte');
        fleet.appendChild(tabelle([
          { key: 'type', label: 'Typ' },
          { key: 'age_years', label: 'Alter', value: function (f) { return zahl(ctx, f.age_years); } },
          { key: 'value', label: 'Wert', value: function (f) { return geld(ctx, f.value); } }
        ], array(trucks.fleet)));
        textZeile(fleet, 'Transportmodus: ' + (trucks.transport_mode || '–'));
      }
      return sortimentPromise;
    });
  }

  REITER.logistik = { async render(elm, ctx) { return logistikRender(elm, ctx); } };

  function finanzenRender(elm, ctx) {
    var root = container(elm);
    var planned;
    try { planned = (ctx.geplant && ctx.geplant()) || {}; } catch (e) { planned = {}; }
    planBox(root, ctx, 'loan', planned.loan ? 'Kredit über ' + geld(ctx, planned.loan.amount) : '');

    return Promise.all([laden(ctx, 'macro'), laden(ctx, 'banks', { amount: kreditBetrag })]).then(function (r) {
      var macro = r[0];
      if (!macro) fehlerBlock(root, 'Wirtschaftslage');
      else {
        var mb = abschnitt(root, 'Wirtschaftslage');
        var grid = el('div', 'rd-grid');
        kachel(grid, 'Leitzins', prozent(ctx, macro.policy_rate));
        kachel(grid, 'Teuerung', prozent(ctx, macro.inflation));
        var fx = zahl(ctx, macro.fx_rate, 3);
        kachel(grid, 'Wechselkurs', fx === '–' ? zahl(ctx, macro.fx_rate) : fx);
        kachel(grid, 'Preisindex', zahl(ctx, macro.price_index));
        mb.appendChild(grid);
        var history = array(macro.history);
        if (history.length) {
          var labels = history.map(function (item) { return item.label; });
          linien(mb, ctx, [
            { name: 'Leitzins', werte: history.map(function (item) { return item.policy_rate; }), farbe: 'var(--akzent)' },
            { name: 'Teuerung', werte: history.map(function (item) { return item.inflation; }), farbe: 'var(--positiv)' }
          ], { labels: labels, hoehe: 180 });
          linien(mb, ctx, [
            { name: 'Wechselkurs', werte: history.map(function (item) { return item.fx_rate; }), farbe: 'var(--text-leise)' }
          ], { labels: labels, hoehe: 180 });
        } else textZeile(mb, 'Keine Verlaufsdaten', 'rd-leise');
      }

      var banks = r[1];
      if (!banks) fehlerBlock(root, 'Banken');
      else {
        var bb = abschnitt(root, 'Banken');
        bb.appendChild(tabelle([
          { key: 'name', label: 'Name' },
          { key: 'margin', label: 'Marge', value: function (b) { return prozent(ctx, b.margin); } },
          { key: 'equity', label: 'Eigenkapital', value: function (b) { return geld(ctx, b.equity); } },
          { key: 'capital_ratio', label: 'Eigenkapitalquote', value: function (b) { return prozent(ctx, b.capital_ratio); } },
          { key: 'active', label: 'Aktiv', value: function (b) { return b.active ? 'Ja' : 'Nein'; } }
        ], array(banks.banks)));
        var loans = abschnitt(root, 'Eigene Kredite');
        loans.appendChild(tabelle([
          { key: 'bank', label: 'Bank' }, { key: 'amount', label: 'Betrag', value: function (l) { return geld(ctx, l.amount); } },
          { key: 'rate', label: 'Zins', value: function (l) { return prozent(ctx, l.rate); } },
          { key: 'years', label: 'Laufzeit Jahre', value: function (l) { return zahl(ctx, l.years); } },
          { key: 'remaining', label: 'Restschuld', value: function (l) { return geld(ctx, l.remaining); } },
          { key: 'purpose', label: 'Zweck' }
        ], array(banks.loans)));
        var accounts = abschnitt(root, 'Kontoverteilung');
        var entries = Object.entries(banks.accounts || {});
        var max = Math.max.apply(null, entries.map(function (pair) { return zahlRoh(pair[1]); }).concat([1]));
        entries.forEach(function (pair) { balken(accounts, pair[0], prozent(ctx, pair[1]), zahlRoh(pair[1]) / max * 100); });
        textZeile(accounts, 'Kreditlimite: ' + geld(ctx, banks.credit_limit));

        var calc = abschnitt(root, 'Kreditrechner');
        var form = el('div', 'rd-form');
        var label = el('label', '', 'Betrag');
        var input = el('input');
        input.type = 'number';
        input.min = '0';
        input.step = '1000';
        input.value = String(kreditBetrag);
        input.addEventListener('input', function () {
          kreditBetrag = Math.max(0, zahlRoh(input.value));
        });
        label.appendChild(input);
        form.appendChild(label);
        var button = el('button', '', 'Angebote anzeigen');
        button.type = 'button';
        form.appendChild(button);
        calc.appendChild(form);
        var offerArea = el('div');
        calc.appendChild(offerArea);
        function zeigeAngebote(data) {
          offerArea.replaceChildren();
          if (!data || !Array.isArray(data.offers) || !data.offers.length) {
            textZeile(offerArea, data ? 'Keine Daten' : 'Daten nicht verfuegbar', 'rd-leise');
            return;
          }
          var list = el('div', 'rd-tabelle');
          data.offers.forEach(function (offer) {
            var row = el('div', 'rd-kachel');
            row.appendChild(el('strong', '', offer.bank + ' · ' + prozent(ctx, offer.rate) + ' · ' + zahl(ctx, offer.years) + ' Jahre'));
            if (offer.ok === false) {
              row.appendChild(el('p', 'rd-negativ', offer.reason || 'Nicht verfügbar'));
            } else {
              row.appendChild(el('p', '', 'Angebot verfügbar'));
              var take = el('button', '', 'Kredit aufnehmen');
              take.type = 'button';
              take.addEventListener('click', function () {
                if (window.confirm('Kredit über ' + geld(ctx, kreditBetrag) + ' bei ' + offer.bank + ' aufnehmen?')) {
                  ctx.plane('loan', { amount: kreditBetrag, bank_id: offer.bank_id });
                  ctx.neuZeichnen();
                }
              });
              row.appendChild(take);
            }
            list.appendChild(row);
          });
          offerArea.appendChild(list);
        }
        zeigeAngebote(banks);
        button.addEventListener('click', function () {
          kreditBetrag = Math.max(0, zahlRoh(input.value));
          offerArea.replaceChildren();
          laden(ctx, 'banks', { amount: kreditBetrag }).then(zeigeAngebote).then(function (data) {
            if (!data) {
              offerArea.replaceChildren();
              textZeile(offerArea, 'Daten nicht verfuegbar', 'rd-leise');
            }
          });
        });
      }
    });
  }

  REITER.finanzen = { async render(elm, ctx) { return finanzenRender(elm, ctx); } };

  function boerseRender(elm, ctx) {
    var root = container(elm);
    var planned;
    try { planned = (ctx.geplant && ctx.geplant()) || {}; } catch (e) { planned = {}; }
    var listedCache = [];
    var depotCache = [];
    function aktienPlanText(stockPlan) {
      if (!stockPlan) return '';
      var parts = [];
      [['buy', 'Kaufen'], ['sell', 'Verkaufen']].forEach(function (pair) {
        var positions = stockPlan[pair[0]] || {};
        Object.keys(positions).forEach(function (id) {
          var company = listedCache.find(function (x) { return String(x.id) === String(id); }) ||
            depotCache.find(function (x) { return String(x.id) === String(id); });
          parts.push(pair[1] + ': ' + (company ? company.name : id) + ' × ' + zahl(ctx, positions[id]));
        });
      });
      return parts.length ? parts.join(', ') : 'Aktienauftrag';
    }
    planBox(root, ctx, 'stock', aktienPlanText(planned.stock));
    return laden(ctx, 'stocks').then(function (data) {
      if (!data) {
        fehlerBlock(root, 'Börse');
        return;
      }
      listedCache = array(data.listed);
      depotCache = array(data.depot);
      if (data.note) {
        var hinweisBox = el('div', 'rd-plan boerse-hinweis', '');
        hinweisBox.setAttribute('role', 'note');
        hinweisBox.appendChild(el('strong', '', String(data.note)));
        root.appendChild(hinweisBox);
      }
      var block = abschnitt(root, 'Börse');
      var rows = listedCache;
      block.appendChild(tabelle([
        { key: 'name', label: 'Name' },
        { key: 'branch', label: 'Branche' },
        { key: 'price', label: 'Kurs', value: function (s) { return (ctx.preis ? ctx.preis(s.price) : geld(ctx, s.price)); } },
        { key: 'change', label: 'Änderung', value: function (s) {
          var span = el('span', zahlRoh(s.change) >= 0 ? 'rd-positiv' : 'rd-negativ', prozent(ctx, s.change));
          return span;
        } },
        { key: 'market_cap', label: 'Börsenwert', value: function (s) { return geld(ctx, s.market_cap); } },
        { key: 'history', label: 'Verlauf', value: function (s) {
          var points = array(s.history);
          var svg = svgEl('svg');
          svg.setAttribute('class', 'rd-mini');
          svg.setAttribute('width', '90');
          svg.setAttribute('height', '24');
          svg.setAttribute('viewBox', '0 0 90 24');
          if (points.length) {
            var nums = points.map(zahlRoh);
            var lo = Math.min.apply(null, nums);
            var hi = Math.max.apply(null, nums);
            var coords = nums.map(function (v, i) {
              var x = nums.length < 2 ? 45 : i * 88 / (nums.length - 1) + 1;
              var y = hi === lo ? 12 : 22 - (v - lo) / (hi - lo) * 20;
              return x + ',' + y;
            }).join(' ');
            var poly = svgEl('polyline');
            poly.setAttribute('points', coords);
            poly.setAttribute('fill', 'none');
            poly.style.stroke = 'var(--akzent)';
            poly.setAttribute('stroke-width', '2');
            svg.appendChild(poly);
          }
          return svg;
        } }
      ], rows));
      var indexBlock = abschnitt(root, 'Marktindex');
      var grid = el('div', 'rd-grid');
      kachel(grid, 'Index', zahl(ctx, data.index));
      indexBlock.appendChild(grid);
      var indexVerlauf = array(data.index_history);
      if (indexVerlauf.length) {
        linien(indexBlock, ctx, [{
          name: 'Index',
          werte: indexVerlauf.map(function (p) { return p.value; }),
          farbe: 'var(--akzent)',
          format: 'zahl'
        }], { labels: indexVerlauf.map(function (p) { return p.label; }), hoehe: 200, format: 'zahl' });
      } else {
        textZeile(indexBlock, 'Noch kein Indexverlauf.', 'rd-leise');
      }

      var selected = listedCache.find(function (s) { return String(s.id) === String(aktienAuswahl); });
      if (selected) {
        var detail = abschnitt(root, selected.name);
        textZeile(detail, 'Kursverlauf');
        linien(detail, ctx, [{ name: selected.name, werte: array(selected.history), farbe: 'var(--akzent)' }], { hoehe: 180 });
        var form = el('div', 'rd-form');
        var label = el('label', '', 'Anzahl');
        var input = el('input');
        input.type = 'number';
        input.min = '1';
        input.step = '1';
        input.value = String(aktienAnzahl);
        input.addEventListener('input', function () {
          aktienAnzahl = Math.max(1, Math.floor(zahlRoh(input.value)));
          kostenText.textContent = kostenBeschreibung();
        });
        label.appendChild(input);
        form.appendChild(label);
        var fee = zahlRoh(data.fee);
        var kostenText = el('span');
        function kostenBeschreibung() {
          var n = Math.max(1, Math.floor(zahlRoh(input.value)));
          var price = zahlRoh(selected.price);
          return 'Kosten inkl. Gebühr: ' + geld(ctx, n * price * (1 + fee)) +
            ' · Erlös abzgl. Gebühr: ' + geld(ctx, n * price * (1 - fee)) +
            ' · Gebühr: ' + prozent(ctx, fee);
        }
        kostenText.textContent = kostenBeschreibung();
        form.appendChild(kostenText);
        ['buy', 'sell'].forEach(function (mode) {
          var button = el('button', '', mode === 'buy' ? 'Kaufen' : 'Verkaufen');
          button.type = 'button';
          button.addEventListener('click', function () {
            var count = Math.max(1, Math.floor(zahlRoh(input.value)));
            var depotItem = depotCache.find(function (d) { return String(d.id) === String(selected.id); });
            if (mode === 'sell' && (!depotItem || count > zahlRoh(depotItem.shares))) {
              window.alert('Du kannst nicht mehr Aktien verkaufen als du im Depot hast.');
              return;
            }
            var action = mode === 'buy' ? 'Kauf' : 'Verkauf';
            if (!window.confirm(action + ' von ' + count + ' Aktien von ' + selected.name + '?')) return;
            var current = {};
            try {
              current = (ctx.geplant() || {}).stock || {};
            } catch (e) {
              current = {};
            }
            var next = { buy: Object.assign({}, current.buy || {}), sell: Object.assign({}, current.sell || {}) };
            var key = mode;
            next[key][selected.id] = zahlRoh(next[key][selected.id]) + count;
            if (!next[key][selected.id]) delete next[key][selected.id];
            if (!Object.keys(next.buy).length) delete next.buy;
            if (!Object.keys(next.sell).length) delete next.sell;
            ctx.plane('stock', Object.keys(next).length ? next : null);
            ctx.neuZeichnen();
          });
          form.appendChild(button);
        });
        detail.appendChild(form);
      } else {
        textZeile(block, 'Wähle eine Firma in der Tabelle für den Kursverlauf und den Aktienhandel.', 'rd-note');
      }

      var depot = abschnitt(root, 'Eigenes Depot');
      var positions = depotCache;
      depot.appendChild(tabelle([
        { key: 'name', label: 'Name' },
        { key: 'shares', label: 'Anzahl', value: function (p) { return zahl(ctx, p.shares); } },
        { key: 'price', label: 'Kurs', value: function (p) { return geld(ctx, p.price); } },
        { key: 'value', label: 'Wert', value: function (p) { return geld(ctx, p.value); } },
        { key: 'paid', label: 'Bezahlt', value: function (p) { return geld(ctx, p.paid); } },
        { key: 'gain', label: 'Gewinn/Verlust', value: function (p) {
          return el('span', zahlRoh(p.gain) >= 0 ? 'rd-positiv' : 'rd-negativ', geld(ctx, p.gain));
        } }
      ], positions));
      var total = positions.reduce(function (sum, p) { return sum + zahlRoh(p.value); }, 0);
      textZeile(depot, 'Depotwert gesamt: ' + geld(ctx, total));
      textZeile(depot, 'Beim Verkauf kannst du nicht mehr Aktien verkaufen als du im Depot hast.', 'rd-note');

      block.querySelectorAll('tbody tr').forEach(function (row, i) {
        row.tabIndex = 0;
        row.addEventListener('click', function () {
          aktienAuswahl = rows[i] && rows[i].id;
          boerseRender(elm, ctx);
        });
      });
    });
  }

  REITER.boerse = { async render(elm, ctx) { return boerseRender(elm, ctx); } };

  function rohstoffeRender(elm, ctx) {
    var root = container(elm);
    return laden(ctx, 'commodities').then(function (data) {
      if (!data) {
        fehlerBlock(root, 'Rohstoffe');
        return;
      }
      var current = abschnitt(root, 'Aktuelle Rohstoffpreise');
      var rows = array(data.current);
      if (rows.length) {
        var grid = el('div', 'rd-grid');
        rows.forEach(function (item) {
          var box = el('div', 'rd-kachel');
          box.appendChild(el('span', 'rd-leise', item.name || '–'));
          box.appendChild(el('strong', '', zahl(ctx, item.index)));
          box.appendChild(el('span', zahlRoh(item.change) >= 0 ? 'rd-positiv' : 'rd-negativ', prozent(ctx, item.change)));
          grid.appendChild(box);
        });
        current.appendChild(grid);
      } else textZeile(current, 'Keine Daten');
      var electricity = abschnitt(root, 'Strom');
      kachel(electricity, 'Strompreisindex', zahl(ctx, data.electricity));

      var historyBlock = abschnitt(root, 'Rohstoffverlauf');
      var history = array(data.history);
      if (!history.length) textZeile(historyBlock, 'Keine Daten');
      else {
        var names = Object.keys(history[0] || {}).filter(function (key) { return key !== 'label'; });
        var colors = ['var(--akzent)', 'var(--positiv)', 'var(--negativ)', 'var(--text-leise)', 'var(--rd-farbe-5)', 'var(--rd-farbe-6)', 'var(--rd-farbe-7)', 'var(--rd-farbe-8)'];
        var series = names.map(function (name, i) {
          return { name: name, werte: history.map(function (item) { return item[name]; }), farbe: colors[i % colors.length] };
        });
        legende(historyBlock, series);
        linien(historyBlock, ctx, series, { labels: history.map(function (item) { return item.label; }), hoehe: 220 });
      }
      erklaerung(root, 'Was bedeutet Vorkauf?', 'Du kannst Rohstoffe vor Preisanstiegen im Voraus einkaufen und lagern. Das spart bei steigenden Preisen, kostet aber Lagerplatz und Kapital und lohnt sich nicht, wenn die Preise fallen. Mutiger Vorkauf bedeutet höheres Risiko.');
    });
  }

  REITER.rohstoffe = { async render(elm, ctx) { return rohstoffeRender(elm, ctx); } };

  function regionName(name) {
    var map = {
      genfersee: 'Genfersee',
      jura_freiburg: 'Jura/Freiburg',
      zuerich: 'Zürich',
      zentralschweiz: 'Zentralschweiz'
    };
    if (map[name]) return map[name];
    return String(name || '').replace(/_/g, ' ').replace(/^./, function (c) { return c.toLocaleUpperCase('de'); });
  }

  function swissMap(parent, data, ctx) {
    var block = abschnitt(parent, 'Schweizer Karte');
    var outline = array(data.outline);
    var regions = array(data.regions);
    var firms = array(data.firms).filter(function (firm) {
      return !bevoelkerungsStufe || String(firm.stage) === String(bevoelkerungsStufe);
    });
    var coords = outline.concat(regions.map(function (r) { return [r.x, r.y]; }));
    if (!coords.length) {
      textZeile(block, 'Keine Daten');
      return;
    }
    var xs = coords.map(function (p) { return zahlRoh(p[0]); });
    var ys = coords.map(function (p) { return zahlRoh(p[1]); });
    var xmin = Math.min.apply(null, xs), xmax = Math.max.apply(null, xs);
    var ymin = Math.min.apply(null, ys), ymax = Math.max.apply(null, ys);
    var width = 760, height = 420, margin = 24;
    var scale = Math.min((width - margin * 2) / Math.max(1, xmax - xmin), (height - margin * 2) / Math.max(1, ymax - ymin));
    var usedW = (xmax - xmin) * scale, usedH = (ymax - ymin) * scale;
    var offX = (width - usedW) / 2, offY = (height - usedH) / 2;
    function point(x, y) {
      return [offX + (x - xmin) * scale, offY + (ymax - y) * scale];
    }
    var svg = svgEl('svg');
    svg.setAttribute('class', 'rd-map');
    svg.setAttribute('viewBox', '0 0 760 420');
    if (outline.length) {
      var polygon = svgEl('polygon');
      polygon.setAttribute('points', outline.map(function (p) { return point(p[0], p[1]).join(','); }).join(' '));
      polygon.style.fill = 'color-mix(in srgb, var(--akzent) 14%, transparent)';
      polygon.style.stroke = 'var(--akzent)';
      polygon.setAttribute('stroke-width', '2');
      svg.appendChild(polygon);
    }
    var regionByName = {};
    regions.forEach(function (region) {
      regionByName[region.name] = region;
      var p = point(zahlRoh(region.x), zahlRoh(region.y));
      var circle = svgEl('circle');
      circle.setAttribute('cx', p[0]);
      circle.setAttribute('cy', p[1]);
      circle.setAttribute('r', String(Math.max(5, Math.sqrt(Math.max(0, zahlRoh(region.share))) * 18)));
      circle.style.fill = 'var(--akzent)';
      circle.setAttribute('fill-opacity', '.3');
      svg.appendChild(circle);
      var label = svgEl('text');
      label.setAttribute('x', p[0] + 7);
      label.setAttribute('y', p[1] - 5);
      label.textContent = regionName(region.name);
      svg.appendChild(label);
    });
    var groups = {};
    firms.forEach(function (firm) {
      var key = firm.region || '';
      if (!groups[key]) groups[key] = [];
      groups[key].push(firm);
    });
    Object.keys(groups).forEach(function (key) {
      var region = regionByName[key];
      if (!region) return;
      var center = point(zahlRoh(region.x), zahlRoh(region.y));
      groups[key].forEach(function (firm, i) {
        var angle = i * 2.399963229728653;
        var distance = 10 + Math.floor(i / 8) * 5;
        var circle = svgEl('circle');
        circle.setAttribute('cx', center[0] + Math.cos(angle) * distance);
        circle.setAttribute('cy', center[1] + Math.sin(angle) * distance);
        circle.setAttribute('r', firm.is_player ? '7' : firm.is_daughter ? '5' : '3');
        circle.style.fill = firm.is_player ? 'var(--akzent)' : firm.is_daughter ? 'var(--positiv)' : 'var(--text-leise)';
        circle.style.stroke = firm.is_player ? 'var(--rand)' : 'none';
        var title = svgEl('title');
        title.textContent = [firm.name, firm.branch, firm.stage].filter(Boolean).join(' · ');
        circle.appendChild(title);
        svg.appendChild(circle);
      });
    });
    block.appendChild(svg);

    var filter = el('label', 'rd-form');
    filter.appendChild(document.createTextNode('Stufe '));
    var select = el('select');
    var all = el('option', '', 'Alle');
    all.value = '';
    select.appendChild(all);
    Array.from(new Set(array(data.firms).map(function (f) { return f.stage; }).filter(function (s) { return s !== null && s !== undefined; })))
      .forEach(function (stage) {
        var option = el('option', '', String(stage));
        option.value = String(stage);
        select.appendChild(option);
      });
    select.value = bevoelkerungsStufe;
    select.addEventListener('change', function () {
      bevoelkerungsStufe = select.value;
      bevoelkerungRender(parent.parentNode || parent, ctx);
    });
    filter.appendChild(select);
    block.appendChild(filter);
    var legend = el('div', 'rd-legende');
    [['var(--akzent)', 'Eigene Firma'], ['var(--positiv)', 'Tochter'], ['var(--text-leise)', 'Konkurrenz']].forEach(function (item) {
      var label = el('span');
      var dot = el('span', 'rd-punkt');
      dot.style.backgroundColor = item[0];
      label.appendChild(dot);
      label.appendChild(document.createTextNode(item[1]));
      legend.appendChild(label);
    });
    block.appendChild(legend);
  }

  function bevoelkerungRender(elm, ctx) {
    var root = container(elm);
    return Promise.all([laden(ctx, 'swiss_map'), laden(ctx, 'population')]).then(function (r) {
      if (!r[0]) fehlerBlock(root, 'Schweizer Karte');
      else swissMap(root, r[0], ctx);

      var data = r[1];
      if (!data) {
        fehlerBlock(root, 'Bevölkerung');
        return;
      }
      var block = abschnitt(root, 'Bevölkerung');
      var grid = el('div', 'rd-grid');
      kachel(grid, 'Personenzahl', zahl(ctx, data.persons));
      block.appendChild(grid);
      [
        { title: 'Altersgruppen', items: array(data.age_groups), name: 'group' },
        { title: 'Einkommensgruppen', items: array(data.income_levels), name: 'level' }
      ].forEach(function (group) {
        var section = abschnitt(root, group.title);
        var max = Math.max.apply(null, group.items.map(function (item) { return zahlRoh(item.persons); }).concat([1]));
        group.items.forEach(function (item) {
          balken(section, wert(item, group.name, '–'), zahl(ctx, item.persons), zahlRoh(item.persons) / max * 100);
        });
        if (!group.items.length) textZeile(section, 'Keine Daten');
      });
      var regions = abschnitt(root, 'Regionen');
      regions.appendChild(tabelle([
        { key: 'name', label: 'Name', value: function (r) { return regionName(r.name); } },
        { key: 'share', label: 'Anteil', value: function (r) { return prozent(ctx, r.share); } },
        { key: 'persons', label: 'Personen', value: function (r) { return zahl(ctx, r.persons); } }
      ], array(data.regions)));
    });
  }

  REITER.bevoelkerung = { async render(elm, ctx) { return bevoelkerungRender(elm, ctx); } };
}());
