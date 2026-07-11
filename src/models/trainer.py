from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import log_loss, mean_squared_error
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from src.database.models import (
    CustomModelConfiguration,
    Fixture,
    HistoricalStats,
    ModelCoefficients,
)
from src.models.features import FeatureMatrixBuilder, flatten_boxscore_json

logger = logging.getLogger(__name__)


@dataclass
class TrainingResult:
    intercept: float
    weights: dict[str, float]
    r_value: float
    test_loss: float
    train_samples: int
    test_samples: int
    feature_names: list[str]
    scaler_mean: list[float]
    scaler_scale: list[float]


def _compute_r_value(r_squared: float) -> float:
    sign = 1.0 if r_squared >= 0 else -1.0
    return sign * math.sqrt(abs(r_squared))


def train_regression(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    split_ratio: float = 0.8,
) -> TrainingResult:
    split_idx = int(len(X) * split_ratio)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = Ridge(alpha=1.0)
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)
    mse = mean_squared_error(y_test, y_pred)
    r_squared = model.score(X_test_scaled, y_test)
    r_val = _compute_r_value(r_squared)

    weights = {name: float(coeff) for name, coeff in zip(feature_names, model.coef_, strict=True)}

    return TrainingResult(
        intercept=float(model.intercept_),
        weights=weights,
        r_value=round(r_val, 6),
        test_loss=round(mse, 6),
        train_samples=len(X_train),
        test_samples=len(X_test),
        feature_names=feature_names,
        scaler_mean=scaler.mean_.tolist(),
        scaler_scale=scaler.scale_.tolist(),
    )


def train_classifier(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    split_ratio: float = 0.8,
) -> TrainingResult:
    split_idx = int(len(X) * split_ratio)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(C=1.0, l1_ratio=0, max_iter=1000)
    model.fit(X_train_scaled, y_train)

    y_proba = model.predict_proba(X_test_scaled)
    loss = log_loss(y_test, y_proba)
    r_squared = model.score(X_test_scaled, y_test)
    r_val = _compute_r_value(r_squared)

    weights = {
        name: float(coeff) for name, coeff in zip(feature_names, model.coef_[0], strict=True)
    }

    return TrainingResult(
        intercept=float(model.intercept_[0]),
        weights=weights,
        r_value=round(r_val, 6),
        test_loss=round(loss, 6),
        train_samples=len(X_train),
        test_samples=len(X_test),
        feature_names=feature_names,
        scaler_mean=scaler.mean_.tolist(),
        scaler_scale=scaler.scale_.tolist(),
    )


def build_training_arrays(
    raw_rows: list[dict[str, float]],
    feature_names: list[str],
    target_key: str,
) -> tuple[np.ndarray, np.ndarray]:
    df = pd.DataFrame(raw_rows)

    for col in feature_names:
        if col not in df.columns:
            df[col] = 0.0
    if target_key not in df.columns:
        df[target_key] = 0.0

    df = df.fillna(0.0)

    X = df[feature_names].to_numpy(dtype=np.float64)
    y = df[target_key].to_numpy(dtype=np.float64)

    return X, y


async def fetch_training_data(
    session: AsyncSession,
    league: str,
    feature_keys: list[str],
    target_stat: str,
    rolling_window: int = 10,
    limit_per_team: int = 200,
) -> list[dict[str, float]]:
    all_raw_keys = []
    for k in feature_keys:
        clean = k.removeprefix("Opponent ").removeprefix("Starting Pitcher ")
        if clean not in all_raw_keys:
            all_raw_keys.append(clean)
    if target_stat not in all_raw_keys:
        all_raw_keys.append(target_stat)

    stmt = (
        select(HistoricalStats)
        .join(Fixture, HistoricalStats.fixture_id == Fixture.id)
        .where(Fixture.status == "final")
        .order_by(HistoricalStats.recorded_at.asc())
        .limit(limit_per_team * 50)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    game_map: dict[tuple[uuid.UUID, uuid.UUID], dict[str, float]] = {}
    for row in rows:
        key = (row.fixture_id, row.team_id)
        if key not in game_map:
            game_map[key] = {}

        if row.boxscore_data:
            extracted = flatten_boxscore_json(row.boxscore_data, all_raw_keys)
            game_map[key].update(extracted)

        if row.stat_type in all_raw_keys:
            game_map[key][row.stat_type] = row.stat_value

    return list(game_map.values())


async def run_training_pipeline(
    session: AsyncSession,
    config: CustomModelConfiguration,
) -> ModelCoefficients:
    feature_list: list[str] = config.feature_list.get("features", [])
    if not feature_list:
        feature_list = config.feature_list if isinstance(config.feature_list, list) else []

    builder = FeatureMatrixBuilder(
        feature_keys=feature_list,
        rolling_window=config.rolling_window,
    )
    feature_names = builder.ordered_feature_names

    raw_rows = await fetch_training_data(
        session=session,
        league=config.league,
        feature_keys=feature_list,
        target_stat=config.target_stat,
        rolling_window=config.rolling_window,
    )

    if len(raw_rows) < 10:
        raise ValueError(f"Insufficient training data: {len(raw_rows)} rows (need at least 10)")

    X, y = build_training_arrays(raw_rows, feature_names, config.target_stat)

    split_ratio = settings.train_test_split_ratio

    if config.target_type == "classification":
        result = train_classifier(X, y, feature_names, split_ratio)
    else:
        result = train_regression(X, y, feature_names, split_ratio)

    coefficients = ModelCoefficients(
        config_id=config.id,
        intercept=result.intercept,
        weights=result.weights,
        r_value=result.r_value,
        test_loss=result.test_loss,
        train_samples=result.train_samples,
        test_samples=result.test_samples,
        metadata_extra={
            "scaler_mean": result.scaler_mean,
            "scaler_scale": result.scaler_scale,
            "feature_names": result.feature_names,
        },
    )
    session.add(coefficients)
    await session.flush()

    logger.info(
        "Model trained: %s | r=%.4f | test_loss=%.4f | train=%d test=%d features=%d",
        config.name,
        result.r_value,
        result.test_loss,
        result.train_samples,
        result.test_samples,
        len(feature_names),
    )

    return coefficients
