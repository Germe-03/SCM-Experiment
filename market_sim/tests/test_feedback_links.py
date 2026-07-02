"""Isolated tests for the runner's annual feedback links."""

import pytest

from market_sim.config import load_market_config
from market_sim.models import load_firms
from market_sim.policies import policies_for_network
from market_sim.runner import SimulationRunner


def _runner(config=None):
    config = config or load_market_config()
    network = load_firms()
    firms = [firm for stage in network.stages for firm in stage.firms]
    return SimulationRunner(network, config, policies_for_network(firms), seed=0)


def _setup(config=None):
    runner = _runner(config)
    runner.env.reset()
    firm = runner.network.firm("retailer_01")
    firm.reputation = 0.5
    firm.reliability = 0.9
    firm.quality_level = 0.8
    runner.env.runtimes[firm.id].quality_level = 0.8
    return runner, firm


def test_feedback_link_wage_raises_reputation():
    low_runner, low_wage = _setup()
    high_runner, high_wage = _setup()
    low_wage.wage_level = 2500.0
    high_wage.wage_level = 7500.0

    low_runner._apply_feedback_links(low_wage, 1.0, 0.5, [5.0, 5.0])
    high_runner._apply_feedback_links(high_wage, 1.0, 0.5, [5.0, 5.0])

    assert high_wage.reputation > low_wage.reputation


def test_feedback_link_reliability_is_earned_and_can_be_disabled():
    low_runner, low_fill = _setup()
    for _ in range(3):
        low_runner._apply_feedback_links(low_fill, 0.2, 0.5, [5.0, 5.0])
    full_runner, full_fill = _setup()
    full_runner._apply_feedback_links(full_fill, 1.0, 0.5, [5.0, 5.0])

    config = load_market_config()
    config = config.model_copy(update={
        "reliability": config.reliability.model_copy(
            update={"reliability_adjust_speed": 0.0}
        )
    })
    disabled_runner, disabled = _setup(config)
    disabled_runner._apply_feedback_links(disabled, 0.0, 0.5, [5.0, 5.0])

    assert low_fill.reliability < 0.9
    assert full_fill.reliability >= 0.9
    assert disabled.reliability == pytest.approx(0.9)


def test_feedback_link_price_volatility_lowers_reputation():
    stable_runner, stable = _setup()
    erratic_runner, erratic = _setup()
    stable_runner._apply_feedback_links(stable, 1.0, 0.5, [5.0] * 4)
    erratic_runner._apply_feedback_links(erratic, 1.0, 0.5, [2.0, 8.0] * 2)

    assert erratic.reputation < stable.reputation


def test_feedback_link_capacity_overload_reduces_quality():
    below_runner, below = _setup()
    overload_runner, overloaded = _setup()
    below_runner._apply_feedback_links(below, 1.0, 0.8, [5.0, 5.0])
    overload_runner._apply_feedback_links(overloaded, 1.0, 1.0, [5.0, 5.0])

    assert below.quality_level == pytest.approx(0.8)
    assert overloaded.quality_level < below.quality_level
