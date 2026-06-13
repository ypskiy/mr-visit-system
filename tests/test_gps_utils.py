"""
Unit tests for GPS simulation and distance utilities.
No DB or network required.
"""
import pytest
from app.services.gps_utils import haversine_distance, simulate_gps

# Reference hospital (Shanghai Ruijin)
HOSP_LAT = 31.2154
HOSP_LNG = 121.4619


class TestHaversineDistance:
    def test_same_point_is_zero(self):
        assert haversine_distance(HOSP_LAT, HOSP_LNG, HOSP_LAT, HOSP_LNG) == 0.0

    def test_known_distance(self):
        # Distance between two Shanghai hospitals ~4.3km
        dist = haversine_distance(31.2154, 121.4619, 31.1986, 121.4486)
        assert 2000 < dist < 3000, f"Expected ~2256m, got {dist:.0f}m"

    def test_symmetry(self):
        d1 = haversine_distance(31.2154, 121.4619, 31.250, 121.500)
        d2 = haversine_distance(31.250, 121.500, 31.2154, 121.4619)
        assert abs(d1 - d2) < 1  # within 1 metre

    def test_result_is_non_negative(self):
        d = haversine_distance(0, 0, 0.001, 0.001)
        assert d >= 0


class TestGpsSimulate:
    """
    Statistical tests for the 60/30/10 distribution.
    Run 1000 samples; expected counts with generous margins.
    """
    N = 1000

    @pytest.fixture(scope="class")
    def samples(self):
        results = {"indoor": 0, "nearby": 0, "anomalous": 0}
        for _ in range(self.N):
            lat, lng = simulate_gps(HOSP_LAT, HOSP_LNG)
            d = haversine_distance(lat, lng, HOSP_LAT, HOSP_LNG)
            if d <= 100:
                results["indoor"] += 1
            elif d <= 500:
                results["nearby"] += 1
            else:
                results["anomalous"] += 1
        return results

    def test_indoor_rate_approx_60pct(self, samples):
        rate = samples["indoor"] / self.N
        # Allow ±10% slack for randomness
        assert 0.50 <= rate <= 0.70, f"Indoor rate {rate:.1%} out of expected 60%±10%"

    def test_nearby_rate_approx_30pct(self, samples):
        rate = samples["nearby"] / self.N
        assert 0.20 <= rate <= 0.40, f"Nearby rate {rate:.1%} out of expected 30%±10%"

    def test_anomalous_rate_approx_10pct(self, samples):
        rate = samples["anomalous"] / self.N
        assert 0.04 <= rate <= 0.18, f"Anomalous rate {rate:.1%} out of expected 10%±6%"

    def test_total_is_complete(self, samples):
        assert sum(samples.values()) == self.N

    def test_output_coordinates_are_valid_range(self):
        for _ in range(20):
            lat, lng = simulate_gps(HOSP_LAT, HOSP_LNG)
            assert -90 <= lat <= 90, f"Invalid latitude {lat}"
            assert -180 <= lng <= 180, f"Invalid longitude {lng}"

    def test_simulate_returns_tuple_of_two_floats(self):
        result = simulate_gps(HOSP_LAT, HOSP_LNG)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)
