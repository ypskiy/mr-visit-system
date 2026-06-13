import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any

from pydantic import BaseModel, field_validator, model_validator, Field


# ── Shared ────────────────────────────────────────────────────────────────────

class DoctorBrief(BaseModel):
    id: uuid.UUID
    name: str
    title: Optional[str] = None
    department_name: str
    hospital_name: str

    model_config = {"from_attributes": True}


class ProductBrief(BaseModel):
    id: uuid.UUID
    name: str
    generic_name: Optional[str] = None
    therapeutic_area: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Visit ─────────────────────────────────────────────────────────────────────

class VisitCreate(BaseModel):
    doctor_id: uuid.UUID
    product_id: uuid.UUID
    planned_date: datetime


class VisitUpdate(BaseModel):
    doctor_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None
    planned_date: Optional[datetime] = None


class CheckinRequest(BaseModel):
    latitude: float
    longitude: float


class ReportRequest(BaseModel):
    talking_points: str = Field(..., min_length=10)
    doctor_feedback: str = Field(..., min_length=10)
    materials_distributed: bool
    material_type: Optional[str] = None

    @model_validator(mode="after")
    def validate_material_type(self):
        allowed = {"文献复印件", "产品说明书", "学术会议摘要"}
        if self.materials_distributed:
            if not self.material_type or self.material_type not in allowed:
                raise ValueError(f"材料类型须为以下之一：{', '.join(allowed)}")
        return self


class ComplianceViolation(BaseModel):
    rule_id: str
    rule_name: str
    severity: str
    message: str
    actual_value: Any = None
    expected_range: Optional[str] = None
    threshold: Optional[float] = None


class ComplianceOut(BaseModel):
    result: str
    score: int
    violations: List[ComplianceViolation] = []


class ReportOut(BaseModel):
    talking_points: Optional[str]
    doctor_feedback: Optional[str]
    materials_distributed: bool
    material_type: Optional[str]
    submitted_at: datetime

    model_config = {"from_attributes": True}


class VisitOut(BaseModel):
    id: uuid.UUID
    status: str
    planned_date: datetime
    checkin_time: Optional[datetime] = None
    checkin_lat: Optional[Decimal] = None
    checkin_lng: Optional[Decimal] = None
    checkout_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    doctor: Optional[DoctorBrief] = None
    product: Optional[ProductBrief] = None
    report: Optional[ReportOut] = None
    compliance: Optional[ComplianceOut] = None

    model_config = {"from_attributes": True}


class PaginatedVisits(BaseModel):
    total: int
    page: int
    limit: int
    items: List[VisitOut]


# ── Stats ─────────────────────────────────────────────────────────────────────

class MonthlyCount(BaseModel):
    month: int
    visit_count: int
    completed_count: int
    compliant_count: int


class ProductVisitStat(BaseModel):
    product_id: uuid.UUID
    product_name: str
    therapeutic_area: Optional[str]
    monthly_counts: List[MonthlyCount]
    total_visits: int
    total_completed: int
    compliance_rate: float


class ProductVisitStats(BaseModel):
    year: int
    data: List[ProductVisitStat]


class WeeklyCompliance(BaseModel):
    week_label: str
    total: int
    compliant: int
    minor: int
    major: int
    compliance_rate: float


class ComplianceStats(BaseModel):
    recent_weeks: List[WeeklyCompliance]
    rule_violation_counts: dict
    violations_list: List[VisitOut]
