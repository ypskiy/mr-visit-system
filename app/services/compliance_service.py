"""
Compliance Checking Service

Evaluates a completed visit against 5 rules and returns a structured result.

Rules:
  R001 - Duration validity      (weight=25)
  R002 - GPS proximity          (weight=30)
  R003 - Working hours          (weight=15)
  R004 - Feedback completeness  (weight=15)
  R005 - Material type validity (weight=15)

Scoring:
  Each violated rule deducts: weight × 0.5 (MINOR) or weight × 1.0 (MAJOR)
  Final score ≥ 80 → COMPLIANT
  60 ≤ score < 80 → MINOR_VIOLATION
  score < 60 → MAJOR_VIOLATION
"""

from datetime import datetime, timezone
from typing import Optional

from app.services.gps_utils import haversine_distance

ALLOWED_MATERIALS = {"文献复印件", "产品说明书", "学术会议摘要"}
MIN_DURATION = 5       # minutes
MAX_DURATION = 120     # minutes
GPS_THRESHOLD = 500    # metres
WORK_HOUR_START = 8    # 08:00
WORK_HOUR_END = 18     # 18:00
MIN_TEXT_LEN = 10      # characters


def _make_rule(rule_id: str, rule_name: str, passed: bool,
               severity: str, message: str, **kwargs) -> dict:
    return {
        "rule_id": rule_id,
        "rule_name": rule_name,
        "passed": passed,
        "severity": severity if not passed else None,
        "message": message,
        **kwargs,
    }


def run_compliance_check(
    *,
    checkin_time: datetime,
    checkin_lat: float,
    checkin_lng: float,
    checkout_time: datetime,
    duration_minutes: int,
    hospital_lat: float,
    hospital_lng: float,
    talking_points: Optional[str],
    doctor_feedback: Optional[str],
    materials_distributed: bool,
    material_type: Optional[str],
) -> dict:
    """
    Execute all 5 compliance rules against visit data.
    Returns dict with: result, score, violations, rule_details.
    """
    score = 100
    violations = []
    rule_details = []

    # ── R001: Duration validity ───────────────────────────────────────────────
    if duration_minutes < MIN_DURATION:
        severity, deduction = "MINOR", 25 * 0.5
        msg = f"停留时长仅 {duration_minutes} 分钟，低于最低要求 {MIN_DURATION} 分钟"
        passed = False
    elif duration_minutes > MAX_DURATION:
        severity, deduction = "MAJOR", 25 * 1.0
        msg = f"停留时长 {duration_minutes} 分钟，超过最大允许值 {MAX_DURATION} 分钟"
        passed = False
    else:
        severity, deduction, msg, passed = None, 0, "停留时长在合理范围内", True

    rule_details.append(_make_rule("R001", "停留时长合理性", passed, severity, msg,
                                   actual_value=duration_minutes,
                                   expected_range=f"{MIN_DURATION}-{MAX_DURATION}"))
    if not passed:
        score -= deduction
        violations.append({
            "rule_id": "R001", "rule_name": "停留时长合理性",
            "severity": severity, "message": msg,
            "actual_value": duration_minutes,
            "expected_range": f"{MIN_DURATION}-{MAX_DURATION}",
        })

    # ── R002: GPS proximity ───────────────────────────────────────────────────
    distance = haversine_distance(
        float(checkin_lat), float(checkin_lng),
        float(hospital_lat), float(hospital_lng)
    )
    distance_m = round(distance)
    if distance_m > GPS_THRESHOLD:
        severity, deduction = "MAJOR", 30 * 1.0
        msg = f"签到位置距目标医院 {distance_m}m，超过允许范围 {GPS_THRESHOLD}m"
        passed = False
    else:
        severity, deduction, msg, passed = None, 0, f"签到位置距医院 {distance_m}m，在允许范围内", True

    rule_details.append(_make_rule("R002", "GPS位置偏差", passed, severity, msg,
                                   actual_value=distance_m, threshold=GPS_THRESHOLD))
    if not passed:
        score -= deduction
        violations.append({
            "rule_id": "R002", "rule_name": "GPS位置偏差",
            "severity": severity, "message": msg,
            "actual_value": distance_m, "threshold": GPS_THRESHOLD,
        })

    # ── R003: Working hours ───────────────────────────────────────────────────
    # Use checkin time, check if it's a weekday and within 08:00-18:00
    local_hour = checkin_time.hour  # UTC stored; for demo treat as local
    is_weekday = checkin_time.weekday() < 5  # 0=Mon, 4=Fri
    in_hours = WORK_HOUR_START <= local_hour < WORK_HOUR_END and is_weekday

    if not in_hours:
        day_label = "工作日" if not is_weekday else "工作时间"
        severity, deduction = "MINOR", 15 * 0.5
        msg = f"签到时间 {checkin_time.strftime('%H:%M')} 不在{day_label}（08:00-18:00，周一至周五）范围内"
        passed = False
    else:
        severity, deduction, msg, passed = None, 0, "签到时间在工作时间范围内", True

    rule_details.append(_make_rule("R003", "工作时间合规", passed, severity, msg,
                                   actual_value=checkin_time.strftime("%Y-%m-%d %H:%M")))
    if not passed:
        score -= deduction
        violations.append({
            "rule_id": "R003", "rule_name": "工作时间合规",
            "severity": severity, "message": msg,
        })

    # ── R004: Feedback completeness ───────────────────────────────────────────
    tp_ok = bool(talking_points and len(talking_points.strip()) >= MIN_TEXT_LEN)
    fb_ok = bool(doctor_feedback and len(doctor_feedback.strip()) >= MIN_TEXT_LEN)
    if not (tp_ok and fb_ok):
        severity, deduction = "MINOR", 15 * 0.5
        missing = []
        if not tp_ok:
            missing.append("谈话要点")
        if not fb_ok:
            missing.append("医生反馈")
        msg = f"以下反馈内容不完整或过短（少于{MIN_TEXT_LEN}字）：{'、'.join(missing)}"
        passed = False
    else:
        severity, deduction, msg, passed = None, 0, "反馈内容完整", True

    rule_details.append(_make_rule("R004", "反馈完整性", passed, severity, msg))
    if not passed:
        score -= deduction
        violations.append({
            "rule_id": "R004", "rule_name": "反馈完整性",
            "severity": severity, "message": msg,
        })

    # ── R005: Material type validity ──────────────────────────────────────────
    if materials_distributed:
        mat_ok = material_type and material_type in ALLOWED_MATERIALS
        if not mat_ok:
            severity, deduction = "MAJOR", 15 * 1.0
            msg = f"派发资料类型「{material_type}」不在合规白名单内（{', '.join(ALLOWED_MATERIALS)}）"
            passed = False
        else:
            severity, deduction, msg, passed = None, 0, f"资料类型「{material_type}」符合合规要求", True
    else:
        severity, deduction, msg, passed = None, 0, "本次拜访未派发资料", True

    rule_details.append(_make_rule("R005", "资料派发合规", passed, severity, msg,
                                   actual_value=material_type))
    if not passed:
        score -= deduction
        violations.append({
            "rule_id": "R005", "rule_name": "资料派发合规",
            "severity": severity, "message": msg,
            "actual_value": material_type,
        })

    # ── Final scoring ─────────────────────────────────────────────────────────
    score = max(0, round(score))
    if score >= 80:
        result = "COMPLIANT"
    elif score >= 60:
        result = "MINOR_VIOLATION"
    else:
        result = "MAJOR_VIOLATION"

    return {
        "result": result,
        "score": score,
        "violations": violations,
        "rule_details": rule_details,
    }
