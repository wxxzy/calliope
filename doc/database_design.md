# 数据库设计文档 (SQLite)

本系统采用 **“单项目单数据库”** 模式，每个写作项目在其根目录下拥有一个独立的 `content.db` 文件。

## 1. 核心模型 (Models)

数据库使用 SQLAlchemy ORM 进行管理，模型定义位于 `core/models.py`。

### 1.1 项目设置表 (`project_settings`)
用于存储项目的全局非结构化数据或状态标志。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `key` | String (PK) | 设置项键名 (如 `plan`, `outline`, `world_bible`) |
| `value` | Text | 设置项内容 (大文本或 JSON 字符串) |

### 1.2 章节表 (`chapters`)
存储创作的核心正文内容。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | Integer (PK) | 自增主键 |
| `index` | Integer (Unique) | 章节序号 (1, 2, 3...) |
| `title` | String | 章节标题 |
| `content` | Text | 章节正文内容 |
| `summary` | Text | 章节摘要 (用于 RAG 回顾) |
| `word_count` | Integer | 该章原始字数 |

### 1.3 时间轴事件表 (`timeline_events`)
存储从章节中提取的结构化时空数据，用于剧情洞察渲染。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | Integer (PK) | 自增主键 |
| `chapter_index` | Integer | 关联的章节序号 |
| `time_str` | String | 故事内时间描述 (如 "星历2024年") |
| `location` | String | 发生地点 |
| `tension` | Float | 戏剧张力评分 (1.0 - 10.0) |
| `event_desc` | String | 核心事件简述 |

---

## 2. 存储策略

1.  **连接管理**: 采用 `lru_cache` 缓存数据库 Engine，确保切换项目时能快速重连，同时避免多项目同时打开时的资源浪费。
2.  **并发处理**: SQLite 连接配置了 `check_same_thread=False`，以适配 Streamlit 的多线程 UI 渲染机制。
3.  **初始化**: 系统在打开或创建项目时，会自动调用 `Base.metadata.create_all(engine)` 确保表结构完整。
