from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import (
    Base,
    CustomModelConfiguration,
    EVOpportunity,
    Fixture,
    League,
    MarketOdds,
    ModelCoefficients,
    PlacedBet,
    Portfolio,
    Team,
)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def api_engine():
    eng = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def api_session_factory(api_engine):
    return async_sessionmaker(bind=api_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client(api_session_factory):
    from fastapi import FastAPI

    from src.api.v1.routes import router
    from src.database.session import get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def override_session():
        async with api_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def seed_data(api_session_factory):
    async with api_session_factory() as session:
        league = League(code="NBA", full_name="National Basketball Association")
        session.add(league)
        await session.flush()

        home_team = Team(
            league_id=league.id, name="Boston Celtics", abbreviation="BOS", city="Boston"
        )
        away_team = Team(league_id=league.id, name="Miami Heat", abbreviation="MIA", city="Miami")
        session.add_all([home_team, away_team])
        await session.flush()

        fixture = Fixture(
            league_id=league.id,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            scheduled_at=datetime(2026, 6, 10, 19, 0, tzinfo=UTC),
            status="scheduled",
            season="2025-26",
        )
        session.add(fixture)
        await session.flush()

        odds = MarketOdds(
            fixture_id=fixture.id,
            sportsbook="DraftKings",
            market_type="moneyline",
            selection="Boston Celtics",
            odds_american=-150,
            odds_decimal=1.667,
        )
        session.add(odds)
        await session.flush()

        ev_opp = EVOpportunity(
            fixture_id=fixture.id,
            market_odds_id=odds.id,
            sportsbook="DraftKings",
            market_type="moneyline",
            selection="Boston Celtics",
            odds_american=-150,
            implied_probability=0.60,
            fair_probability=0.70,
            edge=0.10,
            ev_percentage=8.5,
            is_active=True,
        )
        session.add(ev_opp)
        await session.flush()

        await session.commit()

        return {
            "league_id": league.id,
            "home_team_id": home_team.id,
            "away_team_id": away_team.id,
            "fixture_id": fixture.id,
            "odds_id": odds.id,
            "ev_opp_id": ev_opp.id,
        }


# --- Kelly Criterion Tests ---


class TestKellyCriterion:
    def test_positive_edge_quarter_kelly(self):
        from src.core.math_engine import calculate_kelly_wager

        result = calculate_kelly_wager(
            implied_prob=0.50, fair_prob=0.60, current_bankroll=1000.0, fraction=0.25
        )
        assert result.stake > 0
        assert result.fraction > 0
        assert result.edge > 0
        assert result.stake <= 1000.0

    def test_negative_edge_returns_zero(self):
        from src.core.math_engine import calculate_kelly_wager

        result = calculate_kelly_wager(
            implied_prob=0.60, fair_prob=0.50, current_bankroll=1000.0, fraction=0.25
        )
        assert result.stake == 0.0
        assert result.fraction == 0.0

    def test_full_kelly_vs_quarter_kelly(self):
        from src.core.math_engine import calculate_kelly_wager

        full = calculate_kelly_wager(
            implied_prob=0.50, fair_prob=0.60, current_bankroll=1000.0, fraction=1.0
        )
        quarter = calculate_kelly_wager(
            implied_prob=0.50, fair_prob=0.60, current_bankroll=1000.0, fraction=0.25
        )
        assert abs(full.stake - quarter.stake * 4) < 0.02

    def test_kelly_formula_correctness(self):
        from src.core.math_engine import calculate_kelly_wager

        result = calculate_kelly_wager(
            implied_prob=0.50, fair_prob=0.60, current_bankroll=10000.0, fraction=1.0
        )
        b = (1.0 / 0.50) - 1.0
        p = 0.60
        q = 0.40
        expected_f = (b * p - q) / b
        expected_stake = 10000.0 * expected_f
        assert abs(result.stake - expected_stake) < 0.02
        assert abs(result.full_kelly_fraction - expected_f) < 0.001

    def test_zero_bankroll(self):
        from src.core.math_engine import calculate_kelly_wager

        result = calculate_kelly_wager(
            implied_prob=0.50, fair_prob=0.60, current_bankroll=0.0, fraction=0.25
        )
        assert result.stake == 0.0

    def test_boundary_probabilities(self):
        from src.core.math_engine import calculate_kelly_wager

        r1 = calculate_kelly_wager(implied_prob=0.0, fair_prob=0.60, current_bankroll=1000.0)
        assert r1.stake == 0.0

        r2 = calculate_kelly_wager(implied_prob=0.50, fair_prob=1.0, current_bankroll=1000.0)
        assert r2.stake == 0.0

    def test_even_money_with_edge(self):
        from src.core.math_engine import calculate_kelly_wager

        result = calculate_kelly_wager(
            implied_prob=0.50, fair_prob=0.55, current_bankroll=2000.0, fraction=0.5
        )
        assert result.stake > 0
        assert result.edge == pytest.approx(0.05, abs=0.001)

    def test_heavy_favorite(self):
        from src.core.math_engine import calculate_kelly_wager

        result = calculate_kelly_wager(
            implied_prob=0.80, fair_prob=0.85, current_bankroll=5000.0, fraction=0.25
        )
        assert result.stake > 0
        assert result.full_kelly_fraction > 0


# --- API Endpoint Tests ---


class TestFixturesEndpoint:
    @pytest.mark.asyncio(loop_scope="module")
    async def test_list_fixtures(self, client, seed_data):
        resp = await client.get("/api/v1/fixtures")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["home_team"] == "Boston Celtics"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_list_fixtures_league_filter(self, client, seed_data):
        resp = await client.get("/api/v1/fixtures", params={"league": "NBA"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestOddsEndpoint:
    @pytest.mark.asyncio(loop_scope="module")
    async def test_get_odds(self, client, seed_data):
        fid = str(seed_data["fixture_id"])
        resp = await client.get(f"/api/v1/odds/{fid}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["sportsbook"] == "DraftKings"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_get_odds_not_found(self, client, seed_data):
        resp = await client.get(f"/api/v1/odds/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestEVOpportunitiesEndpoint:
    @pytest.mark.asyncio(loop_scope="module")
    async def test_list_ev_opportunities(self, client, seed_data):
        resp = await client.get("/api/v1/ev-opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["ev_percentage"] > 0
        assert data[0]["recommended_kelly_wager"] is None

    @pytest.mark.asyncio(loop_scope="module")
    async def test_ev_with_kelly_wager(self, client, seed_data, api_session_factory):
        async with api_session_factory() as session:
            portfolio = Portfolio(
                name="Kelly Test", starting_balance=10000.0, current_balance=10000.0
            )
            session.add(portfolio)
            await session.flush()
            pid = portfolio.id
            await session.commit()

        resp = await client.get("/api/v1/ev-opportunities", params={"portfolio_id": str(pid)})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["recommended_kelly_wager"] is not None
        assert data[0]["recommended_kelly_wager"] > 0

    @pytest.mark.asyncio(loop_scope="module")
    async def test_ev_with_bad_portfolio(self, client, seed_data):
        resp = await client.get(
            "/api/v1/ev-opportunities", params={"portfolio_id": str(uuid.uuid4())}
        )
        assert resp.status_code == 404


class TestPortfolioEndpoints:
    @pytest.mark.asyncio(loop_scope="module")
    async def test_create_portfolio(self, client, seed_data):
        resp = await client.post(
            "/api/v1/portfolio",
            json={"starting_balance": 5000.0, "currency": "USD", "name": "Main"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["starting_balance"] == 5000.0
        assert data["current_balance"] == 5000.0
        assert data["total_bets"] == 0
        assert data["name"] == "Main"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_get_portfolio(self, client, seed_data, api_session_factory):
        async with api_session_factory() as session:
            portfolio = Portfolio(name="Get Test", starting_balance=2000.0, current_balance=2000.0)
            session.add(portfolio)
            await session.flush()
            pid = portfolio.id
            await session.commit()

        resp = await client.get(f"/api/v1/portfolio/{pid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_balance"] == 2000.0
        assert data["win_rate"] == 0.0

    @pytest.mark.asyncio(loop_scope="module")
    async def test_get_portfolio_not_found(self, client, seed_data):
        resp = await client.get(f"/api/v1/portfolio/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestPlaceBetEndpoint:
    @pytest.mark.asyncio(loop_scope="module")
    async def test_place_bet_kelly(self, client, seed_data, api_session_factory):
        async with api_session_factory() as session:
            portfolio = Portfolio(
                name="Bet Test", starting_balance=10000.0, current_balance=10000.0
            )
            session.add(portfolio)
            await session.flush()
            pid = portfolio.id
            await session.commit()

        resp = await client.post(
            "/api/v1/portfolio/bet",
            json={
                "portfolio_id": str(pid),
                "ev_opportunity_id": str(seed_data["ev_opp_id"]),
                "kelly_fraction": 0.25,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["stake_amount"] > 0
        assert data["status"] == "PENDING"
        assert data["remaining_balance"] < 10000.0
        assert data["kelly_fraction_used"] is not None

    @pytest.mark.asyncio(loop_scope="module")
    async def test_place_bet_manual_stake(self, client, seed_data, api_session_factory):
        async with api_session_factory() as session:
            portfolio = Portfolio(
                name="Manual Test", starting_balance=5000.0, current_balance=5000.0
            )
            session.add(portfolio)
            await session.flush()
            pid = portfolio.id
            await session.commit()

        resp = await client.post(
            "/api/v1/portfolio/bet",
            json={
                "portfolio_id": str(pid),
                "ev_opportunity_id": str(seed_data["ev_opp_id"]),
                "override_stake": 100.0,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["stake_amount"] == 100.0
        assert data["remaining_balance"] == 4900.0
        assert data["kelly_fraction_used"] is None

    @pytest.mark.asyncio(loop_scope="module")
    async def test_place_bet_insufficient_balance(self, client, seed_data, api_session_factory):
        async with api_session_factory() as session:
            portfolio = Portfolio(name="Broke Test", starting_balance=10.0, current_balance=10.0)
            session.add(portfolio)
            await session.flush()
            pid = portfolio.id
            await session.commit()

        resp = await client.post(
            "/api/v1/portfolio/bet",
            json={
                "portfolio_id": str(pid),
                "ev_opportunity_id": str(seed_data["ev_opp_id"]),
                "override_stake": 500.0,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio(loop_scope="module")
    async def test_place_bet_bad_portfolio(self, client, seed_data):
        resp = await client.post(
            "/api/v1/portfolio/bet",
            json={
                "portfolio_id": str(uuid.uuid4()),
                "ev_opportunity_id": str(seed_data["ev_opp_id"]),
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio(loop_scope="module")
    async def test_place_bet_bad_opportunity(self, client, seed_data, api_session_factory):
        async with api_session_factory() as session:
            portfolio = Portfolio(
                name="Bad Opp Test", starting_balance=1000.0, current_balance=1000.0
            )
            session.add(portfolio)
            await session.flush()
            pid = portfolio.id
            await session.commit()

        resp = await client.post(
            "/api/v1/portfolio/bet",
            json={
                "portfolio_id": str(pid),
                "ev_opportunity_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 404


class TestModelTrainEndpoint:
    @pytest.mark.asyncio(loop_scope="module")
    async def test_train_insufficient_data(self, client, seed_data):
        resp = await client.post(
            "/api/v1/models/train",
            json={
                "league": "NBA",
                "target_variable": "total_points",
                "feature_list": ["rebounds", "assists"],
            },
        )
        assert resp.status_code == 422
        assert "Insufficient" in resp.json()["detail"]


class TestModelBacktestEndpoint:
    @pytest.mark.asyncio(loop_scope="module")
    async def test_backtest_with_model(self, client, seed_data, api_session_factory):
        async with api_session_factory() as session:
            config = CustomModelConfiguration(
                name="test_backtest_model",
                league="NBA",
                target_type="regression",
                target_stat="total_points",
                feature_list={"features": ["rebounds", "assists"]},
                rolling_window=5,
                is_active=True,
            )
            session.add(config)
            await session.flush()

            coefficients = ModelCoefficients(
                config_id=config.id,
                intercept=100.0,
                weights={"rebounds": 1.5, "assists": 2.0},
                r_value=0.65,
                test_loss=12.5,
                train_samples=200,
                test_samples=50,
                metadata_extra={
                    "feature_names": ["rebounds", "assists"],
                    "scaler_mean": [0.0, 0.0],
                    "scaler_scale": [1.0, 1.0],
                },
            )
            session.add(coefficients)
            await session.flush()
            model_id = coefficients.id
            await session.commit()

        resp = await client.post(
            f"/api/v1/models/{model_id}/backtest",
            json={
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2026-06-01T00:00:00Z",
                "ev_threshold": 3.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_bets" in data
        assert "roi_percentage" in data
        assert "bankroll_history" in data

    @pytest.mark.asyncio(loop_scope="module")
    async def test_backtest_not_found(self, client, seed_data):
        resp = await client.post(
            f"/api/v1/models/{uuid.uuid4()}/backtest",
            json={
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2026-06-01T00:00:00Z",
            },
        )
        assert resp.status_code == 404


class TestPortfolioMetrics:
    @pytest.mark.asyncio(loop_scope="module")
    async def test_portfolio_tracks_bets(self, client, seed_data, api_session_factory):
        async with api_session_factory() as session:
            portfolio = Portfolio(
                name="Metrics Test", starting_balance=10000.0, current_balance=9800.0
            )
            session.add(portfolio)
            await session.flush()

            bet1 = PlacedBet(
                portfolio_id=portfolio.id,
                ev_opportunity_id=seed_data["ev_opp_id"],
                stake_amount=100.0,
                odds_taken=1.91,
                status="WON",
                pnl=91.0,
            )
            bet2 = PlacedBet(
                portfolio_id=portfolio.id,
                ev_opportunity_id=seed_data["ev_opp_id"],
                stake_amount=100.0,
                odds_taken=2.10,
                status="LOST",
                pnl=-100.0,
            )
            session.add_all([bet1, bet2])
            await session.flush()
            pid = portfolio.id
            await session.commit()

        resp = await client.get(f"/api/v1/portfolio/{pid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_bets"] == 2
        assert data["win_rate"] == 50.0
        assert data["total_pnl"] == -9.0
