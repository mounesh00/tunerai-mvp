# TunerAI

**Tune AI to your domain.**

TunerAI is an intelligent domain-adaptation platform for production AI. It helps organizations turn specialized datasets into measurable, deployable, domain-specialized open-source LLM models using high-quality data preparation, parameter-efficient fine-tuning (QLoRA/SFT), rigorous evaluation, versioning, and deployment.

> This is **not** a generic chatbot platform. It is an LLM domain-adaptation platform focused on measurable improvement.

## Vision

> The platform that turns domain knowledge and proprietary datasets into measurable, deployable, domain-specialized AI models.

## MVP Scope (v0.1)

Complete end-to-end workflow:

1. Register / Login ✅
2. Create Project ✅
3. Upload JSONL dataset ✅
4. Dataset validation & quality report ✅
5. Select supported base model ✅
6. Configure QLoRA / SFT ✅
7. Start training job (Celery or inline dry-run) ✅
8. Monitor training progress ✅
9. Evaluate tuned model vs base model ✅
10. Register model in registry ✅
11. Deploy OpenAI-compatible inference API ✅
12. View usage & logs (basic) ✅

**Note:** Without a GPU, training runs in **dry-run** mode (`TUNERAI_DRY_RUN=true`) which simulates the job lifecycle and produces honest evaluation structure. On a CUDA machine with PEFT/TRL installed, set `TUNERAI_DRY_RUN=false` for real QLoRA.

Flagship demo domain: **Cybersecurity** (authorized/public educational data only).

## Tech Stack

| Layer        | Technology                                      |
|--------------|-------------------------------------------------|
| Frontend     | Next.js, TypeScript, Tailwind CSS, shadcn/ui    |
| Backend      | Python, FastAPI, Pydantic, SQLAlchemy (async)   |
| Database     | PostgreSQL                                      |
| Queue        | Redis + Celery                                  |
| ML           | PyTorch, Transformers, PEFT, TRL, bitsandbytes  |
| Storage      | S3-compatible object storage                    |
| Inference    | vLLM (OpenAI-compatible)                        |
| Infra        | Docker, Docker Compose                          |

## Monorepo Structure

```
tunerai/
├── apps/
│   ├── web/          # Next.js frontend
│   └── api/          # FastAPI backend
├── ml/
│   ├── data/         # Dataset processing
│   ├── training/     # QLoRA / SFT pipelines
│   ├── evaluation/   # Evaluation engine
│   └── inference/    # Inference helpers
├── workers/          # Celery workers (GPU jobs)
├── packages/
│   └── shared/       # Shared types / utilities
├── infra/
│   ├── docker/       # Dockerfiles
│   └── migrations/   # Alembic migrations
├── docs/
├── tests/
├── scripts/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick Start (Local Development)

### Prerequisites

- Docker & Docker Compose
- Node.js 20+
- Python 3.11+
- (Optional) NVIDIA GPU + CUDA for local training

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env if needed (defaults work for local Docker)
```

### 2. Start infrastructure

```bash
docker compose up -d db redis
```

### 3. Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# From apps/api with PYTHONPATH including this directory:
export PYTHONPATH=.
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Frontend

```bash
cd apps/web
npm install
npm run dev
```

### 5. Full stack with Docker

```bash
docker compose up --build
```

- Web: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Development Phases

We follow a strict phased approach:

1. **Phase 1** – Repository, Docker, PostgreSQL, FastAPI, Next.js, auth foundation, projects, health, migrations, basic dashboard
2. **Phase 2** – Authentication, Projects, Dataset upload
3. **Phase 3** – Dataset validation & quality report
4. **Phase 4** – ML training CLI + QLoRA/SFT pipeline
5. **Phase 5** – GPU worker, Redis/Celery, training jobs
6. **Phase 6** – Evaluation engine
7. **Phase 7** – Model registry
8. **Phase 8** – Inference API
9. **Phase 9** – Full dashboard
10. **Phase 10** – Security hardening
11. **Phase 11** – Documentation
12. **Phase 12** – Public CyberSec demo

## Core Principles

- **Measurable improvement** – every tuned model is evaluated against the base model.
- **Honest results** – if tuning does not improve the benchmark, we say so.
- **Recommend the cheapest viable path** – RAG / prompt optimization before expensive fine-tuning when sufficient.
- **Tenant isolation** from day one.
- **No silent data discarding** – always show what was removed and why.
- **Security & privacy first**.

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [SECURITY.md](docs/SECURITY.md)
- [API.md](docs/API.md)
- [ML_PIPELINE.md](docs/ML_PIPELINE.md)
- [EVALUATION.md](docs/EVALUATION.md)
- [DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [CONTRIBUTING.md](docs/CONTRIBUTING.md)

## License

Proprietary – All rights reserved (TunerAI.in)

---

Built with the long-term goal of becoming a trusted platform for domain-specific AI adaptation, evaluation, and deployment.
