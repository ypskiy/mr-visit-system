# 部署指南

## 方式一：Docker 一键部署（推荐）

### 前提条件
- Docker Desktop（已安装并运行）
- 端口 8000 和 5432 未被占用

### 步骤

```bash
# 1. 进入项目目录
cd mr-visit-system

# 2. 构建并启动（首次约 2-3 分钟）
docker-compose up --build

# 3. 等待看到以下输出后即可访问：
#    ✅ 种子数据写入完成！
#    INFO:     Application startup complete.

# 访问地址
# 前端：http://localhost:8000
# API文档：http://localhost:8000/docs
```

### 常用命令

```bash
# 后台运行
docker-compose up --build -d

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down

# 清除数据重置（清空数据库）
docker-compose down -v
docker-compose up --build
```

---

## 方式二：本地开发环境

### 前提条件
- Python 3.11+
- PostgreSQL 15（本地或 Docker）

### 步骤

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动数据库（如果本地没有 PostgreSQL，用 Docker）
docker run -d --name mr-pg \
  -e POSTGRES_DB=mr_visit \
  -e POSTGRES_USER=mr_admin \
  -e POSTGRES_PASSWORD=mr_secret \
  -p 5432:5432 postgres:15-alpine

# 4. 设置环境变量
export DATABASE_URL="postgresql+asyncpg://mr_admin:mr_secret@localhost:5432/mr_visit"

# 5. 执行数据库迁移
alembic upgrade head

# 6. 写入种子数据
python scripts/seed.py

# 7. 启动开发服务器（热重载）
uvicorn app.main:app --reload --port 8000

# 访问：http://localhost:8000
```

---

## 环境变量说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://mr_admin:mr_secret@localhost:5432/mr_visit` | 数据库连接串 |
| `APP_ENV` | `development` | 运行环境 |
| `DEFAULT_MR_ID` | `00000000-0000-0000-0000-000000000001` | 演示用 MR 默认 ID |

---

## 数据库迁移管理

```bash
# 查看迁移历史
alembic history

# 应用最新迁移
alembic upgrade head

# 回滚一步
alembic downgrade -1

# 创建新迁移（修改模型后）
alembic revision --autogenerate -m "add new field"
```
