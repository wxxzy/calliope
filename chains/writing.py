"""
核心写作链模块 (Writing Chains)
定义了长篇创作流程中与内容生成相关的 AI 处理链。
"""
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from llm_provider import get_llm
from prompts import PLANNER_PROMPT, OUTLINER_PROMPT, DRAFTER_PROMPT, REVISER_PROMPT
from chains.base import get_writing_style_instruction

def create_planner_chain(writing_style: str = ""):
    """
    创建写作规划链。
    用于根据用户需求生成初始计划，或根据反馈优化现有计划。
    
    Args:
        writing_style (str): 写作风格描述。
    Returns:
        Runnable: LangChain 可执行对象。
    """
    planner_llm = get_llm("planner")
    style_inst = get_writing_style_instruction(writing_style)
    return (
        RunnablePassthrough.assign(
            user_prompt=RunnablePassthrough(), 
            writing_style_instruction=lambda x: style_inst,
            refinement_instruction=lambda x: x.get("refinement_instruction", ""),
            plan=lambda x: x.get("plan", "")
        )
        | PLANNER_PROMPT | planner_llm | StrOutputParser()
    )

def create_outliner_chain(writing_style: str = ""):
    """
    创建文章大纲生成链。
    结合规划、研究结果及用户需求设计结构。
    
    Args:
        writing_style (str): 写作风格描述。
    Returns:
        Runnable: LangChain 可执行对象。
    """
    outliner_llm = get_llm("outliner")
    style_inst = get_writing_style_instruction(writing_style)
    return (
        RunnablePassthrough.assign(
            plan=RunnablePassthrough(), 
            user_prompt=RunnablePassthrough(),
            research_results=RunnablePassthrough(),
            writing_style_instruction=lambda x: style_inst,
            refinement_instruction=lambda x: x.get("refinement_instruction", ""),
            outline=lambda x: x.get("outline", "")
        )
        | OUTLINER_PROMPT | outliner_llm | StrOutputParser()
    )

def create_draft_generation_chain(writing_style: str = ""):
    """
    创建章节撰写链。
    利用 RAG 检索到的上下文和用户选择的记忆片段进行内容扩充。
    
    Args:
        writing_style (str): 写作风格描述。
    Returns:
        Runnable: LangChain 可执行对象。
    """
    drafter_llm = get_llm("drafter")
    style_inst = get_writing_style_instruction(writing_style)
    return (
        RunnablePassthrough.assign(
            retrieved_context=lambda x: "\n\n---\n\n".join(x.get("user_selected_docs", [])),
            previous_chapter_draft=lambda x: x.get("previous_chapter_draft", ""),
            refinement_instruction=lambda x: x.get("refinement_instruction", "")
        )
        | RunnablePassthrough.assign(writing_style_instruction=lambda x: style_inst)
        | DRAFTER_PROMPT | drafter_llm | StrOutputParser()
    )

def create_revise_generation_chain(writing_style: str = ""):
    """
    创建全文修订链。
    作为“总编辑”对完成的初稿进行润色和一致性检查。
    
    Args:
        writing_style (str): 写作风格描述。
    Returns:
        Runnable: LangChain 可执行对象。
    """
    reviser_llm = get_llm("reviser", temperature=0.5)
    style_inst = get_writing_style_instruction(writing_style)
    return (
        RunnablePassthrough.assign(
            retrieved_context=lambda x: "\n\n---\n\n".join(x.get("user_selected_docs", []))
        )
        | RunnablePassthrough.assign(writing_style_instruction=lambda x: style_inst)
        | REVISER_PROMPT | reviser_llm | StrOutputParser()
    )