'use strict';

(function () {
  var STIL = [
    '.rl-reihen{display:flex;flex-wrap:wrap;gap:.6rem;margin:.5rem 0}',
    '.rl-punkt{display:inline-block;width:.7rem;height:.7rem;border-radius:50%}'
  ].join('');

  if (typeof document !== 'undefined' && document.head && !document.getElementById('reiter-lager-stil')) {
    var stil = document.createElement('style');
    stil.id = 'reiter-lager-stil';
    stil.textContent = STIL;
    document.head.appendChild(stil);
  }

  var gewaehlteReihen = null;
  var palette = [
    '#2563eb', '#dc2626', '#16a34a', '#9333ea',
    '#ea580c', '#0891b2', '#c026d3', '#65a30d',
    '#4f46e5', '#be123c', '#0d9488', '#a16207'
  ];

  var REITER = window.REITER = window.REITER || {};

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function array(v) {
    return Array.isArray(v) ? v : [];
  }

  function zahlRoh(v) {
    var n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  function wert(obj, key, fallback) {
    if (!obj || obj[key] === undefined || obj[key] === null) return fallback;
    return obj[key];
  }

  function zahl(ctx, n, stellen) {
    var value = Number(n);
    if (!Number.isFinite(value)) return '–';
    try {
      if (ctx && typeof ctx.zahl === 'function') return ctx.zahl(value, stellen);
    } catch (e) {
      return String(value);
    }
    return String(value);
  }

  function geld(ctx, n) {
    var value = Number(n);
    if (!Number.isFinite(value)) return '–';
    try {
      if (ctx && typeof ctx.geld === 'function') return ctx.geld(value);
    } catch (e) {
      return String(value);
    }
    return String(value);
  }

  function preis(ctx, n) {
    var value = Number(n);
    if (!Number.isFinite(value)) return '–';
    try {
      if (ctx && typeof ctx.preis === 'function') return ctx.preis(value);
    } catch (e) {
      return geld(ctx, value);
    }
    return geld(ctx, value);
  }

  function prozent(ctx, n) {
    var value = Number(n);
    if (!Number.isFinite(value)) return '–';
    try {
      if (ctx && typeof ctx.prozent === 'function') return ctx.prozent(value);
    } catch (e) {
      return zahl(ctx, value * 100, 1) + ' %';
    }
    return zahl(ctx, value * 100, 1) + ' %';
  }

  function abschnitt(parent, titel) {
    var block = el('div', 'rd-block');
    block.appendChild(el('h3', '', titel));
    parent.appendChild(block);
    return block;
  }

  function tabelle(spalten, zeilen) {
    var wrap = el('div', 'rd-scroll');
    if (!zeilen.length) {
      wrap.appendChild(el('p', 'rd-leise', 'Keine Daten'));
      return wrap;
    }
    var table = el('table', 'rd-tabelle');
    var head = el('thead');
    var hr = el('tr');
    spalten.forEach(function (spalte) {
      hr.appendChild(el('th', '', spalte.label));
    });
    head.appendChild(hr);
    table.appendChild(head);

    var body = el('tbody');
    zeilen.forEach(function (zeile) {
      var tr = el('tr', zeile.klasse || '');
      spalten.forEach(function (spalte) {
        var td = el('td');
        var value = typeof spalte.value === 'function' ? spalte.value(zeile) : zeile[spalte.key];
        if (value && value.nodeType) td.appendChild(value);
        else td.textContent = value === undefined || value === null || value === '' ? '–' : String(value);
        tr.appendChild(td);
      });
      if (zeile._row) zeile._row(tr);
      body.appendChild(tr);
    });
    table.appendChild(body);
    wrap.appendChild(table);
    return wrap;
  }

  function kachel(parent, titel, inhalt, cls) {
    var box = el('div', 'rd-kachel');
    box.appendChild(el('span', 'rd-leise', titel));
    box.appendChild(el('strong', cls || '', inhalt));
    parent.appendChild(box);
    return box;
  }

  function hinweis(parent) {
    parent.appendChild(el('p', 'rd-leise', 'Noch nicht verfügbar'));
  }

  function formatReichweite(ctx, tage) {
    if (tage === null || tage === undefined) return '–';
    var wertTage = Number(tage);
    if (!Number.isFinite(wertTage) || wertTage >= 999) return '–';
    var span = el('span', wertTage < 1 ? 'rd-negativ' : wertTage > 30 ? 'rd-note' : '');
    span.textContent = zahl(ctx, wertTage);
    return span;
  }

  function reichweiteWert(stock, verbrauch) {
    var bestand = Number(stock);
    var abgang = Number(verbrauch);
    if (!Number.isFinite(bestand) || !Number.isFinite(abgang) || abgang <= 0) return null;
    return bestand / abgang;
  }

  function summe(zeilen, feld) {
    return zeilen.reduce(function (gesamt, zeile) {
      return gesamt + zahlRoh(zeile && zeile[feld]);
    }, 0);
  }

  function navigiereZuEinkauf() {
    if (window.location && window.location.hash === '#einkauf') return;
    window.location.hash = '#einkauf';
    try {
      if (typeof HashChangeEvent === 'function') {
        window.dispatchEvent(new HashChangeEvent('hashchange'));
      }
    } catch (e) {
      // Der Hash-Wechsel genügt auch ohne explizites Ereignis.
    }
  }

  function markenRender(root, ctx, data) {
    var block = abschnitt(root, 'Bestand je Marke');
    if (!data || !Array.isArray(data.brands)) {
      hinweis(block);
      return;
    }

    var brands = data.brands.filter(function (brand) {
      return brand && typeof brand === 'object';
    });
    var gruppen = [];
    var gruppenNachName = Object.create(null);

    brands.forEach(function (brand) {
      var art = String(wert(brand, 'category_name', wert(brand, 'category', 'Unbekannt')));
      var key = '$' + art;
      if (!gruppenNachName[key]) {
        gruppenNachName[key] = { art: art, brands: [] };
        gruppen.push(gruppenNachName[key]);
      }
      gruppenNachName[key].brands.push(brand);
    });

    gruppen.forEach(function (gruppe) {
      gruppe.brands.sort(function (a, b) {
        return String(wert(a, 'name', '')).localeCompare(String(wert(b, 'name', '')), 'de');
      });
    });

    var zeilen = [];
    gruppen.forEach(function (gruppe) {
      var unterzeilen = gruppe.brands.map(function (brand) {
        var button = el('button', '', 'Im Einkauf anpassen');
        button.type = 'button';
        button.addEventListener('click', navigiereZuEinkauf);
        return {
          marke: wert(brand, 'name', '–'),
          art: wert(brand, 'category_name', wert(brand, 'category', '–')),
          stock: brand.stock,
          in_transit: brand.in_transit,
          sales_per_day: brand.sales_per_day,
          days_of_cover: brand.days_of_cover,
          unit_price: brand.unit_price,
          value_chf: brand.value_chf,
          einkauf: button,
          brand: brand
        };
      });

      zeilen = zeilen.concat(unterzeilen);
      zeilen.push({
        marke: 'Zwischensumme ' + gruppe.art,
        art: '',
        stock: summe(gruppe.brands, 'stock'),
        in_transit: summe(gruppe.brands, 'in_transit'),
        sales_per_day: summe(gruppe.brands, 'sales_per_day'),
        value_chf: summe(gruppe.brands, 'value_chf'),
        days_of_cover: reichweiteWert(
          summe(gruppe.brands, 'stock'),
          summe(gruppe.brands, 'sales_per_day')
        ),
        fett: true
      });
    });

    zeilen.push({
      marke: 'Total',
      art: '',
      stock: summe(brands, 'stock'),
      in_transit: summe(brands, 'in_transit'),
      sales_per_day: summe(brands, 'sales_per_day'),
      value_chf: summe(brands, 'value_chf'),
      days_of_cover: reichweiteWert(
        summe(brands, 'stock'),
        summe(brands, 'sales_per_day')
      ),
      fett: true
    });

    zeilen.forEach(function (zeile) {
      zeile._row = function (tr) {
        if (zeile.fett) tr.style.fontWeight = '700';
      };
    });

    block.appendChild(tabelle([
      { key: 'marke', label: 'Marke' },
      { key: 'art', label: 'Getränkeart' },
      { key: 'stock', label: 'An Lager', value: function (row) { return zahl(ctx, row.stock); } },
      { key: 'in_transit', label: 'Unterwegs', value: function (row) { return zahl(ctx, row.in_transit); } },
      { key: 'sales_per_day', label: 'Verkauf/Tag', value: function (row) { return zahl(ctx, row.sales_per_day); } },
      { key: 'days_of_cover', label: 'Reichweite (Tage)', value: function (row) {
        return formatReichweite(ctx, row.days_of_cover);
      } },
      { key: 'unit_price', label: 'Einkaufspreis', value: function (row) {
        return row.fett ? '–' : preis(ctx, row.unit_price);
      } },
      { key: 'value_chf', label: 'Wert', value: function (row) {
        return geld(ctx, row.value_chf);
      } },
      { key: 'einkauf', label: 'Einkauf' }
    ], zeilen));
  }

  function rohstoffeRender(root, ctx, data) {
    var components = data && Array.isArray(data.components) ? data.components : null;
    if (!data || (data.kind !== 'hersteller' && (!components || !components.length))) return;

    var block = abschnitt(root, 'Rohstoffe');
    if (!components) {
      hinweis(block);
      return;
    }

    var rohstoffe = components.filter(function (component) {
      return component && typeof component === 'object';
    });
    var totalStock = summe(rohstoffe, 'stock');
    var totalUse = summe(rohstoffe, 'use_per_day');
    var zeilen = rohstoffe.map(function (component) {
      return {
        name: wert(component, 'name', '–'),
        stock: component.stock,
        use_per_day: component.use_per_day,
        days_of_cover: component.days_of_cover,
        price: component.price,
        value_chf: component.value_chf
      };
    });
    zeilen.push({
      name: 'Total',
      stock: totalStock,
      use_per_day: totalUse,
      days_of_cover: reichweiteWert(totalStock, totalUse),
      value_chf: summe(rohstoffe, 'value_chf'),
      fett: true,
      _row: function (tr) { tr.style.fontWeight = '700'; }
    });

    block.appendChild(tabelle([
      { key: 'name', label: 'Rohstoff' },
      { key: 'stock', label: 'An Lager', value: function (row) { return zahl(ctx, row.stock); } },
      { key: 'use_per_day', label: 'Verbrauch/Tag', value: function (row) { return zahl(ctx, row.use_per_day); } },
      { key: 'days_of_cover', label: 'Reichweite (Tage)', value: function (row) {
        return formatReichweite(ctx, row.days_of_cover);
      } },
      { key: 'price', label: 'Preis', value: function (row) {
        return row.fett ? '–' : preis(ctx, row.price);
      } },
      { key: 'value_chf', label: 'Wert', value: function (row) { return geld(ctx, row.value_chf); } }
    ], zeilen));
  }

  function verlaufRender(root, ctx, data) {
    var block = abschnitt(root, 'Lagerverlauf');
    var history = data && Array.isArray(data.history) ? data.history : [];
    if (!history.length) {
      block.appendChild(el('p', 'rd-leise', 'Der Verlauf erscheint nach der ersten Runde.'));
      return;
    }

    var reihen = [];
    var gesehen = Object.create(null);
    history.forEach(function (eintrag) {
      if (!eintrag || typeof eintrag !== 'object') return;
      Object.keys(eintrag).forEach(function (name) {
        if (name === 'label' || gesehen['$' + name]) return;
        gesehen['$' + name] = true;
        reihen.push(name);
      });
    });

    if (gewaehlteReihen === null) {
      gewaehlteReihen = reihen.slice();
    } else {
      gewaehlteReihen = gewaehlteReihen.filter(function (name) {
        return reihen.indexOf(name) >= 0;
      });
      reihen.forEach(function (name) {
        if (gewaehlteReihen.indexOf(name) < 0) gewaehlteReihen.push(name);
      });
    }

    var liste = el('div', 'rl-reihen');
    var diagrammBox = el('div');
    block.appendChild(liste);
    block.appendChild(diagrammBox);

    function zeichneDiagramm() {
      diagrammBox.replaceChildren();
      var serien = gewaehlteReihen.map(function (name) {
        var farbe = palette[reihen.indexOf(name) % palette.length];
        return {
          name: name,
          werte: history.map(function (eintrag) {
            if (!eintrag || eintrag[name] === undefined || eintrag[name] === null) return null;
            var value = Number(eintrag[name]);
            return Number.isFinite(value) ? value : null;
          }),
          farbe: farbe
        };
      });

      try {
        if (typeof diagramm === 'function') {
          var chart = diagramm(serien, {
            labels: history.map(function (eintrag) {
              return eintrag && eintrag.label !== undefined && eintrag.label !== null
                ? eintrag.label : '';
            }),
            hoehe: 280,
            format: 'ganz'
          });
          if (chart) diagrammBox.appendChild(chart);
          else hinweis(diagrammBox);
        } else if (typeof window.diagramm === 'function') {
          var windowChart = window.diagramm(serien, {
            labels: history.map(function (eintrag) {
              return eintrag && eintrag.label !== undefined && eintrag.label !== null
                ? eintrag.label : '';
            }),
            hoehe: 280,
            format: 'ganz'
          });
          if (windowChart) diagrammBox.appendChild(windowChart);
          else hinweis(diagrammBox);
        } else {
          hinweis(diagrammBox);
        }
      } catch (e) {
        hinweis(diagrammBox);
      }
    }

    reihen.forEach(function (name) {
      var label = el('label');
      var checkbox = el('input');
      checkbox.type = 'checkbox';
      checkbox.checked = gewaehlteReihen.indexOf(name) >= 0;
      checkbox.setAttribute('aria-label', name);
      var punkt = el('span', 'rl-punkt');
      punkt.style.backgroundColor = palette[reihen.indexOf(name) % palette.length];
      label.appendChild(checkbox);
      label.appendChild(punkt);
      label.appendChild(document.createTextNode(' ' + name));
      checkbox.addEventListener('change', function () {
        if (checkbox.checked) {
          if (gewaehlteReihen.indexOf(name) < 0) gewaehlteReihen.push(name);
        } else {
          gewaehlteReihen = gewaehlteReihen.filter(function (item) { return item !== name; });
        }
        zeichneDiagramm();
      });
      liste.appendChild(label);
    });

    if (!reihen.length) {
      block.appendChild(el('p', 'rd-leise', 'Der Verlauf erscheint nach der ersten Runde.'));
      return;
    }
    zeichneDiagramm();
  }

  function lagerAusbauenRender(root, ctx) {
    var block = abschnitt(root, 'Lager ausbauen');
    var choices = ctx && ctx.state && ctx.state.choices ? ctx.state.choices : {};
    var initial = choices.storage_order;
    var label = el('label', '', 'Lager ausbauen (Flaschen)');
    var input = el('input');
    input.type = 'number';
    input.min = '0';
    input.step = '1';
    input.setAttribute('aria-label', 'Lager ausbauen (Flaschen)');
    input.style.width = '8rem';
    input.value = initial === undefined || initial === null ? '' : String(initial);
    label.appendChild(input);

    var form = el('div', 'rd-form');
    form.appendChild(label);
    block.appendChild(form);
    block.appendChild(el('p', 'rd-note', 'Einmalige Kosten, der Ausbau steht ab dem nächsten Halt bereit.'));

    input.addEventListener('input', function () {
      var n = Math.max(0, zahlRoh(input.value));
      if (ctx && typeof ctx.entscheide === 'function') {
        ctx.entscheide({ storage_order: n > 0 ? n : null });
      }
    });
  }

  async function render(elm, ctx) {
    elm.replaceChildren();
    var root = el('div', 'rd-reiter');
    elm.appendChild(root);

    var d = null;
    try {
      if (ctx && typeof ctx.ansicht === 'function') d = await ctx.ansicht('inventory');
    } catch (e) {
      d = null;
    }

    var summary = d && d.summary && typeof d.summary === 'object' ? d.summary : null;
    var grid = el('div', 'rd-grid');
    if (!summary) {
      kachel(grid, 'Bestand (Flaschen)', '–');
      kachel(grid, 'Lagerwert', '–');
      kachel(grid, 'Platz belegt', '–');
      kachel(grid, 'Reichweite', '–');
      kachel(grid, 'Unterwegs', '–');
      root.appendChild(grid);
      hinweis(root);
    } else {
      var bottles = summary.bottles;
      var value = summary.value_chf;
      var used = summary.used;
      var capacity = summary.capacity;
      var usedValue = Number(used);
      var capacityValue = Number(capacity);
      var belegung = Number.isFinite(usedValue) && Number.isFinite(capacityValue) && capacityValue > 0
        ? zahl(ctx, used) + ' von ' + zahl(ctx, capacity) + ' (' + prozent(ctx, usedValue / capacityValue) + ')'
        : zahl(ctx, used) + ' von ' + zahl(ctx, capacity);
      var cover = Number(summary.days_of_cover);
      kachel(grid, 'Bestand (Flaschen)', zahl(ctx, bottles));
      kachel(grid, 'Lagerwert', geld(ctx, value));
      kachel(grid, 'Platz belegt', belegung);
      kachel(grid, 'Reichweite', Number.isFinite(cover) && cover >= 999
        ? '–' : zahl(ctx, summary.days_of_cover) + ' Tage');
      kachel(grid, 'Unterwegs', zahl(ctx, summary.in_transit));
      root.appendChild(grid);
    }

    var warnings = array(d && d.warnings).filter(function (warning) {
      return warning && typeof warning === 'object';
    });
    if (warnings.length) {
      var warnungenBlock = abschnitt(root, 'Warnungen');
      warnings.forEach(function (warning) {
        warnungenBlock.appendChild(el(
          'p',
          warning.level === 'rot' ? 'rd-negativ' : warning.level === 'gelb' ? 'rd-note' : '',
          wert(warning, 'text', '')
        ));
      });
    }

    markenRender(root, ctx, d);
    rohstoffeRender(root, ctx, d);
    verlaufRender(root, ctx, d);
    lagerAusbauenRender(root, ctx);
  }

  REITER.lager = { async render(elm, ctx) { return render(elm, ctx); } };
}());
