"""
定义和创建项目中所有工作流的LangChain链。
我们使用LCEL（LangChain Expression Language）来构建，以获得最大的灵活性和简洁性。
"""
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from llm_provider import get_llm
from prompts import (
    PLANNER_PROMPT, RESEARCH_QUERY_PROMPT, SUMMARIZER_PROMPT, 
    OUTLINER_PROMPT, DRAFTER_PROMPT, REVISER_PROMPT, QUERY_REWRITER_PROMPT,
    CHAPTER_SUMMARIZER_PROMPT, CRITIC_PROMPT, GRAPH_EXTRACTION_PROMPT,
    COMMUNITY_NAMING_PROMPT
)
from vector_store_manager import retrieve_context
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

def _get_writing_style_instruction(writing_style: str) -> str:
    """根据写作风格描述生成指令。"""
    if writing_style:
        return f"请严格遵循以下写作风格和要求：{writing_style}"
    return ""

def create_planner_chain(writing_style: str = ""):
    """
    创建并返回“规划”步骤的链。
    支持初次生成和迭代优化。
    """
    planner_llm = get_llm("planner")
    
    writing_style_instruction = _get_writing_style_instruction(writing_style)
    
    planner_chain = (
        RunnablePassthrough.assign(
            user_prompt=RunnablePassthrough(), 
            writing_style_instruction=lambda x: writing_style_instruction,
            refinement_instruction=lambda x: x.get("refinement_instruction", ""), # 从输入中获取优化指令
            plan=lambda x: x.get("plan", "") # 传递可选的先前计划
        )
        | PLANNER_PROMPT 
        | planner_llm 
        | StrOutputParser()
    )
    
    return planner_chain

def create_query_rewrite_chain():
    """
    创建并返回一个用于重写RAG查询的链。
    """
    query_rewriter_llm = get_llm("query_rewriter")
    
    rewriter_chain = (
        QUERY_REWRITER_PROMPT 
        | query_rewriter_llm 
        | StrOutputParser()
    )
    
    return rewriter_chain
def create_chapter_summary_chain():
    """
    创建并返回一个用于生成章节摘要的链（用于RAG记忆）。
    """
    summarizer_llm = get_llm("chapter_summarizer")
    
    summary_chain = (
        CHAPTER_SUMMARIZER_PROMPT
        | summarizer_llm
        | StrOutputParser()
    )
    
    return summary_chain

def create_research_chain(search_tool, writing_style: str = ""):
    """
    创建并返回“研究”步骤的链。
    这个链现在接收一个工具对象，使其具有通用性。

    这个链的步骤：
    1. 根据plan和user_prompt生成搜索查询词。
    2. 使用传入的search_tool为每个查询词执行搜索。
    3. 将搜索结果和user_prompt交给summarizer模型进行总结。
    
    Args:
        search_tool: 一个符合LangChain BaseTool规范的工具实例。
        writing_style (str): 写作风格描述。

    Returns:
        A LangChain runnable instance.
    """
    
    writing_style_instruction = _get_writing_style_instruction(writing_style)

    generate_queries_chain = (
        RunnablePassthrough.assign(
            plan=RunnablePassthrough(), 
            user_prompt=RunnablePassthrough(),
            writing_style_instruction=lambda x: writing_style_instruction
        )
        | RESEARCH_QUERY_PROMPT
        | get_llm("researcher")
        | StrOutputParser()
        | (lambda text: [line for line in text.strip().split("\n") if line.strip()]) # 解析为查询列表，并过滤空行
    )
    
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def run_search_and_aggregate(queries: list) -> str:
        
        def _search_single_query(query: str) -> str:
            """执行单个查询并返回处理后的文本结果"""
            try:
                # 对包含非ASCII字符的查询进行URL编码，以避免底层库的编码错误
                safe_query = quote(query)
                logger.debug(f"正在使用工具 '{search_tool.name}' 搜索查询: '{query}' (Encoded: '{safe_query}')")
                tool_result = search_tool.invoke(safe_query)
                
                result_text = ""
                # 智能处理不同工具的返回结果
                if isinstance(tool_result, str):
                    result_text = tool_result
                elif isinstance(tool_result, list):
                    # 假设列表中的元素是LangChain的Document对象或类似的结构
                    temp_results = []
                    for item in tool_result:
                        if hasattr(item, 'page_content') and isinstance(item.page_content, str):
                            temp_results.append(item.page_content)
                        else:
                            temp_results.append(str(item))
                    result_text = "\n".join(temp_results)
                else:
                    result_text = str(tool_result)
                return result_text
            except Exception as e:
                logger.error(f"查询 '{query}' 搜索失败: {e}", exc_info=True)
                return f"查询 '{query}' 搜索失败。"

        all_results_text = []
        # 使用线程池并行执行搜索，最大并发数设为5（避免触发API速率限制）
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_query = {executor.submit(_search_single_query, q): q for q in queries}
            
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    result = future.result()
                    if result:
                        all_results_text.append(result)
                except Exception as e:
                    logger.error(f"处理查询 '{query}' 的结果时发生未知错误: {e}", exc_info=True)

        return "\n\n---\n\n".join(all_results_text)

    summarize_chain = (
        RunnablePassthrough.assign(
            user_prompt=RunnablePassthrough(),
            search_results=RunnablePassthrough(), # search_results 由上一个步骤传入
            writing_style_instruction=lambda x: writing_style_instruction,
            refinement_instruction=lambda x: x.get("refinement_instruction", ""),
            research_results=lambda x: x.get("research_results", "")
        )
        | SUMMARIZER_PROMPT
        | get_llm("summarizer")
        | StrOutputParser()
    )

    research_chain = (
        RunnablePassthrough.assign(
            queries=generate_queries_chain
        )
        | RunnablePassthrough.assign(
            search_results=lambda x: run_search_and_aggregate(x["queries"])
        )
        | summarize_chain
    )
    
    return research_chain


def create_outliner_chain(writing_style: str = ""):
    """
    创建并返回“大纲”步骤的链。
    支持初次生成和迭代优化。
    """
    outliner_llm = get_llm("outliner")
    
    writing_style_instruction = _get_writing_style_instruction(writing_style)

    outliner_chain = (
        RunnablePassthrough.assign(
            plan=RunnablePassthrough(), 
            user_prompt=RunnablePassthrough(),
            research_results=RunnablePassthrough(),
            writing_style_instruction=lambda x: writing_style_instruction,
            refinement_instruction=lambda x: x.get("refinement_instruction", ""), # 从输入中获取优化指令
            outline=lambda x: x.get("outline", "") # 传递可选的先前大纲
        )
        | OUTLINER_PROMPT 
        | outliner_llm 
        | StrOutputParser()
    )
    
    return outliner_chain


# RAG 流程已拆分为独立的检索和生成函数

def retrieve_documents_for_drafting(collection_name: str, section_to_write: str, recall_k: int = 20, rerank_k: int = 5, re_ranker = None) -> list[str]:
    """
    为“撰写”步骤从向量数据库检索文档。
    包含查询重写步骤。
    """
    logger.info(f"为撰写章节 '{section_to_write[:50]}...' 准备检索...")
    
    # 步骤1: 重写查询
    query_rewrite_chain = create_query_rewrite_chain()
    rewritten_query = query_rewrite_chain.invoke({"original_query": section_to_write})
    logger.info(f"原始查询: '{section_to_write[:100]}...'")
    logger.info(f"重写后查询: '{rewritten_query}'")
    
    # 步骤2: 使用重写后的查询进行检索
    return retrieve_context(
        collection_name=collection_name,
        query=rewritten_query,
        recall_k=recall_k,
        re_ranker=re_ranker,
        rerank_k=rerank_k
    )

def create_draft_generation_chain(writing_style: str = ""):
    """
    创建根据用户选择的上下文生成草稿的链。
    支持初次生成和迭代优化。
    """
    drafter_llm = get_llm("drafter")
    writing_style_instruction = _get_writing_style_instruction(writing_style)

    generation_chain = (
        RunnablePassthrough.assign(
            retrieved_context=lambda x: "\n\n---\n\n".join(x.get("user_selected_docs", [])),
            previous_chapter_draft=lambda x: x.get("previous_chapter_draft", ""),
            refinement_instruction=lambda x: x.get("refinement_instruction", "")
        )
        | RunnablePassthrough.assign(writing_style_instruction=lambda x: writing_style_instruction)
        | DRAFTER_PROMPT
        | drafter_llm
        | StrOutputParser()
    )
    return generation_chain

def retrieve_documents_for_revising(collection_name: str, full_draft: str, recall_k: int = 30, rerank_k: int = 7, re_ranker = None) -> list[str]:
    """
    为“修订”步骤从向量数据库检索文档。
    包含查询重写步骤。
    """
    logger.info("为修订全文准备检索...")
    
    # 步骤1: 重写查询
    # 对于修订，我们只取草稿的前一小部分来生成概括性查询，避免输入过长
    query_for_rewriting = f"总结以下文稿的核心主题和风格，生成用于检索相关背景资料的关键词：\n\n{full_draft[:1500]}"
    query_rewrite_chain = create_query_rewrite_chain()
    rewritten_query = query_rewrite_chain.invoke({"original_query": query_for_rewriting})
    logger.info(f"原始查询 (用于重写): '{query_for_rewriting[:200]}...'")
    logger.info(f"重写后查询: '{rewritten_query}'")

    # 步骤2: 使用重写后的查询进行检索
    return retrieve_context(
        collection_name=collection_name,
        query=rewritten_query,
        recall_k=recall_k,
        re_ranker=re_ranker,
        rerank_k=rerank_k
    )

def create_revise_generation_chain(writing_style: str = ""):
    """
    创建根据用户选择的上下文修订全文的链。
    输入字典需要包含 'user_selected_docs'键。
    """
    reviser_llm = get_llm("reviser", temperature=0.5)
    writing_style_instruction = _get_writing_style_instruction(writing_style)

    generation_chain = (
        RunnablePassthrough.assign(
            retrieved_context=lambda x: "\n\n---\n\n".join(x.get("user_selected_docs", [])),
            previous_chapter_draft=lambda x: x.get("previous_chapter_draft", ""),
            refinement_instruction=lambda x: x.get("refinement_instruction", "")
        )
        | RunnablePassthrough.assign(writing_style_instruction=lambda x: writing_style_instruction)
        | REVISER_PROMPT
        | reviser_llm
        | StrOutputParser()
    )
    return generation_chain

def create_critic_chain(writing_style: str = ""):
    """
    创建并返回“评论员”步骤的链。
    用于对大纲或草稿进行批判性分析。
    """
    critic_llm = get_llm("critic", temperature=0.3) # 评论员需要相对理性
    writing_style_instruction = _get_writing_style_instruction(writing_style)
    
    critic_chain = (
        RunnablePassthrough.assign(
            stage=lambda x: x.get("stage", "未知阶段"),
            plan=lambda x: x.get("plan", ""),
            content_to_review=lambda x: x.get("content_to_review", ""),
            writing_style_instruction=lambda x: writing_style_instruction
        )
        | CRITIC_PROMPT 
        | critic_llm 
        | StrOutputParser()
    )
    
    return critic_chain

def create_graph_extraction_chain():
    """
    创建并返回“图谱提取”步骤的链。
    用于从文本中提取实体关系三元组。
    """
    # 使用专门的 'graph_generator' 角色
    llm = get_llm("graph_generator", temperature=0.1) 
    
    extraction_chain = (
        GRAPH_EXTRACTION_PROMPT 
        | llm 
        | JsonOutputParser()
    )
    
    return extraction_chain

def create_community_naming_chain():
    """
    创建并返回“派系命名”步骤的链。
    用于根据成员名单自动生成派系名称。
    """
    # 使用专门的 'community_namer' 角色，提升命名的针对性
    llm = get_llm("community_namer", temperature=0.3) 
    
    naming_chain = (
        COMMUNITY_NAMING_PROMPT 
        | llm 
        | StrOutputParser()
    )
    
    return naming_chain
