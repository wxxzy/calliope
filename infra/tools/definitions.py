"""
封装所有与外部服务交互的工具。
"""
import os
import requests
from tavily import TavilyClient
from langchain.tools import tool
import logging

logger = logging.getLogger(__name__)

# --- 从环境变量或config中加载API密钥 ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")

@tool
def custom_web_search(query: str, engine: str = "tavily") -> str:
    """
    一个自定义的Web搜索工具，可以调用Tavily或Google搜索引擎。
    当需要进行网络搜索以获取信息时使用。
    :param query: str, 搜索的关键词或问题。
    :param engine: str, 要使用的搜索引擎，支持 'tavily' 或 'google'。
    :return: str, 搜索结果的摘要字符串。
    """
    logger.info(f"正在使用自定义搜索函数 '{engine}' 引擎搜索: '{query}'...")
    try:
        if engine == "tavily":
            if not TAVILY_API_KEY:
                logger.error("TAVILY_API_KEY 环境变量未设置。")
                raise ValueError("请设置 TAVILY_API_KEY 环境变量以使用Tavily搜索。")
            client = TavilyClient(api_key=TAVILY_API_KEY)
            results = client.search(query, search_depth="basic", max_results=5)
            logger.debug(f"Tavily搜索结果: {results}")
            return "\n\n".join([f"来源 {i+1}: {res['content']}" for i, res in enumerate(results["results"])])

        elif engine == "google":
            if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
                logger.error("GOOGLE_SEARCH_API_KEY 或 GOOGLE_SEARCH_CX 环境变量未设置。")
                raise ValueError("请设置 GOOGLE_SEARCH_API_KEY 和 GOOGLE_SEARCH_CX 环境变量以使用Google搜索。")
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {"key": GOOGLE_SEARCH_API_KEY, "cx": GOOGLE_SEARCH_CX, "q": query, "num": 5}
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            search_results = response.json().get('items', [])
            if not search_results:
                logger.warning(f"Google搜索 '{query}' 没有返回结果。")
                return "Google搜索没有返回结果。"
            
            logger.debug(f"Google搜索结果: {search_results}")
            return "\n\n".join([f"来源 {i+1}: {item['title']}\n摘要: {item.get('snippet', 'N/A')}" for i, item in enumerate(search_results)])

        else:
            logger.error(f"不支持的搜索引擎 '{engine}'。")
            raise ValueError("不支持的搜索引擎。请选择 'tavily' 或 'google'。")

    except Exception as e:
        logger.error(f"搜索过程中发生错误: {e}", exc_info=True)
        return f"搜索过程中发生错误: {e}"

def check_ollama_model_availability(model_name: str, base_url: str) -> dict:
    """
    检查Ollama服务是否正在运行，以及指定的模型是否可用。

    Args:
        model_name (str): 要检查的模型名称 (例如 "llama3:8b").
        base_url (str): Ollama服务的根URL (例如 "http://localhost:11434").

    Returns:
        dict: 一个包含 'status' (bool) 和 'message' (str) 的字典。
    """
    logger.info(f"正在检查Ollama模型 '{model_name}' at {base_url}...")
    try:
        # 1. 检查Ollama服务是否在运行
        response = requests.get(base_url, timeout=5)
        response.raise_for_status()

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logger.warning(f"无法连接到Ollama服务。请确认Ollama正在运行，并且地址 '{base_url}' 是正确的。错误: {e}", exc_info=True)
        return {
            "status": False,
            "message": f"无法连接到Ollama服务。请确认Ollama正在运行，并且地址 '{base_url}' 是正确的。"
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"检查Ollama服务状态时发生网络错误: {e}", exc_info=True)
        return {
            "status": False,
            "message": f"检查Ollama服务状态时发生网络错误: {e}"
        }

    try:
        # 2. 获取已下载的模型列表
        tags_response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=10)
        tags_response.raise_for_status()
        
        available_models = tags_response.json().get("models", [])
        
        # 3. 检查模型是否存在
        for model_data in available_models:
            if model_data.get("name", "").lower() == model_name.lower():
                logger.info(f"成功: 模型 '{model_name}' 可用。")
                return {"status": True, "message": "模型可用"}

        # 如果循环结束仍未找到
        logger.warning(f"模型 '{model_name}' 在您的本地Ollama中未找到。")
        return {
            "status": False,
            "message": f"模型 '{model_name}' 在您的本地Ollama中未找到。\n请通过命令 `ollama pull {model_name}` 下载它。"
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"获取Ollama模型列表时发生网络错误: {e}", exc_info=True)
        return {
            "status": False,
            "message": f"获取Ollama模型列表时发生网络错误: {e}"
        }
    except Exception as e:
        logger.error(f"检查Ollama模型时发生未知错误: {e}", exc_info=True)
        return {
            "status": False,
            "message": f"检查Ollama模型时发生未知错误: {e}"
        }

