"""
业务对象定义 (Schemas)
定义系统各层级间传递的强类型数据结构，确保数据流透明且可预测。
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

@dataclass
class ProjectContext:
    """
    项目运行时上下文 (领域模型)
    该对象包含业务层所需的所有数据，与 UI 框架 (Streamlit) 彻底解耦。
    """
    project_root: str
    project_name: str
    world_bible: str = ""
    plan: str = ""
    research_results: str = ""
    outline: str = ""
    outline_sections: List[str] = field(default_factory=list)
    expected_total_chapters: int = 10
    target_words_per_chapter: int = 2000
    drafts: List[str] = field(default_factory=list)
    drafting_index: int = 0
    final_manuscript: str = ""
    
    # 交互过程中的临时状态
    user_prompt: str = ""
    refinement_instruction: str = ""
    enable_research: bool = False
    selected_tool_id: str = "ddg_default"
    section_to_write: str = ""
    current_chapter_draft: str = ""
    user_selected_docs: List[str] = field(default_factory=list)
    
    # 评审与校验状态
    current_critique: str = ""
    critique_target_type: str = "draft"
    pending_triplets: List[Any] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

@dataclass
class WritingResult:
    """写作业务执行结果"""
    plan: Optional[str] = None
    research_results: Optional[str] = None
    outline: Optional[str] = None
    new_draft_content: Optional[str] = None
    consistency_warning: Optional[str] = None
    final_manuscript: Optional[str] = None
    retrieved_docs: Optional[List[str]] = None

@dataclass
class KnowledgeResult:
    """知识业务执行结果"""
    graph_updated: bool = False
    extracted_count: int = 0
    pending_triplets: Optional[List] = None
    current_critique: Optional[str] = None
    bible_synced: bool = False
    extracted_timeline_event: Optional[Dict[str, Any]] = None