"""
项目核心管理模块 (Core Project Manager)
负责项目生命周期的统一调度，采用基于文件夹的项目结构。
"""
import os
import json
import logging
import networkx as nx
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

class ProjectManager:
    """
    统一管理项目的生命周期。
    现在基于文件夹路径来管理项目资产。
    """
    
    @staticmethod
    def init_project_structure(project_root: str, project_name: str):
        """
        在指定路径初始化一个新的项目结构。
        
        Args:
            project_root (str): 项目根目录的绝对路径。
            project_name (str): 项目名称。
        
        Returns:
            bool: 是否成功。
        """
        try:
            os.makedirs(project_root, exist_ok=True)
            
            # 1. 创建子目录
            knowledge_dir = os.path.join(project_root, "knowledge")
            os.makedirs(knowledge_dir, exist_ok=True)
            
            # 2. 创建元数据文件
            meta_path = os.path.join(project_root, "project.calliope")
            metadata = {
                "name": project_name,
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
                "format": "folder_based"
            }
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 3. 初始化空图谱
            graph_path = os.path.join(knowledge_dir, "graph.json")
            if not os.path.exists(graph_path):
                empty_graph = nx.node_link_data(nx.Graph())
                with open(graph_path, 'w', encoding='utf-8') as f:
                    json.dump(empty_graph, f, ensure_ascii=False, indent=2)

            logger.info(f"项目 '{project_name}' 已在 '{project_root}' 初始化。")
            return True
        except Exception as e:
            logger.error(f"初始化项目失败: {e}", exc_info=True)
            return False

    @staticmethod
    def is_valid_project(project_root: str) -> bool:
        """检查指定目录是否是一个有效的 Calliope 项目"""
        if not os.path.exists(project_root): return False
        meta_path = os.path.join(project_root, "project.calliope")
        return os.path.exists(meta_path)

    @staticmethod
    def load_project_meta(project_root: str) -> dict:
        """加载项目元数据"""
        meta_path = os.path.join(project_root, "project.calliope")
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def create_snapshot(project_root: str):
        """
        为项目创建快照 (备份 content.db)。
        """
        snapshots_dir = os.path.join(project_root, "snapshots")
        os.makedirs(snapshots_dir, exist_ok=True)
        
        source_path = os.path.join(project_root, "content.db")
        if not os.path.exists(source_path): return False
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = os.path.join(snapshots_dir, f"content_{timestamp}.db")
        
        try:
            shutil.copy2(source_path, target_path)
            # 清理旧快照
            files = [f for f in os.listdir(snapshots_dir) if f.startswith("content_") and f.endswith(".db")]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(snapshots_dir, x)), reverse=True)
            if len(files) > 10:
                for old in files[10:]:
                    os.remove(os.path.join(snapshots_dir, old))
            return True
        except Exception as e:
            logger.error(f"创建快照失败: {e}")
            return False