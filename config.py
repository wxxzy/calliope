from dotenv import load_dotenv
import logging # 导入 logging 模块

logger = logging.getLogger(__name__) # 获取当前模块的logger

def load_environment():
    """
    从.env文件加载环境变量到环境中。
    """
    load_dotenv()
    logger.debug("环境变量已从 .env 文件加载。")

