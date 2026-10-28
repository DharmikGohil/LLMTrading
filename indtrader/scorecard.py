"""Grade every rating against what happened next (idea from ai-hedge-fund v2's
analyst scorecard). For each signal dated D (data up to D's close), the outcome
is the stock's return in excess of Nifty from the close of the next trading day
(when the bot would have traded) over `horizon` trading days.

Per source (claude-analyst, tradingagents, vibe-trading, momentum screen):
- hit rate: bullish calls that beat Nifty, bearish calls that lagged it
- mean excess return of bullish vs bearish calls (the spread is what matters)
- rank IC: Spearman correlation between rating score and excess return
Only fully elapsed windows are graded; younger signals count as pending.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SCORE = {"Buy": 2, "Overweight": 1, "Hold": 0, "Underweight": -1, "Sell": -2}


def collect_signals(roots: dict[str, Path]) -> pd.DataFrame:
    """All stored ratings. `roots` maps a label to a signals directory; the label is
    used when a signal has no `source` field. Screen picks become 'momentum' Buy calls."""
    rows = []
    for label, root in roots.items():
        if not root.exists():
            continue
        for day in sorted(p for p in root.iterdir() if p.is_dir()):
            for f in day.glob("*.json"):
                data = json.loads(f.read_text(encoding="utf-8"))
                if f.stem == "_screen":
                    rows += [{"date": day.name, "symbol": s, "rating": "Buy", "source": "momentum-screen"}
                             for s in data.get("candidates", [])]
                elif not f.stem.startswith("_") and data.get("rating") in SCORE:
                    rows.append({"date": day.name, "symbol": data["symbol"], "rating": data["rating"],
                                 "source": data.get("source") or label})
    return pd.DataFrame(rows, columns=["date", "symbol", "rating", "source"])


def grade(signals: pd.DataFrame, closes: Callable[[str], pd.Series], index_closes: pd.Series,
          horizon: int = 10) -> pd.DataFrame:
    """Add `excess` (stock minus index return, %) or NaN while the window is still open."""
    out = signals.copy()
    excess = []
    for r in out.itertuples():
        try:
            px = closes(r.symbol)
        except Exception:
            excess.append(np.nan)
            continue
        after = px.index[px.index > pd.Timestamp(r.date)]
        if len(after) < horizon + 1:
            excess.append(np.nan)
            continue
        t0, t1 = after[0], after[horizon]
        idx = index_closes.loc[t0:t1]
        if len(idx) < 2:
            excess.append(np.nan)
            continue
        stock = px.loc[t1] / px.loc[t0] - 1
        excess.append(round(100 * (stock - (idx.iloc[-1] / idx.iloc[0] - 1)), 2))
    out["excess_pct"] = excess
    out["score"] = out["rating"].map(SCORE)
    return out


def summarize(graded: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for source, g in graded.groupby("source"):
        done = g.dropna(subset=["excess_pct"])
        bull, bear = done[done["score"] > 0], done[done["score"] < 0]
        hits = (bull["excess_pct"] > 0).sum() + (bear["excess_pct"] < 0).sum()
        directional = len(bull) + len(bear)
        ic = done["score"].rank().corr(done["excess_pct"].rank()) if done["score"].nunique() > 1 and len(done) >= 3 else np.nan
        rows.append({
            "source": source, "graded": len(done), "pending": len(g) - len(done),
            "hit_rate_pct": round(100 * hits / directional, 1) if directional else None,
            "bullish_mean_excess_pct": round(bull["excess_pct"].mean(), 2) if len(bull) else None,
            "bearish_mean_excess_pct": round(bear["excess_pct"].mean(), 2) if len(bear) else None,
            "rank_ic": round(float(ic), 3) if pd.notna(ic) else None,
        })
    return pd.DataFrame(rows)


def run_scorecard(roots: dict[str, Path], horizon: int = 10, index: str = "^NSEI") -> tuple[pd.DataFrame, pd.DataFrame]:
    from indtrader import data as market_data

    signals = collect_signals(roots)
    if signals.empty:
        return signals, pd.DataFrame()
    start = date.fromisoformat(signals["date"].min()) - timedelta(days=5)
    cache: dict[str, pd.Series] = {}

    def closes(sym: str) -> pd.Series:
        if sym not in cache:
            cache[sym] = market_data.history(sym, start)["Close"]
        return cache[sym]

    graded = grade(signals, closes, market_data.history(index, start)["Close"], horizon)
    return graded, summarize(graded)
