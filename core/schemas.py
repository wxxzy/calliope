"""
业务对象定义 (Schemas)
定义系统各层级间传递的强类型数据结构，确保数据流透明且可预测。
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

@dataclass
class ActionResult:
    """通用业务执行结果"""
    success: bool = True
    message: str = ""
    # 动态存储业务产出（如 plan, outline 等）
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WritingResult:
    """写作业务专用结果"""
    plan: Optional[str] = None
    research_results: Optional[str] = None
    outline: Optional[str] = None
    new_draft_content: Optional[str] = None
    consistency_warning: Optional[str] = None
    final_manuscript: Optional[str] = None
    retrieved_docs: Optional[List[str]] = None

@dataclass
class KnowledgeResult:
    """知识业务专用结果"""
    graph_updated: bool = False
    extracted_count: int = 0
    pending_triplets: Optional[List] = None
    current_critique: Optional[str] = None
    bible_synced: bool = False
