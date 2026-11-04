"""Phase 12: stories, chronicle and chat from checked facts (tests use a fake model)."""

import pytest

from market_sim.config import load_market_config
from market_sim.dashboard_data import build_dashboard_data
from market_sim.llm import FakeLLM, unchecked_numbers
from market_sim.models import load_firms
from market_sim.run import run_simulation
from market_sim.serve import answer
from market_sim.texts import context_for_question, firm_facts, generate_texts, write_checked


@pytest.fixture(scope="module")
def data():
    config = load_market_config()
    network = load_firms()
    result = run_simulation(12, 0, 20, config, network)
    return build_dashboard_data(result, network, config, 0)


def test_numbers_must_come_from_the_facts():
    facts = "- Gewinn insgesamt: 52 Mio. CHF\n- Bestes Jahr: Jahr 7"
    assert unchecked_numbers("Die Firma verdiente 52 Mio. CHF, am meisten in Jahr 7.", facts) == []
    assert unchecked_numbers("Gegründet 2002 mit 52 Mio. CHF.", facts) == [2002.0]


class _Liar:
    def generate(self, system, prompt):
        return "Die Firma wurde 1999 gegründet."


def test_invented_numbers_fall_back_to_a_plain_summary(data):
    firm_id = next(iter(data["firms"]))
    result = write_checked(_Liar(), "Schreibe die Geschichte.", firm_facts(data, firm_id))
    assert result["checked"] is False and "1999" not in result["text"]


def test_stories_and_chronicle_for_every_firm_and_year(data):
    texts = generate_texts(data, FakeLLM())
    assert set(texts["stories"]) == set(data["firms"])
    assert set(texts["chronicle"]) == {str(k["year"]) for k in data["system"]}
    assert all(t["checked"] for t in texts["stories"].values())


def test_chat_context_picks_the_right_year_and_firm(data):
    facts, sources = context_for_question(data, "Was passierte in Jahr 10?")
    assert sources == ["Jahresbericht Jahr 10"]
    name = next(iter(data["firms"].values()))["name"]
    _, sources = context_for_question(data, f"Wie lief es bei {name}?")
    assert sources[0] == f"Firma {name}"


def test_chat_answer_lists_its_sources(data):
    reply = answer(data, FakeLLM(), "Was passierte in Jahr 5?")
    assert reply["sources"] == ["Jahresbericht Jahr 5"] and reply["answer"]
