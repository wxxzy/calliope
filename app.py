import streamlit as st
import logging
import re
from config import load_environment
import config_manager
import vector_store_manager
import workflow_manager
import state_manager
import logger_config
from custom_exceptions import LLMOperationError, ToolOperationError, VectorStoreOperationError, ConfigurationError

# 引入 UI 组件
from ui_components.writer_view import render_writer_view
from ui_components.explorer_view import render_explorer_view
from ui_components.graph_view import render_graph_view
from ui_components.config_view import render_config_view

# --- 初始化 ---
load_environment()
logger_config.setup_logging()
app_logger = logging.getLogger(__name__)

st.set_page_config(page_title="Calliope AI 写作", page_icon="📚", layout="wide")

def reset_project_state():
    """重置特定项目相关的状态"""
    keys_to_reset = [
        'world_bible', 'plan', 'research_results', 'outline', 'drafts', 
        'drafting_index', 'final_manuscript', 'outline_sections',
        'project_writing_style_id', 'project_writing_style_description',
        'current_critique', 'pending_triplets'
    ]
    for key in keys_to_reset:
        if key in st.session_state: del st.session_state[key]

def run_step_with_spinner(step_name: str, spinner_text: str, full_config: dict):
    """带 Spinner 的步骤运行包装器 (传递给组件使用)"""
    style_desc = st.session_state.get('project_writing_style_description', '')
    output_placeholder = st.empty()
    full_response = ""

    def stream_callback(chunk):
        nonlocal full_response
        full_response += chunk
        output_placeholder.markdown(full_response + "▌")

    with st.spinner(spinner_text):
        try:
            result = workflow_manager.run_step(
                step_name, st.session_state, full_config, style_desc, stream_callback=stream_callback
            )
            if full_response: output_placeholder.markdown(full_response)
            else: output_placeholder.empty()
            st.success(f"步骤 '{step_name}' 完成！")
            return result
        except (LLMOperationError, ToolOperationError, VectorStoreOperationError, ConfigurationError) as e:
            output_placeholder.empty()
            st.error(str(e))
            return None
        except Exception as e:
            output_placeholder.empty()
            st.error(f"未知错误: {e}")
            app_logger.error(f"Error in {step_name}: {e}", exc_info=True)
            return None

# 定义需要持久化保存的 Session State 键名
SAVE_KEYS = [
    'project_name', 'collection_name', 'world_bible', 'plan', 
    'research_results', 'outline', 'drafts', 'drafting_index', 
    'final_manuscript', 'outline_sections', 'user_prompt', 
    'selected_tool_id', 'full_draft', 'project_writing_style_id', 
    'project_writing_style_description', 'retrieved_docs',
    'current_critique', 'critique_target_type'
]

def main():
    full_config = config_manager.load_config()
    state_manager.initialize_state_directory()

    # --- 状态同步逻辑 ---
    sync_keys = {"new_plan": "plan", "new_research_results": "research_results", "new_outline": "outline"}
    for temp_key, main_key in sync_keys.items():
        if temp_key in st.session_state:
            st.session_state[main_key] = st.session_state[temp_key]
            del st.session_state[temp_key]
    
    if st.session_state.get("clear_specific_refinement"):
        key = st.session_state.clear_specific_refinement
        if key in st.session_state: st.session_state[key] = ""
        del st.session_state.clear_specific_refinement

    # --- 侧边栏 ---
    with st.sidebar:
        st.title("📚 Calliope AI")
        st.header("📝 项目管理")
        existing_projects = vector_store_manager.list_all_collections()
        project_selection_options = ["--- 选择项目 ---"] + existing_projects + ["--- 创建新项目 ---"]
        
        # 确定索引
        current_col = st.session_state.get('collection_name')
        idx = existing_projects.index(current_col) + 1 if current_col in existing_projects else 0
        selected_option = st.selectbox("项目列表", options=project_selection_options, index=idx)

        if selected_option == "--- 创建新项目 ---":
            name = st.text_input("项目名称")
            if st.button("创建"):
                if name:
                    col_name = re.sub(r'\W+', '_', name).lower()
                    st.session_state.project_name = name
                    st.session_state.collection_name = col_name
                    reset_project_state()
                    vector_store_manager.get_or_create_collection(col_name)
                    st.rerun()
        elif selected_option != "--- 选择项目 ---" and st.session_state.get('collection_name') != selected_option:
            # 执行项目加载逻辑 (解耦后)
            loaded_data = state_manager.load_state_from_file(selected_option)
            if loaded_data:
                st.session_state.update(loaded_data)
                st.info(f"✅ 已恢复项目: {selected_option}")
            else:
                # 如果没有存档，则视作新加载
                st.session_state.collection_name = selected_option
                st.session_state.project_name = selected_option
                reset_project_state()
            st.rerun()
        
        if st.session_state.get('project_name'):
            st.markdown("---")
            st.info(f"**活跃项目:** {st.session_state.project_name}")
            chaps = len(st.session_state.get('drafts', []))
            words = sum(len(d) for d in st.session_state.get('drafts', []))
            c1, c2 = st.columns(2)
            c1.metric("章节", chaps)
            c2.metric("字数", words)
            
            if st.button("💾 保存进度", type="primary", use_container_width=True):
                # 解耦后的字典保存
                data_to_save = {k: st.session_state[k] for k in SAVE_KEYS if k in st.session_state}
                if state_manager.save_state_to_file(st.session_state.collection_name, data_to_save):
                    st.toast("✅ 进度已保存至磁盘")
                else:
                    st.error("保存失败，请检查日志")

    # --- 主界面入口 ---
    if 'project_name' not in st.session_state:
        st.info("👈 请在侧边栏选择或创建一个项目以开始。")
        st.stop()

    st.title(f"项目: {st.session_state.project_name}")
    t1, t2, t3, t4 = st.tabs(["写作", "记忆", "图谱", "配置"])

    with t1: render_writer_view(full_config, run_step_with_spinner)
    with t2: render_explorer_view(st.session_state.collection_name)
    with t3: render_graph_view(st.session_state.collection_name, full_config, run_step_with_spinner)
    with t4: render_config_view(full_config)

if __name__ == "__main__":
    main()
