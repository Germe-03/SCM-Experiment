(function () {
    'use strict';

    var researchLocalChoice;
    var researchHasLocalChoice = false;

    function h(tag, attrs, children) {
        var el = document.createElement(tag);
        attrs = attrs || {};

        Object.keys(attrs).forEach(function (key) {
            var value = attrs[key];
            if (key === 'on' && value && typeof value === 'object') {
                Object.keys(value).forEach(function (eventName) {
                    el.addEventListener(eventName, value[eventName]);
                });
            } else if (key.slice(0, 2) === 'on' && typeof value === 'function') {
                el.addEventListener(key.slice(2).toLowerCase(), value);
            } else if (key === 'className') {
                el.className = value;
            } else if (key === 'text') {
                el.textContent = value == null ? '' : String(value);
            } else if (key === 'checked' || key === 'disabled' || key === 'hidden') {
                el[key] = Boolean(value);
            } else if (key === 'value') {
                el.value = value == null ? '' : String(value);
            } else if (value != null) {
                el.setAttribute(key, String(value));
            }
        });

        function addChild(child) {
            if (child == null || child === false) {
                return;
            }
            if (Array.isArray(child)) {
                child.forEach(addChild);
            } else if (typeof child === 'string' || typeof child === 'number') {
                var span = document.createElement('span');
                span.textContent = String(child);
                el.appendChild(span);
            } else {
                el.appendChild(child);
            }
        }

        addChild(children);
        return el;
    }

    function ensureStyle() {
        if (document.getElementById('reiter-spezial-stil')) {
            return;
        }
        var style = document.createElement('style');
        style.id = 'reiter-spezial-stil';
        style.textContent = [
            '.rs-abschnitt{margin:0 0 1.25rem}',
            '.rs-kopf{margin-bottom:.75rem}',
            '.rs-kopf h2,.rs-kopf h3{margin:.2rem 0 .5rem}',
            '.rs-text-leise{color:var(--text-leise)}',
            '.rs-zeile{display:flex;align-items:center;flex-wrap:wrap;gap:.6rem;margin:.5rem 0}',
            '.rs-knopf{border:1px solid var(--rand);border-radius:.35rem;background:var(--flaeche);color:var(--akzent);padding:.45rem .75rem;cursor:pointer}',
            '.rs-knopf:disabled{opacity:.55;cursor:not-allowed}',
            '.rs-knopf:focus,.rs-eingabe:focus,.rs-schieber:focus{outline:2px solid var(--akzent);outline-offset:2px}',
            '.rs-banner,.rs-box{border:1px solid var(--rand);border-radius:.4rem;background:var(--flaeche);padding:.75rem;margin:.7rem 0}',
            '.rs-banner{border-left:4px solid var(--warnung)}',
            '.rs-warnung{border:2px solid var(--negativ);border-left-width:6px;border-radius:.4rem;padding:.85rem;background:var(--flaeche);margin:.6rem 0 1rem}',
            '.rs-legende{display:flex;gap:.45rem 1rem;flex-wrap:wrap;margin:.8rem 0}',
            '.rs-legende-eintrag{display:flex;align-items:center;gap:.35rem}',
            '.rs-punkt{display:inline-block;width:.8rem;height:.8rem;border:1px solid var(--rand);border-radius:50%}',
            '.rs-baum-scroll{overflow-x:auto;border:1px solid var(--rand);border-radius:.4rem;background:var(--flaeche);padding:.5rem}',
            '.rs-baum{display:block;max-width:none}',
            '.rs-baum-linie{fill:none;stroke:var(--rand);stroke-width:2}',
            '.rs-knoten{cursor:pointer}',
            '.rs-knoten rect{stroke-width:2;fill:var(--flaeche)}',
            '.rs-knoten text{fill:var(--akzent);font-size:13px;pointer-events:none}',
            '.rs-knoten.rs-implemented rect{fill:var(--positiv);stroke:var(--positiv)}',
            '.rs-knoten.rs-researched rect{fill:var(--akzent);stroke:var(--akzent)}',
            '.rs-knoten.rs-running rect{fill:var(--warnung);stroke:var(--warnung)}',
            '.rs-knoten.rs-available rect{fill:var(--flaeche);stroke:var(--akzent)}',
            '.rs-knoten.rs-locked rect{fill:var(--flaeche);stroke:var(--text-leise);opacity:.55}',
            '.rs-knoten.rs-implemented text,.rs-knoten.rs-researched text,.rs-knoten.rs-running text{fill:var(--flaeche)}',
            '.rs-knoten.rs-ausgewaehlt rect{stroke:var(--akzent);stroke-width:5}',
            '.rs-detail dl{display:grid;grid-template-columns:minmax(7rem,auto) 1fr;gap:.35rem .8rem;margin:.5rem 0}',
            '.rs-detail dt{font-weight:600}',
            '.rs-detail dd{margin:0}',
            '.rs-karte{border:1px solid var(--rand);border-radius:.4rem;background:var(--flaeche);padding:.8rem;margin:.7rem 0}',
            '.rs-karte h3{margin:.1rem 0 .6rem}',
            '.rs-schieber{width:min(100%,25rem);accent-color:var(--akzent)}',
            '.rs-eingabe{border:1px solid var(--rand);border-radius:.3rem;background:var(--flaeche);color:var(--akzent);padding:.45rem}',
            '.rs-overlay{position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;padding:1rem;background:var(--flaeche)}',
            '.rs-dialog{width:min(100%,38rem);max-height:90vh;overflow:auto;border:2px solid var(--rand);border-radius:.5rem;background:var(--flaeche);padding:1rem}',
            '.rs-dialog-zeile{border-top:1px solid var(--rand);padding:.65rem 0}',
            '.rs-glossar-liste{padding-left:1.3rem}',
            '.rs-glossar-liste li{margin:.65rem 0}',
            '.rs-hilfe h3{margin:.9rem 0 .25rem}',
            '.rs-hilfe p{margin:.25rem 0 .65rem}'
        ].join('');
        document.head.appendChild(style);
    }

    function clear(el) {
        while (el.firstChild) {
            el.removeChild(el.firstChild);
        }
    }

    function safeText(value) {
        if (value == null) {
            return '';
        }
        if (typeof value === 'string' || typeof value === 'number') {
            return String(value);
        }
        try {
            return JSON.stringify(value);
        } catch (error) {
            return String(value);
        }
    }

    function formatGeld(ctx, amount) {
        if (ctx && typeof ctx.geld === 'function') {
            try {
                return ctx.geld(amount);
            } catch (error) {
                // Nutze unten eine einfache Ausgabe.
            }
        }
        return safeText(amount) + ' CHF';
    }

    function statusText(status) {
        var map = {
            implemented: 'Umgesetzt',
            researched: 'Erforscht',
            running: 'Läuft',
            available: 'Möglich',
            locked: 'Gesperrt'
        };
        return map[status] || 'Unbekannt';
    }

    function svgElement(tag, attrs) {
        var el = document.createElementNS('http://www.w3.org/2000/svg', tag);
        Object.keys(attrs || {}).forEach(function (key) {
            el.setAttribute(key, String(attrs[key]));
        });
        return el;
    }

    function addSvgText(parent, text, x, y) {
        var label = svgElement('text', { x: x, y: y });
        label.textContent = text;
        parent.appendChild(label);
        return label;
    }

    function normalizeStages(data) {
        if (Array.isArray(data && data.stages)) {
            return data.stages;
        }
        if (Array.isArray(data && data.tree)) {
            return data.tree;
        }
        if (data && data.tree && Array.isArray(data.tree.stages)) {
            return data.tree.stages;
        }
        return [];
    }

    function setResearchChoice(ctx, choice, note, refreshChoice) {
        if (refreshChoice) {
            researchLocalChoice = choice;
            researchHasLocalChoice = true;
        }
        try {
            if (ctx && typeof ctx.entscheide === 'function') {
                ctx.entscheide({ research_target: choice });
            }
            if (note) {
                note.textContent = 'Gespeichert für die nächste Runde';
            }
        } catch (error) {
            if (note) {
                note.textContent = 'Die Wahl konnte nicht gespeichert werden. Bitte versuche es erneut.';
            }
        }
    }

    async function renderForschung(el, ctx) {
        clear(el);
        var root = h('div', { className: 'rs-abschnitt' });
        el.appendChild(root);

        root.appendChild(h('div', { className: 'rs-kopf' }, [
            h('h2', {}, 'Forschung'),
            h('p', { className: 'rs-text-leise' }, 'Forschung schaltet neue Möglichkeiten und Verbesserungen frei. Forschung kostet über den Baum.')
        ]));

        var choiceLine = h('div', { className: 'rs-zeile' });
        var choiceLabel = h('span', {});
        var note = h('span', { className: 'rs-text-leise', 'aria-live': 'polite' });
        choiceLine.appendChild(h('button', {
            className: 'rs-knopf',
            type: 'button',
            onClick: function () {
                setResearchChoice(ctx, '', note, true);
                updateChoiceLabel();
                updateHighlights();
            }
        }, 'Keine Forschung'));
        choiceLine.appendChild(h('button', {
            className: 'rs-knopf',
            type: 'button',
            onClick: function () {
                setResearchChoice(ctx, null, note, true);
                updateChoiceLabel();
                updateHighlights();
            }
        }, 'Autopilot'));
        choiceLine.appendChild(choiceLabel);
        choiceLine.appendChild(note);
        root.appendChild(choiceLine);

        var autopilotText = h('p', { className: 'rs-text-leise' }, 'Autopilot-Angabe nicht verfügbar.');
        root.appendChild(autopilotText);

        var runningBanner = h('div', { className: 'rs-banner', hidden: true });
        root.appendChild(runningBanner);

        var legend = h('div', { className: 'rs-legende', 'aria-label': 'Status-Legende' });
        var legendItems = [
            ['implemented', 'Umgesetzt', 'var(--positiv)'],
            ['researched', 'Erforscht', 'var(--akzent)'],
            ['running', 'Läuft', 'var(--warnung)'],
            ['available', 'Möglich', 'var(--flaeche)'],
            ['locked', 'Gesperrt', 'var(--text-leise)']
        ];
        legendItems.forEach(function (item) {
            var dot = h('span', { className: 'rs-punkt' });
            dot.style.backgroundColor = item[2];
            if (item[0] === 'available') {
                dot.style.borderColor = 'var(--akzent)';
            }
            legend.appendChild(h('span', { className: 'rs-legende-eintrag' }, [dot, item[1]]));
        });
        root.appendChild(legend);

        var graphContainer = h('div', { className: 'rs-baum-scroll', 'aria-label': 'Forschungsbaum' });
        root.appendChild(graphContainer);
        var detail = h('div', { className: 'rs-box rs-detail', hidden: true });
        root.appendChild(detail);

        var data;
        try {
            if (!ctx || typeof ctx.ansicht !== 'function') {
                throw new Error('Ansicht nicht verfügbar');
            }
            data = await ctx.ansicht('research_tree');
        } catch (error) {
            root.appendChild(h('p', { className: 'rs-text-leise' }, 'Der Forschungsbaum konnte gerade nicht geladen werden. Bitte versuche es später erneut.'));
            return;
        }

        var stages = normalizeStages(data);
        if (!stages.length) {
            root.appendChild(h('p', { className: 'rs-text-leise' }, 'Zurzeit sind keine Forschungsstufen verfügbar.'));
            return;
        }

        var byName = {};
        stages.forEach(function (stage) {
            if (stage && stage.name != null) {
                byName[String(stage.name)] = stage;
            }
        });

        var autoData = null;
        try {
            autoData = await ctx.ansicht('autopilot');
        } catch (error) {
            autoData = null;
        }
        var autoResearch = autoData && autoData.research_target;
        if (autoResearch && typeof autoResearch === 'object') {
            var autoParts = [];
            if (autoResearch.text) {
                autoParts.push(safeText(autoResearch.text));
            }
            if (Object.prototype.hasOwnProperty.call(autoResearch, 'value')) {
                autoParts.push('Aktuell: ' + (autoResearch.value == null ? 'keine feste Wahl' : safeText(autoResearch.value)));
            }
            autopilotText.textContent = autoParts.join(' ');
        }

        if (data.running && data.running.stage != null) {
            var runningStage = byName[String(data.running.stage)];
            var runningLabel = runningStage ? (runningStage.label || runningStage.name) : data.running.stage;
            runningBanner.textContent = 'Läuft: ' + safeText(runningLabel) + ', noch ' + safeText(data.running.days_left) + ' Tage';
            runningBanner.hidden = false;
        }

        var choice = ctx && ctx.state && ctx.state.choices ? ctx.state.choices.research_target : undefined;
        if (!researchHasLocalChoice) {
            researchLocalChoice = choice;
        }

        var columnMap = {};
        stages.forEach(function (stage) {
            var depth = Number(stage.depth);
            if (!Number.isFinite(depth) || depth < 0) {
                depth = 0;
            }
            depth = Math.floor(depth);
            columnMap[depth] = columnMap[depth] || [];
            columnMap[depth].push(stage);
        });
        var depths = Object.keys(columnMap).map(Number).sort(function (a, b) { return a - b; });
        var positions = {};
        depths.forEach(function (depth) {
            columnMap[depth].forEach(function (stage, index) {
                positions[String(stage.name)] = {
                    x: 24 + depth * 250,
                    y: 28 + index * 104
                };
            });
        });

        var maxCount = depths.reduce(function (max, depth) {
            return Math.max(max, columnMap[depth].length);
        }, 1);
        var svg = svgElement('svg', {
            class: 'rs-baum',
            width: Math.max(240, 24 + ((depths[depths.length - 1] || 0) * 250) + 220),
            height: Math.max(150, 28 + maxCount * 104),
            role: 'img',
            'aria-label': 'Forschungsbaum mit Voraussetzungen und Forschungsstufen'
        });

        stages.forEach(function (stage) {
            var requires = Array.isArray(stage.requires) ? stage.requires : [];
            var target = positions[String(stage.name)];
            requires.forEach(function (requiredName) {
                var source = positions[String(requiredName)];
                if (!source || !target) {
                    return;
                }
                var x1 = source.x + 190;
                var y1 = source.y + 34;
                var x2 = target.x;
                var y2 = target.y + 34;
                var middle = (x1 + x2) / 2;
                svg.appendChild(svgElement('path', {
                    class: 'rs-baum-linie',
                    d: 'M ' + x1 + ' ' + y1 + ' C ' + middle + ' ' + y1 + ', ' + middle + ' ' + y2 + ', ' + x2 + ' ' + y2
                }));
            });
        });

        function updateChoiceLabel() {
            var current = researchHasLocalChoice ? researchLocalChoice : choice;
            var text;
            if (current === null || typeof current === 'undefined') {
                text = 'Wahl: Autopilot';
            } else if (current === '') {
                text = 'Wahl: Keine Forschung';
            } else {
                var selectedStage = byName[String(current)];
                text = 'Wahl: ' + safeText(selectedStage ? (selectedStage.label || selectedStage.name) : current);
            }
            choiceLabel.textContent = text;
        }

        function updateHighlights() {
            var current = researchHasLocalChoice ? researchLocalChoice : choice;
            Array.prototype.forEach.call(svg.querySelectorAll('.rs-knoten'), function (node) {
                if (node.getAttribute('data-name') === String(current)) {
                    node.classList.add('rs-ausgewaehlt');
                } else {
                    node.classList.remove('rs-ausgewaehlt');
                }
            });
        }

        function showDetail(stage) {
            clear(detail);
            detail.hidden = false;
            var label = stage.label || stage.name;
            detail.appendChild(h('h3', {}, safeText(label)));
            var required = Array.isArray(stage.requires) ? stage.requires : [];
            var requiredLabels = required.map(function (name) {
                var found = byName[String(name)];
                return safeText(found ? (found.label || found.name) : name);
            });
            var rows = [
                ['Art', safeText(stage.kind || 'Nicht angegeben')],
                ['Kosten', formatGeld(ctx, stage.cost)],
                ['Dauer', safeText(stage.duration_days == null ? 'Nicht angegeben' : stage.duration_days) + ' Tage'],
                ['Wirkung', safeText(stage.effect || 'Nicht angegeben')],
                ['Patentierbar', stage.patentable ? 'Ja' : 'Nein'],
                ['Voraussetzungen', requiredLabels.length ? requiredLabels.join(', ') : 'Keine'],
                ['Status', statusText(stage.status)]
            ];
            var dl = document.createElement('dl');
            rows.forEach(function (row) {
                dl.appendChild(h('dt', {}, row[0]));
                dl.appendChild(h('dd', {}, row[1]));
            });
            detail.appendChild(dl);
            if (stage.status === 'available') {
                detail.appendChild(h('button', {
                    className: 'rs-knopf',
                    type: 'button',
                    onClick: function () {
                        setResearchChoice(ctx, stage.name, note, true);
                        updateChoiceLabel();
                        updateHighlights();
                    }
                }, 'Als nächstes erforschen'));
            }
        }

        stages.forEach(function (stage) {
            var position = positions[String(stage.name)];
            if (!position) {
                return;
            }
            var node = svgElement('g', {
                class: 'rs-knoten rs-' + (stage.status || 'locked'),
                'data-name': stage.name,
                role: 'button',
                tabindex: '0',
                'aria-label': safeText(stage.label || stage.name) + ', ' + statusText(stage.status)
            });
            node.appendChild(svgElement('rect', {
                x: position.x,
                y: position.y,
                width: 190,
                height: 68,
                rx: 7
            }));
            var text = safeText(stage.label || stage.name);
            if (text.length > 25) {
                text = text.slice(0, 22) + '...';
            }
            addSvgText(node, text, position.x + 9, position.y + 29);
            node.addEventListener('click', function () {
                showDetail(stage);
            });
            node.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    showDetail(stage);
                }
            });
            svg.appendChild(node);
        });

        graphContainer.appendChild(svg);
        updateChoiceLabel();
        updateHighlights();
    }

    function offenceExplanation(name) {
        var lower = safeText(name).toLocaleLowerCase('de');
        if (lower.indexOf('lohn') !== -1) {
            return 'Lohndumping: Die Firma zahlt weniger Lohn als üblich und spart Kosten. Geschädigt sind die Angestellten und ehrliche Konkurrenten.';
        }
        if (lower.indexOf('pfusch') !== -1 || lower.indexOf('material') !== -1) {
            return 'Pfusch beim Material: Die Firma nutzt billigeres oder schlechteres Material und senkt so die Kosten. Geschädigt sind die Kundschaft (Sicherheit und Qualität) und ehrliche Konkurrenz.';
        }
        if (lower.indexOf('steuer') !== -1) {
            return 'Steuerhinterziehung: Der Gewinn wird zu tief gemeldet. Geschädigt sind alle, die Steuern zahlen, und die Allgemeinheit.';
        }
        return 'Dieser Verstoss kann Kosten senken, schadet aber anderen und kann schwere Folgen haben.';
    }

    function normalizeOffences(value) {
        if (!Array.isArray(value)) {
            return [];
        }
        return value.filter(function (item) {
            return item && item.name != null;
        });
    }

    function getStoredIntensities(state, offences) {
        var choices = state && state.choices ? state.choices.offences : undefined;
        if (choices == null && state) {
            choices = state.offences;
        }
        var result = {};
        offences.forEach(function (offence) {
            result[String(offence.name)] = 0;
        });
        if (Array.isArray(choices)) {
            choices.forEach(function (name) {
                result[String(name)] = 1;
            });
        } else if (choices && typeof choices === 'object') {
            Object.keys(choices).forEach(function (name) {
                var number = Number(choices[name]);
                result[name] = Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : 0;
            });
        }
        return result;
    }

    function sameIntensities(a, b, names) {
        return names.every(function (name) {
            return Math.abs((Number(a[name]) || 0) - (Number(b[name]) || 0)) < 0.0001;
        });
    }

    function renderHistory(root, state) {
        root.appendChild(h('h3', {}, 'Verlauf'));
        var messages = state && Array.isArray(state.messages) ? state.messages : [];
        var relevant = messages.map(function (message) {
            if (typeof message === 'string') {
                return message;
            }
            if (!message || typeof message !== 'object') {
                return '';
            }
            return safeText(message.text || message.message || message.title || '');
        }).filter(function (text) {
            return /entdeckt|busse/i.test(text);
        });
        if (!relevant.length) {
            root.appendChild(h('p', { className: 'rs-text-leise' }, 'Noch nichts passiert.'));
            return;
        }
        var list = h('ul', {});
        relevant.forEach(function (text) {
            list.appendChild(h('li', {}, text));
        });
        root.appendChild(list);
    }

    function showOffenceDialog(ctx, offences, local, stored, updateSavedLabel) {
        var names = offences.map(function (offence) { return String(offence.name); });
        var changed = names.filter(function (name) {
            return Math.abs((Number(local[name]) || 0) - (Number(stored[name]) || 0)) >= 0.0001;
        });
        if (!changed.length) {
            return;
        }

        var overlay = h('div', { className: 'rs-overlay', role: 'presentation' });
        var dialog = h('div', { className: 'rs-dialog', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'rs-dialog-titel' });
        overlay.appendChild(dialog);
        dialog.appendChild(h('h2', { id: 'rs-dialog-titel' }, 'Änderungen bestätigen'));
        dialog.appendChild(h('p', {}, 'Tippe für jeden geänderten Verstoss seinen Namen genau ein. Erst dann kannst du bestätigen.'));
        var inputs = {};
        changed.forEach(function (name) {
            var input = h('input', {
                className: 'rs-eingabe',
                type: 'text',
                autocomplete: 'off',
                'aria-label': 'Name bestätigen: ' + name
            });
            inputs[name] = input;
            dialog.appendChild(h('div', { className: 'rs-dialog-zeile' }, [
                h('label', {}, [h('strong', {}, name), h('p', {}, 'Name des Verstosses eintippen')]),
                input
            ]));
        });

        var buttons = h('div', { className: 'rs-zeile' });
        var confirm = h('button', { className: 'rs-knopf', type: 'button', disabled: true }, 'Bestätigen');
        var cancel = h('button', { className: 'rs-knopf', type: 'button' }, 'Abbrechen');
        buttons.appendChild(confirm);
        buttons.appendChild(cancel);
        dialog.appendChild(buttons);

        function isValid() {
            return changed.every(function (name) {
                return inputs[name].value.trim().toLocaleLowerCase('de') === name.trim().toLocaleLowerCase('de');
            });
        }
        function updateConfirm() {
            confirm.disabled = !isValid();
        }
        changed.forEach(function (name) {
            inputs[name].addEventListener('input', updateConfirm);
        });
        cancel.addEventListener('click', function () {
            if (overlay.parentNode) {
                overlay.parentNode.removeChild(overlay);
            }
        });
        confirm.addEventListener('click', function () {
            if (!isValid()) {
                return;
            }
            var patch = {};
            names.forEach(function (name) {
                patch[name] = Math.max(0, Math.min(1, Number(local[name]) || 0));
            });
            try {
                if (ctx && typeof ctx.entscheide === 'function') {
                    ctx.entscheide({ offences: patch });
                    names.forEach(function (name) {
                        stored[name] = patch[name];
                    });
                    updateSavedLabel('Änderung übernommen.');
                    if (overlay.parentNode) {
                        overlay.parentNode.removeChild(overlay);
                    }
                } else {
                    updateSavedLabel('Die Änderung konnte nicht gespeichert werden.');
                }
            } catch (error) {
                updateSavedLabel('Die Änderung konnte nicht gespeichert werden. Bitte versuche es erneut.');
            }
        });

        document.body.appendChild(overlay);
        if (changed.length) {
            inputs[changed[0]].focus();
        }
    }

    async function renderGraubereich(el, ctx) {
        clear(el);
        var root = h('div', { className: 'rs-abschnitt' });
        el.appendChild(root);
        root.appendChild(h('div', { className: 'rs-kopf' }, [
            h('h2', {}, 'Graubereich'),
            h('p', {}, 'Regeln zu brechen ist eine bewusste Entscheidung.')
        ]));
        root.appendChild(h('div', { className: 'rs-warnung', role: 'alert' },
            'Im echten Leben sind diese Handlungen strafbar und schaden anderen Menschen. Hier sind sie nur ein Gedankenspiel, damit du Risiko und Folgen verstehst.'
        ));

        var offences = [];
        var fetched = false;
        try {
            var response = await fetch('/api/options');
            if (!response.ok) {
                throw new Error('Optionen konnten nicht geladen werden');
            }
            var options = await response.json();
            if (options && Array.isArray(options.offences)) {
                offences = normalizeOffences(options.offences);
                fetched = true;
            }
        } catch (error) {
            // Der Zustand kann die Verstösse ebenfalls enthalten.
        }

        var state = ctx && ctx.state ? ctx.state : {};
        var fallback = state.options && Array.isArray(state.options.offences)
            ? state.options.offences
            : state.offences;
        if (!fetched && Array.isArray(fallback)) {
            offences = normalizeOffences(fallback);
        }
        if (!offences.length) {
            root.appendChild(h('p', { className: 'rs-text-leise' }, 'Keine Verstösse verfügbar'));
            renderHistory(root, state);
            return;
        }

        var stored = getStoredIntensities(state, offences);
        var local = {};
        var names = offences.map(function (offence) { return String(offence.name); });
        names.forEach(function (name) {
            local[name] = stored[name] || 0;
        });
        var cards = h('div', {});
        var savedLabel = h('p', { className: 'rs-text-leise', 'aria-live': 'polite' });
        var applyButton = h('button', { className: 'rs-knopf', type: 'button', disabled: true }, 'Änderung übernehmen');

        function updateApplyState() {
            applyButton.disabled = sameIntensities(local, stored, names);
        }

        offences.forEach(function (offence) {
            var name = String(offence.name);
            var card = h('section', { className: 'rs-karte' });
            card.appendChild(h('h3', {}, name));
            card.appendChild(h('p', {}, offenceExplanation(name)));
            var intensityLabel = h('strong', {});
            var slider = h('input', {
                className: 'rs-schieber',
                type: 'range',
                min: '0',
                max: '100',
                step: '5',
                value: Math.round(local[name] * 100),
                'aria-label': 'Intensität für ' + name
            });
            var advantage = h('p', {});
            var risk = h('p', {});
            var percentNote = h('p', { className: 'rs-text-leise' }, 'Die genaue Wahrscheinlichkeit bleibt geheim.');
            var fine = h('p', {});
            var valueLine = h('div', { className: 'rs-zeile' }, [slider, intensityLabel]);
            card.appendChild(valueLine);
            card.appendChild(advantage);
            card.appendChild(risk);
            card.appendChild(percentNote);
            card.appendChild(fine);

            function updateCard() {
                var intensity = Math.max(0, Math.min(1, Number(slider.value) / 100));
                local[name] = intensity;
                var percent = Math.round(intensity * 100);
                intensityLabel.textContent = percent + ' %';
                var benefit = Number(offence.benefit);
                if (!Number.isFinite(benefit)) {
                    benefit = 0;
                }
                if (benefit <= 1 && benefit >= 0) {
                    advantage.textContent = 'Geschätzter Vorteil pro Jahr: ' + (benefit * intensity * 100).toLocaleString('de-CH', { maximumFractionDigits: 1 }) + ' %';
                } else {
                    advantage.textContent = 'Geschätzter Vorteil pro Jahr: ' + formatGeld(ctx, benefit * intensity);
                }
                var riskText = intensity === 0 ? 'kein Risiko' : (percent < 35 ? 'gering' : (percent < 70 ? 'mittel' : 'hoch'));
                risk.textContent = 'Risiko: ' + riskText;
                fine.textContent = 'Mögliche Folgen: Busse ab ' + formatGeld(ctx, Number(offence.fine) || 0) + ' plus Anteil am Umsatz, Rufschaden und Meldung in der Presse.';
                updateApplyState();
            }
            slider.addEventListener('input', updateCard);
            slider.addEventListener('change', updateCard);
            updateCard();
            cards.appendChild(card);
        });
        root.appendChild(cards);
        root.appendChild(applyButton);
        root.appendChild(savedLabel);
        applyButton.addEventListener('click', function () {
            if (!applyButton.disabled) {
                showOffenceDialog(ctx, offences, local, stored, function (message) {
                    savedLabel.textContent = message;
                    updateApplyState();
                });
            }
        });

        renderHistory(root, state);
    }

    function addHelpSection(parent, title, text) {
        parent.appendChild(h('h3', {}, title));
        parent.appendChild(h('p', {}, text));
    }

    async function renderHilfe(el, ctx) {
        clear(el);
        var root = h('div', { className: 'rs-abschnitt rs-hilfe' });
        el.appendChild(root);
        root.appendChild(h('h2', {}, 'Hilfe'));
        addHelpSection(root, 'Ziel', 'Führe deine Firma erfolgreich: mit Gewinn, gutem Ruf und Marktanteil, ohne pleite zu gehen.');
        addHelpSection(root, 'Runde', 'Jede Runde ist ein Halt in der Simulation. Du stellst Entscheide ein und drückst «Runde beenden». Die Simulation läuft bis zum nächsten Halt. Die Ergebnisse stehen oben im neuen Stand.');
        addHelpSection(root, 'Reiter erklärt', 'Übersicht zeigt den Stand der Firma. Firma erklärt und steuert die eigene Firma. Markt zeigt Kundschaft und Konkurrenz. Forschung zeigt den Forschungsbaum. Logistik behandelt Lieferungen und Kapazität. Finanzen zeigt Geld und Kredite. Börse zeigt Aktien. Rohstoffe zeigt wichtige Einkaufspreise. Bevölkerung zeigt Kundschaft und Regionen. Holding behandelt verbundene Firmen. Graubereich erklärt mögliche Verstösse. Hilfe enthält diese Anleitung und ein Glossar. Rechts stehen Meldungen und Berater. Unten findest du «Runde beenden», «Wie bisher weiter» und «Firma verkaufen».');

        var autoSentence = 'Ist der Autopilot an, entscheidet die Simulation wie für jede andere Firma: Sie wählt Marketingbudget, Forschung, Kredite, Dividende und weitere Entscheide nach den gleichen Regeln wie bei den Computerfirmen. Du kannst jedes Feld einzeln übernehmen. Der Autopilot-Text steht bei jedem Feld.';
        addHelpSection(root, 'Autopilot', autoSentence);

        root.appendChild(h('h3', {}, 'Glossar'));
        var search = h('input', {
            className: 'rs-eingabe',
            type: 'search',
            placeholder: 'Begriff suchen',
            'aria-label': 'Glossar durchsuchen'
        });
        root.appendChild(search);
        var count = h('p', { className: 'rs-text-leise', 'aria-live': 'polite' }, 'Glossar wird geladen.');
        root.appendChild(count);
        var list = h('ul', { className: 'rs-glossar-liste' });
        root.appendChild(list);

        var terms = [];
        try {
            if (!ctx || typeof ctx.ansicht !== 'function') {
                throw new Error('Ansicht nicht verfügbar');
            }
            var glossary = await ctx.ansicht('glossary');
            terms = Array.isArray(glossary && glossary.terms) ? glossary.terms : [];
        } catch (error) {
            count.textContent = 'Das Glossar konnte gerade nicht geladen werden.';
            return;
        }

        terms = terms.filter(function (item) {
            return item && item.term != null;
        }).sort(function (a, b) {
            return safeText(a.term).localeCompare(safeText(b.term), 'de');
        });

        function updateGlossary() {
            var query = search.value.trim().toLocaleLowerCase('de');
            var matches = terms.filter(function (item) {
                return (safeText(item.term) + ' ' + safeText(item.text)).toLocaleLowerCase('de').indexOf(query) !== -1;
            });
            clear(list);
            count.textContent = matches.length + (matches.length === 1 ? ' Treffer' : ' Treffer');
            if (!matches.length) {
                list.appendChild(h('li', { className: 'rs-text-leise' }, 'Nichts gefunden'));
                return;
            }
            matches.forEach(function (item) {
                list.appendChild(h('li', {}, [
                    h('strong', {}, safeText(item.term)),
                    h('span', {}, ': ' + safeText(item.text))
                ]));
            });
        }

        search.addEventListener('input', updateGlossary);
        updateGlossary();
    }

    window.REITER = window.REITER || {};
    window.REITER.forschung = {
        async render(el, ctx) {
            ensureStyle();
            try {
                await renderForschung(el, ctx || {});
            } catch (error) {
                clear(el);
                el.appendChild(h('p', { className: 'rs-text-leise' }, 'Die Forschung konnte gerade nicht angezeigt werden. Bitte versuche es erneut.'));
            }
        }
    };
    window.REITER.graubereich = {
        async render(el, ctx) {
            ensureStyle();
            try {
                await renderGraubereich(el, ctx || {});
            } catch (error) {
                clear(el);
                el.appendChild(h('p', { className: 'rs-text-leise' }, 'Der Graubereich konnte gerade nicht angezeigt werden. Bitte versuche es erneut.'));
            }
        }
    };
    window.REITER.hilfe = {
        async render(el, ctx) {
            ensureStyle();
            try {
                await renderHilfe(el, ctx || {});
            } catch (error) {
                clear(el);
                el.appendChild(h('p', { className: 'rs-text-leise' }, 'Die Hilfe konnte gerade nicht angezeigt werden. Bitte versuche es erneut.'));
            }
        }
    };
}());
