# V2.2 Chunked Upload Retrospective

## Decision: three-stage upload protocol

V2.2 uses `init -> chunks -> complete`.

- Risk if ignored: Large files would have to restart from zero after a network interruption.
- Control: `init` returns existing upload progress, chunks are uploaded independently, and `complete` only runs after all chunks are present.
- Verification: Tests cover new sessions, resume behavior, incomplete uploads, and successful complete.
- Interview version: I implemented upload as a protocol, not a single request with a larger body limit.

## Decision: group-scoped instant upload by SHA-256

`init` checks for a ready document with the same `group_id + file_hash`.

- Risk if ignored: Re-uploading the same document wastes bandwidth and pollutes the knowledge base.
- Control: Existing group document returns `type=INSTANT` and `document_id`.
- Verification: Tests prove a completed document can be re-initialized as instant upload.
- Interview version: I used content identity to avoid duplicate ingestion while preserving group isolation.

## Decision: local disk first, object storage later

V2.2 stores chunks and original files on local disk volumes.

- Risk if ignored: Adding MinIO or OSS now would increase deployment complexity before the ingestion protocol is stable.
- Control: Storage paths are isolated behind config and stored as relative paths in the database.
- Verification: Tests use temporary local directories; production Compose mounts `upload-tmp` and `document-storage`.
- Interview version: I designed the protocol so the storage backend can later move to MinIO or OSS without changing the API contract.

## Decision: parse on complete

V2.2 parses files synchronously in `complete`.

- Risk if ignored: A background queue would add operational complexity before large-file parsing is proven to be a bottleneck.
- Control: If parsing fails, no document is created and the upload session is marked failed.
- Verification: Tests cover MD, TXT, PDF, DOCX, unsupported formats, and hash mismatch.
- Interview version: I chose synchronous parsing to keep the first closed loop explainable, and left worker-based ingestion for a later scale iteration.
