"""Crypto paper desk: momentum with a trend filter, an LLM gate, a rules-only control and a BTC buy-and-hold benchmark.

Three paper accounts of 10,000 USDT each:
- main     the strategy, subject to the analyst's gate (`indtrader crypto-gate`): it can cut exposure or exclude coins,
           never add risk
- control  the same strategy, rules only
- hold     BTC bought on day one and never sold (the benchmark every rule must beat after costs and Indian tax)

Prices come from Binance's public market-data mirror (data-api.binance.vision; the main API is geo-blocked in the US).
Fills: buys at the ask, sells at the bid, plus 0.05% slippage and a 0.1% fee on each trade's value. The strategy's
rules (`target_weights`) are shared with scripts/crypto_momentum_study.py, so the desk trades exactly what was tested.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

log = logging.getLogger(__name__)

API = "https://data-api.binance.vision/api/v3"
FEE, SLIP = 0.001, 0.0005
CAPITAL = 10000.0
ARMS = ("main", "control", "hold")
TOP_N, MIN_HISTORY = 20, 120
EXCLUDE = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "EUR", "TRY", "BRL", "GBP", "AEUR", "USDE", "XUSD", "PAXG",
           "WBTC", "WBETH", "BFUSD", "USD1", "RLUSD", "EURI"}

# The strategy, fixed from the study (docs/crypto-desk.md): time-series momentum (trend) on BTC and ETH. Each coin is
# held, equal weight, while its daily close is above its 50-day average; otherwise that half sits in USDT. Checked
# daily. Cross-sectional altcoin momentum ("MOMENTUM" below) won the 2020-22 design period but lost money in the
# untouched 2023-26 test, so it is kept for research only.
STRATEGY = {"mode": "trend", "coins": ["BTC", "ETH"], "trend_sma": 50, "rebalance_days": 1, "drift": 0.05}
MOMENTUM = {"mode": "momentum", "lookback": 90, "top_k": 3, "risk_adjusted": False, "core_btc": 0.0, "rebalance_days": 7,
            "coin_trend_sma": 50, "regime_sma": 100}


def now_utc() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- strategy (shared with the study)
def above(s: pd.Series, n: int) -> bool:
    s = s.dropna()
    return len(s) > n and s.iloc[-1] > s.iloc[-n:].mean()


def universe(closes: pd.DataFrame, value30: pd.DataFrame, day, top_n: int = TOP_N) -> list[str]:
    """The `top_n` coins by 30-day average traded value on `day`, among those with MIN_HISTORY days of history."""
    hist = closes.loc[:day].notna().sum()
    alive = closes.loc[day].notna()
    ok = [k for k in closes.columns if hist[k] >= MIN_HISTORY and alive[k]]
    tv = value30.loc[day, ok].dropna()
    return list(tv.sort_values(ascending=False).index[:top_n])


def target_weights(closes: pd.DataFrame, value30: pd.DataFrame, day, p: dict | None = None) -> dict[str, float]:
    """Trend mode: each of `coins` gets an equal share while above its `trend_sma`-day average.
    Momentum mode: the top k coins by L-day return (or return / volatility) among the liquid universe, each above its
    own trend average; nothing but the BTC core while BTC is below its regime average."""
    p = p or STRATEGY
    if p.get("mode") == "trend":
        n = len(p["coins"])
        return {c: 1 / n for c in p["coins"] if c in closes and above(closes[c].loc[:day], p["trend_sma"])}
    core = p.get("core_btc", 0.0)
    base = {"BTC": core} if core else {}
    if "BTC" not in closes or not above(closes["BTC"], p["regime_sma"]):
        return base
    score = {}
    for coin in universe(closes, value30, day):
        s = closes[coin].dropna()
        lb = p["lookback"]
        if len(s) <= max(lb, p["coin_trend_sma"]) or not above(s, p["coin_trend_sma"]):
            continue
        r = s.iloc[-1] / s.iloc[-lb - 1] - 1
        if r <= 0:
            continue
        if p.get("risk_adjusted"):
            vol = np.log(s.iloc[-lb - 1:]).diff().std()
            r = r / vol if vol > 0 else 0
        score[coin] = r
    top = sorted(score, key=score.get, reverse=True)[: p["top_k"]]
    w = dict(base)
    for t in top:
        w[t] = w.get(t, 0) + (1 - core) / len(top)
    return w


# ---------------------------------------------------------------- market data
class Binance:
    def __init__(self, session: requests.Session | None = None):
        self.s = session or requests.Session()

    def _get(self, path: str, **params):
        r = self.s.get(f"{API}/{path}", params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def quotes(self, coins: list[str]) -> dict[str, dict]:
        """coin -> {bid, ask, last} for <coin>USDT."""
        if not coins:
            return {}
        syms = json.dumps([f"{c}USDT" for c in coins], separators=(",", ":"))
        out = {}
        for t in self._get("ticker/24hr", symbols=syms):
            c = t["symbol"][:-4]
            out[c] = {"bid": float(t["bidPrice"]), "ask": float(t["askPrice"]), "last": float(t["lastPrice"]),
                      "change_pct": float(t["priceChangePercent"])}
        return out

    def liquid_coins(self, n: int = 45) -> list[str]:
        """Today's most traded USDT pairs (excluding stablecoins, fiat and leveraged tokens), by 24h traded value."""
        rows = []
        for t in self._get("ticker/24hr"):
            s = t["symbol"]
            if not s.endswith("USDT"):
                continue
            c = s[:-4]
            if c in EXCLUDE or c.endswith(("UP", "DOWN", "BULL", "BEAR")) or not c.isalnum():
                continue
            rows.append((float(t["quoteVolume"]), c))
        return [c for _, c in sorted(rows, reverse=True)[:n]]

    def daily(self, coin: str, limit: int = 400) -> pd.DataFrame:
        k = self._get("klines", symbol=f"{coin}USDT", interval="1d", limit=limit)
        df = pd.DataFrame(k, columns=["t", "open", "high", "low", "close", "vol", "tc", "value", "n", "tb", "tq", "x"])
        df.index = pd.to_datetime(df["t"], unit="ms").dt.normalize()
        return df[["open", "close", "value"]].astype(float)

    def panel(self, coins: list[str], limit: int = 400) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Completed daily closes and 30-day average traded value for `coins` (today's unfinished bar dropped)."""
        closes, values = {}, {}
        today = pd.Timestamp(now_utc().date())
        for c in coins:
            try:
                d = self.daily(c, limit)
            except requests.RequestException as exc:
                log.warning("no candles for %s: %s", c, exc)
                continue
            d = d[d.index < today]
            closes[c], values[c] = d["close"], d["value"]
        closes, values = pd.DataFrame(closes).sort_index(), pd.DataFrame(values).sort_index()
        return closes, values.rolling(30, min_periods=20).mean()


# ---------------------------------------------------------------- accounts
class CryptoBook:
    def __init__(self, path: Path, capital: float = CAPITAL):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {
            "capital": capital, "cash": capital, "pos": {}, "realized": 0.0, "fees": 0.0, "last_rebalance": None}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        tmp.replace(self.path)

    def value(self, q: dict[str, dict]) -> float:
        return self.data["cash"] + sum(p["qty"] * q[c]["last"] for c, p in self.data["pos"].items() if c in q)

    def rebalance(self, target: dict[str, float], q: dict[str, dict], why: str, journal) -> list[dict]:
        """Trade to target weights of current value: sells first (at the bid), then buys (at the ask)."""
        total = self.value(q)
        fills = []
        coins = set(self.data["pos"]) | set(target)
        for c in sorted(coins, key=lambda c: target.get(c, 0)):
            if c not in q:
                continue
            held = self.data["pos"].get(c, {}).get("qty", 0.0)
            want = target.get(c, 0.0) * total / q[c]["last"]
            d = want - held
            if abs(d) * q[c]["last"] < STRATEGY.get("drift", 0.002) * total and target.get(c, 0.0) > 0:
                continue                                     # leave small drift alone: fewer trades, lower costs
            if d < 0 and held > 0:
                fills.append(self._fill(c, "SELL", min(-d, held), q[c]["bid"] * (1 - SLIP), why, journal))
        for c in sorted(target, key=lambda c: -target[c]):
            if c not in q:
                continue
            held = self.data["pos"].get(c, {}).get("qty", 0.0)
            want = target[c] * total / q[c]["last"]
            d = want - held
            if d * q[c]["last"] < STRATEGY.get("drift", 0.002) * total:
                continue
            px = q[c]["ask"] * (1 + SLIP)
            d = min(d, 0.99999 * self.data["cash"] / (px * (1 + FEE)))
            if d > 0:
                fills.append(self._fill(c, "BUY", d, px, why, journal))
        self.data["last_rebalance"] = now_utc().isoformat(timespec="seconds")
        self.save()
        return fills

    def _fill(self, coin: str, side: str, qty: float, px: float, why: str, journal) -> dict:
        value = qty * px
        fee = value * FEE
        pos = self.data["pos"].setdefault(coin, {"qty": 0.0, "avg": 0.0, "opened": now_utc().isoformat(timespec="seconds")})
        pnl = None
        if side == "BUY":
            pos["avg"] = (pos["qty"] * pos["avg"] + value) / (pos["qty"] + qty)
            pos["qty"] += qty
            self.data["cash"] -= value + fee
        else:
            pnl = qty * (px - pos["avg"]) - fee
            pos["qty"] -= qty
            self.data["cash"] += value - fee
            self.data["realized"] = round(self.data["realized"] + pnl, 4)
            if pos["qty"] * px < 0.01:
                del self.data["pos"][coin]
        self.data["fees"] = round(self.data["fees"] + fee, 4)
        row = {"time": now_utc().isoformat(timespec="seconds"), "coin": coin, "side": side, "qty": round(qty, 8),
               "price": round(px, 8), "value": round(value, 2), "fee": round(fee, 4),
               "pnl": round(pnl, 2) if pnl is not None else None, "reason": why}
        journal(row)
        return row


class CryptoDesk:
    def __init__(self, root: Path, api: Binance | None = None):
        self.root, self.api = root, api or Binance()
        self.books = {a: CryptoBook(root / f"{a}.json") for a in ARMS}
        self.gates = root / "gates"

    # -- gate: written by the analyst; it may only reduce risk
    def gate(self, day: str | None = None) -> dict:
        f = self.gates / f"{day or now_utc().date().isoformat()}.json"
        if f.exists():
            return json.loads(f.read_text())
        latest = sorted(self.gates.glob("*.json"))[-1:] if self.gates.exists() else []
        if latest:
            g = json.loads(latest[0].read_text())
            age = (now_utc().date() - datetime.fromisoformat(g["date"]).date()).days
            if age <= 1:
                return g
        return {}

    def set_gate(self, exposure: float, exclude: list[str], note: str) -> Path:
        exposure = max(0.0, min(1.0, exposure))
        self.gates.mkdir(parents=True, exist_ok=True)
        f = self.gates / f"{now_utc().date().isoformat()}.json"
        f.write_text(json.dumps({"date": now_utc().date().isoformat(), "max_exposure": exposure,
                                 "exclude": sorted({c.upper() for c in exclude}), "note": note,
                                 "time": now_utc().isoformat(timespec="seconds")}, indent=1))
        return f

    def _journal(self, arm: str):
        f = self.root / "trades.csv"

        def write(row: dict) -> None:
            new = not f.exists()
            with f.open("a", newline="") as fh:
                w = csv.DictWriter(fh, ["arm", *row])
                if new:
                    w.writeheader()
                w.writerow({"arm": arm, **row})
        return write

    def due(self, arm: str) -> bool:
        last = self.books[arm].data.get("last_rebalance")
        if not last:
            return True
        last_day = datetime.fromisoformat(last).date()
        return (now_utc().date() - last_day).days >= STRATEGY["rebalance_days"]   # calendar days (UTC)

    def run(self, force: bool = False) -> dict:
        """Daily job: rebalance the strategy accounts when due, buy the benchmark once, record equity."""
        out: dict = {"time": now_utc().isoformat(timespec="seconds")}
        hold = self.books["hold"]
        need = [a for a in ("main", "control") if force or self.due(a)]
        if need:
            held = {c for a in ARMS for c in self.books[a].data["pos"]}
            if STRATEGY.get("mode") == "trend":
                pool = sorted(set(STRATEGY["coins"]) | held)
            else:
                pool = sorted(set(self.api.liquid_coins()) | {"BTC", "ETH"} | held)
            closes, value30 = self.api.panel(pool)
            day = closes.index[-1]
            target = target_weights(closes, value30, day)
            out["target"] = {k: round(v, 3) for k, v in target.items()}
            g = self.gate()
            gated = {c: w * g.get("max_exposure", 1.0) for c, w in target.items() if c not in set(g.get("exclude", []))}
            out["gate"] = g or None
            for arm, t in (("main", gated), ("control", target)):
                if arm not in need:
                    continue
                q = self.api.quotes(sorted(set(t) | set(self.books[arm].data["pos"]) | {"BTC"}))
                why = f"rebalance: {', '.join(f'{c} {w:.0%}' for c, w in t.items()) or 'all USDT'}"
                if arm == "main" and g:
                    excl = f", excluded {', '.join(g['exclude'])}" if g.get("exclude") else ""
                    why += f"; gate: exposure {g.get('max_exposure', 1):.0%}{excl}"
                out[arm] = self.books[arm].rebalance(t, q, why, self._journal(arm))
        if not hold.data["pos"]:
            q = self.api.quotes(["BTC"])
            out["hold"] = hold.rebalance({"BTC": 1.0}, q, "benchmark: buy and hold BTC", self._journal("hold"))
        out["equity"] = self.record()
        return out

    def check(self) -> dict:
        """Hourly job: apply a new gate to the main account between rebalances (risk can only go down), record equity."""
        g = self.gate()
        out: dict = {"time": now_utc().isoformat(timespec="seconds")}
        main = self.books["main"]
        if g and main.data["pos"]:
            q = self.api.quotes(sorted(main.data["pos"]))
            total = main.value(q)
            cur = {c: p["qty"] * q[c]["last"] / total for c, p in main.data["pos"].items() if c in q}
            cap = g.get("max_exposure", 1.0)
            want = {c: (0.0 if c in set(g.get("exclude", [])) else w) for c, w in cur.items()}
            s = sum(want.values())
            if s > cap + 0.01:
                want = {c: w * cap / s for c, w in want.items()}
            if any(want[c] < cur[c] - 0.01 for c in cur):
                clock = main.data.get("last_rebalance")
                out["main"] = main.rebalance({c: w for c, w in want.items() if w > 0}, q,
                                             f"gate applied: {g.get('note', '')[:160]}", self._journal("main"))
                main.data["last_rebalance"] = clock          # a gate trim does not restart the rebalance clock
                main.save()
        out["equity"] = self.record()
        return out

    def snapshot(self) -> dict:
        coins = sorted({c for a in ARMS for c in self.books[a].data["pos"]} | {"BTC"})
        q = self.api.quotes(coins)
        books = {}
        for a in ARMS:
            b = self.books[a].data
            v = self.books[a].value(q)
            books[a] = {"capital": b["capital"], "value": round(v, 2), "cash": round(b["cash"], 2),
                        "realized": round(b["realized"], 2), "fees": round(b["fees"], 2),
                        "return_pct": round(100 * (v / b["capital"] - 1), 2), "last_rebalance": b.get("last_rebalance"),
                        "positions": [{"coin": c, "qty": p["qty"], "avg": p["avg"], "last": q[c]["last"],
                                       "value": round(p["qty"] * q[c]["last"], 2),
                                       "pnl": round(p["qty"] * (q[c]["last"] - p["avg"]), 2),
                                       "pnl_pct": round(100 * (q[c]["last"] / p["avg"] - 1), 2) if p["avg"] else None,
                                       "day_pct": q[c]["change_pct"], "opened": p.get("opened")}
                                      for c, p in b["pos"].items() if c in q]}
        return {"time": now_utc().isoformat(timespec="seconds"), "btc": q.get("BTC", {}).get("last"), "books": books}

    def record(self) -> dict:
        snap = self.snapshot()
        f = self.root / "equity.csv"
        new = not f.exists()
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a") as fh:
            if new:
                fh.write("time,btc," + ",".join(ARMS) + "\n")
            fh.write(f"{snap['time']},{snap['btc']}," + ",".join(str(snap["books"][a]["value"]) for a in ARMS) + "\n")
        return {a: snap["books"][a]["value"] for a in ARMS}

    def export(self, out: Path) -> dict:
        snap = self.snapshot()
        eq = self.root / "equity.csv"
        snap["equity"] = list(csv.DictReader(eq.open()))[-3000:] if eq.exists() else []
        tr = self.root / "trades.csv"
        snap["trades"] = list(csv.DictReader(tr.open()))[-300:] if tr.exists() else []
        snap["gates"] = [json.loads(f.read_text()) for f in sorted(self.gates.glob("*.json"))][-30:] if self.gates.exists() else []
        snap["strategy"] = STRATEGY
        out.mkdir(parents=True, exist_ok=True)
        (out / "crypto.json").write_text(json.dumps(snap, indent=1, default=str))
        return snap
