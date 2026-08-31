# Security

## Tenant isolation

Every dataset, training run, model, deployment, and API key is scoped by `organization_id`. Service methods always verify membership before returning or mutating resources.

## Authentication

- Password hashing: bcrypt via passlib
- Tokens: JWT (access + refresh), HS256
- Bearer auth on protected routes

## Uploads

- Extension allowlist (`.jsonl`, `.json`)
- Max size from config (default 100 MB)
- UTF-8 text only
- Stored under org/dataset-scoped paths
- Never executed

## Principles

- No customer training data sent to external AI providers by default
- Secrets only via environment variables
- Structured logs without passwords, tokens, or raw dataset content
- CORS restricted to configured origins

## Future hardening (Phase 10)

- API key hashing at rest
- Rate limiting
- Virus/malware scan hooks for uploads
- CSRF protections where cookie sessions are used
- Security headers middleware
