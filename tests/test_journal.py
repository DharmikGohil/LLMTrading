import json
from datetime import date

import numpy as np
import pandas as pd

from indtrader.journal import LessonBook, daily_facts, write_daily

D = date(2026, 10, 28)


def test_lesson_lifecycle(tmp_path):
    book = LessonBook(tmp_path)
    x = book.add("Veto entries when results are due within 3 trading days", "US", "2026-10-28 LLY/MRK vetoed", D)
    assert x.status == "hypothesis" and x.evidence_for == 1
    book.evidence(x.id, True, "case 2", D)
    assert book.get(x.id).status == "hypothesis"
    book.evidence(x.id, True, "case 3", D)
    assert book.get(x.id).status == "confirmed"
    for i in range(4):
        book.evidence(x.id, False, f"miss {i}", D)
    assert book.get(x.id).status == "hypothesis"            # 3 for / 4 against: no longer confirmed
    book.evidence(x.id, False, "miss 5", D)
    assert book.get(x.id).status == "retired"               # against >= for + 2
    book.save()
    again = LessonBook(tmp_path)
    assert again.active() == [] and len(again.lessons) == 1
    assert book.add("Veto entries when results are due within 3 trading days", "US", "x", D).id.endswith("-2")


def test_daily_facts_and_file(tmp_path):
    sig = tmp_path / "signals" / "2026-10-20"
    sig.mkdir(parents=True)
    (sig / "AAA.json").write_text(json.dumps({"symbol": "AAA", "rating": "Underweight", "confidence": 70}))
    book = tmp_path / "book"
    book.mkdir()
    (book / "decisions.json").write_text(json.dumps([
        {"time": "t", "as_of": "2026-10-20", "symbol": "AAA",
         "decision": "momentum Buy; LLM: claude-analyst Underweight (70%) vetoes the buy"}]))
    (book / "trades.csv").write_text("time,symbol,side,qty,limit,status,fill_qty,fill_price,order_id,reason,message\n"
                                     "2026-10-28T10:00:00-04:00,BBB,BUY,5,10,COMPLETE,5,10,x,momentum Buy,\n")
    idx = pd.bdate_range("2026-10-19", periods=10)
    px = pd.Series(np.linspace(100, 90, 10), idx)                  # AAA fell 10%
    nifty = pd.Series(100.0, idx)
    facts = daily_facts(tmp_path / "signals", {"main": book}, D, lambda s: px, nifty)
    assert facts["vetoes"][0]["excess_1d"] < 0 and facts["vetoes"][0]["excess_5d"] < 0   # the veto helped
    assert facts["calls"][0]["excess_5d"] < 0
    assert facts["trades"][0]["symbol"] == "BBB"
    f = write_daily("US", D, facts, [{"book": "main", "equity": 10000, "return_pct": 0}], tmp_path)
    text = f.read_text()
    assert "Vetoes" in text and "AAA" in text and "## Reflection" in text
    f.write_text(text.replace("_To be written by the close run: what worked, what didn't, candidate lessons._", "My reflection"))
    write_daily("US", D, facts, [], tmp_path)                       # re-run keeps the reflection
    assert "My reflection" in f.read_text()
