# MR 学术拜访管理系统

> 医药代表（MR）学术拜访全生命周期管理平台

## 项目资源

- [🎥 点击查看系统演示视频](docs/assets/demo.mov)
- [📝 查看开发过程 Prompt 历史记录](docs/assets/prompt-history.md)


## 功能概览

| 功能 | 描述 |
|------|------|
| 📅 拜访预约 | 在下一自然周范围内预约医生、科室和讨论产品 |
| 📍 GPS签到 | 点击签到记录当前坐标（模拟60/30/10%概率分布） |
| ⏱ 签退计时 | 签退时自动计算停留时长，实时计时器展示 |
| 📝 拜访报告 | 提交谈话要点、医生反馈和资料派发情况 |
| 🛡️ 合规校验 | 5维度算法自动评定：合规/轻微违规/严重违规 |
| 📦 产品看板 | 月度拜访次数按产品维度可视化 |

## 快速启动（Docker）

```bash
git clone https://github.com/ypskiy/mr-visit-system.git
cd mr-visit-system
docker-compose up --build
```

访问 http://localhost:8000


## 技术栈

- **后端**：Python 3.11 + FastAPI + SQLAlchemy 2.0 (async)
- **数据库**：PostgreSQL 15
- **ORM/迁移**：SQLAlchemy + Alembic
- **前端**：Jinja2 模板 + Vanilla CSS + Vanilla JS
- **图表**：Chart.js 4
- **部署**：Docker + docker-compose

## 项目结构

```
mr-visit-system/
├── docker-compose.yaml      # 一键部署
├── Dockerfile
├── requirements.txt
├── alembic/                 # 数据库迁移
├── scripts/seed.py          # 种子数据
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── models/              # SQLAlchemy 模型
│   ├── schemas/             # Pydantic 模型
│   ├── routers/             # API 路由
│   ├── services/            # 业务逻辑
│   ├── templates/           # Jinja2 模板
│   └── static/              # CSS / JS
└── docs/                    # 文档
```

## API 文档

启动后访问：http://localhost:8000/docs（Swagger UI）
