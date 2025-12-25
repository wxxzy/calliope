"""
Vector Store Manager
负责管理ChromaDB向量数据库的连接、集合创建、数据索引和检索。
支持基于项目路径的动态客户端管理。
"""
import os
import chromadb
from typing import List, Optional
from langchain_chroma import Chroma
from infra.llm.embeddings import get_embedding_model
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# 使用 LRU Cache 管理客户端实例，避免重复创建，同时防止内存无限增长
# key 是 project_root
@lru_cache(maxsize=5)
def get_chroma_client(project_root: str):
    """
    获取指定项目的 ChromaDB 客户端单例。
    """
    chroma_path = os.path.join(project_root, "knowledge", "chroma_db")
    os.makedirs(chroma_path, exist_ok=True)
    
    try:
        client = chromadb.PersistentClient(path=chroma_path)
        logger.info(f"ChromaDB 客户端已初始化: {chroma_path}")
        return client
    except Exception as e:
        logger.error(f"初始化 ChromaDB 客户端失败 ({chroma_path}): {e}", exc_info=True)
        raise

def get_or_create_collection(project_root: str):
    """
    获取或创建一个ChromaDB集合。
    注意：在单项目模式下，collection_name 固定为 "main_collection" 或类似的通用名，
    因为项目本身已经由文件夹区分了。
    """
    client = get_chroma_client(project_root)
    embedding_function = get_embedding_model()
    
    COLLECTION_NAME = "project_knowledge"
    
    # 确保集合存在
    client.get_or_create_collection(name=COLLECTION_NAME)
    
    vectorstore = Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding_function=embedding_function
    )
    return vectorstore

def delete_collection(project_root: str):
    """删除当前项目的集合"""
    client = get_chroma_client(project_root)
    COLLECTION_NAME = "project_knowledge"
    try:
        client.delete_collection(name=COLLECTION_NAME)
        return True
    except Exception as e:
        logger.error(f"删除集合失败: {e}")
        return False

# --- 文本处理与索引 ---
def index_text(project_root: str, text: str, text_splitter, metadata: dict = None):
    if not text or not text.strip(): return

    chunks = text_splitter.split_text(text)
    vectorstore = get_or_create_collection(project_root)
    
    metadatas = [metadata] * len(chunks) if metadata else None
    logger.info(f"索引文本到项目 '{project_root}'。Meta: {metadata}")
    try:
        vectorstore.add_texts(texts=chunks, metadatas=metadatas)
        logger.info(f"成功索引 {len(chunks)} 个块。")
    except Exception as e:
        logger.error(f"索引失败: {e}", exc_info=True)

# --- 检索 ---
def retrieve_context(project_root: str, query: str, recall_k: int = 20, re_ranker=None, rerank_k: int = 5, filter_dict: dict = None) -> list[str]:
    vectorstore = get_or_create_collection(project_root)
    
    results_with_scores = vectorstore.similarity_search_with_score(query, k=recall_k, filter=filter_dict)
    retrieved_docs = [doc.page_content for doc, score in results_with_scores]

    if re_ranker and retrieved_docs:
        reranker_input = [(query, doc_content) for doc_content in retrieved_docs]
        scores = re_ranker.predict(reranker_input)
        ranked_docs_with_scores = sorted(zip(retrieved_docs, scores), key=lambda x: x[1], reverse=True)
        final_retrieved_docs = [doc for doc, score in ranked_docs_with_scores[:rerank_k]]
        return final_retrieved_docs
    else:
        return retrieved_docs[:rerank_k]

def get_collection_data(project_root: str) -> dict:
    client = get_chroma_client(project_root)
    COLLECTION_NAME = "project_knowledge"
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
        data = collection.get(include=['metadatas', 'documents'])
        return data
    except Exception as e:
        logger.error(f"获取数据失败: {e}")
        return {'ids': [], 'documents': [], 'metadatas': []}

def delete_by_metadata(project_root: str, filter_dict: dict):
    client = get_chroma_client(project_root)
    COLLECTION_NAME = "project_knowledge"
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
        collection.delete(where=filter_dict)
        return True
    except Exception as e:
        logger.error(f"删除失败: {e}")
        return False