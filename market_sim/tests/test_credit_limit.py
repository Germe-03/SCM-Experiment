"""Hard credit lines cover purchases, shared bank capacity and optional spending."""

from types import SimpleNamespace

import pytest

from market_sim.banking import BankingSystem
from market_sim.config import BankConfig, BankingConfig, load_market_config
from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms
from market_sim.run import build_runner


def bank_case(cash=-100, equity=10, second=False):
    firms = {"a": SimpleNamespace(initial_cash=1000, cash=cash, credit_limit=1000,
                                  last_year_revenue=0, active=True)}
    system = BankingSystem(BankingConfig(enabled=True, second_account_enabled=second), 1, firms)
    system.accounts["a"] = {"B1": 1.0}
    system.banks["B1"].equity = equity
    return system, firms


def budget(system, firms, amount=100, year=1):
    return system.spending_limit("a", firms, {f: r.cash for f, r in firms.items()}, amount, year, 1)


def test_undercapitalized_bank_keeps_debt_but_grants_no_new_credit():
    system, firms = bank_case(equity=9)
    assert budget(system, firms) == 0
    assert firms["a"].cash == -100
    assert system.banks["B1"].loans == 100
    assert "100.00" in system.credit_events[0]["details"]
    firms["a"].cash = -150  # wages and interest can create arrears
    assert budget(system, firms) == 0
    assert firms["a"].cash == -150


def test_two_purchases_share_one_bank_capacity():
    system, firms = bank_case(cash=0, equity=10)
    firms["b"] = SimpleNamespace(initial_cash=1000, cash=0, credit_limit=1000, active=True)
    system.accounts["b"] = {"B1": 1.0}
    assert budget(system, firms, 80) == 100
    firms["a"].cash -= 80
    assert system.spending_limit("b", firms, {f: r.cash for f, r in firms.items()}, 80, 1, 1) == 20
    firms["b"].cash -= 20
    assert budget(system, firms) == 0


def test_rejection_once_per_firm_year_and_report_reset():
    system, firms = bank_case(equity=0)
    for _ in range(5):
        budget(system, firms)
    assert len(system.credit_events) == 1
    assert system.banks["B1"].credit_rejections == 1
    events = []
    reports = system.year_end(firms, BankConfig(), 1, 1, 365, events)
    assert sum(r.credit_rejections for r in reports) == 1
    budget(system, firms, year=2)
    assert system.banks["B1"].credit_rejections == 1
    assert len(events) == 1


@pytest.mark.parametrize("existing", [False, True])
def test_switch_to_second_bank_including_debt_transfer(existing):
    system, firms = bank_case(equity=0, second=True)
    if existing:
        system.accounts["a"] = {"B1": 0.7, "B2": 0.3}
    system.banks["B2"].equity = 30
    assert budget(system, firms) == 200
    assert system.primary_bank("a").id == "B2"
    assert len(system.accounts["a"]) == 2
    assert sum(system.accounts["a"].values()) == pytest.approx(1)
    assert system.banks["B1"].loans == 0
    assert system.banks["B2"].loans == 100
    assert sum(b.credit_rejections for b in system.banks.values()) == 1


def test_second_bank_cannot_ignore_transferred_debt_or_account_limit():
    system, firms = bank_case(equity=0, second=True)
    system.accounts["a"] = {"B1": 0.5, "B2": 0.5}
    system.banks["B2"].equity = 5
    assert budget(system, firms) == 0
    assert system.primary_bank("a").id == "B1"
    system.accounts["a"] = {"B1": 1.0}
    system.cfg.max_accounts = 1
    assert budget(system, firms) == 0


def market(enabled=True, categories=False):
    cfg = load_market_config()
    cfg.banking.enabled = enabled
    # These tests cover the strict credit crunch that also stops purchases.
    cfg.banking.block_purchases = True
    cfg.categories.enabled = categories
    env = MarketEnvironment(load_firms(), config=cfg, initial_inventory=20)
    env.reset()
    return env


@pytest.mark.parametrize("enabled", [True, False])
def test_firm_at_line_orders_and_produces_only_when_disabled(enabled):
    env = market(enabled)
    for rt in env.runtimes.values():
        rt.credit_limit = 100
        rt.adjust_cash(-100 - rt.cash)
    _, info = env.step(0, {fid: 5 for fid in env.runtimes})
    assert any(sum(a.values()) for a in info["split_orders"].values()) is (not enabled)
    factories = env.network.firms_in("factory")
    assert any(env.runtimes[f.id].purchase_cost > 0 for f in factories) is (not enabled)
    # Obligatory costs continue and may breach the line.
    assert all(rt.cash < -rt.credit_limit for rt in env.runtimes.values())


@pytest.mark.parametrize("categories", [False, True])
def test_delivery_caps_money_stock_and_pipeline_together(categories):
    env = market(categories=categories)
    customer = env.network.firms_in("retailer")[0]
    supplier = env.supplier_candidates(customer.id)[0]
    buyer, seller = env.runtimes[customer.id], env.runtimes[supplier.id]
    for rt in env.runtimes.values():
        rt.backlog_by_downstream.clear()
        rt.backlog = 0
        rt.incoming_orders = [{} for _ in rt.incoming_orders]
    price = env._trade_value(1, supplier.sell_price)
    buyer.credit_limit = price * 2.5
    buyer.adjust_cash(-buyer.cash)
    seller.backlog_by_downstream = {customer.id: 10}
    seller.backlog = buyer.on_order = 10
    before_stock = sum(seller.stock.values())
    _, info = env.step(0, {})
    shipped = info["shipments"][supplier.id][customer.id]
    assert 0 <= buyer.purchase_cost <= buyer.credit_limit
    assert shipped < 10
    assert seller.revenue == pytest.approx(buyer.purchase_cost)
    assert before_stock - sum(seller.stock.values()) == shipped
    assert buyer.on_order == shipped
    assert buyer.incoming_shipments[-1] == shipped
    assert customer.id not in seller.backlog_by_downstream


def test_intraday_costs_consume_budget_before_cash_recalculation():
    env = market()
    fid = next(iter(env.runtimes))
    rt = env.runtimes[fid]
    rt.credit_limit = 100
    rt.adjust_cash(-rt.cash)
    env._credit_profit_marks = {f: r.profit for f, r in env.runtimes.items()}
    assert env.can_spend(fid, 80)
    rt.pay("supplier", 80)
    assert not env.can_spend(fid, 21)
    assert env.can_spend(fid, 20)


def test_optional_investment_and_marketing_stop_at_line():
    runner, _ = build_runner(1, 1, 3)
    state = runner.start()
    env = runner.env
    firm = runner._firms()[0]
    rt = env.runtimes[firm.id]
    rt.adjust_cash(-rt.credit_limit - rt.cash)
    env.geography._start(env, firm, "expand", 5, 10, 3, state)
    assert not env.geography.projects
    env.marketing.daily_budget = {firm.id: 10}
    env.marketing.daily(env)
    assert rt.marketing_cost == 0
    assert not env.can_spend(firm.id, 0)


def test_rejections_in_system_kpis_equal_bank_reports_and_events():
    runner, _ = build_runner(2, 1, 3)
    state = runner.start()
    for rt in runner.env.runtimes.values():
        rt.adjust_cash(-rt.credit_limit - rt.cash)
    result = runner.continue_run(state, 2)
    for kpi in result.system_kpis:
        reports = [r for r in result.bank_history if r.year == kpi.year]
        events = [e for e in result.events if e["year"] == kpi.year and e["event"] == "credit_rejected"]
        assert kpi.credit_rejections == sum(r.credit_rejections for r in reports) == len(events)
        assert len({e["firm"] for e in events}) == len(events)
    assert result.system_kpis[0].credit_rejections > 0
