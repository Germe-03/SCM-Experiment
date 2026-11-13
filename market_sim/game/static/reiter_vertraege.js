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

  function geplant(ctx) {
    try {
      if (!ctx || typeof ctx.geplant !== 'function') return {};
      var result = ctx.geplant();
      return result && typeof result === 'object' ? result : {};
    } catch (e) {
      return {};
    }
  }

  function planen(ctx, key, value) {
    try {
      if (ctx && typeof ctx.plane === 'function') ctx.plane(key, value);
    } catch (e) {
      // Ein fehlender Planungszugriff soll den Reiter nicht abbrechen.
    }
  }

  function schaltflaeche(text, handler) {
    var button = el('button', '', text);
    button.type = 'button';
    button.addEventListener('click', handler);
    return button;
  }

  function partnerName(partners, id, fallback) {
    var match = partners.find(function (partner) {
      return partner && partner.id !== undefined && partner.id !== null
        && id !== undefined && id !== null && String(partner.id) === String(id);
    });
    if (match && match.name !== undefined && match.name !== null && match.name !== '') {
      return String(match.name);
    }
    if (fallback !== undefined && fallback !== null && fallback !== '') return String(fallback);
    return id === undefined || id === null || id === '' ? '–' : String(id);
  }

  function vertragsName(contract, side, partners) {
    var id = contract && contract[side];
    var nameKey = side + '_name';
    // Eigene Firma mit Namen statt interner Kennung (z.B. factory_p01).
    var eigene = (typeof aktuellerStand !== 'undefined' && aktuellerStand && aktuellerStand.firm) || null;
    if (eigene && String(id) === String(eigene.id)) return String(eigene.name || id) + ' (du)';
    return partnerName(partners, id, contract && contract[nameKey]);
  }

  function kategorie(contract) {
    return !contract || contract.category === null || contract.category === undefined
      ? 'alle Getränke' : String(contract.category);
  }

  function vertragsSpalten(ctx, partners) {
    return [
      { key: 'supplier', label: 'Lieferant', value: function (contract) {
        return vertragsName(contract, 'supplier', partners);
      } },
      { key: 'buyer', label: 'Kunde', value: function (contract) {
        return vertragsName(contract, 'buyer', partners);
      } },
      { key: 'category', label: 'Getränkeart', value: kategorie },
      { key: 'units_per_day', label: 'Flaschen/Tag', value: function (contract) {
        return zahl(ctx, contract && contract.units_per_day);
      } },
      { key: 'price', label: 'Preis', value: function (contract) {
        return preis(ctx, contract && contract.price);
      } },
      { key: 'start_day', label: 'Start (Tag)', value: function (contract) {
        return zahl(ctx, contract && contract.start_day);
      } },
      { key: 'days', label: 'Laufzeit', value: function (contract) {
        return zahl(ctx, contract && contract.days);
      } },
      { key: 'end_day', label: 'Ende', value: function (contract) {
        var start = Number(contract && contract.start_day);
        var days = Number(contract && contract.days);
        return Number.isFinite(start) && Number.isFinite(days) ? zahl(ctx, start + days) : '–';
      } }
    ];
  }

  // Vertragsanpassung: Vorschlag machen sowie offene Änderungen annehmen oder ablehnen.
  function anpassungUi(ctx, contract, action, plan) {
    var id = contract.id;
    var change = contract.change && typeof contract.change === 'object' ? contract.change : null;
    var box = el('div', 'rd-anpassung');
    action.appendChild(box);
    function gleich(a, b) {
      return a !== undefined && a !== null && id !== undefined && String(a) === String(b);
    }
    var geplantVorschlag = plan.contract_change_propose;
    if (Array.isArray(geplantVorschlag)) {
      geplantVorschlag = geplantVorschlag.find(function (p) { return p && gleich(p.id, id); });
    }
    if (change && !change.by_me) {
      box.appendChild(el('p', 'rd-negativ', 'Anpassung vorgeschlagen: '
        + zahl(ctx, change.units_per_day) + ' Flaschen/Tag zu ' + preis(ctx, change.price)));
      var status = el('p', 'rd-leise');
      if (gleich(plan.contract_change_accept, id)) status.textContent = 'Geplant: annehmen';
      else if (gleich(plan.contract_change_decline, id)) status.textContent = 'Geplant: ablehnen';
      box.appendChild(status);
      box.appendChild(schaltflaeche('Annehmen', function () {
        planen(ctx, 'contract_change_decline', null);
        planen(ctx, 'contract_change_accept', id);
        status.textContent = 'Geplant: annehmen';
      }));
      box.appendChild(schaltflaeche('Ablehnen', function () {
        planen(ctx, 'contract_change_accept', null);
        planen(ctx, 'contract_change_decline', id);
        status.textContent = 'Geplant: ablehnen';
      }));
      return;
    }
    if (change && change.by_me) {
      box.appendChild(el('p', 'rd-leise', 'Dein Vorschlag: '
        + zahl(ctx, change.units_per_day) + ' Flaschen/Tag zu ' + preis(ctx, change.price)
        + ' – wartet auf Antwort der Gegenseite.'));
      return;
    }
    if (geplantVorschlag) {
      box.appendChild(el('p', 'rd-leise', 'Anpassung wird mit «Runde beenden» vorgeschlagen.'));
      box.appendChild(schaltflaeche('Zurücknehmen', function () {
        planen(ctx, 'contract_change_propose', null);
        box.replaceChildren(el('span', 'rd-leise', 'Zurückgenommen.'));
      }));
      return;
    }
    var form = el('div', 'rd-form');
    form.hidden = true;
    var units = el('input', 're-eingabe');
    units.type = 'number';
    units.min = '1';
    units.step = '1';
    units.value = String(Math.round(zahlRoh(contract.units_per_day)));
    units.setAttribute('aria-label', 'Neue Flaschen pro Tag');
    var price = el('input', 're-eingabe');
    price.type = 'number';
    price.min = '0';
    price.step = '0.01';
    price.value = zahlRoh(contract.price).toFixed(2);
    price.setAttribute('aria-label', 'Neuer Preis pro Flasche (CHF)');
    var ul = el('label', '', 'Flaschen/Tag');
    ul.appendChild(units);
    var pl = el('label', '', 'Preis (CHF)');
    pl.appendChild(price);
    var meldung = el('p', 'rd-leise');
    form.appendChild(ul);
    form.appendChild(pl);
    form.appendChild(schaltflaeche('Vorschlag planen', function () {
      var u = Number(units.value);
      var p = Number(price.value);
      if (!Number.isFinite(u) || u <= 0 || !Number.isFinite(p) || p <= 0) {
        meldung.className = 'rd-negativ';
        meldung.textContent = 'Menge und Preis müssen grösser als 0 sein.';
        return;
      }
      planen(ctx, 'contract_change_propose', { id: id, units_per_day: Math.round(u), price: p });
      form.hidden = true;
      box.replaceChildren(el('span', 'rd-leise', 'Anpassung wird mit «Runde beenden» vorgeschlagen.'));
    }));
    form.appendChild(meldung);
    box.appendChild(schaltflaeche('Anpassung vorschlagen', function () {
      form.hidden = !form.hidden;
    }));
    box.appendChild(form);
  }

  async function render(elm, ctx) {
    elm.replaceChildren();
    var root = el('div', 'rd-reiter');
    elm.appendChild(root);

    var v = await laden(ctx, 'contracts');
    if (!v) {
      var nichtVerfuegbar = abschnitt(root, 'Verträge');
      hinweis(nichtVerfuegbar);
      return;
    }

    // Ergebnis der letzten Runde zu Verträgen gut sichtbar oben anzeigen.
    var ergebnisse = array(ctx.state && ctx.state.order_results).filter(function (r) {
      return r && /Vertrag|Paar|Angebot|Partner/i.test(String(r.message || ''));
    });
    if (ergebnisse.length) {
      var ergebnisBlock = abschnitt(root, 'Ergebnis der letzten Runde');
      ergebnisse.forEach(function (r) {
        var text = String(r.message || '');
        if (/schon einen offenen/i.test(text)) {
          text += ' – Dieser Partner hat dir bereits selbst ein Angebot gemacht. Nimm es unten bei «Angebote an dich» an.';
        }
        ergebnisBlock.appendChild(el('p', r.ok ? 'rd-positiv' : 'rd-negativ', (r.ok ? '✓ ' : '✗ ') + text));
      });
    }

    var partners = array(v.partners).filter(function (partner) {
      return partner && typeof partner === 'object';
    });
    var active = array(v.active).filter(function (contract) {
      return contract && typeof contract === 'object';
    });
    var offers = array(v.offers).filter(function (contract) {
      return contract && typeof contract === 'object';
    });
    var proposed = array(v.proposed).filter(function (contract) {
      return contract && typeof contract === 'object';
    });
    var partnerById = {};
    partners.forEach(function (partner) {
      if (partner.id !== undefined && partner.id !== null) {
        partnerById[String(partner.id)] = partner;
      }
    });

    var partnerBlock = abschnitt(root, 'Partner und Marktpreise');
    partnerBlock.appendChild(tabelle([
      { key: 'name', label: 'Name', value: function (partner) {
        return partner.name === undefined || partner.name === null ? '–' : partner.name;
      } },
      { key: 'stage', label: 'Stufe' },
      { key: 'role', label: 'Rolle' },
      { key: 'market_price', label: 'Marktpreis', value: function (partner) {
        return preis(ctx, partner.market_price);
      } }
    ], partners));

    var formBlock = abschnitt(root, 'Vertrag vorschlagen');
    var form = el('div', 'rd-form');
    formBlock.appendChild(form);

    var partnerLabel = el('label', '', 'Partner');
    var partnerSelect = el('select', 're-eingabe');
    var partnerLeer = el('option', '', 'Partner wählen');
    partnerLeer.value = '';
    partnerSelect.appendChild(partnerLeer);
    partners.forEach(function (partner) {
      var name = partner.name === undefined || partner.name === null ? String(partner.id || 'Partner') : String(partner.name);
      var role = partner.role === undefined || partner.role === null ? '' : String(partner.role);
      var option = el('option', '', name + (role ? ' (' + role + ')' : ''));
      option.value = partner.id === undefined || partner.id === null ? '' : String(partner.id);
      partnerSelect.appendChild(option);
    });
    partnerSelect.setAttribute('aria-label', 'Partner');
    partnerLabel.appendChild(partnerSelect);
    form.appendChild(partnerLabel);

    var stateCategories = ctx && ctx.state ? ctx.state.categories : null;
    var hasCategories = Array.isArray(stateCategories);
    var categoryInput;
    var categoryLabel = el('label', '', 'Getränkeart');
    if (hasCategories) {
      categoryInput = el('select', 're-eingabe');
      var allCategories = el('option', '', 'alle Getränke');
      allCategories.value = '';
      categoryInput.appendChild(allCategories);
      stateCategories.forEach(function (category) {
        var id;
        var name;
        if (category && typeof category === 'object') {
          id = category.id !== undefined && category.id !== null ? category.id : category.name;
          name = category.name !== undefined && category.name !== null ? category.name : id;
        } else {
          id = category;
          name = category;
        }
        if (id === undefined || id === null || name === undefined || name === null) return;
        var option = el('option', '', String(name));
        option.value = String(id);
        categoryInput.appendChild(option);
      });
    } else {
      categoryInput = el('input', 're-eingabe');
      categoryInput.type = 'text';
      categoryInput.placeholder = 'leer = alle Getränke';
    }
    categoryInput.setAttribute('aria-label', 'Getränkeart');
    categoryLabel.appendChild(categoryInput);
    form.appendChild(categoryLabel);

    function nummerFeld(labelText, min, step, initial) {
      var label = el('label', '', labelText);
      var input = el('input', 're-eingabe');
      input.type = 'number';
      input.min = String(min);
      input.step = String(step);
      input.value = initial === undefined || initial === null ? '' : String(initial);
      input.setAttribute('aria-label', labelText);
      label.appendChild(input);
      form.appendChild(label);
      return input;
    }

    var unitsInput = nummerFeld('Flaschen pro Tag', 1, 1, '');
    var priceLabel = el('label', '', 'Preis pro Flasche (CHF)');
    var priceInput = el('input', 're-eingabe');
    priceInput.type = 'number';
    priceInput.min = '0';
    priceInput.step = '0.01';
    priceInput.setAttribute('aria-label', 'Preis pro Flasche (CHF)');
    priceLabel.appendChild(priceInput);
    var marketText = el('span', 'rd-leise', 'Marktpreis: –');
    priceLabel.appendChild(marketText);
    form.appendChild(priceLabel);
    // Laufzeit als Auswahl: Rest des Jahres, dieses und nächstes Jahr, 5 Jahre (in Tagen gerechnet).
    var monat = Number(ctx && ctx.state && ctx.state.month) || 1;
    var restTage = Math.max(1, (12 - monat + 1) * 30);
    var daysLabel = el('label', '', 'Laufzeit');
    var daysInput = el('select', 're-eingabe');
    daysInput.setAttribute('aria-label', 'Laufzeit');
    [['Rest des aktuellen Jahres', restTage], ['2 Jahre (dieses und nächstes)', restTage + 360],
     ['5 Jahre', restTage + 4 * 360]].forEach(function (eintrag) {
      var o = el('option', '', eintrag[0] + ' (' + eintrag[1] + ' Tage)');
      o.value = String(eintrag[1]);
      daysInput.appendChild(o);
    });
    daysLabel.appendChild(daysInput);
    form.appendChild(daysLabel);
    var priceTouched = false;

    function ausgewaehlterPartner() {
      return partnerById[partnerSelect.value] || null;
    }

    function aktualisiereMarktpreis() {
      var partner = ausgewaehlterPartner();
      if (!partner) {
        marketText.textContent = 'Marktpreis: –';
        return;
      }
      marketText.textContent = 'Marktpreis: ' + preis(ctx, partner.market_price);
      var offen = array(v.offers).filter(function (c) {
        return c && (String(c.supplier) === String(partner.id) || String(c.buyer) === String(partner.id));
      });
      if (offen.length) {
        marketText.textContent += ' · Achtung: Dieser Partner hat dir schon ein Angebot gemacht ('
          + zahl(ctx, offen[0].units_per_day) + ' Flaschen/Tag zu ' + preis(ctx, offen[0].price)
          + '). Ein eigener Vorschlag wird abgelehnt, solange das Angebot offen ist.';
      }
      if (!priceTouched && (priceInput.value === '' || priceInput.dataset.marktpreis === 'true')) {
        if (partner.market_price !== undefined && partner.market_price !== null
          && Number.isFinite(Number(partner.market_price))) {
          priceInput.value = Number(partner.market_price).toFixed(2);
          priceInput.dataset.marktpreis = 'true';
        }
      }
    }

    partnerSelect.addEventListener('change', aktualisiereMarktpreis);
    priceInput.addEventListener('input', function () {
      priceTouched = true;
      delete priceInput.dataset.marktpreis;
    });

    var formStatus = el('p', 're-status rd-leise');
    formBlock.appendChild(formStatus);
    var proposeButton = schaltflaeche('Vorschlag planen', function () {
      var partnerId = partnerSelect.value;
      var units = Number(unitsInput.value);
      var priceValue = Number(priceInput.value);
      var days = Number(daysInput.value);
      if (!partnerId) {
        formStatus.className = 're-status rd-negativ';
        formStatus.textContent = 'Bitte wähle einen Partner.';
        return;
      }
      if (!Number.isFinite(units) || units <= 0) {
        formStatus.className = 're-status rd-negativ';
        formStatus.textContent = 'Bitte gib eine Flaschenmenge grösser als 0 ein.';
        return;
      }
      if (!Number.isFinite(priceValue) || priceValue <= 0) {
        formStatus.className = 're-status rd-negativ';
        formStatus.textContent = 'Bitte gib einen Preis grösser als 0 ein.';
        return;
      }
      if (!Number.isFinite(days) || days < 1) {
        formStatus.className = 're-status rd-negativ';
        formStatus.textContent = 'Die Laufzeit muss mindestens 1 Tag betragen.';
        return;
      }
      var categoryValue = String(categoryInput.value || '').trim();
      planen(ctx, 'contract_propose', {
        partner: partnerId,
        category: categoryValue || null,
        units_per_day: Math.round(units),
        price: priceValue,
        days: Math.round(days)
      });
      formStatus.className = 're-status rd-leise';
      formStatus.textContent = 'Vorschlag wird mit «Runde beenden» abgeschickt.';
      undoButton.hidden = false;
    });
    formBlock.appendChild(proposeButton);

    var undoButton = schaltflaeche('Zurücknehmen', function () {
      planen(ctx, 'contract_propose', null);
      formStatus.className = 're-status rd-leise';
      formStatus.textContent = '';
      undoButton.hidden = true;
    });
    undoButton.hidden = true;
    formBlock.appendChild(undoButton);

    var currentPlan = geplant(ctx);
    if (currentPlan.contract_propose) {
      formStatus.className = 're-status rd-leise';
      formStatus.textContent = 'Vorschlag wird mit «Runde beenden» abgeschickt.';
      undoButton.hidden = false;
    }
    textZeile(formBlock,
      'Die Gegenseite entscheidet nach «Runde beenden». Lieferketten: Hersteller → Verteiler → Grosshändler → Detailhändler/Gastro.',
      'rd-note');

    var activeBlock = abschnitt(root, 'Aktive Verträge');
    var activePlan = geplant(ctx);
    var activeRows = active.map(function (contract) {
      var id = contract.id;
      var isPlanned = activePlan.contract_cancel !== undefined && activePlan.contract_cancel !== null
        && id !== undefined && String(activePlan.contract_cancel) === String(id);
      var action = el('div');
      if (isPlanned) {
        action.appendChild(el('span', 'rd-leise', 'Wird mit «Runde beenden» gekündigt.'));
      } else {
        var button = schaltflaeche('Kündigen', function () {
          var confirmAction = false;
          try {
            confirmAction = typeof window.confirm === 'function'
              && window.confirm('Vertrag wirklich kündigen?');
          } catch (e) {
            confirmAction = false;
          }
          if (!confirmAction) return;
          planen(ctx, 'contract_cancel', id);
          button.disabled = true;
          action.replaceChildren(el('span', 'rd-leise', 'Wird mit «Runde beenden» gekündigt.'));
        });
        action.appendChild(button);
      }
      anpassungUi(ctx, contract, action, activePlan);
      contract._action = action;
      return contract;
    });
    textZeile(activeBlock,
      'Die Vertragsmenge ist eine Mindestmenge: der Kunde bestellt mindestens so viel, du lieferst mindestens so viel.',
      'rd-note');
    var activeColumns = vertragsSpalten(ctx, partners).concat([
      { key: '_action', label: 'Aktion', value: function (contract) { return contract._action; } }
    ]);
    activeBlock.appendChild(tabelle(activeColumns, activeRows));

    var offerBlock = abschnitt(root, 'Angebote an dich');
    textZeile(offerBlock, 'Pro Runde kannst du je ein Angebot annehmen und eines ablehnen.', 'rd-leise');
    var offerPlan = geplant(ctx);
    var offerRows = offers.map(function (contract) {
      var id = contract.id;
      var accepted = offerPlan.contract_accept !== undefined && offerPlan.contract_accept !== null
        && id !== undefined && String(offerPlan.contract_accept) === String(id);
      var declined = offerPlan.contract_decline !== undefined && offerPlan.contract_decline !== null
        && id !== undefined && String(offerPlan.contract_decline) === String(id);
      var action = el('div');
      var status = el('p', 'rd-leise');
      if (accepted) status.textContent = 'Geplant: annehmen';
      else if (declined) status.textContent = 'Geplant: ablehnen';
      action.appendChild(status);

      var acceptButton = schaltflaeche('Annehmen', function () {
        if (offerPlan.contract_decline !== undefined && offerPlan.contract_decline !== null
          && id !== undefined && String(offerPlan.contract_decline) === String(id)) {
          planen(ctx, 'contract_decline', null);
          offerPlan.contract_decline = null;
        }
        planen(ctx, 'contract_accept', id);
        offerPlan.contract_accept = id;
        status.textContent = 'Geplant: annehmen';
        status.className = 'rd-leise';
      });
      var declineButton = schaltflaeche('Ablehnen', function () {
        if (offerPlan.contract_accept !== undefined && offerPlan.contract_accept !== null
          && id !== undefined && String(offerPlan.contract_accept) === String(id)) {
          planen(ctx, 'contract_accept', null);
          offerPlan.contract_accept = null;
        }
        planen(ctx, 'contract_decline', id);
        offerPlan.contract_decline = id;
        status.textContent = 'Geplant: ablehnen';
        status.className = 'rd-leise';
      });
      acceptButton.disabled = accepted;
      declineButton.disabled = declined;
      action.appendChild(acceptButton);
      action.appendChild(declineButton);
      contract._action = action;
      return contract;
    });
    offerBlock.appendChild(tabelle(vertragsSpalten(ctx, partners).concat([
      { key: '_action', label: 'Aktion', value: function (contract) { return contract._action; } }
    ]), offerRows));

    var proposedBlock = abschnitt(root, 'Meine Vorschläge');
    var firm = ctx && ctx.state && ctx.state.firm ? ctx.state.firm : null;
    var myId = firm && firm.id !== undefined && firm.id !== null ? firm.id
      : ctx && ctx.state && ctx.state.firm_id !== undefined ? ctx.state.firm_id : null;
    var proposedRows = proposed.map(function (contract) {
      var supplierId = contract.supplier;
      var buyerId = contract.buyer;
      var partner;
      if (myId !== null && myId !== undefined) {
        if (supplierId !== undefined && String(supplierId) === String(myId)) {
          partner = partnerName(partners, buyerId, contract.buyer_name);
        } else if (buyerId !== undefined && String(buyerId) === String(myId)) {
          partner = partnerName(partners, supplierId, contract.supplier_name);
        }
      }
      if (!partner) {
        partner = vertragsName(contract, 'supplier', partners) + ' → ' + vertragsName(contract, 'buyer', partners);
      }
      var statusText = contract.status === undefined || contract.status === null ? '–' : String(contract.status);
      var statusClass = contract.status === 'aktiv' ? 'rd-positiv'
        : contract.status === 'abgelehnt' ? 'rd-negativ'
          : contract.status === 'angeboten' ? 'rd-leise' : '';
      return {
        partner: partner,
        category: kategorie(contract),
        units_per_day: contract.units_per_day,
        price: contract.price,
        days: contract.days,
        status: el('span', statusClass, statusText)
      };
    });
    proposedBlock.appendChild(tabelle([
      { key: 'partner', label: 'Partner' },
      { key: 'category', label: 'Getränkeart' },
      { key: 'units_per_day', label: 'Flaschen/Tag', value: function (contract) {
        return zahl(ctx, contract.units_per_day);
      } },
      { key: 'price', label: 'Preis', value: function (contract) {
        return preis(ctx, contract.price);
      } },
      { key: 'days', label: 'Laufzeit', value: function (contract) {
        return zahl(ctx, contract.days);
      } },
      { key: 'status', label: 'Status' }
    ], proposedRows));
  }

  REITER.vertraege = { async render(elm, ctx) { return render(elm, ctx); } };
}());
