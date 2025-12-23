"""
项目核心管理模块 (Core Project Manager)
负责项目生命周期的统一调度，协调向量数据库、知识图谱和状态文件。
"""
import os
import re
import logging
import vector_store_manager
import graph_store_manager
import state_manager
import networkx as nx
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = "data/snapshots"

class ProjectManager:
    """
    统一管理项目的生命周期和多维存储资产。
    协调 JSON 状态、ChromaDB 向量库和 NetworkX 关系图。
    """
    
    @staticmethod
    def create_snapshot(internal_name: str):
        """
        为项目创建时间戳快照。
        """
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        source_path = os.path.join(state_manager.PROJECT_STATE_DIR, f"{internal_name}.json")
        
        if not os.path.exists(source_path):
            return False
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = os.path.join(SNAPSHOT_DIR, f"{internal_name}_{timestamp}.json")
        
        try:
            shutil.copy2(source_path, target_path)
            logger.info(f"Snapshot created: {target_path}")
            # 自动清理旧快照
            ProjectManager.cleanup_snapshots(internal_name)
            return True
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return False

    @staticmethod
    def cleanup_snapshots(internal_name: str, keep_count: int = 10):
        """
        清理旧快照，只保留最近的 10 份。
        """
        try:
            if not os.path.exists(SNAPSHOT_DIR): return
            files = [f for f in os.listdir(SNAPSHOT_DIR) if f.startswith(internal_name) and f.endswith(".json")]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(SNAPSHOT_DIR, x)), reverse=True)
            
            if len(files) > keep_count:
                for old_file in files[keep_count:]:
                    os.remove(os.path.join(SNAPSHOT_DIR, old_file))
                logger.info(f"已清理旧快照。")
        except Exception as e:
            logger.error(f"Snapshot cleanup failed: {e}")

    @staticmethod
    def list_projects():
        """
        列出本地所有已存在的项目。
        依据：向量数据库中的集合列表。
        
        Returns:
            List[str]: 项目内部名称列表。
        """
        return vector_store_manager.list_all_collections()

    @staticmethod
    def sanitize_name(name: str) -> str:
        """
        将用户输入的项目名转换为安全的文件系统和数据库集合名称。
        处理特殊字符并确保最小长度。
        
        Args:
            name (str): 用户输入的原始名称。
            
        Returns:
            str: 清洗后的安全名称。
        """
        name = re.sub(r'[^\w-]', '_', name)
        name = re.sub(r'__+', '_', name)
        name = name.strip('_').lower()
        if len(name) < 3: name = f"proj_{name}"
        return name

    @classmethod
    def create_project(cls, display_name: str):
        """
        初始化一个新项目的所有资产。
        包括向量库集合的创建和初始图谱文件的生成。
        
        Args:
            display_name (str): 项目显示名称。
            
        Returns:
            str: 创建成功的内部项目名称。
        """
        internal_name = cls.sanitize_name(display_name)
        logger.info(f"正在为项目 '{internal_name}' 初始化资产...")
        
        # 1. 初始化向量库
        vector_store_manager.get_or_create_collection(internal_name)
        
        # 2. 初始化知识图谱文件
        graph_store_manager.save_graph(internal_name, nx.Graph())
        
        return internal_name

    @staticmethod
    def save_project(internal_name: str):
        """
        持久化当前项目的内存状态到本地 JSON 文件。
        
        Args:
            internal_name (str): 要保存的项目内部名称。
        """
        state_manager.save_project_state_to_file(internal_name)

    @staticmethod
    def delete_project(internal_name: str):
        """
        危险：永久删除一个项目及其所有关联资产（数据库、图谱、状态）。
        
        Args:
            internal_name (str): 要删除的项目内部名称。
        """
        # 1. 删除向量库集合 (New)
        vector_store_manager.delete_collection(internal_name)

        # 2. 删除图谱数据文件
        graph_path = graph_store_manager.get_graph_path(internal_name)
        if os.path.exists(graph_path): os.remove(graph_path)
        
        # 2. 删除派系名称缓存文件
        name_path = graph_store_manager.get_community_names_path(internal_name)
        if os.path.exists(name_path): os.remove(name_path)
        
        # 3. 删除项目 JSON 状态文件
        state_path = os.path.join(state_manager.PROJECT_STATE_DIR, f"{internal_name}.json")
        if os.path.exists(state_path): os.remove(state_path)
        
        logger.warning(f"项目 '{internal_name}' 的所有关联资产已从磁盘移除。")