import pytest

from market_sim.config import load_market_config
from market_sim.models import load_firms
from market_sim.policies import FirmPolicy
from market_sim.run import run_simulation
from market_sim.runner import YearSummary


def _summary(*, profit: float, price: float, quality: float, share_change: float) -> YearSummary:
    return YearSummary(
        revenue=10_000_000, profit=profit, avg_inventory=5, avg_backlog=0,
        lost_sales=0, service_level=0.99, avg_sell_price=price,
        quality=quality, capacity_utilization=0.70, cash=1_000_000,
        market_share=0.1, market_share_change=share_change,
    )


def test_feedback_differentiates_a_losing_middle_and_reinforces_success():
    config = load_market_config()
    firm = load_firms().firm("retailer_01")
    policy = FirmPolicy()
    initial = policy.decide_annual(firm, None, config)

    losing = policy.decide_annual(
        firm,
        _summary(profit=-1, price=initial.base_price, quality=0.70, share_change=-0.02),
        config,
    )
    assert losing.positioning == "low_cost"
    assert losing.base_price < initial.base_price
    assert losing.r_and_d_budget < initial.r_and_d_budget

    premium = load_firms().firm("retailer_03")
    premium_initial = policy.decide_annual(premium, None, config)
    winning = policy.decide_annual(
        premium,
        _summary(
            profit=1, price=premium_initial.base_price,
            quality=0.90, share_change=0.01,
        ),
        config,
    )
    assert winning.positioning == "premium"
    assert winning.base_price >= premium_initial.base_price
    assert winning.r_and_d_budget > premium_initial.r_and_d_budget


def test_attributes_gate_premium_and_discount_adaptation():
    config = load_market_config()
    policy = FirmPolicy()
    high = load_firms().firm("retailer_01")
    low = high.model_copy(update={"quality_level": 0.58, "reputation": 0.55})
    initial = policy.decide_annual(high, None, config)
    weak = _summary(profit=-1, price=initial.base_price, quality=0.58, share_change=-0.01)
    strong = _summary(profit=-1, price=initial.base_price, quality=0.88, share_change=-0.01)

    high_strategy = policy.decide_annual(high, strong, config)
    low_strategy = policy.decide_annual(low, weak, config)
    assert high_strategy.positioning == "premium"
    assert high_strategy.base_price > initial.base_price
    assert high_strategy.r_and_d_budget > low_strategy.r_and_d_budget
    assert low_strategy.positioning == "low_cost"
    assert low_strategy.base_price < initial.base_price


@pytest.fixture(scope="module")
def ten_year_results():
    return run_simulation(years=10, seed=0), run_simulation(years=10, seed=0)


def test_full_run_is_deterministic_and_strategies_stay_bounded(ten_year_results):
    first, second = ten_year_results
    assert first.yearly_summaries == second.yearly_summaries
    config = load_market_config()
    for reports in first.annual_reports:
        for firm_id, report in reports.items():
            band = config.stage_prices[first.network.firm(firm_id).stage]
            assert band.min <= report.average_sell_price <= band.max
            assert 0 <= report.average_quality <= config.rnd.quality_cap
            assert 0 <= report.capacity_utilization <= 1


def test_adaptation_preserves_market_health_and_diversity(ten_year_results):
    result, _ = ten_year_results
    cumulative = {
        firm.id: sum(year[firm.id].profit for year in result.yearly_summaries)
        for stage in result.network.stages for firm in stage.firms
    }
    profitable_archetypes = {
        firm.archetype for stage in result.network.stages for firm in stage.firms
        if cumulative[firm.id] > 0
    }
    final_retail = result.annual_reports[-1]
    prices = [final_retail[f.id].average_sell_price for f in result.network.firms_in("retailer")]
    final_cash = [item.cash for item in result.final_result.firm_results.values()]

    assert len(profitable_archetypes) >= 4
    # Earned reliability makes chronic under-fill economically visible; the
    # calibrated market still keeps at least 19 of 22 firms profitable.
    assert sum(value > 0 for value in cumulative.values()) >= 19
    assert max(prices) - min(prices) >= 1.0
    threshold = load_market_config().bankruptcy.cash_threshold
    # A firm can cross the threshold on its final active tick before cash is
    # frozen; exits still bound system downside close to that threshold.
    assert min(final_cash) > 1.5 * threshold
