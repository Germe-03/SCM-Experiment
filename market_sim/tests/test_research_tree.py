"""Phase 24: research trees with prerequisites, follower discount and separate implementation."""

from dataclasses import replace

import pytest

from market_sim.research_tree import ResearchTreeLab, tree_key
from market_sim.run import build_runner


def _runner():
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    runner.continue_run(state, 1)
    return runner, state


def _finish(runner, state, firm_id, name, step, success=True, tree="factory"):
    lab = runner.lab
    lab.stages[tree][name].success_probability = 1.0 if success else 0.0
    lab.running[firm_id] = (name, 0, runner.env.period, 1000.0, 1, step, tree)
    lab.year_end(runner, state)


def test_lab_is_tree_lab_and_tree_keys():
    runner, _ = _runner()

    assert isinstance(runner.lab, ResearchTreeLab)
    assert tree_key(runner.network.firm("factory_01")) == "factory"

    restaurants = [
        firm
        for firm in runner.network.firms_in("retailer")
        if firm.stage == "retailer" and firm.channel == "restaurant"
    ]
    if restaurants:
        assert tree_key(restaurants[0]) == "restaurant"


def test_prerequisites():
    runner, _ = _runner()
    lab = runner.lab
    firm = runner.network.firm("factory_01")

    names = {stage.name for stage in lab.options(firm)}
    assert "prozessautomation" in names
    assert "robotik" not in names
    assert "smart_factory" not in names

    lab.progress[firm.id] = {"prozessautomation": "implemented"}
    assert "robotik" in {stage.name for stage in lab.options(firm)}

    lab.progress[firm.id] = {"prozessautomation": "researched"}
    assert "robotik" not in {stage.name for stage in lab.options(firm)}


def test_unreachable_requirement_counts_as_met():
    runner, _ = _runner()
    lab = runner.lab
    wine_firms = [
        firm
        for firm in runner.network.firms_in("factory")
        if firm.category == "wine" and not firm.importer
    ]
    if not wine_firms:
        pytest.skip("No non-importing wine factory in this network")

    wine_firm = wine_firms[0]
    lab.progress[wine_firm.id] = {"neue_marke": "implemented"}
    wine_options = {stage.name for stage in lab.options(wine_firm)}

    assert "neue_geschmacksrichtung" in wine_options
    assert "alkoholfreies_produkt" not in wine_options
    assert "kuerzere_reifezeit" in wine_options

    beer_firm = runner.network.firm("factory_01")
    assert "kuerzere_reifezeit" not in {
        stage.name for stage in lab.options(beer_firm)
    }


def test_follower_discount_by_complexity():
    runner, _ = _runner()
    lab = runner.lab

    for name, discount in (
        ("prozessautomation", 0.25),
        ("robotik", 0.5),
        ("smart_factory", 0.75),
    ):
        stage = lab.stages["factory"][name]
        key = ("factory", name)
        lab.first_success.pop(key, None)

        assert lab.research_cost("factory", stage, 1) == pytest.approx(stage.cost)

        lab.first_success[key] = 1
        assert lab.research_cost("factory", stage, 1) == pytest.approx(
            stage.cost * discount
        )


def test_effect_only_after_implementation():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    firm = runner.network.firm("factory_01")
    before = firm.productivity_per_employee

    _finish(runner, state, firm.id, "prozessautomation", "research")

    assert runner.lab.progress[firm.id]["prozessautomation"] == "researched"
    assert firm.productivity_per_employee == pytest.approx(before)
    research_report = next(
        report
        for report in reversed(runner.lab.reports)
        if report["firm"] == firm.id
    )
    assert research_report["step"] == "research"
    assert research_report["success"] is True
    assert any(
        event["firm"] == firm.id and event["event"] == "rnd_success"
        for event in state.events
    )

    _finish(runner, state, firm.id, "prozessautomation", "implementation")

    assert runner.lab.progress[firm.id]["prozessautomation"] == "implemented"
    assert firm.productivity_per_employee == pytest.approx(before * 1.15)
    implementation_report = next(
        report
        for report in reversed(runner.lab.reports)
        if report["firm"] == firm.id
    )
    assert implementation_report["step"] == "implementation"
    assert any(
        event["firm"] == firm.id and event["event"] == "rnd_implemented"
        for event in state.events
    )


def test_failed_research_keeps_option():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    firm = runner.network.firm("factory_01")

    _finish(
        runner,
        state,
        firm.id,
        "leichtere_flaschen",
        "research",
        success=False,
    )

    assert "leichtere_flaschen" not in runner.lab.progress.get(firm.id, {})
    assert "leichtere_flaschen" in {
        stage.name for stage in runner.lab.options(firm)
    }
    report = next(
        report
        for report in reversed(runner.lab.reports)
        if report["firm"] == firm.id
    )
    assert report["success"] is False


def test_implementation_starts_next_year_at_full_price():
    runner, state = _runner()
    lab = runner.lab
    lab.running.clear()
    lab.progress["factory_01"] = {"robotik": "researched"}
    lab.first_success[("factory", "robotik")] = 1
    runner.env.runtimes["factory_01"].cash = 1e12
    state.summaries[-1]["factory_01"] = replace(
        state.summaries[-1]["factory_01"],
        profit=1e6,
    )
    stage = lab.stages["factory"]["robotik"]

    lab.year_end(runner, state)

    name, _, _, daily_cost, _, step, _ = lab.running["factory_01"]
    assert name == "robotik"
    assert step == "implementation"
    assert daily_cost * stage.implementation_days == pytest.approx(
        stage.implementation_cost * runner.long_run.price_index
    )


def test_same_stage_researched_concurrently():
    runner, state = _runner()
    lab = runner.lab
    lab.cfg.start_probability = 0.0
    factory_ids = [firm.id for firm in runner.network.firms_in("factory")]
    other_id = next(firm_id for firm_id in factory_ids if firm_id != "factory_01")

    lab.stages["factory"]["prozessautomation"].success_probability = 1.0
    lab.progress["factory_01"] = {}
    lab.progress[other_id] = {}
    lab.running["factory_01"] = (
        "prozessautomation",
        0,
        runner.env.period,
        1000.0,
        1,
        "research",
        "factory",
    )
    lab.running[other_id] = (
        "prozessautomation",
        0,
        runner.env.period,
        1000.0,
        1,
        "research",
        "factory",
    )

    lab.year_end(runner, state)

    assert lab.progress["factory_01"]["prozessautomation"] == "researched"
    assert lab.progress[other_id]["prozessautomation"] == "researched"
    assert ("factory", "prozessautomation") in lab.first_success


def test_takeover_hands_over_progress():
    runner, _ = _runner()
    lab = runner.lab
    factory_ids = [firm.id for firm in runner.network.firms_in("factory")]
    other_id = next(firm_id for firm_id in factory_ids if firm_id != "factory_01")

    lab.progress = {
        "factory_01": {
            "prozessautomation": "implemented",
            "leichtere_flaschen": "researched",
        },
        other_id: {"leichtere_flaschen": "implemented"},
    }
    lab.running["factory_01"] = (
        "robotik",
        0,
        99,
        1.0,
        1,
        "research",
        "factory",
    )

    lab.transfer("factory_01", other_id)

    assert lab.progress[other_id]["prozessautomation"] == "researched"
    assert lab.progress[other_id]["leichtere_flaschen"] == "implemented"
    assert "factory_01" not in lab.running


def test_new_kinds():
    runner, _ = _runner()
    lab = runner.lab
    book = runner.env.brand_book

    retailer = runner.network.firm("retailer_01")
    awareness_before = book.store_awareness.get(
        retailer.id, runner.config.marketing.start_awareness
    )
    lab._apply_stage(
        runner,
        retailer,
        lab.stages["retailer"]["kundenkarte"],
    )
    assert book.store_awareness[retailer.id] > awareness_before

    factory = runner.network.firm("factory_01")
    reputation_before = factory.reputation
    lab._apply_stage(
        runner,
        factory,
        lab.stages["factory"]["klimaneutrale_brauerei"],
    )
    assert factory.reputation == pytest.approx(
        min(1.0, reputation_before + 0.05)
    )

    restaurants = [
        firm
        for firm in runner.network.firms_in("retailer")
        if firm.stage == "retailer" and firm.channel == "restaurant"
    ]
    if restaurants:
        restaurant = restaurants[0]
        markup_before = book.markup(restaurant)
        lab._apply_stage(
            runner,
            restaurant,
            lab.stages["restaurant"]["hausbier"],
        )
        assert book.markup(restaurant) == pytest.approx(markup_before * 1.1)


def test_deterministic():
    reports = []
    progress = []

    for _ in range(2):
        runner, _ = build_runner(3, 0, days_per_year=10)
        state = runner.start()
        runner.continue_run(state, 3)
        reports.append(runner.lab.reports)
        progress.append(runner.lab.progress)

    assert reports[0] == reports[1]
    assert progress[0] == progress[1]


def test_phase34_tree_size_levels_and_no_failure():
    from market_sim.kpi import PROJECT_DE

    runner, _ = _runner()
    stages = runner.lab.stages
    assert 25 <= len(stages["factory"]) <= 32
    for tree in ("distributor", "wholesaler", "retailer", "restaurant"):
        assert 8 <= len(stages[tree]) <= 10
    for tree, items in stages.items():
        for name, stage in items.items():
            assert stage.success_probability == 1.0
            assert all(req in items for req in stage.requires)
            assert name in PROJECT_DE
            if name.endswith(("_2", "_3")):
                # Phase 45: Äste sind Ketten; die Vorstufe liegt irgendwo darüber.
                ancestors, todo = set(), list(stage.requires)
                while todo:
                    req = todo.pop()
                    if req not in ancestors:
                        ancestors.add(req)
                        todo.extend(items[req].requires)
                prev = name[:-2] if name.endswith("_2") else name[:-1] + "2"
                assert prev in ancestors
                base = items[prev]
                assert stage.cost > base.cost
                assert stage.implementation_cost >= base.implementation_cost


def test_phase34_level_needs_previous_level():
    runner, _ = _runner()
    lab = runner.lab
    firm = runner.network.firm("factory_01")
    stages = lab.stages["factory"]
    done, todo = set(), list(stages["prozessautomation_2"].requires)
    while todo:
        req = todo.pop()
        if req not in done:
            done.add(req)
            todo.extend(stages[req].requires)
    lab.progress[firm.id] = {name: "implemented" for name in done}
    names = {stage.name for stage in lab.options(firm)}
    assert "prozessautomation_2" in names and "prozessautomation_3" not in names
    lab.progress[firm.id]["prozessautomation_2"] = "implemented"
    assert "prozessautomation_3" in {stage.name for stage in lab.options(firm)}


def test_new_firm_inherits_industry_research_level():
    from market_sim.run import build_runner
    runner, _ = build_runner(years=2, days_per_year=2)
    lab = runner.lab
    state = runner.start()
    factories = [f for f in runner.network.firms_in("factory") if runner.env.runtimes[f.id].active]
    tree = "factory"
    for firm in factories:
        names = [s.name for s in lab.stages[tree].values() if lab.available(firm, s)][:2]
        lab.progress[firm.id] = {n: "implemented" for n in names}
    template = factories[0].model_copy(update={"id": "factory_x1"})
    runner.add_firm(template, state)
    granted = lab.inherit_on_entry(runner, state, template, factories)
    assert 0 < len(granted) <= 2
    assert all(lab.progress["factory_x1"][n] == "implemented" for n in granted)
    assert state.events[-1]["event"] == "rnd_inherited"
    other = runner.network.firms_in("retailer")[0]
    assert lab.inherit_on_entry(runner, state, other, []) == []
