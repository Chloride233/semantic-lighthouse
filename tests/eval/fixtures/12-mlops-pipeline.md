---
title: MLOps数据管道设计
documentType: technical-guide
entityType: Concept
source: semantic-lighthouse-eval
status: published
---

# MLOps数据管道设计

MLOps数据管道将原始数据转为训练用格式化数据集。

组成：数据采集多源、数据验证完整性格式异常值、数据转换清洗标准化特征工程、数据存储。ETL vs ELT：ETL适合结构化数据，ELT适合大规模灵活处理。可靠性：重试机制、幂等性、质量监控告警。
