"""
图谱存储管理 (Graph Store)
负责 NetworkX 图数据的持久化和加载，基于项目路径。
"""
import networkx as nx
import json
import os
import logging
from typing import List, Tuple, Dict

logger = logging.getLogger(__name__)

def get_graph_path(project_root: str) -> str:
    """获取指定项目的图谱文件路径"""
    return os.path.join(project_root, "knowledge", "graph.json")

def load_graph(project_root: str) -> nx.Graph:
    """
    加载项目的知识图谱。如果不存在，返回一个空图。
    """
    path = get_graph_path(project_root)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return nx.node_link_graph(data)
        except Exception as e:
            logger.error(f"加载图谱失败 {project_root}: {e}", exc_info=True)
            return nx.Graph()
    return nx.Graph()

def save_graph(project_root: str, G: nx.Graph):
    """
    保存知识图谱到 JSON 文件。
    """
    path = get_graph_path(project_root)
    try:
        data = nx.node_link_data(G)
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"图谱已保存: {path} (节点数: {G.number_of_nodes()}, 边数: {G.number_of_edges()})")
    except Exception as e:
        logger.error(f"保存图谱失败 {project_root}: {e}", exc_info=True)

def update_graph_from_triplets(project_root: str, triplets: List[Tuple[str, str, str]]):
    """
    根据提取的三元组更新图谱。
    triplets: [(source, relation, target), ...] 
    """
    G = load_graph(project_root)
    updated = False
    
    for triplet in triplets:
        if not isinstance(triplet, (list, tuple)) or len(triplet) != 3:
            continue
            
        source, relation, target = triplet
        if not source or not target or not relation:
            continue
            
        source = source.strip()
        target = target.strip()
        relation = relation.strip()

        if not G.has_node(source):
            G.add_node(source, type="entity")
            updated = True
        if not G.has_node(target):
            G.add_node(target, type="entity")
            updated = True
        
        if G.has_edge(source, target):
            existing_relation = G[source][target].get('relation', '')
            if relation not in existing_relation:
                new_relation = f"{existing_relation}, {relation}" if existing_relation else relation
                G[source][target]['relation'] = new_relation
                updated = True
        else:
            G.add_edge(source, target, relation=relation)
            updated = True
            
    if updated:
        save_graph(project_root, G)
    
    return updated

def get_multi_hop_context(project_root: str, entities: List[str], radius: int = 2) -> str:
    """
    获取多跳邻域上下文。
    """
    G = load_graph(project_root)
    if G.number_of_nodes() == 0:
        return ""

    combined_subgraph = nx.Graph()
    for entity in entities:
        if G.has_node(entity):
            ego = nx.ego_graph(G, entity, radius=radius)
            combined_subgraph = nx.compose(combined_subgraph, ego)

    if combined_subgraph.number_of_nodes() == 0:
        return ""

    context_lines = []
    visited_edges = set()
    
    communities = detect_communities(project_root)
    
    for u, v, d in combined_subgraph.edges(data=True):
        edge_key = tuple(sorted([u, v]))
        if edge_key in visited_edges:
            continue
            
        relation = d.get('relation', '关联')
        u_comm = next((name for name, nodes in communities.items() if u in nodes), "中立/未知")
        v_comm = next((name for name, nodes in communities.items() if v in nodes), "中立/未知")
        
        line = f"- 【{u}】({u_comm}) --[{relation}]--> 【{v}】({v_comm})"
        context_lines.append(line)
        visited_edges.add(edge_key)

    return "\n".join(context_lines)

def detect_communities(project_root: str) -> Dict[str, List[str]]:
    """
    使用 Leiden 或 Greedy 算法识别实体派系。
    """
    G = load_graph(project_root)
    if G.number_of_nodes() < 2:
        return {}

    try:
        import igraph as ig
        import leidenalg
        
        node_list = list(G.nodes())
        node_to_idx = {node: i for i, node in enumerate(node_list)}
        
        edges = []
        for u, v in G.edges():
            edges.append((node_to_idx[u], node_to_idx[v]))
        
        ig_graph = ig.Graph(n=len(node_list), edges=edges)
        partition = leidenalg.find_partition(ig_graph, leidenalg.ModularityVertexPartition)
        
        result = {}
        for i, community_nodes_indices in enumerate(partition):
            comm_nodes = [node_list[idx] for idx in community_nodes_indices]
            result[f"派系_{i+1}"] = comm_nodes
        return result

    except ImportError:
        try:
            from networkx.algorithms import community
            communities_generator = community.greedy_modularity_communities(G)
            result = {}
            for i, comm in enumerate(communities_generator):
                result[f"派系_{i+1}"] = list(comm)
            return result
        except Exception:
            return {}
    except Exception:
        return {}

def detect_triplet_conflicts(project_root: str, new_triplets: List[Tuple[str, str, str]]) -> List[Dict]:
    """
    检测新三元组与现有图谱之间的潜在冲突。
    """
    G = load_graph(project_root)
    conflicts = []
    asymmetric_relations = ["父亲", "母亲", "上级", "主人", "位于"]
    
    for triplet in new_triplets:
        if not isinstance(triplet, (list, tuple)) or len(triplet) != 3:
            continue
        s, r, t = triplet
        
        if G.has_edge(s, t) and r in G[s][t].get('relation', ''):
            continue
            
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

        if ("位于" in r or "身份是" in r) and G.has_node(s):
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

def get_graph_stats(project_root: str) -> Dict:
    G = load_graph(project_root)
    return {
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "density": nx.density(G) if G.number_of_nodes() > 0 else 0
    }

def remove_node(project_root: str, node_id: str):
    G = load_graph(project_root)
    if G.has_node(node_id):
        G.remove_node(node_id)
        save_graph(project_root, G)
        return True
    return False

def add_manual_edge(project_root: str, source: str, relation: str, target: str):
    return update_graph_from_triplets(project_root, [(source, relation, target)])