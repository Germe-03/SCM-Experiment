from market_sim.config import load_market_config
from market_sim.models import load_firms
from market_sim.policies import FirmPolicy
from market_sim.runner import YearSummary


def _summary(utilization: float) -> YearSummary:
    return YearSummary(
        revenue=0, profit=0, avg_inventory=0, avg_backlog=0, lost_sales=0,
        service_level=1, avg_sell_price=0, quality=0.7,
        capacity_utilization=utilization, cash=100_000,
    )


def test_stage_price_ordering():
    config = load_market_config()
    network = load_firms()
    policy = FirmPolicy()
    prices = [
        policy.decide_annual(network.firm(firm_id), None, config).base_price
        for firm_id in ("factory_01", "distributor_01", "wholesaler_01", "retailer_01")
    ]
    assert prices == sorted(prices)
    assert len(set(prices)) == 4


def test_wages_and_rnd_do_not_compound():
    config = load_market_config()
    firm = load_firms().firm("factory_01")
    policy = FirmPolicy()
    values = []
    for _ in range(3):
        strategy = policy.decide_annual(firm, _summary(0.6), config)
        values.append((strategy.wage_level, strategy.r_and_d_budget))
        firm.wage_level = strategy.wage_level
        firm.r_and_d_budget = strategy.r_and_d_budget
    assert values[0] == values[1] == values[2]


def test_hiring_responds_to_utilization():
    config = load_market_config()
    firm = load_firms().firm("distributor_04")  # growth archetype
    policy = FirmPolicy()
    assert policy.decide_annual(firm, _summary(0.39), config).hiring_plan <= 0
    assert policy.decide_annual(firm, _summary(0.86), config).hiring_plan > 0
