"""
配置管理器
负责 config.yaml 文件的读取和写入。
"""
import yaml

CONFIG_PATH = "config.yaml"

def load_config():
    """
    加载并解析 config.yaml 文件。
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        # 如果文件不存在，可以返回一个空的或者默认的结构，防止应用崩溃
        return {"models": {}, "steps": {}}
    except yaml.YAMLError as e:
        raise ValueError(f"错误: 解析 {CONFIG_PATH} 文件失败: {e}")

def load_provider_templates():
    """
    加载并解析 provider_templates.yaml 文件。
    """
    templates_path = "provider_templates.yaml"
    try:
        with open(templates_path, "r", encoding="utf-8") as f:
            templates = yaml.safe_load(f)
        return templates
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        raise ValueError(f"错误: 解析 {templates_path} 文件失败: {e}")

def save_config(config_data: dict):
    """
    将配置字典写回到 config.yaml 文件。

    Args:
        config_data (dict): 要保存的配置数据。
    """
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            # allow_unicode=True 确保中文字符正确写入
            # sort_keys=False 保持字典中原有的顺序
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
    except Exception as e:
        raise IOError(f"错误: 写入 {CONFIG_PATH} 文件失败: {e}")

# --- Test function ---
if __name__ == '__main__':
    # 测试加载
    print("--- 正在加载配置 ---")
    current_config = load_config()
    print(current_config)

    # 测试修改和保存
    if current_config:
        print("\n--- 正在修改配置 (将 planner 指向 claude_3_haiku) ---")
        original_planner_model = current_config.get("steps", {}).get("planner")
        current_config["steps"]["planner"] = "claude_3_haiku"
        
        print("--- 正在保存已修改的配置 ---")
        save_config(current_config)
        print("--- 已修改的配置已保存 ---")