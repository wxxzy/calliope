"""
重排器提供商 (Re-ranker Provider)
负责根据 config.yaml 和 user_config.yaml 动态创建和提供重排器模型实例。
"""
import os
import importlib
from functools import lru_cache
from config_manager import load_config, load_provider_templates

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
        raise ImportError(f"无法从路径 '{class_path}' 动态导入类: {e}")

def get_re_ranker():
    """
    根据配置文件中的 'active_re_ranker_id' 获取并实例化一个重排器模型。
    """
    config = load_config()
    re_ranker_templates = get_re_ranker_provider_templates()
    
    active_re_ranker_id = config.get("active_re_ranker_id")
    if not active_re_ranker_id:
        return None # 如果没有配置活跃重排器，则返回None
        
    user_re_ranker_config = config.get("re_rankers", {}).get(active_re_ranker_id)
    if not user_re_ranker_config:
        raise ValueError(f"错误: 在配置中找不到重排器ID '{active_re_ranker_id}'。")

    template_id = user_re_ranker_config.get("template")
    if not template_id:
        raise ValueError(f"错误: 重排器 '{active_re_ranker_id}' 的配置中缺少 'template' 字段。")
    
    provider_template = re_ranker_templates.get(template_id)
    if not provider_template:
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
                    raise ValueError(f"错误: 需要为重排器 '{active_re_ranker_id}' 设置环境变量 '{user_value}'。")
                constructor_params[param_name] = env_var_value # 例如 API Key
            elif param_type == "string":
                # 特殊处理 CrossEncoder 的 model_name 参数
                if template_id == "sentence_transformers_reranker" and param_name == "model_name":
                    constructor_params["model_name_or_path"] = user_value
                else:
                    constructor_params[param_name] = user_value
                
    print(f"正在实例化重排器: {active_re_ranker_id} (类: {ReRankerClass.__name__})")
    
    try:
        return ReRankerClass(**constructor_params)
    except Exception as e:
        raise ValueError(f"实例化重排器 '{active_re_ranker_id}' 失败: {e}\n使用的参数: {constructor_params}")

# --- Test function ---
if __name__ == '__main__':
    # 假设 config.yaml, user_config.yaml, re_ranker_templates.yaml 已正确设置
    # 例如 user_config.yaml 中有:
    # re_rankers:
    #   my_reranker:
    #     template: sentence_transformers_reranker
    #     model_name: cross-encoder/ms-marco-MiniLM-L-6-v2
    # active_re_ranker_id: my_reranker
    try:
        print("--- 测试重排器提供商 ---")
        reranker = get_re_ranker()
        if reranker:
            print(f"成功获取实例: {type(reranker)}")
            # 简单的测试重排功能
            query = "How to make a good cup of coffee?"
            docs = [
                "Coffee is a brewed drink prepared from roasted coffee beans.",
                "To brew coffee, you need hot water and ground coffee.",
                "Tea is a beverage made from the leaves of the tea plant."
            ]
            scores = reranker.predict([(query, doc) for doc in docs])
            print(f"重排分数: {scores}")
            assert len(scores) == len(docs)
        else:
            print("未配置活跃重排器，跳过测试。" )

    except (ValueError, FileNotFoundError, ImportError) as e:
        print(f"\n测试失败: {e}")
    except Exception as e:
        print(f"\n发生了意外的错误: {e}")
