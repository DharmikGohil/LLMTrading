"""Trading journal: graded facts every close, lessons that must earn their status.

Why: the bot cannot retrain the LLM, but every analyst run reads `lessons.json`
first, so what the desk learns shapes the next decisions (in-context learning).
Research on LLM trading memory (FinMem, FinCon) shows memories built from single
outcomes are fragile, so a lesson starts as a *hypothesis* and is *confirmed*
only with repeated independent evidence; contrary evidence retires it.

Files (tracked in git):
  journal/lessons.json          the lesson book
  journal/daily/<date>-<mkt>.md one review per desk per day (facts + reflection)
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path("journal")
CONFIRM_AT = 3          # independent supporting cases needed to confirm a lesson


@dataclass
class Lesson:
    id: str
    lesson: str
    market: str = "all"                    # US | India | all
    status: str = "hypothesis"             # hypothesis | confirmed | retired
    evidence_for: int = 1
    evidence_against: int = 0
    first_seen: str = ""
    last_seen: str = ""
    examples: list[str] = field(default_factory=list)

    def refresh_status(self) -> None:
        if self.evidence_against >= self.evidence_for + 2:
            self.status = "retired"
        elif self.evidence_for >= CONFIRM_AT and self.evidence_for >= 2 * self.evidence_against:
            self.status = "confirmed"
        else:
            self.status = "hypothesis"


class LessonBook:
    def __init__(self, root: Path = ROOT):
        self.file = root / "lessons.json"
        data = json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else []
        self.lessons = [Lesson(**d) for d in data]

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps([asdict(x) for x in self.lessons], indent=1, ensure_ascii=False), encoding="utf-8")

    def get(self, lesson_id: str) -> Lesson:
        for x in self.lessons:
            if x.id == lesson_id:
                return x
        raise KeyError(f"no lesson {lesson_id!r}")

    def add(self, text: str, market: str, example: str, today: date) -> Lesson:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "lesson"
        lid, n = slug, 2
        while any(x.id == lid for x in self.lessons):
            lid, n = f"{slug}-{n}", n + 1
        x = Lesson(id=lid, lesson=text.strip(), market=market, first_seen=today.isoformat(),
                   last_seen=today.isoformat(), examples=[example] if example else [])
        x.refresh_status()
        self.lessons.append(x)
        return x

    def evidence(self, lesson_id: str, supports: bool, example: str, today: date) -> Lesson:
        x = self.get(lesson_id)
        if supports:
            x.evidence_for += 1
        else:
            x.evidence_against += 1
        x.last_seen = today.isoformat()
        if example:
            x.examples = (x.examples + [("+ " if supports else "- ") + example])[-8:]
        x.refresh_status()
        return x

    def active(self, market: str | None = None) -> list[Lesson]:
        order = {"confirmed": 0, "hypothesis": 1}
        keep = [x for x in self.lessons if x.status != "retired" and (market is None or x.market in (market, "all"))]
        return sorted(keep, key=lambda x: (order[x.status], -x.evidence_for))


# --------------------------------------------------------------- daily facts
def _excess(px: pd.Series, idx: pd.Series, start: str, horizon: int) -> float | None:
    """Stock minus index return (%) from the first close after `start` over `horizon` closes."""
    after = px.index[px.index > pd.Timestamp(start)]
    if len(after) < horizon + 1:
        return None
    t0, t1 = after[0], after[horizon]
    i = idx.loc[t0:t1]
    if len(i) < 2:
        return None
    return round(100 * ((px.loc[t1] / px.loc[t0] - 1) - (i.iloc[-1] / i.iloc[0] - 1)), 2)


def daily_facts(signals_root: Path, books: dict[str, Path], today: date, closes, index_closes: pd.Series,
                horizons=(1, 5)) -> dict:
    """Numbers for the close-of-day review. `closes(symbol)` -> Series of daily closes."""
    calls, vetoes, trades = [], [], []
    days = sorted(p.name for p in signals_root.iterdir() if p.is_dir()) if signals_root.exists() else []
    for d in days[-30:]:
        for f in (signals_root / d).glob("*.json"):
            if f.stem.startswith("_"):
                continue
            g = json.loads(f.read_text(encoding="utf-8"))
            try:
                px = closes(g["symbol"])
            except Exception:
                continue
            row = {"date": d, "symbol": g["symbol"], "rating": g.get("rating"), "confidence": g.get("confidence")}
            for h in horizons:
                row[f"excess_{h}d"] = _excess(px, index_closes, d, h)
            calls.append(row)
    dec = books.get("main")
    seen = set()
    if dec and (dec / "decisions.json").exists():
        for r in json.loads((dec / "decisions.json").read_text(encoding="utf-8")):
            if "veto" not in r.get("decision", "") or (r["as_of"], r["symbol"]) in seen:
                continue
            seen.add((r["as_of"], r["symbol"]))
            try:
                px = closes(r["symbol"])
            except Exception:
                continue
            v = {"date": r["as_of"], "symbol": r["symbol"], "decision": r["decision"]}
            for h in horizons:
                v[f"excess_{h}d"] = _excess(px, index_closes, r["as_of"], h)   # negative = veto helped
            vetoes.append(v)
    for book, d in books.items():
        f = d / "trades.csv"
        if f.exists():
            with f.open(encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if r["time"][:10] == today.isoformat():
                        trades.append({"book": book, "side": r["side"], "symbol": r["symbol"], "qty": r["fill_qty"],
                                       "price": r["fill_price"], "status": r["status"], "reason": r["reason"][:160]})
    return {"calls": calls, "vetoes": vetoes, "trades": trades}


def _table(rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return "_none_\n"
    out = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for r in rows:
        out += "| " + " | ".join("" if r.get(c) is None else str(r.get(c)) for c in cols) + " |\n"
    return out


def write_daily(market: str, today: date, facts: dict, accounts: list[dict], root: Path = ROOT) -> Path:
    """Write the facts part of today's review; the close run then fills in the reflection."""
    f = root / "daily" / f"{today.isoformat()}-{market.lower()}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    graded = [c for c in facts["calls"] if c.get("excess_1d") is not None]
    reflection = "_To be written by the close run: what worked, what didn't, candidate lessons._\n"
    if f.exists() and "## Reflection" in f.read_text(encoding="utf-8"):
        reflection = f.read_text(encoding="utf-8").split("## Reflection", 1)[1].lstrip("\n")
    text = (f"# {market} desk review, {today.isoformat()}\n\n## Accounts\n"
            + _table(accounts, ["book", "equity", "return_pct"])
            + "\n## Orders today\n" + _table(facts["trades"], ["book", "side", "symbol", "qty", "price", "status", "reason"])
            + "\n## Vetoes and what happened next (excess vs index, %; negative = the veto helped)\n"
            + _table(facts["vetoes"], ["date", "symbol", "excess_1d", "excess_5d"])
            + "\n## Analyst calls with outcomes (excess vs index, %)\n"
            + _table(graded, ["date", "symbol", "rating", "confidence", "excess_1d", "excess_5d"])
            + "\n## Reflection\n" + reflection)
    f.write_text(text, encoding="utf-8")
    return f
