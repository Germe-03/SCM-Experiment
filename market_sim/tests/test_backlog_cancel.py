"""Stale open orders at a slow supplier are cancelled and can be re-placed."""

from market_sim.run import build_runner


def _supplier_with_backlog(max_days):
    runner, _ = build_runner()
    runner.config.policy.max_backlog_days = max_days
    runner.start()
    env = runner.env
    supplier = env.runtimes["factory_01"]
    supplier.backlog_by_downstream = {"distributor_01": 3000, "distributor_02": 1000}
    supplier.backlog = 4000
    env.runtimes["distributor_01"].on_order = 3000
    env.runtimes["distributor_02"].on_order = 1000
    return env, supplier


def test_backlog_beyond_limit_is_cancelled_proportionally():
    env, supplier = _supplier_with_backlog(10)
    limit = 10 * env._effective_capacity("factory_01")
    env._cancel_stale_backlog("factory_01", market_mode=True)
    assert supplier.backlog == limit
    assert sum(supplier.backlog_by_downstream.values()) == limit
    kept_01 = supplier.backlog_by_downstream["distributor_01"]
    assert env.runtimes["distributor_01"].on_order == kept_01
    assert kept_01 > supplier.backlog_by_downstream["distributor_02"]
    assert env.cancelled_units == 4000 - limit


def test_disabled_cancellation_keeps_orders():
    env, supplier = _supplier_with_backlog(None)
    env._cancel_stale_backlog("factory_01", market_mode=True)
    assert supplier.backlog == 4000
    assert env.runtimes["distributor_01"].on_order == 3000
