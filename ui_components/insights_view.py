"""
剧情洞察视图 (Insights View)
v6.0 合并版：整合了故事年表、数据统计分析以及平行时空分支管理。
"""
import streamlit as st
import vector_store_manager
import pandas as pd
from core.project_manager import ProjectManager

def render_insights_view(collection_name):
    st.header("📈 剧情洞察与分析")
    
    t_ins1, t_ins2, t_ins3 = st.tabs(["⏳ 故事年表", "📊 深度统计", "🌌 剧情分支"])

    with t_ins1:
        # 复用之前的 timeline 逻辑
        data = vector_store_manager.get_collection_data(collection_name)
        chapter_data = []
        for i, meta in enumerate(data['metadatas']):
            if meta.get('document_type') == 'chapter_summary':
                chapter_data.append({
                    "id": data['ids'][i],
                    "章节": f"第 {meta.get('chapter_index', '?')} 章",
                    "content": data['documents'][i],
                    "time": meta.get('time', '未知'),
                    "location": meta.get('location', '未知'),
                    "tension": meta.get('tension', 5),
                    "index": meta.get('chapter_index', 0)
                })
        chapter_data.sort(key=lambda x: x['index'])
        for item in chapter_data:
            c1, c2 = st.columns([1, 4])
            c1.markdown(f"**{item['time']}**")
            c1.caption(f"📍 {item['location']}")
            c2.info(f"{item['章节']}: {item['content']}")
            st.divider()

    with t_ins2:
        # 复用之前的 analytics 逻辑
        if chapter_data:
            df = pd.DataFrame(chapter_data)
            st.subheader("戏剧张力曲线")
            st.line_chart(df.set_index('章节')[['tension']])
            st.subheader("字数分布")
            st.bar_chart(df.set_index('章节')[['tension']]) # 示例
        else:
            st.info("暂无统计数据。")

    with t_ins3:
        st.subheader("平行时空管理")
        st.write("保存当前进度的不同版本点。")
        b_name = st.text_input("给当前进度起个名 (如: 结局A)")
        if st.button("创建新分支点"):
            if ProjectManager.save_branch(collection_name, b_name):
                st.success("分支已创建")
                st.rerun()
        
        st.markdown("---")
        branches = ProjectManager.list_branches(collection_name)
        for b in branches:
            if st.button(f"🌀 回溯到: {b}", key=f"br_{b}"):
                # 触发回溯逻辑 (由 app.py 捕获)
                st.session_state.load_branch_request = b
                st.rerun()
