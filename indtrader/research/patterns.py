"""Head-and-shoulders tops and double tops, found by code (test plan H9 for stocks, H9c for crypto).

Definitions: Lo, Mamaysky & Wang (2000), "Foundations of Technical Analysis", Journal of Finance 55(4), with the
completion rule the test plan adds. Everything works on rows (trading days for stocks, calendar days for crypto).

- Head-and-shoulders top (hs): five consecutive turning points E1..E5, E1 a peak. The head E3 is above both shoulders
  E1 and E5; the shoulders are within 1.5% of their average, and so are the troughs E2 and E4.
- Double top (dt): a peak E1 and a later peak Ea, Ea the highest turning point after E1, the two within 1.5% of their
  average and at least 22 rows apart.
- Window and lag (LMW l = 35, d = 3): every turning point of a pattern lies inside the 38 rows that end on the
  detection row t, and the last one (E5, or Ea) is exactly 3 rows old on row t. Row t is the row on whose close the
  last turning point is confirmed.
- Complete: a close below the neckline on one of the 10 rows after row t. Neckline: for hs the line through E2 and
  E4, extended; for dt the lowest close strictly between the two peaks.

Two ways to find the turning points (each uses data up to row t only):
- kernel: LMW's Gaussian Nadaraya-Watson smoother of the closes, refitted on each 38-row window, with bandwidth 0.3 x
  the cross-validated bandwidth h* of that window (LMW eq. 12-13: h* minimises the leave-one-out squared error, the
  left-out point's weight dropped without renormalising the others). A turning point is where the sign of the
  smoother's derivative flips; its row and price are the highest close (peak) or lowest close (trough) in
  [tau - 1, tau + 1], tau being the row before the flip.
- swing: indtrader.signals.chart.swing_points with k = 3 on highs (peaks) and lows (troughs); a swing at row i is
  known only from row i + 3, which is the same 3-row lag.
Runs of same-type turning points are merged into one (highest peak, lowest trough; the earlier one on a tie), so
peaks and troughs alternate.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from indtrader.signals.chart import swing_points

WINDOW = 38                 # l + d rows
LAG = 3                     # d: the last turning point is this many rows old when the pattern is detected
TOL = 0.015                 # within 1.5% of their average
DT_MIN_GAP = 22             # double-top peaks at least 22 rows apart
COMPLETE_WITHIN = 10        # a close below the neckline within 10 rows after the detection row
BW_FACTOR = 0.3             # LMW: 0.3 x the cross-validated bandwidth
BW_GRID = np.round(np.arange(0.5, 100.0 + 1e-9, 0.1), 1)     # bandwidths searched by cross-validation, in rows
SWING_K = 3
METHODS = ("kernel", "swing")
KINDS = ("hs", "dt")

Turn = tuple[int, float, int]       # (row, price, +1 peak / -1 trough)


@dataclass(frozen=True)
class Pattern:
    kind: str                                   # "hs" or "dt"
    method: str                                 # "kernel" or "swing"
    detect: int                                 # row whose close confirms the last turning point
    points: tuple[tuple[int, float], ...]       # turning points (row, price): E1..E5 for hs, E1 and Ea for dt
    neck: tuple[tuple[int, float], ...]         # hs: E2 and E4; dt: the lowest close between the peaks (row, close)
    complete: int | None                        # first row in detect+1 .. detect+10 closing below the neckline

    def neckline(self, row: int) -> float:
        if self.kind == "dt":
            return self.neck[0][1]
        (r2, p2), (r4, p4) = self.neck
        return p2 + (p4 - p2) * (row - r2) / (r4 - r2)


# ------------------------------------------------------------------------------------------------- building blocks

def within(a: float, b: float, tol: float = TOL) -> bool:
    """a and b are each within `tol` of their average."""
    m = (a + b) / 2
    return m > 0 and abs(a - m) <= tol * m


def alternate(turns: Iterable[Turn]) -> list[Turn]:
    """Sort turning points by row and merge runs of the same type, so peaks and troughs alternate.

    In a run, the highest peak (lowest trough) is kept, the earlier one on a tie. A row that is both a peak and a
    trough (an outside bar) is entered in the order that alternates with what came before it."""
    by_row: dict[int, list[Turn]] = {}
    for p in turns:
        by_row.setdefault(int(p[0]), []).append((int(p[0]), float(p[1]), int(p[2])))
    out: list[Turn] = []
    for row in sorted(by_row):
        group = by_row[row]
        if len({g[2] for g in group}) > 1 and out:
            group = sorted(group, key=lambda g: g[2] == out[-1][2])      # the type that differs from the last first
        for p in group:
            if out and out[-1][2] == p[2]:
                better = p[1] > out[-1][1] if p[2] > 0 else p[1] < out[-1][1]
                if better:
                    out[-1] = p
            else:
                out.append(p)
    return out


def match_hs(turns: list[Turn], last_row: int, tol: float = TOL) -> tuple[Turn, ...] | None:
    """E1..E5 if the five alternating turning points ending with the peak at `last_row` form a head-and-shoulders top."""
    pos = [i for i, p in enumerate(turns) if p[0] == last_row and p[2] > 0]
    if not pos or pos[-1] < 4:
        return None
    e = tuple(turns[pos[-1] - 4: pos[-1] + 1])
    if [p[2] for p in e] != [1, -1, 1, -1, 1]:
        return None
    p1, p2, p3, p4, p5 = (p[1] for p in e)
    if p3 > p1 and p3 > p5 and within(p1, p5, tol) and within(p2, p4, tol) and e[1][0] < e[3][0]:
        return e
    return None


def match_dt(turns: list[Turn], last_row: int, closes: np.ndarray, tol: float = TOL,
             min_gap: int = DT_MIN_GAP) -> tuple[Turn, Turn, tuple[int, float]] | None:
    """(E1, Ea, neckline) if the peak at `last_row` is the second peak of a double top.

    Ea must be at least as high as every turning point after E1 (LMW: Ea is the highest later extremum). Of several
    qualifying E1, the earliest is used (the longest pattern, so the lowest neckline). Neckline: the lowest close
    strictly between the peaks (`closes` indexed by the same rows)."""
    pos = [i for i, p in enumerate(turns) if p[0] == last_row and p[2] > 0]
    if not pos:
        return None
    ia = pos[-1]
    ea = turns[ia]
    for i1 in range(ia):
        e1 = turns[i1]
        if e1[2] <= 0:
            continue
        if ea[0] - e1[0] < min_gap:
            break
        if not within(e1[1], ea[1], tol):
            continue
        if any(p[1] > ea[1] for j, p in enumerate(turns[i1 + 1:], start=i1 + 1) if j != ia):
            continue
        seg = closes[e1[0] + 1: ea[0]]
        if not len(seg) or not np.isfinite(seg).all():
            continue
        r = e1[0] + 1 + int(np.argmin(seg))
        return e1, ea, (r, float(closes[r]))
    return None


def completion(closes: np.ndarray, detect: int, neckline, within_rows: int = COMPLETE_WITHIN) -> int | None:
    """First row in detect+1 .. detect+within_rows whose close is below neckline(row); None if there is none."""
    for s in range(detect + 1, min(detect + within_rows, len(closes) - 1) + 1):
        c = closes[s]
        if np.isfinite(c) and c < neckline(s):
            return s
    return None


# ------------------------------------------------------------------------------------------------------ the kernel

def _z(n: int) -> np.ndarray:
    x = np.arange(n, dtype=float)
    return x[:, None] - x[None, :]


def lmw_cv_bandwidth(windows: np.ndarray, grid: np.ndarray = BW_GRID) -> np.ndarray:
    """LMW's cross-validated bandwidth h* for each row of `windows` (shape (W, L), prices, no NaN).

    CV(h) = mean_t (P_t - m_h,-t)^2 with m_h,-t = sum_{s != t} K_h(t - s) P_s / sum_s K_h(t - s) (eq. 12-13: the
    weights keep their full-sample normalisation). h* is the first minimiser on `grid`. Each window is divided by its
    mean first, which does not change the minimiser."""
    W, L = windows.shape
    if W == 0:
        return np.empty(0)
    P = windows / windows.mean(1, keepdims=True)
    z = _z(L)
    best = np.full(W, np.inf)
    hstar = np.full(W, np.nan)
    for h in grid:
        K = np.exp(-0.5 * (z / h) ** 2)
        A = K / K.sum(1, keepdims=True)
        np.fill_diagonal(A, 0.0)
        cv = ((P - P @ A.T) ** 2).mean(1)
        better = cv < best
        best[better] = cv[better]
        hstar[better] = h
    return hstar


def kernel_slope_signs(windows: np.ndarray, h: float) -> np.ndarray:
    """Sign of the derivative of the Gaussian Nadaraya-Watson smoother at each row of each window (shape (W, L))."""
    z = _z(windows.shape[1])
    K = np.exp(-0.5 * (z / h) ** 2)
    Kd = -(z / h ** 2) * K                       # d/dx K((x - s) / h)
    N, Nd = windows @ K.T, windows @ Kd.T
    D, Dd = K.sum(1), Kd.sum(1)
    return np.sign(Nd * D - N * Dd)             # sign of (N'D - ND') / D^2


def kernel_turns(prices: np.ndarray, signs: np.ndarray) -> list[Turn]:
    """LMW turning points of one window: where the smoother's slope flips from + to - (a peak) or - to + (a trough).

    tau is the row before the flip (the first zero-slope row if the slope is exactly zero in between); the turning
    point is the highest (lowest) price in [tau - 1, tau + 1]."""
    nz = np.flatnonzero(signs)
    out: list[Turn] = []
    n = len(prices)
    for a, b in zip(nz[:-1], nz[1:], strict=True):
        if signs[a] == signs[b]:
            continue
        tau = a if b == a + 1 else a + 1
        lo, hi = max(tau - 1, 0), min(tau + 1, n - 1)
        seg = prices[lo: hi + 1]
        if signs[a] > 0:
            j = lo + int(np.argmax(seg))
            out.append((j, float(prices[j]), 1))
        else:
            j = lo + int(np.argmin(seg))
            out.append((j, float(prices[j]), -1))
    return out


def detect_kernel(close, window: int = WINDOW, lag: int = LAG, factor: float = BW_FACTOR,
                  grid: np.ndarray = BW_GRID, kinds: Iterable[str] = KINDS) -> list[Pattern]:
    """Patterns found by the kernel method on one series of closes (NaN rows are skipped: no window crosses them).

    One kernel fit per window of `window` rows ending on row t, using those rows only. A pattern is reported on row
    t when its last turning point is on row t - lag."""
    close = np.asarray(close, dtype=float)
    n = len(close)
    if n < window:
        return []
    W = sliding_window_view(close, window)
    ok = np.flatnonzero(np.isfinite(W).all(1) & (W > 0).all(1))
    if not len(ok):
        return []
    h = np.round(factor * lmw_cv_bandwidth(W[ok], grid), 10)
    last = window - 1 - lag
    kinds = tuple(kinds)
    out: list[Pattern] = []
    for hv in np.unique(h):
        sel = ok[h == hv]
        Pw = W[sel]
        signs = kernel_slope_signs(Pw / Pw.mean(1, keepdims=True), float(hv))
        for w, s in zip(sel, signs, strict=True):
            prices = W[w]
            turns = alternate(kernel_turns(prices, s))
            if not any(p[0] == last and p[2] > 0 for p in turns):
                continue
            g = [(int(w) + r, p, k) for r, p, k in turns]          # rows of the whole series
            out.extend(_match(g, int(w) + last, int(w) + window - 1, close, "kernel", kinds))
    return sorted(out, key=lambda p: (p.detect, p.kind))


# ------------------------------------------------------------------------------------------------------ the swings

def detect_swing(high, low, close, k: int = SWING_K, window: int = WINDOW, kinds: Iterable[str] = KINDS) -> list[Pattern]:
    """Patterns found from chart.swing_points(k) on one series. A swing at row i is used only from row i + k, so a
    pattern whose last peak is at row i is reported on row i + k, from the swings of rows i + k - window + 1 .. i."""
    high, low, close = (np.asarray(a, dtype=float) for a in (high, low, close))
    highs, lows = swing_points(pd.DataFrame({"High": high, "Low": low}), k)
    turns = sorted([(i, p, 1) for i, p in highs] + [(i, p, -1) for i, p in lows], key=lambda p: p[0])
    rows = np.array([p[0] for p in turns], dtype=int)
    kinds = tuple(kinds)
    out: list[Pattern] = []
    for i, _ in highs:
        t = i + k
        if t >= len(close):
            continue
        first = t - window + 1
        inside = [turns[j] for j in range(np.searchsorted(rows, first), np.searchsorted(rows, i, side="right"))]
        g = alternate(inside)
        if not any(p[0] == i and p[2] > 0 for p in g):        # merged into an earlier, higher (or equal) peak
            continue
        out.extend(_match(g, i, t, close, "swing", kinds))
    return sorted(out, key=lambda p: (p.detect, p.kind))


# ----------------------------------------------------------------------------------------------------------- shared

def _match(turns: list[Turn], last_row: int, detect: int, close: np.ndarray, method: str, kinds: tuple[str, ...]) -> list[Pattern]:
    out = []
    if "hs" in kinds:
        e = match_hs(turns, last_row)
        if e is not None:
            pat = Pattern("hs", method, detect, tuple((r, p) for r, p, _ in e), ((e[1][0], e[1][1]), (e[3][0], e[3][1])), None)
            out.append(_complete(pat, close))
    if "dt" in kinds:
        m = match_dt(turns, last_row, close)
        if m is not None:
            e1, ea, neck = m
            pat = Pattern("dt", method, detect, ((e1[0], e1[1]), (ea[0], ea[1])), (neck,), None)
            out.append(_complete(pat, close))
    return out


def _complete(pat: Pattern, close: np.ndarray) -> Pattern:
    c = completion(close, pat.detect, pat.neckline)
    return Pattern(pat.kind, pat.method, pat.detect, pat.points, pat.neck, c)


def detect(df: pd.DataFrame, method: str, **kw) -> list[Pattern]:
    """Patterns in a daily frame with open/high/low/close columns (any case), oldest first; rows are positions."""
    cols = {c.lower(): c for c in df.columns}
    close = df[cols["close"]].to_numpy(dtype=float)
    if method == "kernel":
        return detect_kernel(close, **kw)
    if method == "swing":
        return detect_swing(df[cols["high"]].to_numpy(dtype=float), df[cols["low"]].to_numpy(dtype=float), close, **kw)
    raise ValueError(f"unknown method {method!r}")
