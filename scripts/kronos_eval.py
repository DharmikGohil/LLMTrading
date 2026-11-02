"""Walk-forward test of Kronos-small (github.com/shiyu-coder/Kronos, MIT) on daily candles.

Only dates after the model's release (Aug 2025) are tested, so it cannot have seen them in training.
At each origin (every 5th trading day): 128 candles of context, N sampled 5-day paths, then:
- the median path's 5-day direction and the p10-p90 band of the 5-day close
- the post's "race": long, stop 1 x and target 2 x the 5-day volatility; share of paths that hit the
  target first, and what the real candles did
Usage: python scripts/kronos_eval.py <path-to-Kronos-clone> "^NSEI,RELIANCE.NS" out.csv
Needs torch, einops and huggingface_hub (CPU is fine, about 12 s per origin). Not a project dependency.
Env: KN paths (50), KCTX context (128), KT torch threads (4), KLIMIT max origins per symbol.
"""

from __future__ import annotations

import math
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
import yfinance as yf

sys.path.insert(0, sys.argv[1])
from model import Kronos, KronosPredictor, KronosTokenizer  # noqa: E402

N = int(os.environ.get("KN", 50))
CTX = int(os.environ.get("KCTX", 128))
LIMIT = int(os.environ.get("KLIMIT", 10**6))
H, STEP = 5, 5
START = pd.Timestamp("2025-09-01")


def race(highs, lows, stop: float, target: float) -> int:
    """1 if the target is hit first, -1 if the stop is (a day touching both counts as the stop), 0 if neither."""
    for hi, lo in zip(highs, lows, strict=True):
        if lo <= -stop:
            return -1
        if hi >= target:
            return 1
    return 0


def main(symbols: list[str], out: str) -> None:
    torch.set_num_threads(int(os.environ.get("KT", 4)))
    torch.manual_seed(0)
    tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    mdl = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    pred = KronosPredictor(mdl, tok, device="cpu", max_context=512)
    rows = []
    for sym in symbols:
        d = yf.download(sym, start="2023-06-01", end="2026-10-31", progress=False, auto_adjust=True)
        d.columns = [c[0].lower() for c in d.columns]
        d = d[(d.volume > 0) | sym.startswith("^")].dropna().reset_index().rename(columns={"Date": "ts"})
        if sym.startswith("^"):
            d["volume"] = 0.0   # Yahoo index volume is unreliable; Kronos gets zeros instead
        origins = [i for i in range(CTX, len(d) - H) if d.ts[i] >= START][::STEP][:LIMIT]
        t0 = time.time()
        for i in origins:
            ctx, fut = d.iloc[i - CTX + 1: i + 1], d.iloc[i + 1: i + 1 + H]
            x = ctx[["open", "high", "low", "close", "volume"]]
            outs = pred.predict_batch([x] * N, [ctx.ts] * N, [fut.ts] * N, pred_len=H, T=1.0, top_p=0.9,
                                      sample_count=1, verbose=False)
            c0 = float(ctx.close.iloc[-1])
            pc = np.array([o["close"].values for o in outs]) / c0 - 1
            ph = np.array([o["high"].values for o in outs]) / c0 - 1
            pl = np.array([o["low"].values for o in outs]) / c0 - 1
            ac, ah, al = fut.close.values / c0 - 1, fut.high.values / c0 - 1, fut.low.values / c0 - 1
            sig = float(np.log(d.close.iloc[i - 60: i + 1]).diff().dropna().std())
            stop, target = sig * math.sqrt(H), 2 * sig * math.sqrt(H)
            sim = np.array([race(ph[j], pl[j], stop, target) for j in range(N)])
            rows.append({"sym": sym, "date": str(d.ts[i].date()), "sigma_d": sig,
                         "mom20": float(d.close.iloc[i] / d.close.iloc[i - 20] - 1),
                         "act5": float(ac[-1]), "act1": float(ac[0]),
                         "k_med5": float(np.median(pc[:, -1])), "k_mean5": float(pc[:, -1].mean()),
                         "k_med1": float(np.median(pc[:, 0])),
                         "k_p10": float(np.quantile(pc[:, -1], 0.1)), "k_p90": float(np.quantile(pc[:, -1], 0.9)),
                         "k_sd5": float(pc[:, -1].std()), "k_up": float((pc[:, -1] > 0).mean()),
                         "k_maxabs": float(np.median(np.maximum(ph.max(1), -pl.min(1)))),
                         "act_maxabs": float(max(ah.max(), -al.min())),
                         "k_tgt_first": float((sim == 1).mean()), "k_stop_first": float((sim == -1).mean()),
                         "act_race": race(ah, al, stop, target)})
            print(f"{sym} {d.ts[i].date()} {time.time() - t0:.0f}s", flush=True)
            pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main(sys.argv[2].split(","), sys.argv[3])
