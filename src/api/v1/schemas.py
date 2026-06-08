import uuid
from datetime import datetime

from pydantic import BaseModel


class FixtureResponse(BaseModel):
    id: uuid.UUID
    league_code: str
    home_team: str
    away_team: str
    scheduled_at: datetime
    status: str
    season: str
    home_score: int | None = None
    away_score: int | None = None


class OddsResponse(BaseModel):
    id: uuid.UUID
    sportsbook: str
    market_type: str
    selection: str
    line: float | None = None
    odds_american: int
    odds_decimal: float | None = None
    captured_at: datetime


class EVOpportunityResponse(BaseModel):
    id: uuid.UUID
    fixture_id: uuid.UUID
    home_team: str
    away_team: str
    sportsbook: str
    market_type: str
    selection: str
    odds_american: int
    implied_probability: float
    fair_probability: float
    edge: float
    ev_percentage: float
    discovered_at: datetime
