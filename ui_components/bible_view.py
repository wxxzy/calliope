"""
项目设定圣经视图 (Project Bible View)
v6.0 合并版：整合了文字设定、交互式图谱以及实体关系管理。
"""
import streamlit as st
from infra.storage import graph_store as graph_store_manager
import networkx as nx
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config

def render_bible_view(collection_name, full_config, run_step_with_spinner_func):
    st.header("📜 项目设定圣经")
    st.info("在这里统一管理世界观设定、地理位置及人物关系网。")

    # 1. 文字设定区 (原本在写作视图)
    with st.container(border=True):
        st.subheader("📚 核心文字设定")
        st.text_area(
            "世界观/人物小传/地理百科", 
            key="world_bible", 
            height=250,
            help="在这里输入长段的文字设定，点击下方按钮可同步至向量库并自动更新图谱。"
        )
        if st.button("🚀 统一同步 (向量库 + 知识图谱)", width='stretch', type="primary"):
            result = run_step_with_spinner_func("update_bible", "正在进行多维知识沉淀...", full_config)
            if result and getattr(result, "bible_synced", False):
                st.success(f"同步成功！识别到 {getattr(result, 'extracted_count', 0)} 条新关系。")
                st.rerun()

    st.markdown("---")

    # 2. 图谱可视化区
    st.subheader("🕸️ 势力关系网")
    stats = graph_store_manager.get_graph_stats(collection_name)
    col_s1, col_s2 = st.columns(2)
    col_s1.caption(f"节点: {stats['node_count']} | 关系: {stats['edge_count']}")
    
    if st.button("🗑️ 清空图谱数据", type="secondary", help="仅清除图谱，不影响向量库文本"):
        graph_store_manager.save_graph(collection_name, nx.Graph())
        st.rerun()

    # 待审核逻辑
    if st.session_state.get("pending_triplets"):
        with st.expander("📋 发现新关系，待审核入库", expanded=True):
            pending = st.session_state.pending_triplets
            conflicts = graph_store_manager.detect_triplet_conflicts(collection_name, pending)
            display_data = []
            for i, t in enumerate(pending):
                if len(t) != 3: continue
                conflict = next((c for c in conflicts if c["triplet"] == list(t)), None)
                display_data.append({
                    "状态": "⚠️ 冲突" if conflict else "✅ 正常",
                    "源实体": t[0], "关系": t[1], "目标实体": t[2],
                    "备注": conflict["reason"] if conflict else ""
                })
            edited_df = st.data_editor(pd.DataFrame(display_data), hide_index=True)
            if st.button("确认合并选中项"):
                approved = [(row["源实体"], row["关系"], row["目标实体"]) for _, row in edited_df.iterrows()]
                graph_store_manager.update_graph_from_triplets(collection_name, approved)
                del st.session_state.pending_triplets
                st.rerun()

    G = graph_store_manager.load_graph(collection_name)
    if G.number_of_nodes() > 0:
        communities = graph_store_manager.detect_communities(collection_name)
        nodes = []
        color_palette = ["#FF4B4B", "#1C83E1", "#00D4FF", "#7DCEA0", "#F4D03F", "#EB984E", "#A569BD"]
        for node_id in G.nodes():
            comm_index = next((i for i, (n, m) in enumerate(communities.items()) if node_id in m), -1)
            color = color_palette[comm_index % len(color_palette)] if comm_index != -1 else "#E6E6E6"
            nodes.append(Node(id=node_id, label=node_id, size=25, color=color))
        edges = [Edge(source=u, target=v, label=d.get('relation', ''), color="#808080", type="CURVE") for u, v, d in G.edges(data=True)]
        agraph(nodes=nodes, edges=edges, config=Config(width=1000, height=500, physics=True))

        # 3. 在线管理
        with st.expander("🛠️ 实体与关系维护中心", expanded=False):
            tab_edit1, tab_edit2, tab_edit3 = st.tabs(["关系网编辑器", "实体词条管理", "自动提取审核"])
            
            with tab_edit1:
                st.write("**手动织网**")
                col_n1, col_n2, col_n3, col_n4 = st.columns([2,2,2,1])
                ns = col_n1.text_input("主体", key="m_s", placeholder="林恩")
                nr = col_n2.text_input("连接关系", key="m_r", placeholder="宿敌")
                nt = col_n3.text_input("客体", key="m_t", placeholder="艾瑞克")
                if col_n4.button("织网", width='stretch'):
                    if ns and nr and nt:
                        graph_store_manager.add_manual_edge(collection_name, ns, nr, nt)
                        st.rerun()
                
                st.write("**现有关系修正**")
                # 提取当前所有边
                edges_list = []
                for u, v, d in G.edges(data=True):
                    edges_list.append({"源": u, "关系描述": d.get('relation', '关联'), "目标": v})
                
                df_edges = pd.DataFrame(edges_list)
                edited_df = st.data_editor(
                    df_edges, 
                    key="bible_graph_editor", 
                    num_rows="dynamic",
                    width='stretch',
                    column_config={
                        "关系描述": st.column_config.TextColumn(required=True),
                        "源": st.column_config.Column(disabled=True),
                        "目标": st.column_config.Column(disabled=True)
                    }
                )
                
                if st.button("💾 确认同步修改至全书图谱", type="primary"):
                    # 识别修改：目前采取最稳妥的全量同步策略
                    new_G = nx.Graph()
                    for _, row in edited_df.iterrows():
                        if row["源"] and row["目标"]:
                            new_G.add_edge(row["源"], row["目标"], relation=row["关系描述"])
                    graph_store_manager.save_graph(collection_name, new_G)
                    st.success("图谱同步成功！")
                    st.rerun()

            with tab_edit2:
                st.write("**实体清单与清理**")
                nodes_data = []
                communities = graph_store_manager.detect_communities(collection_name)
                
                for node in G.nodes():
                    comm_id = next((n for n, m in communities.items() if node in m), "未知")
                    nodes_data.append({
                        "实体名": node,
                        "所属派系": comm_id,
                        "关系深度": G.degree(node)
                    })
                
                st.table(pd.DataFrame(nodes_data))
                
                to_del = st.multiselect("彻底移除实体 (慎重)", list(G.nodes()), key="del_nodes_ms")
                if st.button("🗑️ 确认删除选中实体"):
                    for n in to_del: graph_store_manager.remove_node(collection_name, n)
                    st.rerun()

            with tab_edit3:
                st.write("**AI 自动发现的关系审核**")
                if st.session_state.get("pending_triplets"):
                    pending = st.session_state.pending_triplets
                    conflicts = graph_store_manager.detect_triplet_conflicts(collection_name, pending)
                    display_data = []
                    for i, t in enumerate(pending):
                        if not isinstance(t, (list, tuple)) or len(t) != 3: continue
                        conflict = next((c for c in conflicts if c["triplet"] == list(t)), None)
                        display_data.append({
                            "状态": "⚠️ 冲突" if conflict else "✅ 正常",
                            "源实体": t[0], "关系": t[1], "目标实体": t[2],
                            "备注": conflict["reason"] if conflict else "待入库"
                        })
                    
                    df_rev = pd.DataFrame(display_data)
                    edited_rev = st.data_editor(df_rev, key="pending_review_editor", width='stretch')
                    
                    c_rev1, c_rev2 = st.columns(2)
                    if c_rev1.button("📥 合并已确认关系", type="primary", width='stretch'):
                        approved = [(row["源实体"], row["关系"], row["目标实体"]) for _, row in edited_rev.iterrows()]
                        graph_store_manager.update_graph_from_triplets(collection_name, approved)
                        del st.session_state.pending_triplets
                        st.rerun()
                    if c_rev2.button("🧹 忽略全部提取", width='stretch'):
                        del st.session_state.pending_triplets
                        st.rerun()
                else:
                    st.info("当前没有待审核的自动提取结果。")
    else:
        st.info("图谱目前为空。请在上方输入世界观并同步。")
