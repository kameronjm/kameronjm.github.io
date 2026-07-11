import uuid
from datetime import datetime

from pydantic import BaseModel, Field


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
    recommended_kelly_wager: float | None = None


# --- Model Builder Schemas ---


class TrainModelRequest(BaseModel):
    league: str = Field(description="League code: NBA, NFL, MLB")
    target_variable: str = Field(description="Target stat to predict, e.g. total_points")
    target_type: str = Field(default="regression", description="regression or classification")
    feature_list: list[str] = Field(min_length=1, description="Feature keys to train on")
    rolling_window: int = Field(default=10, ge=1, le=100)
    name: str | None = Field(
        default=None, description="Optional model name; auto-generated if omitted"
    )


class TrainModelResponse(BaseModel):
    model_id: uuid.UUID
    config_id: uuid.UUID
    name: str
    r_value: float | None
    test_loss: float | None
    train_samples: int | None
    test_samples: int | None
    feature_count: int


class BacktestRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    ev_threshold: float = Field(default=3.0, ge=0.0)
    unit_size: float = Field(default=1.0, gt=0.0)


class BacktestResponse(BaseModel):
    model_id: uuid.UUID
    total_bets: int
    wins: int
    losses: int
    net_units: float
    win_percentage: float
    roi_percentage: float
    max_drawdown: float
    bankroll_history: list[float]


# --- Portfolio Schemas ---


class CreatePortfolioRequest(BaseModel):
    starting_balance: float = Field(gt=0.0)
    currency: str = Field(default="USD", max_length=10)
    name: str = Field(default="Default", max_length=100)


class PortfolioResponse(BaseModel):
    id: uuid.UUID
    name: str
    starting_balance: float
    current_balance: float
    currency: str
    total_bets: int
    total_pnl: float
    win_rate: float
    created_at: datetime


class PlaceBetRequest(BaseModel):
    portfolio_id: uuid.UUID
    ev_opportunity_id: uuid.UUID
    kelly_fraction: float = Field(
        default=0.25, gt=0.0, le=1.0, description="Fraction of Kelly to use"
    )
    override_stake: float | None = Field(
        default=None, gt=0.0, description="Manual stake override; skips Kelly sizing"
    )


class PlacedBetResponse(BaseModel):
    id: uuid.UUID
    portfolio_id: uuid.UUID
    ev_opportunity_id: uuid.UUID
    stake_amount: float
    odds_taken: float
    status: str
    remaining_balance: float
    kelly_fraction_used: float | None = None
