import streamlit as st
import logging
import os
from datetime import datetime
from config import load_environment
from config import loader as config_manager
from infra.storage import vector_store as vector_store_manager
from services import workflow as workflow_manager
from infra.storage import sql_db
from core import logger as logger_config
from core.exceptions import LLMOperationError, ToolOperationError, VectorStoreOperationError, ConfigurationError

# 引入 UI 组件
from ui_components.writer_view import render_writer_view
from ui_components.bible_view import render_bible_view
from ui_components.insights_view import render_insights_view
from ui_components.config_view import render_config_view
from core.project_manager import ProjectManager
from core.schemas import ProjectContext
from dataclasses import asdict, is_dataclass, fields

# --- 初始化 ---
load_environment()
logger_config.setup_logging()
app_logger = logging.getLogger(__name__)

st.set_page_config(page_title="Calliope AI 写作", page_icon="📚", layout="wide")

# 定义需要缓冲更新的 Widget Key
WIDGET_KEYS_TO_BUFFER = ["plan", "research_results", "outline"]

def save_and_snapshot():
    """保存项目状态到 SQLite 并创建数据库快照"""
    project_root = st.session_state.get('project_root')
    if project_root:
        # 只保存 ProjectContext 中定义的业务字段，过滤掉 UI 控件状态
        ctx_fields = {f.name for f in fields(ProjectContext)}
        data_to_save = {k: v for k, v in st.session_state.items() if k in ctx_fields}
        
        if sql_db.save_project_state_to_sql(project_root, data_to_save):
            ProjectManager.create_snapshot(project_root)
            st.session_state.last_save_time = datetime.now().strftime("%H:%M:%S")
            return True
    return False

def run_step_with_spinner(step_name: str, spinner_text: str, full_config: dict):
    """带 Spinner 的步骤运行包装器 (解耦版)"""
    style_desc = st.session_state.get('project_writing_style_description', '')
    output_placeholder = st.empty()
    full_response = ""

    def stream_callback(chunk):
        nonlocal full_response
        full_response += chunk
        output_placeholder.markdown(full_response + "▌")

    # 1. 将 UI 状态封装为领域上下文 (Decoupling point)
    ctx_fields = {f.name for f in fields(ProjectContext)}
    ctx_data = {k: v for k, v in st.session_state.items() if k in ctx_fields}
    context = ProjectContext(**ctx_data)

    with st.spinner(spinner_text):
        try:
            # 2. 调用业务流 (业务流完全不知道 st.session_state)
            result = workflow_manager.run_step(
                step_name, context, full_config, style_desc, stream_callback=stream_callback
            )
            
            if full_response: output_placeholder.markdown(full_response)
            else: output_placeholder.empty()
            
            # 3. 将结果同步回 UI 状态
            if result:
                # 清理已消耗的指令
                if "refinement_instruction" in st.session_state:
                    st.session_state.refinement_instruction = ""
                
                updates = {}
                if isinstance(result, dict):
                    updates = result
                elif is_dataclass(result):
                    updates = {k: v for k, v in asdict(result).items() if v is not None}
                
                safe_updates = {}
                for k, v in updates.items():
                    if k in WIDGET_KEYS_TO_BUFFER:
                        safe_updates[f"new_{k}"] = v
                    else:
                        safe_updates[k] = v
                
                st.session_state.update(safe_updates)

            # 关键步骤自动保存
            critical_steps = ["plan", "outline", "generate_draft", "generate_revision", "update_bible"]
            if step_name in critical_steps:
                save_and_snapshot()
                st.toast(f"✅ 进度已同步 ({st.session_state.last_save_time})")

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

def render_launcher():
    """渲染项目启动器页面"""
    st.title("📚 Calliope AI - 项目启动器")
    
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        st.subheader("📂 打开现有项目")
        # 由于 Streamlit 的 input 限制，我们只能让用户输入路径
        # 或者列出某个默认目录下的文件夹
        default_base_dir = os.path.abspath("./data")
        os.makedirs(default_base_dir, exist_ok=True)
        
        st.caption(f"默认项目目录: {default_base_dir}")
        
        # 扫描有效项目
        projects = []
        if os.path.exists(default_base_dir):
            for d in os.listdir(default_base_dir):
                p_path = os.path.join(default_base_dir, d)
                if os.path.isdir(p_path) and ProjectManager.is_valid_project(p_path):
                    meta = ProjectManager.load_project_meta(p_path)
                    projects.append((d, p_path, meta.get('name', d)))
        
        if projects:
            for dirname, p_path, display_name in projects:
                if st.button(f"📄 {display_name} ({dirname})", key=f"open_{dirname}", use_container_width=True):
                    _load_project(p_path)
        else:
            st.info("暂无项目")

        st.markdown("---")
        manual_path = st.text_input("或输入项目绝对路径:")
        if st.button("打开路径"):
            if ProjectManager.is_valid_project(manual_path):
                _load_project(manual_path)
            else:
                st.error("无效的项目路径 (未找到 project.calliope)")

    with col2:
        st.subheader("✨ 创建新项目")
        new_name = st.text_input("项目名称", placeholder="例如：三体前传")
        new_dir_name = st.text_input("文件夹名称 (英文)", placeholder="three_body_prequel")
        
        base_dir_input = st.text_input("存放位置", value=default_base_dir)
        
        if st.button("立即创建", type="primary"):
            if new_name and new_dir_name:
                target_path = os.path.join(base_dir_input, new_dir_name)
                if os.path.exists(target_path):
                    st.error("目标文件夹已存在！")
                else:
                    if ProjectManager.init_project_structure(target_path, new_name):
                        st.success(f"项目 '{new_name}' 创建成功！")
                        _load_project(target_path)
                    else:
                        st.error("创建失败，请检查日志。")

def _load_project(project_path):
    """加载项目并切换状态 (带安全过滤)"""
    meta = ProjectManager.load_project_meta(project_path)
    state_data = sql_db.load_project_state_from_sql(project_path)
    
    # 清理旧状态
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    
    # --- 安全过滤逻辑 (Sprint 2 增强) ---
    # 只允许加载 ProjectContext 中定义的业务字段和几个必要的系统字段
    ctx_fields = {f.name for f in fields(ProjectContext)}
    system_keys = {"project_root", "project_name", "collection_name", "last_save_time", 
                   "project_writing_style_id", "project_writing_style_description"}
    allowed_keys = ctx_fields | system_keys
    
    safe_state_data = {k: v for k, v in state_data.items() if k in allowed_keys}
    
    # 设置新状态
    st.session_state.update(safe_state_data)
    st.session_state['project_root'] = project_path
    st.session_state['project_name'] = meta.get('name', '未命名项目')
    st.session_state['collection_name'] = project_path # 兼容旧逻辑
    st.rerun()

def render_workspace(full_config):
    """渲染主工作区"""
    with st.sidebar:
        st.title(f"📘 {st.session_state.project_name}")
        st.caption(f"路径: {st.session_state.project_root}")
        
        if st.button("🔙 关闭项目 / 返回启动器"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
            
        st.markdown("---")
        if st.button("💾 手动保存", type="primary", use_container_width=True):
            save_and_snapshot()
            st.toast("✅ 已保存")

    t1, t2, t3, t4 = st.tabs(["🚀 创作中心", "📜 设定圣经", "📈 剧情洞察", "⚙️ 配置"])

    with t1: render_writer_view(full_config, run_step_with_spinner)
    with t2: render_bible_view(st.session_state.collection_name, full_config, run_step_with_spinner)
    with t3: render_insights_view(st.session_state.project_root)
    with t4: render_config_view(full_config)

def main():
    full_config = config_manager.load_config()

    # 状态同步逻辑
    sync_keys = {"new_plan": "plan", "new_research_results": "research_results", "new_outline": "outline"}
    for temp_key, main_key in sync_keys.items():
        if temp_key in st.session_state:
            st.session_state[main_key] = st.session_state[temp_key]
            del st.session_state[temp_key]
    
    if st.session_state.get("clear_specific_refinement"):
        key = st.session_state.clear_specific_refinement
        if key in st.session_state: st.session_state[key] = ""
        del st.session_state.clear_specific_refinement

    # 手动触发保存 (由 UI 组件请求)
    if st.session_state.get("trigger_manual_save"):
        del st.session_state.trigger_manual_save
        save_and_snapshot()

    # 路由逻辑
    if 'project_root' not in st.session_state:
        render_launcher()
    else:
        render_workspace(full_config)

if __name__ == "__main__":
    main()
