import streamlit as st
import vector_store_manager
import pandas as pd

def render_explorer_view(collection_name):
    st.header("记忆库浏览器")
    st.info(f"当前查看的项目记忆库: **{collection_name}**")
    
    with st.spinner("正在从向量数据库加载记忆..."):
        data = vector_store_manager.get_collection_data(collection_name)
    
    if not data or not data['ids']:
        st.warning("当前记忆库为空。")
    else:
        # 构造带有勾选框的数据框
        df = pd.DataFrame({
            "选择": [False] * len(data["ids"]),
            "ID": data["ids"],
            "内容摘要": [doc[:100] + '...' if len(doc) > 100 else doc for doc in data["documents"]],
            "来源": [m.get('source', '未知') for m in data["metadatas"]]
        })
        
        st.info("💡 勾选左侧的“选择”框，然后点击下方的删除按钮。")
        
        # 使用 data_editor 展示，仅允许修改“选择”列
        edited_df = st.data_editor(
            df, 
            key=f"df_editor_{collection_name}", 
            hide_index=True,
            column_config={
                "选择": st.column_config.CheckboxColumn(required=True),
                "ID": st.column_config.Column(disabled=True),
                "内容摘要": st.column_config.Column(disabled=True),
                "来源": st.column_config.Column(disabled=True)
            }
        )
        
        # 获取勾选为 True 的 ID
        selected_indices = edited_df[edited_df["选择"] == True].index
        ids_to_delete = [df.iloc[i]["ID"] for i in selected_indices]

        if ids_to_delete:
            st.warning(f"即将删除 {len(ids_to_delete)} 条记忆。")
            if st.button("🔥 确认执行批量删除", type="secondary", use_container_width=True):
                with st.spinner(f"正在移除索引..."):
                    vector_store_manager.delete_documents(collection_name, ids_to_delete)
                st.success(f"已成功删除 {len(ids_to_delete)} 条记忆条目！")
                st.rerun()
