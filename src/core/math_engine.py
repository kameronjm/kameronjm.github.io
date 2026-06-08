from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KellyResult:
    fraction: float
    stake: float
    edge: float
    full_kelly_fraction: float


@dataclass(frozen=True, slots=True)
class EVResult:
    implied_probability: float
    true_probability: float
    decimal_odds: float
    expected_value: float
    ev_percentage: float
    edge: float


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return (american_odds / 100) + 1
    return (100 / abs(american_odds)) + 1


def american_to_implied_probability(american_odds: int) -> float:
    """Convert American odds to implied probability (0-1 range, includes vig)."""
    if american_odds < 0:
        return abs(american_odds) / (abs(american_odds) + 100)
    return 100 / (american_odds + 100)


def calculate_vig(odds_side_a: int, odds_side_b: int) -> float:
    """Calculate the vig/juice on a two-sided market."""
    implied_a = american_to_implied_probability(odds_side_a)
    implied_b = american_to_implied_probability(odds_side_b)
    return (implied_a + implied_b) - 1.0


def calculate_no_vig_probability(
    american_odds: int,
    odds_side_a: int,
    odds_side_b: int,
) -> float:
    """Remove vig to get a fair probability estimate from market odds."""
    raw = american_to_implied_probability(american_odds)
    total = american_to_implied_probability(odds_side_a) + american_to_implied_probability(
        odds_side_b
    )
    return raw / total


def calculate_expected_value(
    true_probability: float,
    american_odds: int,
    stake: float = 100.0,
) -> EVResult:
    """Calculate expected value of a bet.

    EV = (Probability * Payout) - (Loss Probability * Stake)
    """
    decimal_odds = american_to_decimal(american_odds)
    payout = stake * (decimal_odds - 1)
    loss_probability = 1.0 - true_probability

    ev = (true_probability * payout) - (loss_probability * stake)
    ev_percentage = (ev / stake) * 100

    implied = american_to_implied_probability(american_odds)
    edge = true_probability - implied

    return EVResult(
        implied_probability=round(implied, 6),
        true_probability=round(true_probability, 6),
        decimal_odds=round(decimal_odds, 4),
        expected_value=round(ev, 2),
        ev_percentage=round(ev_percentage, 4),
        edge=round(edge, 6),
    )


def is_positive_ev(
    true_probability: float,
    american_odds: int,
    min_ev_threshold: float = 0.0,
) -> bool:
    """Check whether a bet meets the +EV threshold."""
    result = calculate_expected_value(true_probability, american_odds)
    return result.ev_percentage > min_ev_threshold


def calculate_kelly_wager(
    implied_prob: float,
    fair_prob: float,
    current_bankroll: float,
    fraction: float = 0.25,
) -> KellyResult:
    """Calculate optimal wager using the Fractional Kelly Criterion.

    f* = (bp - q) / b
    where b = decimal_odds - 1, p = fair_prob, q = 1 - p.
    """
    if fair_prob <= 0.0 or fair_prob >= 1.0 or implied_prob <= 0.0 or implied_prob >= 1.0:
        return KellyResult(fraction=0.0, stake=0.0, edge=0.0, full_kelly_fraction=0.0)

    if current_bankroll <= 0.0:
        return KellyResult(fraction=0.0, stake=0.0, edge=0.0, full_kelly_fraction=0.0)

    decimal_odds = 1.0 / implied_prob
    b = decimal_odds - 1.0
    p = fair_prob
    q = 1.0 - p

    if b <= 0.0:
        return KellyResult(fraction=0.0, stake=0.0, edge=0.0, full_kelly_fraction=0.0)

    full_kelly = (b * p - q) / b

    if full_kelly <= 0.0:
        return KellyResult(
            fraction=0.0,
            stake=0.0,
            edge=round(fair_prob - implied_prob, 6),
            full_kelly_fraction=round(full_kelly, 6),
        )

    fractional_kelly = full_kelly * fraction
    stake = round(current_bankroll * fractional_kelly, 2)

    return KellyResult(
        fraction=round(fractional_kelly, 6),
        stake=stake,
        edge=round(fair_prob - implied_prob, 6),
        full_kelly_fraction=round(full_kelly, 6),
    )
