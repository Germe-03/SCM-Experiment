// Spielmodus Phase 5: Berater (Sprachmodell) auf Knopfdruck.
'use strict';

function beraterZeige(daten) {
    const ziel = document.getElementById('berater-antwort');
    if (!ziel) return;
    ziel.replaceChildren();
    if (daten.error) {
        const p = document.createElement('p');
        p.className = 'ergebnis-fehler';
        p.textContent = daten.error;
        ziel.appendChild(p);
        return;
    }
    const tipps = daten.tips || [];
    if (tipps.length) {
        const liste = document.createElement('ul');
        tipps.forEach((tipp) => {
            const li = document.createElement('li');
            li.textContent = tipp;
            liste.appendChild(li);
        });
        ziel.appendChild(liste);
        if (daten.answer) {
            const mehr = document.createElement('details');
            const titel = document.createElement('summary');
            titel.textContent = 'Ganze Antwort';
            const text = document.createElement('p');
            text.style.whiteSpace = 'pre-line';
            text.textContent = daten.answer;
            mehr.append(titel, text);
            ziel.appendChild(mehr);
        }
    } else if (daten.answer) {
        const p = document.createElement('p');
        p.textContent = daten.answer;
        ziel.appendChild(p);
    }
    if (daten.checked === false) {
        const hinweis = document.createElement('p');
        hinweis.className = 'hinweis';
        hinweis.textContent = 'Einzelne Zahlen stehen nicht in den Daten und sind ungeprüft.';
        ziel.appendChild(hinweis);
    }
}

async function beraterFragen() {
    const knopf = document.getElementById('berater-btn');
    const frage = document.getElementById('berater-frage');
    const ziel = document.getElementById('berater-antwort');
    if (!knopf || knopf.disabled) return;
    knopf.disabled = true;
    knopf.textContent = 'Berater denkt nach …';
    if (ziel) ziel.textContent = '';
    try {
        const antwort = await fetch('/api/advice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: frage ? frage.value : '' })
        });
        beraterZeige(await antwort.json());
    } catch (fehler) {
        beraterZeige({ error: 'Der Server ist nicht erreichbar.' });
    } finally {
        knopf.disabled = false;
        knopf.textContent = 'Berater fragen';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const knopf = document.getElementById('berater-btn');
    if (knopf) knopf.addEventListener('click', beraterFragen);
});
