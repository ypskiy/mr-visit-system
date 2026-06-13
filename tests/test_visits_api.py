"""
Integration tests for the Visit API endpoints.
Uses in-memory SQLite + ASGI test client (no real network or PostgreSQL required).

Covers the full lifecycle: create → checkin → checkout → report → compliance
"""
import pytest
from datetime import datetime, timezone, timedelta

from tests.conftest import next_monday_noon


# ── Helper ────────────────────────────────────────────────────────────────────

def next_week_iso():
    """ISO datetime string for next Monday noon — satisfies the 'next week' constraint."""
    return next_monday_noon().isoformat()


# ── POST /api/v1/visits ───────────────────────────────────────────────────────

class TestCreateVisit:
    async def test_create_returns_201(self, client, mr, doctor, product):
        resp = await client.post("/api/v1/visits", json={
            "doctor_id": str(doctor.id),
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        assert resp.status_code == 201

    async def test_create_returns_planned_status(self, client, mr, doctor, product):
        resp = await client.post("/api/v1/visits", json={
            "doctor_id": str(doctor.id),
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        data = resp.json()
        assert data["status"] == "PLANNED"

    async def test_create_returns_doctor_info(self, client, mr, doctor, product):
        resp = await client.post("/api/v1/visits", json={
            "doctor_id": str(doctor.id),
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        data = resp.json()
        assert data["doctor"]["name"] == "张医生"

    async def test_create_returns_product_info(self, client, mr, doctor, product):
        resp = await client.post("/api/v1/visits", json={
            "doctor_id": str(doctor.id),
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        data = resp.json()
        assert data["product"]["name"] == "立普妥"

    async def test_create_invalid_doctor_returns_400_or_422(self, client, mr, product):
        resp = await client.post("/api/v1/visits", json={
            "doctor_id": "00000000-0000-0000-0000-000000000999",
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        assert resp.status_code in (400, 422)

    async def test_create_missing_body_returns_422(self, client, mr):
        resp = await client.post("/api/v1/visits", json={})
        assert resp.status_code == 422


# ── GET /api/v1/visits ────────────────────────────────────────────────────────

class TestListVisits:
    async def _create(self, client, doctor, product):
        r = await client.post("/api/v1/visits", json={
            "doctor_id": str(doctor.id),
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        return r.json()

    async def test_list_returns_200(self, client, mr, doctor, product):
        resp = await client.get("/api/v1/visits?limit=50")
        assert resp.status_code == 200

    async def test_list_has_pagination_fields(self, client, mr, doctor, product):
        resp = await client.get("/api/v1/visits?limit=50")
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert "page" in data

    async def test_list_includes_created_visit(self, client, mr, doctor, product):
        created = await self._create(client, doctor, product)
        resp = await client.get("/api/v1/visits?limit=50")
        ids = [v["id"] for v in resp.json()["items"]]
        assert created["id"] in ids

    async def test_list_filter_by_status_planned(self, client, mr, doctor, product):
        await self._create(client, doctor, product)
        resp = await client.get("/api/v1/visits?status=PLANNED&limit=50")
        data = resp.json()
        assert all(v["status"] == "PLANNED" for v in data["items"])

    async def test_list_filter_by_invalid_status_returns_items_or_empty(self, client, mr):
        resp = await client.get("/api/v1/visits?status=INVALID&limit=50")
        # Should return 200 with empty list or 422 — not 500
        assert resp.status_code in (200, 422)


# ── GET /api/v1/visits/{id} ───────────────────────────────────────────────────

class TestGetVisit:
    async def _create(self, client, doctor, product) -> dict:
        r = await client.post("/api/v1/visits", json={
            "doctor_id": str(doctor.id),
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        return r.json()

    async def test_get_existing_returns_200(self, client, mr, doctor, product):
        v = await self._create(client, doctor, product)
        resp = await client.get(f"/api/v1/visits/{v['id']}")
        assert resp.status_code == 200

    async def test_get_non_existing_returns_404(self, client, mr):
        resp = await client.get("/api/v1/visits/00000000-0000-0000-0000-000000000999")
        assert resp.status_code == 404

    async def test_get_returns_correct_id(self, client, mr, doctor, product):
        v = await self._create(client, doctor, product)
        resp = await client.get(f"/api/v1/visits/{v['id']}")
        assert resp.json()["id"] == v["id"]


# ── Full lifecycle: PLANNED → CHECKED_IN → CHECKED_OUT → COMPLETED ────────────

class TestVisitLifecycle:
    """
    End-to-end state machine test:
    create → checkin → checkout → submit_report → compliance attached
    """

    @pytest.fixture
    async def visit(self, client, mr, doctor, product) -> dict:
        r = await client.post("/api/v1/visits", json={
            "doctor_id": str(doctor.id),
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        assert r.status_code == 201
        return r.json()

    async def test_initial_status_is_planned(self, visit):
        assert visit["status"] == "PLANNED"

    async def test_checkin_transitions_to_checked_in(self, client, visit):
        resp = await client.post(f"/api/v1/visits/{visit['id']}/checkin", json={
            "latitude": 31.2158,
            "longitude": 121.4623,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "CHECKED_IN"

    async def test_checkin_records_gps(self, client, visit):
        resp = await client.post(f"/api/v1/visits/{visit['id']}/checkin", json={
            "latitude": 31.2158,
            "longitude": 121.4623,
        })
        data = resp.json()
        assert data["checkin_lat"] is not None
        assert data["checkin_lng"] is not None

    async def test_double_checkin_returns_409(self, client, visit):
        await client.post(f"/api/v1/visits/{visit['id']}/checkin", json={
            "latitude": 31.2158, "longitude": 121.4623,
        })
        resp2 = await client.post(f"/api/v1/visits/{visit['id']}/checkin", json={
            "latitude": 31.2158, "longitude": 121.4623,
        })
        assert resp2.status_code == 409

    async def test_checkout_before_checkin_returns_409(self, client, visit):
        resp = await client.post(f"/api/v1/visits/{visit['id']}/checkout")
        assert resp.status_code == 409

    async def test_full_lifecycle(self, client, visit):
        vid = visit["id"]

        # 1. Checkin
        r = await client.post(f"/api/v1/visits/{vid}/checkin", json={
            "latitude": 31.2158, "longitude": 121.4623,
        })
        assert r.json()["status"] == "CHECKED_IN"

        # 2. Checkout
        r = await client.post(f"/api/v1/visits/{vid}/checkout")
        assert r.json()["status"] == "CHECKED_OUT"
        assert r.json()["duration_minutes"] is not None

        # 3. Submit report
        r = await client.post(f"/api/v1/visits/{vid}/report", json={
            "talking_points": "详细讨论了产品在心血管疾病中的临床应用循证证据",
            "doctor_feedback": "医生对药品安全性满意，考虑在下次门诊中优先推荐给患者",
            "materials_distributed": True,
            "material_type": "文献复印件",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "COMPLETED"
        assert data["report"] is not None
        assert data["compliance"] is not None
        assert data["compliance"]["result"] in {"COMPLIANT", "MINOR_VIOLATION", "MAJOR_VIOLATION"}

    async def test_report_without_checkout_returns_409(self, client, visit):
        vid = visit["id"]
        # Only checkin, no checkout
        await client.post(f"/api/v1/visits/{vid}/checkin", json={
            "latitude": 31.2158, "longitude": 121.4623,
        })
        r = await client.post(f"/api/v1/visits/{vid}/report", json={
            "talking_points": "详细讨论了产品在心血管疾病中的临床应用循证证据",
            "doctor_feedback": "医生对药品安全性满意，考虑在下次门诊中优先推荐给患者",
            "materials_distributed": False,
        })
        assert r.status_code in (400, 409)

    async def test_report_too_short_returns_400(self, client, visit):
        vid = visit["id"]
        await client.post(f"/api/v1/visits/{vid}/checkin", json={
            "latitude": 31.2158, "longitude": 121.4623,
        })
        await client.post(f"/api/v1/visits/{vid}/checkout")
        r = await client.post(f"/api/v1/visits/{vid}/report", json={
            "talking_points": "短",
            "doctor_feedback": "短",
            "materials_distributed": False,
        })
        assert r.status_code == 422


# ── DELETE /api/v1/visits/{id} ────────────────────────────────────────────────

class TestDeleteVisit:
    async def test_delete_planned_returns_204(self, client, mr, doctor, product):
        r = await client.post("/api/v1/visits", json={
            "doctor_id": str(doctor.id),
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        vid = r.json()["id"]
        resp = await client.delete(f"/api/v1/visits/{vid}")
        assert resp.status_code == 204

    async def test_delete_removes_visit(self, client, mr, doctor, product):
        r = await client.post("/api/v1/visits", json={
            "doctor_id": str(doctor.id),
            "product_id": str(product.id),
            "planned_date": next_week_iso(),
        })
        vid = r.json()["id"]
        await client.delete(f"/api/v1/visits/{vid}")
        resp = await client.get(f"/api/v1/visits/{vid}")
        assert resp.status_code == 404

    async def test_delete_nonexistent_returns_404(self, client, mr):
        resp = await client.delete("/api/v1/visits/00000000-0000-0000-0000-000000000999")
        assert resp.status_code == 404
