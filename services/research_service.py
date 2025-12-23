"""
研究业务服务 (Research Service)
处理在线搜索与信息总结业务逻辑。
"""
from chains import create_research_chain
import tool_provider
import vector_store_manager
import text_splitter_provider
import logging

logger = logging.getLogger(__name__)

class ResearchService:
    @staticmethod
    def run_research(state: dict, writing_style: str, full_config: dict, execute_func):
        """执行多源研究搜索与总结，并将结果持久化到记忆库"""
        search_tool = tool_provider.get_tool(state.get("selected_tool_id"))
        chain = create_research_chain(search_tool, writing_style=writing_style)
        inputs = {
            "plan": state.get("plan"),
            "user_prompt": state.get("user_prompt"),
            "research_results": state.get("research_results"),
            "refinement_instruction": state.get("refinement_instruction")
        }
        
        results = execute_func(chain, inputs)
        
        # --- 知识沉淀 (New) ---
        if results:
            try:
                collection_name = state.get("collection_name")
                active_splitter_id = full_config.get('active_text_splitter', 'default_recursive') 
                text_splitter = text_splitter_provider.get_text_splitter(active_splitter_id)
                
                metadata = {
                    "source": "online_research",
                    "project": state.get("project_name"),
                    "document_type": "background_material"
                }
                
                vector_store_manager.index_text(collection_name, results, text_splitter, metadata=metadata)
                logger.info("研究摘要已成功持久化至向量库。")
            except Exception as e:
                logger.error(f"沉淀研究资料失败: {e}")
        
        return {"research_results": results}
