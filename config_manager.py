import yaml
import os
import re
import logging # 导入 logging 模块

logger = logging.getLogger(__name__) # 获取当前模块的logger

CONFIG_PATH = "config.yaml"
USER_CONFIG_PATH = "user_config.yaml"
PROVIDER_TEMPLATES_PATH = "provider_templates.yaml"

def _merge_configs(base_config: dict, user_config: dict) -> dict:
    """
    合并基础配置和用户配置。
    用户配置中的 'models' 和 'steps' 部分会覆盖或扩展基础配置。
    """
    merged_config = base_config.copy()

    # 合并 models
    if "models" in user_config:
        merged_config["models"] = merged_config.get("models", {})
        merged_config["models"].update(user_config["models"])
    
    # 合并 steps
    if "steps" in user_config:
        merged_config["steps"] = merged_config.get("steps", {})
        merged_config["steps"].update(user_config["steps"])

    # 合并 embeddings
    if "embeddings" in user_config:
        merged_config["embeddings"] = merged_config.get("embeddings", {})
        merged_config["embeddings"].update(user_config["embeddings"])

    # 合并 active_embedding_model
    if "active_embedding_model" in user_config:
        merged_config["active_embedding_model"] = user_config["active_embedding_model"]

    # 合并 writing_styles
    if "writing_styles" in user_config:
        merged_config["writing_styles"] = merged_config.get("writing_styles", {})
        merged_config["writing_styles"].update(user_config["writing_styles"])
        
    # 合并 re_rankers
    if "re_rankers" in user_config:
        merged_config["re_rankers"] = merged_config.get("re_rankers", {})
        merged_config["re_rankers"].update(user_config["re_rankers"])
    
    # 合并 active_re_ranker_id
    if "active_re_ranker_id" in user_config:
        merged_config["active_re_ranker_id"] = user_config["active_re_ranker_id"]

    return merged_config
    
def load_user_config() -> dict:
    """
    加载并解析 user_config.yaml 文件。
    """
    try:
        if not os.path.exists(USER_CONFIG_PATH):
            return {}
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f)
        return user_config if user_config else {}
    except yaml.YAMLError as e:
        logger.error(f"解析 {USER_CONFIG_PATH} 文件失败: {e}", exc_info=True)
        raise ValueError(f"错误: 解析 {USER_CONFIG_PATH} 文件失败: {e}")

def load_config() -> dict:
    """
    加载并解析 config.yaml 和 user_config.yaml 文件，并进行合并。
    """
    try:
        if not os.path.exists(CONFIG_PATH):
            return {"models": {}, "steps": {}} # 基础配置不存在，返回空
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            base_config = yaml.safe_load(f)
        
        user_config = load_user_config()
        merged_config = _merge_configs(base_config, user_config)
        
        return merged_config
    except FileNotFoundError:
        logger.warning(f"配置文件 {CONFIG_PATH} 未找到，返回默认空配置。")
        return {"models": {}, "steps": {}}
    except yaml.YAMLError as e:
        logger.error(f"解析 {CONFIG_PATH} 文件失败: {e}", exc_info=True)
        raise ValueError(f"错误: 解析 {CONFIG_PATH} 文件失败: {e}")

def load_provider_templates() -> dict:
    """
    加载并解析 provider_templates.yaml 文件。
    """
    try:
        if not os.path.exists(PROVIDER_TEMPLATES_PATH):
            logger.warning(f"提供商模板文件 {PROVIDER_TEMPLATES_PATH} 未找到，返回空模板。")
            return {}
        with open(PROVIDER_TEMPLATES_PATH, "r", encoding="utf-8") as f:
            templates = yaml.safe_load(f)
        return templates if templates else {}
    except yaml.YAMLError as e:
        logger.error(f"解析 {PROVIDER_TEMPLATES_PATH} 文件失败: {e}", exc_info=True)
        raise ValueError(f"错误: 解析 {PROVIDER_TEMPLATES_PATH} 文件失败: {e}")

def get_all_model_templates() -> dict:
    """
    获取所有模型提供商的模板及其参数定义。
    """
    templates = load_provider_templates()
    # 过滤掉非模型类的模板，例如 'embeddings' 部分
    model_templates = {k: v for k, v in templates.items() if 'class' in v and k != 'embeddings' and k != 'embedding_models'} # 'embedding_models' is a placeholder if a separate key is used for embedding models
    return model_templates

def get_all_embedding_templates() -> dict:
    """
    获取所有嵌入模型提供商的模板及其参数定义。
    """
    templates = load_provider_templates()
    embedding_templates = templates.get("embeddings", {})
    return embedding_templates

def save_user_config(user_config_data: dict):
    """
    将用户配置字典写回到 user_config.yaml 文件。

    Args:
        user_config_data (dict): 要保存的用户配置数据（例如 models 和 steps）。
    """
    try:
        # 确保 user_config.yaml 目录存在
        os.makedirs(os.path.dirname(USER_CONFIG_PATH) or '.', exist_ok=True)
        with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(user_config_data, f, allow_unicode=True, sort_keys=False)
        logger.info(f"用户配置已成功保存到 {USER_CONFIG_PATH}。")
    except Exception as e:
        logger.error(f"写入 {USER_CONFIG_PATH} 文件失败: {e}", exc_info=True)
        raise IOError(f"错误: 写入 {USER_CONFIG_PATH} 文件失败: {e}")

def save_config(config_data: dict):
    """
    此函数现在仅用于保存基础的 config.yaml，不建议直接修改，
    因为用户自定义配置应保存在 user_config.yaml 中。
    （保留此函数以兼容现有代码，但未来应避免直接调用它修改用户配置）
    """
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        logger.info(f"配置已成功保存到 {CONFIG_PATH}。")
    except Exception as e:
        logger.error(f"写入 {CONFIG_PATH} 文件失败: {e}", exc_info=True)
        raise IOError(f"错误: 写入 {CONFIG_PATH} 文件失败: {e}")

# --- Test function ---
if __name__ == '__main__':
    # 清理旧的 user_config.yaml 以便测试
    if os.path.exists(USER_CONFIG_PATH):
        os.remove(USER_CONFIG_PATH)
        logger.info(f"已清理旧的 {USER_CONFIG_PATH}。")
    
    logger.info("--- 初始加载配置 (user_config.yaml 不存在时) ---")
    current_config = load_config()
    logger.info("加载的配置:")
    logger.info(yaml.dump(current_config, allow_unicode=True, sort_keys=False))

    # 测试 get_all_model_templates
    logger.info("\n--- 获取所有模型模板 ---")
    model_templates = get_all_model_templates()
    logger.info(yaml.dump(model_templates, allow_unicode=True, sort_keys=False))
    assert 'openai' in model_templates and 'ollama' in model_templates

    # 测试 get_all_embedding_templates
    logger.info("\n--- 获取所有嵌入模型模板 ---")
    embedding_templates = get_all_embedding_templates()
    logger.info(yaml.dump(embedding_templates, allow_unicode=True, sort_keys=False))
    assert 'openai' in embedding_templates and 'ollama' in embedding_templates

    # 模拟用户添加模型
    logger.info("\n--- 模拟用户添加一个新模型和修改 steps ---")
    user_data_to_save = {
        "models": {
            "my_new_model": {
                "template": "openai",
                "model_name": "gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY"
            }
        },
        "steps": {
            "drafter": "my_new_model"
        },
        "embeddings": {
            "my_custom_embedding": {
                "template": "openai",
                "model": "text-embedding-3-large",
                "api_key_env": "OPENAI_API_KEY"
            }
        },
        "active_embedding_model": "my_custom_embedding",
        "writing_styles": { # 添加 writing_styles 用于测试
            "academic_report": "采用严谨、客观的学术报告风格，使用专业术语，避免口语化表达。",
            "humorous_narrative": "以轻松幽默的口吻进行叙述，多用比喻、拟人等修辞手法，旨在逗乐读者。"
        },
        "re_rankers": {
            "my_reranker": {
                "template": "sentence_transformers_reranker",
                "model_name": "cross-encoder/ms-marco-MiniLM-L-6-v2"
            }
        },
        "active_re_ranker_id": "my_reranker"
    }
    save_user_config(user_data_to_save)
    logger.info("--- 用户配置已保存 ---")

    logger.info("\n--- 重新加载配置 (包含用户配置) ---")
    merged_config = load_config()
    logger.info("合并后的配置:")
    logger.info(yaml.dump(merged_config, allow_unicode=True, sort_keys=False))

    # 验证合并结果
    assert "my_new_model" in merged_config["models"]
    assert merged_config["steps"]["drafter"] == "my_new_model"
    assert "my_custom_embedding" in merged_config["embeddings"]
    assert merged_config["active_embedding_model"] == "my_custom_embedding"
    assert "academic_report" in merged_config["writing_styles"] # 验证 writing_styles 是否合并成功
    assert "my_reranker" in merged_config["re_rankers"]
    assert merged_config["active_re_ranker_id"] == "my_reranker"
    logger.info("\n--- 配置合并验证成功！---")