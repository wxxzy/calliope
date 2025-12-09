"""
管理和提供不同LLM（大语言模型）的实例。
这个模块现在完全由 config.yaml 文件驱动。
"""
import os
import yaml
from functools import lru_cache
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

# 默认的API密钥环境变量名称
DEFAULT_API_KEY_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "openai_compatible": "OPENAI_API_KEY", # 默认情况下，兼容模型也使用此变量
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}

@lru_cache(maxsize=None)
def load_config():
    """
    加载并解析 config.yaml 文件。
    使用 @lru_cache 确保文件只被读取和解析一次。
    """
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print("config.yaml 已成功加载和解析。")
        return config
    except FileNotFoundError:
        raise FileNotFoundError("错误: config.yaml 文件未找到。请确保它在项目根目录下。")
    except yaml.YAMLError as e:
        raise ValueError(f"错误: 解析 config.yaml 文件失败: {e}")

def get_llm(alias: str, temperature: float = 0.7):
    """
    根据别名从 config.yaml 获取预先配置好的 LangChain LLM 实例。

    Args:
        alias (str): 步骤的别名 (e.g., "planner", "drafter")。
        temperature (float): 控制模型创造力的参数。

    Returns:
        A LangChain chat model instance.
    """
    config = load_config()
    
    # 1. 从步骤别名找到模型ID
    model_id = config.get("steps", {}).get(alias)
    if not model_id:
        raise ValueError(f"错误: 在 config.yaml 的 'steps' 部分找不到别名 '{alias}'。")
        
    # 2. 从模型ID找到模型的具体定义
    model_config = config.get("models", {}).get(model_id)
    if not model_config:
        raise ValueError(f"错误: 在 config.yaml 的 'models' 部分找不到模型ID '{model_id}'。")

    # 3. 根据provider创建对应的实例
    provider = model_config.get("provider")
    model_name = model_config.get("model_name")
    
    print(f"正在加载模型: '{model_name}' (别名: '{alias}' -> 模型ID: '{model_id}')")

    if provider == "openai" or provider == "openai_compatible":
        # 获取API密钥环境变量名
        api_key_env = model_config.get("api_key_env", DEFAULT_API_KEY_ENV_VARS.get(provider))
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"请设置环境变量 {api_key_env} 以使用 {model_id} 模型。")
            
        # 准备构造函数参数
        params = {
            "model_name": model_name,
            "api_key": api_key,
            "temperature": temperature,
        }
        
        # 如果是兼容模型，添加 base_url
        if provider == "openai_compatible":
            base_url_env = model_config.get("base_url_env")
            if not base_url_env:
                 raise ValueError(f"模型 '{model_id}' 是 'openai_compatible' 类型, 但未在 config.yaml 中指定 'base_url_env'。")
            base_url = os.getenv(base_url_env)
            if not base_url:
                raise ValueError(f"请设置环境变量 {base_url_env} 以使用 {model_id} 模型。")
            params["base_url"] = base_url
            
        return ChatOpenAI(**params)

    elif provider == "anthropic":
        api_key_env = model_config.get("api_key_env", DEFAULT_API_KEY_ENV_VARS.get("anthropic"))
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"请设置环境变量 {api_key_env} 以使用 {model_id} 模型。")
        return ChatAnthropic(model_name=model_name, api_key=api_key, temperature=temperature)

    elif provider == "google":
        api_key_env = model_config.get("api_key_env", DEFAULT_API_KEY_ENV_VARS.get("google"))
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"请设置环境变量 {api_key_env} 以使用 {model_id} 模型。")
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=temperature)
        
    else:
        raise NotImplementedError(f"未知的模型提供商 '{provider}'。支持的提供商: 'openai', 'openai_compatible', 'anthropic', 'google'。")

# --- Test function ---
if __name__ == '__main__':
    # 在运行此测试前，请确保您已创建 config.yaml 和 .env 文件并正确配置
    try:
        print("--- 测试配置驱动的LLM提供程序 ---")
        
        # 加载配置以决定要测试哪些别名
        test_config = load_config()
        aliases_to_test = test_config.get("steps", {}).keys()

        for alias in aliases_to_test:
            print(f"\n--- 测试别名: '{alias}' ---")
            llm_instance = get_llm(alias)
            print(f"成功获取实例: {type(llm_instance)}")
            print(f"模型名称: {llm_instance.model_name}")

    except (ValueError, FileNotFoundError, NotImplementedError) as e:
        print(f"\n测试失败: {e}")
    except Exception as e:
        print(f"\n发生了意外的错误: {e}")