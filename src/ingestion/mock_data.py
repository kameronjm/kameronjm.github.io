import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any


def _today_game_time(hour: int) -> str:
    dt = datetime.now(tz=UTC).replace(hour=hour, minute=0, second=0, microsecond=0)
    return dt.isoformat()


_NBA_MATCHUPS: list[dict[str, str]] = [
    {"home": "Boston Celtics", "away": "New York Knicks", "home_abbr": "BOS", "away_abbr": "NYK"},
    {
        "home": "Los Angeles Lakers",
        "away": "Golden State Warriors",
        "home_abbr": "LAL",
        "away_abbr": "GSW",
    },
    {
        "home": "Milwaukee Bucks",
        "away": "Philadelphia 76ers",
        "home_abbr": "MIL",
        "away_abbr": "PHI",
    },
]

_NFL_MATCHUPS: list[dict[str, str]] = [
    {"home": "Kansas City Chiefs", "away": "Buffalo Bills", "home_abbr": "KC", "away_abbr": "BUF"},
    {
        "home": "San Francisco 49ers",
        "away": "Dallas Cowboys",
        "home_abbr": "SF",
        "away_abbr": "DAL",
    },
]

_MLB_MATCHUPS: list[dict[str, str]] = [
    {"home": "New York Yankees", "away": "Boston Red Sox", "home_abbr": "NYY", "away_abbr": "BOS"},
    {
        "home": "Los Angeles Dodgers",
        "away": "San Diego Padres",
        "home_abbr": "LAD",
        "away_abbr": "SD",
    },
]

_LEAGUE_MATCHUPS: dict[str, list[dict[str, str]]] = {
    "NBA": _NBA_MATCHUPS,
    "NFL": _NFL_MATCHUPS,
    "MLB": _MLB_MATCHUPS,
}

SPORTSBOOKS = ["draftkings", "fanduel", "betmgm"]


def generate_mock_fixtures(league: str = "NBA") -> list[dict[str, Any]]:
    matchups = _LEAGUE_MATCHUPS.get(league, _NBA_MATCHUPS)
    fixtures = []
    for i, m in enumerate(matchups):
        fixtures.append(
            {
                "id": str(uuid.uuid4()),
                "external_id": f"mock_{league.lower()}_{i}",
                "league": league,
                "home_team": m["home"],
                "home_abbreviation": m["home_abbr"],
                "away_team": m["away"],
                "away_abbreviation": m["away_abbr"],
                "scheduled_at": _today_game_time(19 + i),
                "status": "scheduled",
                "season": "2025-26",
            }
        )
    return fixtures


def _random_moneyline() -> tuple[int, int]:
    spread = random.randint(110, 300)
    if random.random() > 0.5:
        return -spread, spread - random.randint(0, 30)
    return spread - random.randint(0, 30), -spread


def _random_spread() -> tuple[float, int, int]:
    pts = round(random.uniform(1.0, 10.5) * 2) / 2
    return pts, -110 + random.randint(-5, 5), -110 + random.randint(-5, 5)


def _random_total(league: str) -> tuple[float, int, int]:
    base = {"NBA": 220.0, "NFL": 45.0, "MLB": 8.5}.get(league, 45.0)
    total = base + round(random.uniform(-5, 5) * 2) / 2
    return total, -110 + random.randint(-5, 5), -110 + random.randint(-5, 5)


def generate_mock_odds(
    fixture_id: str,
    home_team: str,
    away_team: str,
    league: str = "NBA",
) -> list[dict[str, Any]]:
    odds_rows: list[dict[str, Any]] = []
    now = datetime.now(tz=UTC).isoformat()

    for book in SPORTSBOOKS:
        home_ml, away_ml = _random_moneyline()
        odds_rows.append(
            {
                "fixture_id": fixture_id,
                "sportsbook": book,
                "market_type": "moneyline",
                "selection": home_team,
                "line": None,
                "odds_american": home_ml,
                "captured_at": now,
            }
        )
        odds_rows.append(
            {
                "fixture_id": fixture_id,
                "sportsbook": book,
                "market_type": "moneyline",
                "selection": away_team,
                "line": None,
                "odds_american": away_ml,
                "captured_at": now,
            }
        )

        spread_pts, spread_home, spread_away = _random_spread()
        odds_rows.append(
            {
                "fixture_id": fixture_id,
                "sportsbook": book,
                "market_type": "spread",
                "selection": home_team,
                "line": -spread_pts,
                "odds_american": spread_home,
                "captured_at": now,
            }
        )
        odds_rows.append(
            {
                "fixture_id": fixture_id,
                "sportsbook": book,
                "market_type": "spread",
                "selection": away_team,
                "line": spread_pts,
                "odds_american": spread_away,
                "captured_at": now,
            }
        )

        total_pts, over_odds, under_odds = _random_total(league)
        odds_rows.append(
            {
                "fixture_id": fixture_id,
                "sportsbook": book,
                "market_type": "over_under",
                "selection": "Over",
                "line": total_pts,
                "odds_american": over_odds,
                "captured_at": now,
            }
        )
        odds_rows.append(
            {
                "fixture_id": fixture_id,
                "sportsbook": book,
                "market_type": "over_under",
                "selection": "Under",
                "line": total_pts,
                "odds_american": under_odds,
                "captured_at": now,
            }
        )

    return odds_rows


def generate_mock_historical(league: str = "NBA") -> list[dict[str, Any]]:
    matchups = _LEAGUE_MATCHUPS.get(league, _NBA_MATCHUPS)
    records: list[dict[str, Any]] = []
    base = datetime.now(tz=UTC) - timedelta(days=7)

    for i, m in enumerate(matchups):
        game_dt = (base + timedelta(days=i)).isoformat()
        if league == "NBA":
            stats = [
                ("points", random.uniform(95, 130)),
                ("rebounds", random.uniform(38, 55)),
                ("assists", random.uniform(18, 32)),
            ]
        elif league == "NFL":
            stats = [
                ("passing_yards", random.uniform(180, 350)),
                ("rushing_yards", random.uniform(60, 180)),
                ("total_points", random.uniform(14, 42)),
            ]
        else:
            stats = [
                ("hits", random.uniform(4, 14)),
                ("runs", random.uniform(1, 10)),
                ("era", random.uniform(2.0, 6.0)),
            ]

        for team_key in ("home", "away"):
            for stat_type, value in stats:
                records.append(
                    {
                        "fixture_external_id": f"mock_{league.lower()}_{i}",
                        "team_name": m[team_key],
                        "stat_type": stat_type,
                        "stat_value": round(value + random.uniform(-5, 5), 1),
                        "recorded_at": game_dt,
                    }
                )

    return records


def generate_baseline_projection(
    fixture_id: str,
    home_team: str,
    away_team: str,
    league: str = "NBA",
) -> dict[str, Any]:
    if league == "NBA":
        home_score = round(random.uniform(100, 120), 1)
        away_score = round(random.uniform(98, 118), 1)
    elif league == "NFL":
        home_score = round(random.uniform(17, 31), 1)
        away_score = round(random.uniform(14, 28), 1)
    else:
        home_score = round(random.uniform(3, 7), 1)
        away_score = round(random.uniform(2, 6), 1)

    total = home_score + away_score
    home_wp = round(0.5 + (home_score - away_score) / (total or 1) * 0.3, 4)
    home_wp = max(0.05, min(0.95, home_wp))

    return {
        "fixture_id": fixture_id,
        "model_name": "baseline_v1",
        "model_version": "0.1.0",
        "predicted_home_score": home_score,
        "predicted_away_score": away_score,
        "home_win_probability": home_wp,
        "away_win_probability": round(1.0 - home_wp, 4),
        "predicted_total": round(total, 1),
    }
