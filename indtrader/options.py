"""Nifty weekly options paper desk.

Three paper accounts on NSE's live option chain:

- main     iron condor (sell ~1 SD call and put, buy wings further out), sized to one lot, subject to the
           analyst's event gate (trade / skip / widen) written by `indtrader options-gate`
- control  the same iron condor with no gate: the rules alone
- lotto    the Rs 1,000 test: buys one cheap out-of-the-money option per expiry in the direction of the
           Nifty's 5-day trend (the gate can skip it)

Fills are at the bid (sells) and ask (buys) of the live chain, with Indian F&O charges. Every structure has
its maximum loss fixed at entry. Exits: take profit at 50% of the credit, stop when the loss equals the
credit, and always close by 15:15 on the last trading day before expiry. The lotto leg sells at 2x its
premium or at that same time.
"""

from __future__ import annotations

import csv
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from indtrader.market import NSE_HOLIDAYS, now_ist

log = logging.getLogger(__name__)

LOT = 65                     # Nifty lot size since the January 2026 contracts
STRIKE_STEP = 50
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept": "application/json,text/plain,*/*", "Referer": "https://www.nseindia.com/option-chain"}


# ---------------------------------------------------------------- costs
@dataclass
class OptionCosts:
    brokerage_per_order: float = 20.0
    stt_sell_pct: float = 0.0015          # 0.15% of premium on sales (from 1 April 2026)
    exchange_pct: float = 0.0003553       # NSE options transaction charge on premium
    sebi_pct: float = 0.000001            # Rs 10 per crore
    stamp_buy_pct: float = 0.00003        # 0.003% on buys
    gst_pct: float = 0.18

    def charges(self, side: str, premium: float, qty: int) -> float:
        """Charges for one executed leg (one order)."""
        value = premium * qty
        if value <= 0:
            return 0.0
        brokerage = self.brokerage_per_order
        exchange, sebi = value * self.exchange_pct, value * self.sebi_pct
        stt = value * self.stt_sell_pct if side == "SELL" else 0.0
        stamp = value * self.stamp_buy_pct if side == "BUY" else 0.0
        return round(brokerage + exchange + sebi + stt + stamp + (brokerage + exchange + sebi) * self.gst_pct, 2)


# ---------------------------------------------------------------- data
@dataclass
class Quote:
    bid: float
    ask: float
    iv: float | None = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2 if self.bid and self.ask else self.bid or self.ask


@dataclass
class Chain:
    expiry: date
    spot: float
    time: str
    calls: dict[int, Quote] = field(default_factory=dict)
    puts: dict[int, Quote] = field(default_factory=dict)

    def quote(self, kind: str, strike: int) -> Quote | None:
        return (self.calls if kind == "CE" else self.puts).get(strike)

    def atm_iv(self) -> float:
        k = min(self.calls, key=lambda s: abs(s - self.spot))
        ivs = [q.iv for q in (self.calls.get(k), self.puts.get(k)) if q and q.iv]
        return sum(ivs) / len(ivs) / 100 if ivs else 0.15


class NSEOptions:
    """NSE's public option chain (v3 API). Needs a browser-like session cookie."""

    def __init__(self, symbol: str = "NIFTY"):
        self.symbol = symbol
        self.s = requests.Session()
        self._primed = False

    def _get(self, url: str) -> dict:
        if not self._primed:
            self.s.get("https://www.nseindia.com/option-chain", headers=_HEADERS, timeout=20)
            self._primed = True
        r = self.s.get(url, headers=_HEADERS, timeout=20)
        if r.status_code in (401, 403):   # cookie expired: prime again once
            self._primed = False
            self.s.get("https://www.nseindia.com/option-chain", headers=_HEADERS, timeout=20)
            self._primed = True
            r = self.s.get(url, headers=_HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()

    def expiries(self) -> list[date]:
        j = self._get(f"https://www.nseindia.com/api/option-chain-contract-info?symbol={self.symbol}")
        return sorted(datetime.strptime(d, "%d-%b-%Y").date() for d in j["expiryDates"])

    def chain(self, expiry: date) -> Chain:
        exp = expiry.strftime("%d-%b-%Y")
        rec = self._get(f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={self.symbol}&expiry={exp}")["records"]
        ch = Chain(expiry, float(rec["underlyingValue"]), rec.get("timestamp", ""))
        for row in rec["data"]:
            k = int(row["strikePrice"])
            for kind, book in (("CE", ch.calls), ("PE", ch.puts)):
                leg = row.get(kind)
                if leg and (leg.get("buyPrice1") or leg.get("sellPrice1")):
                    book[k] = Quote(float(leg.get("buyPrice1") or 0), float(leg.get("sellPrice1") or 0),
                                    float(leg.get("impliedVolatility") or 0) or None)
        return ch

    def vix(self) -> float | None:
        try:
            for d in self._get("https://www.nseindia.com/api/allIndices")["data"]:
                if d["index"] == "INDIA VIX":
                    return float(d["last"])
        except Exception as exc:
            log.warning("India VIX unavailable: %s", exc)
        return None


# ---------------------------------------------------------------- calendar
def trading_days_between(a: date, b: date) -> int:
    """Trading days strictly after a, up to and including b."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in NSE_HOLIDAYS:
            n += 1
    return n


def last_trading_day_before(expiry: date) -> date:
    d = expiry - timedelta(days=1)
    while d.weekday() >= 5 or d in NSE_HOLIDAYS:
        d -= timedelta(days=1)
    return d


# ---------------------------------------------------------------- structures
@dataclass
class Leg:
    kind: str          # CE / PE
    strike: int
    side: str          # SELL (short) or BUY (long) at entry
    qty: int
    entry: float       # premium per unit at entry

    def close_price(self, chain: Chain) -> float | None:
        """What closing it costs (shorts bought back at the ask) or pays (longs sold at the bid)."""
        q = chain.quote(self.kind, self.strike)
        if q is None:
            return None
        return q.ask if self.side == "SELL" else q.bid


def plan_iron_condor(chain: Chain, today: date, sd_mult: float = 1.0, wing: int = 200, lots: int = 1) -> list[Leg] | None:
    """Short strikes about `sd_mult` standard deviations out (from the at-the-money IV), wings `wing` points beyond."""
    days = max((chain.expiry - today).days, 1)
    sd = chain.spot * chain.atm_iv() * math.sqrt(days / 365)
    sc = int(math.ceil((chain.spot + sd_mult * sd) / STRIKE_STEP) * STRIKE_STEP)
    sp = int(math.floor((chain.spot - sd_mult * sd) / STRIKE_STEP) * STRIKE_STEP)
    lc, lp = sc + wing, sp - wing
    q = {k: chain.quote(*k) for k in (("CE", sc), ("PE", sp), ("CE", lc), ("PE", lp))}
    if any(v is None or not v.bid or not v.ask for v in q.values()):
        return None
    qty = LOT * lots
    legs = [Leg("CE", sc, "SELL", qty, q[("CE", sc)].bid), Leg("PE", sp, "SELL", qty, q[("PE", sp)].bid),
            Leg("CE", lc, "BUY", qty, q[("CE", lc)].ask), Leg("PE", lp, "BUY", qty, q[("PE", lp)].ask)]
    credit = sum(lg.entry if lg.side == "SELL" else -lg.entry for lg in legs)
    return legs if credit > 0 else None


def plan_lotto(chain: Chain, direction: str, budget: float) -> list[Leg] | None:
    """The nearest out-of-the-money option in `direction` (CE up / PE down) whose lot fits the budget."""
    kind = "CE" if direction == "up" else "PE"
    book = chain.calls if kind == "CE" else chain.puts
    strikes = sorted(k for k in book if (k > chain.spot if kind == "CE" else k < chain.spot))
    if kind == "PE":
        strikes.reverse()
    for k in strikes:   # nearest first: the cheapest that still fits
        ask = book[k].ask
        if ask and ask * LOT <= budget:
            return [Leg(kind, k, "BUY", LOT, ask)]
    return None


# ---------------------------------------------------------------- the book
class OptionsBook:
    def __init__(self, path: Path, capital: float, costs: OptionCosts | None = None):
        self.path, self.costs = path, costs or OptionCosts()
        self.data = json.loads(path.read_text()) if path.exists() else {
            "capital": capital, "cash": capital, "open": None, "closed": [], "realized": 0.0}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        tmp.replace(self.path)

    @property
    def open(self) -> dict | None:
        return self.data["open"]

    def enter(self, name: str, legs: list[Leg], expiry: date, note: str, max_loss: float) -> dict:
        charges = sum(self.costs.charges(lg.side, lg.entry, lg.qty) for lg in legs)
        credit = sum((lg.entry if lg.side == "SELL" else -lg.entry) * lg.qty for lg in legs)
        self.data["cash"] += credit - charges
        self.data["open"] = {"name": name, "expiry": expiry.isoformat(), "opened": now_ist().isoformat(timespec="seconds"),
                             "legs": [lg.__dict__ for lg in legs], "credit": round(credit, 2),
                             "entry_charges": round(charges, 2), "max_loss": round(max_loss, 2), "note": note}
        self.save()
        return self.data["open"]

    def mark(self, chain: Chain) -> dict | None:
        """Cost to close now (positive = we pay), unrealized P&L before exit charges."""
        pos = self.open
        if not pos:
            return None
        legs = [Leg(**lg) for lg in pos["legs"]]
        prices = [lg.close_price(chain) for lg in legs]
        if any(p is None for p in prices):
            return None
        close_value = sum((p if lg.side == "SELL" else -p) * lg.qty for lg, p in zip(legs, prices, strict=True))
        return {"close_value": round(close_value, 2), "pnl": round(pos["credit"] - close_value - pos["entry_charges"], 2),
                "prices": prices}

    def exit(self, chain: Chain, reason: str) -> dict | None:
        pos, m = self.open, self.mark(chain)
        if not pos or not m:
            return None
        legs = [Leg(**lg) for lg in pos["legs"]]
        exit_side = {"SELL": "BUY", "BUY": "SELL"}
        charges = sum(self.costs.charges(exit_side[lg.side], p, lg.qty) for lg, p in zip(legs, m["prices"], strict=True) if p > 0)
        pnl = round(pos["credit"] - m["close_value"] - pos["entry_charges"] - charges, 2)
        self.data["cash"] += -m["close_value"] - charges
        self.data["realized"] = round(self.data["realized"] + pnl, 2)
        closed = {**pos, "closed": now_ist().isoformat(timespec="seconds"), "exit_prices": m["prices"],
                  "exit_charges": round(charges, 2), "pnl": pnl, "reason": reason}
        self.data["closed"].append(closed)
        self.data["open"] = None
        self.save()
        return closed

    def equity(self, chain: Chain | None) -> float:
        m = self.mark(chain) if chain and self.open else None
        return round(self.data["cash"] - (m["close_value"] if m else 0.0), 2)


def exit_reason(book: OptionsBook, chain: Chain, now: datetime) -> str | None:
    pos = book.open
    m = book.mark(chain)
    if not pos or not m:
        return None
    expiry = date.fromisoformat(pos["expiry"])
    last_day = last_trading_day_before(expiry)
    if now.date() > last_day or (now.date() == last_day and (now.hour, now.minute) >= (15, 15)):
        return f"time exit before expiry {expiry}"
    credit = pos["credit"]
    if pos["name"] == "lotto":
        value = -m["close_value"]          # what selling the bought option pays
        cost = -credit                     # what it cost
        return f"target: worth {value:.0f} >= 2x cost {cost:.0f}" if value >= 2 * cost else None
    if m["close_value"] <= 0.5 * credit:
        return f"take profit: close cost {m['close_value']:.0f} <= 50% of credit {credit:.0f}"
    if m["close_value"] >= 2 * credit:
        return f"stop: close cost {m['close_value']:.0f} >= 2x credit {credit:.0f} (loss = credit)"
    return None


# ---------------------------------------------------------------- desk
ARMS = {"main": 100000.0, "control": 100000.0, "lotto": 1000.0}


class OptionsDesk:
    def __init__(self, root: Path, nse: NSEOptions | None = None):
        self.root = root
        self.nse = nse or NSEOptions()
        self.books = {a: OptionsBook(root / f"{a}.json", c) for a, c in ARMS.items()}
        self.journal = root / "trades.csv"
        self.gates = root / "gates"

    def gate(self, today: date) -> dict:
        f = self.gates / f"{today.isoformat()}.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def set_gate(self, today: date, action: str, direction: str, note: str) -> Path:
        self.gates.mkdir(parents=True, exist_ok=True)
        f = self.gates / f"{today.isoformat()}.json"
        f.write_text(json.dumps({"date": today.isoformat(), "action": action, "lotto_direction": direction,
                                 "note": note, "time": now_ist().isoformat(timespec="seconds")}, indent=1))
        return f

    def _log(self, arm: str, event: str, detail: dict) -> None:
        new = not self.journal.exists()
        with self.journal.open("a", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["time", "arm", "event", "detail"])
            w.writerow([now_ist().isoformat(timespec="seconds"), arm, event, json.dumps(detail)])

    def target_expiry(self, today: date) -> date | None:
        """The nearest expiry with 3 to 7 trading days left: never the one about to expire."""
        for e in self.nse.expiries():
            if 3 <= trading_days_between(today, e) <= 7:
                return e
        return None

    def enter_all(self, today: date, nifty_5d_return: float | None = None) -> list[dict]:
        out = []
        expiry = self.target_expiry(today)
        if not expiry:
            return [{"note": "no expiry 3-7 trading days away"}]
        chain = self.nse.chain(expiry)
        gate = self.gate(today)
        for arm, book in self.books.items():
            if book.open:
                continue
            if arm == "lotto":
                direction = gate.get("lotto_direction") or ("up" if (nifty_5d_return or 0) >= 0 else "down")
                if gate.get("action") == "skip" or direction == "none":
                    out.append({"arm": arm, "skipped": gate.get("note", "gate: skip")})
                    continue
                legs = plan_lotto(chain, direction, book.data["cash"])
                if not legs:
                    out.append({"arm": arm, "skipped": "no option fits the budget"})
                    continue
                cost = legs[0].entry * LOT
                pos = book.enter("lotto", legs, expiry, f"buy {direction}: {gate.get('note', 'trend rule')}", cost)
            else:
                sd = 1.0
                if arm == "main":
                    if not gate:
                        out.append({"arm": arm, "skipped": "no analyst gate for today: not trading without a review"})
                        continue
                    if gate.get("action") == "skip":
                        out.append({"arm": arm, "skipped": gate.get("note")})
                        continue
                    sd = 1.25 if gate.get("action") == "widen" else 1.0
                legs = plan_iron_condor(chain, today, sd_mult=sd)
                if not legs:
                    out.append({"arm": arm, "skipped": "no liquid strikes"})
                    continue
                width = legs[2].strike - legs[0].strike
                credit_pts = sum(lg.entry if lg.side == "SELL" else -lg.entry for lg in legs)
                max_loss = (width - credit_pts) * LOT
                pos = book.enter("iron condor", legs, expiry,
                                 f"{sd:g} SD short strikes, spot {chain.spot:.0f}, ATM IV {chain.atm_iv() * 100:.1f}%"
                                 + (f"; gate: {gate.get('action')}: {gate.get('note')}" if arm == "main" else "; rules only"),
                                 max_loss)
            self._log(arm, "ENTER", pos)
            out.append({"arm": arm, **pos})
        return out

    def monitor(self, now: datetime | None = None) -> list[dict]:
        now = now or now_ist()
        out, chains = [], {}
        for arm, book in self.books.items():
            if not book.open:
                continue
            exp = date.fromisoformat(book.open["expiry"])
            if exp not in chains:
                chains[exp] = self.nse.chain(exp)
            if reason := exit_reason(book, chains[exp], now):
                closed = book.exit(chains[exp], reason)
                if closed:
                    self._log(arm, "EXIT", closed)
                    out.append({"arm": arm, "reason": reason, "pnl": closed["pnl"]})
        return out

    def snapshot(self) -> dict:
        """State of all three accounts at current prices, for the site and the equity log."""
        chains: dict[date, Chain] = {}
        rows = {}
        for arm, book in self.books.items():
            chain = None
            if book.open:
                exp = date.fromisoformat(book.open["expiry"])
                try:
                    chains.setdefault(exp, self.nse.chain(exp))
                    chain = chains[exp]
                except Exception as exc:
                    log.warning("chain unavailable: %s", exc)
            m = book.mark(chain) if chain else None
            rows[arm] = {"capital": book.data["capital"], "equity": book.equity(chain), "realized": book.data["realized"],
                         "open": book.open, "mark": m, "closed": book.data["closed"][-50:]}
        spot = next(iter(chains.values())).spot if chains else None
        return {"time": now_ist().isoformat(timespec="seconds"), "spot": spot, "books": rows}
