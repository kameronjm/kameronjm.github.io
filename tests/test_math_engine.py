from src.core.math_engine import (
    american_to_decimal,
    american_to_implied_probability,
    calculate_expected_value,
    calculate_vig,
    is_positive_ev,
)


class TestAmericanToDecimal:
    def test_positive_odds(self) -> None:
        assert american_to_decimal(150) == 2.5

    def test_negative_odds(self) -> None:
        assert american_to_decimal(-200) == 1.5

    def test_even_odds(self) -> None:
        assert american_to_decimal(100) == 2.0


class TestImpliedProbability:
    def test_heavy_favorite(self) -> None:
        prob = american_to_implied_probability(-300)
        assert abs(prob - 0.75) < 0.001

    def test_underdog(self) -> None:
        prob = american_to_implied_probability(200)
        assert abs(prob - 1 / 3) < 0.001

    def test_even_odds(self) -> None:
        prob = american_to_implied_probability(100)
        assert abs(prob - 0.5) < 0.001


class TestVig:
    def test_standard_vig(self) -> None:
        vig = calculate_vig(-110, -110)
        assert vig > 0
        assert abs(vig - 0.0476) < 0.001

    def test_no_vig_market(self) -> None:
        vig = calculate_vig(100, -100)
        assert abs(vig) < 0.001


class TestExpectedValue:
    def test_positive_ev_bet(self) -> None:
        result = calculate_expected_value(true_probability=0.55, american_odds=100)
        assert result.expected_value > 0
        assert result.ev_percentage > 0

    def test_negative_ev_bet(self) -> None:
        result = calculate_expected_value(true_probability=0.45, american_odds=-110)
        assert result.expected_value < 0
        assert result.ev_percentage < 0

    def test_ev_result_fields(self) -> None:
        result = calculate_expected_value(true_probability=0.60, american_odds=150)
        assert result.implied_probability > 0
        assert result.decimal_odds == 2.5
        assert result.edge > 0


class TestIsPositiveEV:
    def test_above_threshold(self) -> None:
        assert is_positive_ev(0.60, 100, min_ev_threshold=3.0)

    def test_below_threshold(self) -> None:
        assert not is_positive_ev(0.51, 100, min_ev_threshold=5.0)
