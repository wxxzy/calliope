"""
工具提供商 (Tool Provider)
负责根据 tool_templates.yaml 和 user_tools.yaml 动态创建和提供工具实例。
"""
import os
import yaml
import importlib
from functools import lru_cache, partial
from langchain_core.tools import Tool # 统一导入Tool
import logging

logger = logging.getLogger(__name__)

@lru_cache(maxsize=None)
def _load_yaml(file_path: str):
    """通用YAML加载函数，带缓存。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"配置文件 {file_path} 未找到。", exc_info=True)
        raise FileNotFoundError(f"错误: 配置文件 {file_path} 未找到。")
    except yaml.YAMLError as e:
        logger.error(f"解析 {file_path} 文件失败: {e}", exc_info=True)
        raise ValueError(f"错误: 解析 {file_path} 文件失败: {e}")

def get_tool_templates():
    """加载并返回工具模板。"""
    return _load_yaml("config/templates/tools.yaml")

def get_user_tools_config():
    """加载并返回用户工具配置。"""
    # 每次都重新加载，以反映UI上的动态修改
    return _load_yaml("config/user_tools.yaml")

def save_user_tools_config(config_data: dict):
    """保存用户工具配置。"""
    try:
        with open("config/user_tools.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        logger.info(f"用户工具配置已成功保存到 user_tools.yaml。")
    except Exception as e:
        logger.error(f"写入 user_tools.yaml 文件失败: {e}", exc_info=True)
        raise IOError(f"错误: 写入 user_tools.yaml 文件失败: {e}")

def _get_callable_from_path(path: str):
    """根据字符串路径动态导入类或函数。"""
    try:
        module_path, callable_name = path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, callable_name)
    except (ImportError, AttributeError) as e:
        logger.error(f"无法从路径 '{path}' 动态导入: {e}", exc_info=True)
        raise ImportError(f"无法从路径 '{path}' 动态导入: {e}")

def get_tool(tool_id: str):
    """
    根据工具ID从配置文件获取并实例化一个 LangChain Tool。

    Args:
        tool_id (str): 在 user_tools.yaml 中定义的工具实例ID。

    Returns:
        A LangChain BaseTool instance.
    """
    user_tools = get_user_tools_config()
    templates = get_tool_templates()
    
    # 1. 找到用户工具实例的配置
    tool_config = user_tools.get(tool_id)
    if not tool_config:
        logger.error(f"在 user_tools.yaml 中找不到工具ID '{tool_id}'。")
        raise ValueError(f"错误: 在 user_tools.yaml 中找不到工具ID '{tool_id}'。")
    
    # 2. 找到该实例使用的模板
    template_id = tool_config.get("template")
    if not template_id:
        logger.error(f"工具 '{tool_id}' 的配置中缺少 'template' 字段。")
        raise ValueError(f"错误: 工具 '{tool_id}' 的配置中缺少 'template' 字段。")
        
    template = templates.get(template_id)
    if not template:
        logger.error(f"在 tool_templates.yaml 中找不到模板ID '{template_id}'。")
        raise ValueError(f"错误: 在 tool_templates.yaml 中找不到模板ID '{template_id}'。")

    # 3. 准备构造函数/函数参数
    constructor_params = {}
    template_params_schema = template.get("params", {}) # 获取模板定义的参数 schema
    
    for param_name, param_schema_type in template_params_schema.items():
        user_value = tool_config.get(param_name) # 用户在 user_tools.yaml 中配置的值
        
        if user_value is not None:
            # 解析环境变量类型参数
            if param_schema_type == "secret_env" or param_schema_type == "url_env":
                env_var_value = os.getenv(user_value) # user_value 现在是环境变量名
                if not env_var_value:
                    logger.error(f"工具 '{tool_id}' 需要环境变量 '{user_value}'，但它未被设置。")
                    raise ValueError(f"错误: 工具 '{tool_id}' 需要环境变量 '{user_value}'，但它未被设置。")
                
                # 转换参数名 (e.g., 'tavily_api_key_env' -> 'tavily_api_key')
                constructor_params[param_name.replace("_env", "")] = env_var_value
            elif param_schema_type == "int":
                try:
                    constructor_params[param_name] = int(user_value)
                except ValueError:
                    logger.error(f"工具 '{tool_id}' 的参数 '{param_name}' 需要整数类型，但收到 '{user_value}'。", exc_info=True)
                    raise ValueError(f"错误: 工具 '{tool_id}' 的参数 '{param_name}' 需要整数类型，但收到 '{user_value}'。")
            elif param_schema_type == "bool":
                constructor_params[param_name] = str(user_value).lower() == "true"
            elif param_schema_type == "string": # 确保明确处理字符串类型
                constructor_params[param_name] = str(user_value)
            else: # 未知类型，直接传递
                constructor_params[param_name] = user_value
    
    logger.info(f"正在实例化工具: '{tool_id}' (模板: '{template_id}')")

    # 4. 获取工具的通用描述 (用于Tool.from_function或Agent)
    tool_description = tool_config.get("description", f"执行ID为'{tool_id}'的工具")

    # 5. 实例化类或获取函数
    if "class" in template:
        ToolClass = _get_callable_from_path(template["class"])
        try:
            # 过滤掉非构造函数参数，防止TypeError (如description通常不直接传给类构造函数)
            # 这是一个通用化处理，但不同Tool类的构造函数签名可能差异很大
            # 确保传入的参数是构造函数实际接受的
            import inspect
            sig = inspect.signature(ToolClass.__init__)
            valid_params_for_class = {k: v for k, v in constructor_params.items() if k in sig.parameters}
            
            return ToolClass(**valid_params_for_class)
        except Exception as e:
            logger.error(f"实例化工具类 '{template['class']}' 失败: {e}\n使用的参数: {constructor_params}", exc_info=True)
            raise ValueError(f"实例化工具类 '{template['class']}' 失败: {e}\n使用的参数: {constructor_params}")
    
    elif "function" in template:
        tool_function = _get_callable_from_path(template["function"])
        
        # 将用户配置的参数传递给func (通过partial应用)
        final_func_kwargs = {}
        for param_name, param_schema_type in template_params_schema.items():
            user_value = tool_config.get(param_name)
            # 只有非环境变量且用户配置了的值才通过partial传递给函数
            if user_value is not None and param_schema_type not in ["secret_env", "url_env"]:
                final_func_kwargs[param_name] = user_value

        func_to_use = partial(tool_function, **final_func_kwargs) if final_func_kwargs else tool_function

        # Tool.from_function 包装器
        return Tool.from_function(
            func=func_to_use,
            name=tool_id, # 使用tool_id作为工具名称
            description=tool_description,
            # args_schema=None # 可以进一步定义参数的schema，但通常LangChain会自动从func的类型提示推断
        )
        
    else:
        logger.error(f"模板 '{template_id}' 中必须包含 'class' 或 'function' 字段。")
        raise ValueError(f"错误: 模板 '{template_id}' 中必须包含 'class' 或 'function' 字段。")
