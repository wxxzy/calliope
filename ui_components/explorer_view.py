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
        df = pd.DataFrame({
            "ID": data["ids"],
            "内容": [doc[:100] + '...' if len(doc) > 100 else doc for doc in data["documents"]],
            "元数据": data["metadatas"]
        })
        
        st.info("通过勾选行来选择要删除的记忆条目。")
        edited_df = st.data_editor(df, key=f"df_editor_{collection_name}", num_rows="dynamic", column_config={"ID": st.column_config.Column(disabled=True)})
        
        deleted_ids = list(set(df["ID"]) - set(edited_df["ID"]))
        if deleted_ids:
            if st.button("确认删除选中的记忆", type="primary"):
                with st.spinner(f"正在删除 {len(deleted_ids)} 条记忆..."):
                    vector_store_manager.delete_documents(collection_name, deleted_ids)
                st.success("删除成功！")
                st.rerun()
