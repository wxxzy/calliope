"""
知识业务服务 (Knowledge Service)
处理知识图谱提取、派系识别及统一库同步。
已实现与 UI 框架 (Streamlit) 的彻底解耦。
"""
from __future__ import annotations
import logging
from infra.storage import graph_store as graph_store_manager
from infra.storage import vector_store as vector_store_manager
from infra.utils import text_splitters as text_splitter_provider
from core.schemas import KnowledgeResult, ProjectContext
from chains import (
    create_graph_extraction_chain, 
    create_critic_chain, create_consistency_sentinel_chain
)

logger = logging.getLogger(__name__)

class KnowledgeService:
    @staticmethod
    def sync_bible(context: ProjectContext, content: str, full_config: dict) -> KnowledgeResult:
        """统一同步设定"""
        project_root = context.project_root
        # 1. 向量索引
        vector_store_manager.delete_by_metadata(project_root, {"source": "world_bible"})
        text_splitter = text_splitter_provider.get_text_splitter(full_config.get('active_text_splitter', 'default_recursive'))
        vector_store_manager.index_text(project_root, content, text_splitter, metadata={"source": "world_bible"})
        
        # 2. 图谱提取
        graph_res = KnowledgeService.update_graph(context, text_to_extract=content)
        
        return KnowledgeResult(
            bible_synced=True, 
            graph_updated=graph_res.graph_updated, 
            pending_triplets=graph_res.pending_triplets,
            extracted_count=graph_res.extracted_count
        )

    @staticmethod
    def run_critique(context: ProjectContext, writing_style: str, execute_func) -> KnowledgeResult:
        """执行 AI 评审"""
        target_type = context.critique_target_type
        content = context.outline if target_type == "outline" else (context.drafts[-1] if context.drafts else "")
        chain = create_critic_chain(writing_style=writing_style)
        inputs = {"stage": target_type, "plan": context.plan, "content_to_review": content}
        res = execute_func(chain, inputs)
        return KnowledgeResult(current_critique=res)

    @staticmethod
    def update_graph(context: ProjectContext, text_to_extract: str = None) -> KnowledgeResult:
        """提取图谱"""
        text = text_to_extract or context.world_bible
        if not text: return KnowledgeResult()
        
        try:
            triplets = create_graph_extraction_chain().invoke({"text": text})
            if triplets and isinstance(triplets, list):
                current_pending = list(context.pending_triplets)
                new_added = [t for t in triplets if t not in current_pending]
                return KnowledgeResult(graph_updated=True, pending_triplets=current_pending + new_added, extracted_count=len(new_added))
        except Exception as e:
            logger.error(f"图谱提取失败: {e}")
        return KnowledgeResult()

    @staticmethod
    def run_consistency_check(project_root: str, text: str):
        """逻辑哨兵"""
        try:
            G = graph_store_manager.load_graph(project_root)
            mentioned = [node for node in list(G.nodes()) if node.lower() in text.lower()]
            if not mentioned: return "PASS"
            graph_facts = graph_store_manager.get_multi_hop_context(project_root, mentioned, radius=2)
            if not graph_facts: return "PASS"
            return create_consistency_sentinel_chain().invoke({"graph_facts": graph_facts, "chapter_text": text})
        except Exception:
            return "PASS"

    @staticmethod
    def get_scene_entities_info(project_root: str, text: str):
        """分析当前场景涉及的实体信息及潜在冲突"""
        try:
            G = graph_store_manager.load_graph(project_root)
            all_nodes = list(G.nodes())
            mentioned = [node for node in all_nodes if node.lower() in text.lower()]
            
            if not mentioned: return None
            
            communities = graph_store_manager.detect_communities(project_root)
            
            entities_data = []
            conflicts = []
            negative_keywords = ["敌", "仇", "恨", "杀", "背叛", "战", "对立"]

            for entity in mentioned:
                comm_id = next((name for name, nodes in communities.items() if entity in nodes), "未知")
                
                neighbors = list(G.neighbors(entity))
                relations = []
                for n in neighbors[:3]: 
                    r = G[entity][n].get('relation', '关联')
                    relations.append(f"{r} -> {n}")
                    if n in mentioned and any(kw in r for kw in negative_keywords):
                        conflicts.append(f"【{entity}】与【{n}】存在冲突关系: {r}")
                
                entities_data.append({"name": entity, "faction": comm_id, "relations": relations})
            
            return {"entities": entities_data, "conflicts": list(set(conflicts))}
        except Exception as e:
            logger.error(f"获取场景实体信息失败: {e}")
            return None

    @staticmethod
    def quick_update_relation(project_root: str, source: str, relation: str, target: str):
        """快速更新关系"""
        return graph_store_manager.add_manual_edge(project_root, source, relation, target)
