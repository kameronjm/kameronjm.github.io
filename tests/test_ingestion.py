from datetime import UTC, datetime

import pytest

from src.core.math_engine import american_to_decimal
from src.database.models import (
    Fixture,
    League,
    MarketOdds,
    ModelPrediction,
    Team,
)
from src.ingestion.mock_data import (
    generate_baseline_projection,
    generate_mock_fixtures,
    generate_mock_odds,
)
from src.ingestion.odds_feeds.odds_api_provider import OddsAPIProvider
from src.ingestion.stats_scrapers.sports_data_ingester import SportsDataIngester
from src.ingestion.worker import (
    ensure_baseline_prediction,
    evaluate_ev,
    upsert_odds,
)


class TestMockDataGeneration:
    def test_generate_fixtures_returns_list(self) -> None:
        fixtures = generate_mock_fixtures("NBA")
        assert len(fixtures) > 0
        assert all("home_team" in f for f in fixtures)
        assert all("scheduled_at" in f for f in fixtures)

    def test_generate_fixtures_all_leagues(self) -> None:
        for league in ("NBA", "NFL", "MLB"):
            fixtures = generate_mock_fixtures(league)
            assert len(fixtures) > 0
            assert all(f["league"] == league for f in fixtures)

    def test_generate_odds_structure(self) -> None:
        odds = generate_mock_odds("fix-1", "Boston Celtics", "New York Knicks", "NBA")
        assert len(odds) > 0
        required_keys = {"fixture_id", "sportsbook", "market_type", "selection", "odds_american"}
        for o in odds:
            assert required_keys.issubset(o.keys())

    def test_generate_odds_has_all_market_types(self) -> None:
        odds = generate_mock_odds("fix-1", "Home", "Away")
        market_types = {o["market_type"] for o in odds}
        assert market_types == {"moneyline", "spread", "over_under"}

    def test_generate_odds_has_all_books(self) -> None:
        odds = generate_mock_odds("fix-1", "Home", "Away")
        books = {o["sportsbook"] for o in odds}
        assert books == {"draftkings", "fanduel", "betmgm"}

    def test_baseline_projection_structure(self) -> None:
        proj = generate_baseline_projection("fix-1", "Home", "Away", "NBA")
        assert 0 < proj["home_win_probability"] < 1
        assert 0 < proj["away_win_probability"] < 1
        assert abs(proj["home_win_probability"] + proj["away_win_probability"] - 1.0) < 0.001


class TestOddsAPIProvider:
    @pytest.mark.asyncio
    async def test_mock_fallback(self) -> None:
        provider = OddsAPIProvider()
        assert provider._use_mock is True
        odds = await provider.stream_market_odds(
            "fix-1", league="NBA", home_team="Celtics", away_team="Knicks"
        )
        assert len(odds) > 0

    @pytest.mark.asyncio
    async def test_fetch_all_fixtures_odds(self) -> None:
        provider = OddsAPIProvider()
        fixtures = generate_mock_fixtures("NBA")
        all_odds = await provider.fetch_all_fixtures_odds(fixtures)
        assert len(all_odds) > len(fixtures)


class TestSportsDataIngester:
    @pytest.mark.asyncio
    async def test_mock_fixtures(self) -> None:
        ingester = SportsDataIngester()
        fixtures = await ingester.fetch_todays_fixtures("NBA")
        assert len(fixtures) > 0
        assert all("home_team" in f for f in fixtures)

    @pytest.mark.asyncio
    async def test_mock_historical(self) -> None:
        ingester = SportsDataIngester()
        data = await ingester.fetch_historical_data("NBA", "2025")
        assert len(data) > 0
        assert all("stat_type" in r for r in data)

    @pytest.mark.asyncio
    async def test_mock_live_data(self) -> None:
        ingester = SportsDataIngester()
        data = await ingester.fetch_live_data("fixture-123")
        assert data["status"] == "mock_live"


class TestWorkerUpsertOdds:
    @pytest.mark.asyncio
    async def test_upsert_writes_odds(self, db_session) -> None:
        league = League(code="TEST_L", full_name="Test League")
        db_session.add(league)
        await db_session.flush()

        home = Team(league_id=league.id, name="Home Team", abbreviation="HME", city="Home")
        away = Team(league_id=league.id, name="Away Team", abbreviation="AWY", city="Away")
        db_session.add_all([home, away])
        await db_session.flush()

        fixture = Fixture(
            league_id=league.id,
            home_team_id=home.id,
            away_team_id=away.id,
            scheduled_at=datetime.now(tz=UTC),
            season="2025",
        )
        db_session.add(fixture)
        await db_session.flush()

        mock_odds = [
            {
                "sportsbook": "draftkings",
                "market_type": "moneyline",
                "selection": "Home Team",
                "line": None,
                "odds_american": -150,
            },
            {
                "sportsbook": "draftkings",
                "market_type": "moneyline",
                "selection": "Away Team",
                "line": None,
                "odds_american": 130,
            },
        ]

        written = await upsert_odds(db_session, fixture.id, mock_odds)
        assert len(written) == 2
        assert written[0].odds_decimal == american_to_decimal(-150)

    @pytest.mark.asyncio
    async def test_ensure_baseline_prediction(self, db_session) -> None:
        league = League(code="TEST_P", full_name="Test Pred")
        db_session.add(league)
        await db_session.flush()

        home = Team(league_id=league.id, name="Pred Home", abbreviation="PH", city="PCity")
        away = Team(league_id=league.id, name="Pred Away", abbreviation="PA", city="PCity")
        db_session.add_all([home, away])
        await db_session.flush()

        fixture = Fixture(
            league_id=league.id,
            home_team_id=home.id,
            away_team_id=away.id,
            scheduled_at=datetime.now(tz=UTC),
            season="2025",
        )
        db_session.add(fixture)
        await db_session.flush()

        pred = await ensure_baseline_prediction(
            db_session,
            fixture.id,
            {"home_team": "Pred Home", "away_team": "Pred Away", "league": "NBA"},
        )
        assert pred.model_name == "baseline_v1"
        assert 0 < pred.home_win_probability < 1

        pred2 = await ensure_baseline_prediction(
            db_session,
            fixture.id,
            {"home_team": "Pred Home", "away_team": "Pred Away", "league": "NBA"},
        )
        assert pred2.id == pred.id


class TestEVEvaluation:
    @pytest.mark.asyncio
    async def test_ev_trigger_finds_opportunity(self, db_session) -> None:
        league = League(code="TEST_EV", full_name="EV League")
        db_session.add(league)
        await db_session.flush()

        home = Team(league_id=league.id, name="EV Home", abbreviation="EVH", city="EVCity")
        away = Team(league_id=league.id, name="EV Away", abbreviation="EVA", city="EVCity")
        db_session.add_all([home, away])
        await db_session.flush()

        fixture = Fixture(
            league_id=league.id,
            home_team_id=home.id,
            away_team_id=away.id,
            scheduled_at=datetime.now(tz=UTC),
            season="2025",
        )
        db_session.add(fixture)
        await db_session.flush()
        await db_session.refresh(fixture, ["home_team", "away_team"])

        odds_record = MarketOdds(
            fixture_id=fixture.id,
            sportsbook="draftkings",
            market_type="moneyline",
            selection="EV Home",
            odds_american=150,
        )
        db_session.add(odds_record)
        await db_session.flush()

        prediction = ModelPrediction(
            fixture_id=fixture.id,
            model_name="baseline_v1",
            model_version="0.1.0",
            predicted_home_score=110.0,
            predicted_away_score=100.0,
            home_win_probability=0.65,
            away_win_probability=0.35,
            predicted_total=210.0,
        )
        db_session.add(prediction)
        await db_session.flush()

        opps = await evaluate_ev(db_session, [odds_record], prediction, fixture, threshold=3.0)

        assert len(opps) >= 1
        opp = opps[0]
        assert opp.ev_percentage > 3.0
        assert opp.sportsbook == "draftkings"
        assert opp.fair_probability == 0.65

    @pytest.mark.asyncio
    async def test_ev_below_threshold_skipped(self, db_session) -> None:
        league = League(code="TEST_NO", full_name="No EV")
        db_session.add(league)
        await db_session.flush()

        home = Team(league_id=league.id, name="No Home", abbreviation="NOH", city="NoCity")
        away = Team(league_id=league.id, name="No Away", abbreviation="NOA", city="NoCity")
        db_session.add_all([home, away])
        await db_session.flush()

        fixture = Fixture(
            league_id=league.id,
            home_team_id=home.id,
            away_team_id=away.id,
            scheduled_at=datetime.now(tz=UTC),
            season="2025",
        )
        db_session.add(fixture)
        await db_session.flush()
        await db_session.refresh(fixture, ["home_team", "away_team"])

        odds_record = MarketOdds(
            fixture_id=fixture.id,
            sportsbook="fanduel",
            market_type="moneyline",
            selection="No Home",
            odds_american=-300,
        )
        db_session.add(odds_record)
        await db_session.flush()

        prediction = ModelPrediction(
            fixture_id=fixture.id,
            model_name="baseline_v1",
            model_version="0.1.0",
            predicted_home_score=105.0,
            predicted_away_score=103.0,
            home_win_probability=0.52,
            away_win_probability=0.48,
            predicted_total=208.0,
        )
        db_session.add(prediction)
        await db_session.flush()

        opps = await evaluate_ev(db_session, [odds_record], prediction, fixture, threshold=3.0)
        assert len(opps) == 0
