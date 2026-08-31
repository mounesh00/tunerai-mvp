# TunerAI Architecture

## High-Level Overview

TunerAI is a modular monolith with a separate GPU worker process.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Next.js    │────▶│  FastAPI    │────▶│ PostgreSQL  │
│  (Web)      │     │  (API)      │     │             │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           │ enqueue
                           ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   Redis     │────▶│   Celery    │
                    │   (Queue)   │     │  (Worker)   │
                    └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ GPU / ML    │
                                        │ Training    │
                                        └─────────────┘
```

## Core Domains

| Domain          | Responsibility                                      |
|-----------------|-----------------------------------------------------|
| Auth & Tenancy  | Users, Organizations, API keys, isolation            |
| Projects        | Top-level container for datasets, runs, models      |
| Datasets        | Upload, validation, quality scoring, versioning     |
| Training        | Config, job lifecycle, QLoRA/SFT execution          |
| Evaluation      | Base vs tuned comparison, benchmarks                |
| Models          | Registry, versioning, artifacts                     |
| Deployments     | Inference endpoints, OpenAI-compatible API          |
| Observability   | Structured logs, usage tracking                     |

## Key Design Decisions

### 1. Tenant Isolation
Every resource (dataset, training run, model, deployment, API key) belongs to an Organization (and usually a Project). All queries are scoped by `organization_id`. No cross-tenant access is possible.

### 2. Job System
Training and heavy evaluation never run inside the FastAPI request cycle. Flow:

```
API → create TrainingRun (status=QUEUED) → Celery task → Worker updates status
```

Statuses: `QUEUED → PREPARING → TRAINING → EVALUATING → PACKAGING → COMPLETED | FAILED | CANCELLED`

### 3. Dataset Pipeline
```
Upload → Validate schema → Parse → Normalize → Detect duplicates/malformed
→ Token estimates → Length distribution → Quality score → Train/val split
```
Never silently discard records. Always surface what was removed and why.

### 4. Training Abstraction
```
BaseModel → TrainingStrategy (QLoRA/SFT) → TrainingConfig → TrainingRun → ModelArtifact
```
Beginner presets (Fast / Balanced / Quality) + Advanced full hyperparameter control.

### 5. Evaluation as a First-Class Feature
Every successful training run produces an evaluation comparing the tuned model against the base model on a held-out benchmark. Results are honest; regressions are explicitly reported.

### 6. Storage
- Relational data → PostgreSQL
- Artifacts (datasets, adapters, checkpoints) → S3-compatible object storage
- Temporary job logs → Redis / PostgreSQL

### 7. Future Extensibility
Interfaces are designed so a future “AutoTune” layer can:
- Classify task from dataset
- Recommend model + strategy + hyperparameters
- Iterate based on evaluation results

## Technology Choices Rationale

- **FastAPI + async SQLAlchemy**: High performance, excellent OpenAPI docs, type safety with Pydantic.
- **Next.js App Router**: Modern React, server components, excellent DX for dashboards.
- **Celery + Redis**: Battle-tested job queue; easy to scale workers later.
- **PEFT + TRL + bitsandbytes**: Industry standard for parameter-efficient fine-tuning on consumer/professional GPUs.
- **Docker Compose first**: Fast local iteration; Kubernetes only when truly needed.

## Directory Responsibilities

- `apps/api` – HTTP API, auth, business logic, DB models, schemas
- `apps/web` – UI
- `ml/*` – Pure ML code (no FastAPI imports if possible)
- `workers` – Celery app and task definitions
- `packages/shared` – Shared Pydantic models / constants that both API and workers can import
- `infra` – Dockerfiles, Alembic migrations

## Security Boundaries

- Authn/Authz at the API layer
- Tenant scoping in every repository method
- Uploaded files treated as untrusted (MIME, size, extension validation)
- Secrets only via environment variables
- No customer training data sent to external AI providers by default
