---
title: Semantic Lighthouse Fit
tags:
  - semantic-lighthouse/product
  - ontology
  - roadmap-input
created: 2026-07-08
---

# Semantic Lighthouse Fit

This note maps [[synthesis]] into the current repository context. It is intentionally not a roadmap commitment.

## Current Alignment

Semantic Lighthouse already aligns with the article set in several ways:

- Product identity: ontology-oriented semantic operating layer, not a generic chat-over-documents tool.
- Delivery chain: auth and group isolation, document ingestion, retrieval evidence, citation-grounded RAG, user-confirmed action, controlled Agent workflow, ontology governance and graph.
- Phase 19: offline ontology artifacts with no DB writes, no API change, and governance feedback. This resembles a safe early Semantic CI/CD segment.
- Runtime boundary: MCP is not started and remains a future adapter candidate, matching the article set's warning that action harness, identity, audit, and HITL must be scoped before runtime tools.

## Most Useful Product Concepts to Absorb

### Semantic Asset Base

Use A42/A48 as conceptual input:

- Ontology: business object map.
- Metrics: measurement layer.
- Mapping: ontology and metrics handshake.
- Governance: ownership, versioning, review, lifecycle.
- Evidence anchors: documents and data fragments attached to semantic nodes.

Project inference: this could become the top-level mental model for future product copy and architecture notes.

### Semantic CI/CD

Use A18 as implementation language:

- Draft generation.
- Symbolic validation gate.
- Human review queue.
- Versioned merge.
- Runtime feedback loop.

Project inference: current offline artifacts could evolve into a visible review workflow before any DB-backed governance feature.

### Action Harness

Use A15/A20 as safety language:

- Agent output is not the same as agent action.
- Any write-like action needs typed intent, permissions, evidence, confirmation, execution status, audit, and rollback or compensation design.

Project inference: continue preserving current write boundaries. Do not let RAG confidence or ontology extraction imply action authorization.

### Strong/Weak Relation Split

Use A47:

- Approved hard relations belong in governed ontology.
- LLM-generated candidate relations belong in review queues with confidence, evidence, and source context.
- Embedding similarity should stay in retrieval/ranking or weak-signal layers.

Project inference: model schema should avoid one undifferentiated `relationship` bucket.

## Candidate Future Gates

These are possible decision gates, not implementation tasks.

1. Semantic CI/CD UI gate
   - Goal: expose draft, validation, review, and governance feedback as a product loop.
   - Risk: reviewer overload and premature DB-backed governance.
   - Required boundary: no automatic writes without explicit approval and audit.

2. Metric-Ontology mapping gate
   - Goal: introduce metric definitions, dimensions, and mapping contracts as first-class semantic assets.
   - Risk: expanding beyond current ontology artifacts into BI product scope.
   - Required boundary: start with offline mapping and examples before runtime agent integration.

3. HITL evidence packet gate
   - Goal: make every proposal reviewable with source, rule, confidence, diff, and blast-radius context.
   - Risk: UI complexity and false confidence.
   - Required boundary: distinguish evidence from proof.

4. Strong/weak relation governance gate
   - Goal: track candidate edges separately from approved constraints and relationships.
   - Risk: over-modeling early.
   - Required boundary: keep weak edges out of hard reasoning until approved.

5. Action harness gate
   - Goal: define typed, confirmed, audited agent actions.
   - Risk: permission, group isolation, and operational side effects.
   - Required boundary: Safety Lane only.

## What Not To Absorb

- Do not promise automatic ontology construction. A18 explicitly rejects that for serious enterprise contexts.
- Do not treat OWL as mandatory user-facing architecture. A49/A51 argue for scenario-fit.
- Do not treat small scenes as successful unless they deposit reusable semantic assets. A27 warns that small scenes can become dead ends.
- Do not position HITL as a checkbox. A10/A20 require informed, empowered, accountable reviewers.
- Do not conflate knowledge base, semantic library, ontology, and knowledge graph. A33/A48 separate these concepts.

## Suggested Vocabulary For Future Docs

- Semantic asset base.
- Semantic CI/CD.
- Candidate relation vs approved relation.
- Evidence packet.
- Review queue.
- Typed action intent.
- Governance feedback.
- Metric-ontology mapping.
- Action harness.
- Semantic todo.
