from dotenv import load_dotenv

def load_environment():
    """
    从.env文件加载环境变量到环境中。
    """
    load_dotenv()
    print("环境变量已从 .env 文件加载。")

