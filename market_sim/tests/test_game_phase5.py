"""Spielmodus Phase 5: Berater mit Sprachmodell (ohne echtes Modell getestet)."""

from market_sim.game.advisor import advise, facts_from_state, parse_tips
from market_sim.game.controller import GameController


class ScriptedLLM:
    def __init__(self, text="- Preis leicht senken, weil die Konkurrenz billiger ist\n- Lagerziel erhöhen\n"):
        self.text, self.prompts = text, []

    def generate(self, system, prompt):
        self.prompts.append((system, prompt))
        return self.text


class BrokenLLM:
    def generate(self, system, prompt):
        raise TimeoutError("zu langsam")


def test_parse_tips_and_no_sharp_s():
    tips = parse_tips("Einleitung\n- Grösse anpassen\n* Strasse\n1. Mass halten")
    assert tips == ["Grösse anpassen", "Strasse", "Mass halten"]
    assert all("ß" not in t for t in parse_tips("- Straße"))


def test_controller_advice_uses_only_visible_state(tmp_path):
    controller = GameController(tmp_path, seed=0, years=1, days_per_year=60)
    state = controller.new_game("hersteller", "Testbräu", category="beer")
    llm = ScriptedLLM()
    result = controller.advise("Soll ich den Preis senken?", llm=llm)
    assert result["error"] is None
    assert len(result["tips"]) == 2
    system, prompt = llm.prompts[0]
    assert "Testbräu" in prompt and "Soll ich den Preis senken?" in prompt
    # Geheime Grössen der Konkurrenz (z.B. Entdeckungswahrscheinlichkeit) kommen nicht vor.
    assert "detection" not in prompt and "willing" not in prompt
    assert facts_from_state(state)


def test_advice_error_and_no_game(tmp_path):
    assert advise(ScriptedLLM(), {"running": False})["answer"] == "Es läuft kein Spiel."
    controller = GameController(tmp_path, seed=0, years=1, days_per_year=60)
    controller.new_game("hersteller", "Testbräu", category="beer")
    result = controller.advise(llm=BrokenLLM())
    assert result["tips"] == [] and "antwortet nicht" in result["error"]
