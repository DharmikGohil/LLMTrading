"""Bracket questions for the crypto learning loop (question set "bracket-v1").

Ideas adapted (not copied) from zadescoxp/calibrain-harness, read on 11 Nov 2026:
- ask "which is hit first?" instead of "up or down?": if you buy now with a stop d below and a target 1.5d above,
  which is touched first within 24 hours, the target, the stop, or neither? It maps straight to a trade's result;
- measure how often each outcome really happened on the coin's own recent hourly history (the base rates), show
  them to the analyst, and use them as the baseline to beat (harder and fairer than a coin flip);
- blend: p_used = w * p_analyst + (1 - w) * p_base, with w fitted on graded calls (Brier), so an analyst who adds
  nothing ends up at w = 0;
- expected value in code, in R (1R = the stop distance): EV = P(target) * 1.5 - P(stop) - costs / stop. Logged
  only: nothing here trades;
- a mirror probe: the same question on a flipped fact sheet; a consistent forecaster's long call there should match
  its short call on the real one.

Bracket size: d = one day's volatility (daily standard deviation of returns), target = 1.5 d, horizon 24 h. When a
single hourly candle touches both the stop and the target, the stop counts first (the cautious reading).
Files: paper/crypto/learn/brackets.csv, bracket_scores.csv, probes.csv. Paper only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

QSET = "bracket-v1"
RR = 1.5
HORIZON_H = 24
COST_ROUND_TRIP = 0.003          # 0.1% fee + 0.05% slippage, each side (indtrader/crypto.py)
MIN_FIT = 30
PRIOR_W = 0.5
OUTCOMES = ("target", "stop", "neither")
BR_COLS = ["id", "made", "due", "source", "qset", "coin", "spot", "d_pct", "side", "p_target", "p_stop", "p_neither",
           "w", "ev_r", "note"]
BS_COLS = ["id", "source", "coin", "side", "made", "due", "outcome", "p_target", "p_stop", "p_neither", "brier"]
PR_COLS = ["id", "made", "coin", "probe", "of_id", "long_target", "long_stop", "short_target", "short_stop", "note"]


def first_touch(path: list[tuple[float, float]], entry: float, side: str, d: float) -> str:
    """path = [(high, low), ...] after entry. Long: target entry*(1+RR*d), stop entry*(1-d); short mirrored."""
    up, dn = (entry * (1 + RR * d), entry * (1 - d)) if side == "long" else (entry * (1 + d), entry * (1 - RR * d))
    for hi, lo in path:
        hit_up, hit_dn = hi >= up, lo <= dn
        if side == "long":
            if hit_dn:
                return "stop"                 # both in one candle: stop first
            if hit_up:
                return "target"
        else:
            if hit_up:
                return "stop"
            if hit_dn:
                return "target"
    return "neither"


def base_rates(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, d: float, horizon: int = HORIZON_H) -> dict | None:
    """How often each outcome happened, entering at every completed hourly close (no look-ahead: only windows that
    ended before now). Laplace-smoothed so nothing is exactly 0 or 1."""
    n = len(closes) - horizon - 1
    if n < 200:
        return None
    cnt = {s: dict.fromkeys(OUTCOMES, 0) for s in ("long", "short")}
    up = 0
    for i in range(n):
        path = list(zip(highs[i + 1: i + 1 + horizon], lows[i + 1: i + 1 + horizon], strict=True))
        for s in ("long", "short"):
            cnt[s][first_touch(path, closes[i], s, d)] += 1
        up += closes[i + horizon] > closes[i]
    sm = lambda k, m: round((k + 1) / (n + m), 4)  # noqa: E731
    return {"windows": n, "long": {o: sm(cnt["long"][o], 3) for o in OUTCOMES},
            "short": {o: sm(cnt["short"][o], 3) for o in OUTCOMES}, "p_up_24h": sm(up, 2)}


def ev_r(p_target: float, p_stop: float, d: float) -> float:
    return p_target * RR - p_stop - COST_ROUND_TRIP / d


def brier3(p: dict, outcome: str) -> float:
    return sum((p[o] - (1.0 if o == outcome else 0.0)) ** 2 for o in OUTCOMES)


def fit_w(rows: list[tuple[dict, dict, str]]) -> dict:
    """rows = (analyst probs, base probs, outcome). Grid-search the blend weight on the Brier score."""
    n = len(rows)
    if not n:
        return {"n": 0, "w": PRIOR_W, "fitted": False}
    def score(w):
        return sum(brier3({o: w * a[o] + (1 - w) * b[o] for o in OUTCOMES}, y) for a, b, y in rows) / n
    grid = [i / 20 for i in range(21)]
    best = min(grid, key=score)
    out = {"n": n, "brier_analyst": round(score(1.0), 4), "brier_base_rates": round(score(0.0), 4),
           "brier_best_blend": round(score(best), 4), "best_w": best, "fitted": n >= MIN_FIT}
    out["skill_vs_base_pct"] = round(100 * (1 - out["brier_analyst"] / out["brier_base_rates"]), 1) if out["brier_base_rates"] else None
    out["w"] = best if out["fitted"] else PRIOR_W
    return out


def mirror(brief_coin: dict) -> dict:
    """Flip a coin's fact sheet bullish <-> bearish: returns and distances change sign, RSI -> 100 - RSI,
    Fear & Greed -> 100 - value, funding changes sign. Volatility and base-rate sizes stay; long and short swap."""
    f = dict(brief_coin["facts"])
    for k in ("ret_24h_pct", "ret_7d_pct", "ret_30d_pct", "vs_sma50_pct", "vs_sma200_pct"):
        if f.get(k) is not None:
            f[k] = -f[k]
    if f.get("rsi14") is not None:
        f["rsi14"] = round(100 - f["rsi14"], 1)
    fg = dict(f.get("fear_greed") or {})
    if fg.get("value") is not None:
        fg["value"] = 100 - fg["value"]
    f["fear_greed"] = fg
    fu = dict(f.get("funding") or {})
    for k in ("last_pct", "avg3d_pct", "annual_pct"):
        if fu.get(k) is not None:
            fu[k] = -fu[k]
    f["funding"] = fu
    f["up_days_365_pct"] = round(100 - f.get("up_days_365_pct", 50), 1)
    out = {"facts": f, "note": "MIRRORED fact sheet: answer as if this were the real market"}
    br = brief_coin.get("bracket")
    if br and br.get("base_rates"):
        b = br["base_rates"]
        out["bracket"] = {**br, "base_rates": {**b, "long": b["short"], "short": b["long"], "p_up_24h": round(1 - b["p_up_24h"], 4)}}
    return out


class Brackets:
    def __init__(self, learner):
        self.ln = learner
        d = learner.dir
        self.br, self.bs, self.pr = d / "brackets.csv", d / "bracket_scores.csv", d / "probes.csv"

    # -- the fact sheet section
    def hourly(self, coin: str, hours: int = 2000):
        """About 83 days of completed hourly candles (two requests of 1,000)."""
        api, out = self.ln.api, []
        end = int(datetime.now(UTC).replace(minute=0, second=0, microsecond=0).timestamp() * 1000)
        start = end - hours * 3600_000
        while start < end:
            k = api._get("klines", symbol=f"{coin}USDT", interval="1h", startTime=start, limit=1000)
            if not k:
                break
            out += [x for x in k if x[0] + 3600_000 <= end]
            start = k[-1][0] + 3600_000
        h = np.array([float(x[2]) for x in out])
        lo = np.array([float(x[3]) for x in out])
        c = np.array([float(x[4]) for x in out])
        return h, lo, c

    def plan(self, coin: str, vol_daily: float) -> dict:
        d = vol_daily
        h, lo, c = self.hourly(coin)
        br = base_rates(h, lo, c, d)
        w = self.weights()
        out = {"qset": QSET, "stop_pct": round(100 * d, 2), "target_pct": round(100 * RR * d, 2), "horizon_h": HORIZON_H,
               "cost_r": round(COST_ROUND_TRIP / d, 3), "base_rates": br, "blend_w": w}
        if br:
            out["ev_base_r"] = {s: round(ev_r(br[s]["target"], br[s]["stop"], d), 3) for s in ("long", "short")}
        return out

    # -- record
    def record(self, coin: str, long_t: float, long_s: float, short_t: float, short_s: float, note: str,
               brief_coin: dict) -> list[dict]:
        coin = coin.upper()
        for t, s in ((long_t, long_s), (short_t, short_s)):
            if not (0.01 <= t <= 0.98 and 0.01 <= s <= 0.98 and t + s <= 0.99):
                raise ValueError("each bracket needs target and stop chances in 0.01-0.98 that add up to at most 0.99")
        now = datetime.now(UTC)
        for r in self.ln._read_rows(self.br):
            if r["source"] == "llm" and r["coin"] == coin and now - datetime.fromisoformat(r["made"]) < timedelta(hours=6):
                raise ValueError(f"a bracket call on {coin} was made less than 6h ago ({r['made']})")
        plan = brief_coin["bracket"]
        if not plan.get("base_rates"):
            raise ValueError("no base rates yet for this coin")
        d = plan["stop_pct"] / 100
        spot = self.ln.api.quotes([coin])[coin]["last"]
        fid = f"{now:%Y%m%dT%H%M}-{coin}-br"
        made, due = now.isoformat(timespec="seconds"), (now + timedelta(hours=HORIZON_H)).isoformat(timespec="seconds")
        w = self.weights()
        rows = []
        for side, (t, s) in (("long", (long_t, long_s)), ("short", (short_t, short_s))):
            b = plan["base_rates"][side]
            ws = w.get(side, PRIOR_W)
            pt, ps = ws * t + (1 - ws) * b["target"], ws * s + (1 - ws) * b["stop"]
            common = {"id": fid, "made": made, "due": due, "qset": QSET, "coin": coin, "spot": spot, "d_pct": round(100 * d, 4),
                      "side": side}
            rows.append({**common, "source": "llm", "p_target": t, "p_stop": s, "p_neither": round(1 - t - s, 4),
                         "w": ws, "ev_r": round(ev_r(pt, ps, d), 4), "note": note})
            rows.append({**common, "source": "rate", "p_target": b["target"], "p_stop": b["stop"], "p_neither": b["neither"],
                         "w": 0, "ev_r": round(ev_r(b["target"], b["stop"], d), 4), "note": "base rates"})
        self.ln._append_rows(self.br, BR_COLS, rows)
        return rows

    def probe(self, coin: str, long_t: float, long_s: float, short_t: float, short_s: float, note: str) -> dict:
        """A mirror-probe answer, paired with the latest real bracket call on the same coin. Not graded."""
        coin = coin.upper()
        real = [r for r in self.ln._read_rows(self.br) if r["coin"] == coin and r["source"] == "llm"]
        if not real:
            raise ValueError("no real bracket call on this coin to pair the probe with")
        row = {"id": f"{datetime.now(UTC):%Y%m%dT%H%M}-{coin}-mirror", "made": datetime.now(UTC).isoformat(timespec="seconds"),
               "coin": coin, "probe": "mirror", "of_id": real[-1]["id"], "long_target": long_t, "long_stop": long_s,
               "short_target": short_t, "short_stop": short_s, "note": note}
        self.ln._append_rows(self.pr, PR_COLS, [row])
        return row

    # -- grade
    def score(self) -> list[dict]:
        done = {(r["id"], r["source"], r["side"]) for r in self.ln._read_rows(self.bs)}
        now = datetime.now(UTC)
        todo = [r for r in self.ln._read_rows(self.br) if (r["id"], r["source"], r["side"]) not in done
                and datetime.fromisoformat(r["due"]) <= now - timedelta(minutes=5)]
        paths: dict[str, list] = {}
        out = []
        for r in todo:
            if r["id"] not in paths:
                start = int(datetime.fromisoformat(r["made"]).timestamp() * 1000)
                k = self.ln.api._get("klines", symbol=f"{r['coin']}USDT", interval="1m", startTime=start, limit=1000)
                k2 = self.ln.api._get("klines", symbol=f"{r['coin']}USDT", interval="1m", startTime=start + 1000 * 60_000, limit=440)
                bars = [x for x in (k or []) + (k2 or []) if x[0] < start + HORIZON_H * 3600_000]
                paths[r["id"]] = [(float(x[2]), float(x[3])) for x in bars] if len(bars) >= HORIZON_H * 60 - 5 else None
            path = paths[r["id"]]
            if not path:
                continue
            o = first_touch(path, float(r["spot"]), r["side"], float(r["d_pct"]) / 100)
            p = {"target": float(r["p_target"]), "stop": float(r["p_stop"]), "neither": float(r["p_neither"])}
            out.append({"id": r["id"], "source": r["source"], "coin": r["coin"], "side": r["side"], "made": r["made"],
                        "due": r["due"], "outcome": o, **{f"p_{k}": v for k, v in p.items()}, "brier": round(brier3(p, o), 6)})
        self.ln._append_rows(self.bs, BS_COLS, out)
        return out

    # -- reward signal
    def rows_for(self, side: str | None = None) -> list[tuple[dict, dict, str]]:
        sc = self.ln._read_rows(self.bs)
        by = {}
        for r in sc:
            by.setdefault((r["id"], r["side"]), {})[r["source"]] = r
        out = []
        for (_, s), v in sorted(by.items(), key=lambda kv: kv[1].get("llm", {}).get("made", "")):
            if "llm" in v and "rate" in v and (side is None or s == side):
                f = lambda r: {o: float(r[f"p_{o}"]) for o in OUTCOMES}  # noqa: E731
                out.append((f(v["llm"]), f(v["rate"]), v["llm"]["outcome"]))
        return out

    def weights(self) -> dict:
        return {s: fit_w(self.rows_for(s))["w"] for s in ("long", "short")}

    def summary(self) -> dict:
        res = {"qset": QSET, "all": fit_w(self.rows_for())}
        for s in ("long", "short"):
            res[s] = fit_w(self.rows_for(s))
        pr = self.ln._read_rows(self.pr)
        br = {(r["id"], r["side"]): r for r in self.ln._read_rows(self.br) if r["source"] == "llm"}
        errs = []
        for p in pr:
            lo, sh = br.get((p["of_id"], "long")), br.get((p["of_id"], "short"))
            if lo and sh:   # mirrored long should equal the real short, and the other way round
                pairs = ((p["long_target"], sh["p_target"]), (p["long_stop"], sh["p_stop"]),
                     (p["short_target"], lo["p_target"]), (p["short_stop"], lo["p_stop"]))
            errs.append(sum(abs(float(a) - float(b)) for a, b in pairs) / 4)
        res["mirror"] = {"probes": len(errs), "mean_abs_error": round(float(np.mean(errs)), 4) if errs else None}
        llm = [r for r in self.ln._read_rows(self.br) if r["source"] == "llm"]
        res["calls"] = len({r["id"] for r in llm})
        res["mean_ev_r"] = round(float(np.mean([float(r["ev_r"]) for r in llm])), 3) if llm else None
        res["verdict"] = ("too few graded calls to tell" if res["all"]["n"] < MIN_FIT else
                          "analyst beats the base rates" if (res["all"].get("skill_vs_base_pct") or 0) > 0 else
                          "no better than the base rates")
        return res

    def recent(self, n: int = 20) -> list[dict]:
        sc = {(r["id"], r["side"], r["source"]): r for r in self.ln._read_rows(self.bs)}
        out = []
        for r in [x for x in self.ln._read_rows(self.br) if x["source"] == "llm"][-n:]:
            s = sc.get((r["id"], r["side"], "llm"))
            out.append({k: r[k] for k in ("id", "made", "coin", "side", "spot", "d_pct", "p_target", "p_stop", "p_neither", "ev_r")}
                       | {"outcome": s["outcome"] if s else None})
        return list(reversed(out))

