'use strict';

(function () {
  var STIL = [
    '.re-raster{display:grid;grid-template-columns:repeat(auto-fit,minmax(22rem,1fr));gap:.75rem}',
    '.re-diagramm{min-width:0}',
    '.re-filter{display:flex;flex-wrap:wrap;gap:.6rem;margin:.75rem 0}',
    '.re-filter label{display:grid;gap:.25rem}',
    '.re-eingabe{width:8rem;max-width:100%}',
    '.re-lagerwarnung{font-weight:700}',
    '.re-status{margin:.5rem 0}'
  ].join('');

  if (typeof document !== 'undefined' && document.head && !document.getElementById('reiter-einkauf-stil')) {
    var stil = document.createElement('style');
    stil.id = 'reiter-einkauf-stil';
    stil.textContent = STIL;
    document.head.appendChild(stil);
  }

  var produktionsziel = null;
  var markensuche = '';
  var markenkategorie = '';

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
      if (typeof ctx.zahl === 'function') return ctx.zahl(value, stellen);
    } catch (e) {
      return String(value);
    }
    return String(value);
  }

  function geld(ctx, n) {
    var value = Number(n);
    if (!Number.isFinite(value)) return '–';
    try {
      if (typeof ctx.geld === 'function') return ctx.geld(value);
    } catch (e) {
      return String(value);
    }
    return String(value);
  }

  function preis(ctx, n) {
    var value = Number(n);
    if (!Number.isFinite(value)) return '–';
    try {
      if (typeof ctx.preis === 'function') return ctx.preis(value);
    } catch (e) {
      return geld(ctx, value);
    }
    return geld(ctx, value);
  }

  function prozent(ctx, n) {
    var value = Number(n);
    if (!Number.isFinite(value)) return '–';
    try {
      if (typeof ctx.prozent === 'function') return ctx.prozent(value);
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

  function storageAnzeige(parent, ctx, storage, berechneDanach, platzText) {
    var block = abschnitt(parent, 'Lager');
    var capacity = storage && storage.capacity !== undefined && storage.capacity !== null
      ? zahlRoh(storage.capacity) : null;
    var used = storage && storage.used !== undefined && storage.used !== null
      ? zahlRoh(storage.used) : null;
    var werte = el('div');
    block.appendChild(werte);

    var lagerWarnung = el('p', 're-lagerwarnung');
    block.appendChild(lagerWarnung);
    var balkenZeile = el('div', 'rd-balken-zeile');
    var balkenKopf = el('div', 'rd-balken-kopf');
    var balkenTitel = el('span');
    var balkenWert = el('span');
    balkenKopf.appendChild(balkenTitel);
    balkenKopf.appendChild(balkenWert);
    balkenZeile.appendChild(balkenKopf);
    var rahmen = el('div', 'rd-balken-rahmen');
    var fuellung = el('div', 'rd-balken-fuellung');
    rahmen.appendChild(fuellung);
    balkenZeile.appendChild(rahmen);
    block.appendChild(balkenZeile);

    function aktualisieren() {
      werte.replaceChildren();
      lagerWarnung.textContent = '';
      if (capacity === null || used === null) {
        balkenZeile.hidden = true;
        hinweis(werte);
        return;
      }
      balkenZeile.hidden = false;
      var danach = berechneDanach();
      var anteil = capacity > 0 ? danach / capacity : danach > 0 ? Infinity : 0;
      var prozentVoll = anteil * 100;
      textZeile(werte, 'Kapazität: ' + zahl(ctx, capacity) + ' · Lager aktuell: ' + zahl(ctx, used));
      textZeile(werte, 'Lager danach: ' + zahl(ctx, danach));
      balkenTitel.textContent = 'Lager danach';
      balkenWert.textContent = 'Lager danach ' + (Number.isFinite(prozentVoll) ? zahl(ctx, prozentVoll, 1) : '∞') + ' % voll';
      fuellung.style.width = Math.max(0, Math.min(100, Number.isFinite(prozentVoll) ? prozentVoll : 100)) + '%';
      if (prozentVoll > 100) {
        lagerWarnung.className = 'rd-negativ re-lagerwarnung';
        lagerWarnung.textContent = 'Lager übervoll: für die Mehrmenge zahlst du Zusatzmiete';
      } else if (prozentVoll > 90) {
        lagerWarnung.className = 'rd-note re-lagerwarnung';
        lagerWarnung.textContent = 'Lager fast voll';
      } else {
        lagerWarnung.className = 're-lagerwarnung';
      }
    }

    aktualisieren();

    var order = ctx.state && ctx.state.choices ? ctx.state.choices.storage_order : null;
    var feld = eingabefeld('Lager ausbauen (Flaschen)', order === undefined || order === null ? '' : order, 0, 1);
    feld.input.addEventListener('input', function () {
      var n = Math.max(0, zahlRoh(feld.input.value));
      ctx.entscheide({ storage_order: n > 0 ? n : null });
    });
    var form = el('div', 'rd-form');
    form.appendChild(feld.label);
    block.appendChild(form);
    textZeile(block, 'Einmalige Kosten, der Ausbau steht ab dem nächsten Halt bereit.', 'rd-note');
    if (platzText) textZeile(block, platzText, 'rd-leise');

    return { aktualisieren: aktualisieren, block: block };
  }

  function herstellerRender(root, ctx, data) {
    var block = abschnitt(root, 'Einkauf Rohstoffe');
    if (!data) {
      hinweis(block);
      return;
    }

    var need = data.need && typeof data.need === 'object' ? data.need : {};
    var stock = data.stock && typeof data.stock === 'object' ? data.stock : {};
    var prices = data.prices && typeof data.prices === 'object' ? data.prices : {};
    var history = array(data.history);
    var rohstoffe = Object.keys(need);
    [stock, prices].forEach(function (obj) {
      Object.keys(obj).forEach(function (name) {
        if (rohstoffe.indexOf(name) < 0) rohstoffe.push(name);
      });
    });
    history.forEach(function (item) {
      Object.keys(item || {}).forEach(function (name) {
        if (name !== 'label' && rohstoffe.indexOf(name) < 0) rohstoffe.push(name);
      });
    });

    var ziel = produktionsziel !== null ? produktionsziel : zahlRoh(data.target_bottles);
    var zielFeld = eingabefeld('Produktionsziel (Flaschen/Tag)', ziel, 0, 1);
    produktionsziel = ziel;
    var zielForm = el('div', 'rd-form');
    zielForm.appendChild(zielFeld.label);
    block.appendChild(zielForm);

    var eingaben = {};
    var bedarfWerte = {};
    function berechneBedarf(name, target) {
      var original = zahlRoh(need[name]);
      var targetBottles = zahlRoh(data.target_bottles);
      if (targetBottles === 0) return original;
      return original * target / targetBottles;
    }

    var tableRows = rohstoffe.map(function (name) {
      var calculated = berechneBedarf(name, ziel);
      bedarfWerte[name] = calculated;
      var choice = ctx.state && ctx.state.choices && ctx.state.choices.component_plan
        ? ctx.state.choices.component_plan[name] : undefined;
      var initial = choice !== undefined && choice !== null ? choice : Math.round(calculated);
      var feld = eingabefeld('Bestellmenge ' + name, initial, 0, 1);
      eingaben[name] = feld.input;
      return { name: name, feld: feld.input };
    });

    function aktuellerPlan() {
      var plan = {};
      rohstoffe.forEach(function (name) {
        plan[name] = Math.max(0, zahlRoh(eingaben[name].value));
      });
      return plan;
    }

    function sendPlan() {
      ctx.entscheide({ component_plan: aktuellerPlan() });
    }

    var kostenText = el('p');
    block.appendChild(tabelle([
      { key: 'name', label: 'Rohstoff' },
      { key: 'bedarf', label: 'Bedarf/Tag', value: function (row) { return zahl(ctx, bedarfWerte[row.name]); } },
      { key: 'stock', label: 'Lager aktuell', value: function (row) { return zahl(ctx, stock[row.name]); } },
      { key: 'price', label: 'Preis', value: function (row) {
        var current = prices[row.name];
        if (current === undefined || current === null) {
          for (var i = history.length - 1; i >= 0; i -= 1) {
            if (history[i] && history[i][row.name] !== undefined && history[i][row.name] !== null) {
              current = history[i][row.name];
              break;
            }
          }
        }
        row.currentPrice = current;
        return preis(ctx, current);
      } },
      { key: 'bewertung', label: 'Preisbewertung', value: function (row) {
        var values = history.map(function (item) {
          return item && item[row.name] !== undefined && item[row.name] !== null
            ? Number(item[row.name]) : NaN;
        }).filter(Number.isFinite);
        var current = row.currentPrice;
        if (current === undefined || current === null) {
          current = values.length ? values[values.length - 1] : null;
        }
        if (!values.length || current === null || !Number.isFinite(Number(current))) return 'Noch keine Kursdaten';
        var average = values.reduce(function (sum, n) { return sum + n; }, 0) / values.length;
        var difference = average !== 0 ? Number(current) / average - 1 : Number(current) === 0 ? 0 : null;
        var label = 'im Schnitt';
        var cls = '';
        if (difference !== null && Number(current) < average * 0.95) {
          label = 'günstig gegenüber Schnitt';
          cls = 'rd-positiv';
        } else if (difference !== null && Number(current) > average * 1.05) {
          label = 'teuer gegenüber Schnitt';
          cls = 'rd-negativ';
        }
        var text = label + (difference === null ? '' : ' (' + prozent(ctx, difference) + ')');
        return el('span', cls, text);
      } },
      { key: 'feld', label: 'Bestellfeld', value: function (row) { return row.feld; } }
    ], tableRows));

    var kursRaster = el('div', 're-raster');
    rohstoffe.forEach(function (name) {
      var chartBlock = el('div', 'rd-kachel re-diagramm');
      var historyValues = history.map(function (item) {
        return item && item[name] !== undefined && item[name] !== null ? item[name] : null;
      });
      var values = historyValues.map(Number).filter(Number.isFinite);
      var current = prices[name];
      if (current === undefined || current === null) {
        current = values.length ? values[values.length - 1] : null;
      }
      var average = values.length
        ? values.reduce(function (sum, n) { return sum + n; }, 0) / values.length : null;
      var rating = 'Noch keine Kursdaten';
      if (average !== null && current !== null && Number.isFinite(Number(current))) {
        var deviation = average !== 0 ? Number(current) / average - 1 : Number(current) === 0 ? 0 : null;
        if (deviation !== null && Number(current) < average * 0.95) rating = 'günstig gegenüber Schnitt';
        else if (deviation !== null && Number(current) > average * 1.05) rating = 'teuer gegenüber Schnitt';
        else rating = 'im Schnitt';
        if (deviation !== null) rating += ' (' + prozent(ctx, deviation) + ')';
      }
      chartBlock.appendChild(el('strong', '', name + ' · ' + rating));
      if (typeof ctx.linien === 'function') {
        try {
          var chart = ctx.linien([{ name: name, werte: historyValues, farbe: 'var(--akzent)' }], {
            labels: history.map(function (item) { return item ? item.label : ''; }),
            hoehe: 160
          });
          if (chart) chartBlock.appendChild(chart);
          else hinweis(chartBlock);
        } catch (e) {
          hinweis(chartBlock);
        }
      } else {
        hinweis(chartBlock);
      }
      kursRaster.appendChild(chartBlock);
    });
    if (rohstoffe.length) block.appendChild(kursRaster);

    block.appendChild(kostenText);
    var storage = storageAnzeige(root, ctx, data.storage, function () {
      var used = zahlRoh(data.storage && data.storage.used);
      var extra = 0;
      var plan = aktuellerPlan();
      rohstoffe.forEach(function (name) {
        var platz = data.space_per_component;
        if (platz && typeof platz === 'object') platz = platz[name];
        if (platz === undefined || platz === null) platz = 1;
        extra += zahlRoh(plan[name]) * zahlRoh(platz);
      });
      return used + extra;
    });

    function aktualisieren() {
      var plan = aktuellerPlan();
      var gesamt = 0;
      rohstoffe.forEach(function (name) {
        var current = prices[name];
        if (current === undefined || current === null) {
          for (var i = history.length - 1; i >= 0; i -= 1) {
            if (history[i] && history[i][name] !== undefined && history[i][name] !== null) {
              current = history[i][name];
              break;
            }
          }
        }
        gesamt += plan[name] * zahlRoh(current);
      });
      var target = Math.max(0, zahlRoh(zielFeld.input.value));
      kostenText.textContent = 'Kosten der Bestellung: ' + geld(ctx, gesamt) + ' pro Tag' +
        (target > 0 ? ' · pro Flasche: ' + preis(ctx, gesamt / target) : '');
      storage.aktualisieren();
    }

    rohstoffe.forEach(function (name) {
      eingaben[name].addEventListener('input', function () {
        sendPlan();
        aktualisieren();
      });
    });
    zielFeld.input.addEventListener('input', function () {
      ziel = Math.max(0, zahlRoh(zielFeld.input.value));
      produktionsziel = ziel;
      rohstoffe.forEach(function (name) {
        bedarfWerte[name] = berechneBedarf(name, ziel);
        eingaben[name].value = String(Math.max(0, Math.round(bedarfWerte[name])));
      });
      var bedarfCells = block.querySelectorAll('.rd-tabelle tbody tr');
      Array.prototype.forEach.call(bedarfCells, function (row, index) {
        if (rohstoffe[index] === undefined) return;
        var cell = row.children[1];
        if (cell) cell.textContent = zahl(ctx, bedarfWerte[rohstoffe[index]]);
      });
      sendPlan();
      aktualisieren();
    });

    sendPlan();
    aktualisieren();
  }

  function haendlerRender(root, ctx, data) {
    var nachfrageBlock = abschnitt(root, 'Nachfrage je Getränkeart');
    var markenBlock = abschnitt(root, 'Marken');
    if (!data) {
      hinweis(nachfrageBlock);
      hinweis(markenBlock);
      return;
    }

    var categories = array(data.categories);
    var brands = array(data.brands);
    var plan = Object.assign({}, data.plan || {});
    var choices = ctx.state && ctx.state.choices && ctx.state.choices.brand_plan;
    if (choices && typeof choices === 'object') {
      Object.keys(choices).forEach(function (id) {
        plan[id] = choices[id];
      });
    }

    var inputs = {};
    var brandRows = [];
    brands.forEach(function (brand) {
      var id = String(brand.id);
      var field = eingabefeld('Flaschen/Tag: ' + wert(brand, 'name', 'Marke'), zahlRoh(plan[id]), 0, 1);
      inputs[id] = field.input;
      brandRows.push({
        brand: brand,
        id: id,
        feld: field.input,
        _row: function (tr) {
          tr.dataset.marke = String(wert(brand, 'name', '')).toLocaleLowerCase('de');
          tr.dataset.kategorie = String(wert(brand, 'category', ''));
          brandRows[brandRows.length - 1].row = tr;
        }
      });
    });

    function menge(id) {
      return Math.max(0, zahlRoh(inputs[id] && inputs[id].value));
    }

    function planNachKategorie(key) {
      return brandRows.reduce(function (sum, row) {
        return String(wert(row.brand, 'category', '')) === String(key) ? sum + menge(row.id) : sum;
      }, 0);
    }

    var categoryValues = {};
    var catInputs = {};
    categories.forEach(function (category) {
      var key = String(category.key);
      var summe = planNachKategorie(key);
      var f = eingabefeld('Meine Menge (Flaschen/Tag): ' + wert(category, 'name', key), summe > 0 ? summe : '', 0, 1);
      catInputs[key] = f.input;
      categoryValues[key] = {
        plan: el('span'),
        coverage: el('span'),
        verteilt: el('span')
      };
    });

    function katMenge(key) {
      return Math.max(0, zahlRoh(catInputs[key] && catInputs[key].value));
    }

    function verteileKategorie(key) {
      var ziel = Math.round(katMenge(key));
      var zeilen = brandRows.filter(function (row) {
        return String(wert(row.brand, 'category', '')) === String(key);
      });
      if (ziel <= 0) {
        zeilen.forEach(function (row) { row.feld.value = ''; });
        return;
      }
      // Nur neu verteilen, wenn der Spieler die Marken nicht selbst angepasst hat (sonst würde beim
      // Tippen von «75000» schon die «7» verteilt und danach nie mehr nachgeführt).
      if (zeilen.some(function (row) { return menge(row.id) > 0 && !row.auto; })) return;
      var summeAnteil = zeilen.reduce(function (sum, row) { return sum + zahlRoh(row.brand.demand_share); }, 0);
      zeilen.forEach(function (row) {
        var anteil = summeAnteil > 0 ? zahlRoh(row.brand.demand_share) / summeAnteil : (zeilen.length ? 1 / zeilen.length : 0);
        var n = Math.round(ziel * anteil);
        row.feld.value = n > 0 ? String(n) : '';
        row.auto = true;
      });
    }

    nachfrageBlock.appendChild(tabelle([
      { key: 'name', label: 'Getränkeart', value: function (category) { return wert(category, 'name', '–'); } },
      { key: 'demand_per_day', label: 'Nachfrage/Tag', value: function (category) {
        return zahl(ctx, category.demand_per_day);
      } },
      { key: 'rival_cover', label: 'Abdeckung durch Konkurrenz', value: function (category) {
        var cover = zahlRoh(category.rival_cover);
        return prozent(ctx, cover >= 0 && cover <= 1 ? cover : cover / 100);
      } },
      { key: 'eingabe', label: 'Meine Menge (Flaschen/Tag)', value: function (category) {
        return catInputs[String(category.key)];
      } },
      { key: 'verteilt', label: 'Auf Marken verteilt', value: function (category) {
        return categoryValues[String(category.key)].verteilt;
      } },
      { key: 'plan', label: 'Meine Planmenge', value: function (category) {
        return categoryValues[String(category.key)].plan;
      } },
      { key: 'coverage', label: 'Abgedeckt', value: function (category) {
        return categoryValues[String(category.key)].coverage;
      } }
    ], categories));
    var totalZeile = document.createElement('p');
    totalZeile.className = 'rd-total';
    totalZeile.style.fontWeight = '600';
    nachfrageBlock.appendChild(totalZeile);

    var filter = el('div', 're-filter');
    var searchLabel = el('label', '', 'Marke suchen');
    var search = el('input');
    search.type = 'search';
    search.value = markensuche;
    search.setAttribute('aria-label', 'Marke suchen');
    searchLabel.appendChild(search);
    filter.appendChild(searchLabel);
    var categoryLabel = el('label', '', 'Getränkeart');
    var categorySelect = el('select');
    var allOption = el('option', '', 'Alle Getränkearten');
    allOption.value = '';
    categorySelect.appendChild(allOption);
    categories.forEach(function (category) {
      var option = el('option', '', wert(category, 'name', category.key));
      option.value = String(category.key);
      categorySelect.appendChild(option);
    });
    categorySelect.value = markenkategorie;
    categoryLabel.appendChild(categorySelect);
    filter.appendChild(categoryLabel);
    markenBlock.appendChild(filter);

    var costText = el('p');
    var specialtyText = el('p');
    var table = tabelle([
      { key: 'name', label: 'Marke', value: function (row) { return wert(row.brand, 'name', '–'); } },
      { key: 'category', label: 'Getränkeart', value: function (row) {
        var category = categories.find(function (item) {
          return String(item.key) === String(row.brand.category);
        });
        return category ? wert(category, 'name', row.brand.category) : wert(row.brand, 'category', '–');
      } },
      { key: 'owner_name', label: 'Besitzer', value: function (row) { return wert(row.brand, 'owner_name', '–'); } },
      { key: 'positioning', label: 'Positionierung', value: function (row) { return wert(row.brand, 'positioning', '–'); } },
      { key: 'quality', label: 'Qualität', value: function (row) { return zahl(ctx, row.brand.quality); } },
      { key: 'reputation', label: 'Ruf', value: function (row) { return zahl(ctx, row.brand.reputation); } },
      { key: 'price', label: 'Preis', value: function (row) { return preis(ctx, row.brand.price); } },
      { key: 'demand_share', label: 'Nachfrageanteil', value: function (row) {
        return prozent(ctx, row.brand.demand_share);
      } },
      { key: 'feld', label: 'Flaschen/Tag', value: function (row) { return row.feld; } }
    ], brandRows);
    markenBlock.appendChild(table);
    var note = el('div', 'rd-kachel');
    note.appendChild(el('strong', '', 'Regal-Fixkosten'));
    note.appendChild(el('p', '', 'Für jede Getränkeart, die du führst (Lager oder Bestellmenge > 0), fallen Regal-Fixkosten pro Jahr an. Wenige Sorten gut zu führen (Spezialisierung) ist oft günstiger.'));
    note.appendChild(specialtyText);
    markenBlock.appendChild(note);
    markenBlock.appendChild(costText);

    var storage = storageAnzeige(root, ctx, data.storage, function () {
      return zahlRoh(data.storage && data.storage.used) + brandRows.reduce(function (sum, row) {
        return sum + menge(row.id);
      }, 0);
    });

    function sendePlan() {
      var result = {};
      brandRows.forEach(function (row) {
        var n = menge(row.id);
        if (n > 0) result[row.id] = n;
      });
      ctx.entscheide({ brand_plan: result });
    }

    function filterMarken() {
      markensuche = search.value;
      markenkategorie = categorySelect.value;
      var query = markensuche.toLocaleLowerCase('de').trim();
      brandRows.forEach(function (row) {
        if (!row.row) return;
        var matchesName = !query || row.row.dataset.marke.indexOf(query) >= 0;
        var matchesCategory = !markenkategorie || row.row.dataset.kategorie === markenkategorie;
        row.row.hidden = !(matchesName && matchesCategory);
      });
    }

    function aktualisieren() {
      categories.forEach(function (category) {
        var key = String(category.key);
        var planned = planNachKategorie(category.key);
        var demand = zahlRoh(category.demand_per_day);
        categoryValues[key].plan.textContent = zahl(ctx, planned);
        var ziel = Math.round(katMenge(key));
        var v = categoryValues[key].verteilt;
        if (ziel > 0 || planned > 0) {
          v.textContent = 'verteilt ' + zahl(ctx, planned) + ' von ' + zahl(ctx, ziel) + ' Flaschen';
          v.className = Math.round(planned) !== ziel ? 'rd-negativ' : '';
        } else {
          v.textContent = 'nicht geführt';
          v.className = 'rd-leise';
        }
        categoryValues[key].coverage.textContent = prozent(ctx, demand > 0 ? planned / demand : 0);
      });
      if (totalZeile) {
        var sumDemand = 0, sumZiel = 0, sumPlan = 0;
        categories.forEach(function (category) {
          sumDemand += zahlRoh(category.demand_per_day);
          sumZiel += Math.round(katMenge(String(category.key)));
          sumPlan += planNachKategorie(category.key);
        });
        totalZeile.textContent = 'Total: Nachfrage im Markt ' + zahl(ctx, sumDemand) + ' Flaschen/Tag · deine Menge '
          + zahl(ctx, sumZiel) + ' · auf Marken verteilt ' + zahl(ctx, sumPlan) + ' Flaschen/Tag';
      }
      var totalCost = brandRows.reduce(function (sum, row) {
        return sum + menge(row.id) * zahlRoh(row.brand.price);
      }, 0);
      costText.textContent = 'Kosten der Bestellung: ' + geld(ctx, totalCost) + ' pro Tag';
      var ledCategories = categories.filter(function (category) {
        return planNachKategorie(category.key) > 0;
      }).length;
      specialtyText.textContent = 'Du führst aktuell ' + zahl(ctx, ledCategories) + ' Getränkearten';
      brandRows.forEach(function (row) {
        if (!row.row) return;
        row.row.className = menge(row.id) > 0 ? 'rd-eigen' : '';
      });
      storage.aktualisieren();
    }

    search.addEventListener('input', filterMarken);
    categorySelect.addEventListener('change', filterMarken);
    categories.forEach(function (category) {
      var key = String(category.key);
      catInputs[key].addEventListener('input', function () {
        verteileKategorie(key);
        sendePlan();
        aktualisieren();
      });
    });
    brandRows.forEach(function (row) {
      row.feld.addEventListener('input', function () {
        row.auto = false;  // vom Spieler angepasst: nicht mehr automatisch überschreiben
        var key = String(wert(row.brand, 'category', ''));
        if (catInputs[key] && katMenge(key) <= 0) {
          var summe = planNachKategorie(key);
          catInputs[key].value = summe > 0 ? String(summe) : '';
        }
        sendePlan();
        aktualisieren();
      });
    });
    filterMarken();
    aktualisieren();
  }

  function lieferungenRender(root, ctx, data) {
    var block = abschnitt(root, 'Lieferungen');
    if (!data) {
      hinweis(block);
      return;
    }

    var suppliers = array(data.suppliers);
    var orderedTotal = suppliers.reduce(function (sum, supplier) { return sum + zahlRoh(supplier.ordered); }, 0);
    var deliveredTotal = suppliers.reduce(function (sum, supplier) { return sum + zahlRoh(supplier.delivered); }, 0);
    var rows = suppliers.map(function (supplier) {
      return {
        name: wert(supplier, 'name', '–'),
        ordered: supplier.ordered,
        delivered: supplier.delivered,
        open: supplier.open,
        fill_rate: supplier.fill_rate,
        supplier: supplier
      };
    });
    rows.push({
      name: 'Gesamt',
      ordered: orderedTotal,
      delivered: deliveredTotal,
      open: suppliers.reduce(function (sum, supplier) { return sum + zahlRoh(supplier.open); }, 0),
      fill_rate: orderedTotal > 0 ? deliveredTotal / orderedTotal : 0,
      gesamt: true
    });

    block.appendChild(tabelle([
      { key: 'name', label: 'Lieferant' },
      { key: 'ordered', label: 'Bestellt', value: function (row) { return zahl(ctx, row.ordered); } },
      { key: 'delivered', label: 'Geliefert', value: function (row) { return zahl(ctx, row.delivered); } },
      { key: 'open', label: 'Offen', value: function (row) { return zahl(ctx, row.open); } },
      { key: 'fill_rate', label: 'Lieferquote', value: function (row) {
        var rate = row.gesamt ? row.fill_rate : row.supplier.fill_rate;
        if (rate === undefined || rate === null) {
          var ordered = zahlRoh(row.ordered);
          rate = ordered > 0 ? zahlRoh(row.delivered) / ordered : 0;
        }
        return el('span', zahlRoh(rate) < 0.9 ? 'rd-negativ' : '', prozent(ctx, zahlRoh(rate)));
      } }
    ], rows));

    var alreadyCancelled = !!(ctx.state && ctx.state.choices && ctx.state.choices.cancel_open_orders);
    var button = el('button', '', 'Offene Bestellungen stornieren');
    button.type = 'button';
    button.disabled = alreadyCancelled;
    var status = el('p', 're-status rd-leise', alreadyCancelled
      ? 'Wird mit „Runde beenden“ storniert.' : '');
    button.addEventListener('click', function () {
      if (button.disabled) return;
      if (!window.confirm('Alle offenen Bestellungen stornieren? Das kostet nichts, die Ware kommt aber nicht.')) return;
      ctx.entscheide({ cancel_open_orders: true });
      button.disabled = true;
      status.textContent = 'Wird mit „Runde beenden“ storniert.';
    });
    block.appendChild(button);
    block.appendChild(status);
  }

  async function render(elm, ctx) {
    elm.replaceChildren();
    var root = el('div', 'rd-reiter');
    elm.appendChild(root);

    var p = await laden(ctx, 'purchasing');
    var l = await laden(ctx, 'deliveries');
    var branch = ctx && ctx.state && ctx.state.firm ? ctx.state.firm.branch : '';

    if (branch === 'hersteller') herstellerRender(root, ctx, p);
    else haendlerRender(root, ctx, p);
    lieferungenRender(root, ctx, l);
  }

  REITER.einkauf = { async render(elm, ctx) { return render(elm, ctx); } };
}());
