"""
知识管理与 RAG 链模块 (Knowledge Chains)
定义了 RAG 查询重写、章节摘要、知识图谱提取及派系分析等 AI 逻辑。
"""
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from llm_provider import get_llm
from prompts import (
    QUERY_REWRITER_PROMPT, CHAPTER_SUMMARIZER_PROMPT, 
    CRITIC_PROMPT, GRAPH_EXTRACTION_PROMPT, COMMUNITY_NAMING_PROMPT,
    CONSISTENCY_CHECK_PROMPT
)
from vector_store_manager import retrieve_context
from chains.base import get_writing_style_instruction
import logging

logger = logging.getLogger(__name__)

def create_query_rewrite_chain():
    """创建查询重写链：将口语化描述转换为适合检索的关键词"""
    return QUERY_REWRITER_PROMPT | get_llm("query_rewriter") | StrOutputParser()

def create_chapter_summary_chain():
    """创建章节摘要链：用于为存入记忆库提供精简的情节概括及结构化元数据"""
    return CHAPTER_SUMMARIZER_PROMPT | get_llm("chapter_summarizer") | JsonOutputParser()

def create_critic_chain(writing_style: str = ""):
    """创建评论员链：提供专业的文学逻辑和文风评估反馈"""
    style_inst = get_writing_style_instruction(writing_style)
    return (
        RunnablePassthrough.assign(
            stage=lambda x: x.get("stage", "未知"),
            plan=lambda x: x.get("plan", ""),
            content_to_review=lambda x: x.get("content_to_review", ""),
            writing_style_instruction=lambda x: style_inst
        )
        | CRITIC_PROMPT | get_llm("critic", temperature=0.3) | StrOutputParser()
    )

def create_graph_extraction_chain():
    """创建知识图谱提取链：从文本中抽取结构化的实体关系三元组"""
    return GRAPH_EXTRACTION_PROMPT | get_llm("graph_generator", temperature=0.1) | JsonOutputParser()

def create_community_naming_chain():
    """创建派系命名链：根据角色分组信息生成具有文学感的组织名称"""
    return COMMUNITY_NAMING_PROMPT | get_llm("community_namer", temperature=0.3) | StrOutputParser()

def create_consistency_sentinel_chain():
    """创建逻辑一致性校验链：识别正文与图谱设定之间的冲突"""
    return CONSISTENCY_CHECK_PROMPT | get_llm("consistency_sentinel", temperature=0.1) | StrOutputParser()

def retrieve_with_rewriting(collection_name, query_text, recall_k, rerank_k, re_ranker, filter_dict=None):
    """
    带查询重写的综合检索逻辑。
    包含：重写查询 -> 向量数据库召回 (含元数据过滤) -> 重排序优化。
    """
    rewriter = create_query_rewrite_chain()
    rewritten_query = rewriter.invoke({"original_query": query_text})
    return retrieve_context(collection_name, rewritten_query, recall_k, re_ranker, rerank_k, filter_dict=filter_dict)
