"""
写作业务服务 (Writing Service)
处理灵感规划（含自动研究）、大纲生成、章节撰写（含 Hybrid RAG 2.0）及全文修订。
"""
from __future__ import annotations
import logging
from chains import (
    create_planner_chain, create_outliner_chain, 
    create_draft_generation_chain, create_revise_generation_chain,
    create_chapter_summary_chain, retrieve_with_rewriting,
    create_research_chain
)
from infra.storage import vector_store as vector_store_manager
from infra.utils import text_splitters as text_splitter_provider
from infra.llm import rerankers as re_ranker_provider
from infra.tools import factory as tool_provider
from core.schemas import WritingResult, ProjectContext
from core.exceptions import VectorStoreOperationError

logger = logging.getLogger(__name__)

class WritingService:
    @staticmethod
    def run_plan(context: ProjectContext, writing_style: str, full_config: dict, execute_func) -> WritingResult:
        """执行“灵感构思”逻辑。"""
        # 1. 生成计划
        planner_chain = create_planner_chain(writing_style=writing_style)
        planner_inputs = {
            "user_prompt": context.user_prompt,
            "plan": context.plan,
            "refinement_instruction": context.refinement_instruction
        }
        plan_text = execute_func(planner_chain, planner_inputs)

        # 2. 自动研究
        tool_id = context.selected_tool_id
        search_tool = tool_provider.get_tool(tool_id)
        research_chain = create_research_chain(search_tool, writing_style=writing_style)
        research_inputs = {
            "plan": plan_text,
            "user_prompt": context.user_prompt,
            "research_results": None,
            "refinement_instruction": None
        }
        research_text = execute_func(research_chain, research_inputs)

        # 3. 不再直接索引研究结果，而是返回给 UI
        # if research_text:
        #     WritingService._index_research_results(context, research_text, full_config)

        return WritingResult(plan=plan_text, research_results=research_text)

    @staticmethod
    def run_outline(context: ProjectContext, writing_style: str, execute_func) -> WritingResult:
        """生成大纲逻辑"""
        chain = create_outliner_chain(writing_style=writing_style)
        inputs = {
            "plan": context.plan,
            "user_prompt": context.user_prompt,
            "research_results": context.research_results,
            "outline": context.outline,
            "refinement_instruction": context.refinement_instruction
        }
        res_text = execute_func(chain, inputs)
        return WritingResult(outline=res_text)

    @staticmethod
    def generate_draft(context: ProjectContext, writing_style: str, full_config: dict, execute_func) -> WritingResult:
        """生成章节内容并自动摘要审计"""
        chain = create_draft_generation_chain(writing_style=writing_style)
        inputs = {
            "user_prompt": context.user_prompt,
            "research_results": context.research_results,
            "outline": context.outline,
            "section_to_write": context.section_to_write,
            "user_selected_docs": context.user_selected_docs,
            "previous_chapter_draft": context.current_chapter_draft,
            "refinement_instruction": context.refinement_instruction
        }
        new_content = execute_func(chain, inputs)
        
        warning = None
        if new_content:
            # 无论是否是微调，都应当更新年表摘要
            WritingService._index_chapter_summary(context, new_content, full_config)
            from services.knowledge_service import KnowledgeService
            warning = KnowledgeService.run_consistency_check(context.project_root, new_content)
            if warning == "PASS": warning = None
            
        return WritingResult(new_draft_content=new_content, consistency_warning=warning)

    @staticmethod
    def run_revision(context: ProjectContext, writing_style: str, execute_func) -> WritingResult:
        """全文修订逻辑"""
        # 注意：此处假定 context.drafts 已合并为 full_draft
        # 或者直接从 context 获取
        full_draft = "\n\n".join(context.drafts)
        chain = create_revise_generation_chain(writing_style=writing_style)
        inputs = {
            "plan": context.plan,
            "outline": context.outline,
            "full_draft": full_draft,
            "user_selected_docs": context.user_selected_docs
        }
        return WritingResult(final_manuscript=execute_func(chain, inputs))

    @staticmethod
    def retrieve_for_draft(context: ProjectContext, full_config: dict) -> WritingResult:
        """
        为章节撰写检索上下文 (Tiered Memory + Hybrid RAG 2.0)。
        """
        from infra.storage import graph_store as graph_store_manager
        
        project_root = context.project_root
        section_to_write = context.section_to_write
        current_idx = context.drafting_index + 1 
        
        re_ranker = re_ranker_provider.get_re_ranker(full_config.get("active_re_ranker_id"))
        rag_config = full_config.get("rag", {})
        
        all_context_docs = []

        # 1. 图谱层 (Graph Context)
        try:
            G = graph_store_manager.load_graph(project_root)
            mentioned_entities = [node for node in list(G.nodes()) if node.lower() in section_to_write.lower()]
            if mentioned_entities:
                raw_graph_text = graph_store_manager.get_multi_hop_context(project_root, mentioned_entities, radius=2)
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
                project_root, "最近剧情回顾", recall_k=10, filter_dict=strong_filter
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
                search_query = f"{section_to_write}"
                rag_results = retrieve_with_rewriting(
                    project_root, search_query, 
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
                project_root, section_to_write, 
                recall_k=15, rerank_k=5, re_ranker=re_ranker,
                filter_dict=bible_filter
            )
            if bible_results:
                all_context_docs.append("【世界观相关核心设定】:\n" + "\n---\n".join(bible_results))
        except Exception as e:
            logger.error(f"设定召回失败: {e}")

        return WritingResult(retrieved_docs=all_context_docs)



    @staticmethod
    def _index_chapter_summary(context: ProjectContext, content: str, full_config: dict):
        from chains import create_chapter_summary_chain
        from infra.storage import sql_db
        
        # 1. AI 提取摘要与元数据
        res = create_chapter_summary_chain().invoke({"chapter_text": content})
        summary_text = res.get("summary", "")
        metadata = res.get("metadata", {})
        
        # 2. 准备 SQL 数据并保存 (Sprint 2 新增)
        chapter_idx = context.drafting_index + 1
        event_data = {
            "chapter_index": chapter_idx,
            "time": metadata.get("time", "未知"),
            "location": metadata.get("location", "未知"),
            "tension": metadata.get("tension", 5.0),
            "word_count": len(content),
            "summary": summary_text
        }
        sql_db.save_timeline_event(context.project_root, event_data)

        # 3. 向量库索引 (原有逻辑)
        text_splitter = text_splitter_provider.get_text_splitter(full_config.get('active_text_splitter', 'default_recursive'))
        final_meta = {
            "chapter_index": chapter_idx, 
            "document_type": "chapter_summary",
            "original_word_count": len(content)
        }
        # 将 AI 提取的所有元数据也存入向量库，方便后续 RAG 过滤
        for k, v in metadata.items():
            final_meta[k] = ", ".join(v) if isinstance(v, list) else v
            
        vector_store_manager.index_text(context.project_root, summary_text, text_splitter, metadata=final_meta)