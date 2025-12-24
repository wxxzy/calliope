"""
知识业务服务 (Knowledge Service)
处理知识图谱提取、派系识别、命名及统一库同步。
"""
import logging
import graph_store_manager
import vector_store_manager
import text_splitter_provider
from core.schemas import KnowledgeResult
from chains import (
    create_graph_extraction_chain, create_community_naming_chain, 
    create_critic_chain, create_consistency_sentinel_chain
)

logger = logging.getLogger(__name__)

class KnowledgeService:
    @staticmethod
    def sync_bible(state: dict, content: str, full_config: dict) -> KnowledgeResult:
        """统一同步设定，返回 KnowledgeResult"""
        collection_name = state.get("collection_name")
        # 1. 向量索引
        vector_store_manager.delete_by_metadata(collection_name, {"source": "world_bible"})
        text_splitter = text_splitter_provider.get_text_splitter(full_config.get('active_text_splitter', 'default_recursive'))
        vector_store_manager.index_text(collection_name, content, text_splitter, metadata={"source": "world_bible"})
        
        # 2. 图谱提取
        # 使用 dict() 显式转换，因为 st.session_state 没有 .copy() 方法
        state_copy = dict(state)
        state_copy["text_to_extract"] = content
        graph_res = KnowledgeService.update_graph(state_copy)
        
        return KnowledgeResult(
            bible_synced=True, 
            graph_updated=graph_res.graph_updated, 
            pending_triplets=graph_res.pending_triplets,
            extracted_count=graph_res.extracted_count
        )

    @staticmethod
    def run_critique(state: dict, writing_style: str, execute_func) -> KnowledgeResult:
        """执行 AI 评审"""
        target_type = state.get("critique_target_type", "draft")
        content = state.get("outline") if target_type == "outline" else (state.get("drafts", [])[-1] if state.get("drafts") else "")
        chain = create_critic_chain(writing_style=writing_style)
        inputs = {"stage": target_type, "plan": state.get("plan", ""), "content_to_review": content}
        res = execute_func(chain, inputs)
        return KnowledgeResult(current_critique=res)

    @staticmethod
    def update_graph(state: dict) -> KnowledgeResult:
        """提取图谱，不再修改传入的 state"""
        text = state.get("text_to_extract", "")
        if not text: return KnowledgeResult()
        
        try:
            triplets = create_graph_extraction_chain().invoke({"text": text})
            if triplets and isinstance(triplets, list):
                # 仅返回“建议增加”的列表，不直接修改 state
                current_pending = list(state.get("pending_triplets", []))
                new_added = [t for t in triplets if t not in current_pending]
                return KnowledgeResult(graph_updated=True, pending_triplets=current_pending + new_added, extracted_count=len(new_added))
        except Exception as e:
            logger.error(f"图谱提取失败: {e}")
        return KnowledgeResult()

    @staticmethod
    def run_naming(state: dict, collection_name: str, communities: dict):
        """命名逻辑保持原状，因为它直接操作磁盘缓存"""
        chain = create_community_naming_chain()
        world_bible = state.get("world_bible", "")
        return graph_store_manager.generate_and_cache_community_names(collection_name, communities, chain, world_bible)

    @staticmethod
    def run_consistency_check(collection_name: str, text: str):
        """逻辑哨兵保持返回字符串"""
        try:
            G = graph_store_manager.load_graph(collection_name)
            mentioned = [node for node in list(G.nodes()) if node.lower() in text.lower()]
            if not mentioned: return "PASS"
            graph_facts = graph_store_manager.get_multi_hop_context(collection_name, mentioned, radius=2)
            if not graph_facts: return "PASS"
            return create_consistency_sentinel_chain().invoke({"graph_facts": graph_facts, "chapter_text": text})
        except Exception:
            return "PASS"

    @staticmethod
    def get_scene_entities_info(collection_name: str, text: str):
        """
        分析当前场景涉及的实体信息及潜在冲突。
        """
        try:
            G = graph_store_manager.load_graph(collection_name)
            all_nodes = list(G.nodes())
            mentioned = [node for node in all_nodes if node.lower() in text.lower()]
            
            if not mentioned: return None
            
            communities = graph_store_manager.detect_communities(collection_name)
            cached_names = graph_store_manager.load_cached_community_names(collection_name)
            
            entities_data = []
            conflicts = []
            negative_keywords = ["敌", "仇", "恨", "杀", "背叛", "战", "对立"]

            for entity in mentioned:
                comm_id = next((name for name, nodes in communities.items() if entity in nodes), "未知")
                comm_name = cached_names.get(comm_id, comm_id)
                
                neighbors = list(G.neighbors(entity))
                relations = []
                for n in neighbors[:3]: 
                    r = G[entity][n].get('relation', '关联')
                    relations.append(f"{r} -> {n}")
                    # 冲突检测
                    if n in mentioned and any(kw in r for kw in negative_keywords):
                        conflicts.append(f"【{entity}】与【{n}】存在冲突关系: {r}")
                
                entities_data.append({"name": entity, "faction": comm_name, "relations": relations})
            
            return {"entities": entities_data, "conflicts": list(set(conflicts))}
        except Exception as e:
            logger.error(f"获取场景实体信息失败: {e}")
            return None