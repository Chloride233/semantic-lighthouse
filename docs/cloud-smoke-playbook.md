# Cloud Smoke Playbook

Use this playbook after deploying Semantic Lighthouse to Alibaba Cloud ECS.

## Goal

Verify the production-like RAG chain:

```text
register -> login -> create group -> upload Markdown -> rebuild embeddings -> semantic search -> RAG answer
```

This proves:

- auth works on the cloud API
- group-owned resources can be created
- documents can be uploaded
- Aliyun embedding can write vectors
- pgvector semantic search works
- DeepSeek can generate an answer from retrieved citations

## Preconditions

Server:

```bash
cd /opt/semantic-lighthouse
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Expected:

```text
semantic-lighthouse-api        healthy
semantic-lighthouse-postgres   healthy
```

Environment:

```text
EMBEDDING_PROVIDER=aliyun
DASHSCOPE_API_KEY=...
CHAT_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
```

Do not paste API keys into screenshots or chat.

## Smoke Commands

Run from the ECS server:

```bash
BASE_URL=http://127.0.0.1:8000
EMAIL="real-smoke-$(date +%s)@example.com"
PASSWORD="Passw0rd!"

curl -fsS "$BASE_URL/health" && echo

curl -fsS -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"display_name\":\"Real Smoke User\"}"

LOGIN=$(curl -fsS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

TOKEN=$(printf '%s' "$LOGIN" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

GROUP=$(curl -fsS -X POST "$BASE_URL/groups" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Real Cloud Smoke Group"}')

GROUP_ID=$(printf '%s' "$GROUP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

cat > /tmp/ontology-real-smoke.md <<'EOF'
---
title: Ontology Real Smoke
entityType: Concept
source: cloud-smoke
status: reviewed
---

# Ontology

Ontology connects business objects, data assets, permissions, and AI workflows. It helps enterprise AI systems retrieve context with business meaning instead of only raw tables.
EOF

curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/documents/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/ontology-real-smoke.md;type=text/markdown"

curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/documents/embeddings/rebuild" \
  -H "Authorization: Bearer $TOKEN"

curl -fsS "$BASE_URL/groups/$GROUP_ID/documents/semantic-search?q=enterprise%20ontology&limit=3" \
  -H "Authorization: Bearer $TOKEN"

RAG=$(curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/rag/answer" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"企业已经有数据中台，为什么还需要 Ontology？","retrieval_method":"semantic","limit":3}')

printf '%s' "$RAG" | python3 -c 'import json,sys; b=json.load(sys.stdin); print("confidence:", b["confidence"]); print("model:", b["model"]); print("retrieval:", b["retrieval_method"]); print("citations:", len(b["citations"])); print("answer:", b["answer"][:300])'
```

## Passing Criteria

The final output should include:

```text
confidence: high|medium|low
model: deepseek...
retrieval: semantic
citations: 1 or more
answer: ...
```

## Failure Interpretation

- `401`: login token missing or invalid
- `403`: group membership or role boundary failed
- `502` during embedding: Aliyun key, network, or embedding provider problem
- `502` during RAG answer: DeepSeek key, network, or response format problem
- `citations: 0`: retrieval failed or embeddings were not rebuilt

## Interview Version

> I verify cloud RAG through an end-to-end smoke chain rather than only checking Swagger. The smoke creates a real user and group, uploads a Markdown source, builds embeddings through Aliyun, searches pgvector, and asks DeepSeek for a citation-grounded answer.
