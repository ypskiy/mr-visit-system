"""
Unit tests for the compliance scoring algorithm.
All tests are pure Python — no DB, no network.
"""
import pytest
from datetime import datetime, timezone

from app.services.compliance_service import run_compliance_check, ALLOWED_MATERIALS

# ── Shared test data ──────────────────────────────────────────────────────────
HOSP_LAT = 31.2154
HOSP_LNG = 121.4619

# Coordinates well within 500m of hospital
NEAR_LAT = 31.2158
NEAR_LNG = 121.4623

# Coordinates far from hospital (>500m)
FAR_LAT = 31.2500
FAR_LNG = 121.5000

GOOD_CHECKIN = datetime(2026, 6, 16, 9, 0, 0, tzinfo=timezone.utc)   # Monday 09:00
GOOD_CHECKOUT = datetime(2026, 6, 16, 9, 35, 0, tzinfo=timezone.utc)  # 35 minutes

GOOD_TEXT = "详细讨论了产品在心血管疾病中的临床应用证据"  # ≥10 chars
GOOD_FEEDBACK = "医生认为产品安全性良好，有意向在下次门诊中尝试使用"

VALID_MATERIAL = "文献复印件"


def make_result(
    *,
    checkin_lat=NEAR_LAT,
    checkin_lng=NEAR_LNG,
    checkin_time=GOOD_CHECKIN,
    checkout_time=GOOD_CHECKOUT,
    duration_minutes=35,
    hospital_lat=HOSP_LAT,
    hospital_lng=HOSP_LNG,
    talking_points=GOOD_TEXT,
    doctor_feedback=GOOD_FEEDBACK,
    materials_distributed=False,
    material_type=None,
):
    return run_compliance_check(
        checkin_time=checkin_time,
        checkin_lat=checkin_lat,
        checkin_lng=checkin_lng,
        checkout_time=checkout_time,
        duration_minutes=duration_minutes,
        hospital_lat=hospital_lat,
        hospital_lng=hospital_lng,
        talking_points=talking_points,
        doctor_feedback=doctor_feedback,
        materials_distributed=materials_distributed,
        material_type=material_type,
    )


# ── Full compliance (all rules pass) ─────────────────────────────────────────

class TestCompliantCase:
    def test_result_is_compliant(self):
        r = make_result()
        assert r["result"] == "COMPLIANT"

    def test_score_is_100(self):
        r = make_result()
        assert r["score"] == 100

    def test_no_violations(self):
        r = make_result()
        assert r["violations"] == []

    def test_all_rules_pass(self):
        r = make_result()
        assert all(rule["passed"] for rule in r["rule_details"])

    def test_with_valid_material(self):
        r = make_result(materials_distributed=True, material_type=VALID_MATERIAL)
        assert r["result"] == "COMPLIANT"
        assert r["score"] == 100


# ── R001: Duration ────────────────────────────────────────────────────────────

class TestR001Duration:
    def test_too_short_is_minor(self):
        r = make_result(duration_minutes=3)
        viol = next((v for v in r["violations"] if v["rule_id"] == "R001"), None)
        assert viol is not None
        assert viol["severity"] == "MINOR"

    def test_too_short_deducts_12_5_points(self):
        r = make_result(duration_minutes=3)
        assert r["score"] == pytest.approx(87, abs=1)  # 100 - 25*0.5 = 87.5 → 88

    def test_too_long_is_major(self):
        r = make_result(duration_minutes=150)
        viol = next((v for v in r["violations"] if v["rule_id"] == "R001"), None)
        assert viol is not None
        assert viol["severity"] == "MAJOR"

    def test_too_long_deducts_25_points(self):
        r = make_result(duration_minutes=150)
        assert r["score"] == pytest.approx(75, abs=1)  # 100 - 25*1.0 = 75

    def test_too_long_is_minor_violation_result(self):
        r = make_result(duration_minutes=150)
        assert r["result"] == "MINOR_VIOLATION"

    def test_exactly_min_is_compliant(self):
        r = make_result(duration_minutes=5)
        viol = next((v for v in r["violations"] if v["rule_id"] == "R001"), None)
        assert viol is None

    def test_exactly_max_is_compliant(self):
        r = make_result(duration_minutes=120)
        viol = next((v for v in r["violations"] if v["rule_id"] == "R001"), None)
        assert viol is None


# ── R002: GPS Proximity ───────────────────────────────────────────────────────

class TestR002GPS:
    def test_far_gps_is_major_violation(self):
        r = make_result(checkin_lat=FAR_LAT, checkin_lng=FAR_LNG)
        viol = next((v for v in r["violations"] if v["rule_id"] == "R002"), None)
        assert viol is not None
        assert viol["severity"] == "MAJOR"

    def test_far_gps_deducts_30_points(self):
        r = make_result(checkin_lat=FAR_LAT, checkin_lng=FAR_LNG)
        assert r["score"] == pytest.approx(70, abs=1)  # 100 - 30 = 70

    def test_far_gps_result_is_minor_violation(self):
        r = make_result(checkin_lat=FAR_LAT, checkin_lng=FAR_LNG)
        assert r["result"] == "MINOR_VIOLATION"

    def test_near_gps_no_violation(self):
        r = make_result()
        viol = next((v for v in r["violations"] if v["rule_id"] == "R002"), None)
        assert viol is None

    def test_gps_violation_plus_duration_can_be_major_result(self):
        # Far GPS (-30) + too short (-12.5) = 57.5 → MAJOR_VIOLATION
        r = make_result(
            checkin_lat=FAR_LAT, checkin_lng=FAR_LNG,
            duration_minutes=3
        )
        assert r["result"] == "MAJOR_VIOLATION"
        assert r["score"] < 60


# ── R003: Working Hours ───────────────────────────────────────────────────────

class TestR003WorkingHours:
    def test_weekend_is_minor_violation(self):
        # 2026-06-14 is Sunday
        sunday = datetime(2026, 6, 14, 10, 0, 0, tzinfo=timezone.utc)
        r = make_result(checkin_time=sunday)
        viol = next((v for v in r["violations"] if v["rule_id"] == "R003"), None)
        assert viol is not None
        assert viol["severity"] == "MINOR"

    def test_before_work_hours_is_minor_violation(self):
        early = datetime(2026, 6, 16, 6, 0, 0, tzinfo=timezone.utc)  # 06:00 Monday
        r = make_result(checkin_time=early)
        viol = next((v for v in r["violations"] if v["rule_id"] == "R003"), None)
        assert viol is not None

    def test_weekday_business_hours_passes(self):
        r = make_result()  # Monday 09:00
        viol = next((v for v in r["violations"] if v["rule_id"] == "R003"), None)
        assert viol is None

    def test_working_hour_violation_deducts_7_5_points(self):
        sunday = datetime(2026, 6, 14, 10, 0, 0, tzinfo=timezone.utc)
        r = make_result(checkin_time=sunday)
        # score = 100 - 15*0.5 = 92.5 → 93 (only R003 fires)
        assert r["score"] == pytest.approx(93, abs=1)


# ── R004: Feedback Completeness ───────────────────────────────────────────────

class TestR004Feedback:
    def test_empty_talking_points_is_minor(self):
        r = make_result(talking_points="")
        viol = next((v for v in r["violations"] if v["rule_id"] == "R004"), None)
        assert viol is not None
        assert viol["severity"] == "MINOR"

    def test_short_talking_points_is_minor(self):
        r = make_result(talking_points="短")  # 1 char < 10
        viol = next((v for v in r["violations"] if v["rule_id"] == "R004"), None)
        assert viol is not None

    def test_none_talking_points_is_minor(self):
        r = make_result(talking_points=None)
        viol = next((v for v in r["violations"] if v["rule_id"] == "R004"), None)
        assert viol is not None

    def test_empty_feedback_is_minor(self):
        r = make_result(doctor_feedback="")
        viol = next((v for v in r["violations"] if v["rule_id"] == "R004"), None)
        assert viol is not None

    def test_both_ok_no_violation(self):
        r = make_result()
        viol = next((v for v in r["violations"] if v["rule_id"] == "R004"), None)
        assert viol is None

    def test_feedback_violation_deducts_7_5_points(self):
        r = make_result(talking_points="短")
        # score = 100 - 15*0.5 = 92.5 → 93
        assert r["score"] == pytest.approx(93, abs=1)


# ── R005: Material Type Validity ──────────────────────────────────────────────

class TestR005Material:
    def test_valid_material_no_violation(self):
        for mat in ALLOWED_MATERIALS:
            r = make_result(materials_distributed=True, material_type=mat)
            viol = next((v for v in r["violations"] if v["rule_id"] == "R005"), None)
            assert viol is None, f"Unexpected violation for material: {mat}"

    def test_invalid_material_is_major(self):
        r = make_result(materials_distributed=True, material_type="违禁宣传册")
        viol = next((v for v in r["violations"] if v["rule_id"] == "R005"), None)
        assert viol is not None
        assert viol["severity"] == "MAJOR"

    def test_invalid_material_deducts_15_points(self):
        r = make_result(materials_distributed=True, material_type="违禁宣传册")
        assert r["score"] == pytest.approx(85, abs=1)  # 100 - 15 = 85

    def test_none_material_type_with_distributed_is_major(self):
        r = make_result(materials_distributed=True, material_type=None)
        viol = next((v for v in r["violations"] if v["rule_id"] == "R005"), None)
        assert viol is not None
        assert viol["severity"] == "MAJOR"

    def test_no_distribution_ignores_material_type(self):
        r = make_result(materials_distributed=False, material_type="违禁宣传册")
        viol = next((v for v in r["violations"] if v["rule_id"] == "R005"), None)
        assert viol is None


# ── Score threshold boundaries ────────────────────────────────────────────────

class TestScoreThresholds:
    def test_score_ge_80_is_compliant(self):
        r = make_result()
        assert r["score"] >= 80
        assert r["result"] == "COMPLIANT"

    def test_score_lt_60_is_major_violation(self):
        # GPS (-30) + duration too short (-12.5) + invalid material (-15) = 42.5 → MAJOR
        r = make_result(
            checkin_lat=FAR_LAT, checkin_lng=FAR_LNG,
            duration_minutes=2,
            materials_distributed=True,
            material_type="非法资料",
        )
        assert r["score"] < 60
        assert r["result"] == "MAJOR_VIOLATION"

    def test_score_never_negative(self):
        # Trigger all 5 violations at once
        r = make_result(
            checkin_lat=FAR_LAT, checkin_lng=FAR_LNG,
            duration_minutes=1,
            checkin_time=datetime(2026, 6, 14, 6, 0, tzinfo=timezone.utc),  # Sunday 6am
            talking_points="短",
            doctor_feedback=None,
            materials_distributed=True,
            material_type="违规",
        )
        assert r["score"] >= 0

    def test_result_field_is_one_of_three_values(self):
        for params in [
            {},
            {"checkin_lat": FAR_LAT, "checkin_lng": FAR_LNG},
            {"duration_minutes": 1, "checkin_lat": FAR_LAT, "checkin_lng": FAR_LNG,
             "talking_points": "短", "materials_distributed": True, "material_type": "坏"},
        ]:
            r = make_result(**params)
            assert r["result"] in {"COMPLIANT", "MINOR_VIOLATION", "MAJOR_VIOLATION"}

    def test_rule_details_has_five_entries(self):
        r = make_result()
        assert len(r["rule_details"]) == 5

    def test_rule_ids_are_correct(self):
        r = make_result()
        ids = {rule["rule_id"] for rule in r["rule_details"]}
        assert ids == {"R001", "R002", "R003", "R004", "R005"}
