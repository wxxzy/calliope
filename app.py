import streamlit as st
import os
import re
from config import load_environment
import config_manager
import tool_provider
import text_splitter_provider
import vector_store_manager
import workflow_manager
from tools import check_ollama_model_availability

# --- 在应用的最开始加载环境变量 ---
load_environment()

# --- 页面配置 ---
st.set_page_config(page_title="AI 长篇写作智能体 (带记忆)", page_icon="📚", layout="wide")

# --- Helper Functions ---
def sanitize_project_name(name: str) -> str:
    """将项目名称转换为安全的ChromaDB集合名称。"""
    name = re.sub(r'[^\w-]', '_', name)
    name = re.sub(r'__+', '_', name)
    name = name.strip('_')
    if len(name) < 3: name = f"proj_{name}"
    return name.lower()

def reset_project_state():
    """重置与特定项目内容相关的会话状态。"""
    keys_to_reset = ['world_bible', 'plan', 'research_results', 'outline', 'drafts', 'drafting_index', 'final_manuscript', 'outline_sections']
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

def run_step_with_spinner(step_name: str, spinner_text: str):
    """带spinner的运行步骤的通用函数，返回结果。"""
    with st.spinner(spinner_text):
        try:
            result = workflow_manager.run_step(step_name, st.session_state)
            st.success(f"步骤 '{step_name}' 已完成！")
            return result
        except Exception as e:
            st.error(f"执行步骤 '{step_name}' 时发生错误: {e}")
            print(f"详细错误: {e}")
            return None

# ==================================================================
# --- App 启动入口 ---
# ==================================================================
if __name__ == "__main__":
    
    # --- 侧边栏 UI ---
    with st.sidebar:
        st.title("📚 AI 长篇写作智能体")
        
        # --- 项目管理 ---
        st.header("📝 写作项目管理")
        existing_projects = vector_store_manager.list_all_collections()
        project_selection_options = ["--- 选择一个项目 ---"] + existing_projects + ["--- 创建新项目 ---"]
        
        selected_project_index = 0
        if 'collection_name' in st.session_state and st.session_state['collection_name'] in existing_projects:
            selected_project_index = existing_projects.index(st.session_state['collection_name']) + 1

        selected_option = st.selectbox("项目列表", options=project_selection_options, index=selected_project_index, key="project_selector")

        if selected_option == "--- 创建新项目 ---":
            project_name_input = st.text_input("输入新项目名称", key="project_name_input_new")
            if st.button("创建并加载", key="create_and_load_project"):
                if project_name_input:
                    collection_name = sanitize_project_name(project_name_input)
                    if collection_name in existing_projects:
                        st.error(f"项目 '{project_name_input}' 已存在！")
                    else:
                        st.session_state.project_name = project_name_input
                        st.session_state.collection_name = collection_name
                        reset_project_state()
                        with st.spinner(f"正在为新项目 '{project_name_input}' 创建记忆库..."):
                            vector_store_manager.get_or_create_collection(collection_name)
                        st.success(f"项目 '{project_name_input}' 已创建并加载！")
                        st.rerun()
                else:
                    st.error("请输入项目名称！")
        elif selected_option != "--- 选择一个项目 ---" and st.session_state.get('collection_name') != selected_option:
            st.session_state.collection_name = selected_option
            st.session_state.project_name = selected_option
            reset_project_state()
            st.rerun()
        
        st.markdown("---")
        # ... (其他配置UI保持不变，此处省略以保持简洁) ...

    # --- 主界面 UI ---
    if 'project_name' not in st.session_state:
        st.info("👈 请在左侧边栏创建或加载一个写作项目以开始。" )
        st.stop()

    st.title(f"项目: {st.session_state.project_name}")
    
    tab1, tab2 = st.tabs(["主写作流程", "记忆库浏览器"])

    with tab1:
        # --- RENDER MAIN WRITER VIEW ---
        collection_name = st.session_state.collection_name
        vector_store_manager.get_or_create_collection(collection_name) # 确保集合存在

        with st.container(border=True):
            st.subheader("🧠 核心记忆 (世界观)")
            st.text_area("在此输入项目的核心设定...", key="world_bible", height=200)
            if st.button("更新核心记忆"):
                with st.spinner("正在将核心记忆存入向量数据库..."):
                    # active_splitter_id 应该在项目级别配置，暂时硬编码
                    text_splitter = text_splitter_provider.get_text_splitter('default_recursive')
                    vector_store_manager.index_text(collection_name, st.session_state.world_bible, text_splitter, metadata={"source": "world_bible"})
                st.success("核心记忆已更新！")

        with st.container(border=True):
            st.subheader("第一步：规划")
            st.text_area("请输入您的整体写作需求：", key="user_prompt", height=100)
            if st.button("生成写作计划", type="primary"):
                result = run_step_with_spinner("plan", "正在调用“规划师”...")
                if result: st.session_state.update(result)

        if 'plan' in st.session_state:
            st.expander("写作计划").markdown(st.session_state.plan)
            with st.container(border=True):
                st.subheader("第二步：研究")
                user_tools = tool_provider.get_user_tools_config()
                st.selectbox("选择搜索工具:", options=list(user_tools.keys()), key="selected_tool_id")
                if st.button("开始研究", type="primary"):
                    result = run_step_with_spinner("research", f"正在使用工具 '{st.session_state.selected_tool_id}' 进行研究...")
                    if result: st.session_state.update(result)

        if 'research_results' in st.session_state:
            st.expander("研究摘要").markdown(st.session_state.research_results)
            with st.container(border=True):
                st.subheader("第三步：大纲")
                if st.button("生成大纲", type="primary"):
                    result = run_step_with_spinner("outline", "正在调用“大纲师”...")
                    if result: st.session_state.update(result)

        if 'outline' in st.session_state:
            st.expander("文章大纲").markdown(st.session_state.outline)
            with st.container(border=True):
                st.subheader("第四步：撰写 (RAG增强)")
                if st.button("准备撰写 (解析大纲)"):
                    st.session_state.outline_sections = [s.strip() for s in st.session_state.outline.split('\n- ') if s.strip()]
                    st.session_state.drafts = []
                    st.session_state.drafting_index = 0
                
                if 'outline_sections' in st.session_state:
                    total = len(st.session_state.outline_sections)
                    current = st.session_state.get('drafting_index', 0)
                    if current < total:
                        st.info(f"下一章节待撰写: {st.session_state.outline_sections[current].splitlines()[0]}")
                        if st.button(f"撰写章节 {current + 1}/{total}", type="primary"):
                            st.session_state.section_to_write = st.session_state.outline_sections[current]
                            result = run_step_with_spinner("draft", "正在检索记忆并调用“写手”...")
                            if result and "new_draft_content" in result:
                                drafts = st.session_state.get('drafts', [])
                                drafts.append(result["new_draft_content"])
                                st.session_state.drafts = drafts
                                st.session_state.drafting_index += 1
                                st.rerun()
                    else:
                        st.success("所有章节已撰写完毕！")

                if st.session_state.get('drafts'):
                    st.expander("完整初稿").markdown("\n\n".join(st.session_state.drafts))

        if st.session_state.get("drafting_index", 0) > 0 and st.session_state.get("drafting_index") == len(st.session_state.get("outline_sections", [])):
            with st.container(border=True):
                st.subheader("第五步：修订 (RAG增强)")
                if st.button("开始修订全文", type="primary"):
                    st.session_state.full_draft = "\n\n".join(st.session_state.drafts)
                    result = run_step_with_spinner("revise", "“总编辑”正在检索记忆并审阅全文...")
                    if result: st.session_state.update(result)

        if 'final_manuscript' in st.session_state:
            with st.container(border=True):
                st.header("🎉 最终成品")
                st.markdown(st.session_state.final_manuscript)
                st.download_button("下载最终稿件", st.session_state.final_manuscript, file_name=f"{st.session_state.collection_name}_final.md")


    with tab2:
        # --- RENDER VECTOR STORE EXPLORER ---
        st.header("记忆库浏览器")
        collection_name_for_explorer = st.session_state.collection_name
        st.info(f"当前查看的项目记忆库: **{collection_name_for_explorer}**")
        
        with st.spinner("正在从向量数据库加载记忆..."):
            data = vector_store_manager.get_collection_data(collection_name_for_explorer)
        
        if not data or not data['ids']:
            st.warning("当前记忆库为空。")
        else:
            import pandas as pd
            df = pd.DataFrame({
                "ID": data["ids"],
                "内容": [doc[:100] + '...' if len(doc) > 100 else doc for doc in data["documents"]],
                "元数据": data["metadatas"]
            })
            
            st.info("通过勾选行来选择要删除的记忆条目。")
            edited_df = st.data_editor(df, key=f"df_editor_{collection_name_for_explorer}", num_rows="dynamic", column_config={"ID": st.column_config.Column(disabled=True)})
            
            deleted_ids = list(set(df["ID"]) - set(edited_df["ID"]))
            if deleted_ids:
                if st.button("确认删除选中的记忆", type="primary"):
                    with st.spinner(f"正在删除 {len(deleted_ids)} 条记忆..."):
                        vector_store_manager.delete_documents(collection_name_for_explorer, deleted_ids)
                    st.success("删除成功！")
                    st.rerun()