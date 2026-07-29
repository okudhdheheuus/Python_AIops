# ITOps Agent Platform — 智能运维自动化平台

AI 驱动的 IT 运维自动化平台，集成多厂商 LLM、智能告警、自动修复和可视化工作流编排。

## 功能特性

- **服务器管理** — 基于 SSH 的服务器资产管理，支持密码/密钥认证和健康监控
- **AI Copilot 对话** — 多厂商 LLM 对话（DeepSeek / OpenAI 兼容），支持 RAG 知识库检索增强
- **可视化工作流编辑器** — 拖拽式节点编辑器，构建自动化运维工作流
- **工作流引擎** — 执行多步骤工作流，支持 SSH 节点、Agent 节点、条件分支
- **巡检与告警** — 定时服务器健康巡检，Prometheus 指标采集，告警规则与静默管理
- **自动修复** — AI 生成或固定命令的修复策略，支持人工审批流程
- **知识库 (RAG)** — 存储和检索运维手册，自动注入 AI 对话上下文
- **审计日志** — 全量操作审计追踪
- **通知渠道** — 钉钉/飞书 Webhook 告警通知
- **仪表盘** — 运维全局态势一览

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3, FastAPI, SQLAlchemy (async), Redis, APScheduler |
| 前端 | Next.js 16, React 19, Tailwind CSS 4, TypeScript |
| 工作流 UI | @xyflow/react (React Flow) |
| 数据库 | PostgreSQL 16 (生产) / SQLite (开发) |
| LLM | DeepSeek / OpenAI 兼容 (智谱 GLM) |
| 部署 | Docker Compose, Kubernetes, Helm |

## 快速开始

### 环境要求

- Docker & Docker Compose
- （可选）Python 3.11+ 和 Node.js 20+（本地开发）

### Docker Compose 部署

```bash
# 克隆仓库
git clone <repo-url> && cd python-itops-platform

# 设置 LLM API 密钥
export OPENAI_API_KEY=your-api-key

# 启动所有服务
docker-compose up -d
```

启动后访问：

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/docs |
| 指标接口 | http://localhost:8000/metrics |

### 本地开发

**后端：**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 编辑配置文件
uvicorn backend.main:app --reload --port 8000
```

**前端：**

```bash
cd frontend-next
npm install
npm run dev
```

## 配置说明

主要环境变量（通过 `.env` 或环境变量设置）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_PROVIDER` | LLM 提供商：`openai` 或 `deepseek` | `openai` |
| `OPENAI_API_KEY` | OpenAI 兼容 API 密钥 | — |
| `OPENAI_API_BASE` | API 地址 | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型名称 | `gpt-3.5-turbo` |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `DEEPSEEK_API_BASE` | DeepSeek API 地址 | `https://api.deepseek.com/v1` |
| `DATABASE_URL` | 数据库连接串 | `sqlite+aiosqlite:///./data/itops.db` |
| `REDIS_HOST` | Redis 地址 | `localhost` |
| `SECRET_KEY` | JWT 签名密钥 | （生产环境务必修改） |

完整配置项见 `.env` 文件。

## 项目结构

```
├── backend/                # FastAPI 应用
│   ├── api/                # 路由处理（认证、服务器、告警、工作流等）
│   ├── core/               # 中间件、日志、Redis、限流
│   ├── services/           # 业务逻辑（SSH、LLM、工作流引擎、通知）
│   │   └── llm/            # LLM 适配器（DeepSeek、OpenAI）
│   ├── models.py           # SQLAlchemy 数据模型
│   ├── schemas.py          # Pydantic 校验模型
│   ├── config.py           # 应用配置
│   └── main.py             # 应用入口
├── frontend-next/          # Next.js 应用
│   └── src/
│       ├── app/            # App Router 页面
│       ├── components/     # React 组件（工作流编辑器、侧边栏等）
│       └── lib/            # API 客户端、认证工具
├── tests/                  # 后端测试
├── docker-compose.yml      # Docker Compose 编排
├── nginx/                  # Nginx 反向代理配置
├── k8s/                    # Kubernetes 部署清单
├── helm/                   # Helm Chart
├── scripts/                # 部署脚本
└── .github/workflows/      # CI/CD 流水线
```

## API 接口一览

| 路由前缀 | 说明 |
|----------|------|
| `/api/auth` | 认证（登录、Token 刷新） |
| `/api/servers` | 服务器增删改查和 SSH 连接 |
| `/api/agents` | AI Agent 管理 |
| `/api/workflows` | 工作流编排和执行 |
| `/api/dashboard` | 仪表盘数据 |
| `/api/alerts` | 告警规则与告警记录 |
| `/api/patrol` | 定时巡检记录 |
| `/api/remediation` | 自动修复策略与日志 |
| `/api/chat` | AI 对话（含 RAG 上下文） |
| `/api/audit` | 审计日志查询 |
| `/api/knowledge` | 知识库管理 |
| `/api/notifications` | 通知渠道配置 |
| `/health` | 健康检查 |

## 部署

### Kubernetes (kind)

```bash
# 创建本地集群
scripts/deploy-local-k8s.sh
```

### Helm

```bash
helm install itops ./helm/itops-platform \
  --set secrets.openaiApiKey=your-key \
  --set secrets.secretKey=your-jwt-secret
```

## License

[MIT](LICENSE)
