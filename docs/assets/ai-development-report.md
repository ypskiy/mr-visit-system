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

在代码集成与联调阶段，我们本着“实事求是”的原则，通过自动化测试运行、Docker 容器日志监控以及人类工程师的实际 UI 体验，分别捕获并修复了以下三类 Bug：

### 🔍 案例一：SQLite 内存数据库异步测试中 `MissingGreenlet` 异常
* **发现与定位方式**：由**测试运行命令输出**捕获。在人类工程师允许运行 `pytest` 后，测试控制台抛出大量的 `sqlalchemy.exc.MissingGreenlet` 错误。
* **排查与修复**：AI 针对异步 SQLite 在 `session.commit()` 后的懒加载过期行为进行分析，通过在服务层方法中使用 `db.expunge(visit)` 将对象从 Session 剥离，并在查询中显式引入 `selectinload` 进行关联属性的预加载，彻底消除了异步懒加载报错，确保全部 89 个测试用例顺利通过。

### 🔍 案例二：Alembic 迁移在 PostgreSQL 下的 Enum 碰撞与 asyncpg 限制
* **发现与定位方式**：由 **Docker Compose 启动日志**捕获。AI 在启动容器后主动查阅后台日志，捕获到了 Alembic 迁移在 Postgres 中重复创建 ENUM 以及 `asyncpg` 不支持在单个 `execute` 中运行多条 SQL 分隔符的错误。
* **排查与修复**：AI 对迁移文件进行重构：将 ENUM 创建改为显式的独立 `op.execute`，并统一把模型字段类型设定为通用 `String` 以兼容 SQLite 测试。

### 🔍 案例三：拜访列表筛选“全部”选项时的 URL 拼接 Bug
* **发现与定位方式**：由**人类工程师通过 UI 操作直接发现**。工程师在体验拜访列表时，反馈了“拜访列表选择全部时候显示加载错误”的问题。
* **排查与修复**：AI 顺着工程师指出的现象查阅 `list.html`，发现前端拼接 URL 时，若 status 过滤条件为空，URL 会错误地拼接成 `/api/v1/visits&limit=50`（缺失前面的 `?` 分隔符）。AI 随后将逻辑调整为：
  ```javascript
  const qs = currentStatus ? `?status=${currentStatus}` : '';
  const url = `/api/v1/visits${qs}${qs ? '&' : '?'}limit=50`;
  ```
  修复后热重载生效，工程师刷新网页即可正常浏览。


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
