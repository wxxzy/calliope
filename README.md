# Calliope - AI 分步式长篇写作智能体 (v7.0 Refactored)

Calliope 是一个为专业创作者设计的 AI 写作工作站。它采用 **领域驱动设计 (DDD)** 重构了底层架构，将 **Hybrid RAG 2.0**（混合检索）与 **World Bible**（设定圣经）深度集成，旨在解决长篇创作中“记忆遗忘”与“逻辑冲突”两大核心痛点。

## ✨ 核心特性

### 1. 深度写作工作流 (Deep Writing Workflow)
Calliope 不只是简单的聊天机器人，它遵循专业作家的创作流：
*   **灵感规划 (Plan)**: 交互式生成创作蓝图，支持自动网络研究 (Web Search) 补充背景资料。
*   **结构化大纲 (Outline)**: 基于计划生成层级分明的章节大纲，支持 AI 评审与迭代优化。
*   **沉浸式撰写 (Drafting)**: 
    *   **分层记忆 (Tiered Memory)**: 自动加载“强记忆”（近 3 章摘要）维持连贯性，并按需召回“弱记忆”（远期伏笔）。
    *   **上下文感知**: 写作时自动感知当前场景涉及的实体，从图谱中提取背景设定。
*   **总编级修订 (Revision)**: 全文写完后，由 AI 总编进行统一润色，修复文风不一致和逻辑漏洞。

### 2. 双路混合检索 2.0 (Hybrid RAG)
摒弃单一的向量检索，采用“向量 + 图谱”双引擎：
*   **向量检索 (Vector Store)**: 基于 ChromaDB，存储章节摘要、正文片段和百科设定。支持按时间、地点元数据过滤。
*   **知识图谱 (Knowledge Graph)**: 基于 NetworkX，存储人物、地点、物品之间的显性关系（如“A 是 B 的父亲”）。
*   **重排序 (Re-ranking)**: 集成 Cross-Encoder 模型，对召回的记忆片段进行语义重排，确保 AI 看到的上下文精准无误。

### 3. 设定管理中心 (World Bible)
让 AI 真正“记住”你的设定：
*   **动态图谱**: 支持从纯文本设定（如世界观文档）自动提取实体关系三元组，构建可视化关系网。
*   **逻辑一致性哨兵 (Consistency Sentinel)**: 实时监控生成的每一章内容，自动对比图谱中的硬设定（如“某人已死”、“某物在某地”），若发现冲突立即预警。
*   **交互式维护**: 提供可视化界面手动修正实体关系，或审核 AI 自动提取的新设定。

### 4. 模块化配置与架构
*   **模型无关性**: 通过 YAML 模板支持 OpenAI, Anthropic, Google, Ollama 等任意 LLM 后端。
*   **DDD 分层架构**: 清晰分离了基础设施 (`infra`)、领域核心 (`core`) 和业务服务 (`services`)，易于扩展和维护。

## 🚀 技术架构

```text
[ UI Layer ]       Streamlit (Writer, Bible, Config Views)
      |
[ Service Layer ]  WritingService, KnowledgeService (业务逻辑编排)
      |
[ Infra Layer ]    LLM Factory, VectorStore(Chroma), GraphStore(NetworkX)
      |
[ Config Center ]  YAML Configuration & Templates
```

## 📂 目录结构说明

```text
D:\workspace\Creative\20251208\
├── app.py                      # 应用程序启动入口
├── config/                     # 统一配置中心
│   ├── default.yaml            # 默认系统配置
│   ├── user_config.yaml        # 用户自定义配置 (模型、Prompt参数等)
│   └── templates/              # 工具与模型模板定义
├── core/                       # 领域核心定义
│   ├── schemas.py              # 强类型数据契约
│   └── exceptions.py           # 自定义异常体系
├── infra/                      # 基础设施层 (技术实现)
│   ├── llm/                    # LLM, Embedding, Reranker 工厂
│   ├── storage/                # ChromaDB 与 NetworkX 存储实现
│   └── tools/                  # 搜索工具与自定义函数
├── services/                   # 业务服务层
│   ├── writing_service.py      # 写作流程协调
│   └── knowledge_service.py    # 图谱构建与一致性检查
├── chains/                     # LangChain 编排层 (Prompt Chains)
└── ui_components/              # Streamlit 界面组件
```

## 🛠️ 快速开始

### 1. 环境准备
确保已安装 Python 3.10+

```bash
pip install -r requirements.txt
```

### 2. 配置模型
复制配置模板并编辑：

```bash
cp config/default.yaml.example config/user_config.yaml
```

在 `config/user_config.yaml` 中填入你的 API Key（支持 OpenAI, Anthropic 等）和偏好的模型名称。

### 3. 启动应用

```bash
streamlit run app.py
```

## ⚠️ 注意事项
*   **数据安全**: 项目采用本地文件存储（SQLite + JSON），请定期备份 `data/` 目录。
*   **Token 消耗**: 长篇写作涉及大量上下文读写，建议关注 API 使用量，或配置本地 LLM (Ollama) 以降低成本。

--- 
**License:** MIT
