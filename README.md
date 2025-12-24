# Calliope - AI 分步式长篇写作智能体 (v6.0)

Calliope 是一个为专业创作者设计的 AI 写作工作站。它通过深度分层的 **Service-Oriented** 架构，将 **Hybrid RAG 2.0**、**故事时空年表**与**多重叙事宇宙**管理融为一体，旨在为长篇小说、深度报告提供逻辑严密、文风一致的创作环境。

## ✨ 核心特性

*   **双路混合检索 2.0 (Hybrid RAG)**:
    *   **分层记忆管理**: 独创“强记忆（近 3 章强制携带）+ 弱记忆（全书 RAG 召回）”机制，兼顾剧情连贯性与长线伏笔。
    *   **实体导向检索**: 自动识别场景实体，通过知识图谱邻域导航向量库，消除设定冲突。
    *   **覆盖式百科索引**: 确保世界观设定更新后即刻生效，不留冗余旧数据。
*   **智能时空年表 (Chronology & Timeline)**:
    *   **自动时空提取**: 每一章自动识别故事时间、地理位置及戏剧张力指数。
    *   **交互式年表**: 提供可视化故事脉络，支持手动修正 AI 提取的时间偏差。
    *   **时空过滤检索**: 支持“只参考 1990 年、发生在地堡内”的特定范围检索。
*   **设定管理中心 (World Bible 3.0)**:
    *   **三位一体编辑器**: 支持“文字描述、可视化关系网、交互式数据表”三种模式管理设定。
    *   **逻辑一致性哨兵**: 自动对比生成内容与图谱硬设定，实时预警逻辑冲突。
    *   **Leiden 派系识别**: 自动识别阵营，并由 AI 赋予具有文学感的派系名称。
*   **创作洞察 (Plot Analytics)**:
    *   **张力曲线图**: 可视化全书节奏，识别剧情平淡期与高潮点。
    *   **戏份热力图**: 统计各角色/实体的出现频率，平衡群像剧戏份。
*   **多重叙事宇宙 (Multi-Verse)**:
    *   **剧情分支管理**: 保存不同版本的剧情走向，支持一键切换存档点。
    *   **自动快照**: 关键步骤自动备份，安全感拉满。

## 🚀 技术架构

```text
[ UI Layer ]       Streamlit v6.0 Modular Components (Writer, Bible, Insights, Config)
      |
[ Service Layer ]  WritingService, KnowledgeService (Encapsulated Business Logic)
      |
[ Engine Layer ]   Hybrid RAG (ChromaDB + NetworkX), Leiden Algorithm
      |
[ AI Layer ]       LCEL Chains (One Step, One Model Configuration)
```

---
**License:** MIT