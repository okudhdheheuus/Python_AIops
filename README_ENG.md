# ITOps Agent Platform

An AI-powered IT operations automation platform with multi-provider LLM integration, intelligent alerting, automated remediation, and visual workflow orchestration.

## Features

- **Server Management** — SSH-based server inventory with credential management and health monitoring
- **AI Chat Copilot** — Multi-provider LLM chat (DeepSeek / OpenAI-compatible) with RAG knowledge base retrieval
- **Visual Workflow Editor** — Drag-and-drop node editor for building automation workflows
- **Workflow Engine** — Execute multi-step workflows with SSH, agent, and conditional nodes
- **Patrol & Alerting** — Scheduled server health patrols with Prometheus metrics, alert rules, and silence management
- **Auto Remediation** — AI-generated or static repair commands triggered by alerts, with approval workflows
- **Knowledge Base (RAG)** — Store and retrieve operational runbooks, auto-wired into AI chat context
- **Audit Logging** — Full audit trail of all user actions and automated operations
- **Notification Channels** — DingTalk / Feishu webhook notifications for alerts and events
- **Dashboard** — High-level operational overview with key metrics

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, FastAPI, SQLAlchemy (async), Redis, APScheduler |
| Frontend | Next.js 16, React 19, Tailwind CSS 4, TypeScript |
| Workflow UI | @xyflow/react (React Flow) |
| Database | PostgreSQL 16 (production) / SQLite (development) |
| LLM | DeepSeek / OpenAI-compatible (Zhipu GLM) |
| Deployment | Docker Compose, Kubernetes, Helm |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) Python 3.11+ and Node.js 20+ for local development

### Docker Compose

```bash
# Clone the repository
git clone <repo-url> && cd python-itops-platform

# Set your LLM API key
export OPENAI_API_KEY=your-api-key

# Start all services
docker-compose up -d
```

The application will be available at:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Metrics | http://localhost:8000/metrics |

### Local Development

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your configuration
uvicorn backend.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend-next
npm install
npm run dev
```

## Configuration

Key environment variables (set via `.env` or environment):

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider: `openai` or `deepseek` | `openai` |
| `OPENAI_API_KEY` | OpenAI-compatible API key | — |
| `OPENAI_API_BASE` | API base URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Model name | `gpt-3.5-turbo` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `DEEPSEEK_API_BASE` | DeepSeek API base | `https://api.deepseek.com/v1` |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./data/itops.db` |
| `REDIS_HOST` | Redis host | `localhost` |
| `SECRET_KEY` | JWT signing key | (change in production) |

See `.env` for the full list of configurable options.

## Project Structure

```
├── backend/                # FastAPI application
│   ├── api/                # Route handlers (auth, servers, alerts, workflows, etc.)
│   ├── core/               # Middleware, logging, Redis, rate limiting
│   ├── services/           # Business logic (SSH, LLM, workflow engine, notifications)
│   │   └── llm/            # LLM provider adapters (DeepSeek, OpenAI)
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   ├── config.py           # Application settings
│   └── main.py             # App entry point
├── frontend-next/          # Next.js application
│   └── src/
│       ├── app/            # App Router pages
│       ├── components/     # React components (WorkflowEditor, Sidebar, etc.)
│       └── lib/            # API client, auth utilities
├── tests/                  # Backend test suite
├── docker-compose.yml      # Docker Compose orchestration
├── nginx/                  # Nginx reverse proxy config
├── k8s/                    # Kubernetes manifests
├── helm/                   # Helm chart
├── scripts/                # Deployment scripts
└── .github/workflows/      # CI/CD pipelines
```

## API Endpoints

| Prefix | Description |
|--------|-------------|
| `/api/auth` | Authentication (login, token refresh) |
| `/api/servers` | Server CRUD and SSH connectivity |
| `/api/agents` | AI agent management |
| `/api/workflows` | Workflow CRUD and execution |
| `/api/dashboard` | Dashboard metrics |
| `/api/alerts` | Alert rules and firing alerts |
| `/api/patrol` | Scheduled patrol records |
| `/api/remediation` | Auto-remediation policies and logs |
| `/api/chat` | AI chat with RAG context |
| `/api/audit` | Audit log queries |
| `/api/knowledge` | Knowledge base CRUD |
| `/api/notifications` | Notification channel config |
| `/health` | Health check endpoints |

## Deployment

### Kubernetes (kind)

```bash
# Create local cluster
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
