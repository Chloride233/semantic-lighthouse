"""One-shot generator for P3 eval seed documents."""

import os

BASE = "tests/eval/fixtures"
os.makedirs(BASE, exist_ok=True)

FIXTURES: dict[str, tuple[str, str, str]] = {
    "01-ontology-guide.md": (
        "企业Ontology设计指南",
        "Ontology是企业AI转型的核心基础设施，把分散的数据表、业务对象和关系抽象为统一的语义层。",
        "核心原则：业务语义优先、与现有数据解耦、可演进性、AI可读性。设计步骤：识别核心业务对象→定义关系→添加语义描述→验证。常见误区：把Ontology建成数据库镜像、过度建模。",
    ),
    "02-ai-roadmap.md": (
        "AI转型路线图方法论",
        "企业AI转型采用三阶段路线图：数据可访问与语义建模→AI增强决策与自动化→AI原生业务创新。",
        "第一阶段盘点数据资产构建Ontology部署知识库。第二阶段基于RAG实现企业问答建立反馈闭环。第三阶段引入Agent编排实现多步骤自动化对外提供AI服务。",
    ),
    "03-knowledge-graph.md": (
        "知识图谱构建实战",
        "知识图谱将实体概念和关系以图结构组织，使机器理解上下文并推理。",
        "实体识别提取命名实体。关系抽取确定belongs_to、employs、produces、competes_with。图数据库Neo4j适合复杂查询，PostgreSQL+Apache AGE提供图查询而不引入新数据库。",
    ),
    "04-rag-architecture.md": (
        "RAG检索增强生成技术架构",
        "RAG将信息检索与LLM结合，基于企业私有知识库生成准确可溯源的回答。",
        "架构：文档入库管道（上传解析分块向量化索引），检索模块（关键词ILIKE语义向量余弦混合），回答生成（LLM引用），可信度评估。关键技术：pgvector HNSW索引、混合检索加权去重、引用守卫防编造。",
    ),
    "05-data-governance.md": (
        "数据治理与数据资产化",
        "数据治理确保数据质量安全和合规，数据资产化将数据视为可增值的企业资产。",
        "治理框架：数据标准统一、数据血缘追踪、数据安全分级访问控制脱敏加密、数据合规GDPR。资产化路径：建立估值模型量化使用频次和业务效果。",
    ),
    "06-semantic-search.md": (
        "企业级语义搜索设计",
        "语义搜索超越关键词匹配，通过理解查询意图和文档语义提高检索质量。",
        "技术：向量化模型映射高维空间，pgvector是PostgreSQL原生扩展，HNSW索引加速近似最近邻搜索。混合策略合并关键词和语义结果去重排序。评测用Recall@k和MRR指标。",
    ),
    "07-llmops-practice.md": (
        "LLMOps运维实践",
        "LLMOps管理大语言模型从开发到生产的运维方法论。",
        "部署：自托管vs云API，模型路由按任务选模型，容器化。监控：Token消耗量、延迟P50/P95/P99、错误率、成本归因。运维：API密钥轮换、模型版本冻结与灰度升级。",
    ),
    "08-ai-maturity.md": (
        "企业AI成熟度评估模型",
        "AI成熟度评估帮助了解AI能力水平并规划提升路径。",
        "五等级：初始级实验→可重复级独立项目→已定义级共享基础设施→已管理级业务集成→优化级AI创新。评估维度：数据基础、技术能力、人才组织、价值交付。",
    ),
    "09-prompt-engineering.md": (
        "Prompt工程最佳实践",
        "Prompt工程设计LLM输入以获得高质量输出，好的Prompt显著提升RAG系统回答质量。",
        "核心：明确角色、提供约束、Few-shot示例、列出禁止项。RAG场景：system message设定角色格式，user message含问题和检索上下文，证据不足时明确说明。常见反模式：Prompt过长、英文Prompt处理中文场景。",
    ),
    "10-agent-architecture.md": (
        "多Agent协作架构",
        "Agent是能自主规划执行反思的AI系统，多Agent架构允许分工完成复杂任务。",
        "工作流：规划（分析目标分解子任务制定计划）→执行（调用工具收集观察更新进度）→总结（汇总结果生成最终回答）。工具安全：定义名称参数权限风险等级，高风险操作需用户确认。",
    ),
    "11-model-finetuning.md": (
        "模型微调与领域适配",
        "通用大模型在企业特定领域可能表现不佳，微调和RAG可增强领域能力。",
        "方法：全量微调效果好成本高、LoRA效率高适合多领域、QLoRA进一步降低资源。数据：收集问答对清洗格式划分训练验证测试集。评估：构建领域评测集对比微调与RAG成本效果比。",
    ),
    "12-mlops-pipeline.md": (
        "MLOps数据管道设计",
        "MLOps数据管道将原始数据转为训练用格式化数据集。",
        "组成：数据采集多源、数据验证完整性格式异常值、数据转换清洗标准化特征工程、数据存储。ETL vs ELT：ETL适合结构化数据，ELT适合大规模灵活处理。可靠性：重试机制、幂等性、质量监控告警。",
    ),
    "13-ai-security.md": (
        "AI安全与合规框架",
        "AI安全覆盖模型安全数据安全应用安全，合规确保满足法律法规。",
        "模型安全：Prompt注入防护输入过滤、输出内容安全有害检测、模型窃取防护API限流。数据安全：训练数据去敏移除PII、检索数据按租户隔离、日志脱敏。合规：数据跨境、算法备案透明度。",
    ),
    "14-model-evaluation.md": (
        "模型评估与评测体系",
        "模型评估是持续的质量保证，良好评测体系指导模型选型和优化方向。",
        "检索指标：Recall@k前k个结果含正确答案比例、MRR平均倒数排名、NDCG归一化折损累计增益、No Result Rate空结果比例。生成评测：引用准确性、答案忠实度、人工评估。评测集覆盖典型场景和边界情况。",
    ),
    "15-ai-cost-optimization.md": (
        "企业AI成本优化策略",
        "AI系统成本包括API调用基础设施人力运维，优化可提升AI投资ROI。",
        "模型选择：简单用轻量(Haiku)复杂用强力(Opus)，评估自托管替代付费API。Token优化：精简Prompt、截断检索上下文、缓存重复查询。基础设施：HNSW加速检索、合并小服务、合理配置资源限制。",
    ),
}

for filename, (title, abstract, body) in FIXTURES.items():
    content = (
        f"---\n"
        f"title: {title}\n"
        f"documentType: technical-guide\n"
        f"entityType: Concept\n"
        f"source: semantic-lighthouse-eval\n"
        f"status: published\n"
        f"---\n\n"
        f"# {title}\n\n{abstract}\n\n{body}\n"
    )
    with open(os.path.join(BASE, filename), "w", encoding="utf-8") as f:
        f.write(content)

print(f"Generated {len(FIXTURES)} fixture files in {BASE}")
