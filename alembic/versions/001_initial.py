"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-06-12
"""
from alembic import op

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # asyncpg does not support multiple statements in a single execute() call.
    # Each statement must be issued separately.

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE visitstatus AS ENUM ('PLANNED', 'CHECKED_IN', 'CHECKED_OUT', 'COMPLETED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE complianceresult AS ENUM ('COMPLIANT', 'MINOR_VIOLATION', 'MAJOR_VIOLATION');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS mrs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            employee_id VARCHAR(50) NOT NULL UNIQUE,
            phone VARCHAR(20),
            region VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            hospital_name VARCHAR(200) NOT NULL,
            hospital_lat NUMERIC(10,7) NOT NULL,
            hospital_lng NUMERIC(10,7) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            title VARCHAR(50),
            specialty VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            generic_name VARCHAR(200),
            therapeutic_area VARCHAR(100),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            mr_id UUID NOT NULL REFERENCES mrs(id) ON DELETE CASCADE,
            doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            status visitstatus NOT NULL DEFAULT 'PLANNED',
            planned_date TIMESTAMPTZ NOT NULL,
            checkin_time TIMESTAMPTZ,
            checkin_lat NUMERIC(10,7),
            checkin_lng NUMERIC(10,7),
            checkout_time TIMESTAMPTZ,
            duration_minutes INTEGER,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS visit_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            visit_id UUID NOT NULL UNIQUE REFERENCES visits(id) ON DELETE CASCADE,
            talking_points TEXT,
            doctor_feedback TEXT,
            materials_distributed BOOLEAN NOT NULL DEFAULT false,
            material_type VARCHAR(100),
            submitted_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_checks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            visit_id UUID NOT NULL UNIQUE REFERENCES visits(id) ON DELETE CASCADE,
            result complianceresult NOT NULL,
            score INTEGER NOT NULL,
            violations JSONB,
            rule_details JSONB,
            checked_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_visits_mr_status ON visits(mr_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_visits_mr_planned ON visits(mr_id, planned_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_visits_status ON visits(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_visits_product_planned ON visits(product_id, planned_date)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS compliance_checks")
    op.execute("DROP TABLE IF EXISTS visit_reports")
    op.execute("DROP TABLE IF EXISTS visits")
    op.execute("DROP TABLE IF EXISTS products")
    op.execute("DROP TABLE IF EXISTS doctors")
    op.execute("DROP TABLE IF EXISTS departments")
    op.execute("DROP TABLE IF EXISTS mrs")
    op.execute("DROP TYPE IF EXISTS visitstatus")
    op.execute("DROP TYPE IF EXISTS complianceresult")
