"""Each new research kind changes only its intended cost or workforce."""

import pytest
from pydantic import ValidationError

from market_sim.config import ResearchProjectConfig
from market_sim.run import build_runner


@pytest.mark.parametrize("name,component,effect", [("leichtere_flaschen", "packaging", 0.15), ("waermerueckgewinnung", "energy", 0.2), ("ausbeute_optimierung", "malt", 0.08)])
def test_component_projects(name, component, effect):
    runner, _ = build_runner(1, 0, days_per_year=10)
    runner.start()
    env = runner.env
    firm = runner.network.firm("factory_01")
    before = env.unit_production_cost(firm)
    runner.lab._apply(runner, firm, runner.lab.projects[name])
    expected = runner.config.commodities.components[component] * effect
    assert before - env.unit_production_cost(firm) == pytest.approx(expected)
    assert env.component_factor[firm.id][component] == pytest.approx(1 - effect)
    assert env.component_factor.get("factory_02", {}) == {}


def test_transport_project_changes_shipper_quote_and_payment():
    runner, _ = build_runner(1, 0, days_per_year=10)
    runner.start()
    firm, buyer = runner.network.firm("factory_01"), runner.network.firm("distributor_01")
    geo = runner.env.geography
    quote = geo.unit_transport_cost(firm, buyer)
    runner.lab._apply(runner, firm, runner.lab.projects["routenplanung"])
    assert geo.unit_transport_cost(firm, buyer) == pytest.approx(quote * 0.85)
    before = runner.env.runtimes[firm.id].handling_cost
    geo.ship(runner.env, firm, buyer, {"test": 10})
    assert runner.env.runtimes[firm.id].handling_cost - before == pytest.approx(quote * 0.85 * 10)


def test_storage_project_reduces_actual_holding_charge():
    runner, _ = build_runner(1, 0, days_per_year=10)
    runner.start()
    firm = runner.network.firm("retailer_01")
    rt = runner.env.runtimes[firm.id]
    before = rt.holding_cost
    runner.lab._apply(runner, firm, runner.lab.projects["lagerautomation"])
    rt.inventory = 100
    rt.calculate_period_cost(0)
    assert rt.cumulative_holding_cost == pytest.approx(100 * before * 0.75)


@pytest.mark.parametrize("employees", [1, 3, 100])
def test_robotics_keeps_effective_capacity(employees):
    runner, _ = build_runner(1, 0, days_per_year=10)
    runner.start()
    firm = runner.network.firm("retailer_01")
    firm.employees = employees
    capacity = runner.env._effective_capacity(firm.id)
    runner.lab._apply(runner, firm, runner.lab.projects["robotik"])
    assert firm.employees == max(1, employees - round(employees * 0.25))
    assert runner.env.runtimes[firm.id].employees == firm.employees
    assert runner.env._effective_capacity(firm.id) == capacity


def test_component_is_required():
    with pytest.raises(ValidationError):
        ResearchProjectConfig(name="bad", kind="component_reduction", cost=1, duration_days=1, success_probability=1)
