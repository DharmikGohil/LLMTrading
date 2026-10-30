"""Configuration: config/config.yaml + environment variables (.env)."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from indtrader.costs import CostModel


class LLMSettings(BaseModel):
    """Passed through to TradingAgents' config (see tradingagents/default_config.py)."""

    # tradingagents: this machine runs TradingAgents each morning.
    # external: ratings are written by someone else (e.g. the scheduled Claude
    # analyst, see analyst/PLAYBOOK.md) into `signals_dir`; this machine only trades.
    signal_source: Literal["tradingagents", "external"] = "tradingagents"

    llm_provider: str | None = None          # None -> TradingAgents default / TRADINGAGENTS_* env
    deep_think_llm: str | None = None
    quick_think_llm: str | None = None
    backend_url: str | None = None
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
    # Run TradingAgents N times per stock and take a majority vote (LLM output is
    # non-deterministic; disagreement between runs -> Hold). N times the cost.
    runs: int = 1
    analysts: list[str] = Field(default_factory=lambda: ["market", "social", "news", "fundamentals"])
    output_language: str = "English"
    # Indian macro headlines for the News Analyst instead of the US-centric defaults
    global_news_queries: list[str] = Field(default_factory=lambda: [
        "RBI monetary policy repo rate inflation India",
        "Nifty Sensex outlook FII DII flows",
        "India GDP economy budget fiscal deficit",
        "rupee crude oil prices India impact",
        "geopolitical risk global markets",
    ])
    # Fundamentals: SEC EDGAR only covers US filers, so use Yahoo directly
    fundamental_data_vendor: str = "yfinance"


class SecondOpinionSettings(BaseModel):
    """Vibe-Trading investment-committee swarm as a second opinion.

    It can only make the bot MORE conservative: it can block or shrink a buy,
    never create one, and never stops a sell.
    """

    enabled: bool = False
    vibe_python: str = "~/vibe-venv/bin/python"   # interpreter of the separate Vibe-Trading virtualenv
    mode: Literal["veto", "confirm"] = "veto"     # veto: block buys it disagrees with; confirm: buy only if it agrees
    min_confidence: float = 50.0                  # its verdicts below this confidence are ignored (veto) / not enough (confirm)
    on_missing: Literal["hold", "proceed"] = "hold"  # if it failed or has no verdict: skip new buys, or trust TradingAgents alone
    only_when_bullish: bool = True                # only consult it when TradingAgents wants to buy (saves cost)
    timeout_min: float = 45


class StrategySettings(BaseModel):
    # Where entries come from:
    #   hybrid - momentum screen picks the stocks, the LLM rating can only veto/shrink (best-evidenced, default)
    #   llm    - the LLM rating drives entries (TradingAgents-style)
    #   factor - momentum screen alone (the "LLM off" control arm)
    signal_mode: Literal["hybrid", "llm", "factor"] = "hybrid"
    llm_veto_min_confidence: float = 55.0     # hybrid: LLM Underweight/Sell at or above this blocks a buy
    llm_missing: Literal["hold", "proceed"] = "hold"   # hybrid: no LLM review for a candidate -> no new buy / buy anyway
    results_blackout_days: int = 3            # no new buys this many calendar days before a results board meeting
    avoid_surveillance: bool = True           # no new buys in ASM/GSM or trade-for-trade (non-EQ) stocks
    # Target weight (fraction of the per-position allocation) for each rating.
    # None = keep whatever is currently held.
    rating_weights: dict[str, float | None] = Field(default_factory=lambda: {
        "Buy": 1.0, "Overweight": 0.75, "Hold": None, "Underweight": 0.25, "Sell": 0.0,
    })
    trend_filter: bool = True                 # only open/add when close > EMA(trend_ema)
    trend_ema: int = 50
    rsi_max_entry: float = 75.0               # do not chase overbought names
    atr_period: int = 14
    atr_stop_mult: float = 2.0                # fallback stop distance when the LLM gives none
    take_profit_rr: float = 2.5               # fallback target = entry + rr * risk
    min_stop_pct: float = 0.02                # sanity bounds for an LLM-proposed stop
    max_stop_pct: float = 0.15
    max_signal_age_days: int = 3              # do not trade on stale analyses
    reentry_cooldown_days: int = 5            # no re-buy within N calendar days of a stop-loss exit
    min_hold_days: int = 3                    # rating-driven sells wait this long after entry (stops still fire)
    # Market regime: when the index closes below its long moving average, new
    # buys are scaled down (LLM agents tend to be too aggressive in bear markets).
    regime_filter: bool = True
    regime_index: str = "^NSEI"
    regime_sma: int = 200
    bear_market_scale: float = 0.5           # 0 = no new buys in a bear regime
    # Volatility targeting: new buys are scaled by min(1, vol_target / the index's realised volatility over
    # vol_lookback days), so the book buys less in turbulent markets. None = off.
    vol_target: float | None = None          # annualised, e.g. 0.15
    vol_lookback: int = 63


class RiskSettings(BaseModel):
    capital: float = 100000.0                 # rupees the system may deploy (capped by broker funds)
    max_position_pct: float = 0.20            # max allocation per stock
    risk_per_trade_pct: float = 0.01          # rupees lost at stop as fraction of capital
    max_open_positions: int = 5
    max_per_sector: int = 2                   # positions in one NSE industry (screens cluster in hot sectors)
    max_gross_exposure_pct: float = 1.0       # no leverage on CNC
    max_daily_loss_pct: float = 0.03          # kill switch: stop new entries for the day
    max_drawdown_pct: float | None = None     # circuit breaker: no new buys while equity is this far below its peak
    stale_exit_s: int = 120                   # a stop/target sell still working after this long is cancelled and re-priced
    max_orders_per_day: int = 30
    min_order_value: float = 1000.0
    limit_buffer_pct: float = 0.003           # marketable LIMIT = LTP +/- buffer
    max_price_deviation_pct: float = 0.05     # skip if LTP moved >5% from analysed close


class BrokerSettings(BaseModel):
    name: Literal["paper", "zerodha", "openalgo"] = "paper"
    product: Literal["CNC", "MIS"] = "CNC"
    paper_state_file: str = "state/paper_account.json"
    openalgo_host: str = "http://127.0.0.1:5000"
    strategy_tag: str = "indtrader"


class ScheduleSettings(BaseModel):
    analysis_time: str = "08:30"              # IST; TradingAgents runs on previous close data
    execution_time: str = "09:30"             # after opening volatility settles
    monitor_interval_min: int = 5             # stop-loss / target checks
    eod_time: str = "15:05"                   # MIS square-off / daily report (before the 15:15 closing auction)


class ScreenSettings(BaseModel):
    """Momentum + low-vol + trend screen that picks the candidates (indtrader/screen.py)."""

    index: Literal["nifty50", "nifty100", "nifty200", "nifty500", "sp100"] = "nifty200"
    top_n: int = 12
    min_traded_value_cr: float = 20.0        # median daily traded value, Rs crore
    vol_exclude_pct: float = 0.2             # drop the most volatile 20%
    trend_template: bool = False             # also require Minervini's SEPA trend template (stricter)


class Settings(BaseModel):
    universe: list[str] = Field(default_factory=lambda: ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"])
    exchange: Literal["NSE", "BSE", "US"] = "NSE"
    data_dir: str = "state"
    signals_dir: str | None = None            # default <data_dir>/signals; "signals" = tracked in git
    signal_sync: Literal["none", "git"] = "none"   # git: `git pull` before using signals (external analyst)
    extra_holidays: list[date] = Field(default_factory=list)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    second_opinion: SecondOpinionSettings = Field(default_factory=SecondOpinionSettings)
    screen: ScreenSettings = Field(default_factory=ScreenSettings)
    strategy: StrategySettings = Field(default_factory=StrategySettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    costs: dict = Field(default_factory=dict)
    dry_run: bool = False                     # log orders instead of sending them
    nse_checks: bool = True                   # surveillance / results / corporate-action data from nseindia.com
    # Paper "shadow" accounts traded alongside the main one with a different signal_mode,
    # so `indtrader compare` can show whether the LLM adds anything (the research's key control).
    shadow_arms: list[Literal["factor", "llm", "hybrid"]] = Field(default_factory=lambda: ["factor"])

    @property
    def cost_model(self) -> CostModel:
        return CostModel.from_dict(self.costs)

    @property
    def holidays(self) -> set[date]:
        return set(self.extra_holidays)

    @property
    def signals_root(self) -> Path:
        root = Path(self.signals_dir) if self.signals_dir else Path(self.data_dir) / "signals"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def path(self, *parts: str) -> Path:
        p = Path(self.data_dir).joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def load_settings(path: str | os.PathLike | None = None) -> Settings:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # python-dotenv is optional
        pass
    path = Path(path or os.getenv("INDTRADER_CONFIG", "config/config.yaml"))
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    settings = Settings.model_validate(data or {})
    from indtrader.market import configure

    configure(settings.exchange)
    if os.getenv("INDTRADER_BROKER"):
        settings.broker.name = os.environ["INDTRADER_BROKER"]  # type: ignore[assignment]
    return settings
