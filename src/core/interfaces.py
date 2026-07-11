from abc import ABC, abstractmethod
from typing import Any

from src.database.models import Fixture


class BaseDataIngester(ABC):
    """Contract for all data ingestion sources (stats providers, APIs)."""

    @abstractmethod
    async def fetch_historical_data(
        self,
        league: str,
        season: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Retrieve historical boxscore and stat data for a given league/season."""
        ...

    @abstractmethod
    async def fetch_live_data(
        self,
        fixture_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Retrieve live in-game data for an active fixture."""
        ...


class BaseOddsProvider(ABC):
    """Contract for all odds feed integrations (DraftKings, FanDuel, etc.)."""

    @abstractmethod
    async def stream_market_odds(
        self,
        fixture_id: str,
        market_types: list[str] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Stream or poll current market odds for a fixture."""
        ...


class BasePredictiveModel(ABC):
    """Contract for all predictive model implementations (game sims, prop models)."""

    @abstractmethod
    def train(
        self,
        training_data: list[dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        """Train or retrain the model on a dataset."""
        ...

    @abstractmethod
    def predict_game_outcome(
        self,
        fixture: Fixture,
        **kwargs: Any,
    ) -> dict[str, float]:
        """Generate score projections and win probabilities for a fixture.

        Returns dict with keys: predicted_home_score, predicted_away_score,
        home_win_probability, away_win_probability, predicted_total.
        """
        ...

    @abstractmethod
    def predict_player_props(
        self,
        fixture: Fixture,
        player_name: str,
        prop_type: str,
        **kwargs: Any,
    ) -> dict[str, float]:
        """Generate a player prop projection.

        Returns dict with keys: projected_value, over_probability, under_probability.
        """
        ...
