"""Turn an LLM rating + technical snapshot into a target position.

Long-only cash equity (CNC): Indian delivery trades cannot be shorted, so
bearish ratings only reduce what the bot holds.

  Buy / Overweight     -> may ADD up to weight * per-position allocation,
                          only if the trend/RSI filters agree
  Hold / REVIEW / stale -> keep the current quantity
  Underweight / Sell   -> may only TRIM, down to weight * allocation
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from indtrader.config import RiskSettings, StrategySettings
from indtrader.signals.technical import TechnicalSnapshot

BULLISH = ("Buy", "Overweight")
BEARISH = ("Underweight", "Sell")


@dataclass
class TargetPlan:
    symbol: str
    target_qty: int
    stop: float | None = None
    take_profit: float | None = None
    notes: list[str] = field(default_factory=list)


def protective_levels(price: float, tech: TechnicalSnapshot, s: StrategySettings,
                      llm_stop: float | None = None, llm_target: float | None = None) -> tuple[float, float]:
    """Stop-loss and take-profit for a long entered at `price`."""
    stop = None
    atr = tech.atr if math.isfinite(tech.atr) and tech.atr > 0 else s.min_stop_pct * price / max(s.atr_stop_mult, 1e-9)
    if llm_stop and 0 < llm_stop < price:
        dist = (price - llm_stop) / price
        if s.min_stop_pct <= dist <= s.max_stop_pct:
            stop = llm_stop
    if stop is None:
        dist = min(max(s.atr_stop_mult * atr / price, s.min_stop_pct), s.max_stop_pct)
        stop = price * (1 - dist)
    take = llm_target if llm_target and llm_target > price * (1 + s.min_stop_pct) else price + s.take_profit_rr * (price - stop)
    return round(stop, 2), round(take, 2)


def plan_target(symbol: str, rating: str | None, price: float, tech: TechnicalSnapshot, current_qty: int,
                capital: float, s: StrategySettings, r: RiskSettings,
                llm_stop: float | None = None, llm_target: float | None = None,
                bear_market: bool = False, held_days: int | None = None) -> TargetPlan:
    plan = TargetPlan(symbol, current_qty)
    if not (math.isfinite(price) and price > 0):
        plan.notes.append(f"invalid price {price}; holding {current_qty}")
        return plan
    if rating is None or rating not in s.rating_weights:
        plan.notes.append(f"no tradeable rating ({rating}); holding {current_qty}")
        return plan
    weight = s.rating_weights[rating]
    if weight is None:
        plan.notes.append(f"{rating}: keep {current_qty}")
        return plan

    stop, take = protective_levels(price, tech, s, llm_stop, llm_target)
    alloc_qty = math.floor(capital * r.max_position_pct * weight / price)
    risk_per_share = price - stop
    risk_qty = math.floor(capital * r.risk_per_trade_pct / risk_per_share) if risk_per_share > 0 else 0
    sized = min(alloc_qty, risk_qty) if weight > 0 else 0
    if rating in BULLISH and bear_market:
        sized = math.floor(sized * s.bear_market_scale)
        plan.notes.append(f"bear regime: size x{s.bear_market_scale:g}")

    if rating in BULLISH:
        if sized <= current_qty:
            plan.notes.append(f"{rating}: already at/above size ({current_qty} >= {sized})")
            return plan
        if s.trend_filter and not tech.uptrend:
            plan.notes.append(f"{rating} but close {tech.close:.2f} <= EMA{s.trend_ema} {tech.ema_trend:.2f}; not adding")
            return plan
        if tech.rsi > s.rsi_max_entry:
            plan.notes.append(f"{rating} but RSI {tech.rsi:.0f} > {s.rsi_max_entry:.0f}; not chasing")
            return plan
        plan.target_qty, plan.stop, plan.take_profit = sized, stop, take
        plan.notes.append(f"{rating}: add to {sized} (alloc {alloc_qty}, risk-sized {risk_qty}) stop {stop} tp {take}")
    elif rating in BEARISH:
        if current_qty and held_days is not None and held_days < s.min_hold_days:
            plan.notes.append(f"{rating} but held {held_days}d < min {s.min_hold_days}d; keeping (stop still active)")
            return plan
        plan.target_qty = min(current_qty, sized)
        plan.notes.append(f"{rating}: trim {current_qty} -> {plan.target_qty}")
    return plan


def combine_opinions(primary: str | None, second, cfg) -> tuple[str | None, str]:
    """Merge the TradingAgents rating with the Vibe-Trading second opinion.

    The second opinion can only reduce risk: bearish/neutral primary ratings
    pass through unchanged; a bullish one can be downgraded to Hold (no new
    buys, keep what is held) or from Buy to Overweight (smaller size).
    `second` is an LLMSignal or None.
    """
    if not cfg.enabled or primary not in BULLISH:
        return primary, ""
    if second is None or second.rating not in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
        if cfg.on_missing == "proceed":
            return primary, "second opinion missing; proceeding on TradingAgents alone"
        return "Hold", "second opinion missing; no new buys"
    conf = second.confidence
    confident = conf is None or conf >= cfg.min_confidence
    tag = f"Vibe-Trading {second.rating}" + (f" ({conf:.0f}%)" if conf is not None else "")
    if cfg.mode == "confirm":
        if second.rating in BULLISH and confident:
            return primary, f"{tag} confirms"
        return "Hold", f"{tag} does not confirm; no new buys"
    # veto mode
    if second.rating in BEARISH and confident:
        return "Hold", f"{tag} vetoes the buy"
    if second.rating == "Hold" and primary == "Buy" and confident:
        return "Overweight", f"{tag}: Buy softened to Overweight"
    return primary, f"{tag} does not object"
