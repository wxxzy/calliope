"""
文本切分器提供商 (Text Splitter Provider)
负责根据 text_splitter_templates.yaml 和 user_text_splitters.yaml 动态创建和提供文本切分器实例。
"""
import yaml
import importlib
from functools import lru_cache

def _load_yaml(file_path: str):
    """通用YAML加载函数，带缓存。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"错误: 配置文件 {file_path} 未找到。")
    except yaml.YAMLError as e:
        raise ValueError(f"错误: 解析 {file_path} 文件失败: {e}")

@lru_cache(maxsize=None)
def get_splitter_templates():
    """加载并返回文本切分器模板。"""
    return _load_yaml("text_splitter_templates.yaml")

def get_user_splitters_config():
    """加载并返回用户文本切分器配置。"""
    return _load_yaml("user_text_splitters.yaml")

def save_user_splitters_config(config_data: dict):
    """保存用户文本切分器配置。"""
    try:
        with open("user_text_splitters.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
    except Exception as e:
        raise IOError(f"错误: 写入 user_text_splitters.yaml 文件失败: {e}")

def _get_class_from_path(class_path: str):
    """根据字符串路径动态导入类。"""
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"无法从路径 '{{path}}' 动态导入类: {e}")

def get_text_splitter(splitter_id: str):
    """
    根据切分器ID从配置文件获取并实例化一个 LangChain TextSplitter。
    """
    user_splitters = get_user_splitters_config()
    templates = get_splitter_templates()
    
    # 1. 找到用户实例的配置
    splitter_config = user_splitters.get(splitter_id)
    if not splitter_config:
        raise ValueError(f"错误: 在 user_text_splitters.yaml 中找不到切分器ID '{splitter_id}'。")
    
    # 2. 找到该实例使用的模板
    template_id = splitter_config.get("template")
    if not template_id:
        raise ValueError(f"错误: 切分器 '{splitter_id}' 的配置中缺少 'template' 字段。")
        
    template = templates.get(template_id)
    if not template:
        raise ValueError(f"错误: 在 text_splitter_templates.yaml 中找不到模板ID '{template_id}'。")

    # 3. 准备构造函数参数
    constructor_params = {}
    template_params_schema = template.get("params", {})
    
    for param_name, param_schema_type in template_params_schema.items():
        user_value = splitter_config.get(param_name)
        if user_value is not None:
            if param_schema_type == "int":
                constructor_params[param_name] = int(user_value)
            elif param_schema_type == "bool":
                constructor_params[param_name] = str(user_value).lower() == "true"
            else: # string等
                constructor_params[param_name] = user_value
    
    print(f"正在实例化文本切分器: '{splitter_id}' (模板: '{template_id}')")

    # 4. 实例化类
    if "class" in template:
        SplitterClass = _get_class_from_path(template["class"])
        try:
            return SplitterClass(**constructor_params)
        except Exception as e:
            raise ValueError(f"实例化切分器类 '{template['class']}' 失败: {e}\n使用的参数: {constructor_params}")
    else:
        raise ValueError(f"模板 '{template_id}' 中必须包含 'class' 字段。")

# --- Test function ---
if __name__ == '__main__':
    try:
        print("--- 测试文本切分器提供商 ---")
        
        print("\n--- 测试 default_recursive ---")
        recursive_splitter = get_text_splitter("default_recursive")
        print(f"成功获取: {type(recursive_splitter)}")
        
        print("\n--- 测试 default_chinese ---")
        chinese_splitter = get_text_splitter("default_chinese")
        print(f"成功获取: {type(chinese_splitter)}")
        
        print("\n--- 测试 markdown_splitter ---")
        markdown_splitter = get_text_splitter("markdown_splitter")
        print(f"成功获取: {type(markdown_splitter)}")

    except (ValueError, FileNotFoundError, ImportError) as e:
        print(f"\n测试失败: {e}")
    except Exception as e:
        print(f"\n发生了意外的错误: {e}")
