"""
自定义异常类
用于在应用的不同层之间传递具有明确语义的错误信息。
"""

class LLMOperationError(Exception):
    """当与大语言模型交互时发生错误"""
    pass

class ToolOperationError(Exception):
    """当执行外部工具（如搜索引擎）时发生错误"""
    pass

class VectorStoreOperationError(Exception):
    """当与向量数据库交互时发生错误"""
    pass

class ConfigurationError(Exception):
    """当应用配置不正确或缺失时发生错误"""
    pass
