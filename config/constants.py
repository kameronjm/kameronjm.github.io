from enum import StrEnum


class League(StrEnum):
    NFL = "NFL"
    NBA = "NBA"
    MLB = "MLB"


class MarketType(StrEnum):
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    OVER_UNDER = "over_under"
    PLAYER_PROP = "player_prop"


class FixtureStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    FINAL = "final"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


SPORTSBOOKS: dict[str, str] = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars Sportsbook",
    "pointsbet": "PointsBet",
    "barstool": "Barstool Sportsbook",
    "bet365": "Bet365",
    "bovada": "Bovada",
}

LEAGUE_METADATA: dict[League, dict[str, str | int]] = {
    League.NFL: {
        "full_name": "National Football League",
        "country": "US",
        "season_type": "weekly",
        "teams_count": 32,
    },
    League.NBA: {
        "full_name": "National Basketball Association",
        "country": "US",
        "season_type": "daily",
        "teams_count": 30,
    },
    League.MLB: {
        "full_name": "Major League Baseball",
        "country": "US",
        "season_type": "daily",
        "teams_count": 30,
    },
}
