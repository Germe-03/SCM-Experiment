import pytest


@pytest.fixture
def controller(tmp_path):
    from market_sim.game.controller import GameController

    return GameController(tmp_path, seed=0, years=1, days_per_year=60)


def play_until(controller, predicate, max_rounds):
    """Spielt Runden, bis die Bedingung erfuellt ist oder das Limit erreicht ist."""
    state = controller.state()
    for _ in range(max_rounds):
        if predicate(state):
            break
        if state.get("game_over"):
            break
        state = controller.end_round({})
        assert "error" not in state

    assert predicate(state), f"Bedingung nach {max_rounds} Runden nicht erreicht"
    return state


def test_player_choices_update_unknown_key_and_to_dict_fields():
    from market_sim.game.choices import PlayerChoices

    choices = PlayerChoices()
    assert set(choices.to_dict()) == {
        "marketing_budget",
        "research_target",
        "credit_mode",
        "bank_id",
        "payout_ratio",
        "listing",
        "transport_mode",
        "auto_invest",
        "expand_order",
        "site_order",
        "commodity_courage",
        "markup_factor",
        "offences",
        "marketing_focus",
        "marketing_target",
        "supplier_id",
        "supplier_rule",
        "supplier_shares",
        "courier_preference",
        "patent_lawsuits",
        "category_shares",
        "component_plan",
        "brand_plan",
        "storage_order",
        "cancel_open_orders",
        "daughter_rules",
        "brand_suppliers",
        "brand_prices",
    }

    with pytest.raises(ValueError):
        choices.update({"unbekannt": 1})


def test_runs_without_player_choices_have_deterministic_cash():
    from market_sim.run import build_runner

    def run_cash():
        runner, years = build_runner(years=2, seed=3, days_per_year=60)
        runner.continue_run(runner.start(), years)
        return {fid: runtime.cash for fid, runtime in runner.env.runtimes.items()}

    assert run_cash() == run_cash()


def test_marketing_budget_choice_is_used_after_year_change(tmp_path):
    from market_sim.game.controller import GameController

    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    state = controller.new_game("hersteller", "Testbräu")
    assert "error" not in state

    state = controller.end_round({}, {"marketing_budget": 0})
    assert "error" not in state
    assert state["choices"]["marketing_budget"] == 0

    play_until(controller, lambda current: current["year"] == 2, 14)

    runner = controller.session.runner
    if runner.marketing is None:
        pytest.skip("Marketing-System ist nicht verfuegbar")

    firm_id = controller.session._firm_id
    assert runner.marketing.daily_budget.get(firm_id, 0) == 0


def test_credit_mode_never_prevents_player_loan(tmp_path):
    from market_sim.game.controller import GameController

    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    state = controller.new_game("hersteller", "Testbräu")
    assert "error" not in state

    state = controller.end_round({}, {"credit_mode": "never"})
    assert "error" not in state
    play_until(
        controller,
        lambda current: current.get("game_over", False) or current["year"] > 2,
        30,
    )

    runner = controller.session.runner
    banking = runner.env.banking
    if banking is None:
        pytest.skip("Banking-System ist nicht verfuegbar")

    firm_id = controller.session._firm_id
    assert not any(
        loan.firm_id == firm_id for loan in banking.loans.values()
    )


def test_player_commits_no_offences_without_choice(controller):
    state = controller.new_game("hersteller", "Testbräu")
    assert "error" not in state

    play_until(
        controller,
        lambda current: current.get("game_over", False) or current["year"] > 1,
        14,
    )

    runner = controller.session.runner
    state_actor = runner.state_actor
    if state_actor is None:
        pytest.skip("State-System ist nicht verfuegbar")

    firm_id = controller.session._firm_id
    assert not any(item.get("firm") == firm_id for item in state_actor.offence_ledger)
    assert not state_actor.active.get(firm_id, set())


def test_save_and_load_preserve_choices(controller):
    state = controller.new_game("hersteller", "Testbräu")
    assert "error" not in state

    state = controller.end_round({}, {"payout_ratio": 0.5})
    assert "error" not in state
    assert state["choices"]["payout_ratio"] == 0.5

    assert controller.save("t1").get("ok") is True
    loaded = controller.load("t1")

    assert "error" not in loaded
    assert loaded["choices"]["payout_ratio"] == 0.5


def test_options_include_banks_and_offences_without_detection_probability(controller):
    options = controller.options()

    assert isinstance(options["banks"], list)
    assert isinstance(options["offences"], list)
    assert all({"id", "name"} <= set(bank) for bank in options["banks"])
    assert all(
        {"name", "benefit", "fine"} <= set(offence)
        and "detection_probability" not in offence
        for offence in options["offences"]
    )
