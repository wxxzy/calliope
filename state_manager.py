import os
import json
import streamlit as st
import logging

# 获取logger实例
app_logger = logging.getLogger(__name__)

# --- 常量定义 ---
PROJECT_STATE_DIR = "data/project_states"

def initialize_state_directory():
    """确保项目状态存储目录存在。"""
    os.makedirs(PROJECT_STATE_DIR, exist_ok=True)

def save_project_state_to_file(collection_name: str):
    """将当前项目相关的会话状态保存到文件。"""
    state_to_save = {}
    # 定义需要保存的会话状态键
    keys_to_save = [
        'project_name', 'collection_name', 'world_bible', 'plan', 
        'research_results', 'outline', 'drafts', 'drafting_index', 
        'final_manuscript', 'outline_sections', 'user_prompt', 
        'selected_tool_id', 'full_draft', 'project_writing_style_id', 
        'project_writing_style_description', 'retrieved_docs'
    ]
    for key in keys_to_save:
        if key in st.session_state:
            state_to_save[key] = st.session_state[key]
    
    # 构建文件路径
    state_file_path = os.path.join(PROJECT_STATE_DIR, f"{collection_name}.json")
    
    try:
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump(state_to_save, f, ensure_ascii=False, indent=4)
        st.success(f"项目 '{collection_name}' 的状态已保存。")
        app_logger.info(f"Project state for '{collection_name}' saved to {state_file_path}")
    except Exception as e:
        st.error(f"保存项目状态失败: {e}")
        app_logger.error(f"Failed to save project state for '{collection_name}': {e}", exc_info=True)

def load_project_state_from_file(collection_name: str):
    """从文件加载项目相关的会话状态。"""
    state_file_path = os.path.join(PROJECT_STATE_DIR, f"{collection_name}.json")
    
    if os.path.exists(state_file_path):
        try:
            with open(state_file_path, 'r', encoding='utf-8') as f:
                loaded_state = json.load(f)
            
            # 将加载的状态合并到 st.session_state
            for key, value in loaded_state.items():
                st.session_state[key] = value
            st.success(f"项目 '{collection_name}' 的状态已加载。")
            app_logger.info(f"Project state for '{collection_name}' loaded from {state_file_path}")
            return True
        except Exception as e:
            st.error(f"加载项目状态失败: {e}")
            app_logger.error(f"Failed to load project state for '{collection_name}': {e}", exc_info=True)
            return False
    else:
        app_logger.info(f"No saved state file found for project '{collection_name}'. A new session will be started.")
        return False
