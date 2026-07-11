import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.api.v1.schemas import (
    BacktestRequest,
    BacktestResponse,
    CreatePortfolioRequest,
    EVOpportunityResponse,
    FixtureResponse,
    OddsResponse,
    PlaceBetRequest,
    PlacedBetResponse,
    PortfolioResponse,
    TrainModelRequest,
    TrainModelResponse,
)
from src.core.math_engine import american_to_decimal, calculate_kelly_wager
from src.database.models import (
    CustomModelConfiguration,
    EVOpportunity,
    Fixture,
    League,
    MarketOdds,
    ModelCoefficients,
    PlacedBet,
    Portfolio,
)
from src.database.session import get_db_session

router = APIRouter()


# --- Fixture & Odds Endpoints (Phase 2) ---


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
    portfolio_id: uuid.UUID | None = Query(None, description="Attach Kelly wager sizing"),
    session: AsyncSession = Depends(get_db_session),
) -> list[EVOpportunityResponse]:
    portfolio: Portfolio | None = None
    if portfolio_id:
        portfolio = await session.get(Portfolio, portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

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

    responses = []
    for o in opps:
        kelly_wager = None
        if portfolio:
            kelly = calculate_kelly_wager(
                implied_prob=o.implied_probability,
                fair_prob=o.fair_probability,
                current_bankroll=portfolio.current_balance,
            )
            kelly_wager = kelly.stake

        responses.append(
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
                recommended_kelly_wager=kelly_wager,
            )
        )

    return responses


# --- Model Builder Endpoints (Phase 4) ---


@router.post("/models/train", response_model=TrainModelResponse)
async def train_model(
    request: TrainModelRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TrainModelResponse:
    from src.models.trainer import run_training_pipeline

    model_name = request.name or f"{request.league}_{request.target_variable}_model"

    config = CustomModelConfiguration(
        name=model_name,
        league=request.league.upper(),
        target_type=request.target_type,
        target_stat=request.target_variable,
        feature_list={"features": request.feature_list},
        rolling_window=request.rolling_window,
        is_active=True,
    )
    session.add(config)
    await session.flush()

    try:
        coefficients = await run_training_pipeline(session, config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return TrainModelResponse(
        model_id=coefficients.id,
        config_id=config.id,
        name=config.name,
        r_value=coefficients.r_value,
        test_loss=coefficients.test_loss,
        train_samples=coefficients.train_samples,
        test_samples=coefficients.test_samples,
        feature_count=len(request.feature_list),
    )


@router.post("/models/{model_id}/backtest", response_model=BacktestResponse)
async def run_model_backtest(
    model_id: uuid.UUID,
    request: BacktestRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BacktestResponse:
    from src.models.backtester import run_backtest

    coefficients = await session.get(ModelCoefficients, model_id)
    if not coefficients:
        raise HTTPException(status_code=404, detail="Model coefficients not found")

    config = await session.get(CustomModelConfiguration, coefficients.config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Model configuration not found")

    bt = await run_backtest(
        session=session,
        config=config,
        coefficients=coefficients,
        start_date=request.start_date,
        end_date=request.end_date,
        ev_threshold=request.ev_threshold,
        unit_size=request.unit_size,
    )

    return BacktestResponse(
        model_id=model_id,
        total_bets=bt.total_bets,
        wins=bt.wins,
        losses=bt.losses,
        net_units=bt.net_units,
        win_percentage=bt.win_percentage,
        roi_percentage=bt.roi_percentage,
        max_drawdown=bt.max_drawdown,
        bankroll_history=bt.bankroll_history,
    )


# --- Portfolio Endpoints (Phase 4) ---


@router.post("/portfolio", response_model=PortfolioResponse, status_code=201)
async def create_portfolio(
    request: CreatePortfolioRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PortfolioResponse:
    portfolio = Portfolio(
        name=request.name,
        starting_balance=request.starting_balance,
        current_balance=request.starting_balance,
        currency=request.currency,
    )
    session.add(portfolio)
    await session.flush()

    return PortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        starting_balance=portfolio.starting_balance,
        current_balance=portfolio.current_balance,
        currency=portfolio.currency,
        total_bets=0,
        total_pnl=0.0,
        win_rate=0.0,
        created_at=portfolio.created_at,
    )


@router.get("/portfolio/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PortfolioResponse:
    portfolio = await session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    count_stmt = select(func.count()).where(PlacedBet.portfolio_id == portfolio_id)
    total_bets = (await session.execute(count_stmt)).scalar() or 0

    wins_stmt = select(func.count()).where(
        PlacedBet.portfolio_id == portfolio_id, PlacedBet.status == "WON"
    )
    wins = (await session.execute(wins_stmt)).scalar() or 0

    pnl_stmt = select(func.coalesce(func.sum(PlacedBet.pnl), 0.0)).where(
        PlacedBet.portfolio_id == portfolio_id
    )
    total_pnl = float((await session.execute(pnl_stmt)).scalar() or 0.0)

    resolved = total_bets - (
        (
            await session.execute(
                select(func.count()).where(
                    PlacedBet.portfolio_id == portfolio_id,
                    PlacedBet.status == "PENDING",
                )
            )
        ).scalar()
        or 0
    )
    win_rate = round(wins / resolved * 100, 2) if resolved > 0 else 0.0

    return PortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        starting_balance=portfolio.starting_balance,
        current_balance=portfolio.current_balance,
        currency=portfolio.currency,
        total_bets=total_bets,
        total_pnl=round(total_pnl, 2),
        win_rate=win_rate,
        created_at=portfolio.created_at,
    )


@router.post("/portfolio/bet", response_model=PlacedBetResponse, status_code=201)
async def place_bet(
    request: PlaceBetRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PlacedBetResponse:
    portfolio = await session.get(Portfolio, request.portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    opp = await session.get(EVOpportunity, request.ev_opportunity_id)
    if not opp:
        raise HTTPException(status_code=404, detail="EV opportunity not found")

    if request.override_stake is not None:
        stake = request.override_stake
        kelly_fraction_used = None
    else:
        kelly = calculate_kelly_wager(
            implied_prob=opp.implied_probability,
            fair_prob=opp.fair_probability,
            current_bankroll=portfolio.current_balance,
            fraction=request.kelly_fraction,
        )
        stake = kelly.stake
        kelly_fraction_used = kelly.fraction

    if stake <= 0:
        raise HTTPException(
            status_code=422, detail="Kelly criterion suggests no wager on this opportunity"
        )

    if stake > portfolio.current_balance:
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient balance: {portfolio.current_balance:.2f} < {stake:.2f}",
        )

    decimal_odds = american_to_decimal(opp.odds_american)

    bet = PlacedBet(
        portfolio_id=portfolio.id,
        ev_opportunity_id=opp.id,
        stake_amount=stake,
        odds_taken=decimal_odds,
        status="PENDING",
    )
    session.add(bet)

    portfolio.current_balance = round(portfolio.current_balance - stake, 2)
    await session.flush()

    return PlacedBetResponse(
        id=bet.id,
        portfolio_id=portfolio.id,
        ev_opportunity_id=opp.id,
        stake_amount=stake,
        odds_taken=decimal_odds,
        status="PENDING",
        remaining_balance=portfolio.current_balance,
        kelly_fraction_used=kelly_fraction_used,
    )
