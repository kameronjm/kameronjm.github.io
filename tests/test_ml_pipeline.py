from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from src.core.math_engine import calculate_expected_value
from src.database.models import (
    CustomModelConfiguration,
    Fixture,
    HistoricalStats,
    League,
    ModelCoefficients,
    Team,
)
from src.models.backtester import _calculate_drawdown
from src.models.features import (
    FeatureMatrixBuilder,
    compute_rolling_averages,
    flatten_boxscore_json,
    mirror_opponent_features,
    mirror_pitcher_features,
    predict_from_coefficients,
)
from src.models.trainer import (
    TrainingResult,
    _compute_r_value,
    build_training_arrays,
    train_classifier,
    train_regression,
)

COMPLEX_FEATURE_LIST = [
    "batting_average",
    "on_base_percentage",
    "slugging_percentage",
    "ops",
    "hits",
    "runs",
    "home_runs",
    "rbi",
    "stolen_bases",
    "strikeouts",
    "walks",
    "ground_ball_fly_ball_ratio",
    "line_drive_percentage",
    "hard_hit_percentage",
    "barrel_percentage",
    "exit_velocity",
    "launch_angle",
    "sprint_speed",
    "war",
    "wrc_plus",
    "Opponent era",
    "Opponent whip",
    "Opponent strikeouts_per_9",
    "Opponent walks_per_9",
    "Opponent hr_per_9",
    "Opponent fip",
    "Opponent ground_ball_percentage",
    "Opponent left_on_base_percentage",
    "Starting Pitcher fip_plus",
    "Starting Pitcher xfip",
    "Starting Pitcher siera",
    "Starting Pitcher k_percentage",
    "Starting Pitcher bb_percentage",
    "Starting Pitcher hr_fb_ratio",
    "Starting Pitcher era",
    "Starting Pitcher innings_pitched",
    "Opponent catcher_putouts",
    "Opponent fielding_percentage",
]


class TestFlattenBoxscoreJSON:
    def test_extracts_matching_keys(self) -> None:
        payload = {
            "batting_average": 0.285,
            "ops": 0.810,
            "era": 3.45,
            "unrelated": "ignore",
        }
        result = flatten_boxscore_json(payload, ["batting_average", "ops", "war"])
        assert result["batting_average"] == 0.285
        assert result["ops"] == 0.810
        assert result["war"] == 0.0

    def test_none_payload_returns_zeros(self) -> None:
        result = flatten_boxscore_json(None, ["batting_average", "ops"])
        assert result == {"batting_average": 0.0, "ops": 0.0}

    def test_nested_dot_notation(self) -> None:
        payload = {"pitching": {"era": 3.25, "whip": 1.10}}
        result = flatten_boxscore_json(payload, ["pitching.era", "pitching.whip"])
        assert result["pitching.era"] == 3.25
        assert result["pitching.whip"] == 1.10

    def test_non_numeric_value_becomes_zero(self) -> None:
        payload = {"batting_average": "N/A"}
        result = flatten_boxscore_json(payload, ["batting_average"])
        assert result["batting_average"] == 0.0


class TestMirrorPrefixes:
    def test_opponent_prefix(self) -> None:
        features = {"era": 3.50, "whip": 1.20}
        mirrored = mirror_opponent_features(features)
        assert mirrored == {"Opponent era": 3.50, "Opponent whip": 1.20}

    def test_pitcher_prefix(self) -> None:
        features = {"fip_plus": 95.0, "xfip": 3.80}
        mirrored = mirror_pitcher_features(features)
        assert mirrored == {
            "Starting Pitcher fip_plus": 95.0,
            "Starting Pitcher xfip": 3.80,
        }

    def test_custom_prefix(self) -> None:
        features = {"era": 3.0}
        mirrored = mirror_opponent_features(features, prefix="Away ")
        assert mirrored == {"Away era": 3.0}


class TestRollingAverages:
    def test_basic_rolling(self) -> None:
        rows = [{"hits": 8.0}, {"hits": 10.0}, {"hits": 12.0}]
        avg = compute_rolling_averages(rows, window=3)
        assert abs(avg["hits"] - 10.0) < 0.001

    def test_window_larger_than_data(self) -> None:
        rows = [{"runs": 5.0}, {"runs": 7.0}]
        avg = compute_rolling_averages(rows, window=10)
        assert abs(avg["runs"] - 6.0) < 0.001

    def test_window_truncates_old_games(self) -> None:
        rows = [
            {"hits": 1.0},
            {"hits": 2.0},
            {"hits": 100.0},
            {"hits": 100.0},
        ]
        avg = compute_rolling_averages(rows, window=2)
        assert abs(avg["hits"] - 100.0) < 0.001

    def test_empty_rows(self) -> None:
        assert compute_rolling_averages([], window=5) == {}

    def test_multiple_features(self) -> None:
        rows = [
            {"hits": 8.0, "runs": 4.0, "era": 3.0},
            {"hits": 10.0, "runs": 6.0, "era": 4.0},
        ]
        avg = compute_rolling_averages(rows, window=5)
        assert abs(avg["hits"] - 9.0) < 0.001
        assert abs(avg["runs"] - 5.0) < 0.001
        assert abs(avg["era"] - 3.5) < 0.001


class TestFeatureMatrixBuilder:
    def test_parses_all_feature_categories(self) -> None:
        builder = FeatureMatrixBuilder(COMPLEX_FEATURE_LIST, rolling_window=10)
        assert len(builder._base_keys) == 20
        assert len(builder._opponent_keys) == 10
        assert len(builder._pitcher_keys) == 8

    def test_ordered_names_complete(self) -> None:
        builder = FeatureMatrixBuilder(COMPLEX_FEATURE_LIST, rolling_window=10)
        names = builder.ordered_feature_names
        assert len(names) == len(COMPLEX_FEATURE_LIST)
        assert names[0] == "batting_average"
        assert any(n.startswith("Opponent ") for n in names)
        assert any(n.startswith("Starting Pitcher ") for n in names)

    def test_rolling_vector_all_keys_present(self) -> None:
        builder = FeatureMatrixBuilder(COMPLEX_FEATURE_LIST, rolling_window=5)
        home_rows = [
            {k: float(i + 1) for k in builder._base_keys + builder._pitcher_keys} for i in range(5)
        ]
        away_rows = [{k: float(i + 10) for k in builder._opponent_keys} for i in range(5)]
        vector = builder.build_rolling_feature_vector(home_rows, away_rows)

        for name in builder.ordered_feature_names:
            assert name in vector, f"Missing feature: {name}"
            assert isinstance(vector[name], float)

    def test_rolling_vector_no_missing_keys(self) -> None:
        sub_features = [
            "batting_average",
            "ops",
            "Opponent era",
            "Starting Pitcher fip_plus",
        ]
        builder = FeatureMatrixBuilder(sub_features, rolling_window=3)
        vector = builder.build_rolling_feature_vector(
            [{"batting_average": 0.3, "ops": 0.8, "fip_plus": 90.0}],
            [{"era": 3.5}],
        )
        assert set(vector.keys()) == set(builder.ordered_feature_names)


class TestPredictFromCoefficients:
    def test_simple_dot_product(self) -> None:
        vector = {"a": 2.0, "b": 3.0}
        result = predict_from_coefficients(vector, intercept=1.0, weights={"a": 0.5, "b": -1.0})
        assert abs(result - (1.0 + 2.0 * 0.5 + 3.0 * (-1.0))) < 1e-9

    def test_missing_feature_treated_as_zero(self) -> None:
        vector = {"a": 2.0}
        result = predict_from_coefficients(
            vector, intercept=0.0, weights={"a": 1.0, "missing": 5.0}
        )
        assert abs(result - 2.0) < 1e-9

    def test_with_complex_features(self) -> None:
        weights = {name: 0.01 for name in COMPLEX_FEATURE_LIST}
        vector = {name: 1.0 for name in COMPLEX_FEATURE_LIST}
        result = predict_from_coefficients(vector, intercept=0.0, weights=weights)
        expected = len(COMPLEX_FEATURE_LIST) * 0.01
        assert abs(result - expected) < 1e-9


class TestTrainRegression:
    def test_ridge_fits_linear_data(self) -> None:
        np.random.seed(42)
        n = 100
        X = np.random.randn(n, 3)
        y = 2.0 * X[:, 0] - 1.0 * X[:, 1] + 0.5 * X[:, 2] + np.random.randn(n) * 0.1

        result = train_regression(X, y, ["f1", "f2", "f3"], split_ratio=0.8)
        assert isinstance(result, TrainingResult)
        assert result.r_value > 0.8
        assert result.test_loss < 1.0
        assert result.train_samples == 80
        assert result.test_samples == 20
        assert len(result.weights) == 3
        assert len(result.scaler_mean) == 3

    def test_minimum_data(self) -> None:
        X = np.array([[1.0], [2.0], [3.0], [4.0], [5.0]])
        y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        result = train_regression(X, y, ["x"], split_ratio=0.8)
        assert result.train_samples == 4
        assert result.test_samples == 1


class TestTrainClassifier:
    def test_logistic_fits_separable_data(self) -> None:
        np.random.seed(42)
        n = 200
        X = np.random.randn(n, 2)
        y = (X[:, 0] + X[:, 1] > 0).astype(float)

        result = train_classifier(X, y, ["f1", "f2"], split_ratio=0.8)
        assert isinstance(result, TrainingResult)
        assert result.r_value > 0.5
        assert len(result.weights) == 2
        assert result.train_samples == 160
        assert result.test_samples == 40


class TestBuildTrainingArrays:
    def test_builds_arrays_from_dicts(self) -> None:
        rows = [
            {"a": 1.0, "b": 2.0, "target": 10.0},
            {"a": 3.0, "b": 4.0, "target": 20.0},
            {"a": 5.0, "b": 6.0, "target": 30.0},
        ]
        X, y = build_training_arrays(rows, ["a", "b"], "target")
        assert X.shape == (3, 2)
        assert y.shape == (3,)
        np.testing.assert_array_equal(y, [10.0, 20.0, 30.0])

    def test_missing_columns_filled_with_zero(self) -> None:
        rows = [{"a": 1.0, "target": 5.0}]
        X, y = build_training_arrays(rows, ["a", "missing_col"], "target")
        assert X[0, 1] == 0.0

    def test_complex_feature_names(self) -> None:
        rows = [
            {
                "batting_average": 0.3,
                "Opponent era": 3.5,
                "Starting Pitcher fip_plus": 95.0,
                "target": 5.0,
            },
        ]
        X, y = build_training_arrays(
            rows,
            ["batting_average", "Opponent era", "Starting Pitcher fip_plus"],
            "target",
        )
        assert X.shape == (1, 3)
        assert X[0, 0] == 0.3


class TestRValue:
    def test_positive_r_squared(self) -> None:
        assert abs(_compute_r_value(0.81) - 0.9) < 0.001

    def test_negative_r_squared(self) -> None:
        r = _compute_r_value(-0.25)
        assert r < 0
        assert abs(r - (-0.5)) < 0.001

    def test_zero_r_squared(self) -> None:
        assert _compute_r_value(0.0) == 0.0


class TestBacktesterDrawdown:
    def test_no_drawdown(self) -> None:
        assert _calculate_drawdown([100, 101, 102, 103]) == 0.0

    def test_simple_drawdown(self) -> None:
        dd = _calculate_drawdown([100, 110, 90, 95])
        assert dd > 0
        assert abs(dd - 18.1818) < 0.1

    def test_single_point(self) -> None:
        assert _calculate_drawdown([100]) == 0.0


class TestDBIntegration:
    @pytest.mark.asyncio
    async def test_feature_builder_with_db(self, db_session) -> None:
        league = League(code="ML_T", full_name="ML Test")
        db_session.add(league)
        await db_session.flush()

        team = Team(league_id=league.id, name="ML Team", abbreviation="MLT", city="MLCity")
        opp = Team(league_id=league.id, name="ML Opp", abbreviation="MLO", city="MLCity")
        db_session.add_all([team, opp])
        await db_session.flush()

        base_dt = datetime.now(tz=UTC) - timedelta(days=10)
        for i in range(5):
            fixture = Fixture(
                league_id=league.id,
                home_team_id=team.id,
                away_team_id=opp.id,
                scheduled_at=base_dt + timedelta(days=i),
                status="final",
                season="2025",
                home_score=100 + i,
                away_score=95 + i,
            )
            db_session.add(fixture)
            await db_session.flush()

            stat = HistoricalStats(
                fixture_id=fixture.id,
                team_id=team.id,
                stat_type="batting_average",
                stat_value=0.250 + i * 0.01,
                boxscore_data={
                    "batting_average": 0.250 + i * 0.01,
                    "ops": 0.750 + i * 0.02,
                    "era": 3.50 - i * 0.1,
                    "fip_plus": 100 + i,
                },
                recorded_at=base_dt + timedelta(days=i),
            )
            db_session.add(stat)

            opp_stat = HistoricalStats(
                fixture_id=fixture.id,
                team_id=opp.id,
                stat_type="era",
                stat_value=4.0 + i * 0.1,
                boxscore_data={
                    "era": 4.0 + i * 0.1,
                    "whip": 1.3 + i * 0.05,
                    "catcher_putouts": 5.0 + i,
                },
                recorded_at=base_dt + timedelta(days=i),
            )
            db_session.add(opp_stat)

        await db_session.flush()

        builder = FeatureMatrixBuilder(
            [
                "batting_average",
                "ops",
                "Opponent era",
                "Opponent whip",
                "Starting Pitcher fip_plus",
            ],
            rolling_window=5,
        )

        rows, names = await builder.build_historical_matrix(db_session, team.id, opp.id, limit=100)
        assert len(rows) > 0
        assert len(names) == 5
        for row in rows:
            for name in names:
                assert name in row

    @pytest.mark.asyncio
    async def test_model_config_and_coefficients(self, db_session) -> None:
        config = CustomModelConfiguration(
            name="test_model",
            league="MLB",
            target_type="regression",
            target_stat="total_runs",
            feature_list={"features": COMPLEX_FEATURE_LIST},
            rolling_window=10,
        )
        db_session.add(config)
        await db_session.flush()

        coeff = ModelCoefficients(
            config_id=config.id,
            intercept=2.5,
            weights={name: 0.01 for name in COMPLEX_FEATURE_LIST},
            r_value=0.75,
            test_loss=1.2,
            train_samples=500,
            test_samples=125,
            metadata_extra={
                "feature_names": COMPLEX_FEATURE_LIST,
                "scaler_mean": [0.0] * len(COMPLEX_FEATURE_LIST),
                "scaler_scale": [1.0] * len(COMPLEX_FEATURE_LIST),
            },
        )
        db_session.add(coeff)
        await db_session.flush()

        assert coeff.config_id == config.id
        assert len(coeff.weights) == len(COMPLEX_FEATURE_LIST)
        assert coeff.r_value == 0.75

    @pytest.mark.asyncio
    async def test_end_to_end_inference(self, db_session) -> None:
        config = CustomModelConfiguration(
            name="e2e_model",
            league="MLB",
            target_type="regression",
            target_stat="total_runs",
            feature_list={"features": ["batting_average", "ops", "Opponent era"]},
            rolling_window=5,
        )
        db_session.add(config)
        await db_session.flush()

        weights = {"batting_average": 10.0, "ops": 5.0, "Opponent era": -2.0}
        coeff = ModelCoefficients(
            config_id=config.id,
            intercept=3.0,
            weights=weights,
            r_value=0.80,
            test_loss=0.5,
            train_samples=100,
            test_samples=25,
            metadata_extra={
                "feature_names": list(weights.keys()),
            },
        )
        db_session.add(coeff)
        await db_session.flush()

        feature_vector = {
            "batting_average": 0.280,
            "ops": 0.800,
            "Opponent era": 3.50,
        }

        projection = predict_from_coefficients(feature_vector, coeff.intercept, coeff.weights)
        expected = 3.0 + 0.280 * 10.0 + 0.800 * 5.0 - 3.50 * 2.0
        assert abs(projection - expected) < 1e-9

        ev = calculate_expected_value(0.60, 150)
        assert ev.ev_percentage > 0
