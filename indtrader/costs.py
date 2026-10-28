"""Indian equity transaction costs (statutory charges + broker fees).

Defaults follow a typical discount broker (Zerodha-style) schedule for NSE cash
equity. Rates change: verify against your broker's charges page and override
in config.yaml (`costs:` section).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostModel:
    # Brokerage
    delivery_brokerage_pct: float = 0.0        # CNC: zero at most discount brokers
    intraday_brokerage_pct: float = 0.0003     # MIS: 0.03% ...
    intraday_brokerage_cap: float = 20.0       # ... or Rs 20 per order, whichever lower
    # Securities Transaction Tax
    stt_delivery_pct: float = 0.001            # 0.1% on buy and sell
    stt_intraday_sell_pct: float = 0.00025     # 0.025% on sell side only
    # Exchange transaction charges (NSE): Rs 307/crore incl. IPFT from 1 Mar 2026 (NSE/FA/73061)
    exchange_txn_pct: float = 0.0000307
    # SEBI turnover fee: Rs 10 per crore
    sebi_pct: float = 0.000001
    # Stamp duty (buy side only)
    stamp_delivery_pct: float = 0.00015
    stamp_intraday_pct: float = 0.00003
    gst_pct: float = 0.18                      # on brokerage + exchange + SEBI fees
    dp_charge_per_sell: float = 15.34          # depository charge per scrip, delivery sells
    # Slippage assumption used by the paper broker and backtests
    slippage_pct: float = 0.0005

    @classmethod
    def from_dict(cls, data: dict | None) -> CostModel:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in (data or {}).items() if k in known})

    def charges(self, side: str, quantity: int, price: float, product: str = "CNC") -> float:
        """Total charges in rupees for one executed order."""
        turnover = abs(quantity) * price
        if turnover == 0:
            return 0.0
        buy = side.upper() == "BUY"
        intraday = product.upper() == "MIS"

        if intraday:
            brokerage = min(turnover * self.intraday_brokerage_pct, self.intraday_brokerage_cap)
            stt = 0.0 if buy else turnover * self.stt_intraday_sell_pct
            stamp = turnover * self.stamp_intraday_pct if buy else 0.0
            dp = 0.0
        else:
            brokerage = turnover * self.delivery_brokerage_pct
            stt = turnover * self.stt_delivery_pct
            stamp = turnover * self.stamp_delivery_pct if buy else 0.0
            dp = 0.0 if buy else self.dp_charge_per_sell

        exchange = turnover * self.exchange_txn_pct
        sebi = turnover * self.sebi_pct
        gst = (brokerage + exchange + sebi) * self.gst_pct
        return round(brokerage + stt + exchange + sebi + stamp + gst + dp, 2)

    def round_trip_pct(self, price: float, quantity: int, product: str = "CNC") -> float:
        """Cost of buying then selling, as a fraction of the buy turnover."""
        total = self.charges("BUY", quantity, price, product) + self.charges("SELL", quantity, price, product)
        return total / (quantity * price)

