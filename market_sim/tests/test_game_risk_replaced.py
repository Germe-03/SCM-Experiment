from types import SimpleNamespace

from market_sim.couriers import CourierMarket
from market_sim.game.player import PlayerPolicy, PlayerSettings
from market_sim.config import MarketConfig


def _runner(choice):
    strat = SimpleNamespace(risk_tolerance=0.9)
    return SimpleNamespace(player_choices={"f": choice} if choice is not None else {},
                           strategies={"f": strat})


def test_courier_risk_from_preference():
    firm = SimpleNamespace(id="f")
    risk = CourierMarket.risk
    assert risk(_runner(SimpleNamespace(courier_preference="cheap")), firm) == 1.0
    assert risk(_runner(SimpleNamespace(courier_preference="reliable")), firm) == 0.0
    assert risk(_runner(SimpleNamespace(courier_preference=None)), firm) == 0.5
    assert risk(_runner(None), firm) == 0.9


def test_player_policy_ignores_risk_setting():
    from market_sim.models import Firm  # noqa: F401
    import inspect
    src = inspect.getsource(PlayerPolicy.decide_annual)
    assert "risk_tolerance=0.5" in src
