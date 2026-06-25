#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
EMAIL="smoke-$(date +%s)@example.com"
PASSWORD="${SMOKE_PASSWORD:-SmokeTest123!}"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

json_field() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

echo "Base URL: $BASE_URL"

curl -fsS "$BASE_URL/health" >/dev/null
echo "health ok"

REGISTER_BODY=$(cat <<JSON
{"email":"$EMAIL","password":"$PASSWORD","display_name":"Smoke User"}
JSON
)
curl -fsS -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "$REGISTER_BODY" >/dev/null
echo "register ok"

LOGIN_RESPONSE=$(curl -fsS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
ACCESS_TOKEN=$(printf '%s' "$LOGIN_RESPONSE" | json_field access_token)
echo "login ok"

GROUP_RESPONSE=$(curl -fsS -X POST "$BASE_URL/groups" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Group","description":"Cloud deployment smoke test"}')
GROUP_ID=$(printf '%s' "$GROUP_RESPONSE" | json_field id)
echo "group ok: $GROUP_ID"

cat > "$TMP_DIR/ontology-smoke.md" <<'MD'
---
title: Ontology Smoke
entityType: Concept
source: cloud-smoke
status: reviewed
---

# Ontology

Ontology connects business objects, data assets, permissions, and AI workflows.
MD

curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/documents/upload" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@$TMP_DIR/ontology-smoke.md;type=text/markdown" >/dev/null
echo "upload ok"

RAG_RESPONSE=$(curl -fsS -X POST "$BASE_URL/groups/$GROUP_ID/rag/answer" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"我们已经有数据中台，为什么还需要 Ontology？","retrieval_method":"keyword"}')

printf '%s' "$RAG_RESPONSE" > "$TMP_DIR/rag-response.json"
python3 - "$TMP_DIR/rag-response.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as file:
    body = json.load(file)
print("rag ok")
print("confidence:", body["confidence"])
print("retrieval_method:", body["retrieval_method"])
print("citation_count:", len(body["citations"]))
if not body["citations"]:
    raise SystemExit("expected at least one citation")
print("first_title:", body["citations"][0]["title"])
PY
