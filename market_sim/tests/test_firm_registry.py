"""Firms can enter a running market and remain checkpoint/dashboard safe."""

from market_sim.checkpoint import load_checkpoint, save_checkpoint
from market_sim.config import load_market_config
from market_sim.dashboard_data import build_dashboard_data
from market_sim.models import load_firms
from market_sim.run import build_runner, write_outputs


def _entrant(runner):
    return runner.network.firm("retailer_01").model_copy(update={
        "id": "retailer_new",
        "name": "Neue Markt AG",
        "suppliers": [],
        "inventory": 100,
        "cash": 5_000_000,
    })


def test_add_firm_after_year_one_trades_and_appears_everywhere(tmp_path) -> None:
    config = load_market_config()
    runner, _ = build_runner(years=3, days_per_year=40, seed=0, config=config)
    state = runner.start()
    runner.continue_run(state, 1)
    runner.add_firm(_entrant(runner), state)

    checkpoint = save_checkpoint(runner, state, tmp_path / "entrant.pkl")
    resumed_runner, resumed_state = load_checkpoint(checkpoint)
    result = resumed_runner.continue_run(resumed_state, 3)

    assert result.annual_reports[0]["retailer_new"].revenue == 0
    assert result.annual_reports[1]["retailer_new"].revenue > 0
    assert result.financial_breakdown["retailer_new"][1]["purchase_cost"] > 0
    assert result.final_result.firm_results["retailer_new"].revenue > 0
    assert len(result.daily_series["retailer_new"]["cash"]) == result.days_total

    data = build_dashboard_data(result, result.network, resumed_runner.config, 0)
    assert "retailer_new" in data["firms"]
    assert any(row["firm_id"] == "retailer_new" for row in data["ranking"])

    paths = write_outputs(result, tmp_path / "outputs")
    assert all(path.exists() for path in paths)
    assert "retailer_new" in (tmp_path / "outputs" / "annual_reports.csv").read_text()

