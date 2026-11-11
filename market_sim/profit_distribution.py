"""Gewinnverwendung nach Schweizer OR (alle Firmen gelten als AG; GmbH folgt via OR 801 denselben Regeln).

Reihenfolge jedes Jahr nach der Gewinnsteuer:
1. Verlustvortrag verrechnen (ein Jahresverlust erhoeht den Vortrag, keine Dividende).
2. Gesetzliche Gewinnreserve (OR 672): 5 % des verrechneten Jahresgewinns, bis die Reserve
   50 % des Aktienkapitals erreicht. Aktienkapital = Gruendungs-Cash der Firma (initial_cash),
   weil es kein eigenes Kapitalkonto gibt.
3. Dividende nur aus dem Bilanzgewinn (Jahresgewinn + Gewinnvortrag - Reservezuweisung), mal
   Ausschuettungsquote; gekuerzt, damit mindestens ``min_cash_months`` Monatskosten Cash bleiben.
4. Verrechnungssteuer 35 % der Bruttodividende an den Staat, 65 % an die Aktionaere.
   Tochterfirmen von Holdings zahlen die ganze Bruttodividende an die Holding (Beteiligungsabzug,
   vereinfacht: die VST wird nicht an den Staat gezahlt, sondern der Holding gutgeschrieben).
5. Der Rest ist Gewinnvortrag.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DistributionConfig:
    payout_ratio: float = 0.4
    legal_reserve_rate: float = 0.05
    legal_reserve_cap: float = 0.5
    withholding_tax: float = 0.35
    min_cash_months: float = 3.0
    enabled: bool = True


class ProfitDistribution:
    def __init__(self, cfg: DistributionConfig | None = None) -> None:
        self.cfg = cfg or DistributionConfig()
        self.accounts: dict[str, dict[str, float]] = {}
        self.history: list[dict] = []

    def distribute(self, year, firm_id, runtime, profit_after_tax, share_capital, monthly_cost,
                   parent_runtime=None, payout_ratio=None) -> dict:
        cfg = self.cfg
        acc = self.accounts.setdefault(
            firm_id, {"legal_reserve": 0.0, "retained": 0.0, "loss_carryforward": 0.0})
        row = {"year": year, "firm": firm_id, "profit": profit_after_tax, "loss_offset": 0.0,
               "legal_reserve_add": 0.0, "dividend": 0.0, "withholding_tax": 0.0,
               "net_dividend": 0.0, "retained": acc["retained"],
               "loss_carryforward": acc["loss_carryforward"]}
        if not cfg.enabled:
            self.history.append(row)
            return row
        if profit_after_tax <= 0:
            acc["loss_carryforward"] += -profit_after_tax
        else:
            offset = min(acc["loss_carryforward"], profit_after_tax)
            acc["loss_carryforward"] -= offset
            profit = profit_after_tax - offset
            room = max(0.0, cfg.legal_reserve_cap * max(0.0, share_capital) - acc["legal_reserve"])
            add = min(cfg.legal_reserve_rate * profit, room)
            acc["legal_reserve"] += add
            balance = max(0.0, profit + acc["retained"] - add)
            ratio = cfg.payout_ratio if payout_ratio is None else max(0.0, min(1.0, payout_ratio))
            dividend = ratio * balance
            spare = runtime.cash - cfg.min_cash_months * max(0.0, monthly_cost)
            dividend = max(0.0, min(dividend, spare))
            vst = dividend * cfg.withholding_tax
            net = dividend - vst
            if dividend > 0:
                if parent_runtime is not None:
                    runtime.adjust_cash(-dividend, "dividende:holding")
                    parent_runtime.adjust_cash(dividend, "dividende:holding")
                else:
                    runtime.adjust_cash(-vst, "staat:Verrechnungssteuer")
                    runtime.adjust_cash(-net, "dividende:aktionaere")
            acc["retained"] = balance - dividend
            row.update(loss_offset=offset, legal_reserve_add=add, dividend=dividend,
                       withholding_tax=vst, net_dividend=net)
        row["retained"] = acc["retained"]
        row["loss_carryforward"] = acc["loss_carryforward"]
        self.history.append(row)
        return row

    def export(self) -> dict:
        return {"rows": self.history, "accounts": self.accounts}
