# Project skills

`trader-analyst` and `trader-news` come from
[Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill)
(commit 3d0f4ef, MIT, see `LICENSE-day-trader-skill`), copied unchanged.
They serve the US desk's analyst review:

- `trader-analyst`: reported revenue, margins and EPS straight from SEC EDGAR filings (XBRL),
  quarter by quarter against the year before, plus the latest earnings 8-K.
- `trader-news`: new headlines and SEC 8-K filings per ticker since the last check.

Both need `SEC_USER_AGENT` ("Name email") set in the environment, as SEC requires. They write
state to `trader/` (git-ignored). The other skills in that pack (intraday opening-range day trading,
Congress-trade tracking, an Alpaca order executor) were left out: they are US-only intraday tools
and don't fit the desks.
