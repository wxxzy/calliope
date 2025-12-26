"""
剧情洞察视图 (Insights View) - Sprint 2 回归版
基于 SQLite 高效渲染故事年表与戏剧张力统计。
"""
import streamlit as st
import pandas as pd
from infra.storage import sql_db

def render_insights_view(project_root):
    st.header("📈 剧情洞察与分析")
    
    # 1. 获取数据
    timeline_data = sql_db.get_timeline(project_root)
    
    if not timeline_data:
        st.info("💡 暂无故事数据。请先开始撰写章节，AI 将自动分析并生成年表。")
        return

    t_ins1, t_ins2 = st.tabs(["⏳ 故事年表", "📊 张力与字数"])

    with t_ins1:
        st.subheader("故事时空脉络")
        for item in timeline_data:
            c1, c2 = st.columns([1, 4])
            with c1:
                st.markdown(f"**{item['time']}**")
                st.caption(f"📍 {item['location']}")
            with c2:
                with st.expander(f"第 {item['chapter_index']} 章：情节摘要 (约 {item['word_count']} 字)", expanded=True):
                    st.write(item['summary'])
                    st.progress(item['tension'] / 10.0, text=f"戏剧张力: {item['tension']}")
            st.divider()

    with t_ins2:
        df = pd.DataFrame(timeline_data)
        chart_data = df.copy()
        chart_data['章节'] = chart_data['chapter_index'].apply(lambda x: f"第 {x} 章")
        
        # 戏剧张力曲线
        st.subheader("戏剧张力曲线")
        st.line_chart(chart_data.set_index('章节')[['tension']])
        
        # 字数分布
        st.subheader("章节字数分布")
        st.bar_chart(chart_data.set_index('章节')[['word_count']])
        
        # 统计指标
        st.markdown("---")
        avg_tension = df['tension'].mean()
        total_words = df['word_count'].sum()
        max_tension_row = df.loc[df['tension'].idxmax()]
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("平均剧情张力", f"{avg_tension:.1f}")
        col_m2.metric("总字数", f"{total_words:,}")
        col_m3.metric("最高潮章节", f"第 {int(max_tension_row['chapter_index'])} 章", delta=f"张力: {max_tension_row['tension']}")

        st.caption("注：数据由 AI 在章节撰写完成后自动提取并存储至本地数据库。")
