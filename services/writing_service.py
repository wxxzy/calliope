"""
写作业务服务 (Writing Service)
处理灵感规划（含自动研究）、大纲生成、章节撰写（含 Hybrid RAG 2.0）及全文修订。
"""
import logging
from chains import (
    create_planner_chain, create_outliner_chain, 
    create_draft_generation_chain, create_revise_generation_chain,
    create_chapter_summary_chain, retrieve_with_rewriting,
    create_research_chain
)
import vector_store_manager
import text_splitter_provider
import re_ranker_provider
import tool_provider
from core.schemas import WritingResult
from custom_exceptions import VectorStoreOperationError

logger = logging.getLogger(__name__)

class WritingService:
    @staticmethod
    def run_plan(state: dict, writing_style: str, full_config: dict, execute_func) -> WritingResult:
        """执行“灵感构思”逻辑。不再修改 state，仅返回结果对象。"""
        # 1. 生成计划
        planner_chain = create_planner_chain(writing_style=writing_style)
        planner_inputs = {
            "user_prompt": state.get("user_prompt"),
            "plan": state.get("plan"),
            "refinement_instruction": state.get("refinement_instruction")
        }
        plan_text = execute_func(planner_chain, planner_inputs)

        # 2. 自动研究
        tool_id = state.get("selected_tool_id", "ddg_default") 
        search_tool = tool_provider.get_tool(tool_id)
        research_chain = create_research_chain(search_tool, writing_style=writing_style)
        research_inputs = {
            "plan": plan_text,
            "user_prompt": state.get("user_prompt"),
            "research_results": None,
            "refinement_instruction": None
        }
        research_text = execute_func(research_chain, research_inputs)

        # 3. 知识沉淀
        if research_text:
            WritingService._index_research_results(state, research_text, full_config)

        return WritingResult(plan=plan_text, research_results=research_text)

    @staticmethod
    def run_outline(state: dict, writing_style: str, execute_func) -> WritingResult:
        """生成大纲逻辑"""
        chain = create_outliner_chain(writing_style=writing_style)
        inputs = {
            "plan": state.get("plan"),
            "user_prompt": state.get("user_prompt"),
            "research_results": state.get("research_results"),
            "outline": state.get("outline"),
            "refinement_instruction": state.get("refinement_instruction")
        }
        res_text = execute_func(chain, inputs)
        return WritingResult(outline=res_text)

    @staticmethod
    def generate_draft(state: dict, writing_style: str, full_config: dict, execute_func) -> WritingResult:
        """生成章节内容并自动摘要审计"""
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
        
        warning = None
        if new_content and not state.get("refinement_instruction"):
            WritingService._index_chapter_summary(state, new_content, full_config)
            from services.knowledge_service import KnowledgeService
            warning = KnowledgeService.run_consistency_check(state.get("collection_name"), new_content)
            if warning == "PASS": warning = None
            
        return WritingResult(new_draft_content=new_content, consistency_warning=warning)

    @staticmethod
    def run_revision(state: dict, writing_style: str, execute_func) -> WritingResult:
        """全文修订逻辑"""
        chain = create_revise_generation_chain(writing_style=writing_style)
        inputs = {
            "plan": state.get("plan"),
            "outline": state.get("outline"),
            "full_draft": state.get("full_draft"),
            "user_selected_docs": state.get("user_selected_docs", [])
        }
        return WritingResult(final_manuscript=execute_func(chain, inputs))

    @staticmethod
    def retrieve_for_draft(state: dict, full_config: dict) -> WritingResult:
        """
        为章节撰写检索上下文 (Tiered Memory + Hybrid RAG 2.0)。
        实现真正的分层记忆检索。
        """
        import graph_store_manager
        from core.schemas import WritingResult # 局部导入以避免潜在循环
        
        collection_name = state.get("collection_name")
        section_to_write = state.get("section_to_write", "")
        current_idx = state.get("drafting_index", 0) + 1 
        
        re_ranker = re_ranker_provider.get_re_ranker(full_config.get("active_re_ranker_id"))
        rag_config = full_config.get("rag", {})
        
        all_context_docs = []

        # 1. 图谱层 (Graph Context)
        try:
            G = graph_store_manager.load_graph(collection_name)
            mentioned_entities = [node for node in list(G.nodes()) if node.lower() in section_to_write.lower()]
            if mentioned_entities:
                raw_graph_text = graph_store_manager.get_multi_hop_context(collection_name, mentioned_entities, radius=2)
                if raw_graph_text:
                    all_context_docs.append(f"【知识图谱核心关联设定】:\n{raw_graph_text}")
        except Exception as e:
            logger.error(f"图谱预检索失败: {e}")

        # 2. 强记忆层 (Strong Memory: 最近 3 章摘要)
        try:
            strong_filter = {
                "$and": [
                    {"document_type": "chapter_summary"},
                    {"chapter_index": {"$gte": max(1, current_idx - 3)}},
                    {"chapter_index": {"$lt": current_idx}}
                ]
            }
            recent_summaries = vector_store_manager.retrieve_context(
                collection_name, "最近剧情回顾", recall_k=10, filter_dict=strong_filter
            )
            if recent_summaries:
                all_context_docs.append("【近期剧情强记忆 (必读)】:\n" + "\n---\n".join(recent_summaries))
        except Exception as e:
            logger.error(f"强记忆提取失败: {e}")

        # 3. 弱记忆层 (Weak Memory: 更早章节的语义召回)
        try:
            weak_filter = {
                "$and": [
                    {"document_type": "chapter_summary"},
                    {"chapter_index": {"$lt": max(1, current_idx - 3)}}
                ]
            }
            if current_idx > 3:
                search_query = f"{section_to_write} (涉及实体: {', '.join(mentioned_entities)})" if mentioned_entities else section_to_write
                rag_results = retrieve_with_rewriting(
                    collection_name, search_query, 
                    recall_k=rag_config.get("recall_k", 20), 
                    rerank_k=5, 
                    re_ranker=re_ranker,
                    filter_dict=weak_filter
                )
                if rag_results:
                    all_context_docs.append("【远期剧情召回参考】:\n" + "\n---\n".join(rag_results))
        except Exception as e:
            logger.error(f"弱记忆 RAG 失败: {e}")

        # 4. 世界观设定召回 (Bible RAG)
        try:
            bible_filter = {"source": "world_bible"}
            bible_results = retrieve_with_rewriting(
                collection_name, section_to_write, 
                recall_k=15, rerank_k=5, re_ranker=re_ranker,
                filter_dict=bible_filter
            )
            if bible_results:
                all_context_docs.append("【世界观相关核心设定】:\n" + "\n---\n".join(bible_results))
        except Exception as e:
            logger.error(f"设定召回失败: {e}")

        return WritingResult(retrieved_docs=all_context_docs)

    @staticmethod
    def _index_research_results(state, text, full_config):
        collection_name = state.get("collection_name")
        text_splitter = text_splitter_provider.get_text_splitter(full_config.get('active_text_splitter', 'default_recursive'))
        vector_store_manager.index_text(collection_name, text, text_splitter, metadata={"source": "automated_research"})

    @staticmethod
    def _index_chapter_summary(state, content, full_config):
        from chains import create_chapter_summary_chain
        res = create_chapter_summary_chain().invoke({"chapter_text": content})
        text_splitter = text_splitter_provider.get_text_splitter(full_config.get('active_text_splitter', 'default_recursive'))
        final_meta = {"chapter_index": state.get("drafting_index", 0) + 1, "document_type": "chapter_summary"}
        for k, v in res.get("metadata", {}).items():
            final_meta[k] = ", ".join(v) if isinstance(v, list) else v
        vector_store_manager.index_text(state.get("collection_name"), res.get("summary", ""), text_splitter, metadata=final_meta)