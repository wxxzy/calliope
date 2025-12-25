# 项目组织架构文档 (v7.0)

本系统遵循 **领域驱动设计 (DDD)** 原则，并采用 **“文件夹即项目” (Folder-based Project)** 的管理模式。

## 1. 物理目录结构

每个 Calliope 写作项目是一个独立的文件夹，结构如下：

```text
[Project_Root]/                 # 用户指定的项目文件夹
├── project.calliope            # 项目元数据 (JSON: 名称, 版本, 创建时间)
├── content.db                  # 核心数据库 (SQLite: 章节, 计划, 年表)
├── state.json                  # (Legacy) 旧版状态文件 (保留用于迁移参考)
├── knowledge/                  # 知识库子目录
│   ├── graph.json              # 知识图谱数据 (NetworkX 格式)
│   └── chroma_db/              # 向量数据库 (ChromaDB 物理文件)
├── snapshots/                  # 自动生成的数据库备份 (.db 文件)
└── exports/                    # 导出的 Markdown, PDF, EPUB 文件
```

## 2. 代码分层设计

系统代码位于根目录，作为“编辑器”操作上述项目文件夹。

### 2.1 基础设施层 (`infra/`)
*   `storage/sql_db.py`: 管理 `content.db` 的 CRUD。
*   `storage/vector_store.py`: 管理 `chroma_db` 的动态加载。
*   `storage/graph_store.py`: 管理 `graph.json` 的读写。
*   `llm/`: 负责所有 AI 模型的工厂化实例化。

### 2.2 领域核心层 (`core/`)
*   `models.py`: 定义数据库 Schema。
*   `project_manager.py`: 负责项目生命周期 (创建, 校验, 快照)。
*   `schemas.py`: 内部数据交换对象 (Result Objects)。

### 2.3 业务服务层 (`services/`)
*   `writing_service.py`: 协调写作工作流。
*   `knowledge_service.py`: 协调知识提取与一致性校验。
*   `workflow.py`: Facade 模式，统一路由 UI 请求。

### 2.4 表现层 (`ui_components/` & `app.py`)
*   `app.py`: 包含 **Launcher (启动器)** 和 **Workspace (工作区)** 两大状态机。
*   `ui_components/`: 纯净的视图组件，不直接操作数据库路径。

## 3. 核心流程：加载项目

1.  用户在 UI 选择文件夹。
2.  `ProjectManager` 校验 `project.calliope` 是否存在。
3.  `sql_db` 动态创建连接该目录下 `content.db` 的 Engine。
4.  `vector_store` 初始化指向该目录的 `PersistentClient`。
5.  Session State 被注入项目路径，进入 Workspace 模式。
