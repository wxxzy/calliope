"""
重排器提供商 (Re-ranker Provider)
负责根据 config.yaml 和 user_config.yaml 动态创建和提供重排器模型实例。
"""
import os
import importlib
from functools import lru_cache
from config_manager import CONFIG, load_provider_templates
import logging

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_re_ranker_provider_templates():
    """缓存重排器提供商模板。"""
    templates = load_provider_templates() # 这里假定 provider_templates.yaml 也有 re_rankers 部分
    return templates.get("re_rankers", {})

def _get_class_from_path(class_path: str):
    """根据字符串路径动态导入类。"""
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        logger.error(f"无法从路径 '{class_path}' 动态导入类: {e}", exc_info=True)
        raise ImportError(f"无法从路径 '{class_path}' 动态导入类: {e}")

@lru_cache(maxsize=None)
def get_re_ranker(re_ranker_id: str):
    """
    根据传入的 're_ranker_id' 获取并实例化一个重排器模型。
    此函数被缓存，因此对于相同的ID只会实例化一次。
    """
    re_ranker_templates = get_re_ranker_provider_templates()
    
    if not re_ranker_id:
        logger.debug("未提供重排器ID，返回None。")
        return None
        
    user_re_ranker_config = CONFIG.get("re_rankers", {}).get(re_ranker_id)
    if not user_re_ranker_config:
        logger.error(f"在配置中找不到重排器ID '{re_ranker_id}'。")
        raise ValueError(f"错误: 在配置中找不到重排器ID '{re_ranker_id}'。")

    template_id = user_re_ranker_config.get("template")
    if not template_id:
        logger.error(f"重排器 '{re_ranker_id}' 的配置中缺少 'template' 字段。")
        raise ValueError(f"错误: 重排器 '{re_ranker_id}' 的配置中缺少 'template' 字段。")
    
    provider_template = re_ranker_templates.get(template_id)
    if not provider_template:
        logger.error(f"在重排器模板中找不到模板ID '{template_id}'。")
        raise ValueError(f"错误: 在 re_ranker_templates.yaml 中找不到模板ID '{template_id}'。")
    
    ReRankerClass = _get_class_from_path(provider_template["class"])

    constructor_params = {}
    template_params = provider_template.get("params", {})

    for param_name, param_type in template_params.items():
        user_value = user_re_ranker_config.get(param_name)
        if user_value is not None:
            if param_type == "secret_env":
                env_var_value = os.getenv(user_value)
                if not env_var_value:
                    logger.error(f"重排器 '{re_ranker_id}' 需要设置环境变量 '{user_value}'。")
                    raise ValueError(f"错误: 需要为重排器 '{re_ranker_id}' 设置环境变量 '{user_value}'。")
                constructor_params[param_name] = env_var_value # 例如 API Key
            elif param_type == "string":
                # 特殊处理 CrossEncoder 的 model_name 参数
                if template_id == "sentence_transformers_reranker" and param_name == "model_name":
                    constructor_params["model_name_or_path"] = user_value
                else:
                    constructor_params[param_name] = user_value
                
    logger.info(f"正在实例化重排器: {re_ranker_id} (类: {ReRankerClass.__name__})")
    
    try:
        return ReRankerClass(**constructor_params)
    except Exception as e:
        logger.error(f"实例化重排器 '{re_ranker_id}' 失败: {e}\n使用的参数: {constructor_params}", exc_info=True)
        raise ValueError(f"实例化重排器 '{re_ranker_id}' 失败: {e}\n使用的参数: {constructor_params}")
