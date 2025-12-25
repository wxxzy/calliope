"""
管理和提供不同LLM（大语言模型）的实例。
这个模块现在完全由 config.yaml 和 provider_templates.yaml 文件驱动。
"""
import os
import importlib
from functools import lru_cache
from config.loader import load_config, load_provider_templates
import logging

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_provider_templates():
    """缓存提供商模板以避免重复读取文件。"""
    return load_provider_templates()

def _get_class_from_path(class_path: str):
    """根据字符串路径动态导入类。"""
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        logger.error(f"无法从路径 '{class_path}' 动态导入类: {e}", exc_info=True)
        raise ImportError(f"无法从路径 '{class_path}' 动态导入类: {e}")

def get_llm(alias: str, temperature: float = 0.7):
    """
    根据别名从配置文件获取并实例化一个 LangChain LLM 实例。

    Args:
        alias (str): 步骤的别名 (e.g., "planner", "drafter")。
        temperature (float): 控制模型创造力的参数。

    Returns:
        A LangChain chat model instance.
    """
    # config每次都重新加载，以反映UI上的动态修改
    config = load_config()
    templates = get_provider_templates()
    
    # 1. 从步骤别名找到模型ID
    model_id = config.get("steps", {}).get(alias)
    if not model_id:
        logger.error(f"在 config.yaml 的 'steps' 部分找不到别名 '{alias}'。")
        raise ValueError(f"错误: 在 config.yaml 的 'steps' 部分找不到别名 '{alias}'。")
        
    # 2. 从模型ID找到模型的用户配置
    user_model_config = config.get("models", {}).get(model_id)
    if not user_model_config:
        logger.error(f"在 config.yaml 的 'models' 部分找不到模型ID '{model_id}'。")
        raise ValueError(f"错误: 在 config.yaml 的 'models' 部分找不到模型ID '{model_id}'。")

    # 3. 从用户配置找到模板ID，再找到提供商模板
    template_id = user_model_config.get("template")
    if not template_id:
        logger.error(f"模型 '{model_id}' 的配置中缺少 'template' 字段。")
        raise ValueError(f"错误: 模型 '{model_id}' 的配置中缺少 'template' 字段。")
    
    provider_template = templates.get(template_id)
    if not provider_template:
        logger.error(f"在提供商模板中找不到模板ID '{template_id}'。")
        raise ValueError(f"错误: 在 provider_templates.yaml 中找不到模板ID '{template_id}'。")

    # 4. 动态导入模型类
    class_path = provider_template.get("class")
    if not class_path:
        logger.error(f"提供商模板 '{template_id}' 中缺少 'class' 路径。")
        raise ValueError(f"错误: 提供商模板 '{template_id}' 中缺少 'class' 路径。")
    
    LLMClass = _get_class_from_path(class_path)

    # 5. 准备构造函数参数
    constructor_params = {"temperature": temperature}
    template_params = provider_template.get("params", {})

    for param_name, param_type in template_params.items():
        user_value = user_model_config.get(param_name)
        if user_value is not None:
            if param_type == "string":
                constructor_params[param_name] = user_value
            elif param_type == "secret_env" or param_type == "url_env":
                env_var_value = os.getenv(user_value)
                if not env_var_value:
                    logger.error(f"模型 '{model_id}' 需要设置环境变量 '{user_value}'，但它未被设置。")
                    raise ValueError(f"错误: 需要为模型 '{model_id}' 设置环境变量 '{user_value}'，但它未被设置。")
                
                # LangChain的构造函数通常需要 'api_key' 或 'base_url'
                # 我们做个映射，例如 'api_key_env' -> 'api_key'
                mapped_param_name = param_name.replace("_env", "")
                constructor_params[mapped_param_name] = env_var_value
    
    logger.info(f"正在实例化模型: {model_id} (类: {LLMClass.__name__})")
    
    # 6. 实例化并返回
    try:
        return LLMClass(**constructor_params)
    except Exception as e:
        logger.error(f"实例化模型 '{model_id}' 失败: {e}\n使用的参数: {constructor_params}", exc_info=True)
        raise ValueError(f"实例化模型 '{model_id}' 失败: {e}\n使用的参数: {constructor_params}")

