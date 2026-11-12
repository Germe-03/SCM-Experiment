import json

from market_sim.game.controller import GameController

OWN_FIELDS = (
    "bank_id", "bank_name", "deposit_rate", "overdraft_rate", "loan_rate", "policy_rate",
    "cash", "credit_limit", "debt_total", "interest_paid_year", "interest_received_year",
    "next_payment_year",
)


def test_banks_view_has_own_block(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("detailhaendler", "T")
    data = controller.view("banks")
    own = data["own"]
    for key in OWN_FIELDS:
        assert key in own
    assert own["debt_total"] is not None
    assert own["next_payment_year"] is not None
    json.dumps(data)
