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
        if not text: 
            logger.warning("No text to extract for graph.")
            return {"graph_updated": False}
        
        chain = create_graph_extraction_chain()
        try:
            triplets = chain.invoke({"text": text})
            if triplets and isinstance(triplets, list):
                # 显式获取并更新 state 字典
                current_pending = state.get("pending_triplets", [])
                new_count = 0
                for t in triplets:
                    if t not in current_pending: 
                        current_pending.append(t)
                        new_count += 1
                
                # 关键修复：显式赋值写回 state
                state["pending_triplets"] = current_pending
                logger.info(f"成功提取 {new_count} 条新关系，待审总数: {len(current_pending)}")
                return {"graph_updated": True, "extracted_count": new_count}
        except Exception as e:
            logger.error(f"图谱提取失败: {e}", exc_info=True)
        return {"graph_updated": False}

    @staticmethod
    def run_naming(state: dict, collection_name: str, communities: dict):
        """执行派系命名逻辑"""
        chain = create_community_naming_chain()
        world_bible = state.get("world_bible", "")
        return graph_store_manager.generate_and_cache_community_names(
            collection_name, communities, chain, world_bible
        )

    @staticmethod
    def get_scene_entities_info(collection_name: str, text: str):
        """
        分析当前场景涉及的实体信息。
        用于侧边栏挂件展示。
        """
        try:
            G = graph_store_manager.load_graph(collection_name)
            all_nodes = list(G.nodes())
            # 简单的关键词提取（未来可升级为 NER）
            mentioned = [node for node in all_nodes if node.lower() in text.lower()]
            
            if not mentioned:
                return None
            
            # 获取派系和缓存名称
            communities = graph_store_manager.detect_communities(collection_name)
            cached_names = graph_store_manager.load_cached_community_names(collection_name)
            
            entities_data = []
            conflicts = []
            
            # --- 冲突关键词定义 ---
            negative_keywords = ["敌", "仇", "恨", "杀", "背叛", "战", "对立"]

            for i, entity in enumerate(mentioned):
                # 查找派系
                comm_id = next((name for name, nodes in communities.items() if entity in nodes), "未知")
                comm_name = cached_names.get(comm_id, comm_id)
                
                # 获取直接邻居
                neighbors = list(G.neighbors(entity))
                relations = []
                for n in neighbors[:3]: 
                    r = G[entity][n].get('relation', '关联')
                    relations.append(f"{r} -> {n}")
                    
                    # --- 冲突检测逻辑 (New) ---
                    # 如果邻居也在当前场上，且关系中包含负面词，记录冲突
                    if n in mentioned and any(kw in r for keyword in negative_keywords for kw in [keyword]):
                        conflicts.append(f"【{entity}】与【{n}】存在冲突关系: {r}")
                
                entities_data.append({
                    "name": entity,
                    "faction": comm_name,
                    "relations": relations
                })
            
            return {
                "entities": entities_data,
                "conflicts": list(set(conflicts)) # 去重
            }
        except Exception as e:
            logger.error(f"获取场景实体信息失败: {e}")
            return None
