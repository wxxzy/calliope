"""
定义和创建项目中所有工作流的LangChain链。
我们使用LCEL（LangChain Expression Language）来构建，以获得最大的灵活性和简洁性。
"""
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from llm_provider import get_llm
from prompts import PLANNER_PROMPT, RESEARCH_QUERY_PROMPT, SUMMARIZER_PROMPT, OUTLINER_PROMPT, DRAFTER_PROMPT, REVISER_PROMPT
from tools import web_search

def create_planner_chain():
    """
    创建并返回“规划”步骤的链。
    这个链接收用户输入，并返回一个结构化的写作计划。
    """
    # 获取为“规划师”角色指定的LLM
    planner_llm = get_llm("planner")
    
    # 使用LCEL（| 操作符）将提示、模型和输出解析器链接在一起
    # 1. PLANNER_PROMPT: 接收一个字典（如 {"user_prompt": "..."}），生成一个格式化的提示。
    # 2. planner_llm: 接收提示，返回一个AI消息（AIMessage）。
    # 3. StrOutputParser: 从AI消息中提取内容，返回一个字符串。
    planner_chain = PLANNER_PROMPT | planner_llm | StrOutputParser()
    
    return planner_chain

def create_research_chain(search_engine: str = "tavily"):
    """
    创建并返回“研究”步骤的链。

    这个链的步骤：
    1. 根据plan和user_prompt生成搜索查询词。
    2. 使用web_search工具执行搜索。
    3. 将搜索结果和user_prompt交给summarizer模型进行总结。
    
    Args:
        search_engine (str): 要使用的搜索引擎 ('tavily' 或 'google').

    Returns:
        A LangChain runnable instance.
    """
    
    # 定义链的各个部分
    generate_queries_chain = (
        RESEARCH_QUERY_PROMPT
        | get_llm("researcher")
        | StrOutputParser()
        | (lambda text: text.strip().split("\n")) # 将输出的字符串解析为查询列表
    )
    
    # 这是一个自定义函数，用于接收查询列表并为每个查询执行搜索
    def run_search_and_aggregate(queries: list) -> str:
        all_results = []
        for query in queries:
            if query.strip(): # 确保查询不为空
                search_result = web_search(query, engine=search_engine)
                all_results.append(search_result)
        return "\n\n---\n\n".join(all_results)

    summarize_chain = (
        SUMMARIZER_PROMPT
        | get_llm("summarizer")
        | StrOutputParser()
    )

    # 使用LCEL的RunnablePassthrough和assign来编排整个流程
    # RunnablePassthrough.assign(...) 允许我们在链中传递和创建新的变量
    research_chain = (
        RunnablePassthrough.assign(
            # "queries" 键将由 generate_queries_chain 的结果填充
            queries=generate_queries_chain
        )
        | RunnablePassthrough.assign(
            # "search_results" 键将由 run_search_and_aggregate 函数的结果填充
            # 它接收前一步的整个输出（包括 'plan', 'user_prompt', 和新生成的 'queries'）
            search_results=lambda x: run_search_and_aggregate(x["queries"])
        )
        | summarize_chain # 最后，将包含 search_results 的字典传递给总结链
    )
    
    return research_chain


def create_outliner_chain():
    """
    创建并返回“大纲”步骤的链。
    这个链接收plan, research_results, 和 user_prompt，生成详细大纲。
    """
    outliner_llm = get_llm("outliner")
    
    outliner_chain = OUTLINER_PROMPT | outliner_llm | StrOutputParser()
    
    return outliner_chain


def create_drafter_chain():
    """
    创建并返回“撰写”步骤的链。
    这个链接收 outline, research_results, user_prompt, 和 section_to_write，
    生成指定章节的草稿。
    """
    drafter_llm = get_llm("drafter")
    
    drafter_chain = DRAFTER_PROMPT | drafter_llm | StrOutputParser()
    
    return drafter_chain



def create_reviser_chain():
    """
    创建并返回“修订”步骤的链。
    这个链接收 plan, outline, 和 full_draft，生成最终的修订稿。
    """
    reviser_llm = get_llm("reviser", temperature=0.5) # 修订时降低一些创造性
    
    reviser_chain = REVISER_PROMPT | reviser_llm | StrOutputParser()
    
    return reviser_chain


# --- Test function ---
if __name__ == '__main__':
    # 这是一个简单的测试，确保链可以被正确创建和调用
    # 在运行此测试之前，请确保您的API密钥已在环境变量中设置
    test_user_prompt = "写一篇关于“引力波”的科普文章，给高中生看。"
    
    try:
        # --- 1. 规划 ---
        print("="*20 + "\n1. 调用规划链...\n" + "="*20)
        planner_chain = create_planner_chain()
        plan_result = planner_chain.invoke({"user_prompt": test_user_prompt})
        print(plan_result)

        # --- 2. 研究 ---
        print("\n" + "="*20 + "\n2. 调用研究链...\n" + "="*20)
        research_chain = create_research_chain(search_engine="tavily") 
        research_input = {"plan": plan_result, "user_prompt": test_user_prompt}
        research_result = research_chain.invoke(research_input)
        print(research_result)

        # --- 3. 大纲 ---
        print("\n" + "="*20 + "\n3. 调用大纲链...\n" + "="*20)
        outliner_chain = create_outliner_chain()
        outliner_input = {
            "plan": plan_result, 
            "user_prompt": test_user_prompt, 
            "research_results": research_result
        }
        outline_result = outliner_chain.invoke(outliner_input)
        print(outline_result)

        # --- 4. 撰写 (仅测试撰写引言部分) ---
        print("\n" + "="*20 + "\n4. 调用撰写链 (测试引言部分)...\n" + "="*20)
        
        try:
            introduction_section_for_writing = outline_result.split("第一部分")[0]
        except Exception:
            introduction_section_for_writing = "\n".join(outline_result.splitlines()[:4])

        print(f"--- 将为以下章节撰写内容 ---\n{introduction_section_for_writing}\n--------------------------")

        drafter_chain = create_drafter_chain()
        drafter_input = {
            "plan": plan_result,
            "user_prompt": test_user_prompt,
            "research_results": research_result,
            "outline": outline_result,
            "section_to_write": introduction_section_for_writing
        }
        draft_result = drafter_chain.invoke(drafter_input)
        print("\n--- 撰写链输出 (初稿部分) ---")
        print(draft_result)
        print("="*20)

        # --- 5. 修订 (测试修订引言部分) ---
        print("\n" + "="*20 + "\n5. 调用修订链...\n" + "="*20)
        reviser_chain = create_reviser_chain()
        reviser_input = {
            "plan": plan_result,
            "outline": outline_result,
            "full_draft": draft_result # 在真实场景中，这里是完整的初稿
        }
        final_result = reviser_chain.invoke(reviser_input)
        print("\n--- 修订链输出 (最终稿部分) ---")
        print(final_result)
        print("="*20)

    except Exception as e:
        print(f"测试过程中发生错误: {e}")

