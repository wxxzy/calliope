# Calliope - AI 分步式长篇写作智能体

Calliope 是一个基于大语言模型（LLM）的交互式写作助手，专为长篇内容创作设计。它模拟专业作家的分步骤工作流程（规划 -> 研究 -> 大纲 -> 撰写 -> 修订），并利用先进的 **RAG（检索增强生成）** 技术和 **Re-ranking（重排序）** 机制，确保长篇故事或报告在逻辑、设定和文风上的高度一致性。

## ✨ 核心特性

*   **全流程写作工作流:** 将复杂的长篇写作拆解为独立且可控的阶段：
    *   **📋 规划 (Planner):** 分析需求，制定整体创作蓝图。
    *   **🔍 研究 (Researcher):** 集成 Tavily / Google Search，自动进行网络搜索并整理素材。
    *   **📝 大纲 (Outliner):** 生成结构化大纲，支持层级调整。
    *   **✍️ 撰写 (Drafter):** 逐章撰写，自动检索核心设定和前文摘要，拒绝“遗忘”和“幻觉”。
    *   **🎨 修订 (Refiner):** 全文润色，基于全书上下文优化文笔和连贯性。
*   **Writer-Critic 协作模式:** 
    *   内置“**AI 评论员 (Critic)**”角色，可在任意阶段（如大纲、章节草稿）被调用。
    *   评论员会从一致性、逻辑性、文笔风格等多个维度提供专业的编辑反馈。
    *   用户可以一键采纳评审意见，并将其作为“优化指令”自动触发内容重写，形成高效的“**写作-评审-修改**”闭环。
*   **高级 RAG 记忆系统:** 
    *   内置 **ChromaDB** 向量数据库，为每个项目建立独立的“世界观”和“剧情记忆”。
    *   **Re-ranking 重排序:** 集成 `sentence-transformers` Cross-Encoder，对检索到的上下文进行二次精排，确保 LLM 看到的永远是最相关的背景信息。
*   **本地与云端模型混用:** 
    *   支持 **OpenAI, Anthropic, Google Gemini** 等主流云端 API。
    *   深度集成 **Ollama**，支持本地运行 Llama 3, Mistral 等模型，并提供自动可用性检查。
*   **高度可配置架构:** 通过 YAML 配置文件 (`config.yaml`, `user_tools.yaml` 等) 动态管理模型、工具、切分器和重排序器，无需修改代码即可切换底层引擎。

## 🚀 技术栈

*   **核心框架:** Python 3.9+, LangChain (LCEL)
*   **Web 界面:** Streamlit
*   **向量数据库:** ChromaDB
*   **RAG 增强:** `sentence-transformers` (Cross-Encoder Re-ranking)
*   **工具集成:** Tavily API, Google Custom Search API
*   **配置管理:** YAML 驱动的依赖注入系统

## 🛠️ 安装与运行

### 1. 克隆项目

```bash
git clone https://github.com/wxxzy/calliope.git
cd calliope
```

### 2. 创建环境

推荐使用 Conda 或 venv：
```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 系统配置

项目依赖配置文件来决定使用哪些模型和工具。

#### 4.1. 环境变量 (.env)
复制模板并填入您的 API Key：
```bash
cp .env.example .env
```
编辑 `.env` 文件：
```ini
# 模型 API Keys
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."

# 搜索工具 Keys (可选)
TAVILY_API_KEY="tvly-..."
GOOGLE_SEARCH_API_KEY="..."
GOOGLE_SEARCH_CX="..."

# Ollama 配置 (如果使用本地模型)
OLLAMA_BASE_URL="http://localhost:11434"
```

#### 4.2. 核心配置 (config.yaml)
定义模型分配和 RAG 参数。您可以将不同的步骤分配给不同的模型（例如：用 GPT-4 做规划，用 Llama-3 本地模型做初稿撰写）。

#### 4.3. 工具配置 (user_tools.yaml)
启用或禁用搜索工具，配置工具参数。

### 5. 启动应用

```bash
streamlit run app.py
```
浏览器将自动打开 `http://localhost:8501`。

## 📖 使用指南

1.  **项目管理:** 在侧边栏创建新项目。所有进度和记忆都会自动持久化到 `data/project_states` 和 `data/chroma_db`。
2.  **设定世界观:** 在“核心记忆”区域输入小说的背景、人物小传或报告的核心论点。点击更新后，这些信息将被向量化并永久存储。
3.  **循序渐进:**
    *   **Step 1-3 (规划/研究/大纲):** 按顺序生成计划、研究摘要和文章大纲。在每个步骤下方，您都可以随时点击“**🔍 请求 AI 评审**”来获取反馈，或在“优化指令”框中手动输入指令来迭代优化。
    *   **Step 4 (撰写):** 点击“准备撰写”。AI 会逐章生成内容。**注意：** 此时系统会自动触发 RAG，从你的“核心记忆”和“已写章节”中检索相关信息，并使用重排序器优化上下文。
    *   **Step 4.5 (章节优化与评审):** 每完成一章，下方都会出现“**优化第 X 章**”区域。
        - **手动优化**: 在“本章优化指令”框中输入指令（如“这段对话写得更激烈些”），点击“**重写本章**”。
        - **AI 评审**: 点击“**🔍 请求 AI 评审**”获取反馈，然后点击“**🔧 采纳建议并重写本章**”，系统将自动执行优化。
    *   **Step 5 (修订):** 完成所有章节初稿后，AI 可以对全文进行润色，修复前后矛盾。

## 💡 进阶开发

*   **自定义重排序器:** 查看 `re_ranker_provider.py` 和 `re_ranker_templates.yaml`，您可以接入 BGE Reranker 或 Cohere Rerank。
*   **扩展工具:** 在 `tools.py` 中添加新的 LangChain Tool，并在 `user_tools.yaml` 中注册即可使用。

## 📝 待办清单 (Roadmap)

*   [x] **多智能体协作:** 引入“评论员”角色，在写作过程中实时提供反馈。
*   [ ] **非线性叙事支持:** 优化向量检索策略以支持倒叙、插叙等复杂结构。
*   [ ] **导出功能:** 支持导出为 PDF, EPUB 或 Markdown 格式。
*   [ ] **知识图谱:** 引入 GraphRAG 增强对复杂人物关系的理解。

---
**License:** MIT