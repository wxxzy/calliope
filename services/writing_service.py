"""
写作业务服务 (Writing Service)
处理灵感规划（含自动研究）、大纲生成、章节撰写（含 Hybrid RAG）及全文修订。
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
from custom_exceptions import VectorStoreOperationError

logger = logging.getLogger(__name__)

class WritingService:
    """
    核心写作业务类。
    实现了从初步构思到最终成稿的所有高阶业务逻辑。
    """

    @staticmethod
    def run_plan(state: dict, writing_style: str, full_config: dict, execute_func):
        """
        执行“灵感构思”逻辑 (合并了规划与研究)。
        
        流程：
        1. 调用 Planner 生成初步写作计划。
        2. 自动获取选中的搜索工具。
        3. 自动调用 Researcher 根据计划进行 Web 并行搜索并总结。
        4. 将研究资料持久化到项目向量库中。
        """
        # --- 步骤 1: 生成写作计划 ---
        planner_chain = create_planner_chain(writing_style=writing_style)
        planner_inputs = {
            "user_prompt": state.get("user_prompt"),
            "plan": state.get("plan"),
            "refinement_instruction": state.get("refinement_instruction")
        }
        plan_text = execute_func(planner_chain, planner_inputs)

        # --- 步骤 2: 自动进行背景研究 (整合逻辑) ---
        tool_id = state.get("selected_tool_id", "ddg_default") 
        search_tool = tool_provider.get_tool(tool_id)
        
        research_chain = create_research_chain(search_tool, writing_style=writing_style)
        research_inputs = {
            "plan": plan_text,
            "user_prompt": state.get("user_prompt"),
            "research_results": None,
            "refinement_instruction": None
        }
        
        logger.info(f"正在使用工具 '{tool_id}' 进行自动背景研究...")
        research_text = execute_func(research_chain, research_inputs)

        # --- 步骤 3: 研究知识沉淀 ---
        if research_text:
            WritingService._index_research_results(state, research_text, full_config)

        # 同时返回计划和研究摘要，供 UI 更新状态
        return {
            "plan": plan_text, 
            "research_results": research_text 
        }

    @staticmethod
    def _index_research_results(state, text, full_config):
        """内部方法：将自动研究获取的知识打标存入 RAG 库"""
        try:
            collection_name = state.get("collection_name")
            active_splitter_id = full_config.get('active_text_splitter', 'default_recursive') 
            text_splitter = text_splitter_provider.get_text_splitter(active_splitter_id) 
            
            metadata = {
                "source": "automated_research",
                "document_type": "background_material",
                "project": state.get("project_name")
            }
            vector_store_manager.index_text(collection_name, text, text_splitter, metadata=metadata)
            logger.info("研究资料已自动入库。")
        except Exception as e:
            logger.error(f"研究资料入库失败: {e}")

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
        """
        为章节撰写检索上下文 (Hybrid RAG 2.0)。
        融合图谱关系网与向量语义检索。
        """
        import graph_store_manager
        collection_name = state.get("collection_name")
        section_to_write = state.get("section_to_write", "")
        
        # 获取 RAG 配置
        active_re_ranker_id = full_config.get("active_re_ranker_id")
        re_ranker = re_ranker_provider.get_re_ranker(active_re_ranker_id)
        rag_config = full_config.get("rag", {})
        
        # 1. 实体识别与图谱先行
        graph_context_doc = ""
        try:
            G = graph_store_manager.load_graph(collection_name)
            all_nodes = list(G.nodes())
            mentioned_entities = [node for node in all_nodes if node.lower() in section_to_write.lower()]
            
            if mentioned_entities:
                raw_graph_text = graph_store_manager.get_multi_hop_context(collection_name, mentioned_entities, radius=2)
                if raw_graph_text:
                    graph_context_doc = f"【知识图谱核心关联 (权威设定)】:\n{raw_graph_text}\n(请在撰写时严格遵守上述关系设定)"
        except Exception as e:
            logger.error(f"图谱预检索失败: {e}")

        # 2. 向量检索 (增强查询)
        enhanced_query = section_to_write
        if mentioned_entities:
            enhanced_query = f"{section_to_write} (涉及实体: {', '.join(mentioned_entities)})"

        # 未来可以根据 state 中的 timeline_focus 设置 filter_dict
        filter_dict = state.get("active_metadata_filter")

        retrieved_docs = retrieve_with_rewriting(
            collection_name, enhanced_query, 
            rag_config.get("recall_k", 20), 
            rag_config.get("rerank_k", 5), 
            re_ranker,
            filter_dict=filter_dict
        )
        
        if graph_context_doc:
            retrieved_docs.insert(0, graph_context_doc)
        
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
            # 1. 索引摘要
            WritingService._index_chapter_summary(state, new_content, full_config)
            
            # 2. 逻辑一致性审计 (New: Consistency Sentinel)
            from services.knowledge_service import KnowledgeService
            audit_result = KnowledgeService.run_consistency_check(state.get("collection_name"), new_content)
            if audit_result != "PASS":
                # 将冲突警报存入 state
                return {"new_draft_content": new_content, "consistency_warning": audit_result}
            
        return {"new_draft_content": new_content}

    @staticmethod
    def _index_chapter_summary(state, content, full_config):
        """内部方法：为新章节生成摘要和元数据并入库"""
        try:
            summary_chain = create_chapter_summary_chain()
            # 现在返回的是包含 summary 和 metadata 的字典
            res = summary_chain.invoke({"chapter_text": content})
            
            summary_text = res.get("summary", "")
            ai_metadata = res.get("metadata", {})
            
            active_splitter_id = full_config.get('active_text_splitter', 'default_recursive') 
            text_splitter = text_splitter_provider.get_text_splitter(active_splitter_id) 
            
            # 构建最终存入向量库的元数据
            final_metadata = {
                "project_name": state.get("project_name"),
                "chapter_index": state.get("drafting_index", 0) + 1,
                "document_type": "chapter_summary",
                "source": f"chapter_{state.get('drafting_index', 0) + 1}"
            }
            # 合并 AI 提取的元数据（时间、地点、张力等）
            # 关键修复：ChromaDB 不支持列表作为元数据值，需要转换为字符串
            for k, v in ai_metadata.items():
                if isinstance(v, list):
                    final_metadata[k] = ", ".join([str(item) for item in v])
                else:
                    final_metadata[k] = v
            
            # 存入向量数据库
            vector_store_manager.index_text(state.get("collection_name"), summary_text, text_splitter, metadata=final_metadata)
            logger.info(f"章节摘要及元数据已入库: {ai_metadata}")
        except Exception as e:
            logger.error(f"索引摘要失败: {e}")
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