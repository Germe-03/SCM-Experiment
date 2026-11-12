'use strict';

(function () {
  var REITER = window.REITER = window.REITER || {};

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function array(value) {
    return Array.isArray(value) ? value : [];
  }

  function objekt(value) {
    return value && typeof value === 'object' ? value : {};
  }

  function roh(value) {
    var number = Number(value);
    return Number.isFinite(number) ? number : 0;
  }

  function sauber(value) {
    var number = roh(value);
    return Math.abs(number) < 0.005 ? 0 : number;
  }

  function geld(ctx, value) {
    return ctx.geld(sauber(value));
  }

  function zahl(ctx, value, stellen) {
    return ctx.zahl(sauber(value), stellen);
  }

  function prozent(ctx, value) {
    return ctx.prozent(sauber(value));
  }

  function preis(value) {
    var number = sauber(value);
    return new Intl.NumberFormat('de-CH', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(number) + ' CHF';
  }

  function laden(ctx, name) {
    return Promise.resolve().then(function () {
      return ctx.ansicht(name);
    }).catch(function () {
      return null;
    });
  }

  function abschnitt(parent, titel) {
    var block = el('div', 'rd-block');
    block.appendChild(el('h3', '', titel));
    parent.appendChild(block);
    return block;
  }

  function text(parent, inhalt, cls) {
    parent.appendChild(el('p', cls || '', inhalt));
  }

  function tabelle(parent, spalten, zeilen) {
    var wrap = el('div', 'rd-scroll');
    var table = el('table', 'rd-tabelle');
    var thead = el('thead');
    var kopf = el('tr');

    spalten.forEach(function (spalte) {
      kopf.appendChild(el('th', '', spalte));
    });
    thead.appendChild(kopf);
    table.appendChild(thead);

    var tbody = el('tbody');
    zeilen.forEach(function (zeile) {
      var tr = el('tr', zeile.klasse || '');
      if (zeile.fett) tr.style.fontWeight = 'bold';
      zeile.zellen.forEach(function (inhalt) {
        var td = el('td');
        if (inhalt && inhalt.nodeType) td.appendChild(inhalt);
        else td.textContent = inhalt === undefined || inhalt === null || inhalt === '' ? '–' : String(inhalt);
        if (zeile.fett) td.style.fontWeight = 'bold';
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    parent.appendChild(wrap);
    return { wrap: wrap, table: table, tbody: tbody };
  }

  function feld(obj, namen) {
    var quelle = objekt(obj);
    for (var i = 0; i < namen.length; i += 1) {
      if (quelle[namen[i]] !== undefined && quelle[namen[i]] !== null) return quelle[namen[i]];
    }
    return undefined;
  }

  function financialIncome(data, last) {
    var names = last
      ? ['income_last', 'last_income', 'income_statement_last']
      : ['income_current', 'income_statement', 'income_statement_current'];
    return feld(data, names);
  }

  function financialBalance(data) {
    return feld(data, ['balance', 'balance_sheet']);
  }

  function financialCashflow(data) {
    return feld(data, ['cash_flow', 'cashflow']);
  }

  function financialRatios(data) {
    return feld(data, ['ratios']);
  }

  function wert(obj, key) {
    return roh(objekt(obj)[key]);
  }

  function vorzeichenKlasse(value) {
    return sauber(value) < 0 ? 'rd-negativ' : 'rd-positiv';
  }

  function abzug(ctx, value) {
    return geld(ctx, -Math.abs(sauber(value)));
  }

  function erfolgsrechnung(parent, data, ctx) {
    var block = abschnitt(parent, 'Erfolgsrechnung');
    if (!data) {
      text(block, 'Noch keine Daten.', 'rd-leise');
      return;
    }

    var current = financialIncome(data, false);
    var last = financialIncome(data, true);
    if (current === undefined && last === undefined) {
      text(block, 'Noch keine Daten.', 'rd-leise');
      return;
    }

    var currentHeader = 'Laufendes Jahr (bis heute)';
    var lastHeader = 'Letztes Jahr';
    if (current && current.year !== undefined && current.year !== null) currentHeader += ' ' + current.year;
    if (last && last.year !== undefined && last.year !== null) lastHeader += ' ' + last.year;
    else lastHeader = '–';

    var posten = [
      ['Umsatz', 'revenue', 'geld'],
      ['Wareneinsatz', 'cogs', 'abzug'],
      ['Bruttogewinn', 'gross_profit', 'geld', true],
      ['Löhne', 'wages', 'abzug'],
      ['Miete und Fixkosten', 'rent_fixed', 'abzug'],
      ['Umschlag', 'handling', 'abzug'],
      ['Lagerkosten', 'storage', 'abzug'],
      ['Marketing', 'marketing', 'abzug'],
      ['Forschung', 'research', 'abzug'],
      ['Übrige Betriebskosten', 'other_opex', 'abzug'],
      ['EBITDA', 'ebitda', 'geld', true],
      ['Abschreibungen', 'depreciation', 'abzug'],
      ['EBIT', 'ebit', 'geld', true],
      ['Zinsen', 'interest', 'abzug'],
      ['Gewinn vor Steuern', 'ebt', 'geld', true],
      ['Steuern', 'taxes', 'abzug'],
      ['Reingewinn', 'net_income', 'geld', true, true]
    ];

    var rows = posten.map(function (item) {
      function betrag(statement) {
        if (!statement) return '–';
        var value = wert(statement, item[1]);
        return item[2] === 'abzug' ? abzug(ctx, value) : geld(ctx, value);
      }

      var currentValue = current ? wert(current, item[1]) : 0;
      return {
        klasse: item[3] ? 'abschluss-summe' : '',
        fett: Boolean(item[3]),
        zellen: [
          item[0],
          item[4] && current ? el('span', vorzeichenKlasse(currentValue), betrag(current)) : betrag(current),
          item[4] && last ? el('span', vorzeichenKlasse(wert(last, item[1])), betrag(last)) : betrag(last)
        ]
      };
    });

    tabelle(block, ['Posten', currentHeader, lastHeader], rows);
    text(block, 'Staffelform: vom Umsatz werden Schritt für Schritt die Kosten abgezogen, bis der Reingewinn übrig bleibt.', 'rd-note');
  }

  function bilanz(parent, data, ctx) {
    var block = abschnitt(parent, 'Bilanz');
    if (!data) {
      text(block, 'Noch keine Daten.', 'rd-leise');
      return;
    }

    var grid = el('div');
    grid.style.display = 'grid';
    grid.style.gridTemplateColumns = 'repeat(auto-fit,minmax(16rem,1fr))';
    grid.style.gap = '1rem';
    block.appendChild(grid);

    var assets = objekt(data.assets);
    var liabilities = objekt(data.liabilities);
    var aktivBlock = el('div');
    aktivBlock.appendChild(el('h4', '', 'Aktiven'));
    tabelle(aktivBlock, ['Posten', 'Betrag'], [
      { zellen: ['Kasse', geld(ctx, assets.cash)] },
      { zellen: ['Lager', geld(ctx, assets.inventory)] },
      { zellen: ['Lastwagen', geld(ctx, assets.trucks)] },
      { zellen: ['Standorte', geld(ctx, assets.sites)] },
      { zellen: ['Beteiligungen', geld(ctx, assets.participations)] },
      { zellen: ['Wertpapiere', geld(ctx, assets.securities)] },
      { klasse: 'abschluss-summe', fett: true, zellen: ['Total', geld(ctx, assets.total)] }
    ]);
    grid.appendChild(aktivBlock);

    var passivBlock = el('div');
    passivBlock.appendChild(el('h4', '', 'Passiven'));
    tabelle(passivBlock, ['Posten', 'Betrag'], [
      { zellen: ['Kredite', geld(ctx, liabilities.loans)] },
      { zellen: ['Übrige Schulden', geld(ctx, liabilities.other)] },
      { klasse: 'abschluss-summe', fett: true, zellen: ['Total Schulden', geld(ctx, liabilities.total)] },
      { zellen: ['Eigenkapital', geld(ctx, data.equity)] },
      { klasse: 'abschluss-summe', fett: true, zellen: ['Total', geld(ctx, data.total)] }
    ]);
    grid.appendChild(passivBlock);
  }

  function geldfluss(parent, data, ctx) {
    var block = abschnitt(parent, 'Geldflussrechnung');
    if (!data) {
      text(block, 'Noch keine Daten.', 'rd-leise');
      return;
    }

    tabelle(block, ['Posten', 'Betrag'], [
      { zellen: ['Betrieb', geld(ctx, data.operating)] },
      { zellen: ['Investitionen', geld(ctx, data.investing)] },
      { zellen: ['Finanzierung', geld(ctx, data.financing)] },
      { zellen: ['Dividenden erhalten', geld(ctx, data.dividends_received)] },
      { zellen: ['Dividenden bezahlt', geld(ctx, data.dividends_paid)] },
      { klasse: 'abschluss-summe', fett: true, zellen: ['Veränderung der Kasse', geld(ctx, data.change)] }
    ]);
    text(block, 'Die Geldflussrechnung zeigt, wie sich die Kasse durch Betrieb, Investitionen und Finanzierung verändert hat.', 'rd-note');
  }

  function kennzahlen(parent, data, ctx) {
    var block = abschnitt(parent, 'Kennzahlen');
    if (!data) {
      text(block, 'Noch keine Daten.', 'rd-leise');
      return;
    }

    var grid = el('div', 'rd-grid');
    var ratios = [
      ['Bruttomarge', 'gross_margin', prozent, 'Anteil des Umsatzes, der nach dem Wareneinsatz bleibt.'],
      ['EBIT-Marge', 'ebit_margin', prozent, 'Betriebsergebnis im Verhältnis zum Umsatz.'],
      ['Eigenkapitalquote', 'equity_ratio', prozent, 'Anteil des Eigenkapitals an der Bilanzsumme.'],
      ['Liquidität', 'liquidity', function (ctxArg, value) { return zahl(ctxArg, value, 2); }, 'Verhältnis von kurzfristigen Mitteln zu kurzfristigen Schulden.'],
      ['Eigenkapitalrendite', 'roe', prozent, 'Reingewinn im Verhältnis zum Eigenkapital.']
    ];

    ratios.forEach(function (item) {
      var box = el('div', 'rd-kachel');
      box.appendChild(el('span', 'rd-leise', item[0]));
      box.appendChild(el('strong', '', item[2](ctx, wert(data, item[1]))));
      box.appendChild(el('small', 'rd-leise', item[3]));
      grid.appendChild(box);
    });
    block.appendChild(grid);
  }

  function stageName(stage) {
    var value = String(stage === undefined || stage === null ? '' : stage);
    var normalized = value.toLocaleLowerCase('de').replace(/[\s_-]/g, '');
    var names = {
      producer: 'Hersteller',
      hersteller: 'Hersteller',
      wholesaler: 'Grosshändler',
      grosshaendler: 'Grosshändler',
      distributor: 'Verteiler',
      verteiler: 'Verteiler',
      retailer: 'Detailhändler',
      detailhaendler: 'Detailhändler',
      gastro: 'Gastro'
    };
    return names[normalized] || value || '–';
  }

  function reportIncome(firm) {
    return feld(firm, ['income', 'income_statement']) || firm;
  }

  function reportBalance(firm) {
    return feld(firm, ['balance', 'balance_sheet']) || {};
  }

  function reportCashflow(firm) {
    return feld(firm, ['cash_flow', 'cashflow']) || {};
  }

  function reportRatios(firm) {
    return feld(firm, ['ratios']) || {};
  }

  function detailsZeile(firm, ctx) {
    var income = objekt(reportIncome(firm));
    var balance = objekt(reportBalance(firm));
    var assets = objekt(balance.assets);
    var liabilities = objekt(balance.liabilities);
    var wrap = el('div');
    wrap.appendChild(el('strong', '', 'Erfolgsrechnung'));
    tabelle(wrap, ['Posten', 'Betrag'], [
      { zellen: ['Umsatz', geld(ctx, income.revenue)] },
      { zellen: ['Wareneinsatz', abzug(ctx, income.cogs)] },
      { zellen: ['Bruttogewinn', geld(ctx, income.gross_profit)] },
      { zellen: ['EBITDA', geld(ctx, income.ebitda)] },
      { zellen: ['EBIT', geld(ctx, income.ebit)] },
      { zellen: ['Reingewinn', geld(ctx, income.net_income)] }
    ]);
    wrap.appendChild(el('strong', '', 'Bilanz-Totals'));
    tabelle(wrap, ['Posten', 'Betrag'], [
      { zellen: ['Aktiven', geld(ctx, assets.total)] },
      { zellen: ['Schulden', geld(ctx, liabilities.total)] },
      { zellen: ['Eigenkapital', geld(ctx, balance.equity)] },
      { zellen: ['Bilanzsumme', geld(ctx, balance.total)] }
    ]);
    return wrap;
  }

  function berichte(parent, data, ctx) {
    var block = abschnitt(parent, 'Geschäftsberichte der Konkurrenz');
    if (!data) {
      text(block, 'Noch keine Daten.', 'rd-leise');
      return;
    }

    var hinweis = 'Konkurrenten veröffentlichen ihren Geschäftsbericht einmal im Jahr, jeweils für das abgeschlossene Vorjahr.';
    if (data.year !== undefined && data.year !== null) hinweis += ' Berichtsjahr ' + data.year + '.';
    text(block, hinweis, 'rd-note');

    var firms = array(data.firms).slice();
    if (!firms.length) {
      text(block, 'Noch keine Geschäftsberichte: der erste erscheint am Ende des ersten Jahres.', 'rd-leise');
      return;
    }

    firms.sort(function (a, b) {
      return wert(reportIncome(b), 'revenue') - wert(reportIncome(a), 'revenue');
    });

    var table = el('table', 'rd-tabelle');
    var thead = el('thead');
    var header = el('tr');
    ['Name', 'Stufe', 'Umsatz', 'Bruttogewinn', 'EBIT', 'Reingewinn', 'Eigenkapital', 'Eigenkapitalquote', 'Kasse', ''].forEach(function (label) {
      header.appendChild(el('th', '', label));
    });
    thead.appendChild(header);
    table.appendChild(thead);
    var tbody = el('tbody');

    firms.forEach(function (firm) {
      var income = objekt(reportIncome(firm));
      var balance = objekt(reportBalance(firm));
      var ratios = objekt(reportRatios(firm));
      var assets = objekt(balance.assets);
      var mainRow = el('tr');
      var values = [
        firm.name || '–',
        stageName(firm.stage),
        geld(ctx, income.revenue),
        geld(ctx, income.gross_profit),
        geld(ctx, income.ebit),
        geld(ctx, income.net_income),
        geld(ctx, balance.equity),
        prozent(ctx, ratios.equity_ratio),
        geld(ctx, assets.cash)
      ];
      values.forEach(function (value, index) {
        var td = el('td');
        if (index === 5) td.appendChild(el('span', vorzeichenKlasse(income.net_income), value));
        else td.textContent = value;
        mainRow.appendChild(td);
      });

      var actionCell = el('td');
      var button = el('button', '', 'Details');
      button.type = 'button';
      button.setAttribute('aria-expanded', 'false');
      actionCell.appendChild(button);
      mainRow.appendChild(actionCell);
      tbody.appendChild(mainRow);

      var detailRow = el('tr');
      detailRow.hidden = true;
      var detailCell = el('td');
      detailCell.colSpan = 10;
      detailCell.appendChild(detailsZeile(firm, ctx));
      detailRow.appendChild(detailCell);
      tbody.appendChild(detailRow);

      button.addEventListener('click', function () {
        detailRow.hidden = !detailRow.hidden;
        button.textContent = detailRow.hidden ? 'Details' : 'Schliessen';
        button.setAttribute('aria-expanded', String(!detailRow.hidden));
      });
    });

    table.appendChild(tbody);
    var scroll = el('div', 'rd-scroll');
    scroll.appendChild(table);
    block.appendChild(scroll);
  }

  function berechnung(parent, data, ctx) {
    var block = abschnitt(parent, 'Kalkulation pro Flasche');
    if (!data) {
      text(block, 'Noch keine Daten.', 'rd-leise');
      return;
    }

    var inputPreis = el('input');
    inputPreis.type = 'number';
    inputPreis.step = '0.01';
    inputPreis.value = String(sauber(data.sell_price));

    var inputMenge = el('input');
    inputMenge.type = 'number';
    inputMenge.step = '1';
    inputMenge.min = '0';
    inputMenge.value = String(sauber(data.bottles_per_day));

    var resultGewinn = el('span');
    var resultMarge = el('span');
    var resultJahr = el('span');

    function inputZahl(input) {
      var raw = String(input.value).trim().replace(',', '.');
      if (raw === '') return 0;
      var number = Number(raw);
      return Number.isFinite(number) ? number : 0;
    }

    function update() {
      var fullCost = sauber(data.full_cost);
      var newPrice = inputZahl(inputPreis);
      var newQuantity = Math.max(0, inputZahl(inputMenge));
      var profit = sauber(newPrice - fullCost);
      var margin = newPrice > 0 ? profit / newPrice * 100 : null;
      resultGewinn.textContent = geld(ctx, profit);
      resultGewinn.className = vorzeichenKlasse(profit);
      resultMarge.textContent = margin === null ? '–' : zahl(ctx, margin, 1) + ' %';
      resultMarge.className = margin === null ? '' : vorzeichenKlasse(margin);
      resultJahr.textContent = geld(ctx, profit * newQuantity * 360);
      resultJahr.className = vorzeichenKlasse(profit * newQuantity * 360);
    }

    var marginValue = zahl(ctx, data.margin_pct, 1) + ' %';
    var actualAnnual = sauber(data.profit) * sauber(data.bottles_per_day) * 360;
    var rows = [
      { zellen: ['Einkaufspreis', preis(data.purchase_price), '–'] },
      { zellen: ['Beschaffungskosten (Fracht, Zoll usw.)', preis(data.procurement_costs), '–'] },
      { klasse: 'abschluss-summe', fett: true, zellen: ['Einstandspreis', preis(data.landed_cost), '–'] },
      { zellen: ['Gemeinkosten pro Flasche', preis(data.overhead), '–'] },
      { klasse: 'abschluss-summe', fett: true, zellen: ['Selbstkosten', preis(data.full_cost), '–'] },
      { zellen: ['Verkaufspreis', preis(data.sell_price), inputPreis] },
      {
        zellen: [
          'Gewinn pro Flasche',
          el('span', vorzeichenKlasse(data.profit), preis(data.profit)),
          resultGewinn
        ]
      },
      { zellen: ['Marge in %', marginValue, resultMarge] },
      {
        zellen: [
          'Verlustgrenze (unter diesem Preis machst du Verlust)',
          preis(data.break_even_price),
          '–'
        ]
      },
      { zellen: ['Menge pro Tag', zahl(ctx, data.bottles_per_day, 0), inputMenge] },
      {
        zellen: [
          'Gewinn pro Jahr',
          el('span', vorzeichenKlasse(actualAnnual), geld(ctx, actualAnnual)),
          resultJahr
        ]
      }
    ];

    tabelle(block, ['Posten', 'Aktuell', 'Ausprobieren'], rows);
    inputPreis.addEventListener('input', update);
    inputMenge.addEventListener('input', update);
    update();
    text(block, 'Das ist nur eine Rechenhilfe: sie ändert deinen Preis nicht. Den echten Preis stellst du im Reiter Firma ein.', 'rd-note');
  }

  async function render(elm, ctx) {
    elm.replaceChildren();
    var root = el('div', 'rd-reiter');
    elm.appendChild(root);

    var results = await Promise.all([
      laden(ctx, 'financials'),
      laden(ctx, 'reports'),
      laden(ctx, 'calculation')
    ]);

    var financials = results[0];
    erfolgsrechnung(root, financials, ctx);
    bilanz(root, financialBalance(financials), ctx);
    geldfluss(root, financialCashflow(financials), ctx);
    kennzahlen(root, financialRatios(financials), ctx);
    berichte(root, results[1], ctx);
    berechnung(root, results[2], ctx);
  }

  REITER.abschluesse = { async render(elm, ctx) { return render(elm, ctx); } };
}());
