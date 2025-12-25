# 核心概念：ProjectContext (项目上下文)

`ProjectContext` 是 Calliope 系统在 v7.0 重构中引入的底层核心模型。它是实现 **业务逻辑与 UI 表现层彻底解耦** 的基石。

## 1. 核心作用

在系统的架构设计中，`ProjectContext` 扮演着以下四个关键角色：

### 1.1 架构解耦 (Decoupling)
它是业务逻辑层 (`services/`) 唯一能够感知的状态对象。通过引入 `ProjectContext`，业务代码不再依赖 Streamlit 的 `st.session_state`。这意味着核心创作逻辑可以脱离 UI 框架运行，具备了良好的可测试性和可移植性。

### 1.2 领域状态容器 (State Container)
它完整封装了一个创作项目在运行时的所有业务数据（如计划、大纲、草稿、设定等）。它是项目在内存中的“数字化孪生”，确保了数据流的内聚性。

### 1.3 持久化白名单 (Persistence Whitelist)
在基于 SQLite 的存储体系中，`ProjectContext` 定义了哪些字段属于“必须保存的业务资产”。在执行持久化操作时，系统会参考其字段定义进行过滤，从而自动剔除 UI 产生的临时状态（如按钮点击记录、滚动条位置等），有效防止了数据库污染。

### 1.4 数据契约 (Data Contract)
它作为各层级间传递的数据规范，明确了输入和输出的预期，提升了代码的可读性和 IDE 的类型提示能力。

---

## 2. 具体实现

### 2.1 定义位置
`ProjectContext` 定义在 `core/schemas.py` 中，利用 Python 的 `@dataclass` 实现，以确保轻量化和易于序列化。

### 2.2 核心字段分类
*   **基础标识**: `project_root` (项目路径), `project_name` (显示名称)。
*   **创作资产**: `plan`, `outline`, `outline_sections`, `drafts`, `world_bible` 等。
*   **交互状态**: `user_prompt` (用户指令), `selected_tool_id` (工具选择), `section_to_write` (撰写任务)。
*   **审核校验**: `current_critique` (AI反馈), `pending_triplets` (待处理图谱数据)。

---

## 3. 运行时数据流转

在一次典型的用户交互（如“生成大纲”）中，数据的流转流程如下：

1.  **封装 (UI -> Context)**: 
    在 `app.py` 的 `run_step_with_spinner` 中，系统扫描当前的 `st.session_state`，根据 `ProjectContext` 的字段名提取数据，实例化一个 Context 对象。
2.  **执行 (Context -> Service)**: 
    `workflow_manager` 将 Context 对象传递给具体的业务 Service。Service 根据 Context 中的信息调用 LLM 链。
3.  **反馈 (Result -> UI)**: 
    Service 返回结果对象（如 `WritingResult`），`app.py` 捕获结果并将变化同步回 `st.session_state` 触发 UI 刷新。
4.  **持久化 (Context -> SQL)**: 
    在保存阶段，系统遍历 Context 字段，将其写入项目目录下的 `content.db`。

---

## 4. 维护规范
*   **新增业务字段**: 如果需要增加新的持久化状态（如“角色清单”），应首先在 `ProjectContext` 中定义。
*   **严禁污染**: 不得将任何 UI 框架特有的对象（如 Widget 实例、上传文件流等）放入 `ProjectContext`。
