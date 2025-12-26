"""
Prompt Manager
动态加载并管理 config/prompts.yaml 中的所有 Prompt 模板。
支持运行时热重载。
"""
import yaml
import os
import logging
from functools import lru_cache
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)

PROMPTS_PATH = "config/prompts.yaml"

# --- 热重载缓存层 ---
class PromptCache:
    def __init__(self):
        self._cache = {}
        self._last_modified_time = 0

    def get_prompts(self):
        """获取 Prompts，如果文件被修改则重新加载。"""
        try:
            current_mtime = os.path.getmtime(PROMPTS_PATH)
            if current_mtime > self._last_modified_time:
                logger.info("检测到 prompts.yaml 文件变更，正在热重载...")
                with open(PROMPTS_PATH, 'r', encoding='utf-8') as f:
                    self._cache = yaml.safe_load(f)
                self._last_modified_time = current_mtime
                logger.info("热重载完成！")
        except FileNotFoundError:
            logger.error(f"未找到 Prompts 文件: {PROMPTS_PATH}")
            self._cache = {}
        except Exception as e:
            logger.error(f"加载或重载 Prompts 失败: {e}")
            # 保留旧缓存以防万一
        
        return self._cache

# 创建一个全局的缓存实例
_prompt_cache = PromptCache()


def get_prompt_template(prompt_key: str) -> PromptTemplate:
    """
    根据 Key 获取一个 LangChain PromptTemplate 对象 (支持热重载)。
    
    Args:
        prompt_key (str): 在 prompts.yaml 中定义的键。
    
    Returns:
        PromptTemplate: LangChain 模板对象。
    """
    prompts = _prompt_cache.get_prompts()
    template_str = prompts.get(prompt_key)
    
    if not template_str:
        raise ValueError(f"Prompt key '{prompt_key}' not found in {PROMPTS_PATH}")
        
    return PromptTemplate.from_template(template_str)

# (可选) 提供一个手动重载的接口，用于在 UI 上添加按钮
def force_reload_prompts():
    """手动强制重载 Prompts"""
    _prompt_cache._last_modified_time = 0 # 重置时间戳，下次调用就会强制刷新
    logger.info("已请求手动重载 Prompts。")