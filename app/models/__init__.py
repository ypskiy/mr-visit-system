import uuid
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String, Boolean, Integer, Text, Numeric, ForeignKey,
    TIMESTAMP, Enum as SAEnum, UniqueConstraint, JSON, Uuid
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


# ── Enums ────────────────────────────────────────────────────────────────────

class VisitStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    COMPLETED = "COMPLETED"


class ComplianceResult(str, enum.Enum):
    COMPLIANT = "COMPLIANT"
    MINOR_VIOLATION = "MINOR_VIOLATION"
    MAJOR_VIOLATION = "MAJOR_VIOLATION"


# ── Models ───────────────────────────────────────────────────────────────────

class MR(Base):
    __tablename__ = "mrs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="mr")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    hospital_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hospital_lat: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    hospital_lng: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    doctors: Mapped[List["Doctor"]] = relationship("Doctor", back_populates="department")


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(50))
    specialty: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    department: Mapped["Department"] = relationship("Department", back_populates="doctors")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="doctor")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    generic_name: Mapped[Optional[str]] = mapped_column(String(200))
    therapeutic_area: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="product")


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mr_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("mrs.id", ondelete="CASCADE"), nullable=False)
    doctor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[VisitStatus] = mapped_column(SAEnum(VisitStatus, name="visitstatus"), nullable=False, default=VisitStatus.PLANNED)
    planned_date: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    checkin_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    checkin_lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    checkin_lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    checkout_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    mr: Mapped["MR"] = relationship("MR", back_populates="visits")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="visits")
    product: Mapped["Product"] = relationship("Product", back_populates="visits")
    report: Mapped[Optional["VisitReport"]] = relationship("VisitReport", back_populates="visit", uselist=False)
    compliance: Mapped[Optional["ComplianceCheck"]] = relationship("ComplianceCheck", back_populates="visit", uselist=False)


class VisitReport(Base):
    __tablename__ = "visit_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, unique=True)
    talking_points: Mapped[Optional[str]] = mapped_column(Text)
    doctor_feedback: Mapped[Optional[str]] = mapped_column(Text)
    materials_distributed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    material_type: Mapped[Optional[str]] = mapped_column(String(100))
    submitted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    visit: Mapped["Visit"] = relationship("Visit", back_populates="report")


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, unique=True)
    result: Mapped[ComplianceResult] = mapped_column(SAEnum(ComplianceResult, name="complianceresult"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    violations: Mapped[Optional[dict]] = mapped_column(JSON)
    rule_details: Mapped[Optional[dict]] = mapped_column(JSON)
    checked_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    visit: Mapped["Visit"] = relationship("Visit", back_populates="compliance")
