import networkx as nx
import json
import os
import logging
from typing import List, Tuple, Dict

logger = logging.getLogger(__name__)

GRAPH_DIR = "data/project_graphs"

def ensure_graph_dir():
    """确保图谱存储目录存在"""
    os.makedirs(GRAPH_DIR, exist_ok=True)

def get_graph_path(collection_name: str) -> str:
    """获取指定项目的图谱文件路径"""
    ensure_graph_dir()
    # 简单的清理文件名逻辑
    safe_name = "".join([c for c in collection_name if c.isalnum() or c in ('_', '-')])
    return os.path.join(GRAPH_DIR, f"{safe_name}_graph.json")

def load_graph(collection_name: str) -> nx.Graph:
    """
    加载项目的知识图谱。如果不存在，返回一个空图。
    使用 NetworkX 的 node_link_graph 格式。
    """
    path = get_graph_path(collection_name)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # networkx 2.x+ 兼容性
            return nx.node_link_graph(data)
        except Exception as e:
            logger.error(f"加载图谱失败 {collection_name}: {e}", exc_info=True)
            return nx.Graph()
    return nx.Graph()

def save_graph(collection_name: str, G: nx.Graph):
    """
    保存知识图谱到 JSON 文件。
    """
    path = get_graph_path(collection_name)
    try:
        data = nx.node_link_data(G)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"图谱已保存: {path} (节点数: {G.number_of_nodes()}, 边数: {G.number_of_edges()})")
    except Exception as e:
        logger.error(f"保存图谱失败 {collection_name}: {e}", exc_info=True)

def update_graph_from_triplets(collection_name: str, triplets: List[Tuple[str, str, str]]):
    """
    根据提取的三元组更新图谱。
    triplets: [(source, relation, target), ...] 
    """
    G = load_graph(collection_name)
    updated = False
    
    for source, relation, target in triplets:
        if not source or not target or not relation:
            continue
            
        # 简单的标准化：去除首尾空格
        source = source.strip()
        target = target.strip()
        relation = relation.strip()

        # 添加节点（如果是新的）
        if not G.has_node(source):
            G.add_node(source, type="entity")
            updated = True
        if not G.has_node(target):
            G.add_node(target, type="entity")
            updated = True
        
        # 添加边（目前我们简单处理：如果是新关系则添加，如果是旧关系则覆盖）
        # 为了支持两个节点间多种关系，我们可以把 relation 作为边的属性存储
        # 简单的 Graph 不支持多重边，这里我们用覆盖策略，或者将关系合并字符串
        
        if G.has_edge(source, target):
            # 检查现有关系
            existing_relation = G[source][target].get('relation', '')
            if relation not in existing_relation:
                new_relation = f"{existing_relation}, {relation}" if existing_relation else relation
                G[source][target]['relation'] = new_relation
                updated = True
        else:
            G.add_edge(source, target, relation=relation)
            updated = True
            
    if updated:
        save_graph(collection_name, G)
    
    return updated

def get_entity_context(collection_name: str, entities: List[str], depth: int = 1) -> str:
    """
    检索图谱上下文：给定一组实体，查找它们的关系网。
    返回自然语言描述的字符串。
    """
    G = load_graph(collection_name)
    if G.number_of_nodes() == 0:
        return ""

    context_lines = []
    visited_edges = set()

    for entity in entities:
        if not G.has_node(entity):
            continue
        
        # 获取一度邻居
        neighbors = list(G.neighbors(entity))
        if not neighbors:
            continue
            
        context_lines.append(f"关于【{entity}】的关系:")
        
        for neighbor in neighbors:
            # 避免重复描述无向边 (A-B 和 B-A)
            edge_key = tuple(sorted([entity, neighbor]))
            if edge_key in visited_edges:
                continue
            
            relation = G[entity][neighbor].get('relation', '关联')
            context_lines.append(f"- {entity} --[{relation}]--> {neighbor}")
            visited_edges.add(edge_key)
    
    return "\n".join(context_lines)

def get_multi_hop_context(collection_name: str, entities: List[str], radius: int = 2) -> str:
    """
    获取多跳邻域上下文。不仅找一度邻居，还找二度邻居。
    """
    G = load_graph(collection_name)
    if G.number_of_nodes() == 0:
        return ""

    combined_subgraph = nx.Graph()
    for entity in entities:
        if G.has_node(entity):
            # 获取半径为 radius 的邻域子图
            ego = nx.ego_graph(G, entity, radius=radius)
            combined_subgraph = nx.compose(combined_subgraph, ego)

    if combined_subgraph.number_of_nodes() == 0:
        return ""

    context_lines = []
    visited_edges = set()
    
    # 获取派系信息
    communities = detect_communities(collection_name)
    
    for u, v, d in combined_subgraph.edges(data=True):
        edge_key = tuple(sorted([u, v]))
        if edge_key in visited_edges:
            continue
            
        relation = d.get('relation', '关联')
        
        # 获取所属派系（如果有）
        u_comm = next((name for name, nodes in communities.items() if u in nodes), "中立/未知")
        v_comm = next((name for name, nodes in communities.items() if v in nodes), "中立/未知")
        
        line = f"- 【{u}】({u_comm}) --[{relation}]--> 【{v}】({v_comm})"
        context_lines.append(line)
        visited_edges.add(edge_key)

    return "\n".join(context_lines)

def detect_communities(collection_name: str) -> Dict[str, List[str]]:
    """
    使用社区发现算法识别实体派系。
    """
    G = load_graph(collection_name)
    if G.number_of_nodes() < 2 or G.number_of_edges() < 1:
        return {}

    try:
        from networkx.algorithms import community
        # 使用贪婪模组度算法
        communities_generator = community.greedy_modularity_communities(G)
        result = {}
        for i, comm in enumerate(communities_generator):
            result[f"派系_{i+1}"] = list(comm)
        return result
    except Exception as e:
        logger.warning(f"社区发现失败: {e}")
        return {}

def detect_triplet_conflicts(collection_name: str, new_triplets: List[Tuple[str, str, str]]) -> List[Dict]:
    """
    检测新三元组与现有图谱之间的潜在冲突。
    """
    G = load_graph(collection_name)
    conflicts = []
    
    # 定义一些具有方向性或排他性的关系关键词
    asymmetric_relations = ["父亲", "母亲", "上级", "主人", "位于"]
    
    for s, r, t in new_triplets:
        # 1. 检测完全重复
        if G.has_edge(s, t) and r in G[s][t].get('relation', ''):
            continue
            
        # 2. 检测反向逻辑冲突 (例如: A是B的父亲, 新提取出B是A的父亲)
        if any(keyword in r for keyword in asymmetric_relations):
            if G.has_edge(t, s):
                existing_r = G[t][s].get('relation', '')
                if any(keyword in existing_r for keyword in asymmetric_relations):
                    conflicts.append({
                        "type": "逻辑反转",
                        "triplet": [s, r, t],
                        "existing": f"{t} --[{existing_r}]--> {s}",
                        "reason": "检测到可能存在冲突的方向性关系"
                    })

        # 3. 检测同源排他性冲突 (例如: 林恩位于A, 新提取出林恩位于B)
        if "位于" in r or "身份是" in r:
            for neighbor in G.neighbors(s):
                existing_r = G[s][neighbor].get('relation', '')
                if r == existing_r and neighbor != t:
                    conflicts.append({
                        "type": "属性冲突",
                        "triplet": [s, r, t],
                        "existing": f"{s} --[{existing_r}]--> {neighbor}",
                        "reason": f"实体 '{s}' 的该属性已有不同记录"
                    })
                    
    return conflicts

def get_graph_stats(collection_name: str) -> Dict:
# ... (保持不变) ...
    """获取图谱统计信息"""
    G = load_graph(collection_name)
    return {
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "density": nx.density(G) if G.number_of_nodes() > 0 else 0
    }
