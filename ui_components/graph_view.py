"""
知识图谱视图 (Knowledge Graph View)
负责渲染 Tab 3 内容，包含图谱可视化、社区发现、冲突审核以及在线编辑功能。
"""
import streamlit as st
import graph_store_manager
import workflow_manager
import networkx as nx
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config

def render_graph_view(collection_name, full_config, run_step_with_spinner_func):
    """
    渲染知识图谱管理界面。
    
    Args:
        collection_name (str): 当前项目的内部标识名。
        full_config (dict): 合并后的系统配置。
        run_step_with_spinner_func (callable): UI 加载包装函数。
    """
    st.header("🕸️ 项目知识图谱")
    
    # 1. 核心指标统计
    stats = graph_store_manager.get_graph_stats(collection_name)
    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("实体总数 (Nodes)", stats["node_count"])
    col_s2.metric("关系总数 (Edges)", stats["edge_count"])
    col_s3.metric("图连接密度", f"{stats['density']:.3f}")

    st.markdown("---")
    
    # 2. 图谱操作按钮
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 扫描文本提取关系", help="分析核心记忆或最新章节内容并抽取三元组"):
            # 优先扫描世界观设定，如果没有则扫描最后一章草稿
            text_to_scan = st.session_state.world_bible if st.session_state.world_bible else ""
            if not text_to_scan and st.session_state.get("drafts"):
                text_to_scan = st.session_state.drafts[-1]
            
            if text_to_scan:
                st.session_state.text_to_extract = text_to_scan
                result = run_step_with_spinner_func("update_graph", "AI 正在理解并建立关系网...", full_config)
                if result and result.get("extracted_triplets"):
                    st.session_state.pending_triplets = result.get("extracted_triplets")
                    st.rerun()
            else:
                st.warning("没有可扫描的文本内容（核心记忆或草稿为空）。")
    with c2:
         if st.button("🗑️ 彻底清空主图谱", type="secondary", help="清除当前项目的所有实体关系，不可恢复"):
             graph_store_manager.save_graph(collection_name, nx.Graph())
             st.warning("图谱数据已重置。")
             st.rerun()

    # 3. 待审核列表 (Phase 3: Human-in-the-loop)
    if st.session_state.get("pending_triplets"):
        st.markdown("---")
        st.subheader("📋 待入库的新关系")
        st.info("AI 刚才发现了一些新线索！请审核并确认是否合并到主图谱中。")
        
        pending = st.session_state.pending_triplets
        conflicts = graph_store_manager.detect_triplet_conflicts(collection_name, pending)
        
        display_data = []
        for i, triplet in enumerate(pending):
            if len(triplet) != 3: continue
            s, r, t = triplet
            # 标记潜在的逻辑冲突
            conflict = next((c for c in conflicts if c["triplet"] == [s, r, t]), None)
            status = "⚠️ 冲突" if conflict else "✅ 正常"
            note = conflict["reason"] if conflict else "新提取"
            display_data.append({"ID": i, "状态": status, "源实体": s, "关系": r, "目标实体": t, "备注": note})
        
        df_pending = pd.DataFrame(display_data)
        edited_df = st.data_editor(
            df_pending, 
            key="pending_triplets_editor",
            num_rows="fixed",
            disabled=["状态", "备注"],
            hide_index=True
        )

        col_sub1, col_sub2 = st.columns(2)
        if col_sub1.button("✅ 确认合并入库", type="primary"):
            approved_triplets = []
            for _, row in edited_df.iterrows():
                approved_triplets.append((row["源实体"], row["关系"], row["目标实体"]))
            if approved_triplets:
                graph_store_manager.update_graph_from_triplets(collection_name, approved_triplets)
                st.success(f"成功合并 {len(approved_triplets)} 条关系！")
                del st.session_state.pending_triplets
                st.rerun()
        if col_sub2.button("❌ 放弃这些提取"):
            del st.session_state.pending_triplets
            st.rerun()

    # 4. 交互式可视化图谱 (Phase 2: Interactive Viz)
    st.markdown("---")
    st.subheader("🕸️ 交互式势力关系图")
    G = graph_store_manager.load_graph(collection_name)
    communities = {}
    
    if G.number_of_nodes() > 0:
        # 识别派系
        communities = graph_store_manager.detect_communities(collection_name)
        
        # 准备可视化节点和边
        nodes = []
        # 定义派系颜色
        color_palette = ["#FF4B4B", "#1C83E1", "#00D4FF", "#7DCEA0", "#F4D03F", "#EB984E", "#A569BD"]
        
        for node_id in G.nodes():
            comm_index = -1
            for i, (name, members) in enumerate(communities.items()):
                if node_id in members:
                    comm_index = i
                    break
            node_color = color_palette[comm_index % len(color_palette)] if comm_index != -1 else "#E6E6E6"
            nodes.append(Node(id=node_id, label=node_id, size=25, color=node_color))

        edges = [Edge(source=u, target=v, label=d.get('relation', ''), color="#808080", type="CURVE") for u, v, d in G.edges(data=True)]
        
        # 可视化配置
        config = Config(
            width=1000, 
            height=600, 
            directed=False, 
            physics=True, 
            nodeHighlightBehavior=True, 
            highlightColor="#F7A7A7", 
            collapsible=True, 
            staticGraph=False
        )
        # 渲染图表
        agraph(nodes=nodes, edges=edges, config=config)

    # 5. 派系分析与命名
    if communities:
        st.subheader("👥 阵营/派系划分")
        cached_names = graph_store_manager.load_cached_community_names(collection_name)
        
        if st.button("🎭 重新识别派系并自动命名"):
            # 将待命名的数据暂存入 state，由 workflow_manager 转发给 Service
            st.session_state.communities_for_naming = communities
            result = run_step_with_spinner_func("run_naming", "AI 正在分析各势力特征并起名...", full_config)
            if result:
                cached_names = result # 更新本地显示用的变量
            st.success("命名与分析同步完成！")
            st.rerun()

        # 展示派系详情
        cols = st.columns(len(communities))
        for i, (temp_id, nodes_list) in enumerate(communities.items()):
            display_name = cached_names.get(temp_id, temp_id)
            cols[i].markdown(f"**{display_name}**")
            cols[i].write(", ".join(nodes_list))

        # 6. 在线编辑管理 (Phase 3: Online Editor)
        st.markdown("---")
        st.subheader("🛠️ 在线编辑器 (3.0)")
        tab_edit1, tab_edit2 = st.tabs(["关系修正", "实体/节点管理"])
        
        with tab_edit1:
            st.write("**手动新增硬设定**")
            ce1, ce2, ce3, ce4 = st.columns([2, 2, 2, 1])
            new_s = ce1.text_input("源实体", key="manual_s", placeholder="林恩")
            new_r = ce2.text_input("关系", key="manual_r", placeholder="宿敌")
            new_t = ce3.text_input("目标实体", key="manual_t", placeholder="艾瑞克")
            if ce4.button("立即添加", width='stretch'):
                if new_s and new_r and new_t:
                    graph_store_manager.add_manual_edge(collection_name, new_s, new_r, new_t)
                    st.rerun()
            
            st.write("**现有关系在线修正**")
            edges_data = [{"源实体": u, "关系": d.get('relation', '关联'), "目标实体": v} for u, v, d in G.edges(data=True)]
            edited_edges = st.data_editor(
                pd.DataFrame(edges_data), 
                key="main_graph_editor", 
                num_rows="dynamic"
            )
            if st.button("💾 同步保存表格修改"):
                new_G = nx.Graph()
                for _, row in edited_edges.iterrows():
                    new_G.add_edge(row["源实体"], row["目标实体"], relation=row["关系"])
                graph_store_manager.save_graph(collection_name, new_G)
                st.rerun()
                
        with tab_edit2:
            st.write("**节点快速清理**")
            all_nodes = list(G.nodes())
            if all_nodes:
                selected_node_to_del = st.multiselect("选择要彻底移除的实体 (将同时删除其所有关系):", options=all_nodes)
                if st.button("🗑️ 确认删除选中节点", type="secondary"):
                    for node in selected_node_to_del:
                        graph_store_manager.remove_node(collection_name, node)
                    st.rerun()
            else:
                st.info("图谱目前没有可管理的实体。")
    else:
        st.info("图谱目前为空。请尝试从核心记忆提取设定。")