# API Reference (v0.1)

Base URL: `http://localhost:8000`

## Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Create user + personal org |
| POST | `/api/v1/auth/login` | JWT access + refresh |
| GET | `/api/v1/auth/me` | Current user |

## Projects

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects` | List projects |
| GET | `/api/v1/projects/{id}` | Get project |

## Datasets

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/datasets` | Create dataset metadata |
| POST | `/api/v1/datasets/{id}/upload` | Upload JSONL + validate |
| GET | `/api/v1/datasets/project/{project_id}` | List datasets |
| GET | `/api/v1/datasets/{id}/versions/{vid}/report` | Quality report |

## Training

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/training/base-models` | Supported base models |
| POST | `/api/v1/training/estimate` | VRAM/time/cost estimates |
| POST | `/api/v1/training/runs` | Start training job |
| GET | `/api/v1/training/runs/project/{id}` | List runs |
| GET | `/api/v1/training/runs/{id}` | Run status / logs |
| POST | `/api/v1/training/runs/{id}/cancel` | Cancel if safe |

## Models

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/models/project/{id}` | List registered models |
| GET | `/api/v1/models/{id}` | Model + versions |
| GET | `/api/v1/models/versions/{id}` | Single version + eval |

## Deployments

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/deployments` | Deploy model version |
| GET | `/api/v1/deployments/project/{id}` | List deployments |

## Inference (OpenAI-compatible)

```
POST /v1/chat/completions
Authorization: Bearer tai_...
{
  "model": "tunerai/<endpoint_slug>",
  "messages": [{"role": "user", "content": "What is SSRF?"}]
}
```
