"""
Integration tests for reference data endpoints:
  GET /api/v1/departments
  GET /api/v1/doctors
  GET /api/v1/products
"""
import pytest


class TestDepartmentsAPI:
    async def test_list_departments_returns_200(self, client, mr, department):
        resp = await client.get("/api/v1/departments")
        assert resp.status_code == 200

    async def test_list_departments_returns_list(self, client, mr, department):
        resp = await client.get("/api/v1/departments")
        data = resp.json()
        assert isinstance(data, list)

    async def test_list_departments_includes_seeded_dept(self, client, mr, department):
        resp = await client.get("/api/v1/departments")
        names = [d["name"] for d in resp.json()]
        assert "心内科" in names

    async def test_department_has_hospital_coords(self, client, mr, department):
        resp = await client.get("/api/v1/departments")
        dept = next(d for d in resp.json() if d["name"] == "心内科")
        assert dept["hospital_lat"] is not None
        assert dept["hospital_lng"] is not None

    async def test_department_has_hospital_name(self, client, mr, department):
        resp = await client.get("/api/v1/departments")
        dept = next(d for d in resp.json() if d["name"] == "心内科")
        assert dept["hospital_name"] == "测试医院"


class TestDoctorsAPI:
    async def test_list_doctors_returns_200(self, client, mr, doctor):
        resp = await client.get("/api/v1/doctors")
        assert resp.status_code == 200

    async def test_list_doctors_returns_list(self, client, mr, doctor):
        resp = await client.get("/api/v1/doctors")
        assert isinstance(resp.json(), list)

    async def test_list_doctors_includes_seeded_doctor(self, client, mr, doctor):
        resp = await client.get("/api/v1/doctors")
        names = [d["name"] for d in resp.json()]
        assert "张医生" in names

    async def test_filter_by_department(self, client, mr, department, doctor):
        resp = await client.get(f"/api/v1/doctors?department_id={department.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert any(d["name"] == "张医生" for d in data)

    async def test_filter_by_nonexistent_dept_returns_empty(self, client, mr):
        resp = await client.get(
            "/api/v1/doctors?department_id=00000000-0000-0000-0000-000000000999"
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_doctor_has_title_field(self, client, mr, doctor):
        resp = await client.get("/api/v1/doctors")
        doc = next(d for d in resp.json() if d["name"] == "张医生")
        assert doc["title"] == "主任医师"


class TestProductsAPI:
    async def test_list_products_returns_200(self, client, mr, product):
        resp = await client.get("/api/v1/products")
        assert resp.status_code == 200

    async def test_list_products_returns_list(self, client, mr, product):
        resp = await client.get("/api/v1/products")
        assert isinstance(resp.json(), list)

    async def test_list_products_includes_seeded_product(self, client, mr, product):
        resp = await client.get("/api/v1/products")
        names = [p["name"] for p in resp.json()]
        assert "立普妥" in names

    async def test_product_has_generic_name(self, client, mr, product):
        resp = await client.get("/api/v1/products")
        prod = next(p for p in resp.json() if p["name"] == "立普妥")
        assert prod["generic_name"] == "阿托伐他汀钙片"

    async def test_product_has_therapeutic_area(self, client, mr, product):
        resp = await client.get("/api/v1/products")
        prod = next(p for p in resp.json() if p["name"] == "立普妥")
        assert prod["therapeutic_area"] == "心血管"
