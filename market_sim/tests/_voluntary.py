"""Helper for takeover tests: make buyers see a clear gain."""

import dataclasses


def boost_profit(state, profit=1e12, only=None):
    state.summaries[-1] = {k: dataclasses.replace(v, profit=profit) if only is None or k in only else v
                           for k, v in state.summaries[-1].items()}
