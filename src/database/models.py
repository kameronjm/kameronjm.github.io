import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(50), default="US")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    teams: Mapped[list["Team"]] = relationship(back_populates="league")
    fixtures: Mapped[list["Fixture"]] = relationship(back_populates="league")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    league_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leagues.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(10), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    conference: Mapped[str | None] = mapped_column(String(50))
    division: Mapped[str | None] = mapped_column(String(50))
    external_id: Mapped[str | None] = mapped_column(
        String(50), comment="ID from external data provider"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    league: Mapped["League"] = relationship(back_populates="teams")
    home_fixtures: Mapped[list["Fixture"]] = relationship(
        back_populates="home_team", foreign_keys="Fixture.home_team_id"
    )
    away_fixtures: Mapped[list["Fixture"]] = relationship(
        back_populates="away_team", foreign_keys="Fixture.away_team_id"
    )

    __table_args__ = (
        Index("ix_teams_league_abbreviation", "league_id", "abbreviation", unique=True),
    )


class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    league_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leagues.id"), nullable=False
    )
    home_team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    away_team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    week: Mapped[int | None] = mapped_column(Integer, comment="Applicable for NFL weekly schedule")
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    external_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    league: Mapped["League"] = relationship(back_populates="fixtures")
    home_team: Mapped["Team"] = relationship(
        back_populates="home_fixtures", foreign_keys=[home_team_id]
    )
    away_team: Mapped["Team"] = relationship(
        back_populates="away_fixtures", foreign_keys=[away_team_id]
    )
    stats: Mapped[list["HistoricalStats"]] = relationship(back_populates="fixture")
    odds: Mapped[list["MarketOdds"]] = relationship(back_populates="fixture")
    predictions: Mapped[list["ModelPrediction"]] = relationship(back_populates="fixture")

    __table_args__ = (
        Index("ix_fixtures_scheduled", "league_id", "scheduled_at"),
        Index("ix_fixtures_status", "status"),
    )


class HistoricalStats(Base):
    __tablename__ = "historical_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fixture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fixtures.id"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    player_name: Mapped[str | None] = mapped_column(String(150))
    stat_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="e.g. passing_yards, rebounds, hits"
    )
    stat_value: Mapped[float] = mapped_column(Float, nullable=False)
    boxscore_data: Mapped[dict | None] = mapped_column(
        JSON, comment="Full boxscore payload for extended metrics"
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    fixture: Mapped["Fixture"] = relationship(back_populates="stats")

    __table_args__ = (
        Index("ix_stats_fixture_team", "fixture_id", "team_id"),
        Index("ix_stats_player", "player_name"),
    )


class MarketOdds(Base):
    __tablename__ = "market_odds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fixture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fixtures.id"), nullable=False
    )
    sportsbook: Mapped[str] = mapped_column(String(50), nullable=False)
    market_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="spread, moneyline, over_under, player_prop"
    )
    selection: Mapped[str] = mapped_column(
        String(150), nullable=False, comment="e.g. team name, Over, player name"
    )
    line: Mapped[float | None] = mapped_column(
        Float, comment="Spread or total value, null for moneyline"
    )
    odds_american: Mapped[int] = mapped_column(Integer, nullable=False)
    odds_decimal: Mapped[float | None] = mapped_column(Float)
    vig: Mapped[float | None] = mapped_column(Float, comment="Calculated vig/juice percentage")
    prop_description: Mapped[str | None] = mapped_column(
        Text, comment="Player prop detail, e.g. 'Patrick Mahomes Over 275.5 Passing Yards'"
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    fixture: Mapped["Fixture"] = relationship(back_populates="odds")

    __table_args__ = (
        Index("ix_odds_fixture_book_market", "fixture_id", "sportsbook", "market_type"),
        Index("ix_odds_captured", "captured_at"),
    )


class ModelPrediction(Base):
    __tablename__ = "model_predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fixture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fixtures.id"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    predicted_home_score: Mapped[float | None] = mapped_column(Float)
    predicted_away_score: Mapped[float | None] = mapped_column(Float)
    home_win_probability: Mapped[float | None] = mapped_column(Float)
    away_win_probability: Mapped[float | None] = mapped_column(Float)
    predicted_total: Mapped[float | None] = mapped_column(Float)
    edge_vs_market: Mapped[float | None] = mapped_column(
        Float, comment="Calculated edge: our probability minus implied market probability"
    )
    ev_percentage: Mapped[float | None] = mapped_column(
        Float, comment="Expected value as a percentage of stake"
    )
    prediction_metadata: Mapped[dict | None] = mapped_column(
        JSON, comment="Additional prediction context and feature importances"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    fixture: Mapped["Fixture"] = relationship(back_populates="predictions")

    __table_args__ = (
        Index("ix_predictions_fixture_model", "fixture_id", "model_name"),
        Index("ix_predictions_ev", "ev_percentage"),
    )


class EVOpportunity(Base):
    __tablename__ = "ev_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fixture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fixtures.id"), nullable=False
    )
    market_odds_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("market_odds.id"), nullable=False
    )
    sportsbook: Mapped[str] = mapped_column(String(50), nullable=False)
    market_type: Mapped[str] = mapped_column(String(30), nullable=False)
    selection: Mapped[str] = mapped_column(String(150), nullable=False)
    odds_american: Mapped[int] = mapped_column(Integer, nullable=False)
    implied_probability: Mapped[float] = mapped_column(Float, nullable=False)
    fair_probability: Mapped[float] = mapped_column(Float, nullable=False)
    edge: Mapped[float] = mapped_column(Float, nullable=False)
    ev_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    fixture: Mapped["Fixture"] = relationship()
    market_odds_record: Mapped["MarketOdds"] = relationship()

    __table_args__ = (
        Index("ix_ev_opps_active", "is_active", "ev_percentage"),
        Index("ix_ev_opps_fixture", "fixture_id"),
    )


class CustomModelConfiguration(Base):
    __tablename__ = "custom_model_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    league: Mapped[str] = mapped_column(String(10), nullable=False)
    target_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="regression or classification",
    )
    target_stat: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The outcome variable: e.g. total_points, win, over_under",
    )
    feature_list: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON array of feature key strings selected for this model",
    )
    rolling_window: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    coefficients: Mapped[list["ModelCoefficients"]] = relationship(back_populates="configuration")

    __table_args__ = (Index("ix_model_config_league_active", "league", "is_active"),)


class ModelCoefficients(Base):
    __tablename__ = "model_coefficients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_model_configurations.id"),
        nullable=False,
    )
    intercept: Mapped[float] = mapped_column(Float, nullable=False)
    weights: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Map of feature_name -> coefficient beta_n",
    )
    r_value: Mapped[float | None] = mapped_column(Float)
    test_loss: Mapped[float | None] = mapped_column(Float)
    train_samples: Mapped[int | None] = mapped_column(Integer)
    test_samples: Mapped[int | None] = mapped_column(Integer)
    metadata_extra: Mapped[dict | None] = mapped_column(
        JSON, comment="Scaler params, feature means, etc."
    )
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    configuration: Mapped["CustomModelConfiguration"] = relationship(back_populates="coefficients")

    __table_args__ = (Index("ix_coefficients_config", "config_id"),)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), default="Default")
    starting_balance: Mapped[float] = mapped_column(Float, nullable=False)
    current_balance: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bets: Mapped[list["PlacedBet"]] = relationship(back_populates="portfolio")


class PlacedBet(Base):
    __tablename__ = "placed_bets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False
    )
    ev_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ev_opportunities.id"), nullable=False
    )
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("custom_model_configurations.id")
    )
    stake_amount: Mapped[float] = mapped_column(Float, nullable=False)
    odds_taken: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Decimal odds at time of placement"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", comment="PENDING, WON, LOST, PUSH"
    )
    pnl: Mapped[float | None] = mapped_column(Float)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    portfolio: Mapped["Portfolio"] = relationship(back_populates="bets")
    ev_opportunity: Mapped["EVOpportunity"] = relationship()
    model_config_ref: Mapped["CustomModelConfiguration | None"] = relationship()

    __table_args__ = (
        Index("ix_placed_bets_portfolio", "portfolio_id"),
        Index("ix_placed_bets_status", "status"),
    )
