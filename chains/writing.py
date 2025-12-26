"""
核心写作链模块 (Writing Chains)
定义了长篇创作流程中与内容生成相关的 AI 处理链。
"""
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from infra.llm.factory import get_llm
from prompts import get_prompt_template
from chains.base import get_writing_style_instruction

def create_planner_chain(writing_style: str = ""):
    """创建写作规划链"""
    planner_llm = get_llm("planner")
    style_inst = get_writing_style_instruction(writing_style)
    prompt = get_prompt_template("planner")
    return (
        RunnablePassthrough.assign(
            user_prompt=RunnablePassthrough(), 
            writing_style_instruction=lambda x: style_inst,
            refinement_instruction=lambda x: x.get("refinement_instruction", ""),
            plan=lambda x: x.get("plan", "")
        )
        | prompt | planner_llm | StrOutputParser()
    )

def create_outliner_chain(writing_style: str = ""):
    """创建文章大纲生成链"""
    outliner_llm = get_llm("outliner", temperature=0.4) 
    style_inst = get_writing_style_instruction(writing_style)
    prompt = get_prompt_template("outliner")
    return (
        RunnablePassthrough.assign(
            plan=lambda x: x.get("plan", ""),
            user_prompt=lambda x: x.get("user_prompt", ""),
            research_results=lambda x: x.get("research_results", ""),
            writing_style_instruction=lambda x: style_inst,
            refinement_instruction=lambda x: x.get("refinement_instruction", ""),
            outline=lambda x: x.get("outline", "")
        )
        | prompt | outliner_llm | StrOutputParser()
    )

def create_draft_generation_chain(writing_style: str = ""):
    """创建章节撰写链"""
    drafter_llm = get_llm("drafter")
    style_inst = get_writing_style_instruction(writing_style)
    prompt = get_prompt_template("drafter")
    return (
        RunnablePassthrough.assign(
            retrieved_context=lambda x: "\n\n---\n\n".join(x.get("user_selected_docs", [])),
            previous_chapter_draft=lambda x: x.get("previous_chapter_draft", ""),
            refinement_instruction=lambda x: x.get("refinement_instruction", "")
        )
        | RunnablePassthrough.assign(writing_style_instruction=lambda x: style_inst)
        | prompt | drafter_llm | StrOutputParser()
    )

def create_revise_generation_chain(writing_style: str = ""):
    """创建全文修订链"""
    reviser_llm = get_llm("reviser", temperature=0.5)
    style_inst = get_writing_style_instruction(writing_style)
    prompt = get_prompt_template("reviser")
    return (
        RunnablePassthrough.assign(
            retrieved_context=lambda x: "\n\n---\n\n".join(x.get("user_selected_docs", []))
        )
        | RunnablePassthrough.assign(writing_style_instruction=lambda x: style_inst)
        | prompt | reviser_llm | StrOutputParser()
    )