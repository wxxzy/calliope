"""
Embedding Provider
负责根据配置动态创建和提供LangChain的Embedding模型实例。
"""
import os
import importlib
from functools import lru_cache
from config_manager import load_config, load_provider_templates
import logging

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_embedding_provider_templates():
    """缓存Embedding模型提供商模板。"""
    templates = load_provider_templates()
    return templates.get("embeddings", {})

def _get_class_from_path(class_path: str):
    """根据字符串路径动态导入类。"""
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        logger.error(f"无法从路径 '{class_path}' 动态导入类: {e}", exc_info=True)
        raise ImportError(f"无法从路径 '{class_path}' 动态导入类: {e}")

def get_embedding_model():
    """
    根据配置文件中的 'active_embedding_model' 获取并实例化一个Embedding模型。
    """
    config = load_config()
    templates = get_embedding_provider_templates()
    
    # 1. 获取当前激活的Embedding模型ID
    active_model_id = config.get("active_embedding_model")
    if not active_model_id:
        logger.error("在配置中未指定 'active_embedding_model'。")
        raise ValueError("错误: 在 config.yaml 中未指定 'active_embedding_model'。")
        
    # 2. 找到模型的用户配置
    user_model_config = config.get("embeddings", {}).get(active_model_id)
    if not user_model_config:
        logger.error(f"在配置的 'embeddings' 部分找不到模型ID '{active_model_id}'。")
        raise ValueError(f"错误: 在 config.yaml 的 'embeddings' 部分找不到模型ID '{active_model_id}'。")

    # 3. 找到模板并动态导入类
    template_id = user_model_config.get("template")
    if not template_id:
        logger.error(f"Embedding模型 '{active_model_id}' 的配置中缺少 'template' 字段。")
        raise ValueError(f"错误: Embedding模型 '{active_model_id}' 的配置中缺少 'template' 字段。")
    
    provider_template = templates.get(template_id)
    if not provider_template:
        logger.error(f"在 'embeddings' 模板中找不到模板ID '{template_id}'。")
        raise ValueError(f"错误: 在 provider_templates.yaml 的 'embeddings' 部分找不到模板ID '{template_id}'。")
    
    EmbeddingClass = _get_class_from_path(provider_template["class"])

    # 4. 准备构造函数参数
    constructor_params = {}
    template_params = provider_template.get("params", {})

    for param_name, param_type in template_params.items():
        user_value = user_model_config.get(param_name)
        if user_value is not None:
            if param_type in ["secret_env", "url_env"]:
                env_var_value = os.getenv(user_value)
                if not env_var_value:
                    logger.error(f"Embedding模型 '{active_model_id}' 需要设置环境变量 '{user_value}'。")
                    raise ValueError(f"错误: 需要为Embedding模型 '{active_model_id}' 设置环境变量 '{user_value}'。")
                mapped_param_name = param_name.replace("_env", "")
                constructor_params[mapped_param_name] = env_var_value
            else:
                constructor_params[param_name] = user_value
                
    logger.info(f"正在实例化Embedding模型: {active_model_id} (类: {EmbeddingClass.__name__})")
    
    # 5. 实例化并返回
    try:
        return EmbeddingClass(**constructor_params)
    except Exception as e:
        logger.error(f"实例化Embedding模型 '{active_model_id}' 失败: {e}\n使用的参数: {constructor_params}", exc_info=True)
        raise ValueError(f"实例化Embedding模型 '{active_model_id}' 失败: {e}\n使用的参数: {constructor_params}")

# --- Test function ---
if __name__ == '__main__':
    try:
        logger.info("--- 测试Embedding模型提供程序 ---")
        embedding_model = get_embedding_model()
        logger.info(f"成功获取实例: {type(embedding_model)}")
        
        # 测试向量化
        logger.info("正在测试文本向量化...")
        test_vector = embedding_model.embed_query("这是一个测试句子。")
        logger.info(f"向量化成功！维度: {len(test_vector)}")

    except (ValueError, FileNotFoundError, ImportError) as e:
        logger.error(f"\n测试失败: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"\n发生了意外的错误: {e}", exc_info=True)
