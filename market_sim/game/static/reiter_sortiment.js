'use strict';

(function () {
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function array(value) {
    return Array.isArray(value) ? value : [];
  }

  function zahlRoh(value) {
    var number = Number(value);
    return Number.isFinite(number) ? number : 0;
  }

  function finite(value) {
    if (value === undefined || value === null || value === '') return null;
    var number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function format(ctx, value, art, stellen) {
    var number = Number(value);
    if (!Number.isFinite(number)) return '–';
    try {
      if (art === 'prozent' && typeof ctx.prozent === 'function') return ctx.prozent(number);
      if (art === 'zahl' && typeof ctx.zahl === 'function') return ctx.zahl(number, stellen);
    } catch (e) {
      return String(number);
    }
    return String(number);
  }

  function prozent(ctx, value) {
    return format(ctx, value, 'prozent');
  }

  function zahl(ctx, value, stellen) {
    return format(ctx, value, 'zahl', stellen);
  }

  function preis(value) {
    var number = finite(value);
    if (number === null) return '–';
    try {
      return new Intl.NumberFormat('de-CH', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }).format(number) + ' CHF';
    } catch (e) {
      return number.toFixed(2) + ' CHF';
    }
  }

  function abschnitt(parent, titel) {
    var block = el('div', 'rd-block');
    block.appendChild(el('h3', '', titel));
    parent.appendChild(block);
    return block;
  }

  function tabelle(spalten, zeilen) {
    var wrap = el('div', 'rd-scroll');
    var table = el('table', 'rd-tabelle');
    var head = el('thead');
    var headerRow = el('tr');

    spalten.forEach(function (spalte) {
      headerRow.appendChild(el('th', '', spalte.label));
    });
    head.appendChild(headerRow);
    table.appendChild(head);

    var body = el('tbody');
    zeilen.forEach(function (zeile) {
      var row = el('tr');
      spalten.forEach(function (spalte) {
        var cell = el('td');
        var value = spalte.value(zeile);
        if (value && value.nodeType) cell.appendChild(value);
        else cell.textContent = value === undefined || value === null || value === '' ? '–' : String(value);
        row.appendChild(cell);
      });
      body.appendChild(row);
    });
    table.appendChild(body);
    wrap.appendChild(table);
    return wrap;
  }

  function gespeicherteAnteile(ctx) {
    try {
      if (typeof entwurfEntscheide !== 'undefined' &&
          entwurfEntscheide &&
          Object.prototype.hasOwnProperty.call(entwurfEntscheide, 'category_shares')) {
        return entwurfEntscheide.category_shares;
      }
      if (ctx.state && ctx.state.choices) return ctx.state.choices.category_shares;
    } catch (e) {
      return null;
    }
    return null;
  }

  function lieferantenAnteile(ctx) {
    try {
      if (typeof entwurfEntscheide !== 'undefined' &&
          entwurfEntscheide &&
          Object.prototype.hasOwnProperty.call(entwurfEntscheide, 'supplier_shares')) {
        return entwurfEntscheide.supplier_shares;
      }
      if (ctx.state && ctx.state.choices) return ctx.state.choices.supplier_shares;
    } catch (e) {
      return null;
    }
    return null;
  }

  function zeichneSortiment(root, ctx, kandidaten) {
    return new Promise(function (resolve) {
      var arbeit;
      try {
        arbeit = Promise.resolve().then(function () {
          return ctx.ansicht('assortment');
        }).then(function (daten) {
          var block = abschnitt(root, 'Sortiment');
          var categories = array(daten && daten.categories);

          if (!daten || !categories.length) {
            block.appendChild(el('p', 'rd-leise', 'Das Sortiment ist noch nicht verfügbar.'));
            return;
          }

          block.appendChild(el('p', '', 'Hier legst du fest, wie viel Prozent deines Einkaufs auf welche Getränkeart entfallen. Der Lieferant liefert dir dann diese Mischung, soweit er die Ware hat. Leer lassen = keine Vorgabe.'));

          var bisher = gespeicherteAnteile(ctx);
          var eingaben = {};
          var summe = el('p', 'rd-leise', '');
          var sortimentTabelle = tabelle([
            { label: 'Getränkeart', value: function (category) { return category.name || category.key || '–'; } },
            { label: 'Marktanteil', value: function (category) { return prozent(ctx, category.share_market); } },
            { label: 'Mein Anteil heute', value: function (category) { return prozent(ctx, category.share_mine); } },
            { label: 'Lager (Flaschen)', value: function (category) { return zahl(ctx, category.stock_bottles, 0); } },
            {
              label: 'Anteil %',
              value: function (category) {
                var input = el('input');
                input.type = 'number';
                input.min = '0';
                input.max = '100';
                input.step = '1';
                input.className = 'anteil-feld';
                input.setAttribute('data-kategorie', String(category.key));
                input.setAttribute('aria-label', 'Anteil in Prozent: ' + (category.name || category.key || 'Getränkeart'));

                var gespeicherterWert = bisher && typeof bisher === 'object' ? bisher[category.key] : null;
                var number = finite(gespeicherterWert);
                input.value = number !== null ? String(Math.round(number)) : '';
                eingaben[String(category.key)] = input;
                input.addEventListener('input', aktualisiere);
                return input;
              }
            }
          ], categories);

          function leseEingaben() {
            var ergebnis = {};
            Object.keys(eingaben).forEach(function (key) {
              var text = String(eingaben[key].value).trim().replace(',', '.');
              var number = text === '' ? null : Number(text);
              if (number !== null && Number.isFinite(number) && number > 0) ergebnis[key] = number;
            });
            return ergebnis;
          }

          function aktualisiereSumme(werte) {
            var summeWert = Object.keys(werte).reduce(function (total, key) {
              return total + werte[key];
            }, 0);
            summe.textContent = summeWert > 0
              ? 'Summe der Eingaben: ' + zahl(ctx, summeWert, 1) + ' % (wird auf 100 % umgerechnet)'
              : 'Keine Vorgabe: der Lieferant liefert wie bisher.';
            return summeWert;
          }

          function aktualisiere() {
            var ergebnis = leseEingaben();
            aktualisiereSumme(ergebnis);
            try {
              ctx.entscheide({ category_shares: Object.keys(ergebnis).length ? ergebnis : null });
            } catch (e) {
              // Fehler beim Speichern der Eingabe ruhig behandeln.
            }
          }

          block.appendChild(sortimentTabelle);
          block.appendChild(summe);
          aktualisiereSumme(leseEingaben());

          var lieferanten = array(kandidaten);
          if (!lieferanten.length) return;

          return Promise.resolve().then(function () {
            return ctx.ansicht('pricing');
          }).catch(function () {
            return null;
          }).then(function (preisDaten) {
            var vergleich = abschnitt(root, 'Lieferantenpreis im Vergleich');
            var meinPreis = finite(preisDaten && preisDaten.purchase_price);

            vergleich.appendChild(tabelle([
              { label: 'Lieferant', value: function (kandidat) { return kandidat.name || '–'; } },
              { label: 'Preis pro Flasche', value: function (kandidat) { return preis(kandidat.price); } },
              {
                label: 'Unterschied zu meinem Einkaufspreis',
                value: function (kandidat) {
                  if (meinPreis === null) return '‒';
                  var kandidatPreis = finite(kandidat.price);
                  if (kandidatPreis === null) return '‒';

                  var unterschied = kandidatPreis - meinPreis;
                  var vorzeichen = unterschied < 0 ? '-' : '+';
                  var klasse = unterschied < 0 ? 'rd-positiv' : unterschied > 0 ? 'rd-negativ' : '';
                  var anzeige = vorzeichen + preis(Math.abs(unterschied));
                  return el('span', klasse, anzeige);
                }
              }
            ], lieferanten));

            var anteile = lieferantenAnteile(ctx);
            if (!anteile || typeof anteile !== 'object') return;

            var gewichteteSumme = 0;
            var preisSumme = 0;
            lieferanten.forEach(function (kandidat) {
              var anteil = finite(anteile[String(kandidat.id)]);
              var kandidatPreis = finite(kandidat.price);
              if (anteil !== null && anteil > 0 && kandidatPreis !== null) {
                gewichteteSumme += anteil;
                preisSumme += anteil * kandidatPreis;
              }
            });

            if (gewichteteSumme > 0) {
              vergleich.appendChild(el('p', '', 'Mischpreis bei deinen Lieferanten-Anteilen: ' +
                preis(preisSumme / gewichteteSumme) + ' pro Flasche'));
            }
          });
        });

        arbeit.then(function () {
          resolve();
        }, function () {
          resolve();
        });
      } catch (e) {
        resolve();
      }
    });
  }

  window.zeichneSortiment = zeichneSortiment;
}());
