# AI 分步式长篇写作智能体

这是一个基于大语言模型（LLM）的交互式写作助手原型，旨在模拟专业作家的分步骤工作流程，帮助用户从零开始构建高质量、高一致性的长篇内容。通过将复杂的写作任务分解为规划、研究、大纲、撰写和修订等多个阶段，本智能体旨在提升写作效率和内容质量。

## ✨ 特性

*   **完全可配置:** 通过 `config.yaml` 文件，可以轻松添加新的大模型，并为工作流的每一步自由分配模型，无需修改代码。
*   **多模型智能路由:** 根据不同任务的认知复杂度，动态选择最适合的LLM（如GPT-4o用于规划/修订，GPT-3.5-Turbo用于撰写初稿），平衡性能与成本。
*   **在线研究集成:** 能够根据写作计划自动生成搜索查询，并利用Tavily AI或Google Custom Search API进行在线信息检索和摘要。
*   **迭代式撰写:** 逐节生成内容，用户可以查看每部分草稿并控制生成进度，为长篇写作提供更好的上下文管理。
*   **智能修订:** 使用最强大的LLM作为“总编辑”，对全文进行全面审阅和润色，确保内容的逻辑性、流畅性和风格一致性。
*   **交互式UI:** 基于Streamlit构建的直观Web界面，方便用户操作和查看各项成果。
*   **成果导出:** 支持将最终稿件一键导出为Markdown格式。

## 🚀 技术栈

*   **核心语言:** Python 3.9+
*   **配置文件:** YAML (`config.yaml`)
*   **LLM 编排:** LangChain
*   **Web 界面:** Streamlit
*   **大模型:** OpenAI, Anthropic, Google, 及任何兼容OpenAI API的自定义模型
*   **外部工具:** Tavily AI API / Google Custom Search API (用于Web搜索)
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

项目的核心行为由 `config.yaml` 和 `.env` 两个文件控制。

#### 4.1. 配置模型 (`config.yaml`)

这个文件是您定义和分配AI模型的地方。

*   **`models` 部分:** 在这里注册所有您想使用的模型。
    *   `provider`: 支持 `openai`, `anthropic`, `google`, `openai_compatible`。
    *   `model_name`: 模型的API名称。
    *   `api_key_env`: (可选) 模型API密钥对应的环境变量名称。
    *   `base_url_env`: (仅 `openai_compatible` 需要) 模型URL对应的环境变量名称。

*   **`steps` 部分:** 在这里将工作流的每一步（如 `planner`, `drafter`）分配给上面定义的一个模型ID。

**示例: 如何添加一个新的兼容模型并使用它?**
1.  在 `models` 部分添加您的模型定义:
    ```yaml
    my_new_model:
      provider: "openai_compatible"
      model_name: "some-model-name-v1"
      api_key_env: "MY_NEW_MODEL_API_KEY"
      base_url_env: "MY_NEW_MODEL_BASE_URL"
    ```
2.  在 `steps` 部分将 `drafter` (写手) 指向它:
    ```yaml
    steps:
      # ... 其他步骤
      drafter: "my_new_model"
    ```
3.  确保在下一步的 `.env` 文件中定义了 `MY_NEW_MODEL_API_KEY` 和 `MY_NEW_MODEL_BASE_URL`。

#### 4.2. 设置环境变量 (`.env`)

1.  **创建 `.env` 文件:**
    在项目根目录下，将 `.env.example` 文件复制一份，并重命名为 `.env`。

2.  **编辑 `.env` 文件:**
    打开 `.env` 文件，为您在 `config.yaml` 中配置的模型所需要的环境变量填入实际值。
    ```
    # 示例:
    OPENAI_API_KEY="sk-..."
    ANTHROPIC_API_KEY="sk-ant-..."
    DOUBAO_CUSTOM_API_KEY="your-doubao-key"
    DOUBAO_CUSTOM_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
    ```

### 5. 启动应用

在您激活的虚拟环境中，运行以下命令启动Streamlit应用：
```bash
streamlit run app.py
```
您的默认浏览器会自动打开一个新页面，显示AI写作智能体的用户界面。

## ✍️ 使用指南

1.  **输入写作需求:** 在主界面文本框中输入您想创作的内容（例如：一篇关于“量子计算的未来影响”的科普文章）。
2.  **生成计划:** 点击“生成写作计划”按钮，AI将为您提供一份详细的写作计划。
3.  **进行研究:** 确认计划后，点击“开始研究”。AI将进行网络搜索并总结研究结果。
4.  **生成大纲:** 在研究完成后，点击“生成大纲”，AI将根据计划和研究结果创建文章结构。
5.  **逐节撰写:** 点击“准备撰写 (解析大纲)”后，您可以点击“撰写章节”按钮逐一生成文章的每个部分。
6.  **修订全文:** 初稿完成后，点击“开始修订全文”，AI将对整篇文章进行质量检查和润色。
7.  **下载成果:** 最终修订稿显示后，您可以点击“下载最终稿件”按钮保存您的作品。

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
