"""
故事年表视图 (Timeline View)
负责渲染 Tab 5 内容，按故事发生时间展示章节线索和核心元数据。
"""
import streamlit as st
import vector_store_manager
import pandas as pd

def render_timeline_view(collection_name):
    st.header("⏳ 故事年表 (Chronology)")
    st.info("本视图展示了 AI 从各章节中提取的“故事发生时间”和“地理位置”线索。")

    with st.spinner("正在解析时空线索..."):
        # 获取所有数据
        data = vector_store_manager.get_collection_data(collection_name)
    
    if not data or not data['ids']:
        st.warning("暂无章节记忆。开始撰写章节后，AI 会自动提取时间线。")
        return

    # 过滤出章节摘要类型的文档
    chapter_data = []
    for i, meta in enumerate(data['metadatas']):
        if meta.get('document_type') == 'chapter_summary':
            chapter_data.append({
                "id": data['ids'][i],
                "章节": f"第 {meta.get('chapter_index', '?')} 章",
                "content_full": data['documents'][i],
                "故事时间": meta.get('time', '未知'),
                "发生地点": meta.get('location', '未知'),
                "张力指数": meta.get('tension', 5),
                "index": meta.get('chapter_index', 0)
            })
    
    if not chapter_data:
        st.info("尚未生成章节摘要。请先在“主写作流程”中点击“撰写章节”。")
        return

    # 按章节顺序排序 (narrative order)
    chapter_data.sort(key=lambda x: x['index'])

    # --- 时间轴渲染 ---
    for item in chapter_data:
        col_t1, col_t2 = st.columns([1, 4])
        
        with col_t1:
            # 侧边时间标签
            st.markdown(f"### `{item['故事时间']}`")
            st.caption(f"📍 {item['发生地点']}")
            # 张力条展示
            tension = item['张力指数']
            st.progress(tension / 10.0, text=f"冲突强度: {tension}")
            
        with col_t2:
            # 内容卡片
            with st.container(border=True):
                st.markdown(f"**{item['章节']}**")
                st.write(item['content_full'])
                
                # --- 修正功能 (New: Metadata Editor) ---
                with st.popover("🔧 修正时空设定"):
                    st.caption("纠正 AI 自动提取的错误设定")
                    new_time = st.text_input("故事时间", value=item['故事时间'], key=f"edit_time_{item['id']}")
                    new_loc = st.text_input("地理位置", value=item['发生地点'], key=f"edit_loc_{item['id']}")
                    new_tension = st.slider("张力指数", 1, 10, int(item['张力指数']), key=f"edit_ten_{item['id']}")
                    
                    if st.button("💾 保存修改", key=f"save_edit_{item['id']}", use_container_width=True):
                        # 获取原始元数据并更新
                        # 注意：为了更新，我们需要保留所有原始元数据字段，只覆盖修改项
                        original_meta = next((m for j, m in enumerate(data['metadatas']) if data['ids'][j] == item['id']), {})
                        updated_meta = original_meta.copy()
                        updated_meta.update({
                            "time": new_time,
                            "location": new_loc,
                            "tension": new_tension
                        })
                        
                        vector_store_manager.update_document(
                            collection_name, 
                            item['id'], 
                            new_metadata=updated_meta
                        )
                        st.success("设定已同步至向量库！")
                        st.rerun()
        
        st.markdown("---")

    # --- 数据汇总表 ---
    with st.expander("📊 查看时空元数据概览"):
        df = pd.DataFrame(chapter_data).drop(columns=["content_full", "index", "id"])
        st.table(df)
