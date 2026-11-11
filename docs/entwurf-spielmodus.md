# Entwurf: Spielmodus «Eigene Firma gründen»

Stand 11.11.2026. Nur Entwurf, kein Code. Umsetzung erst auf Startzeichen.

## Idee in einem Satz

Der Spieler gründet eine neue Firma und baut sie von null auf. Alle anderen Firmen, Banken, Kuriere, Händler und Kunden laufen wie heute automatisch weiter.

## Start

- Der Spieler wählt eine der 5 Branchen der Hauptsimulation: Hersteller, Grosshändler, Verteiler, Detailhändler oder Gastro. Banken, Kuriere, Post, Lastwagenhändler und Ähnliches sind nicht spielbar.
- Er wählt die Kategorie (z.B. Bier, Wein, Softdrinks), die Region und einen Firmennamen.
- Startkapital: genau gleich wie bei einer neuen Firma in der Simulation (gleiche Regel wie beim Eintritt einer neuen Firma in `runner.py`). Kein Vorteil, kein Nachteil.
- Kein Szenario und kein festes Ziel. Gezählt wird am Ende der Firmenwert und die Rangliste gegen die anderen Firmen. Szenarien (Rettung, Rohstoffschock, Übernahmeschlacht usw.) kommen vielleicht später.

## Ablauf einer Runde

1. Die Simulation rechnet einen Monat und hält dann an.
2. Der Spieler sieht sein Cockpit: Kasse, Lager, Absatz, Preise der Konkurrenz, Meldungen seit der letzten Runde.
3. Er ändert Entscheide oder lässt die bisherigen stehen. Es gibt keine Zeitgrenze: Die Simulation wartet, bis der Spieler «Runde beenden» drückt.
4. Mit dem Knopf «Wie bisher weiter» lassen sich ruhige Monate schnell überspringen.

Einzelne Bereiche (z.B. Einkauf) kann der Spieler dem Autopiloten überlassen. Dann entscheidet die heutige Firmenlogik.

## Was der Spieler entscheidet

Grundsatz: Alles, was die Firmenlogik heute selbst entscheidet, darf der Spieler entscheiden. Dazu kommen ein paar neue Dinge, die mit «(neu)» markiert sind; die gibt es in der Simulation noch nicht und sie müssten auch für die anderen Firmen gebaut werden. Jeden Bereich kann man dem Autopiloten überlassen.

### Mitarbeiter

- Anzahl Mitarbeiter je Standort: einstellen und entlassen. Einstellen kostet eine Gebühr, Entlassen eine Abfindung (neu) und schadet dem Ruf.
- Lohnniveau gegenüber dem Durchschnitt der Region. Zu tiefe Löhne: Leute kündigen oder werden abgeworben. Höhere Löhne: weniger Wechsel, besserer Ruf.
- Überstunden: mehr Kapazität für kurze Zeit, aber teurer und mehr Kündigungen.
- Aufteilung nach Bereichen (neu): Produktion, Verkauf, Lager, Fahrer, Verwaltung. Fehlen Fahrer, stehen die eigenen Lastwagen.
- Weiterbildung (neu): Budget pro Mitarbeiter, hebt die Produktivität langsam und senkt die Kündigungen.
- Lohnerhöhung bei Mindestlohn-Gesetz oder knappem Arbeitsmarkt: sofort, später oder gar nicht (dann droht Abwanderung).

### Produkt und Qualität

- Positionierung: günstig, Mittelklasse oder Premium.
- Zielqualität und was man dafür ausgibt.
- Sortiment je Kategorie (z.B. Bier, Wein, Softdrinks, Wasser), soweit die Branche es erlaubt; neue Sorten über den F&E-Baum.
- Marken (neu für den Spieler wählbar): eine Marke für alles oder mehrere Marken für verschiedene Preisstufen.
- Verpackung bei Gesetzen zu Pfand und Verpackung: Mehrweg oder Einweg.

### Preise und Verkauf

- Grundpreis und Preisband (tiefster und höchster Preis), getrennt je Produkt und Region.
- Rabatte für Grosskunden (neu) und Aktionen für kurze Zeit (neu).
- Welche Kunden und Regionen beliefert werden, und ob Rückstände angenommen werden oder nicht.
- Export: ja oder nein und welcher Anteil, abhängig vom Wechselkurs.

### Einkauf und Lieferanten

- Lieferanten wählen, nach Preis, Zuverlässigkeit, Qualität, Ruf, Lieferzeit und Kapazität. Wichtigste Kriterien selbst gewichten.
- Alles bei einem Lieferanten oder auf mehrere verteilen.
- Bestellmenge und Sicherheitsbestand in Tagen.
- Rahmenverträge mit festem Preis über ein Jahr (neu).
- Import statt Inland, wenn günstiger (Zoll und Wechselkurs beachten).
- Nur Hersteller: Rohstoffe nach Zeitpunkt und Menge kaufen, Lager und Verderb; Strom als eigener Kostenpunkt, evtl. Festpreisvertrag (neu).

### Produktion und Lager (je nach Branche)

- Produktionsmenge pro Tag oder Monat, Lagerziel.
- Kapazität ausbauen: wie viel, wann, wo. Der Bau dauert und wird abgeschrieben.
- Neue Standorte in anderen Regionen eröffnen oder schliessen.
- Maschinen modernisieren über F&E-Stufen.

### Transport

- Post, Kurier oder eigene Flotte, je Strecke getrennt.
- Lastwagen kaufen oder leasen, Typ wählen, Occasion oder neu.
- Händler und Servicevertrag wählen (wenn die Händler-Werkstatt aus den Todos gebaut ist).

### Branchen-Eigenheiten

- **Detailhändler:** Ladenfläche und Anzahl Filialen je Region, Sortiment, Anteil der Regalfläche je Kategorie und Marke, Eigenmarke ja oder nein (neu).
- **Gastro:** Anzahl Lokale je Region, Aufschlag gegenüber dem Ladenpreis, Personal und Küche, Angebot (eher Bar, eher Restaurant).
- **Grosshändler und Verteiler:** Gebiete, Lieferfrequenz, Mindestbestellmenge für Kunden (neu).
- **Hersteller:** Rezeptur und Qualität, Rohstoffmix, Reifezeit bei Wein.

### Marketing

- Budget pro Jahr.
- Aufteilung zwischen Werbung für die Marke und für die Läden oder Lokale.
- Zielgruppe nach Alter, weil die Altersgruppen verschieden stark auf Werbung reagieren.
- Bei Werbeverbot: was mit dem Budget passiert.

### Forschung und Patente

- F&E-Stufen im Baum wählen und Reihenfolge festlegen.
- Erfindungen als Patent anmelden oder geheim halten.
- Lizenzen an andere vergeben (neu) oder fremde Lizenzen kaufen (neu).

### Geld

- Bank wählen, zweites Konto bei einer anderen Bank (Schutz bei Bankpleite).
- Betriebskredit und Investitionskredit beantragen, zurückzahlen.
- Reserve: wie viele Monate Kosten in der Kasse bleiben.
- Gewinnverwendung nach OR: gesetzliche Reserve, Dividende, Vortrag.
- Börsengang (ab Jahr 1), später Kapitalerhöhung (neu).
- Überschüssiges Geld in Aktien oder ETFs anlegen.

### Holding und Übernahmen

- Firmen ganz oder teilweise kaufen, Tochter verkaufen, Fusion vorschlagen (Grenze 40 % Marktanteil).
- CEO für jede Tochter einstellen und entlassen, Lohn verhandeln, Vorgaben machen (Gewinnabgabe, Investitionsbudget).
- Auf Übernahmeangebote für die eigene Firma reagieren.
- Die eigene Firma verkaufen (an einen Käufer aus der Simulation oder über die Börse). Damit endet das Spiel, siehe «Ende».

### Regeln brechen (freiwillig, mit Risiko)

Die Simulation kennt heute Verstösse mit Busse und Rufschaden, wenn sie auffliegen: Lohndumping, billigeres Material, Steuern sparen und fremde Patente verletzen. Der Spieler darf das auch tun. Er kennt die Entdeckungswahrscheinlichkeit nicht genau. Fliegt es auf, kommt eine Meldung, eine Busse und der Ruf sinkt.

### Reaktion auf Ereignisse

- Neue Gesetze (Mindestlohn, Alkoholsteuer, Zuckersteuer, Pfand, Werbeverbot, Zoll): anpassen oder abwarten.
- Rohstoffengpass, Schaden beim Transport, Vergiftungsfall: Rückruf ja oder nein (neu), Kommunikation (neu).

## Was der Spieler sieht

Die eigene Firma vollständig. Von der Konkurrenz nur Öffentliches: Preise, Börsenkurs, Geschäftsbericht einmal im Jahr, Chronik. Die Wirkung fremder F&E-Stufen bleibt verborgen. Das Beobachter-Dashboard mit allen Daten gibt es erst nach Spielende.

## Übernahmen und CEOs

- Kauft der Spieler eine andere Firma, entsteht eine Holding (oder die Firma kommt in die bestehende). Der Spieler besitzt die Holding und damit die gekaufte Firma.
- **Selbst führen darf er nur seine gegründete Firma.** Für jede gekaufte Firma muss er einen CEO einstellen. Der CEO führt die Firma mit der normalen Firmenlogik, gefärbt durch seinen Stil (z.B. vorsichtig, auf Wachstum aus, sparsam, auf Marketing aus).
- Der Spieler gibt der Tochter nur grobe Vorgaben: Gewinnabgabe an die Holding, Budget für Investitionen, Verkauf der Tochter. Er kann den CEO entlassen und einen anderen einstellen.
- Ein CEO führt immer nur eine Firma. Der CEO kostet einen Lohn, der in der Tochter als Kosten zählt.
- Ohne CEO (z.B. direkt nach dem Kauf oder nach einer Pensionierung) läuft die Tochter auf einem vorsichtigen Autopiloten und es kommt jeden Monat eine Mahnung, bis ein CEO eingestellt ist.

### Die 20 CEO-Avatare

- 20 feste Personen mit Name, Geburtstag, Stil und Bild. Die Liste steht in `docs/avatar-prompts.md`.
- Wählbar ab 25 Jahren. Mit 65 gehen sie in Pension und sind nicht mehr wählbar. Ein amtierender CEO tritt an seinem 65. Geburtstag zurück, der Spieler muss einen Nachfolger einstellen.
- Bei Spielstart sind 10 Avatare da, zwischen 25 und 52 Jahre alt. Die anderen 10 tauchen später auf, jeder in einem eigenen Spieljahr und mit eigenem Alter (z.B. Spieljahr 32 mit 20 Jahren, wählbar ab 25, also ab Spieljahr 37). Die Daten sind so gewählt, dass jeder neue Avatar spätestens dann wählbar wird, wenn der nächste in Pension geht. Damit sind von Spieljahr 0 bis 51 immer mindestens 10 wählbar (nachgerechnet). Läuft ein Spiel länger, braucht es zusätzliche Avatare.
- Das Bild wechselt mit dem Alter: jung (25–39), mittel (40–54), alt (55–64). Ein Avatar bekommt nur Bilder für Altersstufen, die er im Spiel noch erreicht. Wer bei Spielstart schon 42 ist, hat also kein junges Bild.
- Bilder liegen später unter `market_sim/static/avatare/`, Name z.B. `ceo_07_mittel.png`.

## Berater mit Sprachmodell

- Im Cockpit gibt es einen Knopf «Berater fragen». Das Sprachmodell (GLM über den CSCS-Zugang, Anbindung über `llm.py`) bekommt die eigenen Zahlen und die öffentlichen Daten und gibt 3 bis 5 kurze Tipps mit Begründung.
- Der Berater sieht nicht mehr als der Spieler, verrät also keine geheimen Zahlen der Konkurrenz.
- Er entscheidet nichts selbst, der Spieler muss die Tipps umsetzen.
- Nur auf Knopfdruck, so bleibt man unter der Grenze von 14 Anfragen pro Minute. Fällt GLM aus, kommt eine kurze Meldung und das Spiel läuft ohne Berater weiter.

## Meldungen

Kurze Meldungen im Stil eines Managerspiels, aus den Chronik-Vorlagen: «Brauerei Aare senkt den Preis um 8 %», «Die SNB erhöht den Leitzins», «Reto Gerber geht im März in Pension». Manche verlangen einen Entscheid, z.B. ein Übernahmeangebot für die eigene Firma.

## Ende

- Freiwilliges Ende: Der Spieler verkauft seine gegründete Firma. Der Verkaufserlös zählt als Endergebnis. Danach übernimmt die normale Firmenlogik die Firma beim Käufer, und die Simulation läuft ohne Halt bis zum Ende der eingestellten Jahre weiter. Der Spieler sieht danach das volle Beobachter-Dashboard und kann verfolgen, was aus seiner Firma wird.

- Verloren bei Konkurs der eigenen Firma oder wenn sie übernommen wird.
- Sonst spielt man so lange man will. Am Schluss ein Rückblick: Kurven der eigenen Firma und der Holding gegen die Konkurrenz, Rang nach Firmenwert, wichtigste Entscheide.

## Wie man es umsetzen könnte

- **Spieler-Logik:** Für die Spielerfirma ersetzt eine eigene Logik die heutige Firmenlogik (`decisions.py`, `policies.py`). Sie liefert die Entscheide aus dem Cockpit. Der Rest der Simulation merkt keinen Unterschied.
- **Neue Firma:** Die Gründung nutzt den bestehenden Eintritt neuer Firmen, nur mit Namen, Branche und Region vom Spieler.
- **CEO-Logik:** Töchter laufen mit der normalen Firmenlogik, der Stil des CEO verschiebt ein paar Regler (Risiko, Preisniveau, Investitionsfreude). Die Holding-Regeln (`holdings.py`, `holding_groups.py`) bleiben, nur gehört die Holding dem Spieler.
- **Anhalten:** `runner.py` bekommt einen Haltepunkt pro Monat, der Zustand wird dort gespeichert (`checkpoint.py`). Damit gibt es Spielstände.
- **Oberfläche:** Neuer Reiter «Cockpit» im Dashboard über `serve.py`, mit Formularen, CEO-Auswahl (Bild, Alter, Stil, Lohn) und Berater-Knopf.
- **Tempo:** Ein Monat muss in wenigen Sekunden gerechnet sein. Vor dem Bau messen.

## Mögliche Phasen

1. Gründung, Spieler-Logik und Haltepunkt, nur Preis und Menge, ohne Oberfläche (zum Testen).
2. Cockpit, Meldungen, Spielstände.
3. Übrige bestehende Entscheide (Mitarbeiter, Einkauf, Transport, Geld, F&E, Marketing, Branchen-Eigenheiten) und Autopilot je Bereich.
3b. Die neuen Entscheide «(neu)», für den Spieler und die anderen Firmen.
4. Übernahmen mit Holding, CEOs und Avataren mit Bildern.
5. Berater mit GLM.
6. Rückblick und Feinabstimmung.

## Ideen für später

- Szenarien mit Ziel und Frist.
- Mehrere Spieler gegeneinander (abwechselnd am gleichen Gerät oder übers Netz).
