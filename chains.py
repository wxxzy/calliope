"""
定义和创建项目中所有工作流的LangChain链。
我们使用LCEL（LangChain Expression Language）来构建，以获得最大的灵活性和简洁性。
"""
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from llm_provider import get_llm
from prompts import PLANNER_PROMPT, RESEARCH_QUERY_PROMPT, SUMMARIZER_PROMPT, OUTLINER_PROMPT, DRAFTER_PROMPT, REVISER_PROMPT
from vector_store_manager import retrieve_context
import logging

logger = logging.getLogger(__name__)

def _get_writing_style_instruction(writing_style: str) -> str:
    """根据写作风格描述生成指令。"""
    if writing_style:
        return f"请严格遵循以下写作风格和要求：{writing_style}"
    return ""

def create_planner_chain(writing_style: str = ""):
    """
    创建并返回“规划”步骤的链。
    这个链接收用户输入，并返回一个结构化的写作计划。
    """
    planner_llm = get_llm("planner")
    
    writing_style_instruction = _get_writing_style_instruction(writing_style)
    
    planner_chain = (
        RunnablePassthrough.assign(user_prompt=RunnablePassthrough(), writing_style_instruction=lambda x: writing_style_instruction)
        | PLANNER_PROMPT 
        | planner_llm 
        | StrOutputParser()
    )
    
    return planner_chain

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
    
    def run_search_and_aggregate(queries: list) -> str:
        all_results = []
        for query in queries:
            logger.debug(f"正在使用工具 '{search_tool.name}' 搜索查询: '{query}'")
            tool_result = search_tool.invoke(query)
            all_results.append(str(tool_result)) # 确保结果是字符串
        return "\n\n---\n\n".join(all_results)

    summarize_chain = (
        RunnablePassthrough.assign(
            user_prompt=RunnablePassthrough(),
            search_results=RunnablePassthrough(), # search_results 由上一个步骤传入
            writing_style_instruction=lambda x: writing_style_instruction
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
    这个链接收plan, research_results, 和 user_prompt，生成详细大纲。
    """
    outliner_llm = get_llm("outliner")
    
    writing_style_instruction = _get_writing_style_instruction(writing_style)

    outliner_chain = (
        RunnablePassthrough.assign(
            plan=RunnablePassthrough(), 
            user_prompt=RunnablePassthrough(),
            research_results=RunnablePassthrough(),
            writing_style_instruction=lambda x: writing_style_instruction
        )
        | OUTLINER_PROMPT 
        | outliner_llm 
        | StrOutputParser()
    )
    
    return outliner_chain


# RAG 流程已拆分为独立的检索和生成函数

def retrieve_documents_for_drafting(collection_name: str, section_to_write: str, re_ranker=None) -> list[str]:
    """
    为“撰写”步骤从向量数据库检索文档。
    """
    logger.info(f"为撰写章节 '{section_to_write[:50]}...' 检索文档...")
    return retrieve_context(
        collection_name=collection_name,
        query=section_to_write,
        n_results=10,
        re_ranker=re_ranker,
        re_ranker_top_n=3
    )

def create_draft_generation_chain(writing_style: str = ""):
    """
    创建根据用户选择的上下文生成草稿的链。
    输入字典需要包含 'user_selected_docs' 键。
    """
    drafter_llm = get_llm("drafter")
    writing_style_instruction = _get_writing_style_instruction(writing_style)

    generation_chain = (
        RunnablePassthrough.assign(
            retrieved_context=lambda x: "\n\n---\n\n".join(x.get("user_selected_docs", []))
        )
        | RunnablePassthrough.assign(writing_style_instruction=lambda x: writing_style_instruction)
        | DRAFTER_PROMPT
        | drafter_llm
        | StrOutputParser()
    )
    return generation_chain

def retrieve_documents_for_revising(collection_name: str, full_draft: str, re_ranker=None) -> list[str]:
    """
    为“修订”步骤从向量数据库检索文档。
    """
    logger.info("为修订全文检索文档...")
    return retrieve_context(
        collection_name=collection_name,
        query=full_draft[:2000],
        n_results=15,
        re_ranker=re_ranker,
        re_ranker_top_n=5
    )

def create_revise_generation_chain(writing_style: str = ""):
    """
    创建根据用户选择的上下文修订全文的链。
    输入字典需要包含 'user_selected_docs' 键。
    """
    reviser_llm = get_llm("reviser", temperature=0.5)
    writing_style_instruction = _get_writing_style_instruction(writing_style)

    generation_chain = (
        RunnablePassthrough.assign(
            retrieved_context=lambda x: "\n\n---\n\n".join(x.get("user_selected_docs", []))
        )
        | RunnablePassthrough.assign(writing_style_instruction=lambda x: writing_style_instruction)
        | REVISER_PROMPT
        | reviser_llm
        | StrOutputParser()
    )
    return generation_chain


# --- Test function ---
if __name__ == '__main__':
    # 这是一个简单的测试，确保链可以被正确创建和调用
    # 在运行此测试之前，请确保您的API密钥已在环境变量中设置
    test_user_prompt = "写一篇关于“引力波”的科普文章，给高中生看。"
    
    try:
        # --- 1. 规划 ---
        logger.info("="*20 + "\n1. 调用规划链...\n" + "="*20)
        planner_chain = create_planner_chain()
        plan_result = planner_chain.invoke({"user_prompt": test_user_prompt})
        logger.info(plan_result)

        # --- 2. 测试研究链 ---
        logger.info("\n" + "="*20 + "\n2. 调用研究链...\n" + "="*20)
        
        # 首先，获取一个工具实例
        from tool_provider import get_tool
        search_tool = get_tool("ddg_default") # 默认的搜索工具
        
        # 然后，将工具实例传递给研究链
        research_chain = create_research_chain(search_tool=search_tool) 
        research_input = {"plan": plan_result, "user_prompt": test_user_prompt}
        research_result = research_chain.invoke(research_input)
        logger.info(research_result)
        logger.info("="*20)

        # --- 3. 大纲 ---
        logger.info("\n" + "="*20 + "\n3. 调用大纲链...\n" + "="*20)
        outliner_chain = create_outliner_chain()
        outliner_input = {
            "plan": plan_result, 
            "user_prompt": test_user_prompt, 
            "research_results": research_result
        }
        outline_result = outliner_chain.invoke(outliner_input)
        logger.info(outline_result)

        # --- 模拟RAG流程：先索引一些内容 ---
        from vector_store_manager import index_text, reset_collection
        test_collection_name = "test_project"
        logger.info(f"\n--- 准备RAG测试 (重置集合: {test_collection_name}) ---")
        reset_collection(test_collection_name)
        logger.info("--- 正在索引'世界观'和'大纲' ---")
        index_text(test_collection_name, "世界观: 主角是一个AI侦探。", metadata={"source": "world_bible"})
        index_text(test_collection_name, outline_result, metadata={"source": "outline"})
        
        # --- 4. 撰写 (RAG增强) ---
        logger.info("\n" + "="*20 + "\n4. 调用拆分后的RAG撰写流程 (测试引言部分)...\n" + "="*20)
        
        try:
            introduction_section_for_writing = outline_result.split("第一部分")[0]
        except Exception:
            introduction_section_for_writing = "\n".join(outline_result.splitlines()[:4])

        logger.info(f"--- 将为以下章节撰写内容 ---\n{introduction_section_for_writing}\n--------------------------")
        
        # 步骤 4.1: 检索
        retrieved_for_draft = retrieve_documents_for_drafting(test_collection_name, introduction_section_for_writing)
        logger.info(f"--- 检索到 {len(retrieved_for_draft)} 篇文档 ---")
        # 假设用户审核并全选了所有文档
        user_selected_for_draft = retrieved_for_draft

        # 步骤 4.2: 生成
        draft_generation_chain = create_draft_generation_chain()
        drafter_input = {
            "user_prompt": test_user_prompt,
            "research_results": research_result,
            "outline": outline_result,
            "section_to_write": introduction_section_for_writing,
            "user_selected_docs": user_selected_for_draft
        }
        draft_result = draft_generation_chain.invoke(drafter_input)
        logger.info("\n--- 撰写链输出 (初稿部分) ---")
        logger.info(draft_result)
        logger.info("="*20)

        # --- 5. 修订 (RAG增强) ---
        logger.info("\n" + "="*20 + "\n5. 调用拆分后的RAG修订流程...\n" + "="*20)
        
        # 步骤 5.1: 检索
        retrieved_for_revise = retrieve_documents_for_revising(test_collection_name, draft_result)
        logger.info(f"--- 检索到 {len(retrieved_for_revise)} 篇文档 ---")
        # 假设用户审核并全选了所有文档
        user_selected_for_revise = retrieved_for_revise

        # 步骤 5.2: 生成
        revise_generation_chain = create_revise_generation_chain()
        reviser_input = {
            "plan": plan_result,
            "outline": outline_result,
            "full_draft": draft_result,
            "user_selected_docs": user_selected_for_revise
        }
        final_result = revise_generation_chain.invoke(reviser_input)
        logger.info("\n--- 修订链输出 (最终稿部分) ---")
        logger.info(final_result)
        logger.info("="*20)

    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}", exc_info=True)

