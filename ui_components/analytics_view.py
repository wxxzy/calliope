"""
剧情分析视图 (Plot Analytics View)
负责渲染 Tab 6 内容，提供全书张力曲线、实体曝光度及篇幅统计的可视化展示。
"""
import streamlit as st
import vector_store_manager
import pandas as pd

def render_analytics_view(collection_name):
    st.header("📊 剧情数据分析")
    st.info("基于已完成章节的摘要与元数据，实时分析故事走向。")

    # 1. 数据准备
    data = vector_store_manager.get_collection_data(collection_name)
    if not data or not data['ids']:
        st.warning("暂无足够数据进行分析。请先撰写并保存一些章节。")
        return

    chapter_stats = []
    for i, meta in enumerate(data['metadatas']):
        if meta.get('document_type') == 'chapter_summary':
            chapter_stats.append({
                "chapter_index": meta.get('chapter_index', 0),
                "tension": meta.get('tension', 5),
                "entities": meta.get('entities', ""), # 已转换为逗号分隔字符串
                "word_count": len(data['documents'][i]) # 摘要字数，可作为剧情密度的参考
            })
    
    if not chapter_stats:
        st.info("尚未识别到章节元数据。")
        return

    # 按章节顺序排列
    df_stats = pd.DataFrame(chapter_stats).sort_values("chapter_index")
    df_stats['章节'] = df_stats['chapter_index'].apply(lambda x: f"第{x}章")

    # 2. 核心图表展示
    t_col1, t_col2 = st.tabs(["⚡ 戏剧张力曲线", "👥 角色戏份统计"])

    with t_col1:
        st.subheader("全书张力波动图")
        st.caption("分值越高代表冲突越激烈。理想的曲线通常应呈现起伏波动态势。")
        # 准备绘图数据
        chart_data = df_stats.set_index('章节')[['tension']]
        st.line_chart(chart_data, color="#FF4B4B")
        
        # 自动诊断
        avg_tension = df_stats['tension'].mean()
        st.write(f"**AI 诊断报告**: 当前平均张力为 **{avg_tension:.1f}**。")
        if avg_tension < 4:
            st.warning("提示：前期剧情相对平淡，建议在下一章引入突发冲突。")
        elif avg_tension > 8:
            st.warning("提示：剧情持续高压，建议安排一个过渡章节（温情或日常）以缓解读者疲劳。")

    with t_col2:
        st.subheader("实体/角色曝光度")
        st.caption("基于摘要中提到的次数统计（非正文统计，代表角色在核心情节中的重要性）。")
        
        # 统计实体出现次数
        all_mentioned = []
        for e_str in df_stats['entities']:
            if e_str:
                all_mentioned.extend([e.strip() for e in e_str.split(",")])
        
        if all_mentioned:
            entity_counts = pd.Series(all_mentioned).value_counts().reset_index()
            entity_counts.columns = ["实体名称", "出现章节数"]
            
            # 绘制横向柱状图
            st.bar_chart(entity_counts.set_index("实体名称"))
            
            # 矩阵图预览
            with st.expander("查看实体分布明细"):
                st.dataframe(entity_counts, use_container_width=True)
        else:
            st.info("暂未提取到具体的实体关联信息。")

    st.markdown("---")
    # 3. 篇幅分布
    st.subheader("📝 剧情信息密度分布")
    st.caption("反映了各章节摘要的信息承载量。")
    st.bar_chart(df_stats.set_index('章节')[['word_count']])
