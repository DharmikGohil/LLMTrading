"""Snapshot everything the public dashboard shows, as JSON row files.

`indtrader export-dashboard` reads each configured account (main + shadow arms)
and writes summary / positions / trades / decisions / signals / equity files.
Each run also appends an intraday equity point, so the equity chart moves
during the session.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from indtrader.config import Settings
from indtrader.market import is_us, now_ist

BOOK_LABEL = {"main": "LLM-reviewed (hybrid)", "factor": "LLM off (momentum only)", "llm": "LLM-driven", "hybrid": "LLM-reviewed (hybrid)"}


def _books(s: Settings) -> dict[str, Path]:
    books = {"main": Path(s.data_dir)}
    for arm in s.shadow_arms:
        p = Path(s.data_dir) / "arms" / arm
        if p.exists():
            books[arm] = p
    return books


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except ValueError:
        return default


def export(s: Settings, out_dir: Path, prices_fn) -> dict[str, list]:
    market = "US" if is_us() else "India"
    ccy = "USD" if is_us() else "INR"
    now = now_ist().isoformat(timespec="seconds")
    summary, positions, trades, decisions, equity = [], [], [], [], []
    try:
        index_close = round(float(prices_fn(s.strategy.regime_index)), 2)
    except Exception:
        index_close = None

    for book, d in _books(s).items():
        state = _read_json(d / "bot_state.json", {})
        pos = state.get("positions", {})
        prices = {}
        for sym in pos:
            try:
                prices[sym] = float(prices_fn(sym))
            except Exception:
                prices[sym] = pos[sym]["avg"]
        cash = float(state.get("cash", s.risk.capital))
        mv = sum(p["qty"] * prices[sym] for sym, p in pos.items())
        unreal = sum(p["qty"] * (prices[sym] - p["avg"]) for sym, p in pos.items())
        equity_now = cash + mv
        n_trades = 0
        tfile = d / "trades.csv"
        if tfile.exists():
            with tfile.open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    n_trades += 1
                    trades.append({"time": r["time"], "market": market, "book": book, "symbol": r["symbol"],
                                   "side": r["side"], "qty": int(float(r["fill_qty"] or 0)) or int(r["qty"]),
                                   "price": float(r["fill_price"]) if r["fill_price"] else None,
                                   "status": r["status"], "reason": r["reason"]})
        for sym, p in pos.items():
            px = prices[sym]
            positions.append({"market": market, "book": book, "symbol": sym, "qty": p["qty"], "avg_price": p["avg"],
                              "last_price": round(px, 2), "value": round(p["qty"] * px, 2),
                              "unrealized": round(p["qty"] * (px - p["avg"]), 2),
                              "unrealized_pct": round(100 * (px / p["avg"] - 1), 2) if p["avg"] else None,
                              "stop": p.get("stop"), "target": p.get("target"), "opened": p.get("opened")})
        for row in _read_json(d / "decisions.json", [])[-300:]:
            decisions.append({"market": market, "book": book, **row})
        # intraday equity log (appended each export)
        eq_file = d / "equity_intraday.csv"
        new = not eq_file.exists()
        with eq_file.open("a", encoding="utf-8") as f:
            if new:
                f.write("time,equity,index_close\n")
            f.write(f"{now},{equity_now:.2f},{index_close if index_close is not None else ''}\n")
        with eq_file.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                equity.append({"time": r["time"], "market": market, "book": book, "equity": float(r["equity"]),
                               "index_close": float(r["index_close"]) if r["index_close"] else None})
        summary.append({"market": market, "book": book, "label": BOOK_LABEL.get(book, book), "currency": ccy,
                        "start_capital": s.risk.capital, "equity": round(equity_now, 2), "cash": round(cash, 2),
                        "return_pct": round(100 * (equity_now / s.risk.capital - 1), 3),
                        "realized_pnl": round(float(state.get("realized_pnl", 0.0)), 2),
                        "unrealized_pnl": round(unreal, 2), "open_positions": len(pos), "trades": n_trades,
                        "updated": now})

    # index return since the first equity point, per market
    idx_pts = [e for e in equity if e["index_close"] and e["book"] == "main"]
    if idx_pts:
        first = idx_pts[0]["index_close"]
        for r in summary:
            r["index_return_pct"] = round(100 * (idx_pts[-1]["index_close"] / first - 1), 3)

    signals = []
    root = s.signals_root
    for day in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True)[:30] if root.exists() else []:
        screen = _read_json(day / "_screen.json", {})
        ranks = {r["symbol"]: r.get("rank") for r in screen.get("table", [])}
        for f in sorted(day.glob("*.json")):
            if f.stem.startswith("_"):
                continue
            g = _read_json(f, {})
            signals.append({"date": g.get("as_of", day.name), "market": market, "symbol": g.get("symbol"),
                            "rating": g.get("rating"), "confidence": g.get("confidence"), "source": g.get("source"),
                            "screen_rank": ranks.get(g.get("symbol")), "stop": g.get("stop_loss"),
                            "target": g.get("price_target"), "thesis": g.get("summary", "")[:600]})

    for r in summary:
        r["id"] = f"{market}:{r['book']}"
    for i, r in enumerate(trades):
        r["id"] = f"{market}:{r['book']}:{i}"
    for r in positions:
        r["id"] = f"{market}:{r['book']}:{r['symbol']}"
    for i, r in enumerate(decisions):
        r["id"] = f"{market}:{r['book']}:{i}"
    for r in signals:
        r["id"] = f"{market}:{r['date']}:{r['symbol']}"
    for i, r in enumerate(equity):
        r["id"] = f"{market}:{r['book']}:{i}"
    out = {"summary": summary, "positions": positions, "trades": trades, "decisions": decisions,
           "signals": signals, "equity": equity}
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in out.items():
        (out_dir / f"{market.lower()}_{name}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return out
