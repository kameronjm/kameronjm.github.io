import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.api.v1.schemas import EVOpportunityResponse, FixtureResponse, OddsResponse
from src.database.models import EVOpportunity, Fixture, League, MarketOdds
from src.database.session import get_db_session

router = APIRouter()


@router.get("/fixtures", response_model=list[FixtureResponse])
async def list_fixtures(
    league: str | None = Query(None, description="Filter by league code (NBA, NFL, MLB)"),
    session: AsyncSession = Depends(get_db_session),
) -> list[FixtureResponse]:
    stmt = (
        select(Fixture)
        .join(League, Fixture.league_id == League.id)
        .options(
            joinedload(Fixture.home_team),
            joinedload(Fixture.away_team),
            joinedload(Fixture.league),
        )
        .where(Fixture.status.in_(["scheduled", "in_progress"]))
        .order_by(Fixture.scheduled_at)
    )
    if league:
        stmt = stmt.where(League.code == league.upper())

    result = await session.execute(stmt)
    fixtures = result.unique().scalars().all()

    return [
        FixtureResponse(
            id=f.id,
            league_code=f.league.code,
            home_team=f.home_team.name,
            away_team=f.away_team.name,
            scheduled_at=f.scheduled_at,
            status=f.status,
            season=f.season,
            home_score=f.home_score,
            away_score=f.away_score,
        )
        for f in fixtures
    ]


@router.get("/odds/{fixture_id}", response_model=list[OddsResponse])
async def get_fixture_odds(
    fixture_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[OddsResponse]:
    fixture = await session.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")

    stmt = (
        select(MarketOdds)
        .where(MarketOdds.fixture_id == fixture_id)
        .order_by(MarketOdds.captured_at.desc())
    )
    result = await session.execute(stmt)
    odds = result.scalars().all()

    return [
        OddsResponse(
            id=o.id,
            sportsbook=o.sportsbook,
            market_type=o.market_type,
            selection=o.selection,
            line=o.line,
            odds_american=o.odds_american,
            odds_decimal=o.odds_decimal,
            captured_at=o.captured_at,
        )
        for o in odds
    ]


@router.get("/predictions/{fixture_id}")
async def get_predictions(
    fixture_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    from src.database.models import ModelPrediction

    fixture = await session.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")

    stmt = (
        select(ModelPrediction)
        .where(ModelPrediction.fixture_id == fixture_id)
        .order_by(ModelPrediction.created_at.desc())
    )
    result = await session.execute(stmt)
    predictions = result.scalars().all()

    return {
        "fixture_id": str(fixture_id),
        "predictions": [
            {
                "model_name": p.model_name,
                "model_version": p.model_version,
                "predicted_home_score": p.predicted_home_score,
                "predicted_away_score": p.predicted_away_score,
                "home_win_probability": p.home_win_probability,
                "away_win_probability": p.away_win_probability,
                "predicted_total": p.predicted_total,
            }
            for p in predictions
        ],
    }


@router.get("/ev-opportunities", response_model=list[EVOpportunityResponse])
async def list_ev_opportunities(
    min_ev: float = Query(0.0, description="Minimum EV percentage filter"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> list[EVOpportunityResponse]:
    stmt = (
        select(EVOpportunity)
        .options(
            joinedload(EVOpportunity.fixture).joinedload(Fixture.home_team),
            joinedload(EVOpportunity.fixture).joinedload(Fixture.away_team),
        )
        .where(EVOpportunity.is_active.is_(True), EVOpportunity.ev_percentage >= min_ev)
        .order_by(EVOpportunity.ev_percentage.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    opps = result.unique().scalars().all()

    return [
        EVOpportunityResponse(
            id=o.id,
            fixture_id=o.fixture_id,
            home_team=o.fixture.home_team.name,
            away_team=o.fixture.away_team.name,
            sportsbook=o.sportsbook,
            market_type=o.market_type,
            selection=o.selection,
            odds_american=o.odds_american,
            implied_probability=o.implied_probability,
            fair_probability=o.fair_probability,
            edge=o.edge,
            ev_percentage=o.ev_percentage,
            discovered_at=o.discovered_at,
        )
        for o in opps
    ]
