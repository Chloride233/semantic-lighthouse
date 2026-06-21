# Cloud Smoke Playbook

Use this playbook after deploying Semantic Lighthouse to a small Ubuntu cloud server.
Covers V1-V7 capabilities. Updated 2026-06-16.

## Goal

Verify deployment in two levels:

1. Quick smoke script: auth, group creation, Markdown upload, keyword RAG, and citation output.
2. Manual 4-chain smoke: RAG, conversation, Agent run, and frontend console.

The full production chain spans:

```text
health -> register -> login -> create group -> upload -> rebuild -> hybrid search
-> RAG answer -> conversation multi-turn -> agent run (plan -> execute -> conclude) -> frontend console
```

## Preconditions

Server:

```bash
cd /opt/semantic-lighthouse
sudo docker compose --env-file .env.production -f docker-compose.prod.yml ps
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

## Quick Smoke Script

Run from the cloud server:

```bash
cd /opt/semantic-lighthouse
bash scripts/deploy/smoke-cloud.sh
```

Expected:

```text
health ok
register ok
login ok
group ok
upload ok
rag ok
citation_count: 1
```

Verified on Tencent Cloud Lighthouse on 2026-06-16 with Ubuntu Server 24.04 Docker CE image, PostgreSQL/pgvector containers healthy, `/health` returning 200, and the quick smoke script returning one citation.

## Manual Smoke Commands

Run from the cloud server. Each chain uses the same auth setup from Chain 1.

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
  -d '{"question":"What does Ontology connect?","retrieval_method":"hybrid"}')
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
curl -fsS -o /dev/null -w "%{http_code}" "$BASE_URL/static/console.js" && echo " console.js"
curl -fsS -o /dev/null -w "%{http_code}" "$BASE_URL/static/styles.css" && echo " styles.css"
```

## Passing Criteria

| Chain | Expected |
|-------|----------|
| `/health` | `{"status":"ok","database":"connected",...}` |
| Quick smoke | `rag ok`, `citation_count >= 1` |
| Chain 1 (RAG) | confidence high/medium/low, citations >= 1, model from configured chat provider |
| Chain 2 (Conversation) | message_count >= 4 (2 user + 2 assistant) |
| Chain 3 (Agent) | status=completed, step_count >= 2 |
| Chain 4 (Console) | 200 for console HTML + JS + CSS |
| Chain 5 (FDE) | outcome-summary 200, outcome-artifact.md returns text/markdown, artifact gate PASS |

## Failure Interpretation

| Status | Meaning |
|--------|---------|
| `401` | Token missing or expired |
| `403` | Group membership or role boundary |
| `502` embedding | Aliyun key or DashScope issue |
| `502` RAG | DeepSeek key or response format |
| `citations: 0` | Retrieval failed or embeddings not rebuilt |
| `database: unavailable` | PostgreSQL not reachable |

## Chain 5: FDE Outcome Delivery (Phase 16+)

> Added 2026-06-21 during Phase 18.1 config audit. The FDE outcome chain is
> the strongest current demo. Verify it after the 4-chain smoke above.

```bash
# Create outcome record
OUTCOME=$(curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/projects/$PROJECT_ID/outcomes" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Deploy Smoke Outcome","decision_summary":"Deployment verified."}')
OUTCOME_ID=$(printf '%s' "$OUTCOME" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# Fetch outcome summary (JSON)
curl -fsS "$BASE_URL/groups/$GROUP_ID/projects/$PROJECT_ID/outcome-summary" \
  -H "Authorization: Bearer $TOKEN" | python3 -c '
import json,sys; d=json.load(sys.stdin)
print(f"evidence={d[\"evidence_summary\"][\"total_active\"]} pkg={d[\"package_summary\"][\"count\"]} runtime={d[\"runtime_summary\"][\"total_operations\"]}")'

# Fetch markdown artifact
curl -fsS "$BASE_URL/groups/$GROUP_ID/projects/$PROJECT_ID/outcome-artifact.md" \
  -H "Authorization: Bearer $TOKEN" -o /tmp/outcome-artifact.md
wc -c < /tmp/outcome-artifact.md
head -5 /tmp/outcome-artifact.md
```

**Local FDE smoke (pre-deployment)**:
```powershell
.\.venv\Scripts\python scripts\smoke_fde_demo.py
```

## Interview Version

> I verify deployment through a quick script and a 5-chain smoke suite covering auth, RAG, multi-turn conversation, agent orchestration, frontend console, and the FDE outcome delivery chain. Each chain proves a different layer of the enterprise RAG/Agent/Ontology stack. The FDE chain — business goal → evidence → package → runtime → outcome → markdown artifact — is the strongest current demo.
