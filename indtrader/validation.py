"""Is a backtest result luck? Cheap statistical checks.

- bootstrap_sharpe_ci: resample daily returns -> confidence interval for Sharpe.
  If the interval contains 0, the backtest has not shown an edge.
- walk_forward: split the equity curve into consecutive windows; a real edge
  should be positive in most of them, not just one lucky stretch.
- deflated_sharpe: the probability that the Sharpe ratio is real after testing
  n_trials variants (Bailey and Lopez de Prado, 2014). Picking the best of many
  backtests inflates its Sharpe; this corrects for that and for fat tails.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

_EULER = 0.5772156649015329
_N = NormalDist()


def _sharpe(rets: np.ndarray) -> float:
    sd = rets.std(ddof=1) if len(rets) > 1 else 0.0
    return float(np.sqrt(252) * rets.mean() / sd) if sd > 0 else 0.0


def bootstrap_sharpe_ci(equity: pd.Series, n: int = 2000, confidence: float = 0.95, seed: int = 42,
                        block: int = 5) -> dict:
    """Moving-block bootstrap (keeps short-term autocorrelation) of the daily Sharpe."""
    rets = equity.pct_change().dropna().to_numpy()
    if len(rets) < 2 * block:
        return {"error": f"need at least {2 * block} daily returns"}
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(len(rets) / block))
    starts = rng.integers(0, len(rets) - block + 1, size=(n, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n, -1)[:, : len(rets)]
    samples = rets[idx]
    sd = samples.std(axis=1, ddof=1)
    sharpes = np.where(sd > 0, np.sqrt(252) * samples.mean(axis=1) / np.where(sd > 0, sd, 1), 0.0)
    lo, hi = np.quantile(sharpes, [(1 - confidence) / 2, 1 - (1 - confidence) / 2])
    return {
        "sharpe": round(_sharpe(rets), 2),
        "ci_low": round(float(lo), 2),
        "ci_high": round(float(hi), 2),
        "prob_sharpe_positive": round(float((sharpes > 0).mean()), 3),
        "edge_shown": bool(lo > 0),
    }


def walk_forward(equity: pd.Series, windows: int = 4, benchmark: pd.Series | None = None) -> dict:
    """Per-window return (and excess over benchmark when given)."""
    if len(equity) < windows * 10:
        return {"error": f"need at least {windows * 10} bars for {windows} windows"}
    edges = np.linspace(0, len(equity) - 1, windows + 1).astype(int)
    rows = []
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        seg = equity.iloc[a: b + 1]
        row = {"start": str(seg.index[0].date()), "end": str(seg.index[-1].date()),
               "return_pct": round(100 * (seg.iloc[-1] / seg.iloc[0] - 1), 2)}
        if benchmark is not None:
            bseg = benchmark.loc[(benchmark.index >= seg.index[0]) & (benchmark.index <= seg.index[-1])]
            if len(bseg) > 1:
                row["benchmark_pct"] = round(100 * (bseg.iloc[-1] / bseg.iloc[0] - 1), 2)
                row["excess_pct"] = round(row["return_pct"] - row["benchmark_pct"], 2)
        rows.append(row)
    key = "excess_pct" if all("excess_pct" in r for r in rows) else "return_pct"
    wins = sum(r[key] > 0 for r in rows)
    return {"windows": rows, "positive_windows": f"{wins}/{len(rows)}", "measured_on": key}


def probabilistic_sharpe(rets: np.ndarray, benchmark_sr: float = 0.0) -> float:
    """P(true per-period Sharpe > benchmark_sr), allowing for skew and fat tails."""
    if len(rets) < 3 or rets.std(ddof=1) == 0:
        return float("nan")
    sr = rets.mean() / rets.std(ddof=1)
    r = pd.Series(rets)
    skew, kurt = float(r.skew()), float(r.kurt()) + 3.0   # pandas kurt is excess kurtosis
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if denom <= 0:
        return float("nan")
    return _N.cdf((sr - benchmark_sr) * math.sqrt(len(rets) - 1) / math.sqrt(denom))


def deflated_sharpe(equity: pd.Series, n_trials: int, trial_sharpes: list[float] | None = None) -> dict:
    """Deflated Sharpe ratio. `trial_sharpes` are the annualised Sharpes of every variant tried; without
    them the spread of Sharpe under the null is taken as 1/sqrt(T)."""
    rets = equity.pct_change().dropna().to_numpy()
    if len(rets) < 30:
        return {"error": "need at least 30 daily returns"}
    if n_trials > 1:
        sd = float(np.std(np.asarray(trial_sharpes) / math.sqrt(252), ddof=1)) if trial_sharpes and len(trial_sharpes) > 1 \
            else 1 / math.sqrt(len(rets))
        sr0 = sd * ((1 - _EULER) * _N.inv_cdf(1 - 1 / n_trials) + _EULER * _N.inv_cdf(1 - 1 / (n_trials * math.e)))
    else:
        sr0 = 0.0
    dsr = probabilistic_sharpe(rets, sr0)
    verdict = "robust" if dsr >= 0.95 else "marginal" if dsr >= 0.80 else "likely luck"
    return {"n_trials": n_trials, "sharpe": round(_sharpe(rets), 2), "sharpe_hurdle": round(sr0 * math.sqrt(252), 2),
            "deflated_sharpe": round(dsr, 3), "verdict": verdict}
