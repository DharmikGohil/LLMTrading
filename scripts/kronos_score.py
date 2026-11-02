"""Score scripts/kronos_eval.py output against naive baselines, per symbol and pooled.

Usage: python scripts/kronos_score.py docs/data/kronos-walkforward-2025-09-to-2026-10.csv
"""

from __future__ import annotations

import math
import sys

import numpy as np
import pandas as pd
from scipy import stats

Z80 = 1.2816   # half-width of a normal 80% band, in standard deviations


def score(g: pd.DataFrame, name: str) -> dict:
    n, up = len(g), g.act5 > 0
    right = (g.k_med5 > 0) == up
    naive_half = Z80 * g.sigma_d * math.sqrt(5)
    stop = g.sigma_d * math.sqrt(5)
    r = np.where(g.act_race == 1, 2.0, np.where(g.act_race == -1, -1.0, g.act5 / stop))
    take = g.k_tgt_first > g.k_stop_first
    hit = (g.act_race == 1).astype(float)
    return {
        "set": name, "n": n,
        "dir_hit_kronos": round(right.mean(), 3),
        "p_vs_coinflip": round(stats.binomtest(int(right.sum()), n, 0.5).pvalue, 3),
        "dir_hit_mom20": round(((g.mom20 > 0) == up).mean(), 3),
        "always_up": round(up.mean(), 3),
        "rank_ic": round(stats.spearmanr(g.k_mean5, g.act5).statistic, 3),
        "cov80_kronos": round(((g.act5 >= g.k_p10) & (g.act5 <= g.k_p90)).mean(), 3),
        "cov80_naive": round((g.act5.abs() <= naive_half).mean(), 3),
        "band_kronos_pct": round(100 * (g.k_p90 - g.k_p10).mean(), 2),
        "band_naive_pct": round(100 * (2 * naive_half).mean(), 2),
        "volcorr_kronos": round(stats.spearmanr(g.k_sd5, g.act5.abs()).statistic, 3),
        "volcorr_naive": round(stats.spearmanr(g.sigma_d, g.act5.abs()).statistic, 3),
        "brier_kronos": round(((g.k_tgt_first - hit) ** 2).mean(), 4),
        "brier_base_rate": round(((hit.mean() - hit) ** 2).mean(), 4),
        "avg_R_all": round(r.mean(), 3),
        "avg_R_kronos_says_go": round(r[take].mean(), 3) if take.any() else None,
        "n_go": int(take.sum()),
    }


def main(path: str) -> None:
    df = pd.read_csv(path)
    out = [score(g, s) for s, g in df.groupby("sym")] + [score(df, "ALL")]
    pd.set_option("display.width", 250)
    print(pd.DataFrame(out).set_index("set").T.to_string())


if __name__ == "__main__":
    main(sys.argv[1])
