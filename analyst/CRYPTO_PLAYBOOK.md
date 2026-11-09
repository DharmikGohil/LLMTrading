# Crypto desk: playbook for the scheduled analyst runs

The crypto paper desk trades by itself on GitHub Actions (`.github/workflows/crypto-desk.yml`):
- daily at 00:10 UTC: the weekly rebalance, when it is due
- every 2 hours: apply today's gate and record equity

Your job is the **gate** for the LLM-gated account. You never place orders and never edit code. Paper money only.

| Account | Rules |
|---|---|
| `main` | The momentum strategy, subject to your gate |
| `control` | The same strategy, rules only (no gate) |
| `hold` | BTC bought once and held: the benchmark |

The gate can only make `main` **safer**: it caps the share of the account in coins (`--exposure`, 0-1) and/or
excludes coins (`--exclude`). It cannot add a coin or raise exposure. Whether the gate adds value is measured by
`main` against `control`.

## 0. Setup
```bash
cd /home/user/LLMTrading 2>/dev/null || { git clone https://github.com/DharmikGohil/LLMTrading /home/user/LLMTrading && cd /home/user/LLMTrading; }
git fetch origin main && git checkout main && git pull --ff-only origin main
git config user.name "dharmikgohil" && git config user.email "gohildharmik2020@gmail.com"
pip install -q pandas numpy pydantic pyyaml python-dotenv requests typer yfinance && pip install -q --no-deps -e .
indtrader crypto-status
```

## 1. What the strategy will hold next
- `paper/crypto/main.json` and `control.json` show the holdings and `last_rebalance`. The next rebalance is 7 days
  after it, at the first 00:10 UTC run.
- The candidates are the coins the momentum rule would pick: today's most-traded Binance USDT pairs, ranked by their
  90-day return, each above its 50-day average, and only while BTC is above its 100-day average.

## 2. Check the next 24-48 hours for events (web search, cite sources and dates)
- **Macro:** FOMC decisions and minutes, US CPI/PCE, US jobs report, large options expiries (Deribit monthly and
  quarterly).
- **Coin-specific, for each holding and likely candidate:**
  - exchange or protocol hacks and exploits
  - large token unlocks (over 2% of supply)
  - Binance delisting or "monitoring tag" announcements
  - SEC/CFTC actions
  - stablecoin de-pegs
  - chain halts
  - founder or insider dumping
- **Market stress:** a BTC move of more than 8% in 24h, funding rates at extremes, or a large liquidation cascade.

## 3. Decide the gate
| Situation | Gate |
|---|---|
| Nothing material | `--exposure 1` (no limit) |
| A major macro event in the next 24 hours (FOMC, CPI) while holding high-volatility coins | `--exposure 0.5` |
| A coin-specific red flag (hack, delisting notice, unlock over 5%, regulatory action) | `--exclude COIN` |
| Systemic stress (an exchange failure, a stablecoin de-peg, BTC −15% in 24h) | `--exposure 0` |

```bash
indtrader crypto-gate --exposure 1 --exclude "" --note "No material events before the next rebalance: FOMC on 9 Dec (Fed calendar), no unlocks over 2% for the holdings (Token Unlocks, <date>)."
```
Every note cites its sources and dates. **No invented facts.** If you cannot verify an event, do not act on it.

## 4. Save
```bash
indtrader crypto-export --out public && cp public/crypto.json web/data/crypto.json
git add paper/crypto public/crypto.json web/data/crypto.json && git commit -m "Crypto gate <date>" && git push origin main
```
Retry the push up to 4 times (2s/4s/8s/16s). If it is rejected because the branch moved, run
`git pull --rebase origin main` and push again.

Finish with three lines: account values against BTC holding, the gate you set and why, and anything unusual.
