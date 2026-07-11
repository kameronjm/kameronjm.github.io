from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.math_engine import (
    calculate_expected_value,
)
from src.database.models import (
    CustomModelConfiguration,
    Fixture,
    HistoricalStats,
    MarketOdds,
    ModelCoefficients,
)
from src.models.features import (
    FeatureMatrixBuilder,
    flatten_boxscore_json,
    predict_from_coefficients,
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    units_won: float = 0.0
    units_lost: float = 0.0
    net_units: float = 0.0
    win_percentage: float = 0.0
    roi_percentage: float = 0.0
    bankroll_history: list[float] = field(default_factory=list)
    max_drawdown: float = 0.0
    bet_log: list[dict[str, Any]] = field(default_factory=list)


def _calculate_drawdown(bankroll_history: list[float]) -> float:
    if len(bankroll_history) < 2:
        return 0.0
    peak = bankroll_history[0]
    max_dd = 0.0
    for val in bankroll_history:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 4)


async def run_backtest(
    session: AsyncSession,
    config: CustomModelConfiguration,
    coefficients: ModelCoefficients,
    start_date: datetime,
    end_date: datetime,
    ev_threshold: float = 3.0,
    unit_size: float = 1.0,
) -> BacktestResult:
    feature_list: list[str] = (
        coefficients.metadata_extra.get("feature_names", []) if coefficients.metadata_extra else []
    )
    if not feature_list:
        raw = config.feature_list
        feature_list = raw.get("features", raw) if isinstance(raw, dict) else raw

    builder = FeatureMatrixBuilder(
        feature_keys=feature_list,
        rolling_window=config.rolling_window,
    )

    stmt = (
        select(Fixture)
        .where(
            Fixture.status == "final",
            Fixture.scheduled_at >= start_date,
            Fixture.scheduled_at <= end_date,
        )
        .order_by(Fixture.scheduled_at.asc())
    )
    result_q = await session.execute(stmt)
    fixtures = result_q.scalars().all()

    bt = BacktestResult()
    bankroll = 100.0
    bt.bankroll_history.append(bankroll)

    for fixture in fixtures:
        home_rows = await _get_team_history(
            session, fixture.home_team_id, builder, fixture.scheduled_at
        )
        away_rows = await _get_team_history(
            session, fixture.away_team_id, builder, fixture.scheduled_at
        )

        feature_vector = builder.build_rolling_feature_vector(home_rows, away_rows)

        projection = predict_from_coefficients(
            feature_vector, coefficients.intercept, coefficients.weights
        )

        odds_stmt = (
            select(MarketOdds)
            .where(MarketOdds.fixture_id == fixture.id)
            .order_by(MarketOdds.captured_at.desc())
        )
        odds_result = await session.execute(odds_stmt)
        odds_rows = odds_result.scalars().all()

        for odds_record in odds_rows:
            fair_prob = _projection_to_probability(
                projection,
                config.target_type,
                config.target_stat,
                odds_record,
                fixture,
            )
            if fair_prob is None:
                continue

            ev = calculate_expected_value(fair_prob, odds_record.odds_american)

            if ev.ev_percentage <= ev_threshold:
                continue

            actual_won = _did_bet_win(
                config.target_type,
                config.target_stat,
                odds_record,
                fixture,
                projection,
            )

            bt.total_bets += 1
            if actual_won:
                bt.wins += 1
                payout = unit_size * (ev.decimal_odds - 1)
                bt.units_won += payout
                bankroll += payout
            else:
                bt.losses += 1
                bt.units_lost += unit_size
                bankroll -= unit_size

            bt.bankroll_history.append(round(bankroll, 4))
            bt.bet_log.append(
                {
                    "fixture_id": str(fixture.id),
                    "sportsbook": odds_record.sportsbook,
                    "market_type": odds_record.market_type,
                    "selection": odds_record.selection,
                    "odds": odds_record.odds_american,
                    "ev_pct": ev.ev_percentage,
                    "won": actual_won,
                }
            )

    if bt.total_bets > 0:
        bt.net_units = round(bt.units_won - bt.units_lost, 4)
        bt.win_percentage = round(bt.wins / bt.total_bets * 100, 2)
        bt.roi_percentage = round(bt.net_units / (bt.total_bets * unit_size) * 100, 2)
    bt.max_drawdown = _calculate_drawdown(bt.bankroll_history)

    logger.info(
        "Backtest complete: bets=%d W/L=%d/%d net=%.2fu ROI=%.2f%% drawdown=%.2f%%",
        bt.total_bets,
        bt.wins,
        bt.losses,
        bt.net_units,
        bt.roi_percentage,
        bt.max_drawdown,
    )

    return bt


async def _get_team_history(
    session: AsyncSession,
    team_id: uuid.UUID,
    builder: FeatureMatrixBuilder,
    before: datetime,
) -> list[dict[str, float]]:
    all_raw = builder._base_keys + builder._opponent_keys + builder._pitcher_keys
    stmt = (
        select(HistoricalStats)
        .where(
            HistoricalStats.team_id == team_id,
            HistoricalStats.recorded_at < before,
        )
        .order_by(HistoricalStats.recorded_at.asc())
        .limit(builder.rolling_window * 5)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    game_map: dict[uuid.UUID, dict[str, float]] = {}
    for row in rows:
        fid = row.fixture_id
        if fid not in game_map:
            game_map[fid] = {}
        if row.boxscore_data:
            extracted = flatten_boxscore_json(row.boxscore_data, all_raw)
            game_map[fid].update(extracted)
        if row.stat_type in all_raw:
            game_map[fid][row.stat_type] = row.stat_value

    return list(game_map.values())


def _projection_to_probability(
    projection: float,
    target_type: str,
    target_stat: str,
    odds_record: MarketOdds,
    fixture: Fixture,
) -> float | None:
    if target_type == "classification":
        return max(0.01, min(0.99, projection))

    if target_stat in ("total_points", "total_runs", "total_goals"):
        if odds_record.market_type == "over_under" and odds_record.line:
            margin = projection - odds_record.line
            prob = 0.5 + (margin / (abs(margin) + 5)) * 0.4
            return max(0.01, min(0.99, prob))
        return None

    if odds_record.market_type == "moneyline":
        return max(0.01, min(0.99, 0.5 + projection * 0.1))

    return None


def _did_bet_win(
    target_type: str,
    target_stat: str,
    odds_record: MarketOdds,
    fixture: Fixture,
    projection: float,
) -> bool:
    if odds_record.market_type == "over_under":
        actual = (fixture.home_score or 0) + (fixture.away_score or 0)
        if odds_record.selection == "Over":
            return actual > (odds_record.line or 0)
        return actual < (odds_record.line or 0)

    if odds_record.market_type == "moneyline":
        home_won = (fixture.home_score or 0) > (fixture.away_score or 0)
        if odds_record.selection == fixture.home_team_id:
            return home_won
        return not home_won

    return False
