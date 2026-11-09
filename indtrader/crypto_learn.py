"""Crypto learning loop: small, checkable forecasts, scored automatically against a no-skill baseline.

Why: the crypto desk makes about one trading decision a day, too few to learn from quickly. Forecasts can be made
several times a day at no risk, and each one is graded when its horizon passes. That gives hundreds of graded
calls a month, which is enough to see whether the LLM has any skill, and in which conditions.

How it works (the reinforcement-learning analogy, without retraining any model):
- `brief()` builds a fact sheet: price, trend, volatility, the Fear & Greed index, perpetual funding rates.
  It also tags the market state ("fg_extreme_greed", "below_50d", ...) from the data, not from the LLM.
- `record()` stores the LLM's call (chance the price is higher after `horizon_h` hours, and an 80% range) next to a
  baseline call made at the same moment: a coin flip with a volatility-based range. Skill = beating the baseline.
- `score()` grades every call whose time has come, using Binance's 1-minute price at the due time.
- `summary()` is the reward signal: Brier score (lower is better) against the baseline, with a t-statistic that
  allows for overlapping horizons, range coverage, calibration, and the same split by market-state tag.
- Lessons (journal/crypto_lessons.json) are tied to a tag. Their evidence is counted by `update_lessons()` from the
  scores, never by hand, so a lesson only becomes "confirmed" when the data says so, and is retired when it stops
  holding. Every analyst run reads the lessons first.

Files: paper/crypto/learn/forecasts.csv and scores.csv. Paper only: nothing here trades.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from indtrader.crypto import Binance, now_utc

Z80 = 1.2816                      # 10th/90th percentile of a normal distribution
MIN_GAP_H = 6                     # one call per coin and horizon every 6 hours at most
MIN_N, MIN_T = 30, 2.0            # a lesson needs 30 scored pairs and |t| >= 2 to be confirmed or retired
FC_COLS = ["id", "made", "due", "source", "coin", "horizon_h", "spot", "p_up", "lo", "hi", "tags", "note"]
SC_COLS = ["id", "source", "coin", "horizon_h", "made", "due", "spot", "px", "up", "p_up", "brier", "inside",
           "pinball", "tags"]


class Feeds:
    """Free public data that works from US servers: alternative.me Fear & Greed, OKX perpetual funding."""

    def __init__(self, session: requests.Session | None = None):
        self.s = session or requests.Session()

    def fear_greed(self) -> dict:
        try:
            d = self.s.get("https://api.alternative.me/fng/?limit=8", timeout=15).json()["data"]
            now, week = int(d[0]["value"]), int(d[min(7, len(d) - 1)]["value"])
            return {"value": now, "label": d[0]["value_classification"], "change_7d": now - week}
        except Exception as e:  # noqa: BLE001 - a missing feed must not stop the brief
            return {"error": str(e)[:120]}

    def funding(self, coin: str) -> dict:
        """Latest and average of the last 9 eight-hour funding rates on OKX's <coin>-USDT perpetual, in %."""
        try:
            r = self.s.get("https://www.okx.com/api/v5/public/funding-rate-history",
                           params={"instId": f"{coin}-USDT-SWAP", "limit": 9}, timeout=15).json()["data"]
            rates = [100 * float(x["fundingRate"]) for x in r]
            return {"last_pct": round(rates[0], 4), "avg3d_pct": round(sum(rates) / len(rates), 4),
                    "annual_pct": round(sum(rates) / len(rates) * 3 * 365, 1)}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)[:120]}


def rsi(close: pd.Series, n: int = 14) -> float:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return float(100 - 100 / (1 + up.iloc[-1] / dn.iloc[-1])) if dn.iloc[-1] else 100.0


def state(close: pd.Series, spot: float, fg: dict, fund: dict, chg24: float | None = None) -> dict:
    """Facts and market-state tags for one coin, from completed daily closes, the live price and its rolling 24h change."""
    lr = np.log(close).diff().dropna()
    vol30 = float(lr.tail(30).std())
    vol365 = lr.rolling(30).std().tail(365)
    s50, s200 = close.tail(50).mean(), close.tail(200).mean()
    facts = {
        "spot": spot,
        "ret_24h_pct": round(chg24 if chg24 is not None else 100 * (spot / close.iloc[-1] - 1), 2),
        "ret_7d_pct": round(100 * (spot / close.iloc[-7] - 1), 2),
        "ret_30d_pct": round(100 * (spot / close.iloc[-30] - 1), 2),
        "vs_sma50_pct": round(100 * (spot / s50 - 1), 2),
        "vs_sma200_pct": round(100 * (spot / s200 - 1), 2),
        "rsi14": round(rsi(pd.concat([close, pd.Series([spot])], ignore_index=True)), 1),
        "vol_daily_pct": round(100 * vol30, 2),
        "vol_annual_pct": round(100 * vol30 * math.sqrt(365), 1),
        "up_days_365_pct": round(100 * float((lr.tail(365) > 0).mean()), 1),
        "fear_greed": fg,
        "funding": fund,
    }
    tags = ["above_50d" if spot > s50 else "below_50d", "above_200d" if spot > s200 else "below_200d"]
    v = fg.get("value")
    if v is not None:
        tags.append("fg_extreme_fear" if v < 25 else "fg_fear" if v < 45 else "fg_neutral" if v <= 55
                    else "fg_greed" if v <= 75 else "fg_extreme_greed")
    f = fund.get("avg3d_pct")
    if f is not None:
        tags.append("funding_negative" if f < 0 else "funding_high" if f > 0.03 else "funding_normal")
    if len(vol365.dropna()) > 60:
        med = float(vol365.median())
        tags.append("vol_high" if vol30 > 1.3 * med else "vol_low" if vol30 < 0.7 * med else "vol_normal")
    if abs(facts["ret_24h_pct"]) > 5:
        tags.append("big_move_24h")
    facts["rsi_zone"] = "overbought" if facts["rsi14"] >= 70 else "oversold" if facts["rsi14"] <= 30 else "middle"
    tags.append(f"rsi_{facts['rsi_zone']}")
    return {"facts": facts, "tags": tags, "vol_daily": vol30}


def baseline(spot: float, vol_daily: float, horizon_h: float) -> dict:
    """The no-skill call: 50% up, and an 80% range from recent volatility (lognormal, zero drift)."""
    w = Z80 * vol_daily * math.sqrt(horizon_h / 24)
    return {"p_up": 0.5, "lo": round(spot * math.exp(-w), 6), "hi": round(spot * math.exp(w), 6)}


def nw_tstat(x: np.ndarray, lags: int) -> float:
    """t-statistic of the mean of x with a Newey-West standard error (overlapping forecasts are correlated)."""
    n = len(x)
    if n < 3:
        return float("nan")
    d = x - x.mean()
    var = float(d @ d) / n
    for k in range(1, min(lags, n - 1) + 1):
        var += 2 * (1 - k / (lags + 1)) * float(d[k:] @ d[:-k]) / n
    se = math.sqrt(max(var, 1e-18) / n)
    return float(x.mean() / se)


def _read(f: Path) -> list[dict]:
    return list(csv.DictReader(f.open())) if f.exists() else []


def _append(f: Path, cols: list[str], rows: list[dict]) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    new = not f.exists()
    with f.open("a", newline="") as fh:
        w = csv.DictWriter(fh, cols)
        if new:
            w.writeheader()
        w.writerows(rows)


class Learner:
    def __init__(self, root: Path, api: Binance | None = None, feeds: Feeds | None = None,
                 lessons: Path = Path("journal/crypto_lessons.json")):
        self.dir = root / "learn"
        self.fc, self.sc = self.dir / "forecasts.csv", self.dir / "scores.csv"
        self.api, self.feeds, self.lessons = api or Binance(), feeds or Feeds(), lessons

    # -- 1. the fact sheet the analyst reads before forecasting
    def brief(self, coins: list[str]) -> dict:
        q = self.api.quotes(coins)
        fg = self.feeds.fear_greed()
        out = {"time": now_utc().isoformat(timespec="seconds"), "coins": {}}
        for c in coins:
            closes = self.api.daily(c, limit=400)["close"]
            closes = closes[closes.index < pd.Timestamp(now_utc().date())]        # completed days only
            st = state(closes, q[c]["last"], fg, self.feeds.funding(c), q[c].get("change_pct"))
            st["baseline_24h"] = baseline(q[c]["last"], st["vol_daily"], 24)
            st["baseline_168h"] = baseline(q[c]["last"], st["vol_daily"], 168)
            out["coins"][c] = st
        out["scorecard"] = self.summary()
        out["lessons"] = json.loads(self.lessons.read_text()) if self.lessons.exists() else []
        return out

    # -- 2. record a call, with the baseline made at the same moment
    def record(self, coin: str, horizon_h: int, p_up: float, lo: float, hi: float, note: str) -> list[dict]:
        coin = coin.upper()
        if not 0.01 <= p_up <= 0.99:
            raise ValueError("p_up must be between 0.01 and 0.99")
        if not 0 < lo < hi:
            raise ValueError("need 0 < lo < hi")
        if horizon_h not in (24, 168):
            raise ValueError("horizon must be 24 or 168 hours")
        now = now_utc()
        for r in _read(self.fc):
            if r["source"] == "llm" and r["coin"] == coin and int(r["horizon_h"]) == horizon_h \
                    and now - datetime.fromisoformat(r["made"]) < timedelta(hours=MIN_GAP_H):
                raise ValueError(f"a {horizon_h}h call on {coin} was made less than {MIN_GAP_H}h ago ({r['made']})")
        qc = self.api.quotes([coin])[coin]
        spot = qc["last"]
        closes = self.api.daily(coin, limit=400)["close"]
        closes = closes[closes.index < pd.Timestamp(now.date())]
        st = state(closes, spot, self.feeds.fear_greed(), self.feeds.funding(coin), qc.get("change_pct"))
        if not lo < spot < hi:
            raise ValueError(f"the range {lo}-{hi} must contain the current price {spot}")
        base = baseline(spot, st["vol_daily"], horizon_h)
        made, due = now.isoformat(timespec="seconds"), (now + timedelta(hours=horizon_h)).isoformat(timespec="seconds")
        fid = f"{now:%Y%m%dT%H%M}-{coin}-{horizon_h}"
        tags = ";".join(st["tags"])
        rows = [
            {"id": fid, "made": made, "due": due, "source": "llm", "coin": coin, "horizon_h": horizon_h, "spot": spot,
             "p_up": round(p_up, 3), "lo": lo, "hi": hi, "tags": tags, "note": note},
            {"id": fid, "made": made, "due": due, "source": "base", "coin": coin, "horizon_h": horizon_h, "spot": spot,
             "p_up": base["p_up"], "lo": base["lo"], "hi": base["hi"], "tags": tags, "note": "no-skill baseline"},
        ]
        _append(self.fc, FC_COLS, rows)
        return rows

    # -- 3. grade every call whose time has come
    def price_at(self, coin: str, t: datetime) -> float | None:
        k = self.api._get("klines", symbol=f"{coin}USDT", interval="1m", startTime=int(t.timestamp() * 1000), limit=1)
        if not k or abs(k[0][0] / 1000 - t.timestamp()) > 120:
            return None
        return float(k[0][1])

    def score(self) -> list[dict]:
        done = {(r["id"], r["source"]) for r in _read(self.sc)}
        now = now_utc()
        todo = [r for r in _read(self.fc) if (r["id"], r["source"]) not in done
                and datetime.fromisoformat(r["due"]) <= now - timedelta(minutes=3)]
        px_cache: dict[tuple[str, str], float | None] = {}
        out = []
        for r in todo:
            key = (r["coin"], r["due"])
            if key not in px_cache:
                px_cache[key] = self.price_at(r["coin"], datetime.fromisoformat(r["due"]))
            px = px_cache[key]
            if px is None:
                continue
            spot, p, lo, hi = float(r["spot"]), float(r["p_up"]), float(r["lo"]), float(r["hi"])
            up = 1 if px > spot else 0
            # pinball loss of the 10% and 90% quantiles, in % of the starting price
            pin = sum(max(q * (px - x), (q - 1) * (px - x)) for q, x in ((0.1, lo), (0.9, hi))) / spot * 100
            out.append({"id": r["id"], "source": r["source"], "coin": r["coin"], "horizon_h": r["horizon_h"],
                        "made": r["made"], "due": r["due"], "spot": spot, "px": px, "up": up, "p_up": p,
                        "brier": round((p - up) ** 2, 6), "inside": int(lo <= px <= hi), "pinball": round(pin, 6),
                        "tags": r["tags"]})
        _append(self.sc, SC_COLS, out)
        return out

    # -- 4. the reward signal
    def pairs(self, tag: str | None = None, horizon_h: int | None = None) -> pd.DataFrame:
        rows = _read(self.sc)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        for c in ("brier", "pinball", "p_up", "up", "inside", "horizon_h"):
            df[c] = pd.to_numeric(df[c])
        if tag:
            df = df[df["tags"].str.split(";").apply(lambda t: tag in t)]
        if horizon_h:
            df = df[df["horizon_h"] == horizon_h]
        llm, base = df[df.source == "llm"].set_index("id"), df[df.source == "base"].set_index("id")
        j = llm.join(base[["brier", "pinball", "inside"]].add_suffix("_base"), how="inner")
        return j.sort_values("made")

    def stats(self, j: pd.DataFrame, horizon_h: int) -> dict:
        if j.empty:
            return {"n": 0, "verdict": "no scored calls yet"}
        diff = (j["brier_base"] - j["brier"]).to_numpy()          # > 0: the LLM beat the baseline
        lags = max(0, math.ceil(horizon_h / 8) - 1)                # calls ~8h apart overlap for horizon_h hours
        t = nw_tstat(diff, lags)
        n = len(j)
        verdict = ("too few calls to tell" if n < MIN_N else "LLM beats the baseline" if t >= MIN_T
                   else "LLM is worse than the baseline" if t <= -MIN_T else "no evidence of skill yet")
        return {"n": n, "brier_llm": round(float(j["brier"].mean()), 4), "brier_base": round(float(j["brier_base"].mean()), 4),
                "skill_pct": round(100 * (1 - j["brier"].mean() / j["brier_base"].mean()), 1) if j["brier_base"].mean() else None,
                "t": round(t, 2) if not math.isnan(t) else None, "coverage_llm_pct": round(100 * float(j["inside"].mean()), 1),
                "coverage_base_pct": round(100 * float(j["inside_base"].mean()), 1),
                "pinball_llm": round(float(j["pinball"].mean()), 3), "pinball_base": round(float(j["pinball_base"].mean()), 3),
                "hit_rate_pct": round(100 * float(((j["p_up"] > 0.5) == (j["up"] == 1))[j["p_up"] != 0.5].mean()), 1)
                if (j["p_up"] != 0.5).any() else None,
                "verdict": verdict}

    def summary(self) -> dict:
        out: dict = {}
        for h in (24, 168):
            j = self.pairs(horizon_h=h)
            s = self.stats(j, h)
            if not j.empty:
                bins = pd.cut(j["p_up"], [0, 0.35, 0.45, 0.55, 0.65, 1.0], include_lowest=True)
                s["calibration"] = [{"range": str(b), "n": int(len(g)), "said_pct": round(100 * float(g["p_up"].mean()), 1),
                                     "happened_pct": round(100 * float(g["up"].mean()), 1)}
                                    for b, g in j.groupby(bins, observed=True)]
                tags = sorted({t for ts in j["tags"] for t in ts.split(";") if t})
                s["by_tag"] = [{"tag": t, **{k: v for k, v in self.stats(self.pairs(tag=t, horizon_h=h), h).items()
                                             if k in ("n", "skill_pct", "t", "verdict")}} for t in tags]
            out[f"{h}h"] = s
        return out

    def market_stats(self, tag: str, horizon_h: int) -> dict:
        """How often the price rose over the horizon when this tag was on (from the baseline rows: one per call)."""
        rows = [r for r in _read(self.sc) if r["source"] == "base" and int(r["horizon_h"]) == horizon_h
                and tag in r["tags"].split(";")]
        if not rows:
            return {"n": 0, "up_pct": None, "t": None}
        x = np.array([int(r["up"]) - 0.5 for r in sorted(rows, key=lambda r: r["made"])], dtype=float)
        t = nw_tstat(x, max(0, math.ceil(horizon_h / 8) - 1))
        return {"n": len(x), "up_pct": round(100 * (x.mean() + 0.5), 1), "t": None if math.isnan(t) else round(t, 2)}

    # -- 5. lessons: text by the analyst, evidence by the data
    def update_lessons(self) -> list[dict]:
        if not self.lessons.exists():
            return []
        lessons = json.loads(self.lessons.read_text())
        for le in lessons:
            tag, h = le.get("tag"), int(le.get("horizon_h", 24))
            if not tag or le.get("status") == "retired":
                continue
            if le.get("kind") == "market":
                # a claim about the market itself: under this tag the price rose ("expect": "up") or fell ("down")
                # more often than half the time over the horizon
                s = self.market_stats(tag, h)
                want = 1 if le.get("expect", "up") == "up" else -1
                le["evidence"] = s
            else:
                # a claim about the LLM's calls under this tag: "worse" than the baseline (lean on the baseline
                # there) or "better"
                s = self.stats(self.pairs(tag=tag, horizon_h=h), h)
                want = 1 if le.get("expect", "worse") == "better" else -1
                le["evidence"] = {k: s.get(k) for k in ("n", "brier_llm", "brier_base", "skill_pct", "t", "verdict")}
            le["last_checked"] = now_utc().date().isoformat()
            t = s.get("t")
            if s["n"] >= MIN_N and t is not None:
                if want * t >= MIN_T:
                    le["status"] = "confirmed"
                elif want * t <= -MIN_T or (le.get("status") == "confirmed" and want * t < 0):
                    le["status"] = "retired"
        self.lessons.write_text(json.dumps(lessons, indent=1, ensure_ascii=False) + "\n")
        return lessons

    def export(self) -> dict:
        fc, sc = _read(self.fc), _read(self.sc)
        scored = {(r["id"], r["source"]): r for r in sc}
        recent = []
        for r in [x for x in fc if x["source"] == "llm"][-40:]:
            s = scored.get((r["id"], "llm"))
            b = next((x for x in fc if x["id"] == r["id"] and x["source"] == "base"), None)
            recent.append({**{k: r[k] for k in ("id", "made", "due", "coin", "horizon_h", "spot", "p_up", "lo", "hi", "note")},
                           "base_lo": b["lo"] if b else None, "base_hi": b["hi"] if b else None,
                           "px": s["px"] if s else None, "up": s["up"] if s else None,
                           "brier": s["brier"] if s else None, "inside": s["inside"] if s else None})
        return {"summary": self.summary(), "recent": list(reversed(recent)),
                "lessons": json.loads(self.lessons.read_text()) if self.lessons.exists() else [],
                "open": sum(1 for r in fc if r["source"] == "llm" and (r["id"], "llm") not in scored)}

