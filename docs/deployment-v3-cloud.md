# Cloud Deployment Guide (V7)

Deploy Semantic Lighthouse on a small Ubuntu 24.04 ECS instance.
Updated 2026-06-13 for V7 Agent + Frontend Console.

Target server: 2 vCPU / 2 GiB RAM / Ubuntu 24.04 x64 / 3 Mbps

## Goal

- FastAPI + PostgreSQL/pgvector via Docker Compose
- Alembic migrations on startup (0008 head, 17 tables)
- `/health` returns DB + provider status
- Swagger at `/docs`, Console SPA at `/console`
- Full V1–V7 API surface
- Secrets in `.env.production`

## Out of Scope

- Kubernetes, RDS, MinIO, CI/CD
- HTTPS/domain/Nginx (requires DNS + certificate)
- Local LLM or local embedding model

## Server Bootstrap

SSH into the server, then run:

```bash
cd /opt
sudo mkdir -p semantic-lighthouse
sudo chown "$USER":"$USER" semantic-lighthouse
```

Install Docker, Docker Compose, and 2 GiB swap:

```bash
bash scripts/deploy/bootstrap-ubuntu.sh
```

If the project has not been copied to the server yet, copy it first, then run the script from the project root.

## Project Files

The production deployment uses:

- `Dockerfile`
- `docker-compose.prod.yml`
- `.env.production`
- `scripts/docker/start-api.sh`

Create the production env file on the server:

```bash
cp .env.production.example .env.production
nano .env.production
```

Fill these values manually:

- `POSTGRES_PASSWORD`
- `JWT_SECRET_KEY`
- `DASHSCOPE_API_KEY`
- `DEEPSEEK_API_KEY`

Do not commit `.env.production`.

V2.2 also requires document upload storage settings:

```text
DOCUMENT_STORAGE_PATH=/app/document-storage
UPLOAD_TMP_PATH=/app/upload-tmp
MAX_DOCUMENT_UPLOAD_BYTES=52428800
UPLOAD_SESSION_EXPIRE_HOURS=24
UPLOAD_CHUNK_BYTES=2097152
```

The production Compose file mounts:

```text
./document-storage -> /app/document-storage
./upload-tmp        -> /app/upload-tmp
```

These directories store uploaded original files and temporary chunks. Do not delete them during normal redeploys.

## Optional Knowledge Base Import

The compose file mounts:

```text
./knowledge-graph -> /app/knowledge-graph
```

If you want to use `POST /groups/{group_id}/documents/import-local` on the server, copy Markdown files into:

```bash
mkdir -p knowledge-graph
```

V2 upload APIs can still be used without this folder.

## Start

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Check status:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker logs semantic-lighthouse-api --tail 100
```

Expected:

- `semantic-lighthouse-postgres` is healthy
- `semantic-lighthouse-api` is healthy
- Alembic reaches latest migration

## Smoke Test

From the server:

```bash
curl -fsS http://127.0.0.1:8000/health
```

Run the full API smoke chain:

```bash
bash scripts/deploy/smoke-cloud.sh
```

If `DEEPSEEK_API_KEY` has not been configured yet, temporarily set:

```text
CHAT_PROVIDER=fake
```

Then restart the API container before running the smoke script. This validates the API, auth, document upload, retrieval, and response contract without calling the real chat provider.

This verifies:

- health check
- registration
- login
- group creation
- Markdown upload
- keyword RAG answer
- at least one citation returned

To smoke test the public endpoint instead of localhost:

```bash
BASE_URL=http://SERVER_PUBLIC_IP:8000 bash scripts/deploy/smoke-cloud.sh
```

## Real Provider Smoke

After configuring real keys:

```text
DASHSCOPE_API_KEY=...
DEEPSEEK_API_KEY=...
CHAT_PROVIDER=deepseek
EMBEDDING_PROVIDER=aliyun
```

Run this chain:

```text
register -> login -> create group -> upload Markdown -> rebuild embeddings -> semantic search -> RAG answer
```

Expected result:

- embedding rebuild returns `processed_count >= 1`
- semantic search returns at least one citation
- RAG answer returns a DeepSeek model name
- answer is grounded in the uploaded citation

Verified on 2026-06-11 with Alibaba Cloud ECS, Aliyun embedding, pgvector, and DeepSeek chat.

From your local browser:

```text
http://SERVER_PUBLIC_IP:8000/docs
```

The ECS security group must allow inbound TCP `8000` for this temporary demo.

## Security Group Cleanup

After `/docs` is reachable, tighten the ECS security group.

Keep only:

```text
TCP 22     your current public IP/32
TCP 8000   0.0.0.0/0 for temporary demo access
ICMP       optional
```

Remove:

```text
TCP 3389      0.0.0.0/0
TCP 1/65535   0.0.0.0/0
```

Risk if ignored:

- `TCP 1/65535` exposes every listening service on the instance.
- `TCP 3389` is unnecessary for Ubuntu and should not be open.

Later, replace public `8000` with HTTPS through a reverse proxy or cloud gateway.

## Stop

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml down
```

Do not add `-v` unless you intentionally want to delete PostgreSQL data.

## Engineering Notes

This deployment keeps the architecture intentionally small:

- Cloud APIs handle model inference.
- The ECS only runs API logic, PostgreSQL, and pgvector.
- `API_WORKERS=1` is intentional for a 2 GiB server.
- The local evidence gate prevents no-context RAG calls from wasting model tokens.
- Security group cleanup is part of deployment completion, not an optional polish step.

Interview version:

> I deployed the V3 RAG prototype on a small ECS by containerizing the API and pgvector database, keeping secrets in environment variables, using migrations on startup, and adding swap because the server has only 2 GiB RAM. I avoided Kubernetes and CI/CD at this stage because the goal was a reliable demo deployment, not production platform complexity.
