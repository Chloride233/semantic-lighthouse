# V2 Learning Review

## Q26: Why use PostgreSQL keyword search before vector search?

### Question

Why does V2 start with PostgreSQL keyword search instead of vector search?

### Your Answer

> 都不清楚

### Engineering Review

This was an honest gap, and it is a useful one. The core distinction is not "keyword search is better than vector search." The distinction is that V2 needs to prove the document pipeline before adding semantic retrieval complexity.

Keyword search is easier to inspect: if a chunk is returned, the matching word is visible in the text. Vector search introduces embeddings, similarity thresholds, model choice, vector indexing, and retrieval evaluation. If the first retrieval version fails after adding all of that, it becomes hard to identify whether the failure is caused by parsing, chunking, permissions, embeddings, indexing, or ranking.

### Engineering Answer

V2 uses PostgreSQL keyword search first because the immediate goal is to verify document ingestion, chunking, source metadata, and `group_id` retrieval isolation. These are prerequisites for enterprise RAG. Vector search can improve semantic recall later, but it should be introduced after the permission and citation foundation is measurable.

### Interview Version

> I did not start V2 with vector search because the first risk was not semantic recall; it was whether the document pipeline was permission-safe and citation-ready. I used PostgreSQL keyword search to verify ingestion, chunking, source metadata, and `group_id` isolation first. Once that boundary is stable, adding embeddings and vector search becomes a controlled upgrade instead of a debugging black box.

## Q27: Is cross-group retrieval a serious bug even if the answer is correct?

### Question

If a user retrieves another group's document chunk, and the final answer is factually correct, is this still a serious bug? Why?

### Your Answer

> 这是重大事故。这是越权泄露问题，说明整个系统的权限管理隔离功能都失效了

### Engineering Review

This answer is correct and sharply stated. The next upgrade is to connect it to the retrieval layer specifically. In enterprise RAG, the security boundary is not only at the page or API level. The retrieval query itself must be permission-scoped, because retrieved chunks become model context and citations.

### Engineering Answer

Yes, this is a serious security bug. A correct answer can still be unauthorized if it was produced from documents the user is not allowed to access. Cross-group retrieval means the system has leaked knowledge across tenant or collaboration boundaries, and it means V1 group permissions were not successfully inherited by V2 document retrieval.

### Interview Version

> In enterprise RAG, correctness has two dimensions: factual correctness and permission correctness. If the answer uses or cites another group's document, it is still a security incident even when the text is factually right. That is why I enforce `group_id` on documents, chunks, and retrieval queries, not only on the outer API endpoint.

## Q28: Why store `group_id` on `document_chunks` too?

### Question

Why does `document_chunks` store `group_id` when it already has `document_id`, and the document already has `group_id`?

### Your Answer

> 一样的，group id是最后一道防线，是必须要有的

### Engineering Review

The direction is right: this is a defensive boundary. The engineering upgrade is to explain why the duplication is intentional. Retrieval often happens at the chunk level, especially in RAG. If chunk search can directly filter by `group_id`, the query does not depend entirely on a perfect join or later application filtering.

This also makes future retrieval code easier to audit: every query over retrievable chunks should visibly contain `DocumentChunk.group_id == group_id`.

### Engineering Answer

`document_chunks.group_id` is intentional denormalization for security and query clarity. Although the group can be reached through `documents`, chunks are the actual retrieval unit. Storing `group_id` on chunks lets the retrieval query enforce the permission boundary directly at the data layer and reduces the risk that a future query searches chunks without joining documents correctly.

### Interview Version

> I store `group_id` on both documents and chunks because chunks are the unit that RAG retrieves. This is deliberate denormalization for safety: retrieval SQL can filter chunks by group directly instead of relying only on a later document join or application-level check. It makes the permission boundary visible in the query that actually feeds model context.

## Q29: Why only support Markdown in V2?

### Question

Why does V2 only support Markdown instead of PDF or Word? Does that make the project look weak?

### Your Answer

> 目前的阶段是先把文档输入到文档检索的链条打通，存储格式问题并不是主要的

### Engineering Review

This is a good stage-aware answer. The key upgrade is to explain that Markdown is not only a simplification; it matches the real knowledge source. The ontology knowledge base is already Markdown with frontmatter, headings, and wikilinks, so Markdown lets V2 preserve structured metadata and source context.

PDF and Word support would introduce parsing quality, layout noise, file dependencies, and ambiguous chunk boundaries before the retrieval pipeline is stable.

### Engineering Answer

V2 supports Markdown only because the immediate goal is to verify the document retrieval chain: ingest, parse, chunk, store metadata, search, and enforce `group_id` isolation. Markdown is the best first format because the source knowledge base already uses Markdown structure. PDF and Word parsing are valuable later, but they would add format-processing complexity before the retrieval boundary is proven.

### Interview Version

> V2 is intentionally Markdown-only because the first goal is not broad file compatibility; it is to prove the retrieval pipeline. My source knowledge base is already Markdown with frontmatter, headings, and wikilinks, so Markdown preserves the metadata needed for citations and filtering. PDF and Word support can be added later after the permission-aware retrieval chain is stable.

## Q30: Why skip `INDEX.md`, `AUTO_INDEX.md`, `schema.md`, and `_TEMPLATE.md`?

### Question

Why does local import skip `INDEX.md`, `AUTO_INDEX.md`, `schema.md`, and `_TEMPLATE.md` even though these files also have content?

### Your Answer

> 考虑到后续的文件检索，这些index和schema对文件检索链条来说只是噪声，会增加文件检索的难度

### Engineering Review

This is correct. The refinement is that these files are not worthless; they are knowledge-base infrastructure. They help humans and scripts manage the knowledge base, but they are not business knowledge entities that should be retrieved as answers or citations.

If imported, they could dominate search results with index tables, schema rules, or templates instead of returning actual concepts, cases, methodologies, or proposals.

### Engineering Answer

V2 skips these files because they are infrastructure documents, not retrieval targets. The retrieval layer should prioritize reusable business knowledge entities. Importing indexes, schemas, and templates would pollute search results, produce weak citations, and make it harder to evaluate whether the system can retrieve the right knowledge asset.

### Interview Version

> I exclude index, schema, auto-index, and template files from V2 ingestion because they are knowledge-base infrastructure, not business knowledge. They are useful for maintaining the corpus, but if they enter retrieval, they add noise and can become poor citations. V2 should retrieve concepts, cases, methodologies, research, proposals, and FAQs, not the files that manage those entities.

## Q31: Why return citation fields with search results?

### Question

Why must V2 search results return `source_path`, `title`, and frontmatter fields instead of only returning chunk text?

### Your Answer

> 引用字段是追溯的第一证据

### Engineering Review

This is a strong concise answer. The engineering upgrade is to expand what traceability protects. Citation fields help users judge trust, help developers debug retrieval, help auditors verify permission boundaries, and give V3 RAG the data needed to cite sources rather than producing unsupported text.

### Engineering Answer

Search results need citation metadata because chunk text alone is not enough to evaluate reliability. `source_path` shows where the knowledge came from, `title` tells the user what document it belongs to, and frontmatter fields like `entityType`, `source`, and `status` help judge whether the result is a concept, case, methodology, draft, reviewed item, or lower-confidence source.

### Interview Version

> I return citation fields from V2 because retrieval should be traceable before it becomes RAG context. The chunk answers "what matched", but `source_path`, title, and frontmatter answer "where did this come from, what type of knowledge is it, and how trustworthy is it". This prepares V3 to produce cited answers instead of unsupported generated text.

## Q32: Why can only Owner/Admin upload documents?

### Question

Why does V2 allow only Owner/Admin to import or upload documents instead of allowing every Member to upload?

### Your Answer

> 一是防止用户乱上传文件增加系统压力。二是做好权限管理，明确管理者权力。

### Engineering Review

This is correct. The stronger engineering framing is that upload is a write operation that changes the shared knowledge base. It can affect other members' search results and future RAG answers, so it needs a higher permission level than reading or searching.

System pressure is also real, but the more important enterprise risk is knowledge pollution: low-quality, wrong, duplicated, or unauthorized content can enter the group corpus and become model context.

### Engineering Answer

Owner/Admin-only upload protects the integrity of the group knowledge base. Members can read and search, but importing documents changes shared retrieval behavior for everyone in the group. Restricting writes reduces accidental pollution, storage pressure, and future RAG answers based on unreviewed content.

### Interview Version

> I treat document upload as a privileged write operation, not a normal member action. Once a document enters the group corpus, it can affect search results and future RAG answers for the whole group. So V2 allows Members to retrieve, but only Owner/Admin can change the knowledge base. This controls both resource pressure and knowledge-quality risk.

## Q33: Why use `content_hash` for duplicate imports?

### Question

Why should duplicate import of the same document not create two document rows, and what does `content_hash` solve?

### Your Answer

> 创建两条记录对文件检索来说也只是噪声，没有实际意义，这里的hash确保了文档唯一性，是保护数据清洁的防线之一

### Engineering Review

This is a strong answer. The key addition is idempotency. Import jobs often need to be retried. If retrying creates duplicates, the same document can dominate search results, distort counts, and make citations confusing.

`content_hash` makes ingestion deterministic: the same group and same content map to the same logical document.

### Engineering Answer

Duplicate documents pollute retrieval and make the corpus harder to evaluate. `content_hash` lets the system detect that the same content already exists in the same group, so repeated imports become safe no-ops instead of creating duplicate searchable chunks. This protects corpus cleanliness and makes import retries safe.

### Interview Version

> I use `content_hash` to make document ingestion idempotent. Without it, retrying a local import or uploading the same Markdown twice would create duplicate chunks, add search noise, and confuse citations. The unique boundary is `group_id + content_hash`, so the same content can be reused safely inside one group without leaking across groups.

## Q34: Why use `group_id + content_hash` instead of global `content_hash` uniqueness?

### Question

Why is the unique constraint `group_id + content_hash` instead of global `content_hash`? If two groups upload the same document, why not share one document row?

### Your Answer

> 一是要保证权限分离，双重耦合的约束会更有效果，全局hash唯一太消耗资源。2用同一个文档这样会发生权限混淆问题，并且要接入不同的agent链路，从前到后都要区分。

### Engineering Review

The strongest part of this answer is the permission-separation intuition: same content does not mean same authorization boundary. The Agent-chain point is also important because future workflows may attach group-specific processing, citations, audit logs, and lifecycle state to the document.

One correction: avoiding global hash uniqueness is not mainly about resource consumption. It is about avoiding cross-group coupling. A global document row would make two groups share lifecycle, metadata, deletion, audit, and retrieval semantics unless an additional authorization mapping layer is introduced.

### Engineering Answer

The same file content can appear in multiple groups, but each group has its own permission boundary and document lifecycle. `group_id + content_hash` keeps ingestion idempotent inside a group while allowing another group to own its own copy of the same content. This avoids permission confusion and makes future retrieval, deletion, auditing, and Agent workflows group-scoped by default.

### Interview Version

> I use `group_id + content_hash` instead of global hash uniqueness because identical content does not imply identical permissions or lifecycle. Two groups may upload the same document, but their ownership, citations, deletion rules, and future Agent workflows should remain separate. This keeps idempotency inside each group without coupling groups through a shared document row.

## Q35: Why limit search result count?

### Question

Why does V2 search limit result count, for example to at most 50 rows, instead of returning every matching chunk?

### Your Answer

> 首先从架构承载能力上说，限制信息搜索数量是节省开支的方法，同时也是对承载能力的妥协，其次下游的大模型输入token量也是有限的，避免幻觉产生。

### Engineering Review

This is a strong systems answer. It correctly connects search volume with infrastructure cost and downstream LLM token limits. The refinement is that `limit` also protects latency and usability: users and models both need a bounded, ranked, inspectable result set rather than an unbounded dump.

One wording adjustment: limiting context does not directly "avoid hallucination" by itself, but it reduces noisy or irrelevant context that can make generation less grounded.

### Engineering Answer

Search limits protect database load, API latency, response size, and downstream LLM context windows. Returning all matches can overwhelm the user, increase cost, and send too much noisy context into future RAG prompts. A bounded result set keeps retrieval measurable and makes it easier to evaluate whether the top results are relevant and permission-correct.

### Interview Version

> I limit search results because retrieval is part of a larger system, not just a database query. Unbounded search can hurt database load, response latency, API payload size, and future LLM context cost. For RAG, the goal is not to return everything; it is to return a bounded, relevant, permission-safe set of chunks that can be inspected and cited.

## Q36: Why is keyword search not yet RAG?

### Question

Why does V2 keyword search not count as full RAG, and what changes in V3?

### Your Answer

> RAG是增强检索生成，现在只有检索没有其余链接大模型的生成

### Engineering Review

This answer is correct. V2 implements the retrieval foundation, but RAG requires generation grounded in retrieved context. The engineering upgrade is to describe the additional responsibilities between search and answer: selecting context, building prompts, enforcing citation rules, judging confidence, and reporting knowledge gaps.

### Engineering Answer

V2 is retrieval-only: it stores documents, searches chunks, and returns citation-ready results. V3 becomes RAG when the system uses retrieved chunks as controlled model context and generates a consulting-style answer with citations, confidence, knowledge gaps, and next-step suggestions.

### Interview Version

> V2 is not full RAG because it only solves the retrieval side. It can find permission-safe chunks and return citation metadata, but it does not yet assemble context for an LLM or generate an answer. V3 will add the generation layer: prompt construction, grounded answering, citations, confidence judgment, and knowledge-gap reporting.

## Q37: Why retest non-member access for document search?

### Question

Why does V2 need API tests proving non-members cannot search documents if V1 already tested that non-members cannot access groups?

### Your Answer

> 访问群组权限和成员越界权限控制是两码事

### Engineering Review

This is correct. The sharper framing is that every new group-scoped resource must prove it inherits the group boundary. V1 proves the group API is protected; it does not automatically prove V2 document routes call the same permission checks or filter queries correctly.

### Engineering Answer

V2 document search is a new access path to group data. Even if V1 group endpoints reject non-members, a new documents endpoint could accidentally skip membership checks or query chunks without `group_id`. Testing non-member search directly proves the retrieval layer itself enforces the boundary.

### Interview Version

> V1 proves the group endpoints are protected, but V2 introduces a new data access path: document retrieval. I test non-member document search separately because every new group-scoped resource must explicitly inherit the permission boundary. Otherwise the system could have secure group pages but insecure retrieval APIs.

## Q38: Why restrict local import to Owner/Admin?

### Question

Why does the local import endpoint require Owner/Admin permission if it only reads from the server-local `F:\ontology-kb` path instead of accepting user-uploaded files?

### Your Answer

> 便于以后扩展的代码复用，这是提前的规划

### Engineering Review

This answer captures one secondary benefit: consistent permission rules help future reuse. The more important point is that local import is still a write operation. It changes the group's searchable corpus and therefore changes what members and future RAG answers can retrieve.

Even if the source files are trusted, choosing to import them into a group is a privileged corpus-management action.

### Engineering Answer

Local import must require Owner/Admin because it writes documents and chunks into the group knowledge base. The risk is not only malicious upload; it is unauthorized corpus modification. A normal Member should not be able to change what the whole group can search or what future RAG answers can use as context.

### Interview Version

> I restrict local import to Owner/Admin because it is still a privileged write operation. The source path is server-local, but importing it changes the group's retrievable corpus and future RAG context. Members can search the corpus, but they should not decide what enters it. Keeping upload and local import under the same write-permission rule also makes the authorization model easier to audit and extend.

## Q39: Why not add document deletion in V2?

### Question

Why does V2 not implement a document deletion API? Is that an incomplete feature?

### Your Answer

> 为什么？我确实不知道

Follow-up reflection:

> 是的，这是我从来没想过的点

### Engineering Review

This was a new engineering-risk area. The important realization is that deletion is not just another CRUD button in an enterprise knowledge base. It affects auditability, historical citations, chunk cleanup, future vector index cleanup, and accidental data loss recovery.

### Engineering Answer

V2 does not implement deletion because the first goal is to prove ingestion, retrieval, citations, and permission isolation. Deletion belongs to document lifecycle management. A safe deletion design needs decisions about who can delete, whether deletion is soft or hard, how to preserve audit trails, how to handle historical RAG citations, and how to keep chunks and future vector indexes consistent.

### Interview Version

> I intentionally left document deletion out of V2 because deletion is not simple CRUD in an enterprise knowledge base. It affects audit logs, historical citations, chunk cleanup, future vector index consistency, and recovery from accidental deletion. V2 focuses on proving the permission-aware ingestion and retrieval loop first. When deletion is added, I would start with soft delete fields like `deleted_at` and `deleted_by`, and make every retrieval query exclude deleted documents.

## Q40: What happens if many retrieved chunks are irrelevant?

### Question

If V2 search returns 10 chunks, but 7 only match the keyword accidentally and are not relevant to the user question, what impact does that have on V3 RAG?

### Your Answer

> 首先在上下文注入中就注入了无效信息，增加了输入的噪声 其次会降低模型回答的质量 最后在审计环节也不好评估本次请求质量

### Engineering Review

This is a strong answer. It correctly connects retrieval noise to context quality, model output quality, and evaluation difficulty. The next concept to add is retrieval precision. RAG quality depends not only on whether the system can find something, but whether the top retrieved chunks are relevant enough to be used as model context.

### Engineering Answer

Irrelevant chunks reduce retrieval precision. In V3, those chunks would enter the prompt as noisy context, making the model more likely to produce vague, distracted, or poorly cited answers. They also make debugging and auditing harder because it becomes unclear whether the answer failed due to retrieval quality, prompt construction, or model behavior.

### Interview Version

> Noisy retrieval directly harms RAG because retrieved chunks become model context. If most top chunks are only keyword matches and not actually relevant, the prompt contains noise, answer quality drops, citations become weaker, and evaluation becomes harder. That is why V2's keyword search is only the baseline; V3 will need better query planning, ranking, and possibly hybrid retrieval.

## Q41: Why return chunks instead of whole documents?

### Question

Why does V2 search return chunks instead of returning the entire document?

### Your Answer

> 这个不清楚

### Engineering Review

This is a core RAG concept. A document is usually the management unit, but a chunk is the retrieval unit. Returning the full document makes the context too large, too noisy, and too hard to cite precisely. Returning chunks gives the system smaller, inspectable units that can be ranked, cited, and passed into an LLM context window.

### Engineering Answer

V2 returns chunks because RAG needs fine-grained, relevant context. A whole document can contain many unrelated sections, while a chunk should represent a smaller passage around a specific topic or heading. Chunk-level retrieval improves relevance, controls token cost, supports precise citations, and makes retrieval evaluation easier.

### Interview Version

> In my design, `documents` are the corpus management unit, while `document_chunks` are the retrieval unit. RAG should not pass entire documents to the model by default because they are too long and noisy. Chunk retrieval gives the model a smaller, more relevant context and lets the system cite the exact passage that supported the answer.

## Q42: Why chunk by Markdown headings?

### Question

The current project chunks Markdown by headings instead of fixed character count. What are the advantages and disadvantages?

### Your Answer

> 我这个ontology本来就是经过各种切分之后的，有各种实例和case，检索方式某种意义上已经架构了。每个markdown都是经过架构加工后的文档，所以检索会更加方便。3内容特别长会让chunk特别长，影响上下文和检索进度，同样特别短也不行。5在引入其余格式文件和大文件的计划敲定之后再更改

### Engineering Review

This is a good answer. The strongest point is that the source corpus is already structured. Markdown headings represent human-designed semantic boundaries, so using them as chunk boundaries preserves the knowledge author's organization.

The tradeoff needs sharper wording. Very long sections produce chunks that are too large for efficient retrieval and LLM context. Very short sections may lack enough surrounding context to be useful. A later hybrid strategy can keep heading boundaries but split oversized sections further.

### Engineering Answer

Heading-based chunking fits `ontology-kb` because the Markdown files are already curated knowledge assets with titles, sections, cases, and examples. It makes chunks easier to cite and explain because each chunk carries a heading path. The weakness is uneven chunk size: long sections may be too broad, while short sections may be too thin. When the corpus expands to long files or non-Markdown formats, the system should evolve to heading-aware chunking plus max-size splitting and optional overlap.

### Interview Version

> I chose heading-based chunking because my source corpus is not raw text; it is an organized Markdown knowledge base. Headings preserve the author's semantic boundaries and make citations more explainable through `heading_path`. The tradeoff is uneven chunk size. If sections become too long or too short, I would upgrade to a hybrid strategy: keep heading boundaries, but split oversized sections by token length with overlap.

## Q43: Why can an overly short chunk be weak for RAG?

### Question

If a chunk only says "Ontology is the enterprise semantic layer", why might that be insufficient for RAG?

### Your Answer

> 首先是信息太少，注入上下文对模型回答正确内容基本上没有帮助。

### Engineering Review

This is correct. A short chunk may match a keyword, but it may not contain enough explanation, evidence, examples, or boundaries to support a grounded answer. RAG context should not only be relevant; it should be sufficient.

### Engineering Answer

An overly short chunk can be low-value context. It may contain the keyword but lack definition, reasoning, examples, or contrast with related concepts. If passed to the LLM, it gives little evidence for a consulting-style answer and can lead to vague or unsupported generation.

### Interview Version

> A chunk can be too small to be useful. Even if it matches the query, one sentence may not provide enough context, evidence, or examples for the model to generate a grounded answer. For RAG, retrieved chunks need both relevance and sufficiency; otherwise the citation exists, but it does not really support the answer.

## Q44: Why can an overly long chunk be weak for RAG?

### Question

If a chunk contains around 3000 Chinese characters, why might that be bad for RAG?

### Your Answer

> 会影响rag的检索精度，同时过大的上下文注入也会影响llm的回答判断

### Engineering Review

This is correct. A long chunk can contain the answer, but it also carries a lot of unrelated context. This lowers retrieval precision and makes the LLM process more noise. The additional points are token cost and citation granularity.

### Engineering Answer

Overly long chunks reduce precision because a match may be caused by a small part of a large passage. Passing the whole chunk into the LLM increases token cost and can distract the model with unrelated material. Long chunks also make citations less precise because the cited passage is too broad.

### Interview Version

> A chunk that is too long hurts both retrieval and generation. It may match the query because of one sentence, but the rest of the chunk becomes noise in the prompt. That increases token cost, lowers answer focus, and makes citations less precise. Good chunking balances enough context with a tight evidence boundary.

## Q45: How do we know a chunking strategy improved?

### Question

If the chunking strategy is optimized later, what metrics should determine whether it actually improved instead of only feeling better?

### Your Answer

> 这个在不同架构有不同的方案吧 目前我确实不知道对应的优秀方案

### Engineering Review

This is an honest gap. The direction is right that evaluation depends on architecture, but even a small project needs minimum measurable signals. For Semantic Lighthouse, chunking should be evaluated by retrieval quality, citation usefulness, context cost, and unchanged permission safety.

### Engineering Answer

A practical first evaluation set can contain 20 typical questions with manually marked expected documents or chunks. Then compare `Recall@K`, `Precision@K`, citation usability, average chunk length, Top-K token cost, and permission isolation tests. This keeps optimization tied to evidence rather than subjective preference.

### Interview Version

> I would not judge chunking by intuition. I would create a small evaluation set of representative questions, label expected documents or chunks, and compare Recall@K, Precision@K, citation usefulness, and context token cost. I would also keep permission tests running, because a retrieval optimization is not acceptable if it breaks `group_id` isolation.

## Q46: Why is returning more chunks not necessarily better?

### Question

If an old strategy returns 5 chunks for "Ontology" and a new strategy returns 30 chunks, why can't we directly say the new strategy is better?

### Your Answer

> 首先在没有质量判断指标的情况下返回的chunk质量未知，数量相对来说没有参考意义。返回的chunk太多也会使得上下文拥挤，影响llm输出，对用户审阅与引用会变得更加混乱。指标我认为要按最有价值的，比如召回率。

### Engineering Review

This is a strong answer. More results can mean better recall, but it can also mean more noise. The key refinement is that recall should be evaluated together with precision. A retrieval system that returns everything may have high recall but poor precision, which is bad for RAG context quality.

### Engineering Answer

Returning more chunks is not automatically better because quantity does not prove relevance. Too many chunks increase review burden, prompt noise, token cost, and citation confusion. Evaluation should compare whether the top results contain the needed evidence and how much irrelevant content is mixed in, using metrics like Recall@K, Precision@K, citation usability, and context token cost.

### Interview Version

> I would not treat more retrieved chunks as better by default. More results may improve recall, but they can also lower precision and pollute the LLM context. For RAG, the useful question is whether the top-K chunks contain enough relevant, citeable, permission-safe evidence with limited noise. So I would evaluate both Recall@K and Precision@K, plus citation usefulness and token cost.

## Q47: Why preserve wikilinks without parsing them into graph relations?

### Question

Why does V2 preserve Obsidian wikilinks like `[[concepts/ontology]]` as text instead of expanding them into knowledge graph relations?

### Your Answer

> 关系解析应该是v3才要考虑的部分吧

### Engineering Review

This is close, but the version boundary should be sharper. V3's main goal is RAG generation, while wikilink graph parsing is more like a V2.x retrieval enhancement or a V4 Agent/graph capability. V2 should preserve the raw link text so the information is not lost, but avoid adding relationship extraction before the basic retrieval loop is stable.

### Engineering Answer

Preserving wikilinks is reasonable because they carry useful relationship hints. Not parsing them yet is also reasonable because graph relation extraction introduces entity resolution, link normalization, broken-link handling, graph schema decisions, and new query behavior. V2's job is to prove document ingestion, chunk retrieval, citations, and permissions first.

### Interview Version

> In V2 I preserve wikilinks but do not parse them into graph relations yet. Wikilinks are valuable semantic hints, so I keep them in the chunk text. But turning them into graph edges requires entity resolution, schema decisions, broken-link handling, and graph query design. I would add that after the basic permission-aware retrieval loop is stable, likely as a V2.x retrieval enhancement or before Agent workflows.

## Q48: What is the first step for wikilink graph parsing?

### Question

If wikilinks are later parsed into graph relations, should the first step be a graph database?

### Your Answer

> 我不了解图谱架构如何建立

### Engineering Review

This was an honest gap. The key principle is that a graph capability should start with reliable relation extraction, not immediately with specialized infrastructure. For this project, PostgreSQL can store a first `document_links` table and keep `group_id` isolation before introducing a graph database.

### Engineering Answer

The first step should be extracting and storing verifiable link edges, such as `source_chunk_id -> target_path`, while preserving `group_id`. A graph database is only justified after the project has real graph-query needs. Before that, a relational table is easier to test, migrate, audit, and explain.

### Interview Version

> I would not start wikilink parsing by adding Neo4j. I would first create a lightweight relational edge table in PostgreSQL, such as `source_document_id/source_chunk_id -> target_path`, and keep `group_id` on every edge. That lets me validate link extraction, target resolution, and permission isolation before deciding whether a graph database is actually needed.

## Q49: Why is one successful import/search not enough for V2 usability?

### Question

Why does "one successful import and search" not mean V2 is usable?

### Your Answer

> 压力测试，链路可持续性测试，健壮性测试，权限保护测试，最后一个不知道

### Engineering Review

This answer contains several important engineering instincts: robustness, sustainable flow, and permission protection. The refinement is that V2's current priority is not large-scale pressure testing yet. The more immediate usability evidence is idempotency, negative permission tests, cross-group isolation, migration, and API discoverability.

Migration and OpenAPI matter because a feature is not only code. It must be upgradeable through the database version chain and discoverable/debuggable through the API surface.

### Engineering Answer

One happy-path run only proves the simplest path works once. V2 usability requires proof that repeated imports do not duplicate data, non-members cannot search, cross-group search cannot leak chunks, migrations can upgrade the database schema, and OpenAPI exposes the document endpoints for manual verification and demo.

### Interview Version

> V2 usable does not mean import and search succeeded once. I verify the critical failure paths: duplicate import must be idempotent, non-members and cross-group searches must fail, migrations must upgrade the real schema, and OpenAPI must expose the endpoints for debugging and demonstration. At this stage, permission correctness and iterability matter more than premature large-scale pressure testing.

## Q50: Why is document status directly `ready` in V2?

### Question

Why does V2 set imported Markdown documents directly to `ready` instead of using a complex state machine like `uploaded -> parsing -> chunked -> indexed -> ready -> failed`?

### Your Answer

> 不知道

### Engineering Review

This is a good example of avoiding premature complexity. V2 ingestion is synchronous: read Markdown, parse frontmatter, create chunks, write database rows, and return. There is no object storage, OCR, embedding job, vector index, or async worker yet, so a large state machine would create more code paths than the current system needs.

The important compromise is that V2 still keeps a `status` field. That preserves an expansion point without forcing the whole async lifecycle early.

### Engineering Answer

V2 can mark documents as `ready` because successful ingestion means the document is already searchable. A complex status flow becomes necessary when ingestion has long-running or failure-prone stages, such as MinIO upload, PDF parsing, OCR, embeddings, vector indexing, retries, or user-visible processing status. Until then, a simple `ready` status is easier to test and explain.

### Interview Version

> V2 uses `ready` directly because Markdown ingestion is synchronous and completes inside one request. I did not add a full ingestion state machine before introducing async parsing, embeddings, or vector indexing. But I kept a `status` field so the model can evolve later into `uploaded/parsing/indexed/ready/failed` when the pipeline actually needs it.

## Q51: Why store frontmatter as structured metadata?

### Question

Why does V2 store Markdown frontmatter as a structured database field instead of only keeping it inside the raw Markdown text?

### Your Answer

> 不清楚

### Engineering Review

This is an important knowledge-modeling point. Frontmatter is not just document decoration. In this project, fields like `entityType`, `source`, and `status` describe the type, evidence strength, and maturity of a knowledge asset.

Storing frontmatter structurally makes it queryable and reusable without reparsing Markdown on every request.

### Engineering Answer

Structured frontmatter supports filtering, ranking, citation display, and future confidence judgment. `entityType` helps distinguish concepts, cases, methodologies, and FAQs. `source` and `status` help judge evidence strength and maturity. Keeping these fields only inside raw Markdown would make retrieval and RAG behavior harder to query, test, and explain.

### Interview Version

> I store frontmatter structurally because it is metadata, not just text. `entityType` tells the system what kind of knowledge asset this is, while `source` and `status` support trust and maturity judgments. This prepares V3 to filter, rank, cite, and explain answers based on metadata instead of reparsing raw Markdown every time.

## Q52: Why not treat all retrieved chunks as equally trustworthy?

### Question

If V3 retrieves one chunk from `official-doc + reviewed` and another from `personal-analysis + draft`, why should they not be treated as equally trustworthy?

### Your Answer

> 来源直接决定文档可信度和可追溯性，成熟度直接影响回答质量，剩下不知道

### Engineering Review

This answer correctly identifies the two main metadata signals: source and maturity. The missing piece is how the system should behave with lower-confidence material. It should not necessarily discard it, but it should label it as weaker evidence, avoid overclaiming, and surface uncertainty.

### Engineering Answer

Different sources and maturity levels represent different evidence strength. `official-doc + reviewed` can support stronger claims. `personal-analysis + draft` may be useful as context or hypothesis, but it should be treated as lower-confidence evidence. V3 should reflect that in confidence judgment, wording, and citations.

### Interview Version

> I do not treat all retrieved chunks as equal evidence. Official or reviewed material can support stronger claims, while draft personal analysis should be framed as lower-confidence context. In a consulting-style answer, the system should cite both if useful, but it should communicate uncertainty and avoid presenting draft analysis as verified fact.

## Q53: What should happen when retrieval evidence is insufficient?

### Question

If retrieved chunks are not enough to answer the user's question, should the system force the model to generate an answer?

### Your Answer

> 采取一些折中的方案，提供一个相对模糊的概念性答案，但是得让用户知道来源不足。

### Engineering Review

This is a good direction. The system can provide limited help, but it must not pretend the evidence is sufficient. The stronger framing is to separate supported answer, uncertainty, knowledge gaps, and next steps.

### Engineering Answer

The system should not force a confident answer from insufficient evidence. It can provide a limited conceptual response if safe, but it should explicitly state that the current knowledge base does not contain enough supporting evidence, list the missing information, and recommend next steps such as adding documents, refining the query, or asking a narrower question.

### Interview Version

> If retrieval is insufficient, I would not let the model hallucinate a confident answer. I would return a bounded response: what can be said from the retrieved evidence, what remains uncertain, what knowledge gaps exist, and what next information is needed. For an enterprise RAG system, saying "I don't have enough evidence" is safer than producing an unsupported consulting recommendation.

## Q54: Why should V3 answers include knowledge gaps?

### Question

Why should V3 include a "knowledge gaps" field instead of behaving like a normal chatbot that directly answers?

### Your Answer

> 我们做的相当于一个知识顾问，客户有对回答质量的知情权。

### Engineering Review

This is an excellent product and trust framing. The knowledge-gap field is not just a technical artifact; it is part of the consulting contract. It tells the user where the answer is supported and where the system lacks evidence.

### Engineering Answer

Knowledge gaps make the answer auditable and honest. In enterprise consulting, a recommendation can affect business decisions, so the system should disclose missing evidence, weak assumptions, and information needed for a better answer. This helps users trust the system without overtrusting it.

### Interview Version

> Semantic Lighthouse is closer to a knowledge consultant than a casual chatbot. The user has a right to know the quality boundary of the answer. I include knowledge gaps so the system can say what it knows, what it does not know, and what evidence is missing before making stronger recommendations. This reduces overconfidence and makes the answer more useful for business decision-making.
