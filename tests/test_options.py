from datetime import date, datetime

import pytest

from indtrader.options import (
    LOT,
    Chain,
    OptionCosts,
    OptionsBook,
    OptionsDesk,
    Quote,
    exit_reason,
    last_trading_day_before,
    plan_iron_condor,
    plan_lotto,
    trading_days_between,
)


def make_chain(spot=23300.0, iv=15.0, expiry=date(2026, 11, 9), shift=0.0):
    """A toy chain: premiums fall with distance from the spot; `shift` moves the spot to reprice."""
    ch = Chain(expiry, spot + shift, "t")
    for k in range(21000, 25600, 50):
        dc, dp = max(k - (spot + shift), 0), max((spot + shift) - k, 0)
        intrinsic_c, intrinsic_p = max((spot + shift) - k, 0), max(k - (spot + shift), 0)
        c = intrinsic_c + 300 * 2.718 ** (-dc / 250)
        p = intrinsic_p + 300 * 2.718 ** (-dp / 250)
        ch.calls[k] = Quote(round(c * 0.99, 2), round(c * 1.01, 2), iv)
        ch.puts[k] = Quote(round(p * 0.99, 2), round(p * 1.01, 2), iv)
    return ch


def test_charges_follow_the_rules():
    c = OptionCosts()
    sell, buy = c.charges("SELL", 100, LOT), c.charges("BUY", 100, LOT)
    assert sell - buy == pytest.approx(6500 * (0.0015 - 0.00003), abs=0.02)   # STT on sales, stamp on buys
    assert buy == pytest.approx(20 + 6500 * 0.0003563 + 6500 * 0.00003 + (20 + 6500 * 0.0003563) * 0.18, abs=0.02)


def test_iron_condor_is_defined_risk_and_wider_with_the_gate():
    ch = make_chain()
    legs = plan_iron_condor(ch, date(2026, 11, 2))
    sc, sp, lc, lp = legs
    assert (sc.kind, sc.side, lc.side) == ("CE", "SELL", "BUY") and lc.strike == sc.strike + 200 and lp.strike == sp.strike - 200
    assert sp.strike < ch.spot < sc.strike
    credit = sc.entry + sp.entry - lc.entry - lp.entry
    assert 0 < credit < 200
    wide = plan_iron_condor(ch, date(2026, 11, 2), sd_mult=1.25)
    assert wide[0].strike > sc.strike and wide[1].strike < sp.strike


def test_book_pnl_take_profit_stop_and_time_exit(tmp_path):
    ch = make_chain()
    book = OptionsBook(tmp_path / "b.json", 100000)
    legs = plan_iron_condor(ch, date(2026, 11, 2))
    book.enter("iron condor", legs, ch.expiry, "t", 10000)
    m = book.mark(ch)
    assert m["pnl"] < 0                                   # paying the spread to get out right away
    monday = datetime(2026, 11, 3, 11, 0)
    assert exit_reason(book, ch, monday) is None
    calm = make_chain()                                    # time decay: options at a fraction of their value
    for book_ in (calm.calls, calm.puts):
        for k, q in book_.items():
            book_[k] = Quote(round(q.bid * 0.3, 2), round(q.ask * 0.3, 2), q.iv)
    assert exit_reason(book, calm, monday).startswith("take profit")
    crash = make_chain(shift=-700)
    assert exit_reason(book, crash, monday).startswith("stop")
    friday_late = datetime(2026, 11, 6, 15, 20)
    assert exit_reason(book, ch, friday_late).startswith("time exit")
    closed = book.exit(crash, "stop")
    assert closed["pnl"] < 0 and book.open is None
    assert book.data["cash"] == pytest.approx(100000 + closed["pnl"], abs=0.05)
    credit = sum(lg.entry if lg.side == "SELL" else -lg.entry for lg in legs)
    max_loss = (200 - credit) * LOT
    spread = sum((crash.quote(lg.kind, lg.strike).ask - crash.quote(lg.kind, lg.strike).bid) * lg.qty for lg in legs)
    assert closed["pnl"] >= -max_loss - spread - 400     # bounded by the wings, plus the exit spread and charges


def test_lotto_fits_budget_and_doubles(tmp_path):
    ch = make_chain()
    legs = plan_lotto(ch, "up", 1000)
    assert legs and legs[0].kind == "CE" and legs[0].entry * LOT <= 1000 and legs[0].strike > ch.spot
    book = OptionsBook(tmp_path / "l.json", 1000)
    book.enter("lotto", legs, ch.expiry, "t", legs[0].entry * LOT)
    up = make_chain(shift=600)
    assert exit_reason(book, up, datetime(2026, 11, 3, 11, 0)).startswith("target")
    assert plan_lotto(ch, "down", 1) is None


def test_calendar_helpers():
    assert trading_days_between(date(2026, 11, 2), date(2026, 11, 9)) == 5
    assert last_trading_day_before(date(2026, 11, 9)) == date(2026, 11, 6)


class FakeNSE:
    def __init__(self, chain):
        self.ch = chain

    def expiries(self):
        return [date(2026, 11, 3), date(2026, 11, 9), date(2026, 11, 17)]

    def chain(self, expiry):
        return self.ch


def test_desk_needs_a_gate_for_the_llm_account(tmp_path):
    desk = OptionsDesk(tmp_path, FakeNSE(make_chain()))
    out = {r["arm"]: r for r in desk.enter_all(date(2026, 11, 2), 0.01)}
    assert "skipped" in out["main"] and "legs" in out["control"] and out["lotto"]["legs"][0]["kind"] == "CE"
    assert out["control"]["expiry"] == "2026-11-09"                 # not the 3 Nov expiry (1 trading day left)
    desk.set_gate(date(2026, 11, 2), "widen", "none", "US midterms 3 Nov")
    out = {r["arm"]: r for r in desk.enter_all(date(2026, 11, 2), 0.01)}
    assert "legs" in out["main"] and "1.25 SD" in out["main"]["note"]
    assert set(out) == {"main"}                                      # the others are already open


def test_lotto_stakes_at_most_1000_and_keeps_winnings(tmp_path):
    from indtrader.options import LOTTO_STAKE
    desk = OptionsDesk(tmp_path, FakeNSE(make_chain()))
    desk.books["lotto"].data["cash"] = 8675.0          # after two winning trades
    out = {r["arm"]: r for r in desk.enter_all(date(2026, 11, 2), 0.01)}
    leg = out["lotto"]["legs"][0]
    assert leg["entry"] * LOT <= LOTTO_STAKE                   # stake capped, not the whole balance
    assert desk.books["lotto"].data["cash"] >= 8675.0 - LOTTO_STAKE - 50   # winnings stay in the account
