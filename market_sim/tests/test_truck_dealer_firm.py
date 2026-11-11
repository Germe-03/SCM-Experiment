"""Phase 56: truck dealers are firms of their own stage outside the beverage chain."""

from market_sim.dashboard_data import build_dashboard_data
from market_sim.models import EXTRA_STAGES, STAGES
from market_sim.run import build_runner
from market_sim.trucks import Truck


def make(years=3, days=10):
    runner, _ = build_runner(years=years, days_per_year=days)
    state = runner.start()
    return runner, state, runner.env.geography.trucks


def test_dealer_is_a_firm_but_not_part_of_the_chain():
    runner, state, trucks = make()
    dealer = next(iter(trucks.dealers.values()))
    firm = runner.network.firm(dealer.id)
    assert firm.stage == "truck_dealer" and "truck_dealer" in EXTRA_STAGES and "truck_dealer" not in STAGES
    assert dealer.rt is runner.env.runtimes[dealer.id] and dealer.rt.active
    assert firm.id not in {f.id for f in runner._firms()}
    assert firm.id in {f.id for f in runner._reported_firms()}
    # No supplier choice, no customer role: nobody lists the dealer as a candidate.
    for chain_firm in runner._firms():
        if chain_firm.stage != "factory":
            assert firm.id not in {c.id for c in runner.env.supplier_candidates(chain_firm.id)}
    assert firm.id not in state.daily_series or "cash" in state.daily_series[firm.id]


def test_dealer_gets_yearly_accounts_reports_and_sales_arrive_next_day():
    runner, state, trucks = make()
    dealer = next(iter(trucks.dealers.values()))
    runner.run_year(state)
    runner.run_year(state)
    report = state.annual_reports[-1][dealer.id]
    summary = state.summaries[-1][dealer.id]
    # Tax, dividend and stock bookings follow the summary, so the account may differ from it.
    assert report.firm_id == dealer.id and summary.cash > 0 and dealer.rt.cash > 0
    assert len(state.financial_breakdown[dealer.id]) == state.year
    assert len(state.daily_series[dealer.id]["cash"]) == state.global_day
    # A sale made at the year end reaches the firm's revenue on the next day.
    before = dealer.rt.revenue
    dealer.stock_new["mittel"].append(Truck(id="t", type="mittel", owner=dealer.id, cost_basis=100.0))
    dealer.sell_stock(500.0, 100.0)
    assert dealer.rt.revenue == before
    runner.run_year(state)
    assert dealer.rt.revenue >= before + 500.0


def test_dashboard_lists_dealer_with_stage_label():
    runner, state, trucks = make(years=2)
    runner.continue_run(state, 2)
    result = runner.result(state)
    data = build_dashboard_data(result, runner.network, runner.config, 0)
    dealer_id = next(iter(trucks.dealers))
    assert data["firms"][dealer_id]["stage"] == "truck_dealer"
    assert len(data["firms"][dealer_id]["yearly"]) == 2
    assert "active_firms_truck_dealer" in data["system"][-1]


def test_bankrupt_dealer_leaves_and_loses_its_stock():
    runner, state, trucks = make()
    runner.run_year(state)
    dealer = next(iter(trucks.dealers.values()))
    assert dealer.stock_total() > 0
    runner.env.close_firm(dealer.id)
    dealer.rt.active = False
    assert dealer not in trucks._active_dealers()
    assert dealer.stock_total() == 0


def test_takeover_moves_the_stock_to_the_buyer():
    runner, state, trucks = make()
    runner.run_year(state)
    first = next(iter(trucks.dealers.values()))
    second = trucks._new_dealer(2, 1e6)
    trucks.register_dealer(runner, state, second)
    stock = first.stock_total()
    assert stock > 0
    trucks.merge_dealers(first.id, second.id)
    assert first.stock_total() == 0 and second.stock_total() == stock
    assert not first.active


def test_dealer_pays_profit_tax_and_is_listed_on_the_stock_market():
    runner, state, trucks = make()
    dealer = next(iter(trucks.dealers.values()))
    runner.config.stock_market.tradable_from_year = 1
    runner.run_year(state)
    runner.run_year(state)
    assert dealer.id in runner.stock_market.listed
    assert any(k.startswith("staat:") for k in dealer.rt.cash_flows)
