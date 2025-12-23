"""
写作业务服务 (Writing Service)
处理规划、大纲生成、章节撰写（含 RAG 增强）及全文修订的业务逻辑。
"""
import logging
from chains import (
    create_planner_chain, create_outliner_chain, 
    create_draft_generation_chain, create_revise_generation_chain,
    create_chapter_summary_chain, retrieve_with_rewriting
)
import vector_store_manager
import text_splitter_provider
import re_ranker_provider
from custom_exceptions import VectorStoreOperationError

logger = logging.getLogger(__name__)

class WritingService:
    @staticmethod
    def run_plan(state: dict, writing_style: str, execute_func):
        """执行写作规划逻辑"""
        chain = create_planner_chain(writing_style=writing_style)
        inputs = {
            "user_prompt": state.get("user_prompt"),
            "plan": state.get("plan"),
            "refinement_instruction": state.get("refinement_instruction")
        }
        return {"plan": execute_func(chain, inputs)}

    @staticmethod
    def run_outline(state: dict, writing_style: str, execute_func):
        """执行大纲生成逻辑"""
        chain = create_outliner_chain(writing_style=writing_style)
        inputs = {
            "plan": state.get("plan"),
            "user_prompt": state.get("user_prompt"),
            "research_results": state.get("research_results"),
            "outline": state.get("outline"),
            "refinement_instruction": state.get("refinement_instruction")
        }
        return {"outline": execute_func(chain, inputs)}

    @staticmethod
    def retrieve_for_draft(state: dict, full_config: dict):
        """为章节撰写检索上下文 (含图谱与向量)"""
        collection_name = state.get("collection_name")
        section_to_write = state.get("section_to_write", "")
        
        # 获取配置
        active_re_ranker_id = full_config.get("active_re_ranker_id")
        re_ranker = re_ranker_provider.get_re_ranker(active_re_ranker_id)
        rag_config = full_config.get("rag", {})
        
        # 1. 向量检索
        retrieved_docs = retrieve_with_rewriting(
            collection_name, section_to_write, 
            rag_config.get("recall_k", 20), 
            rag_config.get("rerank_k", 5), 
            re_ranker
        )
        
        # 2. 图谱增强 (此处暂留接口，实际由 workflow_manager 协调或在 knowledge_service 处理)
        return {"retrieved_docs": retrieved_docs}

    @staticmethod
    def generate_draft(state: dict, writing_style: str, full_config: dict, execute_func):
        """生成章节内容并自动摘要索引"""
        chain = create_draft_generation_chain(writing_style=writing_style)
        inputs = {
            "user_prompt": state.get("user_prompt"),
            "research_results": state.get("research_results"),
            "outline": state.get("outline"),
            "section_to_write": state.get("section_to_write"),
            "user_selected_docs": state.get("user_selected_docs", []),
            "previous_chapter_draft": state.get("current_chapter_draft"),
            "refinement_instruction": state.get("refinement_instruction")
        }
        
        new_content = execute_func(chain, inputs)
        
        # 自动摘要与记忆索引逻辑
        if new_content and not state.get("refinement_instruction"):
            WritingService._index_chapter_summary(state, new_content, full_config)
            
        return {"new_draft_content": new_content}

    @staticmethod
    def _index_chapter_summary(state, content, full_config):
        """内部方法：为新章节生成摘要并入库"""
        try:
            summary_chain = create_chapter_summary_chain()
            summary = summary_chain.invoke({"chapter_text": content})
            
            active_splitter_id = full_config.get('active_text_splitter', 'default_recursive') 
            text_splitter = text_splitter_provider.get_text_splitter(active_splitter_id)
            
            metadata = {
                "project_name": state.get("project_name"),
                "chapter_index": state.get("drafting_index", 0) + 1,
                "document_type": "chapter_summary"
            }
            vector_store_manager.index_text(state.get("collection_name"), summary, text_splitter, metadata=metadata)
        except Exception as e:
            logger.error(f"索引章节摘要失败: {e}")
            raise VectorStoreOperationError(f"无法同步记忆库: {e}")

    @staticmethod
    def run_revision(state: dict, writing_style: str, execute_func):
        """执行全文修订逻辑"""
        chain = create_revise_generation_chain(writing_style=writing_style)
        inputs = {
            "plan": state.get("plan"),
            "outline": state.get("outline"),
            "full_draft": state.get("full_draft"),
            "user_selected_docs": state.get("user_selected_docs", [])
        }
        return {"final_manuscript": execute_func(chain, inputs)}
