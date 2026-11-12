Du arbeitest im Repo `C:\Users\david\PycharmProjects\SCM-Experiment` (Branch `main`, Stand `b1441fb`). Lies zuerst `docs/bauplan-erweiterung-4.md` vollständig. Dort stehen die Arbeitsregeln und die Phasen 21–33.

Auftrag:

1. Prüfe den Ausgangsstand: `git status`, letzter Commit, alle Tests mit `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider market_sim/tests` (im Hintergrund, dauert länger). Melde kurz, ob alles grün ist.
2. Setze die Phasen **21 bis 27** der Reihe nach um, genau wie im Bauplan beschrieben (David hat sie bestätigt).
   - Code mit dem MCP `delegate-coder` schreiben lassen: echte Logik mit `model: "swissai:CSCS-Inference/zai-org/GLM-5.3"`, einfache Dinge mit `ibm/granite4.1:3b`, immer mit `check_command` (passende Tests). Diff prüfen, nur bei Fehlern selbst nachbessern. Kleine Edits selbst.
   - Pro Phase: Tests ergänzen, alle Tests grün, `runs/dashboard.html` neu erzeugen und den betroffenen Reiter im Browser prüfen, Eintrag im Umsetzungs-Log von `docs/bauplan-erweiterung-4.md`, ein Commit pro Phase **ohne** Co-Authored-By-Zeile. Nicht pushen.
   - Nach jeder Phase kurz in einfachem Deutsch melden, was jetzt geht, und dann mit der nächsten weitermachen.
3. Vor den Phasen **28 bis 33** (Post und Kuriere, Börsengang über Bank, Rohstoffbörse, offene Punkte der Banken) anhalten und mir die offenen Fragen aus dem Bauplan stellen. Erst nach meinen Antworten weitermachen.

Regeln: Deutsch, Schweizer Rechtschreibung, kein ß, kurze und einfache Meldungen ohne Fachjargon. Ordner `.test-tmp-stocks-*` nicht anfassen. Wenn etwas im Bauplan nicht zum Code passt oder eine Phase grösser wird als gedacht, zuerst fragen statt raten.
