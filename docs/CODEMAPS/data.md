<!-- Generated: 2026-06-13 | Tables: 17 | ~500 tokens -->

# Data Model

## Tables (17)

| Table | Key Columns | FK References | Indexes |
|-------|-------------|---------------|---------|
| `users` | id, email, password_hash, display_name, disabled_at | — | email (unique) |
| `refresh_tokens` | id, user_id, token_hash, family_id, jti, revoked_at | users | user_id, token_hash (unique), family_id, jti (unique) |
| `groups` | id, name, description, created_by | users | — |
| `group_memberships` | id, group_id, user_id, role | groups, users | group_id, user_id, unique(group,user) |
| `group_invites` | id, group_id, invite_code_hash, expires_at | groups, users | group_id, invite_code_hash (unique) |
| `group_join_requests` | id, group_id, user_id, status, reviewed_by | groups, users | group_id, user_id, unique(group,user,status) |
| `documents` | id, group_id, title, file_name, content_hash, status, ingestion_error | groups, users | group_id, content_hash (unique per group), file_hash |
| `document_chunks` | id, group_id, document_id, chunk_index, content, embedding | groups, documents | group_id, document_id, unique(doc,index), HNSW on embedding |
| `document_upload_sessions` | id, group_id, file_hash, chunk_size, status | groups, users | group_id, file_hash |
| `document_upload_chunks` | id, upload_id, chunk_index, storage_path | upload_sessions, groups | upload_id, unique(upload,index) |
| `ingestion_jobs` | id, group_id, document_id, status, step_log | groups, documents, users | group_id, document_id |
| `rag_runs` | id, group_id, user_id, question, answer, citations | groups, users | group_id, user_id |
| `conversations` | id, group_id, user_id, title | groups, users | group_id, user_id |
| `conversation_messages` | id, conversation_id, role, content, citations, tool_calls | conversations | conversation_id |
| `agent_runs` | id, group_id, user_id, goal, status, current_phase, plan_json, citations | groups, users, conversations | group_id, user_id |
| `agent_steps` | id, run_id, phase, step_index, thought, action_type, observation | agent_runs | run_id |
| `agent_memories` | id, group_id, user_id, key, value, scope, ttl_days | groups, users, agent_runs | group_id, user_id |

## Migrations

| ID | Name | What |
|----|------|------|
| 0001 | v1_auth_groups | users, refresh_tokens, groups, memberships, invites, join_requests |
| 0002 | v2_documents | documents, document_chunks |
| 0003 | v21_embeddings | embedding column on document_chunks |
| 0004 | v33_rag_runs | rag_runs table |
| 0005 | v22_chunked_uploads | upload_sessions, upload_chunks, document metadata columns |
| 0006 | v34_ingestion_jobs | ingestion_jobs, document.ingestion_error, HNSW index |
| 0007 | v4_conversations | conversations, conversation_messages |
| 0008 | v7_agent_orchestration | agent_runs, agent_steps, agent_memories |

## Document Status

```
uploaded → processing → ready ↔ archived
               ↘ failed → ready (retry)
```

## Ingestion Job Status

```
pending → running → completed / failed → running (retry)
```

## Key Types

- All IDs: `str(uuid4())` → `String(36)`
- Timestamps: `DateTime(timezone=True)`, `datetime.now(UTC)`
- Embeddings: `VectorType(1024)` (pgvector / SQLite float list)
- JSON columns: `citations`, `knowledge_gaps`, `step_log`, `frontmatter`, `tool_calls`
- `step_log` uses `MutableDict.as_mutable(JSON)` for mutation tracking
