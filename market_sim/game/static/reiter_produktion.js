'use strict';

(function () {
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

  function textZeile(parent, text, cls) {
    parent.appendChild(el('p', cls || '', text));
  }

  function hinweis(parent) {
    textZeile(parent, 'Noch nicht verfügbar', 'rd-leise');
  }

  function laden(ctx, name) {
    return Promise.resolve().then(function () {
      if (!ctx || typeof ctx.ansicht !== 'function') return null;
      return ctx.ansicht(name);
    }).catch(function () {
      return null;
    });
  }

  function eingabefeld(labelText, wertText, min, step) {
    var label = el('label', '', labelText);
    var input = el('input', 're-eingabe');
    input.type = 'number';
    input.min = String(min);
    input.step = String(step);
    input.value = wertText === null || wertText === undefined ? '' : String(wertText);
    input.setAttribute('aria-label', labelText);
    label.appendChild(input);
    return { label: label, input: input };
  }

  function sende(ctx, entscheidung) {
    try {
      if (ctx && typeof ctx.entscheide === 'function') ctx.entscheide(entscheidung);
    } catch (e) {
      // Eine fehlgeschlagene Entscheidung soll die Anzeige nicht blockieren.
    }
  }

  function rohstoffText(name) {
    try {
      if (typeof rohstoffName === 'function') return rohstoffName(name);
    } catch (e) {
      return String(name);
    }
    return String(name);
  }

  function entwurfPreis() {
    if (typeof entwurfEinstellungen !== 'undefined' &&
        entwurfEinstellungen &&
        typeof entwurfEinstellungen === 'object' &&
        entwurfEinstellungen.base_price !== null &&
        entwurfEinstellungen.base_price !== undefined) {
      return entwurfEinstellungen.base_price;
    }
    return undefined;
  }

  function schreibeEntwurfPreis(value) {
    if (typeof entwurfEinstellungen === 'object' &&
        entwurfEinstellungen &&
        Number.isFinite(value)) {
      entwurfEinstellungen.base_price = value;
    }
  }

  function productionRender(root, ctx, data, marketing) {
    var block = abschnitt(root, 'Produktion heute');
    if (!data) {
      hinweis(block);
      return;
    }

    var capacity = data.capacity_per_day;
    var producible = data.producible_per_day;
    var stock = data.stock_bottles;
    var days = data.days_of_cover;
    var raster = el('div', 're-raster');
    kachel(raster, 'Kapazität pro Tag (max)', zahl(ctx, capacity) + ' Flaschen');
    kachel(
      raster,
      'Heute produzierbar (Rohstoffe)',
      zahl(ctx, producible) + ' Flaschen',
      zahlRoh(producible) < zahlRoh(capacity) ? 'rd-negativ' : ''
    );
    kachel(raster, 'Bestellungen der Kunden pro Tag', zahl(ctx, data.orders_per_day) + ' Flaschen');
    kachel(raster, 'Lager / Reichweite', zahl(ctx, stock) + ' Flaschen · ' + zahl(ctx, days) + ' Tage');
    block.appendChild(raster);
    textZeile(block, 'Produziert wird jeden Tag so viel, wie Kapazität und Rohstofflager zulassen.', 'rd-note');

    var materialBlock = abschnitt(root, 'Rohstoffe');
    var materials = array(data.materials);
    var choices = ctx && ctx.state && ctx.state.choices ? ctx.state.choices : {};
    var componentChoices = choices.component_plan && typeof choices.component_plan === 'object'
      ? choices.component_plan : {};
    var inputs = {};

    materials.forEach(function (material) {
      var name = String(material && material.name !== undefined ? material.name : '');
      var initial = componentChoices[name] !== undefined && componentChoices[name] !== null
        ? componentChoices[name]
        : Math.round(zahlRoh(material && material.need_per_day_at_capacity));
      inputs[name] = eingabefeld(
        'Bestellmenge ' + rohstoffText(name),
        initial,
        0,
        1
      ).input;
    });

    function aktuellerPlan() {
      var plan = {};
      materials.forEach(function (material) {
        var name = String(material && material.name !== undefined ? material.name : '');
        plan[name] = Math.max(0, zahlRoh(inputs[name] && inputs[name].value));
      });
      return plan;
    }

    var bestellkosten = el('p');
    materialBlock.appendChild(tabelle([
      {
        key: 'name',
        label: 'Rohstoff',
        value: function (material) { return rohstoffText(material.name); }
      },
      {
        key: 'stock',
        label: 'Lager',
        value: function (material) { return zahl(ctx, material.stock); }
      },
      {
        key: 'need_per_day_at_capacity',
        label: 'Bedarf/Tag bei voller Kapazität',
        value: function (material) { return zahl(ctx, material.need_per_day_at_capacity); }
      },
      {
        key: 'price',
        label: 'Kurs',
        value: function (material) { return preis(ctx, material.price); }
      },
      {
        key: 'price_trend',
        label: 'Trend',
        value: function (material) {
          var trend = material.price_trend;
          var cls = trend === 'günstig' ? 'rd-positiv' : trend === 'teuer' ? 'rd-negativ' : '';
          return el('span', cls, trend === undefined || trend === null ? '–' : trend);
        }
      },
      {
        key: 'cost_per_bottle',
        label: 'Kosten/Flasche',
        value: function (material) { return preis(ctx, material.cost_per_bottle); }
      },
      {
        key: 'input',
        label: 'Bestellmenge',
        value: function (material) { return inputs[String(material.name)]; }
      }
    ], materials));

    var vorschlag = el('button', '', 'Vorschlag für volle Kapazität');
    vorschlag.type = 'button';
    vorschlag.addEventListener('click', function () {
      materials.forEach(function (material) {
        var name = String(material && material.name !== undefined ? material.name : '');
        if (inputs[name]) {
          inputs[name].value = String(Math.ceil(zahlRoh(material.need_per_day_at_capacity)));
        }
      });
      aktualisierePlan(true);
    });
    materialBlock.appendChild(vorschlag);
    materialBlock.appendChild(bestellkosten);

    function aktualisierePlan(senden) {
      var plan = aktuellerPlan();
      var summe = materials.reduce(function (total, material) {
        var name = String(material && material.name !== undefined ? material.name : '');
        return total + zahlRoh(plan[name]) * zahlRoh(material.price);
      }, 0);
      bestellkosten.textContent = 'Kosten der Bestellung: ' + geld(ctx, summe) + ' pro Tag';
      if (senden) sende(ctx, { component_plan: plan });
    }

    materials.forEach(function (material) {
      var name = String(material && material.name !== undefined ? material.name : '');
      if (inputs[name]) {
        inputs[name].addEventListener('input', function () {
          aktualisierePlan(true);
        });
      }
    });
    aktualisierePlan(false);

    var costs = data.cost_per_bottle && typeof data.cost_per_bottle === 'object'
      ? data.cost_per_bottle : {};
    var costBlock = abschnitt(root, 'Kosten pro Flasche (zu aktuellen Marktpreisen)');
    var costRows = [
      { name: 'Rohstoffe', value: costs.materials },
      { name: 'Energie', value: costs.energy },
      { name: 'Löhne', value: costs.wages },
      { name: 'Fixkosten', value: costs.fixed },
      { name: 'Umschlag/Handling', value: costs.handling },
      { name: 'Total', value: costs.total, total: true }
    ];
    costBlock.appendChild(tabelle([
      { key: 'name', label: 'Kostenart' },
      {
        key: 'value',
        label: 'Kosten pro Flasche',
        value: function (row) {
          var value = preis(ctx, row.value);
          return row.total ? el('strong', '', value) : value;
        }
      }
    ], costRows));

    var priceBlock = abschnitt(root, 'Verkaufspreis');
    var settings = ctx && ctx.state && ctx.state.settings ? ctx.state.settings : {};
    var initialPrice = entwurfPreis();
    if (initialPrice === undefined && settings.base_price !== null && settings.base_price !== undefined) {
      initialPrice = settings.base_price;
    }
    if (initialPrice === undefined || initialPrice === null) initialPrice = data.sell_price;
    var priceField = eingabefeld(
      'Verkaufspreis pro Flasche (CHF)',
      initialPrice !== null && initialPrice !== undefined && Number.isFinite(Number(initialPrice))
        ? Number(initialPrice).toFixed(2) : '',
      0,
      0.01
    );
    var priceForm = el('div', 'rd-form');
    priceForm.appendChild(priceField.label);
    priceBlock.appendChild(priceForm);

    var totalCost = zahlRoh(costs.total);
    var liveMargin = el('p');
    var breakEvenLine = el('p');
    var warning = el('p', 'rd-negativ');
    var bandLine = el('p', 'rd-leise');
    var rivalLine = el('p', 'rd-leise');
    priceBlock.appendChild(liveMargin);
    priceBlock.appendChild(breakEvenLine);
    priceBlock.appendChild(warning);
    priceBlock.appendChild(bandLine);
    priceBlock.appendChild(rivalLine);

    var priceBand = ctx && ctx.state && ctx.state.price_band ? ctx.state.price_band : null;
    if (priceBand && priceBand.min !== undefined && priceBand.max !== undefined) {
      bandLine.textContent = 'Erlaubter Preisbereich: ' + preis(ctx, priceBand.min) + ' – ' + preis(ctx, priceBand.max);
    } else {
      bandLine.hidden = true;
    }
    var rivalPrice = ctx && ctx.state && ctx.state.kpis ? ctx.state.kpis.rival_price : null;
    if (rivalPrice !== null && rivalPrice !== undefined) {
      rivalLine.textContent = 'Konkurrenzpreis: ' + preis(ctx, rivalPrice);
    } else {
      rivalLine.hidden = true;
    }

    function aktualisierePreis() {
      var raw = String(priceField.input.value).trim();
      var current = raw === '' ? NaN : Number(raw);
      var breakEven = data.break_even_price !== undefined && data.break_even_price !== null
        ? Number(data.break_even_price) : totalCost;
      if (!Number.isFinite(breakEven)) breakEven = totalCost;

      if (!Number.isFinite(current)) {
        liveMargin.textContent = 'Marge pro Flasche: –';
        liveMargin.className = '';
        breakEvenLine.textContent = 'Verlustgrenze (Preis, ab dem du Gewinn machst): ' + preis(ctx, breakEven);
        warning.hidden = true;
        return;
      }

      schreibeEntwurfPreis(current);
      var margin = current - totalCost;
      liveMargin.textContent = 'Marge pro Flasche: ' + preis(ctx, margin);
      liveMargin.className = margin < 0 ? 'rd-negativ' : 'rd-positiv';
      breakEvenLine.textContent = 'Verlustgrenze (Preis, ab dem du Gewinn machst): ' + preis(ctx, breakEven);
      warning.textContent = 'Unter der Verlustgrenze: du verkaufst mit Verlust.';
      warning.hidden = current >= breakEven;
    }

    priceField.input.addEventListener('input', aktualisierePreis);
    aktualisierePreis();

    var priceTools = el('div', 'rd-form');
    var percentField = el('input', 're-eingabe');
    percentField.type = 'number';
    percentField.min = '0';
    percentField.step = '1';
    percentField.value = '5';
    percentField.setAttribute('aria-label', 'Prozent für Preisänderung');
    var percentLabel = el('label', '', 'Änderung in Prozent ');
    percentLabel.appendChild(percentField);
    priceTools.appendChild(percentLabel);

    function priceButton(text, action) {
      var button = el('button', '', text);
      button.type = 'button';
      button.addEventListener('click', action);
      priceTools.appendChild(button);
    }

    function setPrice(value) {
      if (!Number.isFinite(value)) return;
      priceField.input.value = (Math.round(value * 100) / 100).toFixed(2);
      aktualisierePreis();
    }

    priceButton('Preis um x % erhöhen', function () {
      var current = Number(priceField.input.value);
      var change = Number(percentField.value);
      if (Number.isFinite(current) && Number.isFinite(change)) setPrice(current * (1 + change / 100));
    });
    priceButton('Preis um x % senken', function () {
      var current = Number(priceField.input.value);
      var change = Number(percentField.value);
      if (Number.isFinite(current) && Number.isFinite(change)) setPrice(current * (1 - change / 100));
    });
    priceButton('Preis = Kosten + x %', function () {
      var change = Number(percentField.value);
      if (Number.isFinite(change)) setPrice(totalCost * (1 + change / 100));
    });
    priceBlock.appendChild(priceTools);

    var brandBlock = abschnitt(root, 'Marke und Kunden');
    var brands = Array.isArray(marketing) ? marketing : array(marketing && marketing.brands);
    brands = brands.slice().sort(function (a, b) {
      return Number(!!b.is_mine) - Number(!!a.is_mine);
    });
    if (brands.length) {
      brandBlock.appendChild(tabelle([
        {
          key: 'name',
          label: 'Marke',
          value: function (brand) {
            return String(brand.name === undefined || brand.name === null ? '–' : brand.name) +
              (brand.is_mine ? ' (meine)' : '');
          }
        },
        { key: 'awareness', label: 'Bekanntheit', value: function (brand) { return prozent(ctx, brand.awareness); } },
        { key: 'reputation', label: 'Ruf', value: function (brand) { return prozent(ctx, brand.reputation); } },
        { key: 'quality', label: 'Qualität', value: function (brand) { return prozent(ctx, brand.quality); } },
        { key: 'price', label: 'Preis', value: function (brand) { return preis(ctx, brand.price); } },
        { key: 'share_of_sales', label: 'Anteil', value: function (brand) { return prozent(ctx, brand.share_of_sales); } },
        {
          key: 'marketing_budget_year',
          label: 'Marketingbudget (CHF/Jahr)',
          value: function (brand) { return geld(ctx, brand.marketing_budget_year); }
        }
      ], brands.map(function (brand) {
        return Object.assign({}, brand, { klasse: brand.is_mine ? 'rd-eigene' : '' });
      })));
    } else {
      hinweis(brandBlock);
    }

    var marketingForm = el('div', 'rd-form');
    var marketingChoices = ctx && ctx.state && ctx.state.choices ? ctx.state.choices : {};
    var budgetInitial = marketingChoices.marketing_budget;
    var budgetField = eingabefeld(
      'Marketingbudget (CHF/Jahr)',
      budgetInitial === undefined || budgetInitial === null ? '' : budgetInitial,
      0,
      1
    );
    budgetField.input.addEventListener('input', function () {
      var text = String(budgetField.input.value).trim();
      var value = text === '' ? null : Number(text);
      sende(ctx, { marketing_budget: value === null || !Number.isFinite(value) ? null : value });
    });
    marketingForm.appendChild(budgetField.label);

    var focusInitial = marketingChoices.marketing_focus;
    var focusValue = focusInitial === undefined || focusInitial === null ? 0.5 : Number(focusInitial);
    if (!Number.isFinite(focusValue)) focusValue = 0.5;
    focusValue = Math.max(0, Math.min(1, focusValue));
    var focusLabel = el('label', '', 'Fokus (0 = Laden, 100 = Marke) ');
    var focusInput = el('input', 're-eingabe');
    focusInput.type = 'range';
    focusInput.min = '0';
    focusInput.max = '100';
    focusInput.step = '1';
    focusInput.value = String(Math.round(focusValue * 100));
    focusInput.setAttribute('aria-label', 'Fokus Marke oder Laden');
    var focusText = el('span');
    function aktualisiereFokus(senden) {
      var value = Math.max(0, Math.min(100, zahlRoh(focusInput.value)));
      focusText.textContent = zahl(ctx, value, 0) + ' % Marke, ' + zahl(ctx, 100 - value, 0) + ' % Laden';
      if (senden) sende(ctx, { marketing_focus: value / 100 });
    }
    focusInput.addEventListener('input', function () { aktualisiereFokus(true); });
    focusLabel.appendChild(focusInput);
    focusLabel.appendChild(focusText);
    marketingForm.appendChild(focusLabel);
    aktualisiereFokus(false);

    var targetLabel = el('label', '', 'Zielgruppe ');
    var targetSelect = el('select');
    [
      { value: '', label: 'Alle' },
      { value: '18-34', label: '18–34' },
      { value: '35-64', label: '35–64' },
      { value: '65+', label: '65+' }
    ].forEach(function (item) {
      var option = el('option', '', item.label);
      option.value = item.value;
      targetSelect.appendChild(option);
    });
    var targetInitial = marketingChoices.marketing_target;
    targetSelect.value = targetInitial === undefined || targetInitial === null ? '' : String(targetInitial);
    targetSelect.setAttribute('aria-label', 'Zielgruppe');
    targetSelect.addEventListener('change', function () {
      sende(ctx, { marketing_target: targetSelect.value || null });
    });
    targetLabel.appendChild(targetSelect);
    marketingForm.appendChild(targetLabel);
    brandBlock.appendChild(marketingForm);
    textZeile(
      brandBlock,
      'Mehr Marketing steigert Bekanntheit und Anteil, kostet aber Geld. Ein Vergleich mit der Konkurrenz steht in der Tabelle.',
      'rd-note'
    );

    aktualisierePlan(true);
  }

  async function render(elm, ctx) {
    try {
      if (!elm || typeof elm.replaceChildren !== 'function') return;
      elm.replaceChildren();
      var root = el('div', 'rd-reiter');
      elm.appendChild(root);

      var p = await laden(ctx, 'production');
      var m = await laden(ctx, 'brand_marketing');
      var e = await laden(ctx, 'purchasing');
      void e;

      productionRender(root, ctx, p, m);
    } catch (error) {
      try {
        if (elm && typeof elm.replaceChildren === 'function') {
          elm.replaceChildren();
          var fallback = el('div', 'rd-block');
          hinweis(fallback);
          elm.appendChild(fallback);
        }
      } catch (e) {
        // Fehler bei der Wiederherstellung der Anzeige ignorieren.
      }
    }
  }

  REITER.produktion = { async render(elm, ctx) { return render(elm, ctx); } };
}());
