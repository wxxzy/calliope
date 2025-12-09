"""
管理和提供不同LLM（大语言模型）的实例。
这是实现多模型智能路由的核心。
"""
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
import os

# --- 从环境变量加载API密钥 ---
# 为了安全，推荐将API密钥设置在环境变量中
# 您可以在终端中使用 export OPENAI_API_KEY='Your_Key' (macOS/Linux)
# 或 set OPENAI_API_KEY='Your_Key' (Windows)
# 或者，如果您不想设置环境变量，可以直接在此处替换 os.getenv('...') 为您的密钥字符串，
# 例如：api_key=os.getenv("OPENAI_API_KEY", "sk-...")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- 自定义 OpenAI 兼容模型 (例如火山方舟豆包) ---
DOUBAO_CUSTOM_BASE_URL = os.getenv("DOUBAO_CUSTOM_BASE_URL")
DOUBAO_CUSTOM_API_KEY = os.getenv("DOUBAO_CUSTOM_API_KEY")

# --- 模型别名定义 ---
# 我们为不同任务指定了首选模型
MODEL_ALIASES = {
    # 标准模型配置
    "planner": "gpt-4o",
    "researcher": "claude-3-haiku-20240307",
    "summarizer": "gemini-1.5-flash-latest",
    "outliner": "gpt-4o",
    "drafter": "gpt-3.5-turbo",
    "reviser": "claude-3-opus-20240229",

    # --- 自定义 OpenAI 兼容模型 (例如火山方舟豆包) ---
    # 如果您想使用豆包模型作为特定角色的模型，可以修改上面的别名，
    # 或者添加新的别名，例如：
    "doubao-planner": "doubao-seed-1-6-251015",
    "doubao-researcher": "doubao-seed-1-6-251015",
    "doubao-summarizer": "doubao-seed-1-6-251015",
    "doubao-outliner": "doubao-seed-1-6-251015",
    "doubao-drafter": "doubao-seed-1-6-251015",
    "doubao-reviser": "doubao-seed-1-6-251015",
}

def get_llm(alias: str, temperature: float = 0.7):
    """
    根据别名获取预先配置好的 LangChain LLM 实例。

    Args:
        alias (str): 模型的别名 (e.g., "planner", "drafter").
        temperature (float): 控制模型创造力的参数.

    Returns:
        A LangChain chat model instance.
    """
    model_name = MODEL_ALIASES.get(alias)
    if not model_name:
        raise ValueError(f"未知的模型别名: {alias}")

    print(f"正在加载模型: {model_name} (别名: {alias})")

    # --- 处理自定义 OpenAI 兼容模型 (例如火山方舟豆包) ---
    if model_name == "doubao-seed-1-6-251015":
        if not DOUBAO_CUSTOM_BASE_URL:
            raise ValueError("请设置 DOUBAO_CUSTOM_BASE_URL 环境变量以使用 doubao 模型。")
        if not DOUBAO_CUSTOM_API_KEY:
            raise ValueError("请设置 DOUBAO_CUSTOM_API_KEY 环境变量以使用 doubao 模型。")
        return ChatOpenAI(
            model_name=model_name, 
            api_key=DOUBAO_CUSTOM_API_KEY, 
            base_url=DOUBAO_CUSTOM_BASE_URL, 
            temperature=temperature
        )
    
    elif model_name.startswith("gpt"):
        if not OPENAI_API_KEY:
            raise ValueError("请设置 OPENAI_API_KEY 环境变量")
        return ChatOpenAI(model_name=model_name, api_key=OPENAI_API_KEY, temperature=temperature)
    
    elif model_name.startswith("claude"):
        if not ANTHROPIC_API_KEY:
            raise ValueError("请设置 ANTHROPIC_API_KEY 环境变量")
        return ChatAnthropic(model_name=model_name, api_key=ANTHROPIC_API_KEY, temperature=temperature)
    
    elif model_name.startswith("gemini"):
        if not GOOGLE_API_KEY:
            raise ValueError("请设置 GOOGLE_API_KEY 环境变量")
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=GOOGLE_API_KEY, temperature=temperature)
    
    else:
        raise NotImplementedError(f"模型提供商 {model_name} 尚未实现。")

# --- Test function ---
if __name__ == '__main__':
    try:
        # 测试获取不同模型的实例
        print("测试获取 'planner' 模型...")
        planner_llm = get_llm('planner')
        print(f"成功获取: {type(planner_llm)}")

        print("\n测试获取 'drafter' 模型...")
        drafter_llm = get_llm('drafter')
        print(f"成功获取: {type(drafter_llm)}")

        print("\n测试获取 'summarizer' 模型...")
        summarizer_llm = get_llm('summarizer')
        print(f"成功获取: {type(summarizer_llm)}")

    except ValueError as e:
        print(f"错误: {e}")
    except Exception as e:
        print(f"发生了意外的错误: {e}")
