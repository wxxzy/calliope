# AI 分步式长篇写作智能体

这是一个基于大语言模型（LLM）的交互式写作助手原型，旨在模拟专业作家的分步骤工作流程，帮助用户从零开始构建高质量、高一致性的长篇内容。通过将复杂的写作任务分解为规划、研究、大纲、撰写和修订等多个阶段，本智能体旨在提升写作效率和内容质量。

## ✨ 特性

*   **记忆系统 / RAG:** 通过集成的ChromaDB向量数据库，为每个写作项目创建独立的“记忆库”。能够索引“世界观”和已完成的章节，并在后续的撰写和修订中智能检索相关上下文，极大地提升了长篇内容的一致性。
*   **完全可配置:** 用户可以在UI上动态配置和管理模型、工具和文本切分器，系统会根据`config.yaml`, `user_tools.yaml`等配置文件动态加载。
*   **多模型与多工具:** 支持并预置了多种主流LLM提供商（OpenAI, Google, Anthropic, Ollama等）和搜索工具（Tavily, Brave, DuckDuckGo等）的模板。

## 🚀 技术栈

*   **核心语言:** Python 3.9+
*   **配置文件:** YAML
*   **LLM 编排:** LangChain
*   **Web 界面:** Streamlit
*   **向量数据库:** ChromaDB (用于RAG)
*   **文本切分:** `langchain-text-splitters`, `sentence-transformers`

## 🛠️ 安装与运行

请按照以下步骤在您的本地环境中设置并运行项目。

### 1. 克隆项目 (如果适用)

如果您从代码仓库获取此项目，请先克隆它：
```bash
# git clone <repository_url>
# cd <project_directory>
```

### 2. 创建并激活虚拟环境 (推荐)

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

### 4. 系统配置 (核心步骤)

项目的核心行为由 `config.yaml` (模型配置), `user_tools.yaml` (工具配置), `user_text_splitters.yaml` (切分器配置) 和 `.env` (环境变量) 文件控制。

#### 4.1. 配置模型 (`config.yaml`)

这个文件是您定义和分配AI模型的地方。

*   **`models` 部分:** 在这里注册所有您想使用的模型实例。
    *   `template`: 模型使用的提供商模板ID (定义在 `provider_templates.yaml` 中)。
    *   `model_name` 或 `model`: 模型的API名称。
    *   `api_key_env`: (可选) 模型API密钥对应的环境变量名称。
    *   `base_url_env`: (可选) 模型URL对应的环境变量名称。

*   **`steps` 部分:** 在这里将项目工作流的每一步（如 `planner`, `drafter`）映射到上面定义的模型实例ID。

*   **`embeddings` 部分:** 在这里注册所有您想使用的Embedding模型实例。
    *   **`active_embedding_model`:** 指定当前激活的Embedding模型实例ID。

**示例: 如何使用本地HuggingFace模型作为Embedding?**
1.  确保 `sentence-transformers` 已安装 (已在`requirements.txt`中)。
2.  在 `config.yaml` 的 `embeddings` 部分添加一个新实例:
    ```yaml
    my_local_embedding:
      template: "huggingface"
      model_name: "BAAI/bge-small-zh-v1.5" # 一个优秀的中文模型
    ```
3.  将 `active_embedding_model` 设置为 `my_local_embedding`。
    *   **注意:** 首次使用时，`sentence-transformers` 会自动从Hugging Face Hub下载模型，这可能需要一些时间。

#### 4.2. 配置工具 (`user_tools.yaml`)

这个文件是您定义和管理工具实例的地方。

*   **`my_tool_id`:** 您为工具实例定义的唯一ID。
    *   `template`: 工具使用的模板ID (定义在 `tool_templates.yaml` 中)。
    *   `description`: (可选) 工具的描述，用于UI显示或Agent理解。
    *   `api_key_env`, `max_results` 等: 根据工具模板定义的参数进行填写。

#### 4.3. 配置文本切分器 (`user_text_splitters.yaml`)

这个文件是您定义和管理文本切分器实例的地方。

*   **`my_splitter_id`:** 您为切分器实例定义的唯一ID。
    *   `template`: 切分器使用的模板ID (定义在 `text_splitter_templates.yaml` 中)。
    *   `description`: (可选) 切分器的描述，用于UI显示。
    *   `chunk_size`, `chunk_overlap` 等: 根据切分器模板定义的参数进行填写。

#### 4.4. 设置环境变量 (`.env`)

1.  **创建 `.env` 文件:**
    在项目根目录下，将 `.env.example` 文件复制一份，并重命名为 `.env`。

2.  **编辑 `.env` 文件:**
    打开 `.env` 文件，为您在 `config.yaml` 或 `user_tools.yaml` 中配置的模型/工具所需要的所有环境变量填入实际值。

    ```
    # 示例:
    OPENAI_API_KEY="sk-..."
    ANTHROPIC_API_KEY="sk-ant-..."
    GOOGLE_API_KEY="AIzaSy..." # Google LLM 和 Embedding 模型共用此密钥
    TAVILY_API_KEY="tvly-..."
    BRAVE_API_KEY="your-brave-api-key" # Brave Search API Key (如果使用Brave Search)
    EXA_API_KEY="your-exa-api-key" # Exa Search API Key (如果使用Exa Search)
    
    # 火山方舟豆包模型 (OpenAI 兼容)
    DOUBAO_CUSTOM_API_KEY="your-doubao-api-key"
    DOUBAO_CUSTOM_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"

    # Ollama 本地模型 (可选)
    OLLAMA_BASE_URL="http://localhost:11434" # 默认地址
    
    # Google Custom Search API (可选)
    GOOGLE_SEARCH_API_KEY="your-google-search-api-key"
    GOOGLE_SEARCH_CX="your-custom-search-engine-id"
    ```

### 5. 启动应用

在您激活的虚拟环境中，运行以下命令启动Streamlit应用：
```bash
streamlit run app.py
```
您的默认浏览器会自动打开一个新页面，显示AI写作智能体的用户界面。

## ✍️ 使用指南

1.  **打开应用:** 运行 `streamlit run app.py` 启动Web界面。
2.  **创建项目:** 在左侧边栏输入一个新项目的名称，点击“创建新项目”。每个项目都有自己独立的记忆库。
3.  **配置系统 (可选):** 在侧边栏的“系统配置”区域，您可以进行配置：
    *   **步骤模型分配:** 为每个写作步骤（规划、研究、撰写等）从下拉菜单中选择一个已定义的模型。
    *   **模型/工具/切分器实例管理:** 查看、添加、配置和管理您自己的模型、工具和文本切分器实例。
4.  **保存配置:** 完成任何配置更改后，请务必点击相应的“保存”按钮。
5.  **分步执行:**
    *   **更新核心记忆:** 在主界面的“核心记忆 (世界观)”文本框中，输入您作品的核心设定，然后点击“更新核心记忆”。
    *   **规划:** 输入整体写作需求，生成计划。
    *   **研究:** 选择一个搜索工具，进行在线研究。
    *   **大纲:** 生成文章的结构大纲。
    *   **撰写 (RAG增强):** 点击“准备撰写”解析大纲，然后逐一点击“撰写章节”。在这一步，AI会**自动检索**核心记忆和已写章节的内容，以保证上下文连贯。每完成一章，该章节也会被自动存入记忆库。
    *   **修订 (RAG增强):** 初稿完成后，点击“开始修订全文”。AI“总编辑”会**自动检索**全文最相关的上下文，进行一次保证全局一致性的深度润色。
6.  **完成与下载:** 最终稿件生成后，点击“下载最终稿件”按钮保存您的作品。

## 💡 未来可能的增强功能

*   **RAG (检索增强生成) 模块:** 整合向量数据库（如ChromaDB），以更智能地管理上下文和长篇内容的一致性。
*   **用户反馈与迭代:** 允许用户在每一步对AI的输出进行修改和反馈，从而引导后续创作。
*   **更多工具集成:** 例如图片生成、图表生成工具。
*   **保存/加载项目:** 实现写作项目的持久化存储。
*   **更复杂的大纲解析:** 提升从Markdown大纲中提取结构的能力。

---
**License:** (可选，例如 MIT License)
```
MIT License

Copyright (c) [Year] [Your Name/Organization]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```