# Project skills

All eleven skills from [Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill)
(commit 3d0f4ef, MIT, see `LICENSE-day-trader-skill`), copied unchanged with their offline test
suite (`tests/`, run `python3 -m unittest discover -s tests` from this folder). The pack's own
repo-layout test is left out. Standard-library Python; free public data (Yahoo, SEC EDGAR, Nasdaq
Trader, House Clerk). State goes to `trader/` (git-ignored). SEC tools need `SEC_USER_AGENT`
("Name email") in the environment.

How the desks use them:

| Skill | Role here |
|---|---|
| `trader-news` | **US analyst review**: new headlines and SEC 8-K filings for every candidate and holding. |
| `trader-analyst` | **US analyst review**: filed revenue, margins and EPS (XBRL) for any candidate that reported in the last 30 days. |
| `trader-pelosi` | **US analyst review**: Congress trade disclosures in our candidates. Context only, never a reason on its own (disclosures lag up to 45 days). |
| `trader-scanner` | US daily scan (20-day breakouts, flags, oversold) as a cross-check on the momentum screen; its intraday opening-range scan is for a possible later US intraday paper desk. |
| `trader-timemachine` | Odds check for US intraday plans. The Nifty options desk uses the same idea, rebuilt for Nifty: replay Nifty's own moves to expiry before each iron condor. |
| `trader-entry`, `trader-exit`, `trader-budget`, `trader-risk`, `trader-alerts` | The intraday trade pipeline (entry timing, stop/target, sizing, limits, alerts). Available for a US intraday paper experiment; the swing desks keep `indtrader`'s own sizing and risk engine. |
| `trader-broker` | Alpaca order tickets, paper by default and never without an explicit yes. Not connected: the desks trade on `indtrader`'s paper broker. |
