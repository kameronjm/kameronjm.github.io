from __future__ import annotations

import logging
import uuid
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import HistoricalStats

logger = logging.getLogger(__name__)


def flatten_boxscore_json(
    payload: dict[str, Any] | None,
    feature_keys: list[str],
) -> dict[str, float]:
    if not payload:
        return {k: 0.0 for k in feature_keys}

    flat: dict[str, float] = {}
    for key in feature_keys:
        val = _deep_get(payload, key)
        if val is not None:
            try:
                flat[key] = float(val)
            except (ValueError, TypeError):
                flat[key] = 0.0
        else:
            flat[key] = 0.0
    return flat


def _deep_get(d: dict[str, Any], dotted_key: str) -> Any:
    parts = dotted_key.split(".")
    current: Any = d
    for p in parts:
        if isinstance(current, dict):
            current = current.get(p)
        else:
            return None
    return current


def mirror_opponent_features(
    team_features: dict[str, float],
    prefix: str = "Opponent ",
) -> dict[str, float]:
    return {f"{prefix}{k}": v for k, v in team_features.items()}


def mirror_pitcher_features(
    pitcher_features: dict[str, float],
    prefix: str = "Starting Pitcher ",
) -> dict[str, float]:
    return {f"{prefix}{k}": v for k, v in pitcher_features.items()}


def compute_rolling_averages(
    game_rows: list[dict[str, float]],
    window: int,
) -> dict[str, float]:
    if not game_rows:
        return {}

    recent = game_rows[-window:] if len(game_rows) >= window else game_rows
    all_keys = set()
    for row in recent:
        all_keys.update(row.keys())

    averages: dict[str, float] = {}
    for key in all_keys:
        vals = [r[key] for r in recent if key in r]
        if vals:
            averages[key] = float(np.mean(vals))
        else:
            averages[key] = 0.0
    return averages


class FeatureMatrixBuilder:
    def __init__(
        self,
        feature_keys: list[str],
        rolling_window: int = 10,
    ) -> None:
        self.feature_keys = feature_keys
        self.rolling_window = rolling_window

        self._base_keys: list[str] = []
        self._opponent_keys: list[str] = []
        self._pitcher_keys: list[str] = []

        for k in feature_keys:
            if k.startswith("Opponent "):
                self._opponent_keys.append(k.removeprefix("Opponent "))
            elif k.startswith("Starting Pitcher "):
                self._pitcher_keys.append(k.removeprefix("Starting Pitcher "))
            else:
                self._base_keys.append(k)

    @property
    def ordered_feature_names(self) -> list[str]:
        names = list(self._base_keys)
        names += [f"Opponent {k}" for k in self._opponent_keys]
        names += [f"Starting Pitcher {k}" for k in self._pitcher_keys]
        return names

    async def build_historical_matrix(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
        opponent_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> tuple[list[dict[str, float]], list[str]]:
        team_rows = await self._fetch_team_game_rows(session, team_id, limit)
        opp_rows: list[dict[str, float]] = []
        if opponent_id and self._opponent_keys:
            opp_rows = await self._fetch_team_game_rows(session, opponent_id, limit)

        feature_names = self.ordered_feature_names
        matrix_rows: list[dict[str, float]] = []

        for i, team_row in enumerate(team_rows):
            row: dict[str, float] = {}
            for k in self._base_keys:
                row[k] = team_row.get(k, 0.0)

            if opp_rows and i < len(opp_rows):
                opp_flat = opp_rows[i]
            elif opp_rows:
                opp_flat = opp_rows[-1]
            else:
                opp_flat = {}

            for k in self._opponent_keys:
                row[f"Opponent {k}"] = opp_flat.get(k, 0.0)

            for k in self._pitcher_keys:
                row[f"Starting Pitcher {k}"] = team_row.get(k, 0.0)

            matrix_rows.append(row)

        return matrix_rows, feature_names

    def build_rolling_feature_vector(
        self,
        game_rows: list[dict[str, float]],
        opponent_game_rows: list[dict[str, float]] | None = None,
    ) -> dict[str, float]:
        team_avg = compute_rolling_averages(game_rows, self.rolling_window)
        opp_avg = compute_rolling_averages(opponent_game_rows or [], self.rolling_window)

        vector: dict[str, float] = {}
        for k in self._base_keys:
            vector[k] = team_avg.get(k, 0.0)
        for k in self._opponent_keys:
            vector[f"Opponent {k}"] = opp_avg.get(k, 0.0)
        for k in self._pitcher_keys:
            vector[f"Starting Pitcher {k}"] = team_avg.get(k, 0.0)

        return vector

    async def _fetch_team_game_rows(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
        limit: int,
    ) -> list[dict[str, float]]:
        all_raw_keys = self._base_keys + self._opponent_keys + self._pitcher_keys

        stmt = (
            select(HistoricalStats)
            .where(HistoricalStats.team_id == team_id)
            .order_by(HistoricalStats.recorded_at.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        game_map: dict[uuid.UUID, dict[str, float]] = {}
        for row in rows:
            fid = row.fixture_id
            if fid not in game_map:
                game_map[fid] = {}

            if row.boxscore_data:
                extracted = flatten_boxscore_json(row.boxscore_data, all_raw_keys)
                game_map[fid].update(extracted)

            if row.stat_type in all_raw_keys:
                game_map[fid][row.stat_type] = row.stat_value

        return list(game_map.values())


def predict_from_coefficients(
    feature_vector: dict[str, float],
    intercept: float,
    weights: dict[str, float],
) -> float:
    result = intercept
    for feat, coeff in weights.items():
        result += coeff * feature_vector.get(feat, 0.0)
    return result
