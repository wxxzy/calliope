import streamlit as st
import logging
from datetime import datetime
from config import load_environment
import config_manager
import vector_store_manager
import workflow_manager
import state_manager
import logger_config
from custom_exceptions import LLMOperationError, ToolOperationError, VectorStoreOperationError, ConfigurationError

# 引入 UI 组件 (v6.0 合并版)
from ui_components.writer_view import render_writer_view
from ui_components.bible_view import render_bible_view
from ui_components.insights_view import render_insights_view
from ui_components.config_view import render_config_view
from core.project_manager import ProjectManager
from dataclasses import asdict, is_dataclass

# --- 初始化 ---
load_environment()
logger_config.setup_logging()
app_logger = logging.getLogger(__name__)

st.set_page_config(page_title="Calliope AI 写作", page_icon="📚", layout="wide")

# 定义需要持久化保存的 Session State 键名
SAVE_KEYS = [
    'project_name', 'collection_name', 'world_bible', 'plan', 
    'research_results', 'outline', 'drafts', 'drafting_index', 
    'final_manuscript', 'outline_sections', 'user_prompt', 
    'selected_tool_id', 'full_draft', 'project_writing_style_id', 
    'project_writing_style_description', 'retrieved_docs',
    'current_critique', 'critique_target_type'
]

def reset_project_state():
    """重置特定项目相关的状态"""
    keys_to_reset = SAVE_KEYS + ['pending_triplets', 'consistency_warning']
    for key in keys_to_reset:
        if key in st.session_state: del st.session_state[key]

def save_and_snapshot():
    """统一执行保存和创建快照的逻辑"""
    if 'collection_name' in st.session_state:
        data_to_save = {k: st.session_state[k] for k in SAVE_KEYS if k in st.session_state}
        if state_manager.save_state_to_file(st.session_state.collection_name, data_to_save):
            ProjectManager.create_snapshot(st.session_state.collection_name)
            st.session_state.last_save_time = datetime.now().strftime("%H:%M:%S")
            return True
    return False

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
            
            # --- 显式状态更新 (副作用隔离的终点) ---
            if result:
                # 兼容旧的字典返回
                if isinstance(result, dict):
                    st.session_state.update(result)
                # 核心：处理新的强类型对象
                elif is_dataclass(result):
                    # 仅更新非 None 的值，防止抹除 UI 状态
                    updates = {k: v for k, v in asdict(result).items() if v is not None}
                    st.session_state.update(updates)

            # 关键步骤自动保存 (保持)
            critical_steps = ["plan", "outline", "generate_draft", "generate_revision", "update_bible"]
            if step_name in critical_steps:
                save_and_snapshot()
                st.toast(f"✅ 进度已同步并备份 ({st.session_state.last_save_time})")

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

def main():
    full_config = config_manager.load_config()
    state_manager.initialize_state_directory()

    # --- 状态同步逻辑 (解决 UI 刷新导致的新值丢失) ---
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
        
        current_col = st.session_state.get('collection_name')
        idx = existing_projects.index(current_col) + 1 if current_col in existing_projects else 0
        selected_option = st.selectbox("项目列表", options=project_selection_options, index=idx)

        if selected_option == "--- 创建新项目 ---":
            name = st.text_input("项目名称", key="new_proj_name_input")
            if st.button("确认创建", width='stretch'):
                if name:
                    reset_project_state()
                    # 统一调用资产创建逻辑
                    internal_name = ProjectManager.create_project(name)
                    st.session_state.project_name = name
                    st.session_state.collection_name = internal_name
                    save_and_snapshot()
                    st.success(f"项目 '{name}' 已创建！")
                    st.rerun()
        elif selected_option != "--- 选择项目 ---" and st.session_state.get('collection_name') != selected_option:
            loaded_data = state_manager.load_state_from_file(selected_option)
            if loaded_data:
                reset_project_state()
                st.session_state.update(loaded_data)
                st.session_state.project_name = loaded_data.get('project_name', selected_option)
                st.info(f"✅ 已恢复项目进度: {selected_option}")
            else:
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
            
            if st.session_state.get("last_save_time"):
                st.caption(f"⏱️ 上次自动保存: {st.session_state.last_save_time}")

            if st.button("💾 手动保存并备份", type="primary", width='stretch'):
                if save_and_snapshot(): st.toast("✅ 快照已手动生成")
            
            # 分支切换请求处理
            if st.session_state.get("load_branch_request"):
                branch_name = st.session_state.load_branch_request
                branch_id = f"{st.session_state.collection_name}_branch_{branch_name}"
                loaded = state_manager.load_state_from_file(branch_id)
                if loaded:
                    st.session_state.update(loaded)
                    st.toast(f"已回溯到分支: {branch_name}")
                del st.session_state.load_branch_request
                st.rerun()

            st.markdown("---")
            with st.expander("☢️ 危险区域", expanded=False):
                if st.checkbox("确定要彻底删除本项目", key="confirm_delete_check"):
                    if st.button("🔥 立即彻底删除", type="secondary", width='stretch'):
                        ProjectManager.delete_project(st.session_state.collection_name)
                        reset_project_state()
                        if 'project_name' in st.session_state: del st.session_state.project_name
                        st.rerun()

    # --- 主界面入口 ---
    if 'project_name' not in st.session_state:
        st.info("👈 请在侧边栏选择或创建一个项目以开始。")
        st.stop()

    st.title(f"项目: {st.session_state.project_name}")
    
    # v6.0 合并版 Tab 布局
    t1, t2, t3, t4 = st.tabs(["🚀 创作中心", "📜 设定圣经", "📈 剧情洞察", "⚙️ 配置"])

    with t1: render_writer_view(full_config, run_step_with_spinner)
    with t2: render_bible_view(st.session_state.collection_name, full_config, run_step_with_spinner)
    with t3: render_insights_view(st.session_state.collection_name)
    with t4: render_config_view(full_config)

if __name__ == "__main__":
    main()