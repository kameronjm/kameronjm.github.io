import logging
from typing import Any

import httpx

from config import settings
from src.core.interfaces import BaseOddsProvider
from src.ingestion.mock_data import generate_mock_odds

logger = logging.getLogger(__name__)

_SPORT_KEY_MAP: dict[str, str] = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
}


class OddsAPIProvider(BaseOddsProvider):
    def __init__(self) -> None:
        self._api_key = settings.odds_api_key
        self._base_url = settings.odds_api_base_url
        self._use_mock = not bool(self._api_key)
        if self._use_mock:
            logger.warning("No ODDS_API_KEY set — falling back to mock odds data")

    async def stream_market_odds(
        self,
        fixture_id: str,
        market_types: list[str] | None = None,
        *,
        league: str = "NBA",
        home_team: str = "Home",
        away_team: str = "Away",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        if self._use_mock:
            return generate_mock_odds(fixture_id, home_team, away_team, league)
        return await self._fetch_live_odds(fixture_id, league, home_team, away_team)

    async def _fetch_live_odds(
        self,
        fixture_id: str,
        league: str,
        home_team: str,
        away_team: str,
    ) -> list[dict[str, Any]]:
        sport_key = _SPORT_KEY_MAP.get(league, "basketball_nba")
        url = f"{self._base_url}/sports/{sport_key}/odds"
        params: dict[str, str] = {
            "apiKey": self._api_key,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "bookmakers": "draftkings,fanduel,betmgm",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            events = resp.json()

        return self._normalize_response(events, fixture_id, home_team, away_team)

    def _normalize_response(
        self,
        events: list[dict[str, Any]],
        fixture_id: str,
        home_team: str,
        away_team: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for event in events:
            for bookmaker in event.get("bookmakers", []):
                book_key = bookmaker["key"]
                for market in bookmaker.get("markets", []):
                    market_key = market["key"]
                    market_type = {
                        "h2h": "moneyline",
                        "spreads": "spread",
                        "totals": "over_under",
                    }.get(market_key, market_key)

                    for outcome in market.get("outcomes", []):
                        selection = outcome["name"]
                        if selection == event.get("home_team"):
                            selection = home_team
                        elif selection == event.get("away_team"):
                            selection = away_team

                        rows.append(
                            {
                                "fixture_id": fixture_id,
                                "sportsbook": book_key,
                                "market_type": market_type,
                                "selection": selection,
                                "line": outcome.get("point"),
                                "odds_american": int(outcome["price"]),
                                "captured_at": event.get("commence_time"),
                            }
                        )
        return rows

    async def fetch_all_fixtures_odds(
        self,
        fixtures: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        all_odds: list[dict[str, Any]] = []
        for f in fixtures:
            odds = await self.stream_market_odds(
                fixture_id=f["id"],
                league=f.get("league", "NBA"),
                home_team=f.get("home_team", "Home"),
                away_team=f.get("away_team", "Away"),
            )
            all_odds.extend(odds)
        return all_odds
