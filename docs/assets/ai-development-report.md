# AI 协同开发报告 (AI Collaborative Development Report)

本项目 “医药代表（MR）学术拜访管理系统” 采用 **AI 与人类工程师双人配对编程 (Pair Programming)** 的模式进行全栈开发。以下是本次协同开发的关键记录与技术总结。

---

## 1. 关键 Prompt 记录

在系统设计之初，人类工程师与 AI 进行了深度对话，确立了系统的业务模型与架构设计。以下是引导 AI 进行数据库 Schema 设计与复杂合规校验算法的核心提示词：

### 💬 核心提示词 1：拜访生命周期与数据库 Schema 设计
> **工程师 Prompt:**
> "搭建一个医药代表学术拜访管理子系统。
> 一次拜访定义为药企医药代表（MR）在特定时间访问特定医生（HCP）传递关于某个具体产品的学术信息的沟通。通常系统应满足如下功能：
> 1. 拜访计划 (Plan)
> 2. 现场签到 (Check-in)
> 3. 拜访签退 (Check-out)
> 4. 反馈拜访记录 (Call Report)
> 
> User Journey 如下：
> MR 可以在当前日期所在星期的之后一周范围内选择预约时间，选择待访问科室、医生及计划讨论的具体产品，从而新建一个预约。
> 对已存在预约的拜访进行签到（记录时间、GPS）。
> 对已签到拜访进行签退（记录时间、计算停留时长）。
> 对已签退拜访补充谈话要点、反馈、派发资料，并标志拜访完成。
> 对已完成拜访，系统运行严肃专业的合规性校验算法，判断其是否为合规/轻微违规/严重违规并存储备查。
> 
> 系统应包括前端 + API + 后端 + 数据库。从前端界面、API设计和数据库 schema 入手做高层次设计。在我要求之前不准写 code。"

* **AI 响应亮点**：基于该 Prompt，设计了严格的 `PLANNED -> CHECKED_IN -> CHECKED_OUT -> COMPLETED` 状态机，并规划了以 `visits` 表为核心，一对一关联 `visit_reports` 和 `compliance_checks` 表的紧凑 Schema 结构，为系统打下了高内聚的数据基础。

### 💬 核心提示词 2：GPS 仿真分布与看板统计
> **工程师 Prompt:**
> "添加一个页面：一个按“产品”维度统计月度拜访次数的看板。
> 这里我们生成随机数模拟移动端采集 GPS 坐标：60% 可能是医院坐标（误差 100 米以内），30% 可能是医院周边坐标（误差 500 米以内），10% 可能是其他坐标（误差 500 米以上）。"

* **AI 响应亮点**：在 `app/static/js/gps-simulator.js` 中编写了概率控制算法，通过三段随机距离偏置，精准模拟出 `60/30/10%` 的统计学分布，用于前台一键模拟签到位置。

---

## 2. AI 纠偏亮点案例

在代码生成与集成阶段，通过自动化测试与容器化验证，人类工程师发现了 AI 生成的若干隐藏 Bug，并成功进行了引导和修复。

### 🔍 案例一：SQLite 内存数据库异步测试中 `MissingGreenlet` 异常
* **发现问题**：在执行 `pytest` 自动化测试时，由于测试环境使用的是 SQLite 内存库（通过 `aiosqlite`），而 FastAPI 应用层在提交拜访签退/报告后会调用 `session.commit()`，导致 SQLAlchemy 中的对象缓存过期。在 Pydantic 将 `Visit` 序列化为响应时，尝试懒加载关联的 `mr`、`doctor` 等关系属性，抛出了 `sqlalchemy.exc.MissingGreenlet: parent instance is not bound to a Session; lazy load operation cannot proceed` 异常。
* **排查与修复**：工程师引导 AI 仔细分析 SQLAlchemy 在异步上下文下的关系加载机制。最终通过在服务层方法中对已提交的对象显式使用 `db.expunge(visit)`（将对象从 Session 剥离，保留已被加载的属性），或在 SQLAlchemy 查询中统一采用 `selectinload` 进行预加载（Eager Loading），彻底消除了异步懒加载报错，确保测试用例绿灯通过。

### 🔍 案例二：Alembic 迁移在 PostgreSQL 下的 Enum 碰撞与 asyncpg 局限
* **发现问题**：在 Docker Compose 启动 Postgres 并执行 Alembic 自动迁移时，由于 SQLAlchemy `Enum` 类型在 `create_table` 阶段会被隐式触发二次创建，导致抛出 `DuplicateObject` 异常；此外，`asyncpg` 驱动程序不支持在单个 `op.execute()` 块中执行以分号分隔的多条 SQL 语句，导致迁移中断。
* **排查与修复**：工程师发现该问题后，对迁移逻辑进行了微调：
  1. 将建表中的 `sa.Enum` 定义解耦，将 `visitstatus` 和 `complianceresult` 的生成拆分为独立的 `op.execute("CREATE TYPE ...")` 语句；
  2. 为了兼顾 SQLite（不支持原生 Postgres ENUM）和 PostgreSQL，将底层的模型字段类型声明调整为通用的 `String` 并搭配 Check 约束，同时将多条 SQL 拆分至不同的 `op.execute` 块中执行，完美解决了一键部署的迁移死锁问题。

### 🔍 案例三：拜访列表筛选“全部”选项时的 URL 拼接 Bug
* **发现问题**：在前端点击“全部”状态标签筛选拜访列表时，页面上提示“加载错误”。
* **排查与修复**：打开浏览器开发者工具，发现请求的 URL 变为了 `/api/v1/visits&limit=50`（因为 `currentStatus` 为空时，JavaScript 代码中粗暴地拼接了 `&limit=50`，导致缺少前面的问号 `?` 从而被 FastAPI 拦截抛出 422 校验错误）。工程师指出拼接逻辑缺陷后，将拼接逻辑重构为：
  ```javascript
  const qs = currentStatus ? `?status=${currentStatus}` : '';
  const url = `/api/v1/visits${qs}${qs ? '&' : '?'}limit=50`;
  ```
  修复后，过滤“全部”及各个具体状态时均可秒级响应。

---

## 3. 全程 AI 会话导出与 Git 历史

* **全程会话导出（Prompt History）**：
  详细记录了从零到完工的所有对话、中间排错日志和代码修补记录。可在项目内直接访问：
  👉 [Prompt 历史记录 (prompt-history.md)](./prompt-history.md)

* **Git Commit 历史 (Git History)**：
  ```bash
  c193e26 docs: add prompt history asset and update README references
  3e211ee docs: add system demo video and update README clone URL
  b53e996 Initial commit: MR Academic Visit Management System
  ```

---

## 4. 应用 Demo 录屏

录制了该系统的完整使用流程（包含拜访预约、签到 GPS 模拟与实时计时、签退与报告提交、自动合规算法评级、以及按产品维度统计的月度看板）。
* **视频资源**：
  👉 [🎥 查看系统演示视频 (demo.mov)](./demo.mov)
