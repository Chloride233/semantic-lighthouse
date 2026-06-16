# Cloud Deployment Guide (V7)

Deploy Semantic Lighthouse on a small Ubuntu 24.04 cloud server.
Updated 2026-06-16 after Tencent Cloud Lighthouse verification.

Baseline target server: 2 vCPU / 2 GiB RAM / Ubuntu 24.04 x64 / 3 Mbps.
Verified Tencent Cloud server: Lighthouse 4 vCPU / 4 GiB RAM / 40 GiB system disk / Ubuntu Server 24.04 LTS Docker CE image.

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

Tencent Cloud note: the Docker CE application image already includes Docker and Compose. Still run the version checks and keep the bootstrap script available for missing packages or swap setup:

```bash
docker --version
docker compose version
free -h
df -h
```

## Project Files

The production deployment uses:

- `Dockerfile`
- `docker-compose.prod.yml`
- `.env.production`
- `scripts/docker/start-api.sh`

If using the Tencent Cloud console file upload, upload the clean deploy archive to:

```text
/home/ubuntu
```

Then extract it into the stable deployment path:

```bash
sudo mkdir -p /opt/semantic-lighthouse
sudo chown ubuntu:ubuntu /opt/semantic-lighthouse
tar -xzf ~/semantic-lighthouse-deploy.tar.gz -C /opt/semantic-lighthouse
cd /opt/semantic-lighthouse
```

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
sudo docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Check status:

```bash
sudo docker compose --env-file .env.production -f docker-compose.prod.yml ps
sudo docker logs semantic-lighthouse-api --tail 100
```

Expected:

- `semantic-lighthouse-postgres` is healthy
- `semantic-lighthouse-api` is healthy
- Alembic reaches latest migration

If `docker compose` fails with `permission denied while trying to connect to the Docker daemon socket`, use `sudo docker compose` for deployment. To remove the need for `sudo`, add the user to the `docker` group and re-login:

```bash
sudo usermod -aG docker ubuntu
```

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

Verified on 2026-06-16 with Tencent Cloud Lighthouse, Ubuntu Server 24.04 Docker CE image, PostgreSQL/pgvector, real provider environment variables configured on the server, and `scripts/deploy/smoke-cloud.sh` passing with one citation.

From your local browser:

```text
http://<SERVER_PUBLIC_IP>:8000/docs
http://<SERVER_PUBLIC_IP>:8000/console
```

The cloud firewall or security group must allow inbound TCP `8000` for this temporary demo.

## Security Group Cleanup

After `/docs` and `/console` are reachable, tighten the cloud firewall or security group.

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
sudo docker compose --env-file .env.production -f docker-compose.prod.yml down
```

Do not add `-v` unless you intentionally want to delete PostgreSQL data.

## Engineering Notes

This deployment keeps the architecture intentionally small:

- Cloud APIs handle model inference.
- The cloud server only runs API logic, PostgreSQL, and pgvector.
- `API_WORKERS=1` is intentional for small 2-4 GiB servers.
- The local evidence gate prevents no-context RAG calls from wasting model tokens.
- Security group cleanup is part of deployment completion, not an optional polish step.

Interview version:

> I deployed the RAG/Agent prototype on a small Ubuntu cloud server by containerizing the API and pgvector database, keeping secrets in environment variables, running migrations on startup, and validating the full chain with smoke tests. I avoided Kubernetes and CI/CD at this stage because the goal was a reliable demo deployment, not production platform complexity.
