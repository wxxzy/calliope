import streamlit as st
import logging
import re
from datetime import datetime
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
from ui_components.timeline_view import render_timeline_view
from ui_components.analytics_view import render_analytics_view
from core.project_manager import ProjectManager

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
    keys_to_reset = SAVE_KEYS + ['pending_triplets']
    for key in keys_to_reset:
        if key in st.session_state: del st.session_state[key]

def save_and_snapshot():
    """统一执行保存和创建快照的逻辑"""
    if 'collection_name' in st.session_state:
        # 1. 内存同步到磁盘 (Save)
        data_to_save = {k: st.session_state[k] for k in SAVE_KEYS if k in st.session_state}
        if state_manager.save_state_to_file(st.session_state.collection_name, data_to_save):
            # 2. 创建备份副本 (Snapshot)
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
            
            # --- 自动保存逻辑 ---
            critical_steps = ["plan", "outline", "generate_draft", "generate_revision", "update_bible"]
            if step_name in critical_steps:
                save_and_snapshot()
                st.toast(f"✅ 进度已自动保存并创建快照 ({st.session_state.last_save_time})")

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
            name = st.text_input("项目名称", key="new_proj_name_input")
            if st.button("确认创建", use_container_width=True):
                if name:
                    # 1. 先清空旧状态，确保环境干净
                    reset_project_state()
                    
                    # 2. 使用 ProjectManager 统一创建资产
                    internal_name = ProjectManager.create_project(name)
                    
                    # 3. 设置当前项目的标识
                    st.session_state.project_name = name
                    st.session_state.collection_name = internal_name
                    
                    # 4. 立即保存初始存档
                    save_and_snapshot()
                    
                    st.success(f"项目 '{name}' 已创建！")
                    st.rerun()
        elif selected_option != "--- 选择项目 ---" and st.session_state.get('collection_name') != selected_option:
            # 执行项目加载逻辑 (解耦后)
            loaded_data = state_manager.load_state_from_file(selected_option)
            if loaded_data:
                # 先重置再更新，确保干净
                reset_project_state()
                st.session_state.update(loaded_data)
                st.session_state.project_name = loaded_data.get('project_name', selected_option)
                st.info(f"✅ 已恢复项目进度: {selected_option}")
            else:
                # 如果没有存档，则作为新加载
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

            # --- 剧情分支管理 (New: Multi-Verse) ---
            with st.expander("🌌 剧情分支 (Multi-Verse)", expanded=False):
                st.caption("您可以保存当前进度的不同版本，用于探索不同的剧情走向。")
                
                # 创建新分支
                branch_name = st.text_input("新分支名称", placeholder="例如: 结局A-悲剧", key="new_branch_input")
                if st.button("保存当前为新分支", use_container_width=True):
                    if branch_name:
                        # 先保存当前
                        data_to_save = {k: st.session_state[k] for k in SAVE_KEYS if k in st.session_state}
                        state_manager.save_state_to_file(st.session_state.collection_name, data_to_save)
                        # 创建分支
                        if ProjectManager.save_branch(st.session_state.collection_name, branch_name):
                            st.success(f"已开启分支: {branch_name}")
                            st.rerun()
                
                st.markdown("---")
                # 加载已有分支
                branches = ProjectManager.list_branches(st.session_state.collection_name)
                if branches:
                    st.write("现有分支:")
                    for b in branches:
                        if st.button(f"切换到: {b}", key=f"load_branch_{b}", use_container_width=True):
                            # 构建分支对应的文件路径名
                            branch_internal_id = f"{st.session_state.collection_name}_branch_{b}"
                            # 使用 state_manager 加载
                            loaded_data = state_manager.load_state_from_file(branch_internal_id)
                            if loaded_data:
                                # 注意：恢复后我们要把 collection_name 设回正常的
                                st.session_state.update(loaded_data)
                                st.rerun()
                else:
                    st.info("暂无命名分支。")

            if st.button("💾 手动保存并创建快照", type="primary", use_container_width=True):
                if save_and_snapshot():
                    st.toast("✅ 快照已手动生成")
                else:
                    st.error("保存失败")
            
            # --- 危险区域: 删除项目 (New) ---
            st.markdown("---")
            with st.expander("☢️ 危险区域", expanded=False):
                st.warning("删除操作不可撤销，将清除所有文字、记忆和图谱。")
                confirm_delete = st.checkbox("我确定要彻底删除本项目", key="confirm_delete_check")
                if confirm_delete:
                    if st.button("🔥 立即彻底删除", type="secondary", use_container_width=True):
                        col_to_del = st.session_state.collection_name
                        ProjectManager.delete_project(col_to_del)
                        st.success(f"项目 {col_to_del} 已清理。")
                        reset_project_state()
                        # 强行清理关键标识以返回初始界面
                        if 'project_name' in st.session_state: del st.session_state.project_name
                        if 'collection_name' in st.session_state: del st.session_state.collection_name
                        st.rerun()

    # --- 主界面入口 ---
    if 'project_name' not in st.session_state:
        st.info("👈 请在侧边栏选择或创建一个项目以开始。")
        st.stop()

    st.title(f"项目: {st.session_state.project_name}")
    t1, t2, t3, t4, t5, t6 = st.tabs(["写作", "记忆", "图谱", "年表", "分析", "配置"])

    with t1: render_writer_view(full_config, run_step_with_spinner)
    with t2: render_explorer_view(st.session_state.collection_name)
    with t3: render_graph_view(st.session_state.collection_name, full_config, run_step_with_spinner)
    with t4: render_timeline_view(st.session_state.collection_name)
    with t5: render_analytics_view(st.session_state.collection_name)
    with t6: render_config_view(full_config)

if __name__ == "__main__":
    main()
