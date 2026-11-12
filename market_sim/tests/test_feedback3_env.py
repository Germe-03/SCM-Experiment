"""Feedback 3 (Simulation): Rohstoffplan, Lagerplatz, Lieferbuch, Stornierung, Tochter-Regeln."""

from market_sim.config import MarketConfig, load_market_config
from market_sim.game.controller import GameController


def _producer(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    state = controller.new_game("hersteller", "T", category="beer")
    assert "error" not in state
    runner = controller.session.runner
    return controller, runner.env, controller.snapshot.firm_id


def _trader(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    state = controller.new_game("detailhaendler", "T")
    assert "error" not in state
    runner = controller.session.runner
    return controller, runner.env, controller.snapshot.firm_id


def test_storage_config_default():
    cfg = load_market_config()
    assert isinstance(cfg, MarketConfig)
    assert cfg.storage.start_days > 0 and cfg.storage.build_cost_per_bottle >= 0


def test_component_helpers_and_plan(tmp_path):
    controller, env, firm_id = _producer(tmp_path)
    need = env.component_need(firm_id, 20000)
    assert need and all(v > 0 for v in need.values())
    assert set(env.component_stock(firm_id)) == set(need) == set(env.component_prices(firm_id))
    assert all(p > 0 for p in env.component_prices(firm_id).values())
    before = sum(env.component_stock(firm_id).values())
    plan = env.component_need(firm_id, 100000)
    for _ in range(3):
        state = controller.end_round({}, {"component_plan": plan})
        assert "error" not in state
    assert sum(env.component_stock(firm_id).values()) > before


def test_storage_order_raises_capacity_and_clears(tmp_path):
    controller, env, firm_id = _producer(tmp_path)
    capacity = env.storage_capacity(firm_id)
    assert capacity > 0 and env.storage_used(firm_id) >= 0
    state = controller.end_round({}, {"storage_order": 50000})
    assert "error" not in state
    assert env.storage_capacity(firm_id) >= capacity + 50000
    assert env.player_choices[firm_id].storage_order is None


def test_delivery_book_and_cancel(tmp_path):
    controller, env, firm_id = _trader(tmp_path)
    for _ in range(4):
        assert "error" not in controller.end_round({}, {})
    book = env.delivery_book.get(firm_id, {})
    assert book
    row = next(iter(book.values()))
    assert set(row) == {"ordered", "delivered", "open"}
    assert sum(r["ordered"] for r in book.values()) > 0
    env.player_choices[firm_id].cancel_open_orders = True
    env._player_orders()
    assert env.player_choices[firm_id].cancel_open_orders is None
    runtime = env.runtimes[firm_id]
    assert runtime.on_order == sum(runtime.incoming_shipments)
    assert all(r["open"] == 0 for r in env.delivery_book[firm_id].values())
    for supplier in env.runtimes.values():
        assert firm_id not in supplier.backlog_by_downstream
        assert all(firm_id not in queue for queue in supplier.incoming_orders)


def test_daughter_no_credit_forces_never(tmp_path):
    controller, env, firm_id = _trader(tmp_path)
    other = next(fid for fid in env.runtimes if fid != firm_id)
    seen = []
    original = env.banking.loan_offer if env.banking is not None else None
    if original is None:
        return
    env.banking.loan_offer = lambda *a, **k: (seen.append(a[0]) or original(*a, **k))
    env.player_choices[firm_id].daughter_rules = {other: {"no_credit": True}}
    env.runtimes[other].cash = -1e9
    env.arrange_funding(other, 1000.0, "test")
    assert other in seen  # offer is computed, but mode "never" returns the cash rule only
    assert env.arrange_funding(other, 1000.0, "test") is False
