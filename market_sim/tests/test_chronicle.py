"""Template based chronicle and firm stories (no language model)."""

import re

import pytest

from market_sim import chronicle_templates as ct
from market_sim.config import load_market_config
from market_sim.dashboard_data import build_dashboard_data
from market_sim.llm import FakeLLM
from market_sim.models import load_firms
from market_sim.run import run_simulation
from market_sim.texts import (KEY_EVENTS, YEAR_EVENTS, _follow_ups_for, _Picker, _safe_format,
                              generate_texts, template_chronicle)

KNOWN = {"firma", "jahr", "details", "stufe", "ereignis", "gewinn", "firmen", "frueher", "bestjahr", "schlechtjahr",
         "zeit", "ziel", "liste", "anzahl", "nachfolger"}
WHEN = {"profit", "loss", "loss_streak3", "largest_in_stage", "first_in_stage", "last_in_stage"}


@pytest.fixture(scope="module")
def data():
    config = load_market_config()
    network = load_firms()
    result = run_simulation(12, 0, 20, config, network)
    return build_dashboard_data(result, network, config, 0)


def _all_template_strings():
    for entries in ct.EVENT_TEMPLATES.values():
        for entry in entries:
            yield entry["text"]
    yield from ct.GENERIC_TEMPLATES
    for group in (ct.INTRO, ct.FOLLOW_UPS, ct.STORY_END, ct.STORY_PROFIT):
        for texts in group.values():
            yield from texts
    yield from ct.STORY_START
    for kinds in ct.GROUP_TEMPLATES.values():
        for texts in kinds.values():
            yield from texts


def test_every_key_and_year_event_has_a_template_chronicle():
    for name in KEY_EVENTS | YEAR_EVENTS:
        entries = ct.EVENT_TEMPLATES[name]
        assert any(e["when"] is None for e in entries), name
        assert name in ct.EVENT_IMPORTANCE


def test_templates_only_use_known_placeholders_chronicle():
    for text in _all_template_strings():
        assert set(re.findall(r"\{(\w*)\}", text)) <= KNOWN, text
        assert "ß" not in text
    for entries in ct.EVENT_TEMPLATES.values():
        assert all(e["when"] is None or e["when"] in WHEN for e in entries)


def test_no_gap_stays_in_generated_texts_chronicle(data):
    texts = generate_texts(data, None)
    assert set(texts["stories"]) == set(data["firms"])
    assert set(texts["chronicle"]) == {str(k["year"]) for k in data["system"]}
    for group in texts.values():
        for entry in group.values():
            assert entry["checked"] is True and entry["text"]
            assert "{" not in entry["text"] and "}" not in entry["text"] and "ß" not in entry["text"]
    assert set(generate_texts(data, FakeLLM())["chronicle"]) == set(texts["chronicle"])


def test_same_seed_same_text_chronicle(data):
    assert generate_texts(data, None, seed=3) == generate_texts(data, None, seed=3)
    assert generate_texts(data, None, seed=3)["chronicle"] != generate_texts(data, None, seed=4)["chronicle"]


def test_picker_never_repeats_in_a_row_chronicle():
    for candidates in (["a", "b", "c"], ["a", "b"]):
        picker = _Picker(1)
        picks = [picker.pick(candidates) for _ in range(200)]
        assert all(x != y for x, y in zip(picks, picks[1:]))


def test_unknown_event_uses_generic_template_chronicle(data):
    year = data["system"][0]["year"]
    d = dict(data, events=[{"year": year, "day": 1, "firm": "", "event": "brand_new_kind", "details": ""}])
    text = template_chronicle(d, year, _Picker(0), {})
    assert "brand new kind" in text and "{" not in text


def test_follow_up_index_chronicle():
    events = [{"year": 2, "firm": "f1", "event": "takeover", "details": ""},
              {"year": 5, "firm": "f1", "event": "spin_off", "details": ""}]
    idx = _follow_ups_for(events)
    assert idx[id(events[1])] == ("takeover>spin_off", 2) and id(events[0]) not in idx


def test_safe_format_blanks_missing_values_chronicle():
    out = _safe_format("A {x} B {y}", x="1")
    assert "{" not in out and "1" in out


_TIME_COMMA = re.compile(r"(?:Im selben Jahr|Kurz darauf|Ausserdem|Gleichzeitig|Trotzdem|Dennoch|Wenig später|"
                         r"Später im Jahr|Ebenfalls im Jahr \d+|Im Jahr \d+),")


def test_no_comma_after_time_word_chronicle(data):
    texts = generate_texts(data, None)
    for group in texts.values():
        for entry in group.values():
            assert not _TIME_COMMA.search(entry["text"]), entry["text"]


def test_event_templates_start_with_time_slot_chronicle():
    for entries in ct.EVENT_TEMPLATES.values():
        for e in entries:
            assert e["text"].startswith("{zeit} ") and "{jahr}" not in e["text"]
    assert all(t.startswith("{zeit} ") for t in ct.GENERIC_TEMPLATES)


def test_same_kind_is_merged_in_one_year_chronicle(data):
    year = data["system"][0]["year"]
    firms = list(data["firms"])[:3]
    events = [{"year": year, "day": 10 + i, "firm": f, "event": "stake_bought", "details": "kauft 11% an x für 5 CHF"}
              for i, f in enumerate(firms)]
    d = dict(data, events=events)
    text = template_chronicle(d, year, _Picker(0), {})
    names = [data["firms"][f]["name"] for f in firms]
    assert text.count("Beteiligung") == 1 and "darunter" in text
    assert names[0] in text and names[1] in text
    d2 = dict(data, events=events[:2])
    text2 = template_chronicle(d2, year, _Picker(0), {})
    assert text2.count("Beteiligung") == 1 and f"{names[0]} und {names[1]}" in text2


def test_no_two_sentences_of_same_kind_per_year_chronicle(data):
    year = data["system"][0]["year"]
    firms = list(data["firms"])[:2]
    events = [{"year": year, "day": 5 + i, "firm": f, "event": "recession", "details": ""} for i, f in enumerate(firms)]
    text = template_chronicle(dict(data, events=events), year, _Picker(0), {})
    assert text.count("Rezession") <= 1


def test_new_event_kinds_have_templates_and_render_chronicle():
    from market_sim.texts import _event_sentence
    for name in ("delisted", "lease_started", "lease_ended", "lease_default"):
        assert any(e["when"] is None for e in ct.EVENT_TEMPLATES[name]), name
        assert name in ct.EVENT_IMPORTANCE
    for reason in ("holding", "merger", "takeover", "bankruptcy", "exit"):
        assert len(ct.EVENT_TEMPLATES[f"delisted_{reason}"]) >= 2
    assert ct.EVENT_IMPORTANCE["lease_default"] > ct.EVENT_IMPORTANCE["lease_started"]
    data = {"firms": {"a": {"name": "Alpha AG"}, "b": {"name": "Beta AG"}}}
    for reason in ("holding", "merger", "takeover", "bankruptcy", "exit", None):
        for successor in ("b", None):
            event = {"year": 3, "day": 1, "firm": "a", "event": "delisted", "details": "",
                     "reason": reason, "successor": successor}
            for seed in range(6):
                text = _event_sentence(data, event, _Picker(seed), zeit="Im Jahr 3")
                assert "Alpha AG" in text and "{" not in text and "  " not in text
                if successor is None:
                    assert "Beta AG" not in text
    for name in ("lease_started", "lease_ended", "lease_default"):
        text = _event_sentence(data, {"year": 2, "firm": "a", "event": name, "details": ""}, _Picker(1), zeit="Im Jahr 2")
        assert "Alpha AG" in text
