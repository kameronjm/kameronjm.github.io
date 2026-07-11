import logging
from typing import Any

import httpx

from config import settings
from src.core.interfaces import BaseDataIngester
from src.ingestion.mock_data import generate_mock_fixtures, generate_mock_historical

logger = logging.getLogger(__name__)


class SportsDataIngester(BaseDataIngester):
    def __init__(self) -> None:
        self._api_key = settings.stats_api_key
        self._base_url = settings.stats_api_base_url
        self._use_mock = not bool(self._api_key)
        if self._use_mock:
            logger.warning("No STATS_API_KEY set — falling back to mock fixture/stats data")

    async def fetch_historical_data(
        self,
        league: str,
        season: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        if self._use_mock:
            return generate_mock_historical(league)
        return await self._fetch_boxscores(league, season)

    async def fetch_live_data(
        self,
        fixture_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if self._use_mock:
            return {"fixture_id": fixture_id, "status": "mock_live", "data": {}}
        return await self._fetch_live_boxscore(fixture_id)

    async def fetch_todays_fixtures(
        self,
        league: str = "NBA",
    ) -> list[dict[str, Any]]:
        if self._use_mock:
            return generate_mock_fixtures(league)
        return await self._fetch_schedule(league)

    async def _fetch_boxscores(
        self,
        league: str,
        season: str,
    ) -> list[dict[str, Any]]:
        url = f"{self._base_url}/{league.lower()}/stats/json/BoxScores/{season}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"Ocp-Apim-Subscription-Key": self._api_key})
            resp.raise_for_status()
            return resp.json()

    async def _fetch_live_boxscore(self, fixture_id: str) -> dict[str, Any]:
        url = f"{self._base_url}/nba/stats/json/BoxScore/{fixture_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"Ocp-Apim-Subscription-Key": self._api_key})
            resp.raise_for_status()
            return resp.json()

    async def _fetch_schedule(self, league: str) -> list[dict[str, Any]]:
        url = f"{self._base_url}/{league.lower()}/scores/json/GamesByDate/today"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"Ocp-Apim-Subscription-Key": self._api_key})
            resp.raise_for_status()
            raw = resp.json()

        return [
            {
                "id": str(g.get("GameID", "")),
                "external_id": str(g.get("GameID", "")),
                "league": league,
                "home_team": g.get("HomeTeam", ""),
                "away_team": g.get("AwayTeam", ""),
                "scheduled_at": g.get("DateTime", ""),
                "status": g.get("Status", "scheduled").lower(),
                "season": g.get("Season", ""),
            }
            for g in raw
        ]
