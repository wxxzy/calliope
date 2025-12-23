"""
知识业务服务 (Knowledge Service)
处理知识图谱提取、派系识别、命名及冲突检测业务逻辑。
"""
import logging
import graph_store_manager
from chains import create_graph_extraction_chain, create_community_naming_chain, create_critic_chain

logger = logging.getLogger(__name__)

class KnowledgeService:
    @staticmethod
    def run_critique(state: dict, writing_style: str, execute_func):
        """执行 AI 评审逻辑"""
        target_type = state.get("critique_target_type", "draft")
        content = state.get("outline") if target_type == "outline" else (state.get("drafts", [])[-1] if state.get("drafts") else "")
        
        chain = create_critic_chain(writing_style=writing_style)
        inputs = {
            "stage": "章节撰写" if target_type == "draft" else "大纲设计",
            "plan": state.get("plan", ""),
            "content_to_review": content
        }
        return {"current_critique": execute_func(chain, inputs)}

    @staticmethod
    def update_graph(state: dict):
        """执行图谱自动提取逻辑"""
        text = state.get("text_to_extract", "")
        if not text: return {"graph_updated": False}
        
        chain = create_graph_extraction_chain()
        try:
            triplets = chain.invoke({"text": text})
            if triplets and isinstance(triplets, list):
                # 依据 Phase 3 逻辑：推送到待审列表
                current_pending = state.get("pending_triplets", [])
                for t in triplets:
                    if t not in current_pending: current_pending.append(t)
                return {"graph_updated": True, "pending_triplets": current_pending}
        except Exception as e:
            logger.error(f"图谱提取失败: {e}")
        return {"graph_updated": False}

    @staticmethod
    def run_naming(state: dict, collection_name: str, communities: dict):
        """执行派系命名逻辑"""
        chain = create_community_naming_chain()
        world_bible = state.get("world_bible", "")
        return graph_store_manager.generate_and_cache_community_names(
            collection_name, communities, chain, world_bible
        )
