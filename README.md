# Calliope - AI 分步式长篇写作智能体 (v5.0)

Calliope 是一个为专业创作者设计的 AI 写作工作站。它通过深度分层的 **Service-Oriented** 架构，将 **GraphRAG**、**多智能体协作**与**多重叙事宇宙**管理融为一体，旨在为长篇小说、深度报告提供逻辑严密、文风一致的创作环境。

## ✨ 核心特性

*   **深度解耦架构 (SoA)**:
    *   **UI 组件化**: 彻底拆分视觉逻辑，响应速度与可维护性大幅提升。
    *   **业务服务化**: `Writing`, `Knowledge`, `Project` 服务独立运作，支持一步一模型。
*   **智能灵感构思 (Bibled & Integrated)**:
    *   **一键构思**: 规划、并行搜索、知识持久化三位一体，自动沉淀研究资料。
    *   **圣经 2.0 (The Bible)**: 文字设定与图谱关系强实时同步，世界观更新即刻生效。
*   **双路混合检索 (Hybrid RAG 2.0)**:
    *   **实体导向检索**: 自动识别场上实体，通过图谱邻域（Leiden 算法）导航向量库召回。
    *   **逻辑一致性哨兵 (Sentinel)**: 自动审计生成内容，实时预警与既有图谱设定的逻辑冲突。
*   **侧边栏动态百科 (Live Widget)**:
    *   **场景感知**: 写作时自动浮现当前涉及的人物卡片、阵营立场及重要关联。
    *   **实时编辑**: 支持在写作界面直接修正图谱设定，无需中断灵感。
*   **多重叙事宇宙 (Multi-Verse)**:
    *   **剧情分支管理**: 支持保存“结局 A/B”等命名分支，一键切换平行时空进度。
    *   **自动快照**: 每一步关键创作均有时间戳备份，提供全方位的“后悔药”。
*   **专业级输出**:
    *   支持导出为 **Markdown**, **EPUB**, **PDF**（含中文字体支持与优化排版）。

## 🚀 技术架构

```text
[ UI Layer ]       Streamlit Components (Writer, Graph, Config, Explorer)
      |
[ Coord Layer ]    Workflow Manager (Facade & Routing)
      |
[ Service Layer ]  WritingService, KnowledgeService, ResearchService
      |
[ Chain Layer ]    LCEL Modular Chains (Chains/Writing, Chains/Knowledge, etc.)
      |
[ Storage Layer ]  Vector (ChromaDB), Graph (NetworkX), State (JSON)
```

## 📖 核心工作流

1.  **百科同步**: 更新设定，系统自动抽取三元组并划分派系（Leiden 算法）。
2.  **灵感构思**: 生成计划并自动进行全网背景研究，资料自动存入 RAG 库。
3.  **大纲/撰写**: AI 写手在“逻辑哨兵”的监督下创作，自动感知场上人物冲突。
4.  **分支实验**: 保存多个剧情分支，探索不同的叙事可能性。
5.  **一键成书**: 导出带目录和排版的电子书。

## 📝 待办清单 (Roadmap 5.0)

*   [x] **全系统模块化重构**: 实现 100% 逻辑与 UI 解耦。
*   [x] **Hybrid RAG 2.0**: 实现实体先导的混合检索。
*   [x] **逻辑一致性审计**: 部署实时剧情冲突预警系统。
*   [x] **剧情分支管理**: 实现命名的叙事版本控制。
*   [ ] **非线性时间轴管理**: 引入基于元数据的故事年表视图。
*   [ ] **自动剧情分析**: 可视化角色戏份占比与全书张力曲线。

---
**License:** MIT
