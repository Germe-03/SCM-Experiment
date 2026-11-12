from __future__ import annotations

import json

import pytest

from market_sim import financials
from market_sim.config import load_market_config
from market_sim.run import build_runner


@pytest.fixture(scope="module")
def simulation():
    config = load_market_config()
    config = config.model_copy(update={
        "simulation": config.simulation.model_copy(update={"years": 2, "days_per_year": 15})
    })
    runner, years = build_runner(2, 0, 15, config)
    result = runner.continue_run(runner.start(), 2)
    return runner, result


def test_annual_reports_for_all_active_firms(simulation):
    runner, _ = simulation

    assert 1 in runner.annual_reports
    assert 2 in runner.annual_reports
    for firm_id, runtime in runner.env.runtimes.items():
        if runtime.active:
            assert firm_id in runner.annual_reports[2]

    for year_reports in runner.annual_reports.values():
        for report in year_reports.values():
            assert {
                "year",
                "income_statement",
                "balance_sheet",
                "cash_flow",
                "ratios",
                "calculation",
            } <= report.keys()


def test_income_statement_consistency(simulation):
    runner, _ = simulation
    expected_keys = {
        "year", "revenue", "cogs", "gross_profit", "wages", "rent_fixed",
        "handling", "storage", "marketing", "research", "other_opex",
        "ebitda", "depreciation", "ebit", "interest", "ebt", "taxes",
        "net_income",
    }

    for year_reports in runner.annual_reports.values():
        for report in year_reports.values():
            income = report["income_statement"]
            assert set(income) == expected_keys
            assert income["gross_profit"] == pytest.approx(
                income["revenue"] - income["cogs"], abs=0.05
            )
            assert income["ebit"] == pytest.approx(
                income["ebitda"] - income["depreciation"], abs=0.05
            )
            assert income["ebt"] == pytest.approx(
                income["ebit"] - income["interest"], abs=0.05
            )
            assert income["net_income"] == pytest.approx(
                income["ebt"] - income["taxes"], abs=0.05
            )
            assert income["cogs"] >= 0
            assert income["revenue"] >= 0


def test_balance_sheet_balances(simulation):
    runner, _ = simulation

    for year_reports in runner.annual_reports.values():
        for report in year_reports.values():
            balance = report["balance_sheet"]
            assets = balance["assets"]
            asset_items = ("cash", "inventory", "trucks", "sites", "participations", "securities")
            assert assets["total"] == pytest.approx(
                sum(assets[key] for key in asset_items)
            )
            assert balance["total"] == pytest.approx(assets["total"], abs=0.05)
            assert balance["total"] == pytest.approx(
                balance["liabilities"]["total"] + balance["equity"], abs=0.05
            )
            assert all(assets[key] >= 0 for key in asset_items)


def test_cash_flow_reconciles(simulation):
    runner, _ = simulation

    for year_reports in runner.annual_reports.values():
        for report in year_reports.values():
            cash = report["cash_flow"]
            assert cash["change"] == pytest.approx(
                cash["operating"]
                + cash["investing"]
                + cash["financing"]
                + cash["dividends_received"]
                - cash["dividends_paid"],
                abs=0.05,
            )


def test_calculation_keys_and_break_even(simulation):
    runner, _ = simulation
    expected_keys = {
        "purchase_price", "procurement_costs", "landed_cost", "overhead",
        "full_cost", "sell_price", "profit", "margin_pct",
        "break_even_price", "bottles_per_day",
    }

    for year_reports in runner.annual_reports.values():
        for report in year_reports.values():
            calculation = report["calculation"]
            assert expected_keys <= calculation.keys()
            assert calculation["break_even_price"] == calculation["full_cost"]
            assert calculation["profit"] == pytest.approx(
                calculation["sell_price"] - calculation["full_cost"], abs=0.02
            )
            assert calculation["full_cost"] == pytest.approx(
                calculation["landed_cost"] + calculation["overhead"], abs=0.02
            )


def test_public_functions_match_stored(simulation):
    runner, _ = simulation
    firm_id = next(iter(runner.annual_reports[2]))
    stored = runner.annual_reports[2][firm_id]

    assert financials.income_statement(runner, firm_id, 2) == stored["income_statement"]
    assert financials.cash_flow(runner, firm_id, 2) == stored["cash_flow"]
    assert {
        "gross_margin", "ebit_margin", "equity_ratio", "liquidity", "roe"
    } <= financials.ratios(runner, firm_id).keys()
    assert "total" in financials.balance_sheet(runner, firm_id)["assets"]


def test_unknown_firm_is_robust(simulation):
    runner, _ = simulation

    assert isinstance(financials.income_statement(runner, "does_not_exist"), dict)
    assert isinstance(financials.balance_sheet(runner, "does_not_exist"), dict)
    assert isinstance(financials.calculation(runner, "does_not_exist"), dict)


def test_result_and_dashboard_payload(simulation):
    runner, result = simulation
    assert 1 in result.annual_financials
    assert 2 in result.annual_financials

    from market_sim.dashboard_data import build_dashboard_data

    config = load_market_config()
    config = config.model_copy(update={
        "simulation": config.simulation.model_copy(update={"years": 2, "days_per_year": 15})
    })
    data = build_dashboard_data(result, runner.network, config, 0)
    assert isinstance(data["financials"], dict)
    json.dumps(data["financials"])

    reports = next(iter(data["financials"].values()))
    assert len(reports) == 2
    assert [report["year"] for report in reports] == sorted(
        report["year"] for report in reports
    )
