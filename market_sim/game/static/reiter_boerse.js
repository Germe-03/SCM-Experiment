'use strict';

(function () {
  var REITER = window.REITER = window.REITER || {};
  var alt = REITER.boerse;
  var auswahl = null;
  var startBeiHundert = true;
  var palette = [
    '#2563eb', '#dc2626', '#16a34a', '#9333ea',
    '#ea580c', '#0891b2', '#c026d3', '#65a30d',
    '#4f46e5', '#be123c', '#0d9488', '#a16207'
  ];
  var stilText = [
    '.rb-layout{display:grid;grid-template-columns:300px minmax(0,1fr);gap:1rem;align-items:start}',
    '.rb-seite,.rb-haupt{min-width:0}',
    '.rb-filter{display:grid;gap:.6rem;margin-bottom:.75rem}',
    '.rb-filter input,.rb-filter select{max-width:100%;box-sizing:border-box}',
    '.rb-aktionen{display:flex;flex-wrap:wrap;gap:.4rem}',
    '.rb-liste{max-height:460px;overflow-y:auto;border:1px solid var(--rand);border-radius:.4rem}',
    '.rb-zeile{display:grid;grid-template-columns:auto auto minmax(0,1fr);gap:.5rem;align-items:center;padding:.5rem;border-bottom:1px solid var(--rand)}',
    '.rb-zeile:last-child{border-bottom:0}',
    '.rb-zeile label{min-width:0;cursor:pointer}',
    '.rb-firmenname{display:block;overflow-wrap:anywhere}',
    '.rb-kurs{display:block;color:var(--text-leise);font-size:.85em}',
    '.rb-nicht-kotiert{color:var(--text-leise)}',
    '.rb-punkt{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;flex:none}',
    '.rb-optionen{display:flex;flex-wrap:wrap;gap:.75rem;align-items:center;margin-bottom:.5rem}',
    '.rb-hinweis{margin:.5rem 0;color:var(--text-leise)}',
    '.rb-chart{height:460px;min-width:0}',
    '.rb-chart>div{max-width:100%}',
    '.rb-keine{padding:.75rem;border:1px solid var(--rand);border-radius:.4rem;color:var(--text-leise)}',
    '.rb-zahlen{margin-top:.75rem}',
    '@media(max-width:800px){.rb-layout{grid-template-columns:1fr}}'
  ].join('');

  if (typeof document !== 'undefined' && document.head && !document.getElementById('reiter-boerse-stil')) {
    var stil = document.createElement('style');
    stil.id = 'reiter-boerse-stil';
    stil.textContent = stilText;
    document.head.appendChild(stil);
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function array(value) {
    return Array.isArray(value) ? value : [];
  }

  function finite(value) {
    var number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function formatZahl(ctx, value, stellen) {
    var number = finite(value);
    if (number === null) return '–';
    try {
      if (ctx && typeof ctx.zahl === 'function') return ctx.zahl(number, stellen);
    } catch (e) {
      // Fallback auf die lokale Formatierung.
    }
    return new Intl.NumberFormat('de-CH', { maximumFractionDigits: stellen === undefined ? 2 : stellen }).format(number);
  }

  function formatPreis(ctx, value) {
    var number = finite(value);
    if (number === null) return '–';
    try {
      if (ctx && typeof ctx.preis === 'function') return ctx.preis(number);
    } catch (e) {
      // Fallback auf die lokale Formatierung.
    }
    return formatZahl(ctx, number, 2) + ' CHF';
  }

  function branchName(branch) {
    var namen = {
      hersteller: 'Hersteller',
      grosshaendler: 'Grosshändler',
      verteiler: 'Verteiler',
      detailhaendler: 'Detailhändler',
      gastro: 'Gastro',
      bank: 'Bank',
      courier: 'Lastwagenhandel'
    };
    return Object.prototype.hasOwnProperty.call(namen, branch) ? namen[branch] : String(branch || '');
  }

  function labelsTag(day) {
    if (typeof day === 'string') return day;
    var number = finite(day);
    if (number === null) return String(day);
    return 'Jahr ' + (Math.floor(number / 365) + 1) + ', Tag ' + (number % 365 + 1);
  }

  function changeOf(points) {
    var values = points.map(function (point) {
      var price = finite(point && point.price);
      return price !== null && price > 0 ? price : null;
    }).filter(function (price) {
      return price !== null;
    });
    if (!values.length) return null;
    return { first: values[0], last: values[values.length - 1], change: values[0] > 0 ? (values[values.length - 1] / values[0] - 1) * 100 : null,
      high: Math.max.apply(null, values), low: Math.min.apply(null, values) };
  }

  function render(elm, ctx) {
    return (async function () {
      var data = null;
      try {
        data = await ctx.ansicht('stocks_all');
      } catch (e) {
        data = null;
      }

      var wrapper = el('div', 'rd-reiter');
      var block = el('div', 'rd-block');
      block.appendChild(el('h3', '', 'Kurse aller Firmen'));
      wrapper.appendChild(block);

      var firms = array(data && data.firms).filter(function (firm) {
        return firm && firm.id !== undefined && firm.id !== null;
      });

      if (!data || !firms.length) {
        block.appendChild(el('p', 'rd-leise', 'Die Kursübersicht aller Firmen ist noch nicht verfügbar.'));
      } else {
        var sortedFirms = firms.slice().sort(function (a, b) {
          return String(a.name || '').localeCompare(String(b.name || ''), 'de');
        });
        var firmById = new Map();
        var colorsById = new Map();
        sortedFirms.forEach(function (firm, index) {
          var id = String(firm.id);
          firmById.set(id, firm);
          colorsById.set(id, palette[index % palette.length]);
        });

        var seriesData = data.series && typeof data.series === 'object' ? data.series : {};
        var allDays = [];
        Object.keys(seriesData).forEach(function (id) {
          array(seriesData[id]).forEach(function (point) {
            if (point && point.day !== undefined && point.day !== null) allDays.push(point.day);
          });
        });
        var dayMap = new Map();
        allDays.forEach(function (day) {
          var key = String(day);
          if (!dayMap.has(key)) dayMap.set(key, day);
        });
        var days = Array.from(dayMap.values()).sort(function (a, b) {
          var left = finite(a);
          var right = finite(b);
          if (left !== null && right !== null) return left - right;
          return String(a).localeCompare(String(b), 'de');
        });

        var statsById = new Map();
        sortedFirms.forEach(function (firm) {
          statsById.set(String(firm.id), changeOf(array(seriesData[String(firm.id)])));
        });

        if (auswahl === null) {
          auswahl = [];
          var ownId = ctx && ctx.state && ctx.state.firm && ctx.state.firm.id !== undefined
            ? String(ctx.state.firm.id) : null;
          if (ownId !== null && firmById.has(ownId)) auswahl.push(ownId);
          var top = sortedFirms.filter(function (firm) {
            return !!firm.listed && String(firm.id) !== ownId;
          }).map(function (firm) {
            var stats = statsById.get(String(firm.id));
            return { id: String(firm.id), last: stats ? stats.last : null };
          }).filter(function (item) {
            return item.last !== null && Number.isFinite(item.last);
          }).sort(function (a, b) {
            return b.last - a.last;
          }).slice(0, 3);
          top.forEach(function (item) {
            if (auswahl.indexOf(item.id) < 0) auswahl.push(item.id);
          });
        } else {
          auswahl = auswahl.filter(function (id) { return firmById.has(String(id)); }).map(String);
        }

        var layout = el('div', 'rb-layout');
        var side = el('div', 'rb-seite');
        var main = el('div', 'rb-haupt');
        layout.appendChild(side);
        layout.appendChild(main);
        block.appendChild(layout);

        var filters = el('div', 'rb-filter');
        var search = el('input');
        search.type = 'search';
        search.placeholder = 'Name suchen …';
        search.setAttribute('aria-label', 'Name suchen');
        search.autocomplete = 'off';
        filters.appendChild(search);

        var branches = Array.from(new Set(firms.map(function (firm) {
          return String(firm.branch || '');
        }).filter(Boolean))).sort(function (a, b) {
          return branchName(a).localeCompare(branchName(b), 'de');
        });
        var branchSelect = el('select');
        branchSelect.setAttribute('aria-label', 'Branche');
        var allBranches = el('option', '', 'Alle Branchen');
        allBranches.value = '';
        branchSelect.appendChild(allBranches);
        branches.forEach(function (branch) {
          var option = el('option', '', branchName(branch));
          option.value = branch;
          branchSelect.appendChild(option);
        });
        filters.appendChild(branchSelect);
        side.appendChild(filters);

        var actions = el('div', 'rb-aktionen');
        var selectVisible = el('button', '', 'Alle sichtbaren wählen');
        selectVisible.type = 'button';
        var clearSelection = el('button', '', 'Keine');
        clearSelection.type = 'button';
        actions.appendChild(selectVisible);
        actions.appendChild(clearSelection);
        side.appendChild(actions);

        var list = el('div', 'rb-liste');
        list.setAttribute('role', 'group');
        list.setAttribute('aria-label', 'Firmen auswählen');
        side.appendChild(list);

        var options = el('div', 'rb-optionen');
        var normLabel = el('label');
        var norm = el('input');
        norm.type = 'checkbox';
        norm.checked = startBeiHundert;
        normLabel.appendChild(norm);
        normLabel.appendChild(document.createTextNode(' Start = 100'));
        options.appendChild(normLabel);
        main.appendChild(options);
        main.appendChild(el('p', 'rb-hinweis', 'Die Linien zeigen den Kursverlauf aller ausgewählten Firmen. Lücken entstehen vor dem Börsengang und wenn kein Kurs vorliegt.'));
        var chartBox = el('div', 'rb-chart');
        chartBox.setAttribute('aria-live', 'polite');
        main.appendChild(chartBox);
        var statsBox = el('div', 'rb-zahlen');

        function isVisible(firm) {
          var query = search.value.trim().toLocaleLowerCase('de');
          var name = String(firm.name || '').toLocaleLowerCase('de');
          return (!query || name.indexOf(query) >= 0) &&
            (!branchSelect.value || String(firm.branch || '') === branchSelect.value);
        }

        function drawList() {
          list.replaceChildren();
          sortedFirms.forEach(function (firm) {
            if (!isVisible(firm)) return;
            var id = String(firm.id);
            var row = el('div', 'rb-zeile' + (firm.listed ? '' : ' rb-nicht-kotiert'));
            var checkbox = el('input');
            checkbox.type = 'checkbox';
            checkbox.checked = auswahl.indexOf(id) >= 0;
            checkbox.setAttribute('aria-label', String(firm.name || 'Firma'));
            checkbox.addEventListener('change', function () {
              if (checkbox.checked) {
                if (auswahl.indexOf(id) < 0) auswahl.push(id);
              } else {
                auswahl = auswahl.filter(function (item) { return item !== id; });
              }
              drawChart();
            });
            row.appendChild(checkbox);

            var dot = el('span', 'rb-punkt');
            dot.style.backgroundColor = colorsById.get(id);
            row.appendChild(dot);

            var label = el('label');
            var name = el('span', 'rb-firmenname', String(firm.name || '–') + (firm.listed ? '' : ' (nicht börsennotiert)'));
            label.appendChild(name);
            var stats = statsById.get(id);
            var kursText = stats
              ? formatPreis(ctx, stats.last) + ' · ' + (stats.change === null ? '–' :
                (stats.change >= 0 ? '+' : '') + formatZahl(ctx, stats.change, 1) + ' %')
              : '–';
            var kursClass = stats && stats.change !== null
              ? (stats.change >= 0 ? 'rd-positiv' : 'rd-negativ') : 'rd-leise';
            label.appendChild(el('span', 'rb-kurs ' + kursClass, kursText));
            row.appendChild(label);
            list.appendChild(row);
          });
          if (!list.childNodes.length) list.appendChild(el('p', 'rd-leise', 'Keine Treffer.'));
        }

        function drawChart() {
          chartBox.replaceChildren();
          statsBox.replaceChildren();
          var chosen = auswahl.filter(function (id) { return firmById.has(String(id)); });
          if (!chosen.length) {
            chartBox.appendChild(el('p', 'rb-keine', 'Wähle links Firmen aus.'));
            main.appendChild(statsBox);
            return;
          }

          var axisDays = days;
          if (axisDays.length > 400) {
            var indices = [];
            for (var i = 0; i < 399; i += 1) {
              indices.push(Math.round(i * (axisDays.length - 1) / 399));
            }
            indices.push(axisDays.length - 1);
            axisDays = indices.filter(function (index, indexAt) {
              return indexAt === 0 || index !== indices[indexAt - 1];
            }).map(function (index) {
              return days[index];
            });
          }

          var labels = axisDays.map(labelsTag);
          var chartSeries = chosen.map(function (id) {
            var firm = firmById.get(String(id));
            var rawPoints = array(seriesData[String(id)]);
            var valuesByDay = new Map();
            rawPoints.forEach(function (point) {
              if (!point || point.day === undefined || point.day === null) return;
              var price = finite(point.price);
              valuesByDay.set(String(point.day), price !== null && price > 0 ? price : null);
            });
            var values = axisDays.map(function (day) {
              return valuesByDay.get(String(day)) === undefined ? null : valuesByDay.get(String(day));
            });
            if (startBeiHundert) {
              var first = null;
              array(seriesData[String(id)]).some(function (point) {
                var price = finite(point && point.price);
                if (price !== null && price > 0) {
                  first = price;
                  return true;
                }
                return false;
              });
              values = values.map(function (value) {
                return value !== null && first !== null && first > 0 ? value / first * 100 : null;
              });
            }
            return {
              name: String(firm.name || 'Firma'),
              werte: values,
              farbe: colorsById.get(String(id))
            };
          });

          var chart = null;
          if (typeof ctx.linien === 'function') {
            try {
              chart = ctx.linien(chartSeries, {
                labels: labels,
                hoehe: 460,
                format: startBeiHundert ? 'zahl' : 'preis'
              });
            } catch (e) {
              chart = null;
            }
          }
          if (chart) chartBox.appendChild(chart);
          else chartBox.appendChild(el('p', 'rb-keine', 'Das Diagramm ist nicht verfügbar.'));

          var table = el('table', 'rd-tabelle');
          var head = el('thead');
          var heading = el('tr');
          ['Firma', 'Letzter Kurs', 'Veränderung', 'Hoch', 'Tief'].forEach(function (title) {
            heading.appendChild(el('th', '', title));
          });
          head.appendChild(heading);
          table.appendChild(head);
          var body = el('tbody');
          chosen.forEach(function (id) {
            var firm = firmById.get(String(id));
            var stats = statsById.get(String(id));
            var row = el('tr');
            row.appendChild(el('td', '', String(firm.name || '–')));
            row.appendChild(el('td', '', stats ? formatPreis(ctx, stats.last) : '–'));
            var change = stats && stats.change !== null ? (stats.change >= 0 ? '+' : '') + formatZahl(ctx, stats.change, 1) + ' %' : '–';
            row.appendChild(el('td', stats && stats.change !== null ? (stats.change >= 0 ? 'rd-positiv' : 'rd-negativ') : '', change));
            row.appendChild(el('td', '', stats ? formatPreis(ctx, stats.high) : '–'));
            row.appendChild(el('td', '', stats ? formatPreis(ctx, stats.low) : '–'));
            body.appendChild(row);
          });
          table.appendChild(body);
          statsBox.appendChild(table);
          main.appendChild(statsBox);
        }

        search.addEventListener('input', drawList);
        branchSelect.addEventListener('change', drawList);
        selectVisible.addEventListener('click', function () {
          sortedFirms.forEach(function (firm) {
            var id = String(firm.id);
            if (isVisible(firm) && auswahl.indexOf(id) < 0) auswahl.push(id);
          });
          drawList();
          drawChart();
        });
        clearSelection.addEventListener('click', function () {
          auswahl = [];
          drawList();
          drawChart();
        });
        norm.addEventListener('change', function () {
          startBeiHundert = norm.checked;
          drawChart();
        });

        drawList();
        drawChart();
      }

      var rest = document.createElement('div');
      wrapper.appendChild(rest);
      elm.replaceChildren(wrapper);
      if (alt && alt.render) {
        try {
          await alt.render(rest, ctx);
        } catch (e) {
          // Der bisherige Börseninhalt ist optional.
        }
      }
    }());
  }

  REITER.boerse = { async render(elm, ctx) { return render(elm, ctx); } };
}());
