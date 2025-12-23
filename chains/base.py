from llm_provider import get_llm

def get_writing_style_instruction(writing_style: str) -> str:
    """统一生成写作风格指令"""
    if writing_style:
        return f"请严格遵循以下写作风格和要求：{writing_style}"
    return ""
