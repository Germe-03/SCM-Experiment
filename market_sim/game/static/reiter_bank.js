'use strict';

(function () {
  var kreditBetrag = 100000;
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

  function format(ctx, v, art, stellen) {
    if (v === undefined || v === null || v === '') return '–';
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
      hr.appendChild(el('th', '', spalte.label));
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
    box.appendChild(el('strong', cls || '', inhalt));
    parent.appendChild(box);
    return box;
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

  function linien(parent, ctx, series, optionen) {
    if (!series.length || !ctx || typeof ctx.linien !== 'function') {
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

  function fehlerBlock(parent, titel) {
    var block = abschnitt(parent, titel);
    textZeile(block, 'Daten nicht verfuegbar', 'rd-leise');
    return block;
  }

  function kreditrechner(parent, ctx, banks) {
    var calc = abschnitt(parent, 'Kredit aufnehmen');
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

  async function render(elm, ctx) {
    var root = container(elm);
    var planned;
    try { planned = (ctx.geplant && ctx.geplant()) || {}; } catch (e) { planned = {}; }
    planBox(root, ctx, 'loan', planned.loan ? 'Kredit über ' + geld(ctx, planned.loan.amount) : '');

    var result = await Promise.all([
      laden(ctx, 'banks', { amount: kreditBetrag }),
      laden(ctx, 'macro')
    ]);
    var data = result[0];
    var macro = result[1];

    if (!data) {
      fehlerBlock(root, 'Bank');
    } else {
      var own = data.own || {};

      var eigeneBank = abschnitt(root, 'Deine Bank');
      var grid = el('div', 'rd-grid');
      kachel(grid, 'Hausbank', own.bank_name === undefined || own.bank_name === null ? '–' : own.bank_name);
      kachel(grid, 'Kasse', geld(ctx, own.cash));
      kachel(grid, 'Kreditlimite', geld(ctx, own.credit_limit));
      kachel(grid, 'Schulden total', geld(ctx, own.debt_total));
      kachel(grid, 'Zinsen dieses Jahr bezahlt', geld(ctx, own.interest_paid_year));
      kachel(grid, 'Zinsen dieses Jahr erhalten', geld(ctx, own.interest_received_year));
      kachel(grid, 'Leitzins', prozent(ctx, own.policy_rate));
      eigeneBank.appendChild(grid);

      var saetze = abschnitt(root, 'Deine Zinssätze');
      saetze.appendChild(tabelle([
        { label: 'Art', value: function (r) { return r.art; } },
        { label: 'Zinssatz', value: function (r) { return r.zins; } },
        { label: 'Bedeutung', value: function (r) { return r.bedeutung; } }
      ], [
        { art: 'Guthabenzins', zins: prozent(ctx, own.deposit_rate), bedeutung: 'Zins auf dein Guthaben bei der Bank.' },
        { art: 'Kontokorrent-/Überziehungszins', zins: prozent(ctx, own.overdraft_rate), bedeutung: 'Zins auf Überziehungen deines Kontos.' },
        { art: 'Kreditzins', zins: prozent(ctx, own.loan_rate), bedeutung: 'Zins für deine Kredite.' }
      ]));

      var loans = array(data.loans);
      var kredite = abschnitt(root, 'Deine Kredite');
      var loanRows = loans.slice();
      if (loans.length) {
        loanRows.push({
          _total: true,
          amount: loans.reduce(function (sum, loan) { return sum + zahlRoh(loan && loan.amount); }, 0),
          remaining: loans.reduce(function (sum, loan) { return sum + zahlRoh(loan && loan.remaining); }, 0)
        });
      }
      kredite.appendChild(tabelle([
        { key: 'bank', label: 'Bank' },
        { key: 'amount', label: 'Betrag', value: function (loan) { return loan._total ? geld(ctx, loan.amount) : geld(ctx, loan.amount); } },
        { key: 'remaining', label: 'Restschuld', value: function (loan) { return geld(ctx, loan.remaining); } },
        { key: 'rate', label: 'Zins', value: function (loan) { return loan._total ? '–' : prozent(ctx, loan.rate); } },
        { key: 'years', label: 'Laufzeit (Jahre)', value: function (loan) { return loan._total ? 'Total' : zahl(ctx, loan.years); } },
        { key: 'purpose', label: 'Zweck' }
      ], loanRows, { rowClass: function (loan) { return loan._total ? 'rd-eigen' : ''; } }));
      textZeile(kredite, 'Nächstes Jahr fällig (Zins und Tilgung): ' + geld(ctx, own.next_payment_year));

      var banken = array(data.banks);
      var offers = array(data.offers);
      var vergleich = abschnitt(root, 'Banken im Vergleich');
      vergleich.appendChild(tabelle([
        { key: 'name', label: 'Bank' },
        { key: 'margin', label: 'Marge', value: function (bank) { return prozent(ctx, bank.margin); } },
        { key: 'loan_rate', label: 'Kreditzins', value: function (bank) {
          var offer = offers.find(function (item) {
            return item && item.bank_id !== undefined && item.bank_id !== null &&
              bank && bank.id !== undefined && bank.id !== null &&
              String(item.bank_id) === String(bank.id);
          });
          return offer ? prozent(ctx, offer.rate) : '–';
        } },
        { key: 'capital_ratio', label: 'Eigenkapitalquote', value: function (bank) { return prozent(ctx, bank.capital_ratio); } },
        { key: 'action', label: 'Aktion', value: function (bank) {
          var bankId = bank && bank.id;
          if (own.bank_id !== undefined && own.bank_id !== null && bankId !== undefined && bankId !== null &&
              String(own.bank_id) === String(bankId)) {
            return 'Hausbank';
          }
          if (!bank.active) return 'Nicht aktiv';
          var button = el('button', '', 'Zur Hausbank machen');
          button.type = 'button';
          button.addEventListener('click', function () {
            if (window.confirm(bank.name + ' zur Hausbank machen?')) {
              ctx.entscheide({ bank_id: bank.id });
              ctx.neuZeichnen();
            }
          });
          return button;
        } }
      ], banken, {
        rowClass: function (bank) {
          return own.bank_id !== undefined && own.bank_id !== null && bank && bank.id !== undefined && bank.id !== null &&
            String(own.bank_id) === String(bank.id) ? 'rd-eigen' : '';
        }
      }));

      kreditrechner(root, ctx, data);
    }

    var verlauf = abschnitt(root, 'Leitzins-Verlauf');
    var history = array(macro && macro.history);
    if (!history.length) {
      textZeile(verlauf, 'Keine Verlaufsdaten', 'rd-leise');
    } else {
      linien(verlauf, ctx, [
        { name: 'Leitzins', werte: history.map(function (item) { return item ? item.policy_rate : null; }), farbe: 'var(--akzent)' }
      ], { labels: history.map(function (item) { return item ? item.label : '–'; }), hoehe: 180 });
    }
  }

  REITER.bank = { async render(elm, ctx) { return render(elm, ctx); } };
}());
