import math
from types import SimpleNamespace

from market_sim.leasing import LeasingBook


class FakeRuntime:
    def __init__(self, cash, active=True, fixed_cost=0.0):
        self.cash = cash
        self.active = active
        self.fixed_cost = fixed_cost
        self.reasons = []

    def adjust_cash(self, delta, reason):
        self.cash += delta
        self.reasons.append(reason)


class FakeEnv:
    def __init__(self, runtimes):
        self.runtimes = runtimes


class FakeState:
    def __init__(self, year, events=None):
        self.year = year
        self.events = events if events is not None else []


class FakeTruck:
    def __init__(self, id, type, age, leased=False):
        self.id = id
        self.type = type
        self.age = age
        self.leased = leased


class FakeDealer:
    def __init__(self, id, cash, margin, rt=None, active=True):
        self.id = id
        self.cash = cash
        self.margin = margin
        self.rt = rt
        self.active = active
        self.taken_back_count = 0


class FakeTrucks:
    def __init__(self, dealers=None):
        self.types = {"t": SimpleNamespace(life_years=10)}
        self.dealers = {dealer.id: dealer for dealer in (dealers or [])}
        self.last_takeback_price = 0.0
        self.taken_back = []
        self.removed = []

    def _active_dealers(self):
        return [dealer for dealer in self.dealers.values() if dealer.active]

    def value(self, env, truck):
        return 100000.0

    def take_back_leased(self, env, state, truck, dealer_id):
        self.taken_back.append(dealer_id)
        truck.leased = False
        self.last_takeback_price = 40000.0
        self.dealers[dealer_id].taken_back_count += 1
        return True

    def remove_truck(self, firm_id, truck_id):
        self.removed.append((firm_id, truck_id))


class FakeBanking:
    """loan_offer returns ((bank, 0.04, 5), "") or (None, "x") when no bank loan."""

    def __init__(self, bank_loan=True):
        self.bank = SimpleNamespace(id="B1")
        self.bank_terms = (self.bank, 0.04, 5) if bank_loan else None
        self.bank_reason = "" if bank_loan else "x"
        self.receivables = {}
        self.income = 0.0
        self.loss = 0.0

    def loan_offer(self, firm_id, runtime, amount, purpose, policy_rate):
        return self.bank_terms, self.bank_reason

    def fund_lease(self, bank_id, amount):
        self.receivables[bank_id] = max(
            0.0, self.receivables.get(bank_id, 0.0) + amount
        )

    def book_lease_income(self, bank_id, amount):
        self.income += amount

    def book_lease_loss(self, bank_id, amount):
        self.loss += amount


class FakeRunner:
    def __init__(self, env):
        self.env = env


def make_system(cash=1_000_000.0, dealers=None, bank_loan=True):
    runtime = FakeRuntime(cash)
    env = FakeEnv({"F1": runtime})
    state = FakeState(1)
    truck = FakeTruck("T1", "t", age=0)
    trucks = FakeTrucks(dealers)
    banking = FakeBanking(bank_loan)
    book = LeasingBook(None, banking, trucks, 360, seed=1)
    return book, banking, trucks, env, state, runtime, truck


def make_offer(book, env, price=200000.0, risk=0.02):
    return book.offer(
        env,
        "F1",
        price,
        life_years=10,
        policy_rate=0.01,
        risk=risk,
    )


def test_rate_is_depreciation_plus_interest():
    book, banking, trucks, env, state, runtime, truck = make_system()
    offer = make_offer(book, env)

    assert offer.kind == "bank"
    assert math.isclose(offer.annual_rate, 0.04 + book.cfg.bank_margin)
    assert 4 <= offer.years <= 6
    financed = 200000.0 * 0.9
    expected = (
        (financed - offer.residual) / (offer.years * 12)
        + (financed + offer.residual) / 2 * offer.annual_rate / 12
    )
    assert math.isclose(offer.monthly_payment, expected)


def test_start_and_daily():
    book, banking, trucks, env, state, runtime, truck = make_system()
    offer = make_offer(book, env)
    initial_cash = runtime.cash
    contract = book.start(env, state, "F1", truck, None, offer)
    financed = 200000.0 * 0.9

    assert math.isclose(runtime.cash, initial_cash - offer.down_payment)
    assert math.isclose(banking.receivables["B1"], financed)
    assert truck.leased is True
    assert any(event["event"] == "lease_started" for event in state.events)

    cash_after_start = runtime.cash
    for _ in range(360):
        book.daily(env)

    assert math.isclose(
        runtime.cash, cash_after_start - 12 * contract["monthly"]
    )
    assert banking.income > 0
    assert banking.receivables["B1"] < financed


def test_default_bankruptcy():
    book, banking, trucks, env, state, runtime, truck = make_system()
    offer = make_offer(book, env)
    contract = book.start(env, state, "F1", truck, None, offer)
    outstanding = contract["outstanding"]
    runtime.active = False

    book.year_end(FakeRunner(env), state)

    expected_loss = max(0.0, outstanding - 0.7 * trucks.value(env, truck))
    assert ("F1", "T1") in trucks.removed
    assert any(event["event"] == "lease_default" for event in state.events)
    assert contract["status"] == "default"
    assert math.isclose(banking.loss, expected_loss)
    assert book.export()["history"][-1]["defaults"] == 1


def test_return_at_end():
    dealer = FakeDealer("D1", cash=100000.0, margin=0.1)
    book, banking, trucks, env, state, runtime, truck = make_system(
        cash=100.0, dealers=[dealer]
    )
    offer = make_offer(book, env)
    contract = book.start(env, state, "F1", truck, dealer, offer)
    state.year = contract["start_year"] + contract["years"]

    book.year_end(FakeRunner(env), state)

    assert trucks.taken_back == ["D1"]
    assert dealer.taken_back_count == 1
    event = next(
        event for event in state.events
        if event["event"] == "lease_ended"
    )
    assert "zurückgegeben" in event["details"]
    assert contract["status"] == "returned"
    assert truck.leased is False
    assert banking.receivables["B1"] == 0.0


def test_buy_at_residual():
    book, banking, trucks, env, state, runtime, truck = make_system()
    truck.age = 2
    offer = make_offer(book, env)
    contract = book.start(env, state, "F1", truck, None, offer)
    state.year = contract["start_year"] + contract["years"]

    book.year_end(FakeRunner(env), state)

    assert contract["status"] == "bought"
    event = next(
        event for event in state.events
        if event["event"] == "lease_ended"
    )
    assert "zum Restwert gekauft" in event["details"]


def test_dealer_self_lease():
    dealer = FakeDealer("D1", cash=50_000_000.0, margin=0.3)
    book, banking, trucks, env, state, runtime, truck = make_system(
        dealers=[dealer], bank_loan=False
    )
    offer = make_offer(book, env)

    assert offer.kind == "dealer"
    assert offer.lessor_id == dealer.id
    dealer_cash = dealer.cash
    receivables_before = dict(banking.receivables)

    book.start(env, state, "F1", truck, dealer, offer)

    financed = 200000.0 - offer.down_payment
    assert math.isclose(dealer.cash, dealer_cash - financed)
    assert banking.receivables == receivables_before
