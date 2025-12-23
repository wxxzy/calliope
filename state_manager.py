"""
项目状态持久化工具 (State Manager)
负责将字典数据保存至 JSON 文件或从中读取。
本模块已与 UI 框架解耦，可用于任何 Python 环境。
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

# 项目状态存储目录
PROJECT_STATE_DIR = "data/project_states"

def initialize_state_directory():
    """确保存储目录存在"""
    os.makedirs(PROJECT_STATE_DIR, exist_ok=True)

def save_state_to_file(collection_name: str, state_data: dict):
    """
    将状态字典保存到本地 JSON 文件。
    
    Args:
        collection_name (str): 集合/项目唯一标识。
        state_data (dict): 要保存的数据字典。
    """
    initialize_state_directory()
    path = os.path.join(PROJECT_STATE_DIR, f"{collection_name}.json")
    
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False, indent=4)
        logger.info(f"项目状态已保存至: {path}")
        return True
    except Exception as e:
        logger.error(f"保存项目状态失败: {e}", exc_info=True)
        return False

def load_state_from_file(collection_name: str) -> dict:
    """
    从本地文件加载状态。
    
    Args:
        collection_name (str): 项目唯一标识。
        
    Returns:
        dict: 加载的数据字典，若失败则返回空字典。
    """
    path = os.path.join(PROJECT_STATE_DIR, f"{collection_name}.json")
    
    if not os.path.exists(path):
        logger.info(f"未找到项目 '{collection_name}' 的存档文件。")
        return {}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载项目状态失败: {e}", exc_info=True)
        return {}