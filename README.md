# AI 分步式长篇写作智能体

这是一个基于大语言模型（LLM）的交互式写作助手原型，旨在模拟专业作家的分步骤工作流程，帮助用户从零开始构建高质量、高一致性的长篇内容。通过将复杂的写作任务分解为规划、研究、大纲、撰写和修订等多个阶段，本智能体旨在提升写作效率和内容质量。

## ✨ 特性

*   **完全可配置:** 通过 `config.yaml` 文件，可以轻松添加新的大模型，并为工作流的每一步自由分配模型，无需修改代码。
*   **多模型智能路由:** 根据不同任务的认知复杂度，动态选择最适合的LLM（如GPT-4o用于规划/修订，GPT-3.5-Turbo用于撰写初稿），平衡性能与成本。
*   **工具集成与管理:** 支持LangChain内置的多种工具（如Tavily Search, DuckDuckGo Search, Brave Search, Exa Search），并允许用户在UI上动态添加、配置和管理。
*   **在线研究集成:** 能够根据写作计划自动生成搜索查询，并利用可配置的搜索工具进行在线信息检索和摘要。
*   **迭代式撰写:** 逐节生成内容，用户可以查看每部分草稿并控制生成进度，为长篇写作提供更好的上下文管理。
*   **智能修订:** 使用最强大的LLM作为“总编辑”，对全文进行全面审阅和润色，确保内容的逻辑性、流畅性和风格一致性。
*   **交互式UI:** 基于Streamlit构建的直观Web界面，方便用户操作和查看各项成果。
*   **成果导出:** 支持将最终稿件一键导出为Markdown格式。

## 🚀 技术栈

*   **核心语言:** Python 3.9+
*   **配置文件:** YAML (`config.yaml`, `user_tools.yaml`, `provider_templates.yaml`, `tool_templates.yaml`)
*   **LLM 编排:** LangChain
*   **Web 界面:** Streamlit
*   **大模型:** OpenAI, Anthropic, Google, Ollama, Groq, Fireworks, MistralAI (通过动态配置支持更多兼容模型)
*   **外部工具:** Tavily Search, DuckDuckGo Search, Brave Search, Exa Search (通过动态配置支持更多)
*   **本地存储:** `st.session_state` (会话状态管理)

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

项目的核心行为由 `config.yaml` (模型配置), `user_tools.yaml` (工具配置) 和 `.env` (环境变量) 文件控制。

#### 4.1. 配置模型 (`config.yaml`)

这个文件是您定义和分配AI模型的地方。

*   **`models` 部分:** 在这里注册所有您想使用的模型实例。
    *   `template`: 模型使用的提供商模板ID (定义在 `provider_templates.yaml` 中)。
    *   `model_name` 或 `model`: 模型的API名称。
    *   `api_key_env`: (可选) 模型API密钥对应的环境变量名称。
    *   `base_url_env`: (可选) 模型URL对应的环境变量名称。

*   **`steps` 部分:** 在这里将项目工作流的每一步（如 `planner`, `drafter`）映射到上面定义的模型实例ID。

#### 4.2. 配置工具 (`user_tools.yaml`)

这个文件是您定义和管理工具实例的地方。

*   **`my_tool_id`:** 您为工具实例定义的唯一ID。
    *   `template`: 工具使用的模板ID (定义在 `tool_templates.yaml` 中)。
    *   `description`: (可选) 工具的描述，用于UI显示或Agent理解。
    *   `api_key_env`, `max_results` 等: 根据工具模板定义的参数进行填写。

#### 4.3. 设置环境变量 (`.env`)

1.  **创建 `.env` 文件:**
    在项目根目录下，将 `.env.example` 文件复制一份，并重命名为 `.env`。

2.  **编辑 `.env` 文件:**
    打开 `.env` 文件，为您在 `config.yaml` 或 `user_tools.yaml` 中配置的模型/工具所需要的所有环境变量填入实际值。

    ```
    # 示例:
    OPENAI_API_KEY="sk-..."
    ANTHROPIC_API_KEY="sk-ant-..."
    GOOGLE_API_KEY="AIzaSy..."
    TAVILY_API_KEY="tvly-..."
    BRAVE_API_KEY="your-brave-api-key" # Brave Search API Key
    EXA_API_KEY="your-exa-api-key" # Exa Search API Key
    
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
2.  **配置系统 (可选):** 在左侧边栏的“系统配置”区域，您可以进行配置：
    *   **步骤模型分配:** 为每个写作步骤（规划、研究、撰写等）从下拉菜单中选择一个已定义的模型。
    *   **模型实例管理:** 查看、添加、配置和管理您自己的模型实例。
    *   **工具实例管理:** 查看、添加、配置和管理您自己的工具实例。
3.  **保存配置:** 完成任何配置更改后，请务必点击相应的“保存”按钮。
4.  **分步执行:** 在主界面输入您的写作需求。然后，依次点击各步骤按钮，开始您的AI辅助创作之旅。
    *   **在“研究”步骤中**，您需要从下拉菜单中选择本次搜索要使用的**工具实例**。
    *   在“撰写”阶段，通过“准备撰写”按钮解析大纲，然后使用“撰写下一章节”按钮逐一生成内容。
5.  **完成与下载:** 全部章节撰写完毕后，点击“开始修订全文”进行最终润色，然后通过“下载最终稿件”按钮保存您的作品。

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
