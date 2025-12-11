import streamlit as st
import os
import re
from config import load_environment
import config_manager
import tool_provider
import text_splitter_provider
import vector_store_manager
import workflow_manager # 导入新的工作流管理器
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

    """带spinner的运行步骤的通用函数，现在返回结果而不是直接修改state。"""

    with st.spinner(spinner_text):

        try:

            result = workflow_manager.run_step(step_name, st.session_state)

            st.success(f"步骤 '{step_name}' 已完成！")

            return result

        except Exception as e:

            st.error(f"执行步骤 '{step_name}' 时发生错误: {e}")

            print(f"详细错误: {e}")

            return None



# --- UI: 侧边栏 ---

def setup_sidebar():

    st.sidebar.title("📚 AI 长篇写作智能体")

    

    # ... (侧边栏的其他部分保持不变) ...



# --- UI: 主界面 ---

def main_app():

    if 'project_name' not in st.session_state:

        st.info("👈 请在左侧边栏创建或加载一个写作项目以开始。")

        st.stop()



    st.title(f"项目: {st.session_state.project_name}")

    collection_name = st.session_state.collection_name

    vector_store_manager.get_or_create_collection(collection_name)



    # --- 核心记忆 ---

    with st.container(border=True):

        st.header("🧠 核心记忆 (世界观)")

        st.text_area("在此输入项目的核心设定...", key="world_bible", height=200)

        if st.button("更新核心记忆"):

            with st.spinner("正在将核心记忆存入向量数据库..."):

                active_splitter_id = st.session_state.get('active_text_splitter', 'default_recursive')

                text_splitter = text_splitter_provider.get_text_splitter(active_splitter_id)

                vector_store_manager.index_text(collection_name, st.session_state.world_bible, text_splitter, metadata={"source": "world_bible"})

            st.success("核心记忆已更新！")



    # --- 步骤 1: 规划 ---

    with st.container(border=True):

        st.header("第一步：规划")

        st.text_area("请输入您的整体写作需求：", key="user_prompt", height=100)

        if st.button("生成写作计划", type="primary"):

            result = run_step_with_spinner("plan", "正在调用“规划师”...")

            if result:

                st.session_state.update(result)



    # --- 后续步骤的UI ---

    if 'plan' in st.session_state:

        st.container(border=True).markdown(st.session_state.plan)

        with st.container(border=True):

            st.header("第二步：研究")

            user_tools = tool_provider.get_user_tools_config()

            st.selectbox("选择搜索工具:", options=list(user_tools.keys()), key="selected_tool_id")

            if st.button("开始研究", type="primary"):

                result = run_step_with_spinner("research", f"正在使用工具 '{st.session_state.selected_tool_id}' 进行研究...")

                if result:

                    st.session_state.update(result)



    if 'research_results' in st.session_state:

        st.container(border=True).markdown(st.session_state.research_results)

        with st.container(border=True):

            st.header("第三步：大纲")

            if st.button("生成大纲", type="primary"):

                result = run_step_with_spinner("outline", "正在调用“大纲师”...")

                if result:

                    st.session_state.update(result)

    

    if 'outline' in st.session_state:

        st.container(border=True).markdown(st.session_state.outline)

        with st.container(border=True):

            st.header("第四步：撰写 (RAG增强)")

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

                            st.session_state.drafts.append(result["new_draft_content"])

                            st.session_state.drafting_index += 1

                            st.rerun()

                else:

                    st.success("所有章节已撰写完毕！")



            if st.session_state.get('drafts'):

                st.expander("完整初稿").markdown("\n\n".join(st.session_state.drafts))



    if st.session_state.get("drafting_index", 0) > 0 and st.session_state.drafting_index == len(st.session_state.get("outline_sections", [])):

        with st.container(border=True):

            st.header("第五步：修订 (RAG增强)")

            if st.button("开始修订全文", type="primary"):

                st.session_state.full_draft = "\n\n".join(st.session_state.drafts)

                result = run_step_with_spinner("revise", "“总编辑”正在检索记忆并审阅全文...")

                if result:

                    st.session_state.update(result)



    if 'final_manuscript' in st.session_state:

        st.container(border=True).markdown(st.session_state.final_manuscript)

        st.download_button("下载最终稿件", st.session_state.final_manuscript, file_name=f"{st.session_state.collection_name}_final.md")



# --- App 启动入口 ---

if __name__ == "__main__":

    setup_sidebar()

    main_app()


