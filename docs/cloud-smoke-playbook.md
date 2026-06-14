# Cloud Smoke Playbook

Use this playbook after deploying Semantic Lighthouse to Alibaba Cloud ECS.
Covers V1–V7 capabilities. Updated 2026-06-13.

## Goal

Verify the full production chain across 4 smoke chains:

```text
health → register → login → create group → upload → rebuild → hybrid search
→ RAG answer → conversation multi-turn → agent run (plan→execute→conclude) → frontend console
```

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

Run from the ECS server. Each chain uses the same auth setup from Chain 1.

### Common Setup

```bash
BASE_URL=http://127.0.0.1:8000
EMAIL="smoke-$(date +%s)@e.com"
PASSWORD="Passw0rd!"
```

### Chain 1: RAG Answer (V3 baseline)

```bash
curl -fsS -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"display_name\":\"Smoke\"}"

LOGIN=$(curl -fsS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
TOKEN=$(printf '%s' "$LOGIN" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

GROUP=$(curl -fsS -X POST "$BASE_URL/groups" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name":"Smoke"}')
GROUP_ID=$(printf '%s' "$GROUP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

cat > /tmp/smoke-onto.md <<'EOF'
---
title: Ontology Smoke
entityType: Concept
source: cloud-smoke
status: reviewed
---
# Ontology
Ontology connects business objects, data, permissions, and AI workflows for enterprise context.
EOF

curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/documents/upload" \
  -H "Authorization: Bearer $TOKEN" -F "file=@/tmp/smoke-onto.md;type=text/markdown"

curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/documents/embeddings/rebuild" \
  -H "Authorization: Bearer $TOKEN"

RAG=$(curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/rag/answer" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"企业已经有数据中台，为什么还需要 Ontology？","retrieval_method":"hybrid"}')
printf '%s' "$RAG" | python3 -c '
import json,sys; b=json.load(sys.stdin)
print(f"confidence: {b[\"confidence\"]}  model: {b[\"model\"]}  citations: {len(b[\"citations\"])}")'
```

### Chain 2: Conversation Multi-Turn (V4)

```bash
CONV=$(curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/conversations" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"title":"Smoke Chat"}')
CONV_ID=$(printf '%s' "$CONV" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/conversations/$CONV_ID/messages" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"What is Ontology?","retrieval_method":"keyword"}' > /dev/null

curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/conversations/$CONV_ID/messages" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"How does it help AI?","retrieval_method":"keyword"}' > /dev/null

curl -fsS "$BASE_URL/groups/$GROUP_ID/conversations/$CONV_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"messages: {d[\"message_count\"]}")'
```

### Chain 3: Agent Run (V7)

```bash
RUN=$(curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/agent/runs" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"goal":"Search Ontology knowledge"}')
RUN_ID=$(printf '%s' "$RUN" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/agent/runs/$RUN_ID/execute" \
  -H "Authorization: Bearer $TOKEN" > /dev/null

curl -fsS "$BASE_URL/groups/$GROUP_ID/agent/runs/$RUN_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -c 'import json,sys; r=json.load(sys.stdin); print(f"status={r[\"status\"]} steps={r[\"step_count\"]}")'
```

### Chain 4: Frontend Console

```bash
curl -fsS -o /dev/null -w "%{http_code}" "$BASE_URL/console" && echo " console"
curl -fsS -o /dev/null -w "%{http_code}" "$BASE_URL/static/js/app.js" && echo " app.js"
curl -fsS -o /dev/null -w "%{http_code}" "$BASE_URL/static/styles.css" && echo " styles.css"
```

## Passing Criteria

| Chain | Expected |
|-------|----------|
| /health | `{"status":"ok","database":"connected",...}` |
| Chain 1 (RAG) | confidence high/medium/low, citations ≥ 1, model deepseek... |
| Chain 2 (Conv) | message_count ≥ 4 (2 user + 2 assistant) |
| Chain 3 (Agent) | status=completed, step_count ≥ 2 |
| Chain 4 (Console) | 200 for console HTML + JS + CSS |

## Failure Interpretation

| Status | Meaning |
|--------|---------|
| `401` | Token missing or expired |
| `403` | Group membership or role boundary |
| `502` embedding | Aliyun key or DashScope issue |
| `502` RAG | DeepSeek key or response format |
| `citations: 0` | Retrieval failed or embeddings not rebuilt |
| `database: unavailable` | PostgreSQL not reachable |

## Interview Version

> I verify deployment through a 4-chain smoke suite covering auth, RAG, multi-turn conversation, agent orchestration, and frontend console. Each chain proves a different layer of the enterprise RAG/Agent stack — not just Swagger.
