"""
研究与信息检索链模块 (Research Chains)
定义了网络搜索、查询生成以及搜索结果总结相关的 AI 处理链。
"""
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from infra.llm.factory import get_llm
from prompts import get_prompt_template
from chains.base import get_writing_style_instruction
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)

def create_research_chain(search_tool, writing_style: str = ""):
    """
    创建完整的搜索与总结链。
    包含：生成多个查询词 -> 并行执行搜索工具 -> 整合总结结果。
    
    Args:
        search_tool (BaseTool): LangChain 兼容的搜索工具。
        writing_style (str): 写作风格描述。
    Returns:
        Runnable: 组合后的链。
    """
    style_inst = get_writing_style_instruction(writing_style)

    research_query_prompt = get_prompt_template("research_query")
    generate_queries_chain = (
        RunnablePassthrough.assign(
            plan=RunnablePassthrough(), 
            user_prompt=RunnablePassthrough(),
            writing_style_instruction=lambda x: style_inst
        )
        | research_query_prompt | get_llm("researcher") | StrOutputParser()
        | (lambda text: [line for line in text.strip().split("\n") if line.strip()])
    )
    
    def run_search_and_aggregate(queries: list) -> str:
        """内部辅助函数：并行执行搜索并合并文本"""
        def _search_single_query(query: str) -> str:
            try:
                safe_query = quote(query)
                tool_result = search_tool.invoke(safe_query)
                if isinstance(tool_result, str): return tool_result
                if isinstance(tool_result, list): 
                    return "\n".join([str(item.page_content if hasattr(item, 'page_content') else item) for item in tool_result])
                return str(tool_result)
            except Exception as e:
                logger.error(f"查询 '{query}' 失败: {e}")
                return ""

        all_results_text = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_query = {executor.submit(_search_single_query, q): q for q in queries}
            for future in as_completed(future_to_query):
                res = future.result()
                if res: all_results_text.append(res)
        return "\n\n---\n\n".join(all_results_text)

    # 2. 结果总结子链
    summarizer_prompt = get_prompt_template("summarizer")
    summarize_chain = (
        RunnablePassthrough.assign(
            user_prompt=RunnablePassthrough(),
            search_results=RunnablePassthrough(),
            writing_style_instruction=lambda x: style_inst,
            refinement_instruction=lambda x: x.get("refinement_instruction", ""),
            research_results=lambda x: x.get("research_results", "")
        )
        | summarizer_prompt | get_llm("summarizer") | StrOutputParser()
    )

    return (
        RunnablePassthrough.assign(queries=generate_queries_chain)
        | RunnablePassthrough.assign(search_results=lambda x: run_search_and_aggregate(x["queries"]))
        | summarize_chain
    )