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

    llm_provider: str | None = None          # None -> TradingAgents default / TRADINGAGENTS_* env
    deep_think_llm: str | None = None
    quick_think_llm: str | None = None
    backend_url: str | None = None
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
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


class StrategySettings(BaseModel):
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


class RiskSettings(BaseModel):
    capital: float = 100000.0                 # rupees the system may deploy (capped by broker funds)
    max_position_pct: float = 0.20            # max allocation per stock
    risk_per_trade_pct: float = 0.01          # rupees lost at stop as fraction of capital
    max_open_positions: int = 5
    max_gross_exposure_pct: float = 1.0       # no leverage on CNC
    max_daily_loss_pct: float = 0.03          # kill switch: stop new entries for the day
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
    eod_time: str = "15:20"                   # MIS square-off / daily report


class Settings(BaseModel):
    universe: list[str] = Field(default_factory=lambda: ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"])
    exchange: Literal["NSE", "BSE"] = "NSE"
    data_dir: str = "state"
    extra_holidays: list[date] = Field(default_factory=list)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    strategy: StrategySettings = Field(default_factory=StrategySettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    costs: dict = Field(default_factory=dict)
    dry_run: bool = False                     # log orders instead of sending them

    @property
    def cost_model(self) -> CostModel:
        return CostModel.from_dict(self.costs)

    @property
    def holidays(self) -> set[date]:
        return set(self.extra_holidays)

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
    if os.getenv("INDTRADER_BROKER"):
        settings.broker.name = os.environ["INDTRADER_BROKER"]  # type: ignore[assignment]
    return settings
