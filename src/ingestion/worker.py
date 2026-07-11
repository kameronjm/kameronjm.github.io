import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from src.core.math_engine import (
    american_to_decimal,
    calculate_expected_value,
)
from src.database.models import (
    CustomModelConfiguration,
    EVOpportunity,
    Fixture,
    League,
    MarketOdds,
    ModelCoefficients,
    ModelPrediction,
    Team,
)
from src.database.session import async_session
from src.ingestion.mock_data import generate_baseline_projection
from src.ingestion.odds_feeds.odds_api_provider import OddsAPIProvider
from src.ingestion.stats_scrapers.sports_data_ingester import SportsDataIngester
from src.models.features import FeatureMatrixBuilder, predict_from_coefficients

logger = logging.getLogger(__name__)


async def _ensure_league(session: AsyncSession, code: str) -> uuid.UUID:
    result = await session.execute(select(League).where(League.code == code))
    league = result.scalar_one_or_none()
    if league:
        return league.id

    league = League(code=code, full_name=code)
    session.add(league)
    await session.flush()
    return league.id


async def _ensure_team(
    session: AsyncSession,
    league_id: uuid.UUID,
    name: str,
    abbreviation: str,
) -> uuid.UUID:
    result = await session.execute(
        select(Team).where(Team.league_id == league_id, Team.abbreviation == abbreviation)
    )
    team = result.scalar_one_or_none()
    if team:
        return team.id

    team = Team(
        league_id=league_id,
        name=name,
        abbreviation=abbreviation,
        city=name.rsplit(" ", 1)[0],
    )
    session.add(team)
    await session.flush()
    return team.id


async def _ensure_fixture(
    session: AsyncSession,
    fixture_data: dict[str, Any],
    league_id: uuid.UUID,
    home_team_id: uuid.UUID,
    away_team_id: uuid.UUID,
) -> uuid.UUID:
    ext_id = fixture_data.get("external_id", "")
    if ext_id:
        result = await session.execute(select(Fixture).where(Fixture.external_id == ext_id))
        existing = result.scalar_one_or_none()
        if existing:
            return existing.id

    fixture = Fixture(
        league_id=league_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        scheduled_at=datetime.fromisoformat(fixture_data["scheduled_at"]),
        status=fixture_data.get("status", "scheduled"),
        season=fixture_data.get("season", "2025-26"),
        external_id=ext_id or None,
    )
    session.add(fixture)
    await session.flush()
    return fixture.id


async def upsert_odds(
    session: AsyncSession,
    fixture_db_id: uuid.UUID,
    odds_rows: list[dict[str, Any]],
) -> list[MarketOdds]:
    written: list[MarketOdds] = []
    for row in odds_rows:
        odds_record = MarketOdds(
            fixture_id=fixture_db_id,
            sportsbook=row["sportsbook"],
            market_type=row["market_type"],
            selection=row["selection"],
            line=row.get("line"),
            odds_american=row["odds_american"],
            odds_decimal=american_to_decimal(row["odds_american"]),
        )
        session.add(odds_record)
        written.append(odds_record)

    await session.flush()
    return written


async def ensure_baseline_prediction(
    session: AsyncSession,
    fixture_db_id: uuid.UUID,
    fixture_data: dict[str, Any],
) -> ModelPrediction:
    result = await session.execute(
        select(ModelPrediction).where(
            ModelPrediction.fixture_id == fixture_db_id,
            ModelPrediction.model_name == "baseline_v1",
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    proj = generate_baseline_projection(
        fixture_id=str(fixture_db_id),
        home_team=fixture_data.get("home_team", "Home"),
        away_team=fixture_data.get("away_team", "Away"),
        league=fixture_data.get("league", "NBA"),
    )
    prediction = ModelPrediction(
        fixture_id=fixture_db_id,
        model_name=proj["model_name"],
        model_version=proj["model_version"],
        predicted_home_score=proj["predicted_home_score"],
        predicted_away_score=proj["predicted_away_score"],
        home_win_probability=proj["home_win_probability"],
        away_win_probability=proj["away_win_probability"],
        predicted_total=proj["predicted_total"],
    )
    session.add(prediction)
    await session.flush()
    return prediction


async def _fetch_active_model(
    session: AsyncSession,
    league: str,
) -> tuple[CustomModelConfiguration, ModelCoefficients] | None:
    cfg_stmt = (
        select(CustomModelConfiguration)
        .where(
            CustomModelConfiguration.league == league,
            CustomModelConfiguration.is_active.is_(True),
        )
        .order_by(CustomModelConfiguration.created_at.desc())
        .limit(1)
    )
    cfg_result = await session.execute(cfg_stmt)
    config = cfg_result.scalar_one_or_none()
    if not config:
        return None

    coeff_stmt = (
        select(ModelCoefficients)
        .where(ModelCoefficients.config_id == config.id)
        .order_by(ModelCoefficients.trained_at.desc())
        .limit(1)
    )
    coeff_result = await session.execute(coeff_stmt)
    coefficients = coeff_result.scalar_one_or_none()
    if not coefficients:
        return None

    return config, coefficients


async def generate_ml_prediction(
    session: AsyncSession,
    fixture_db_id: uuid.UUID,
    home_team_id: uuid.UUID,
    away_team_id: uuid.UUID,
    config: CustomModelConfiguration,
    coefficients: ModelCoefficients,
) -> ModelPrediction:
    feature_names: list[str] = (
        coefficients.metadata_extra.get("feature_names", []) if coefficients.metadata_extra else []
    )
    if not feature_names:
        raw = config.feature_list
        feature_names = raw.get("features", raw) if isinstance(raw, dict) else raw

    builder = FeatureMatrixBuilder(
        feature_keys=feature_names,
        rolling_window=config.rolling_window,
    )

    home_rows, _ = await builder.build_historical_matrix(
        session,
        home_team_id,
        away_team_id,
        limit=config.rolling_window * 3,
    )
    away_rows, _ = await builder.build_historical_matrix(
        session,
        away_team_id,
        home_team_id,
        limit=config.rolling_window * 3,
    )

    home_vector = builder.build_rolling_feature_vector(home_rows, away_rows)
    away_vector = builder.build_rolling_feature_vector(away_rows, home_rows)

    home_proj = predict_from_coefficients(
        home_vector, coefficients.intercept, coefficients.weights
    )
    away_proj = predict_from_coefficients(
        away_vector, coefficients.intercept, coefficients.weights
    )

    if config.target_type == "classification":
        home_wp = max(0.05, min(0.95, home_proj))
        away_wp = round(1.0 - home_wp, 4)
        pred_home = None
        pred_away = None
        pred_total = None
    else:
        pred_home = round(home_proj, 2)
        pred_away = round(away_proj, 2)
        pred_total = round(home_proj + away_proj, 2)
        diff = home_proj - away_proj
        home_wp = round(max(0.05, min(0.95, 0.5 + diff / (abs(diff) + 10) * 0.4)), 4)
        away_wp = round(1.0 - home_wp, 4)

    prediction = ModelPrediction(
        fixture_id=fixture_db_id,
        model_name=config.name,
        model_version="ml_v1",
        predicted_home_score=pred_home,
        predicted_away_score=pred_away,
        home_win_probability=home_wp,
        away_win_probability=away_wp,
        predicted_total=pred_total,
        prediction_metadata={
            "config_id": str(config.id),
            "coefficients_id": str(coefficients.id),
            "home_raw_projection": round(home_proj, 6),
            "away_raw_projection": round(away_proj, 6),
        },
    )
    session.add(prediction)
    await session.flush()
    return prediction


def resolve_fair_probability(
    odds_record: MarketOdds,
    prediction: ModelPrediction,
    fixture: Fixture,
) -> float | None:
    mt = odds_record.market_type
    sel = odds_record.selection

    if mt == "moneyline":
        home_name = ""
        away_name = ""
        if fixture.home_team:
            home_name = fixture.home_team.name
        if fixture.away_team:
            away_name = fixture.away_team.name

        if sel == home_name and prediction.home_win_probability:
            return prediction.home_win_probability
        if sel == away_name and prediction.away_win_probability:
            return prediction.away_win_probability
        if prediction.home_win_probability:
            return prediction.home_win_probability
        return None

    if mt == "over_under":
        return 0.50

    if mt == "spread":
        return 0.52

    return None


async def evaluate_ev(
    session: AsyncSession,
    odds_records: list[MarketOdds],
    prediction: ModelPrediction,
    fixture: Fixture,
    threshold: float,
) -> list[EVOpportunity]:
    opportunities: list[EVOpportunity] = []

    for odds_record in odds_records:
        fair_prob = resolve_fair_probability(odds_record, prediction, fixture)
        if fair_prob is None:
            continue

        ev_result = calculate_expected_value(fair_prob, odds_record.odds_american)

        if ev_result.ev_percentage > threshold:
            opp = EVOpportunity(
                fixture_id=odds_record.fixture_id,
                market_odds_id=odds_record.id,
                sportsbook=odds_record.sportsbook,
                market_type=odds_record.market_type,
                selection=odds_record.selection,
                odds_american=odds_record.odds_american,
                implied_probability=ev_result.implied_probability,
                fair_probability=ev_result.true_probability,
                edge=ev_result.edge,
                ev_percentage=ev_result.ev_percentage,
            )
            session.add(opp)
            opportunities.append(opp)

            logger.info(
                "+EV FOUND: %s | %s %s @ %s | %+d | edge=%.2f%% | EV=%.2f%%",
                odds_record.sportsbook,
                odds_record.market_type,
                odds_record.selection,
                odds_record.fixture_id,
                odds_record.odds_american,
                ev_result.edge * 100,
                ev_result.ev_percentage,
            )

    if opportunities:
        await session.flush()

    return opportunities


async def run_single_cycle(leagues: list[str] | None = None) -> dict[str, int]:
    leagues = leagues or ["NBA", "NFL", "MLB"]
    stats_ingester = SportsDataIngester()
    odds_provider = OddsAPIProvider()
    threshold = settings.ev_threshold_percent

    totals = {"fixtures": 0, "odds": 0, "opportunities": 0}

    async with async_session() as session:
        for league_code in leagues:
            fixture_list = await stats_ingester.fetch_todays_fixtures(league_code)
            league_id = await _ensure_league(session, league_code)

            active_model = await _fetch_active_model(session, league_code)

            for f_data in fixture_list:
                home_team_id = await _ensure_team(
                    session,
                    league_id,
                    f_data["home_team"],
                    f_data.get("home_abbreviation", f_data["home_team"][:3].upper()),
                )
                away_team_id = await _ensure_team(
                    session,
                    league_id,
                    f_data["away_team"],
                    f_data.get("away_abbreviation", f_data["away_team"][:3].upper()),
                )

                fixture_db_id = await _ensure_fixture(
                    session, f_data, league_id, home_team_id, away_team_id
                )
                totals["fixtures"] += 1

                odds_rows = await odds_provider.stream_market_odds(
                    fixture_id=f_data.get("id", str(fixture_db_id)),
                    league=league_code,
                    home_team=f_data["home_team"],
                    away_team=f_data["away_team"],
                )

                written_odds = await upsert_odds(session, fixture_db_id, odds_rows)
                totals["odds"] += len(written_odds)

                if active_model:
                    config, coefficients = active_model
                    try:
                        prediction = await generate_ml_prediction(
                            session,
                            fixture_db_id,
                            home_team_id,
                            away_team_id,
                            config,
                            coefficients,
                        )
                    except Exception:
                        logger.warning(
                            "ML prediction failed for %s, using baseline",
                            fixture_db_id,
                        )
                        prediction = await ensure_baseline_prediction(
                            session, fixture_db_id, f_data
                        )
                else:
                    prediction = await ensure_baseline_prediction(session, fixture_db_id, f_data)

                fixture_obj = await session.get(Fixture, fixture_db_id, options=[])
                if fixture_obj:
                    await session.refresh(fixture_obj, ["home_team", "away_team"])
                    opps = await evaluate_ev(
                        session, written_odds, prediction, fixture_obj, threshold
                    )
                    totals["opportunities"] += len(opps)

        await session.commit()

    logger.info(
        "Cycle complete — fixtures=%d, odds=%d, +EV opportunities=%d",
        totals["fixtures"],
        totals["odds"],
        totals["opportunities"],
    )
    return totals


async def run_polling_loop(leagues: list[str] | None = None) -> None:
    interval = settings.odds_poll_interval_seconds
    logger.info("Starting odds polling loop (interval=%ds)", interval)

    while True:
        try:
            await run_single_cycle(leagues)
        except Exception:
            logger.exception("Error in polling cycle")
        await asyncio.sleep(interval)
