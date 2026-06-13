"""
Seed script: pre-populates demo data for MR Visit Management System.
Run with: python scripts/seed.py
"""
import asyncio
import uuid
import os
import sys
from datetime import datetime, timezone, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text

from app.config import settings
from app.models import Base, MR, Department, Doctor, Product, Visit, VisitReport, ComplianceCheck, VisitStatus
from app.services.compliance_service import run_compliance_check
from app.services.gps_utils import simulate_gps

# ─────────────────────────────────────────────────────────────────────────────
# Seed data definitions
# ─────────────────────────────────────────────────────────────────────────────

FIXED_MR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

MR_DATA = {
    "id": FIXED_MR_ID,
    "name": "李明",
    "employee_id": "MR001",
    "phone": "13812345678",
    "region": "华东区",
}

DEPARTMENTS = [
    {"name": "心内科", "hospital_name": "上海瑞金医院", "hospital_lat": 31.2154, "hospital_lng": 121.4619},
    {"name": "神经内科", "hospital_name": "上海瑞金医院", "hospital_lat": 31.2154, "hospital_lng": 121.4619},
    {"name": "肿瘤科", "hospital_name": "上海中山医院", "hospital_lat": 31.1986, "hospital_lng": 121.4486},
    {"name": "内分泌科", "hospital_name": "上海中山医院", "hospital_lat": 31.1986, "hospital_lng": 121.4486},
    {"name": "呼吸内科", "hospital_name": "上海华山医院", "hospital_lat": 31.2206, "hospital_lng": 121.4489},
]

DOCTORS = [
    {"name": "张伟", "title": "主任医师", "specialty": "冠心病", "dept_idx": 0},
    {"name": "王芳", "title": "副主任医师", "specialty": "脑血管病", "dept_idx": 1},
    {"name": "陈建国", "title": "主任医师", "specialty": "肺癌", "dept_idx": 2},
    {"name": "刘洋", "title": "主治医师", "specialty": "糖尿病", "dept_idx": 3},
    {"name": "赵敏", "title": "副主任医师", "specialty": "哮喘", "dept_idx": 4},
]

PRODUCTS = [
    {"name": "立普妥", "generic_name": "阿托伐他汀钙片", "therapeutic_area": "心血管"},
    {"name": "泰嘉", "generic_name": "氯吡格雷片", "therapeutic_area": "心血管"},
    {"name": "特罗凯", "generic_name": "盐酸厄洛替尼片", "therapeutic_area": "肿瘤"},
    {"name": "诺和锐", "generic_name": "门冬胰岛素注射液", "therapeutic_area": "内分泌"},
    {"name": "信必可", "generic_name": "布地奈德福莫特罗", "therapeutic_area": "呼吸"},
]

# Historical visit scenarios for demo (covering past weeks for charts)
TALKING_POINTS_SAMPLES = [
    "讨论了阿托伐他汀在ACS二级预防中的最新循证医学证据，重点介绍JUPITER研究的新数据，说明高敏CRP作为治疗靶点的临床意义。",
    "介绍了产品最新的RCT研究数据，讨论了其在目标患者群体中的安全性和有效性，医生对药物的肝功能安全性数据表示关注。",
    "传递了最新版治疗指南推荐意见，讨论了产品在一线治疗中的地位，以及与竞品的头对头研究结论。",
    "系统介绍了产品的作用机制和临床优势，讨论了典型病例的用药方案，医生对剂量调整问题有详细询问。",
    "分享了近期学术会议的最新研究进展，讨论了产品在特殊人群（老年患者）中的用药安全性数据。",
]

FEEDBACK_SAMPLES = [
    "医生对产品的长期安全性数据表示认可，希望进一步了解药物相互作用方面的资料，计划在下次门诊中尝试使用。",
    "医生表达了对产品价格和医保覆盖情况的关切，认为若能纳入医保目录，使用意愿会显著提高。",
    "医生对产品在特定适应症中的疗效持积极态度，但对某些不良反应有所顾虑，需要更多真实世界证据。",
    "医生表示已有使用经验，整体满意度较高，希望了解是否有针对该科室的患者教育资料。",
    "医生对最新的循证证据表示认可，希望参加下次相关领域的学术研讨会，并请求提供文献复印件。",
]


async def seed(db: AsyncSession):
    # Check if already seeded
    result = await db.execute(select(MR).where(MR.id == FIXED_MR_ID))
    if result.scalar_one_or_none():
        print("✅ 数据库已有种子数据，跳过。")
        return

    print("🌱 开始写入种子数据...")

    # MR
    mr = MR(**MR_DATA)
    db.add(mr)
    await db.flush()
    print(f"  ✓ MR: {mr.name} ({mr.employee_id})")

    # Departments
    dept_objs = []
    for d in DEPARTMENTS:
        dept = Department(**d)
        db.add(dept)
        dept_objs.append(dept)
    await db.flush()
    print(f"  ✓ 科室: {len(dept_objs)} 个")

    # Doctors
    doctor_objs = []
    for d in DOCTORS:
        doc = Doctor(
            name=d["name"],
            title=d["title"],
            specialty=d["specialty"],
            department_id=dept_objs[d["dept_idx"]].id,
        )
        db.add(doc)
        doctor_objs.append(doc)
    await db.flush()
    print(f"  ✓ 医生: {len(doctor_objs)} 位")

    # Products
    product_objs = []
    for p in PRODUCTS:
        prod = Product(**p)
        db.add(prod)
        product_objs.append(prod)
    await db.flush()
    print(f"  ✓ 产品: {len(product_objs)} 个")

    # Historical visits (past 3 months, 2-4 per week for chart data)
    now = datetime.now(timezone.utc)
    visit_count = 0

    for weeks_ago in range(1, 13):  # 12 weeks back
        week_start = now - timedelta(weeks=weeks_ago)
        # 2-4 visits per week
        n_visits = random.randint(2, 4)
        for _ in range(n_visits):
            doc = random.choice(doctor_objs)
            prod = random.choice(product_objs)
            dept = dept_objs[DOCTORS[doctor_objs.index(doc)]["dept_idx"]]

            # Random day in that week (Mon-Fri)
            day_offset = random.randint(0, 4)
            hour = random.randint(8, 17)
            planned = week_start.replace(
                hour=hour, minute=random.randint(0, 59), second=0, microsecond=0
            ) + timedelta(days=day_offset)

            # Simulate GPS
            lat, lng = simulate_gps(float(dept.hospital_lat), float(dept.hospital_lng))
            checkin = planned + timedelta(minutes=random.randint(-10, 15))
            duration = random.randint(3, 90)
            checkout = checkin + timedelta(minutes=duration)

            talking = random.choice(TALKING_POINTS_SAMPLES)
            feedback = random.choice(FEEDBACK_SAMPLES)
            has_material = random.random() > 0.4
            material_type = random.choice(["文献复印件", "产品说明书", "学术会议摘要"]) if has_material else None

            visit = Visit(
                mr_id=mr.id,
                doctor_id=doc.id,
                product_id=prod.id,
                status=VisitStatus.COMPLETED,
                planned_date=planned,
                checkin_time=checkin,
                checkin_lat=lat,
                checkin_lng=lng,
                checkout_time=checkout,
                duration_minutes=duration,
            )
            db.add(visit)
            await db.flush()

            report = VisitReport(
                visit_id=visit.id,
                talking_points=talking,
                doctor_feedback=feedback,
                materials_distributed=has_material,
                material_type=material_type,
            )
            db.add(report)

            # Compliance check
            comp_data = run_compliance_check(
                checkin_time=checkin,
                checkin_lat=lat,
                checkin_lng=lng,
                checkout_time=checkout,
                duration_minutes=duration,
                hospital_lat=float(dept.hospital_lat),
                hospital_lng=float(dept.hospital_lng),
                talking_points=talking,
                doctor_feedback=feedback,
                materials_distributed=has_material,
                material_type=material_type,
            )
            comp = ComplianceCheck(
                visit_id=visit.id,
                result=comp_data["result"],
                score=comp_data["score"],
                violations=comp_data["violations"],
                rule_details=comp_data["rule_details"],
            )
            db.add(comp)
            visit_count += 1

    await db.commit()
    print(f"  ✓ 历史拜访记录: {visit_count} 条（含报告+合规校验）")
    print("✅ 种子数据写入完成！")
    print("\n📌 演示账号信息：")
    print(f"   MR ID: {FIXED_MR_ID}")
    print("   姓名: 李明 | 工号: MR001 | 华东区")
    print("\n🌐 访问地址: http://localhost:8000")


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
