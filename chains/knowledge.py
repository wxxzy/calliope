"""
知识管理与 RAG 链模块 (Knowledge Chains)
定义了 RAG 查询重写、章节摘要、知识图谱提取及派系分析等 AI 逻辑。
"""
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from infra.llm.factory import get_llm
from prompts import get_prompt_template
from infra.storage.vector_store import retrieve_context
from chains.base import get_writing_style_instruction
import logging

logger = logging.getLogger(__name__)

def create_query_rewrite_chain():
    """创建查询重写链"""
    prompt = get_prompt_template("query_rewriter")
    return prompt | get_llm("query_rewriter") | StrOutputParser()

def create_chapter_summary_chain():
    """创建章节摘要链"""
    prompt = get_prompt_template("chapter_summarizer")
    return prompt | get_llm("chapter_summarizer") | JsonOutputParser()

def create_critic_chain(writing_style: str = ""):
    """创建评论员链"""
    style_inst = get_writing_style_instruction(writing_style)
    prompt = get_prompt_template("critic")
    return (
        RunnablePassthrough.assign(
            stage=lambda x: x.get("stage", "未知"),
            plan=lambda x: x.get("plan", ""),
            content_to_review=lambda x: x.get("content_to_review", ""),
            writing_style_instruction=lambda x: style_inst
        )
        | prompt | get_llm("critic", temperature=0.3) | StrOutputParser()
    )

def create_graph_extraction_chain():
    """创建知识图谱提取链"""
    prompt = get_prompt_template("graph_extraction")
    return prompt | get_llm("graph_generator", temperature=0.1) | JsonOutputParser()

def create_consistency_sentinel_chain():
    """创建逻辑一致性校验链"""
    prompt = get_prompt_template("consistency_check")
    return prompt | get_llm("consistency_sentinel", temperature=0.1) | StrOutputParser()

def retrieve_with_rewriting(collection_name, query_text, recall_k, rerank_k, re_ranker, filter_dict=None):
    """
    带查询重写的综合检索逻辑。
    包含：重写查询 -> 向量数据库召回 (含元数据过滤) -> 重排序优化。
    """
    rewriter = create_query_rewrite_chain()
    rewritten_query = rewriter.invoke({"original_query": query_text})
    return retrieve_context(collection_name, rewritten_query, recall_k, re_ranker, rerank_k, filter_dict=filter_dict)
